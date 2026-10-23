"""ربط التصميم بالمحاكاة والتسعير والحساب المالي (طبقة بين الـ API والحسابات)."""

from collections.abc import Callable
from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.geo import point_from_db
from app.models import Component, DesignVersion, PriceItem, Project, Simulation, TariffRow, WeatherCache
from app.services import finance, pricing, pvgis, simulation, tariffs

WeatherFetcher = Callable[[float, float], dict]
QUOTE_LABELS = {
    "ar": {
        "module": "لوح شمسي {name} ({power:g} واط)",
        "inverter": "انفرتر",
        "racking": "هيكل التثبيت",
        "units": {"per_unit": "وحدة", "per_watt": "واط", "per_kwp": "kWp", "per_module": "لوح", "fixed": "مقطوع"},
    },
    "en": {
        "module": "PV module {name} ({power:g} W)",
        "inverter": "Inverter",
        "racking": "Mounting structure",
        "units": {"per_unit": "pcs", "per_watt": "W", "per_kwp": "kWp", "per_module": "modules", "fixed": "lump sum"},
    },
}


class StudyError(ValueError):
    pass


def default_fetcher(lat: float, lon: float) -> dict:
    return pvgis.fetch_tmy_json(lat, lon, get_settings().pvgis_base_url)


# ---------- التعرفة ----------
def tariff_from_row(row: TariffRow) -> tariffs.Tariff:
    tiers = tuple(tariffs.Tier(t.get("up_to_kwh"), float(t["rate_sar"])) for t in row.tiers)
    return tariffs.Tariff(row.code, tiers, vat=row.vat, export_rate_sar=row.export_rate_sar)


def project_tariff(db: Session, project: Project) -> tariffs.Tariff:
    row = db.get(TariffRow, project.tariff_code)
    if row is None:
        raise StudyError(f"التعرفة غير موجودة: {project.tariff_code}")
    return tariff_from_row(row)


def load_profile(project: Project) -> list[float]:
    return tariffs.LOAD_PROFILES.get(project.customer.customer_type, tariffs.LOAD_PROFILES["residential"])


# ---------- ملخص التصميم ----------
def design_totals(design: DesignVersion) -> dict:
    module_count = 0
    dc_w = 0.0
    for area in design.roof_areas:
        for arr in area.arrays:
            module_count += len(arr.modules)
            dc_w += len(arr.modules) * float(arr.module.specs.get("power_w", 0))
    ac_kw = 0.0
    if design.inverter is not None:
        ac_kw = float(design.inverter.specs.get("ac_power_kw", 0)) * design.inverter_count
    return {"module_count": module_count, "dc_kwp": round(dc_w / 1000, 3), "ac_kw": round(ac_kw, 3)}


# ---------- الطقس ----------
def weather_payload(db: Session, lat: float, lon: float, fetcher: WeatherFetcher) -> dict:
    """السنة النموذجية من الذاكرة المؤقتة أو من PVGIS (الدقة 0.01° ≈ 1 كم أدق من شبكة PVGIS)."""
    key_lat, key_lon = round(lat, 2), round(lon, 2)
    cached = db.scalar(
        select(WeatherCache).where(
            WeatherCache.latitude == key_lat, WeatherCache.longitude == key_lon, WeatherCache.source == "pvgis_tmy"
        )
    )
    if cached:
        return cached.payload
    payload = fetcher(key_lat, key_lon)
    pvgis.parse_tmy(payload)  # تحقق قبل الحفظ
    db.add(WeatherCache(latitude=key_lat, longitude=key_lon, source="pvgis_tmy", payload=payload))
    db.flush()
    return payload


# ---------- المحاكاة ----------
def array_inputs(design: DesignVersion) -> list[simulation.ArrayInput]:
    inputs = []
    for area in design.roof_areas:
        for index, arr in enumerate(area.arrays, start=1):
            if not arr.modules:
                continue
            specs = arr.module.specs
            inputs.append(
                simulation.ArrayInput(
                    name=f"{area.name or 'مساحة'} - {index}",
                    module_count=len(arr.modules),
                    module_power_w=float(specs["power_w"]),
                    tilt_deg=arr.tilt_deg,
                    azimuth_deg=arr.azimuth_deg,
                    gamma_pdc=float(specs.get("gamma_pdc_pct", -0.35)) / 100,
                    mounting=arr.mounting,
                )
            )
    return inputs


def run_simulation(db: Session, design: DesignVersion, losses_in: dict, fetcher: WeatherFetcher, user_id: int) -> Simulation:
    arrays = array_inputs(design)
    if not arrays:
        raise StudyError("لا توجد ألواح في هذا التصميم؛ وزّع الألواح أولًا")
    loc = point_from_db(design.project.location)
    try:
        payload = weather_payload(db, loc["lat"], loc["lon"], fetcher)
    except pvgis.PVGISError as exc:
        raise StudyError(str(exc)) from exc
    weather, meta = pvgis.parse_tmy(payload)

    totals = design_totals(design)
    inverter_eff = 0.98
    if design.inverter is not None:
        inverter_eff = float(design.inverter.specs.get("efficiency_pct", 98.0)) / 100
    losses = simulation.LossInput(
        albedo=losses_in["albedo"],
        soiling_monthly=[v / 100 for v in losses_in["soiling_monthly_pct"]],
        mismatch=losses_in["mismatch_pct"] / 100,
        dc_wiring=losses_in["dc_wiring_pct"] / 100,
        lid=losses_in["lid_pct"] / 100,
        inverter_efficiency=inverter_eff,
        ac_wiring=losses_in["ac_wiring_pct"] / 100,
        transformer=losses_in["transformer_pct"] / 100,
    )
    result = simulation.simulate(
        weather,
        meta["latitude"],
        meta["longitude"],
        meta["elevation"],
        arrays,
        totals["ac_kw"] or None,
        losses,
        get_settings().local_timezone,
    )
    sim = Simulation(
        design_id=design.id,
        weather_meta=meta,
        inputs={
            "losses": losses_in,
            "inverter_efficiency": inverter_eff,
            "arrays": [asdict(a) for a in arrays],
            "ac_kw_assumed": totals["ac_kw"] == 0,
        },
        results=result.to_dict(),
        created_by_id=user_id,
    )
    db.add(sim)
    return sim


# ---------- عرض السعر ----------
def build_quote(db: Session, design: DesignVersion, vat: float, finance_in: dict, language: str = "ar") -> pricing.Quote:
    labels = QUOTE_LABELS[language]
    totals = design_totals(design)
    quote = pricing.Quote(discount_pct=finance_in.get("discount_pct", 0.0), vat=vat)

    per_module: dict[int, tuple[Component, int]] = {}
    for area in design.roof_areas:
        for arr in area.arrays:
            if arr.modules:
                comp, count = per_module.get(arr.module_id, (arr.module, 0))
                per_module[arr.module_id] = (comp, count + len(arr.modules))
    for comp, count in per_module.values():
        quote.lines.append(
            pricing.module_line(
                labels["module"].format(name=f"{comp.manufacturer} {comp.model}", power=float(comp.specs["power_w"])),
                comp.price_sar,
                comp.price_unit,
                count,
                float(comp.specs["power_w"]),
            )
        )
    for comp, label, units in (
        (design.inverter, labels["inverter"], design.inverter_count),
        (design.racking, labels["racking"], 1),
    ):
        if comp is None:
            continue
        qty = pricing.quantity_for(comp.price_unit, units=units, module_count=totals["module_count"], dc_kwp=totals["dc_kwp"])
        quote.lines.append(pricing.QuoteLine(f"{label} {comp.manufacturer} {comp.model}", qty, comp.price_unit, comp.price_sar))

    items = db.scalars(select(PriceItem).where(PriceItem.is_active.is_(True)).order_by(PriceItem.sort_order, PriceItem.id))
    for item in items:
        qty = pricing.quantity_for(item.unit, units=1, module_count=totals["module_count"], dc_kwp=totals["dc_kwp"])
        quote.lines.append(pricing.QuoteLine(item.name, qty, item.unit, item.unit_price_sar))
    for extra in finance_in.get("extra_lines", []):
        quote.lines.append(
            pricing.QuoteLine(str(extra.get("description", "")), float(extra.get("quantity", 1)), "per_unit", float(extra.get("unit_price_sar", 0)))
        )
    return quote


# ---------- الدراسة المالية ----------
def financial_study(db: Session, sim: Simulation, finance_in: dict, language: str = "ar") -> tuple[dict, dict]:
    design = sim.design
    project = design.project
    if not project.monthly_consumption_kwh:
        raise StudyError("أدخل الاستهلاك الشهري للمشروع قبل الدراسة المالية")
    tariff = project_tariff(db, project)
    quote = build_quote(db, design, tariff.vat, finance_in, language)
    capex = finance_in.get("override_total_sar") or quote.total_sar
    if capex <= 0:
        raise StudyError("تكلفة النظام صفر؛ راجع أسعار المكونات")

    params = finance.FinanceParams(
        years=finance_in["years"],
        discount_rate=finance_in["discount_rate_pct"] / 100,
        degradation_rate=finance_in["degradation_pct"] / 100,
        om_rate=finance_in["om_pct"] / 100,
        tariff_escalation=finance_in["tariff_escalation_pct"] / 100,
        inverter_replacement_year=finance_in.get("inverter_replacement_year"),
        inverter_replacement_cost_sar=finance_in.get("inverter_replacement_cost_sar", 0.0),
    )
    result = finance.analyze(
        capex,
        project.monthly_consumption_kwh,
        sim.results["production_matrix_kwh"],
        tariff,
        load_profile(project),
        params,
    )
    first_year = tariffs.net_billing_year(
        project.monthly_consumption_kwh, sim.results["production_matrix_kwh"], tariff, load_profile(project)
    )
    financial = asdict(result)
    financial["params"] = finance_in
    financial["tariff"] = {"code": tariff.code, "name": db.get(TariffRow, tariff.code).name, "tiers": [asdict(t) for t in tariff.tiers], "vat": tariff.vat, "export_rate_sar": tariff.export_rate_sar}
    financial["first_year_months"] = [
        asdict(m) | {"savings_sar": m.savings_sar, "payable_sar": m.payable_sar} for m in first_year.months
    ]
    financial["first_year_expired_credit_sar"] = first_year.expired_credit_sar
    quote_dict = quote.to_dict()
    quote_dict["capex_sar"] = round(capex, 2)
    for line in quote_dict["lines"]:
        line["unit_label"] = QUOTE_LABELS[language]["units"].get(line["unit"], line["unit"])
    return quote_dict, financial
