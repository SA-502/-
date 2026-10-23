import pytest

from app.services.finance import FinanceParams, analyze, irr, npv, payback
from app.services.tariffs import DEFAULT_TARIFFS, Tariff, Tier

FLAT = [1 / 24] * 24


def test_npv_hand_calculation():
    # -1000 + 600/1.1 + 600/1.21
    assert npv(0.1, [-1000, 600, 600]) == pytest.approx(-1000 + 545.4545 + 495.8678, abs=1e-3)


def test_irr_known_value():
    # -100 ثم 110 ⇒ 10%
    assert irr([-100, 110]) == pytest.approx(0.10, abs=1e-6)
    assert irr([-1000, 600, 600]) == pytest.approx(0.1307, abs=1e-4)


def test_irr_no_sign_change():
    assert irr([100, 100]) is None


def test_payback_fractional():
    # -1000 ثم 400 سنويًا ⇒ 2.5 سنة
    assert payback([-1000, 400, 400, 400]) == pytest.approx(2.5)
    assert payback([-1000, 100, 100]) is None


def test_analyze_simple_flat_tariff():
    # تعرفة ثابتة بدون ضريبة ولا تصدير، والإنتاج أقل من الحمل كل ساعة ⇒ التوفير = الإنتاج × السعر
    tariff = Tariff("flat", (Tier(None, 0.20),), vat=0.0)
    cons = [3000.0] * 12
    pv = [[50.0] * 24 for _ in range(12)]  # 14,400 kWh/سنة
    params = FinanceParams(years=25, discount_rate=0.0, degradation_rate=0.0, om_rate=0.0)
    result = analyze(10_000, cons, pv, tariff, FLAT, params)
    assert result.first_year_savings_sar == pytest.approx(14_400 * 0.20)
    assert result.payback_years == pytest.approx(10_000 / 2_880)
    assert result.lifetime_savings_sar == pytest.approx(2_880 * 25)
    # LCOE بدون خصم = التكلفة ÷ الإنتاج الكلي
    assert result.lcoe_sar_per_kwh == pytest.approx(10_000 / (14_400 * 25))
    assert result.npv_sar == pytest.approx(2_880 * 25 - 10_000)


def test_degradation_reduces_production():
    tariff = DEFAULT_TARIFFS["residential"]
    cons = [3000.0] * 12
    pv = [[50.0] * 24 for _ in range(12)]
    result = analyze(50_000, cons, pv, tariff, FLAT, FinanceParams(degradation_rate=0.005))
    first, last = result.rows[0].production_kwh, result.rows[-1].production_kwh
    assert last == pytest.approx(first * 0.995**24)
    assert result.rows[-1].cumulative_sar == pytest.approx(-50_000 + sum(r.net_cash_flow_sar for r in result.rows))


def test_inverter_replacement_cost_in_year():
    tariff = DEFAULT_TARIFFS["residential"]
    cons = [3000.0] * 12
    pv = [[50.0] * 24 for _ in range(12)]
    params = FinanceParams(inverter_replacement_year=12, inverter_replacement_cost_sar=5000)
    result = analyze(50_000, cons, pv, tariff, FLAT, params)
    assert result.rows[11].other_costs_sar == 5000
    assert result.rows[10].other_costs_sar == 0
