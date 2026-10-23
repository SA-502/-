from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SOLAR_", extra="ignore")

    database_url: str = "postgresql+psycopg://solar:solar@localhost:5432/solar"
    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 12 * 60
    cors_origins: list[str] = ["http://localhost:5173"]

    pvgis_base_url: str = "https://re.jrc.ec.europa.eu/api/v5_3"
    nominatim_url: str = "https://nominatim.openstreetmap.org"
    local_timezone: str = "Asia/Riyadh"

    # أول مدير يُنشأ عند التشغيل إذا لم يوجد مستخدمون
    admin_email: str = "admin@example.com"
    admin_password: str = "change-me"
    admin_name: str = "مدير النظام"
    # مكونات وبنود أسعار للتجربة عند أول تشغيل (تُوقف من شاشة المكونات)
    seed_samples: bool = True

    # بيانات الشركة في التقرير
    company_name: str = "طاقات بديلة"
    company_phone: str = ""
    company_email: str = ""
    company_address: str = "الرياض، المملكة العربية السعودية"
    company_logo_path: str = ""
    quote_validity_days: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()
