"""اختبارات تكامل للـ API على قاعدة PostgreSQL + PostGIS حقيقية (تُتخطى إذا لم تتوفر القاعدة)."""

import math
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.db import SessionLocal, engine

try:
    with engine.connect() as conn:
        conn.execute(text("select 1"))
except OperationalError:  # pragma: no cover
    pytest.skip("قاعدة الاختبار غير متاحة", allow_module_level=True)

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.api.simulations import get_weather_fetcher
from app.main import app
from app.seed import seed
from tests.weather_fixture import pvgis_payload

BACKEND = Path(__file__).resolve().parents[1]
LAT, LON = 24.7136, 46.6753
M_PER_DEG = 111_320.0


@pytest.fixture(scope="module")
def payload():
    return pvgis_payload(LAT, LON)


@pytest.fixture(scope="module", autouse=True)
def database():
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    command.upgrade(cfg, "head")
    with SessionLocal() as db:
        seed(db)
    yield


@pytest.fixture(scope="module")
def fetch_calls():
    return []


@pytest.fixture(scope="module")
def client(payload, fetch_calls):
    def fetcher(lat, lon):
        fetch_calls.append((lat, lon))
        return payload

    app.dependency_overrides[get_weather_fetcher] = lambda: fetcher
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def login(client, email, password):
    r = client.post("/api/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def admin(client):
    return login(client, "admin@test.sa", "admin-pass-123")


@pytest.fixture(scope="module")
def engineer(client, admin):
    r = client.post("/api/users", json={"name": "مهندس", "email": "eng@test.sa", "password": "eng-pass-123", "role": "engineer"}, headers=admin)
    assert r.status_code == 201, r.text
    return login(client, "eng@test.sa", "eng-pass-123")


@pytest.fixture(scope="module")
def sales(client, admin):
    r = client.post("/api/users", json={"name": "مبيعات", "email": "sales@test.sa", "password": "sales-pass-123", "role": "sales"}, headers=admin)
    assert r.status_code == 201, r.text
    return login(client, "sales@test.sa", "sales-pass-123")


def square(lat, lon, size_m):
    dlat = size_m / M_PER_DEG
    dlon = size_m / (M_PER_DEG * math.cos(math.radians(lat)))
    ring = [[lon, lat], [lon + dlon, lat], [lon + dlon, lat + dlat], [lon, lat + dlat], [lon, lat]]
    return {"type": "Polygon", "coordinates": [ring]}


def modules_grid(count, lat, lon):
    out = []
    for i in range(count):
        x, y = 2 + (i % 5) * 1.2, 2 + (i // 5) * 3.0
        out.append(
            {
                "lon": lon + x / (M_PER_DEG * math.cos(math.radians(lat))),
                "lat": lat + y / M_PER_DEG,
                "x": x,
                "y": y,
                "z": 3.0,
                "rotation_deg": 180,
            }
        )
    return out


def components(client, headers, kind):
    r = client.get("/api/components", params={"kind": kind}, headers=headers)
    assert r.status_code == 200
    return r.json()


def test_requires_auth(client):
    assert client.get("/api/projects").status_code == 401
    assert client.post("/api/auth/login", data={"username": "admin@test.sa", "password": "wrong"}).status_code == 401


def test_roles(client, admin, engineer, sales):
    assert client.get("/api/auth/me", headers=sales).json()["role"] == "sales"
    body = {"kind": "inverter", "manufacturer": "X", "model": "Y", "specs": {"ac_power_kw": 5}, "price_sar": 1000}
    assert client.post("/api/components", json=body, headers=sales).status_code == 403
    assert client.post("/api/components", json=body, headers=engineer).status_code == 403
    assert client.post("/api/components", json=body, headers=admin).status_code == 201
    bad = body | {"specs": {}}
    assert client.post("/api/components", json=bad, headers=admin).status_code == 422


def test_tariffs_seeded_and_bill_conversion(client, sales):
    tariffs = {t["code"]: t for t in client.get("/api/tariffs", headers=sales).json()}
    assert set(tariffs) == {"residential", "commercial", "industrial", "agricultural", "governmental"}
    assert tariffs["residential"]["tiers"][0] == {"up_to_kwh": 6000, "rate_sar": 0.18}
    r = client.post("/api/tariffs/residential/bills-to-kwh", json={"monthly_bill_sar": [207.0] * 12}, headers=sales)
    assert r.json()["monthly_consumption_kwh"][0] == pytest.approx(1000, abs=0.1)


def test_tariff_update_validation(client, admin):
    bad = {"code": "residential", "name": "سكني", "tiers": [{"up_to_kwh": None, "rate_sar": 0.2}, {"up_to_kwh": 6000, "rate_sar": 0.3}], "vat": 0.15, "export_rate_sar": 0.07}
    assert client.put("/api/tariffs/residential", json=bad, headers=admin).status_code == 422


def test_project_validation(client, sales):
    customer = client.post("/api/customers", json={"name": "عميل"}, headers=sales).json()
    both = {"name": "x", "customer_id": customer["id"], "location": {"lat": LAT, "lon": LON}, "monthly_consumption_kwh": [1] * 12, "monthly_bill_sar": [1] * 12}
    assert client.post("/api/projects", json=both, headers=sales).status_code == 422
    eleven = {"name": "x", "customer_id": customer["id"], "location": {"lat": LAT, "lon": LON}, "monthly_consumption_kwh": [1] * 11}
    assert client.post("/api/projects", json=eleven, headers=sales).status_code == 422


def test_full_study_flow(client, admin, engineer, sales, fetch_calls):
    # العميل والمشروع (مبيعات) بالفواتير
    customer = client.post(
        "/api/customers", json={"name": "محمد العتيبي", "phone": "0500000000", "city": "الرياض", "customer_type": "residential"}, headers=sales
    )
    assert customer.status_code == 201
    bills = [600, 650, 800, 1100, 1500, 1900, 2100, 2100, 1700, 1200, 800, 650]
    project = client.post(
        "/api/projects",
        json={"name": "فيلا الملقا", "customer_id": customer.json()["id"], "location": {"lat": LAT, "lon": LON}, "monthly_bill_sar": bills},
        headers=sales,
    )
    assert project.status_code == 201, project.text
    project = project.json()
    assert project["tariff_code"] == "residential"
    assert project["monthly_consumption_kwh"][0] == pytest.approx(600 / 1.15 / 0.18, abs=0.1)
    assert project["status"] == "new"

    listed = client.get("/api/projects", params={"q": "العتيبي"}, headers=sales).json()
    assert [p["id"] for p in listed] == [project["id"]]

    # التصميم (مهندس فقط)
    assert client.post(f"/api/projects/{project['id']}/designs", json={}, headers=sales).status_code == 403
    design = client.post(f"/api/projects/{project['id']}/designs", json={}, headers=engineer)
    assert design.status_code == 201, design.text
    design = design.json()
    assert design["version_no"] == 1

    module = next(c for c in components(client, engineer, "module") if c["specs"]["power_w"] == 550)
    inverter = next(c for c in components(client, engineer, "inverter") if c["specs"]["ac_power_kw"] == 10)
    racking = components(client, engineer, "racking")[0]
    content = {
        "name": "تصميم أولي",
        "inverter_id": inverter["id"],
        "inverter_count": 1,
        "racking_id": racking["id"],
        "roof_areas": [
            {
                "name": "السطح الرئيسي",
                "geometry": square(LAT, LON, 20),
                "height_m": 6,
                "setback_m": 1,
                "arrays": [{"module_id": module["id"], "tilt_deg": 25, "azimuth_deg": 180, "row_spacing_m": 1.5, "modules": modules_grid(20, LAT, LON)}],
            }
        ],
        "obstructions": [{"kind": "tank", "geometry": square(LAT + 0.00012, LON + 0.00012, 2), "height_m": 1.5}],
    }
    saved = client.put(f"/api/designs/{design['id']}", json=content, headers=engineer)
    assert saved.status_code == 200, saved.text
    saved = saved.json()
    assert saved["module_count"] == 20
    assert saved["dc_kwp"] == pytest.approx(11.0)
    assert saved["ac_kw"] == pytest.approx(10.0)
    assert saved["roof_areas"][0]["arrays"][0]["modules"][0]["lat"] == pytest.approx(content["roof_areas"][0]["arrays"][0]["modules"][0]["lat"])
    assert client.get(f"/api/projects/{project['id']}", headers=sales).json()["status"] == "designing"

    # نسخة ثانية منسوخة من الأولى
    copy = client.post(f"/api/projects/{project['id']}/designs", json={"copy_from_id": design["id"]}, headers=engineer).json()
    assert copy["version_no"] == 2 and copy["module_count"] == 20

    # المحاكاة: أول مرة تجلب من PVGIS، والثانية من الذاكرة المؤقتة
    sim = client.post(f"/api/designs/{design['id']}/simulate", json={}, headers=engineer)
    assert sim.status_code == 201, sim.text
    sim = sim.json()
    assert len(fetch_calls) == 1
    assert 1600 < sim["results"]["specific_yield_kwh_kwp"] < 2600
    again = client.post(f"/api/designs/{copy['id']}/simulate", json={}, headers=engineer)
    assert again.status_code == 201
    assert len(fetch_calls) == 1
    assert again.json()["results"]["annual_energy_kwh"] == pytest.approx(sim["results"]["annual_energy_kwh"])

    # معاينة مالية
    preview = client.post(f"/api/simulations/{sim['id']}/financial", json={"discount_pct": 5}, headers=sales)
    assert preview.status_code == 200, preview.text
    quote, fin = preview.json()["quote"], preview.json()["financial"]
    module_line = quote["lines"][0]
    assert module_line["quantity"] == 20
    assert module_line["total_sar"] == pytest.approx(20 * 550 * 0.75)
    descriptions = " ".join(line["description"] for line in quote["lines"])
    assert "انفرتر" in descriptions and "هيكل" in descriptions and "التركيب" in descriptions
    assert quote["total_sar"] == pytest.approx(quote["net_sar"] * 1.15, abs=0.02)
    assert fin["capex_sar"] == pytest.approx(quote["total_sar"])
    assert fin["first_year_savings_sar"] > 0
    assert fin["payback_years"] is not None
    assert len(fin["rows"]) == 25

    # التقرير PDF
    report = client.post(f"/api/simulations/{sim['id']}/reports", json={"discount_pct": 5}, headers=sales)
    assert report.status_code == 201, report.text
    pdf = client.get(f"/api/reports/{report.json()['id']}/pdf", headers=sales)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    assert len(pdf.content) > 20_000
    english = client.post(f"/api/simulations/{sim['id']}/reports", json={"language": "en"}, headers=sales)
    assert english.status_code == 201
    assert len(client.get(f"/api/projects/{project['id']}/reports", headers=sales).json()) == 2
    assert client.get(f"/api/projects/{project['id']}", headers=sales).json()["status"] == "quoted"


def test_simulate_empty_design_is_rejected(client, engineer, sales):
    customer = client.post("/api/customers", json={"name": "ب"}, headers=sales).json()
    project = client.post("/api/projects", json={"name": "فارغ", "customer_id": customer["id"], "location": {"lat": LAT, "lon": LON}}, headers=sales).json()
    design = client.post(f"/api/projects/{project['id']}/designs", json={}, headers=engineer).json()
    r = client.post(f"/api/designs/{design['id']}/simulate", json={}, headers=engineer)
    assert r.status_code == 422
    assert "ألواح" in r.json()["detail"]


def test_invalid_polygon_rejected(client, engineer, sales):
    customer = client.post("/api/customers", json={"name": "ج"}, headers=sales).json()
    project = client.post("/api/projects", json={"name": "س", "customer_id": customer["id"], "location": {"lat": LAT, "lon": LON}}, headers=sales).json()
    design = client.post(f"/api/projects/{project['id']}/designs", json={}, headers=engineer).json()
    bowtie = {"type": "Polygon", "coordinates": [[[LON, LAT], [LON + 0.001, LAT + 0.001], [LON + 0.001, LAT], [LON, LAT + 0.001], [LON, LAT]]]}
    r = client.put(f"/api/designs/{design['id']}", json={"roof_areas": [{"geometry": bowtie}]}, headers=engineer)
    assert r.status_code == 422
