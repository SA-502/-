"""تعرفة الكهرباء بالشرائح، وتحويل الفاتورة إلى استهلاك، وحساب الفاتورة بعد النظام الشمسي."""

from dataclasses import dataclass, field

# أنواع العملاء المدعومة (تطابق customer_type في قاعدة البيانات)
CUSTOMER_TYPES = ("residential", "commercial", "industrial", "agricultural", "governmental")


@dataclass(frozen=True)
class Tier:
    # الحد الأعلى للشريحة بالكيلوواط ساعة شهريًا؛ None = بلا حد
    up_to_kwh: float | None
    rate_sar: float


@dataclass(frozen=True)
class Tariff:
    code: str
    tiers: tuple[Tier, ...]
    vat: float = 0.15
    # سعر احتساب الطاقة الفائضة المصدَّرة للشبكة (ريال/kWh)
    export_rate_sar: float = 0.0

    def __post_init__(self):
        if not self.tiers:
            raise ValueError("tariff needs at least one tier")
        limits = [t.up_to_kwh for t in self.tiers[:-1]]
        if any(lim is None for lim in limits) or limits != sorted(limits):
            raise ValueError("tiers must be ascending and only the last may be open-ended")


# قيم افتراضية تُزرع في قاعدة البيانات ويعدّلها المدير من شاشة الأسعار.
# السكني والزراعي والصناعي والحكومي: جدول الشركة السعودية للكهرباء المطبق منذ 2018-01-01.
# التجاري: 0.22/0.32 حسب تقارير 2026 (يحتاج تأكيدًا).
# سعر التصدير: المقترح من هيئة تنظيم الكهرباء (0.07 سكني، 0.05 لغيره) — يحتاج تأكيدًا عند الاعتماد.
DEFAULT_TARIFFS: dict[str, Tariff] = {
    "residential": Tariff("residential", (Tier(6000, 0.18), Tier(None, 0.30)), export_rate_sar=0.07),
    "commercial": Tariff("commercial", (Tier(6000, 0.22), Tier(None, 0.32)), export_rate_sar=0.05),
    "industrial": Tariff("industrial", (Tier(None, 0.18),), export_rate_sar=0.05),
    "agricultural": Tariff("agricultural", (Tier(6000, 0.16), Tier(None, 0.20)), export_rate_sar=0.05),
    "governmental": Tariff("governmental", (Tier(None, 0.32),), export_rate_sar=0.05),
}


def energy_charge(kwh: float, tariff: Tariff) -> float:
    """قيمة الاستهلاك الشهري بالشرائح قبل الضريبة."""
    if kwh <= 0:
        return 0.0
    total, lower = 0.0, 0.0
    for tier in tariff.tiers:
        upper = tier.up_to_kwh if tier.up_to_kwh is not None else float("inf")
        if kwh > lower:
            total += (min(kwh, upper) - lower) * tier.rate_sar
        lower = upper
    return total


def monthly_bill(kwh: float, tariff: Tariff, include_vat: bool = True) -> float:
    charge = energy_charge(kwh, tariff)
    return charge * (1 + tariff.vat) if include_vat else charge


def kwh_from_bill(bill_sar: float, tariff: Tariff, includes_vat: bool = True) -> float:
    """عكس الفاتورة الشهرية إلى استهلاك kWh."""
    charge = bill_sar / (1 + tariff.vat) if includes_vat else bill_sar
    if charge <= 0:
        return 0.0
    kwh, lower, spent = 0.0, 0.0, 0.0
    for tier in tariff.tiers:
        upper = tier.up_to_kwh if tier.up_to_kwh is not None else float("inf")
        tier_cost = (upper - lower) * tier.rate_sar
        if spent + tier_cost >= charge:
            return lower + (charge - spent) / tier.rate_sar
        spent += tier_cost
        kwh = upper
        lower = upper
    return kwh


# شكل الحمل اليومي (24 ساعة بالتوقيت المحلي) لكل نوع عميل، يُستخدم لتقدير
# الاستهلاك الذاتي اللحظي من الإنتاج الشمسي في نظام صافي الفوترة.
_RAW_PROFILES = {
    # سكني: تكييف بعد الظهر والمساء
    "residential": [3, 3, 3, 3, 3, 3, 3, 3.5, 4, 4, 4.5, 5, 5, 5.5, 5.5, 5.5, 5.5, 5.5, 5, 5, 4.5, 4, 3.5, 3],
    # تجاري: ساعات العمل 8–23
    "commercial": [1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 2, 3, 5, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 5.5, 5, 3.5, 2],
    # صناعي: تشغيل شبه مستمر مع ذروة نهارية
    "industrial": [3, 3, 3, 3, 3, 3, 3.5, 4.5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 4.5, 4, 3.5, 3, 3, 3, 3],
    # زراعي: ضخ نهاري
    "agricultural": [1, 1, 1, 1, 1, 1.5, 3, 5, 6, 6.5, 7, 7, 7, 7, 7, 6.5, 6, 4, 2, 1.5, 1, 1, 1, 1],
    # حكومي: دوام 7–16
    "governmental": [2, 2, 2, 2, 2, 2, 3, 5, 7, 7.5, 7.5, 7.5, 7.5, 7.5, 7, 6, 4, 3, 2.5, 2.5, 2, 2, 2, 2],
}
LOAD_PROFILES: dict[str, list[float]] = {
    code: [v / sum(vals) for v in vals] for code, vals in _RAW_PROFILES.items()
}


@dataclass
class MonthBalance:
    consumption_kwh: float
    production_kwh: float
    self_consumed_kwh: float
    imported_kwh: float
    exported_kwh: float
    bill_before_sar: float
    bill_after_sar: float
    export_credit_sar: float

    @property
    def savings_sar(self) -> float:
        return self.bill_before_sar - self.bill_after_sar + self.export_credit_sar


@dataclass
class YearBalance:
    months: list[MonthBalance] = field(default_factory=list)

    def total(self, attr: str) -> float:
        if attr == "savings_sar":
            return sum(m.savings_sar for m in self.months)
        return sum(getattr(m, attr) for m in self.months)


def net_billing_year(
    consumption_kwh: list[float],
    production_matrix_kwh: list[list[float]],
    tariff: Tariff,
    profile: list[float],
    production_scale: float = 1.0,
    tariff_scale: float = 1.0,
) -> YearBalance:
    """موازنة سنة في نظام صافي الفوترة.

    consumption_kwh: الاستهلاك الشهري (12 قيمة).
    production_matrix_kwh: إنتاج كل شهر موزعًا على ساعات اليوم المحلية (12 × 24).
    الاستهلاك الذاتي يُحسب ساعة بساعة على يوم متوسط في الشهر؛ الفائض يُصدَّر بسعر التصدير.
    production_scale و tariff_scale لتطبيق التدهور وزيادة التعرفة في السنوات اللاحقة.
    """
    if len(consumption_kwh) != 12 or len(production_matrix_kwh) != 12:
        raise ValueError("need 12 months of consumption and production")
    if len(profile) != 24:
        raise ValueError("load profile needs 24 hourly values")
    year = YearBalance()
    for month, cons in enumerate(consumption_kwh):
        self_used = exported = produced = 0.0
        for hour in range(24):
            pv = production_matrix_kwh[month][hour] * production_scale
            load = cons * profile[hour]
            used = min(pv, load)
            self_used += used
            exported += pv - used
            produced += pv
        imported = cons - self_used
        before = monthly_bill(cons, tariff) * tariff_scale
        after = monthly_bill(imported, tariff) * tariff_scale
        year.months.append(
            MonthBalance(
                consumption_kwh=cons,
                production_kwh=produced,
                self_consumed_kwh=self_used,
                imported_kwh=imported,
                exported_kwh=exported,
                bill_before_sar=before,
                bill_after_sar=after,
                export_credit_sar=exported * tariff.export_rate_sar * tariff_scale,
            )
        )
    return year
