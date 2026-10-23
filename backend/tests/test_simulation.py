import copy

import pandas as pd
import pvlib
import pytest

from app.services.pvgis import PVGISError, parse_tmy
from app.services.simulation import ArrayInput, LossInput, simulate
from tests.weather_fixture import pvgis_payload


@pytest.fixture(scope="module")
def payload():
    return pvgis_payload()


@pytest.fixture(scope="module")
def weather(payload):
    data, meta = parse_tmy(payload)
    return data, meta


def riyadh_array(count=20, tilt=25.0, azimuth=180.0, mounting="tilted_rows"):
    return ArrayInput("A", count, 550.0, tilt, azimuth, mounting=mounting)


def run(weather, arrays, ac_kw=None, losses=None):
    data, meta = weather
    return simulate(data, meta["latitude"], meta["longitude"], meta["elevation"], arrays, ac_kw, losses)


def test_parse_tmy_shape(weather):
    data, meta = weather
    assert len(data) == 8760
    assert data.index.tz is not None
    assert set(data.index.year) == {2023}
    assert data.index.is_monotonic_increasing
    assert {"ghi", "dni", "dhi", "temp_air", "wind_speed"} <= set(data.columns)
    assert meta["elevation"] == 612.0


def test_parse_tmy_rejects_bad_payload(payload):
    with pytest.raises(PVGISError):
        parse_tmy({"outputs": {}})
    short = copy.deepcopy(payload)
    short["outputs"]["tmy_hourly"] = short["outputs"]["tmy_hourly"][:100]
    with pytest.raises(PVGISError):
        parse_tmy(short)


def test_pvwatts_dc_reference_point():
    # عند ظروف الاختبار القياسية (1000 W/m²، 25°C) القدرة = القدرة الاسمية
    assert pvlib.pvsystem.pvwatts_dc(1000, 25, 11000, -0.0035) == pytest.approx(11000)
    # عند 65°C: 11000 × (1 − 0.0035 × 40)
    assert pvlib.pvsystem.pvwatts_dc(1000, 65, 11000, -0.0035) == pytest.approx(11000 * 0.86)


def test_annual_energy_in_plausible_range(weather):
    result = run(weather, [riyadh_array()])
    assert result.dc_kwp == pytest.approx(11.0)
    # سماء صافية مخففة في الرياض: عائد نوعي مرتفع لكن ضمن حدود فيزيائية
    assert 1700 < result.specific_yield_kwh_kwp < 2600
    assert 0.65 < result.performance_ratio < 0.90
    assert sum(result.monthly_energy_kwh) == pytest.approx(result.annual_energy_kwh, rel=1e-3)
    assert len(result.production_matrix_kwh) == 12
    assert all(len(row) == 24 for row in result.production_matrix_kwh)
    # لا إنتاج في منتصف الليل بالتوقيت المحلي
    assert all(row[0] == 0 for row in result.production_matrix_kwh)


def test_waterfall_is_consistent(weather):
    result = run(weather, [riyadh_array()])
    energies = [row["energy_kwh"] for row in result.losses]
    assert energies[-1] == pytest.approx(result.annual_energy_kwh, abs=0.2)
    assert all(b <= a + 0.1 for a, b in zip(energies, energies[1:]))
    by_key = {row["key"]: row for row in result.losses}
    assert by_key["soiling"]["loss_pct"] == pytest.approx(4.0, abs=0.01)
    assert by_key["mismatch"]["loss_pct"] == pytest.approx(2.0, abs=0.01)
    # مناخ حار ⇒ خسارة حرارة واضحة
    assert by_key["temperature"]["loss_pct"] > 4


def test_clipping_only_when_inverter_undersized(weather):
    big = run(weather, [riyadh_array()], ac_kw=11.0)
    small = run(weather, [riyadh_array()], ac_kw=6.0)
    clip = lambda r: next(x for x in r.losses if x["key"] == "clipping")["loss_pct"]
    assert clip(big) == pytest.approx(0.0, abs=0.01)
    assert clip(small) > 1.0
    assert small.annual_energy_kwh < big.annual_energy_kwh


def test_south_tilt_beats_north_tilt(weather):
    south = run(weather, [riyadh_array(azimuth=180)])
    north = run(weather, [riyadh_array(azimuth=0)])
    assert south.annual_poa_kwh_m2 > north.annual_poa_kwh_m2


def test_energy_scales_with_module_count(weather):
    one = run(weather, [riyadh_array(count=10)])
    two = run(weather, [riyadh_array(count=10), riyadh_array(count=10)])
    assert two.annual_energy_kwh == pytest.approx(2 * one.annual_energy_kwh, rel=1e-6)


def test_flush_mount_runs_hotter(weather):
    rows = run(weather, [riyadh_array(mounting="tilted_rows")])
    flush = run(weather, [riyadh_array(mounting="flush")])
    assert flush.annual_energy_kwh < rows.annual_energy_kwh


def test_rejects_empty_design(weather):
    with pytest.raises(ValueError):
        run(weather, [riyadh_array(count=0)])
    with pytest.raises(ValueError):
        run(weather, [riyadh_array()], losses=LossInput(soiling_monthly=[0.03] * 11))


def test_rejects_naive_index(weather):
    data, meta = weather
    naive = data.copy()
    naive.index = pd.DatetimeIndex(naive.index.tz_localize(None))
    with pytest.raises(ValueError):
        simulate(naive, meta["latitude"], meta["longitude"], 0, [riyadh_array()], None)


def test_result_is_json_serializable(weather):
    import json

    json.dumps(run(weather, [riyadh_array()]).to_dict())
