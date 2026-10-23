from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

ROLES = ("engineer", "sales", "admin")
PROJECT_STATUSES = ("new", "designing", "simulated", "quoted", "won", "lost")
COMPONENT_KINDS = ("module", "inverter", "racking")
AREA_KINDS = ("roof", "ground")
OBSTRUCTION_KINDS = ("keepout", "tank", "wall", "tree", "other")
ORIENTATIONS = ("portrait", "landscape")
MOUNTINGS = ("tilted_rows", "flush", "ground")


def _now_column() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="engineer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _now_column()


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(100))
    customer_type: Mapped[str] = mapped_column(String(20), default="residential")
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = _now_column()

    projects: Mapped[list["Project"]] = relationship(back_populates="customer")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    location = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    address: Mapped[str | None] = mapped_column(String(300))
    city: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    # 12 قيمة kWh من يناير إلى ديسمبر
    monthly_consumption_kwh: Mapped[list[float] | None] = mapped_column(JSONB)
    tariff_code: Mapped[str] = mapped_column(String(30), default="residential")
    designer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = _now_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    customer: Mapped[Customer] = relationship(back_populates="projects")
    designer: Mapped[User | None] = relationship()
    designs: Mapped[list["DesignVersion"]] = relationship(
        back_populates="project", order_by="DesignVersion.version_no", cascade="all, delete-orphan"
    )


class Component(Base):
    __tablename__ = "components"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    manufacturer: Mapped[str] = mapped_column(String(120))
    model: Mapped[str] = mapped_column(String(160))
    # لوح: power_w, length_m, width_m, gamma_pdc_pct, voc, isc, vmp, imp, beta_voc_pct
    # انفرتر: ac_power_kw, efficiency_pct, max_dc_voltage, mppt_min_v, mppt_max_v, mppt_count
    specs: Mapped[dict] = mapped_column(JSONB, default=dict)
    price_sar: Mapped[float] = mapped_column(Float, default=0.0)
    price_unit: Mapped[str] = mapped_column(String(20), default="per_unit")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _now_column()


class PriceItem(Base):
    """بنود عرض السعر غير المكونات: التركيب، الأعمال الكهربائية، التصاريح..."""

    __tablename__ = "price_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    unit: Mapped[str] = mapped_column(String(20), default="per_kwp")
    unit_price_sar: Mapped[float] = mapped_column(Float, default=0.0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class TariffRow(Base):
    __tablename__ = "tariffs"

    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    # [{"up_to_kwh": 6000, "rate_sar": 0.18}, {"up_to_kwh": null, "rate_sar": 0.30}]
    tiers: Mapped[list[dict]] = mapped_column(JSONB)
    vat: Mapped[float] = mapped_column(Float, default=0.15)
    export_rate_sar: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DesignVersion(Base):
    __tablename__ = "design_versions"
    __table_args__ = (UniqueConstraint("project_id", "version_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200), default="")
    inverter_id: Mapped[int | None] = mapped_column(ForeignKey("components.id"))
    inverter_count: Mapped[int] = mapped_column(Integer, default=1)
    racking_id: Mapped[int | None] = mapped_column(ForeignKey("components.id"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = _now_column()

    project: Mapped[Project] = relationship(back_populates="designs")
    inverter: Mapped[Component | None] = relationship(foreign_keys=[inverter_id])
    racking: Mapped[Component | None] = relationship(foreign_keys=[racking_id])
    roof_areas: Mapped[list["RoofArea"]] = relationship(
        back_populates="design", cascade="all, delete-orphan", order_by="RoofArea.id"
    )
    obstructions: Mapped[list["Obstruction"]] = relationship(
        back_populates="design", cascade="all, delete-orphan", order_by="Obstruction.id"
    )


class RoofArea(Base):
    __tablename__ = "roof_areas"

    id: Mapped[int] = mapped_column(primary_key=True)
    design_id: Mapped[int] = mapped_column(ForeignKey("design_versions.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100), default="")
    kind: Mapped[str] = mapped_column(String(10), default="roof")
    geometry = mapped_column(Geometry("POLYGON", srid=4326), nullable=False)
    height_m: Mapped[float] = mapped_column(Float, default=3.0)
    pitch_deg: Mapped[float] = mapped_column(Float, default=0.0)
    azimuth_deg: Mapped[float] = mapped_column(Float, default=180.0)
    setback_m: Mapped[float] = mapped_column(Float, default=1.0)

    design: Mapped[DesignVersion] = relationship(back_populates="roof_areas")
    arrays: Mapped[list["Array"]] = relationship(
        back_populates="roof_area", cascade="all, delete-orphan", order_by="Array.id"
    )


class Obstruction(Base):
    __tablename__ = "obstructions"

    id: Mapped[int] = mapped_column(primary_key=True)
    design_id: Mapped[int] = mapped_column(ForeignKey("design_versions.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="keepout")
    geometry = mapped_column(Geometry("POLYGON", srid=4326), nullable=False)
    height_m: Mapped[float] = mapped_column(Float, default=0.0)

    design: Mapped[DesignVersion] = relationship(back_populates="obstructions")


class Array(Base):
    __tablename__ = "arrays"

    id: Mapped[int] = mapped_column(primary_key=True)
    roof_area_id: Mapped[int] = mapped_column(ForeignKey("roof_areas.id", ondelete="CASCADE"), index=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("components.id"))
    orientation: Mapped[str] = mapped_column(String(12), default="portrait")
    mounting: Mapped[str] = mapped_column(String(16), default="tilted_rows")
    tilt_deg: Mapped[float] = mapped_column(Float, default=20.0)
    azimuth_deg: Mapped[float] = mapped_column(Float, default=180.0)
    row_spacing_m: Mapped[float] = mapped_column(Float, default=1.0)
    module_gap_m: Mapped[float] = mapped_column(Float, default=0.02)

    roof_area: Mapped[RoofArea] = relationship(back_populates="arrays")
    module: Mapped[Component] = relationship()
    modules: Mapped[list["ModulePlacement"]] = relationship(
        back_populates="array", cascade="all, delete-orphan", order_by="ModulePlacement.id"
    )


class ModulePlacement(Base):
    __tablename__ = "modules_layout"

    id: Mapped[int] = mapped_column(primary_key=True)
    array_id: Mapped[int] = mapped_column(ForeignKey("arrays.id", ondelete="CASCADE"), index=True)
    position = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    # إحداثيات محلية بالمتر من موقع المشروع (شرق، شمال، ارتفاع)
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    z: Mapped[float] = mapped_column(Float, default=0.0)
    rotation_deg: Mapped[float] = mapped_column(Float, default=0.0)
    string_id: Mapped[int | None] = mapped_column(Integer)  # يُربط بجدول السلاسل في المرحلة الرابعة

    array: Mapped[Array] = relationship(back_populates="modules")


class WeatherCache(Base):
    __tablename__ = "weather_cache"
    __table_args__ = (UniqueConstraint("latitude", "longitude", "source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(40), default="pvgis_tmy")
    payload: Mapped[dict] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = _now_column()


class Simulation(Base):
    __tablename__ = "simulations"

    id: Mapped[int] = mapped_column(primary_key=True)
    design_id: Mapped[int] = mapped_column(ForeignKey("design_versions.id", ondelete="CASCADE"), index=True)
    weather_meta: Mapped[dict] = mapped_column(JSONB)
    inputs: Mapped[dict] = mapped_column(JSONB)
    results: Mapped[dict] = mapped_column(JSONB)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = _now_column()

    design: Mapped[DesignVersion] = relationship()


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    simulation_id: Mapped[int] = mapped_column(ForeignKey("simulations.id", ondelete="CASCADE"), index=True)
    language: Mapped[str] = mapped_column(String(5), default="ar")
    pdf: Mapped[bytes] = mapped_column(LargeBinary)
    quote: Mapped[dict] = mapped_column(JSONB)
    financial: Mapped[dict] = mapped_column(JSONB)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = _now_column()

    simulation: Mapped[Simulation] = relationship()
