"""محرك المحاكاة للمرحلة الأولى: سلسلة pvlib ساعية بدون تظليل.

الإشعاع الأفقي ← موقع الشمس ← الإشعاع على سطح اللوح (Perez + Albedo) ← زاوية السقوط (IAM)
← الاتساخ ← حرارة الخلية (Faiman) ← قدرة DC (PVWatts) ← خسائر DC ← الانفرتر مع القص ← خسائر AC.
المرحلة الثانية تستبدل PVWatts بنموذج الدايود الواحد ومنحنيات الانفرتر.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import pvlib

# معاملات Faiman (W/m²K, W·s/m³K) حسب طريقة التركيب
FAIMAN_BY_MOUNTING = {
    "tilted_rows": (25.0, 6.84),  # هيكل مائل مفتوح من الخلف
    "flush": (18.0, 3.0),  # ملاصق للسطح، تهوية أقل
    "ground": (25.0, 6.84),
}


@dataclass
class ArrayInput:
    name: str
    module_count: int
    module_power_w: float
    tilt_deg: float
    azimuth_deg: float  # 180 = جنوب (اصطلاح pvlib)
    gamma_pdc: float = -0.0035  # معامل حرارة القدرة لكل درجة
    mounting: str = "tilted_rows"

    @property
    def dc_kw(self) -> float:
        return self.module_count * self.module_power_w / 1000.0


@dataclass
class LossInput:
    albedo: float = 0.25
    soiling_monthly: list[float] = field(default_factory=lambda: [0.04] * 12)
    mismatch: float = 0.02
    dc_wiring: float = 0.015
    lid: float = 0.015  # تدهور الضوء الأولي وتفاوت القدرة الاسمية
    inverter_efficiency: float = 0.98
    ac_wiring: float = 0.01
    transformer: float = 0.0


@dataclass
class SimulationResult:
    dc_kwp: float
    ac_kw: float
    annual_ghi_kwh_m2: float
    annual_poa_kwh_m2: float
    annual_energy_kwh: float
    specific_yield_kwh_kwp: float
    performance_ratio: float
    monthly_energy_kwh: list[float]
    monthly_poa_kwh_m2: list[float]
    production_matrix_kwh: list[list[float]]  # 12 شهر × 24 ساعة محلية
    losses: list[dict]  # مخطط الشلال: الخطوة، الطاقة بعدها، النسبة
    arrays: list[dict]

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def _inverter(pdc: pd.Series, pac0: float, eta_nom: float, eta_ref: float = 0.9637) -> tuple[pd.Series, pd.Series]:
    """منحنى كفاءة PVWatts (نفس معادلة pvlib.inverter.pvwatts) قبل القص وبعده."""
    pdc0 = pac0 / eta_nom
    zeta = (pdc / pdc0).where(pdc > 0, 1.0)
    eta = eta_nom / eta_ref * (-0.0162 * zeta - 0.0059 / zeta + 0.9858)
    unclipped = (eta * pdc).where(pdc > 0, 0.0).clip(lower=0)
    return unclipped, unclipped.clip(upper=pac0)


def _check_inputs(weather: pd.DataFrame, arrays: list[ArrayInput], losses: LossInput) -> None:
    if not arrays or sum(a.module_count for a in arrays) == 0:
        raise ValueError("لا توجد ألواح في التصميم")
    if len(losses.soiling_monthly) != 12:
        raise ValueError("الاتساخ يحتاج 12 قيمة شهرية")
    if weather.index.tz is None:
        raise ValueError("فهرس الطقس يجب أن يحمل منطقة زمنية")


def simulate(
    weather: pd.DataFrame,
    latitude: float,
    longitude: float,
    elevation: float,
    arrays: list[ArrayInput],
    ac_kw: float | None,
    losses: LossInput | None = None,
    local_tz: str = "Asia/Riyadh",
) -> SimulationResult:
    losses = losses or LossInput()
    _check_inputs(weather, arrays, losses)
    index = weather.index
    dc_kwp = sum(a.dc_kw for a in arrays)
    ac_kw = ac_kw if ac_kw and ac_kw > 0 else dc_kwp

    location = pvlib.location.Location(latitude, longitude, altitude=elevation)
    solpos = location.get_solarposition(index, pressure=weather.get("pressure"), temperature=weather["temp_air"])
    dni_extra = pvlib.irradiance.get_extra_radiation(index)
    airmass = pvlib.atmosphere.get_relative_airmass(solpos["apparent_zenith"])
    soiling = np.array(losses.soiling_monthly)[index.month - 1]

    # الطاقة (Wh) بعد كل خطوة، مجمعة على كل المصفوفات
    steps = {k: 0.0 for k in ("nominal", "iam", "soiling", "temperature")}
    dc_total = pd.Series(0.0, index=index)
    poa_weighted = pd.Series(0.0, index=index)
    array_reports = []

    for arr in arrays:
        poa = pvlib.irradiance.get_total_irradiance(
            arr.tilt_deg,
            arr.azimuth_deg,
            solpos["apparent_zenith"],
            solpos["azimuth"],
            weather["dni"],
            weather["ghi"],
            weather["dhi"],
            dni_extra=dni_extra,
            airmass=airmass,
            albedo=losses.albedo,
            model="perez",
        ).fillna(0.0)
        aoi = pvlib.irradiance.aoi(arr.tilt_deg, arr.azimuth_deg, solpos["apparent_zenith"], solpos["azimuth"])
        iam = pvlib.iam.physical(aoi).fillna(0.0)
        poa_global = poa["poa_global"].clip(lower=0)
        poa_iam = (poa["poa_direct"] * iam + poa["poa_diffuse"]).clip(lower=0)
        poa_eff = poa_iam * (1 - soiling)

        u0, u1 = FAIMAN_BY_MOUNTING.get(arr.mounting, FAIMAN_BY_MOUNTING["tilted_rows"])
        temp_cell = pvlib.temperature.faiman(poa_global, weather["temp_air"], weather["wind_speed"], u0, u1)
        pdc0 = arr.dc_kw * 1000.0
        dc = pvlib.pvsystem.pvwatts_dc(poa_eff, temp_cell, pdc0, arr.gamma_pdc).clip(lower=0)

        kw_factor = arr.dc_kw  # (W/m²)/1000 × kWp = kW، والجمع الساعي = kWh
        steps["nominal"] += poa_global.sum() * kw_factor
        steps["iam"] += poa_iam.sum() * kw_factor
        steps["soiling"] += poa_eff.sum() * kw_factor
        steps["temperature"] += dc.sum()
        dc_total += dc
        poa_weighted += poa_global * arr.dc_kw
        array_reports.append(
            {
                "name": arr.name,
                "module_count": arr.module_count,
                "dc_kwp": round(arr.dc_kw, 3),
                "tilt_deg": arr.tilt_deg,
                "azimuth_deg": arr.azimuth_deg,
                "annual_poa_kwh_m2": round(float(poa_global.sum()) / 1000.0, 1),
                "dc_energy_kwh": round(float(dc.sum()) / 1000.0, 1),
            }
        )

    dc_factor = (1 - losses.mismatch) * (1 - losses.dc_wiring) * (1 - losses.lid)
    dc_net = dc_total * dc_factor
    after_mismatch = steps["temperature"] * (1 - losses.mismatch)
    after_wiring = after_mismatch * (1 - losses.dc_wiring)
    after_lid = after_wiring * (1 - losses.lid)

    unclipped, ac = _inverter(dc_net, ac_kw * 1000.0, losses.inverter_efficiency)
    ac_net = ac * (1 - losses.ac_wiring) * (1 - losses.transformer)

    energy_kwh = float(ac_net.sum()) / 1000.0
    poa_avg = poa_weighted / dc_kwp
    annual_poa = float(poa_avg.sum()) / 1000.0

    waterfall = [
        ("poa", "الإشعاع على سطح اللوح × القدرة الاسمية", steps["nominal"]),
        ("iam", "زاوية سقوط الأشعة (IAM)", steps["iam"]),
        ("soiling", "الاتساخ والغبار", steps["soiling"]),
        ("temperature", "حرارة الخلايا", steps["temperature"]),
        ("mismatch", "عدم التطابق", after_mismatch),
        ("dc_wiring", "أسلاك DC", after_wiring),
        ("lid", "التدهور الأولي وتفاوت القدرة", after_lid),
        ("inverter", "كفاءة الانفرتر", unclipped.sum()),
        ("clipping", "القص عند حد قدرة AC", ac.sum()),
        ("ac", "أسلاك AC والمحولات", ac_net.sum()),
    ]
    loss_rows, previous = [], None
    for key, label, wh in waterfall:
        kwh = float(wh) / 1000.0
        loss_pct = 0.0 if previous in (None, 0) else (previous - kwh) / previous * 100
        loss_rows.append({"key": key, "label": label, "energy_kwh": round(kwh, 1), "loss_pct": round(loss_pct, 2)})
        previous = kwh

    local = ac_net.tz_convert(local_tz) / 1000.0
    matrix = local.groupby([local.index.month, local.index.hour]).sum()
    production_matrix = [[round(float(matrix.get((m, h), 0.0)), 3) for h in range(24)] for m in range(1, 13)]
    monthly = [round(sum(row), 1) for row in production_matrix]
    poa_local = poa_avg.tz_convert(local_tz)
    monthly_poa = [round(float(v) / 1000.0, 1) for v in poa_local.groupby(poa_local.index.month).sum().reindex(range(1, 13), fill_value=0)]

    return SimulationResult(
        dc_kwp=round(dc_kwp, 3),
        ac_kw=round(ac_kw, 3),
        annual_ghi_kwh_m2=round(float(weather["ghi"].sum()) / 1000.0, 1),
        annual_poa_kwh_m2=round(annual_poa, 1),
        annual_energy_kwh=round(energy_kwh, 1),
        specific_yield_kwh_kwp=round(energy_kwh / dc_kwp, 1),
        performance_ratio=round(energy_kwh / (annual_poa * dc_kwp), 4) if annual_poa else 0.0,
        monthly_energy_kwh=monthly,
        monthly_poa_kwh_m2=monthly_poa,
        production_matrix_kwh=production_matrix,
        losses=loss_rows,
        arrays=array_reports,
    )
