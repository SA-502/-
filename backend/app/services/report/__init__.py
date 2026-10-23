"""توليد تقرير الدراسة وعرض السعر PDF من قالب HTML عبر WeasyPrint (دعم كامل للعربية RTL)."""

import math
from datetime import timedelta
from pathlib import Path

from geoalchemy2.shape import to_shape
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from app.config import get_settings
from app.geo import point_from_db
from app.models import Report, Simulation, User
from app.services.report import charts
from app.services.study import design_totals

APP_DIR = Path(__file__).resolve().parents[2]
TEMPLATES = Path(__file__).parent / "templates"
EARTH_M_PER_DEG = 111_320.0

MONTHS = {
    "ar": ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"],
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}

TEXT = {
    "ar": {
        "dir": "rtl",
        "title": "دراسة نظام طاقة شمسية وعرض سعر",
        "report_no": "رقم العرض",
        "date": "التاريخ",
        "valid_until": "صالح حتى",
        "prepared_by": "إعداد",
        "customer": "العميل",
        "project": "المشروع",
        "location": "الموقع",
        "summary": "ملخص الدراسة",
        "system_size": "قدرة النظام",
        "modules": "عدد الألواح",
        "annual_energy": "الإنتاج السنوي",
        "specific_yield": "العائد النوعي",
        "first_year_savings": "توفير السنة الأولى",
        "payback": "فترة الاسترداد",
        "total_price": "السعر الإجمالي",
        "coverage": "تغطية الاستهلاك",
        "design": "التصميم",
        "plan": "مخطط توزيع الألواح",
        "north": "شمال",
        "area": "المساحة",
        "tilt": "الميل",
        "azimuth": "الاتجاه",
        "components": "المكونات",
        "module": "اللوح",
        "inverter": "الانفرتر",
        "dc_ac": "نسبة DC/AC",
        "not_selected": "غير محدد",
        "production": "الإنتاج والاستهلاك",
        "legend_prod": "الإنتاج الشمسي (kWh)",
        "legend_cons": "الاستهلاك (kWh)",
        "month": "الشهر",
        "produced": "الإنتاج",
        "consumed": "الاستهلاك",
        "self_used": "استهلاك ذاتي",
        "exported": "مُصدَّر للشبكة",
        "bill_before": "الفاتورة قبل",
        "bill_after": "الفاتورة بعد",
        "savings": "التوفير",
        "total": "الإجمالي",
        "losses": "دليل الخسائر",
        "losses_note": "من الإشعاع على سطح الألواح حتى الطاقة الصافية المسلَّمة",
        "step": "المرحلة",
        "energy_after": "الطاقة بعدها (kWh)",
        "loss": "الخسارة",
        "pr": "نسبة الأداء (PR)",
        "quote": "عرض السعر",
        "item": "البند",
        "qty": "الكمية",
        "unit_price": "سعر الوحدة",
        "line_total": "المجموع",
        "subtotal": "المجموع قبل الخصم",
        "discount": "الخصم",
        "net": "الصافي قبل الضريبة",
        "vat": "ضريبة القيمة المضافة",
        "grand_total": "الإجمالي شامل الضريبة",
        "financial": "الجدوى المالية",
        "npv": "صافي القيمة الحالية",
        "irr": "العائد الداخلي",
        "discounted_payback": "الاسترداد المخصوم",
        "lcoe": "تكلفة الكيلوواط ساعة (LCOE)",
        "lifetime_savings": "إجمالي التوفير",
        "roi": "العائد على الاستثمار",
        "cashflow": "التدفق النقدي التراكمي",
        "count": "العدد",
        "year": "السنة",
        "net_cf": "صافي التدفق",
        "cumulative": "التراكمي",
        "om": "تشغيل وصيانة",
        "assumptions": "الافتراضات والملاحظات",
        "years": "سنة",
        "sar": "ر.س",
        "not_reached": "لا يسترد خلال العمر",
        "weather": "بيانات الطقس: سنة نموذجية (TMY) من PVGIS ({db}) للإحداثيات {lat:.3f}، {lon:.3f}.",
        "tariff_line": "التعرفة: {name} بالشرائح {tiers} ريال/kWh، ضريبة {vat:.0f}%، وسعر الفائض المُصدَّر {export} ريال/kWh.",
        "finance_line": "عمر الدراسة {years} سنة، تراجع الإنتاج {deg}% سنويًا، التشغيل والصيانة {om}% من التكلفة سنويًا، معدل الخصم {disc}%، زيادة التعرفة {esc}% سنويًا.",
        "model_line": "المحاكاة ساعية لـ 8760 ساعة بمكتبة pvlib (نموذج Perez للإشعاع، Faiman للحرارة، PVWatts للألواح والانفرتر) بدون حساب التظليل في هذه النسخة.",
        "ac_assumed": "لم يُحدد انفرتر؛ افتُرضت قدرة AC مساوية لقدرة الألواح.",
        "self_line": "الاستهلاك الذاتي مقدَّر من نمط حمل يومي نموذجي لنوع العميل؛ الأرقام الفعلية تختلف حسب نمط الاستخدام.",
        "disclaimer": "هذه الدراسة تقديرية مبنية على بيانات طقس تاريخية، والإنتاج الفعلي قد يختلف حسب الطقس والتشغيل والصيانة.",
        "page": "صفحة",
    },
    "en": {
        "dir": "ltr",
        "title": "Solar PV System Study & Quotation",
        "report_no": "Quote No.",
        "date": "Date",
        "valid_until": "Valid until",
        "prepared_by": "Prepared by",
        "customer": "Customer",
        "project": "Project",
        "location": "Location",
        "summary": "Summary",
        "system_size": "System size",
        "modules": "Modules",
        "annual_energy": "Annual energy",
        "specific_yield": "Specific yield",
        "first_year_savings": "Year-1 savings",
        "payback": "Payback",
        "total_price": "Total price",
        "coverage": "Consumption covered",
        "design": "Design",
        "plan": "Module layout",
        "north": "N",
        "area": "Area",
        "tilt": "Tilt",
        "azimuth": "Azimuth",
        "components": "Components",
        "module": "Module",
        "inverter": "Inverter",
        "dc_ac": "DC/AC ratio",
        "not_selected": "Not selected",
        "production": "Production & consumption",
        "legend_prod": "Solar production (kWh)",
        "legend_cons": "Consumption (kWh)",
        "month": "Month",
        "produced": "Produced",
        "consumed": "Consumed",
        "self_used": "Self-consumed",
        "exported": "Exported",
        "bill_before": "Bill before",
        "bill_after": "Bill after",
        "savings": "Savings",
        "total": "Total",
        "losses": "Loss diagram",
        "losses_note": "From plane-of-array irradiance to net delivered energy",
        "step": "Step",
        "energy_after": "Energy after (kWh)",
        "loss": "Loss",
        "pr": "Performance ratio (PR)",
        "quote": "Quotation",
        "item": "Item",
        "qty": "Qty",
        "unit_price": "Unit price",
        "line_total": "Total",
        "subtotal": "Subtotal",
        "discount": "Discount",
        "net": "Net before VAT",
        "vat": "VAT",
        "grand_total": "Total incl. VAT",
        "financial": "Financial analysis",
        "npv": "Net present value",
        "irr": "IRR",
        "discounted_payback": "Discounted payback",
        "lcoe": "LCOE",
        "lifetime_savings": "Lifetime savings",
        "roi": "ROI",
        "cashflow": "Cumulative cash flow",
        "count": "Qty",
        "year": "Year",
        "net_cf": "Net cash flow",
        "cumulative": "Cumulative",
        "om": "O&M",
        "assumptions": "Assumptions & notes",
        "years": "years",
        "sar": "SAR",
        "not_reached": "Not reached",
        "weather": "Weather: PVGIS typical meteorological year ({db}) at {lat:.3f}, {lon:.3f}.",
        "tariff_line": "Tariff: {name}, tiers {tiers} SAR/kWh, VAT {vat:.0f}%, export credit {export} SAR/kWh.",
        "finance_line": "Study period {years} years, degradation {deg}%/yr, O&M {om}% of capex/yr, discount rate {disc}%, tariff escalation {esc}%/yr.",
        "model_line": "Hourly 8760 h simulation with pvlib (Perez transposition, Faiman cell temperature, PVWatts module and inverter); shading not modelled in this version.",
        "ac_assumed": "No inverter selected; AC capacity assumed equal to DC capacity.",
        "self_line": "Self-consumption is estimated from a typical daily load profile for the customer type.",
        "disclaimer": "This is an estimate based on historical weather; actual output varies with weather, operation and maintenance.",
        "page": "Page",
    },
}


def _to_local(lon: float, lat: float, origin: dict) -> tuple[float, float]:
    """إسقاط مستطيلي حول موقع المشروع (يكفي لمساحات بحجم سطح أو محطة)."""
    return (
        (lon - origin["lon"]) * EARTH_M_PER_DEG * math.cos(math.radians(origin["lat"])),
        (lat - origin["lat"]) * EARTH_M_PER_DEG,
    )


def _footprint(module_specs: dict, orientation: str, tilt_deg: float) -> tuple[float, float]:
    """(العرض على امتداد الصف، العمق الأفقي) للوح بالمتر — نفس معادلة الواجهة."""
    length, width = float(module_specs["length_m"]), float(module_specs["width_m"])
    along, slope = (width, length) if orientation == "portrait" else (length, width)
    return along, slope * math.cos(math.radians(tilt_deg))


def plan_drawing(sim: Simulation, north_label: str) -> str:
    design = sim.design
    origin = point_from_db(design.project.location)
    areas, modules = [], []
    for area in design.roof_areas:
        ring = [_to_local(x, y, origin) for x, y in to_shape(area.geometry).exterior.coords]
        areas.append({"ring": ring})
        for arr in area.arrays:
            w, d = _footprint(arr.module.specs, arr.orientation, arr.tilt_deg)
            modules += [{"x": m.x, "y": m.y, "w": w, "d": d, "rot": m.rotation_deg} for m in arr.modules]
    obstructions = [[_to_local(x, y, origin) for x, y in to_shape(o.geometry).exterior.coords] for o in design.obstructions]
    return charts.plan_svg(areas, obstructions, modules, north_label)


def _area_rows(sim: Simulation) -> list[dict]:
    rows = []
    for area in sim.design.roof_areas:
        geom = to_shape(area.geometry)
        lat = geom.centroid.y
        # مساحة تقريبية بالمتر المربع
        sq_m = geom.area * EARTH_M_PER_DEG**2 * math.cos(math.radians(lat))
        for arr in area.arrays:
            if not arr.modules:
                continue
            rows.append(
                {
                    "name": area.name,
                    "area_m2": sq_m,
                    "modules": len(arr.modules),
                    "kwp": len(arr.modules) * float(arr.module.specs["power_w"]) / 1000,
                    "tilt": arr.tilt_deg,
                    "azimuth": arr.azimuth_deg,
                }
            )
    return rows


def build_context(sim: Simulation, report: Report, user: User) -> dict:
    settings = get_settings()
    lang = report.language
    t = TEXT[lang]
    design = sim.design
    project = design.project
    results = sim.results
    fin = report.financial
    totals = design_totals(design)
    consumption = project.monthly_consumption_kwh or [0.0] * 12
    location = point_from_db(project.location)
    tariff = fin["tariff"]
    params = fin["params"]
    tiers = " / ".join(f"{tier['rate_sar']:g}" for tier in tariff["tiers"])

    modules = {}
    for area in design.roof_areas:
        for arr in area.arrays:
            if arr.modules:
                modules[arr.module_id] = arr.module

    notes = [
        t["weather"].format(db=sim.weather_meta.get("radiation_db") or "SARAH", lat=location["lat"], lon=location["lon"]),
        t["model_line"],
        t["tariff_line"].format(name=tariff.get("name", tariff["code"]), tiers=tiers, vat=tariff["vat"] * 100, export=f"{tariff['export_rate_sar']:g}"),
        t["finance_line"].format(
            years=params["years"],
            deg=f"{params['degradation_pct']:g}",
            om=f"{params['om_pct']:g}",
            disc=f"{params['discount_rate_pct']:g}",
            esc=f"{params['tariff_escalation_pct']:g}",
        ),
        t["self_line"],
    ]
    if sim.inputs.get("ac_kw_assumed"):
        notes.append(t["ac_assumed"])
    notes.append(t["disclaimer"])

    annual = results["annual_energy_kwh"]
    return {
        "t": t,
        "lang": lang,
        "months": MONTHS[lang],
        "company": settings,
        "logo": Path(settings.company_logo_path).resolve().as_uri() if settings.company_logo_path else None,
        "report": report,
        "issued": report.created_at,
        "valid_until": report.created_at + timedelta(days=settings.quote_validity_days),
        "user": user,
        "project": project,
        "customer": project.customer,
        "location": location,
        "design": design,
        "totals": totals,
        "results": results,
        "quote": report.quote,
        "fin": fin,
        "consumption": consumption,
        "coverage_pct": annual / sum(consumption) * 100 if sum(consumption) else None,
        "modules": list(modules.values()),
        "area_rows": _area_rows(sim),
        "dc_ac": totals["dc_kwp"] / totals["ac_kw"] if totals["ac_kw"] else None,
        "notes": notes,
        "monthly_chart": Markup(charts.monthly_chart(results["monthly_energy_kwh"], consumption, MONTHS[lang], (t["legend_prod"], t["legend_cons"]))),
        "cashflow_chart": Markup(charts.cashflow_chart([r["cumulative_sar"] for r in fin["rows"]], fin["capex_sar"])),
        "max_loss": max([l["loss_pct"] for l in results["losses"][1:]] + [1.0]),
        "plan": Markup(plan_drawing(sim, t["north"])),
    }


def _num(value, digits: int = 0) -> str:
    if value is None:
        return "—"
    return f"{value:,.{digits}f}"


_env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))
_env.filters["num"] = _num


def render_html(sim: Simulation, report: Report, user: User) -> str:
    return _env.get_template("report.html").render(**build_context(sim, report, user))


def render_pdf(sim: Simulation, report: Report, user: User) -> bytes:
    from weasyprint import HTML

    return HTML(string=render_html(sim, report, user), base_url=str(APP_DIR)).write_pdf()
