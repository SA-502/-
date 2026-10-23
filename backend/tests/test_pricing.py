import pytest

from app.services.pricing import Quote, QuoteLine, module_line, quantity_for


def test_quote_totals():
    quote = Quote(
        lines=[QuoteLine("ألواح", 20, "per_unit", 400), QuoteLine("انفرتر", 1, "per_unit", 6000)],
        discount_pct=10,
    )
    assert quote.subtotal_sar == 14_000
    assert quote.discount_sar == 1_400
    assert quote.net_sar == 12_600
    assert quote.vat_sar == pytest.approx(1_890)
    assert quote.total_sar == pytest.approx(14_490)
    assert quote.to_dict()["total_sar"] == 14_490


def test_quantities_by_unit():
    kw = dict(units=2, module_count=20, dc_kwp=11.0)
    assert quantity_for("per_unit", **kw) == 2
    assert quantity_for("per_watt", **kw) == 11_000
    assert quantity_for("per_kwp", **kw) == 11.0
    assert quantity_for("per_module", **kw) == 20
    assert quantity_for("fixed", **kw) == 1
    with pytest.raises(ValueError):
        quantity_for("per_banana", **kw)


def test_module_line_per_watt_becomes_per_module():
    line = module_line("لوح 550", 0.75, "per_watt", 20, 550)
    assert line.unit_price_sar == pytest.approx(412.5)
    assert line.total_sar == pytest.approx(8_250)
