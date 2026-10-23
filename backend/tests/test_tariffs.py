import pytest

from app.services.tariffs import (
    DEFAULT_TARIFFS,
    LOAD_PROFILES,
    Tariff,
    Tier,
    energy_charge,
    kwh_from_bill,
    monthly_bill,
    net_billing_year,
)

RES = DEFAULT_TARIFFS["residential"]


def test_residential_first_tier_only():
    assert energy_charge(5000, RES) == pytest.approx(5000 * 0.18)


def test_residential_crosses_tier():
    # 6000 × 0.18 + 2000 × 0.30
    assert energy_charge(8000, RES) == pytest.approx(1080 + 600)


def test_bill_includes_vat():
    assert monthly_bill(1000, RES) == pytest.approx(180 * 1.15)
    assert monthly_bill(1000, RES, include_vat=False) == pytest.approx(180)


def test_zero_and_negative_consumption():
    assert energy_charge(0, RES) == 0
    assert energy_charge(-10, RES) == 0


@pytest.mark.parametrize("kwh", [0, 1, 3500, 6000, 6001, 9000, 25000])
@pytest.mark.parametrize("code", sorted(DEFAULT_TARIFFS))
def test_bill_inverse_round_trip(code, kwh):
    tariff = DEFAULT_TARIFFS[code]
    assert kwh_from_bill(monthly_bill(kwh, tariff), tariff) == pytest.approx(kwh, abs=1e-6)


def test_tiers_must_ascend():
    with pytest.raises(ValueError):
        Tariff("bad", (Tier(6000, 0.2), Tier(3000, 0.3), Tier(None, 0.4)))
    with pytest.raises(ValueError):
        Tariff("bad", (Tier(None, 0.2), Tier(6000, 0.3)))


def test_profiles_sum_to_one():
    for profile in LOAD_PROFILES.values():
        assert len(profile) == 24
        assert sum(profile) == pytest.approx(1.0)


def test_net_billing_all_self_consumed():
    flat = [1 / 24] * 24
    cons = [2400.0] * 12
    pv = [[50.0] * 24 for _ in range(12)]  # 1200 kWh شهريًا وأقل من الحمل كل ساعة
    year = net_billing_year(cons, pv, RES, flat)
    month = year.months[0]
    assert month.self_consumed_kwh == pytest.approx(1200)
    assert month.exported_kwh == pytest.approx(0)
    assert month.imported_kwh == pytest.approx(1200)
    assert month.savings_sar == pytest.approx(1200 * 0.18 * 1.15)


def test_net_billing_surplus_is_exported_at_export_rate():
    flat = [1 / 24] * 24
    cons = [240.0] * 12  # 10 kWh كل ساعة
    pv = [[0.0] * 12 + [30.0] * 12 for _ in range(12)]  # 30 kWh في ساعات النهار
    month = net_billing_year(cons, pv, RES, flat).months[0]
    assert month.self_consumed_kwh == pytest.approx(120)
    assert month.exported_kwh == pytest.approx(240)
    assert month.export_credit_sar == pytest.approx(240 * 0.07)
    assert month.bill_after_sar == pytest.approx(120 * 0.18 * 1.15)
    # الرصيد (16.8) أقل من الفاتورة (24.84) فيُخصم كاملًا
    assert month.credit_applied_sar == pytest.approx(240 * 0.07)
    assert month.savings_sar == pytest.approx(240 * 0.18 * 1.15 - (120 * 0.18 * 1.15 - 240 * 0.07))


def test_export_credit_never_makes_bill_negative_and_carries_over():
    flat = [1 / 24] * 24
    # الشهر الأول فائض كبير، والشهور التالية بلا إنتاج
    cons = [240.0] * 12
    pv = [[0.0] * 12 + [200.0] * 12] + [[0.0] * 24 for _ in range(11)]
    year = net_billing_year(cons, pv, RES, flat)
    first, second = year.months[0], year.months[1]
    earned = (2400 - 120) * 0.07
    assert first.export_credit_sar == pytest.approx(earned)
    assert first.payable_sar == pytest.approx(0)
    assert second.credit_applied_sar == pytest.approx(second.bill_after_sar)
    assert all(m.payable_sar >= -1e-9 for m in year.months)
    used = year.total("credit_applied_sar")
    assert used + year.expired_credit_sar == pytest.approx(earned)


def test_net_billing_scales():
    flat = [1 / 24] * 24
    cons = [2400.0] * 12
    pv = [[50.0] * 24 for _ in range(12)]
    base = net_billing_year(cons, pv, RES, flat)
    scaled = net_billing_year(cons, pv, RES, flat, production_scale=0.5, tariff_scale=2.0)
    assert scaled.total("production_kwh") == pytest.approx(base.total("production_kwh") / 2)
    assert scaled.total("bill_before_sar") == pytest.approx(base.total("bill_before_sar") * 2)
