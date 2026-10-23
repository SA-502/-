"""بيانات أولية: المدير الأول، التعرفة، وبعض المكونات وبنود الأسعار للتجربة. آمن للتشغيل أكثر من مرة."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Component, PriceItem, TariffRow, User
from app.security import hash_password
from app.services.tariffs import DEFAULT_TARIFFS

TARIFF_NAMES = {
    "residential": "سكني",
    "commercial": "تجاري",
    "industrial": "صناعي",
    "agricultural": "زراعي",
    "governmental": "حكومي",
}

# أمثلة فقط؛ تُستبدل بأسعار الشركة الفعلية من شاشة المكونات
SAMPLE_COMPONENTS = [
    {
        "kind": "module",
        "manufacturer": "مثال",
        "model": "Mono 550W",
        "specs": {"power_w": 550, "length_m": 2.278, "width_m": 1.134, "gamma_pdc_pct": -0.34, "voc": 49.9, "isc": 14.0, "vmp": 41.9, "imp": 13.13, "beta_voc_pct": -0.27},
        "price_sar": 0.75,
        "price_unit": "per_watt",
    },
    {
        "kind": "module",
        "manufacturer": "مثال",
        "model": "Bifacial 620W",
        "specs": {"power_w": 620, "length_m": 2.382, "width_m": 1.134, "gamma_pdc_pct": -0.29, "voc": 48.3, "isc": 16.2, "vmp": 40.4, "imp": 15.35, "beta_voc_pct": -0.25},
        "price_sar": 0.85,
        "price_unit": "per_watt",
    },
    {
        "kind": "inverter",
        "manufacturer": "مثال",
        "model": "10kW 3-phase",
        "specs": {"ac_power_kw": 10, "efficiency_pct": 98.2, "max_dc_voltage": 1100, "mppt_min_v": 200, "mppt_max_v": 1000, "mppt_count": 2},
        "price_sar": 6500,
        "price_unit": "per_unit",
    },
    {
        "kind": "inverter",
        "manufacturer": "مثال",
        "model": "50kW 3-phase",
        "specs": {"ac_power_kw": 50, "efficiency_pct": 98.6, "max_dc_voltage": 1100, "mppt_min_v": 200, "mppt_max_v": 1000, "mppt_count": 4},
        "price_sar": 22000,
        "price_unit": "per_unit",
    },
    {
        "kind": "racking",
        "manufacturer": "مثال",
        "model": "هيكل حديد مجلفن للأسطح المستوية",
        "specs": {"material": "galvanized steel"},
        "price_sar": 350,
        "price_unit": "per_kwp",
    },
]

SAMPLE_PRICE_ITEMS = [
    {"name": "التركيب والأعمال الميكانيكية", "unit": "per_kwp", "unit_price_sar": 300, "sort_order": 1},
    {"name": "الكابلات والحمايات واللوحات الكهربائية", "unit": "per_kwp", "unit_price_sar": 250, "sort_order": 2},
    {"name": "الدراسة الهندسية وتصاريح التوصيل", "unit": "fixed", "unit_price_sar": 1500, "sort_order": 3},
]


def seed(db: Session, with_samples: bool = True) -> None:
    settings = get_settings()
    if db.scalar(select(func.count()).select_from(User)) == 0:
        db.add(
            User(
                name=settings.admin_name,
                email=settings.admin_email.lower(),
                role="admin",
                password_hash=hash_password(settings.admin_password),
            )
        )
    for code, tariff in DEFAULT_TARIFFS.items():
        if db.get(TariffRow, code) is None:
            db.add(
                TariffRow(
                    code=code,
                    name=TARIFF_NAMES[code],
                    tiers=[{"up_to_kwh": t.up_to_kwh, "rate_sar": t.rate_sar} for t in tariff.tiers],
                    vat=tariff.vat,
                    export_rate_sar=tariff.export_rate_sar,
                )
            )
    if with_samples and db.scalar(select(func.count()).select_from(Component)) == 0:
        db.add_all(Component(**c) for c in SAMPLE_COMPONENTS)
    if with_samples and db.scalar(select(func.count()).select_from(PriceItem)) == 0:
        db.add_all(PriceItem(**p) for p in SAMPLE_PRICE_ITEMS)
    db.commit()


if __name__ == "__main__":
    from app.db import SessionLocal

    with SessionLocal() as session:
        seed(session)
    print("seed done")
