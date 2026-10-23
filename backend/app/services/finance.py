"""الحساب المالي على عمر المشروع: التوفير، صافي القيمة الحالية، الاسترداد، العائد الداخلي، وLCOE."""

from dataclasses import dataclass, field

from app.services.tariffs import Tariff, net_billing_year


@dataclass
class FinanceParams:
    years: int = 25
    discount_rate: float = 0.06
    degradation_rate: float = 0.005  # تراجع الإنتاج السنوي
    first_year_degradation: float = 0.0  # تراجع إضافي في السنة الأولى (LID)
    om_rate: float = 0.01  # التشغيل والصيانة كنسبة من التكلفة سنويًا
    om_escalation: float = 0.0
    tariff_escalation: float = 0.0
    inverter_replacement_year: int | None = None
    inverter_replacement_cost_sar: float = 0.0


@dataclass
class YearRow:
    year: int
    production_kwh: float
    self_consumed_kwh: float
    exported_kwh: float
    savings_sar: float
    om_sar: float
    other_costs_sar: float
    net_cash_flow_sar: float
    cumulative_sar: float


@dataclass
class FinanceResult:
    capex_sar: float
    rows: list[YearRow] = field(default_factory=list)
    npv_sar: float = 0.0
    irr: float | None = None
    payback_years: float | None = None
    discounted_payback_years: float | None = None
    lcoe_sar_per_kwh: float = 0.0
    roi_pct: float = 0.0
    first_year_savings_sar: float = 0.0
    first_year_bill_before_sar: float = 0.0
    first_year_bill_after_sar: float = 0.0
    lifetime_savings_sar: float = 0.0


def npv(rate: float, flows: list[float]) -> float:
    """flows[0] في السنة صفر (غير مخصومة)."""
    return sum(cf / (1 + rate) ** t for t, cf in enumerate(flows))


def irr(flows: list[float], low: float = -0.99, high: float = 1.0, tol: float = 1e-7) -> float | None:
    """العائد الداخلي بطريقة التنصيف؛ None إذا لم يتغير الإشارة."""
    f_low, f_high = npv(low, flows), npv(high, flows)
    if f_low * f_high > 0:
        return None
    for _ in range(200):
        mid = (low + high) / 2
        f_mid = npv(mid, flows)
        if abs(f_mid) < tol:
            return mid
        if f_low * f_mid < 0:
            high = mid
        else:
            low, f_low = mid, f_mid
    return (low + high) / 2


def payback(flows: list[float]) -> float | None:
    """أول لحظة يصبح فيها التدفق التراكمي موجبًا، مع كسور السنة."""
    cumulative = flows[0]
    for year, cf in enumerate(flows[1:], start=1):
        previous = cumulative
        cumulative += cf
        if cumulative >= 0 and cf > 0:
            return year - 1 + (-previous / cf)
    return None


def analyze(
    capex_sar: float,
    consumption_kwh: list[float],
    production_matrix_kwh: list[list[float]],
    tariff: Tariff,
    profile: list[float],
    params: FinanceParams | None = None,
) -> FinanceResult:
    p = params or FinanceParams()
    result = FinanceResult(capex_sar=capex_sar)
    flows = [-capex_sar]
    discounted_production = 0.0
    discounted_costs = capex_sar
    cumulative = -capex_sar

    for year in range(1, p.years + 1):
        production_scale = (1 - p.first_year_degradation) * (1 - p.degradation_rate) ** (year - 1)
        tariff_scale = (1 + p.tariff_escalation) ** (year - 1)
        balance = net_billing_year(
            consumption_kwh, production_matrix_kwh, tariff, profile, production_scale, tariff_scale
        )
        savings = balance.total("savings_sar")
        om = capex_sar * p.om_rate * (1 + p.om_escalation) ** (year - 1)
        other = p.inverter_replacement_cost_sar if year == p.inverter_replacement_year else 0.0
        net = savings - om - other
        cumulative += net
        flows.append(net)

        production = balance.total("production_kwh")
        discount = (1 + p.discount_rate) ** year
        discounted_production += production / discount
        discounted_costs += (om + other) / discount

        if year == 1:
            result.first_year_savings_sar = savings
            result.first_year_bill_before_sar = balance.total("bill_before_sar")
            result.first_year_bill_after_sar = balance.total("payable_sar")
        result.rows.append(
            YearRow(
                year=year,
                production_kwh=production,
                self_consumed_kwh=balance.total("self_consumed_kwh"),
                exported_kwh=balance.total("exported_kwh"),
                savings_sar=savings,
                om_sar=om,
                other_costs_sar=other,
                net_cash_flow_sar=net,
                cumulative_sar=cumulative,
            )
        )

    result.npv_sar = npv(p.discount_rate, flows)
    result.irr = irr(flows)
    result.payback_years = payback(flows)
    discounted_flows = [cf / (1 + p.discount_rate) ** t for t, cf in enumerate(flows)]
    result.discounted_payback_years = payback(discounted_flows)
    result.lcoe_sar_per_kwh = discounted_costs / discounted_production if discounted_production else 0.0
    result.lifetime_savings_sar = sum(r.savings_sar for r in result.rows)
    result.roi_pct = (sum(flows[1:]) - capex_sar) / capex_sar * 100 if capex_sar else 0.0
    return result
