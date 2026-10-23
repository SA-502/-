from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

Role = Literal["engineer", "sales", "admin"]
CustomerType = Literal["residential", "commercial", "industrial", "agricultural", "governmental"]
ProjectStatus = Literal["new", "designing", "simulated", "quoted", "won", "lost"]
ComponentKind = Literal["module", "inverter", "racking"]
PriceUnit = Literal["per_unit", "per_watt", "per_kwp", "per_module", "fixed"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- المستخدمون ----------
class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(ORM):
    id: int
    name: str
    email: str
    role: Role
    is_active: bool


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8)
    role: Role = "engineer"


class UserUpdate(BaseModel):
    name: str | None = None
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8)


# ---------- العملاء ----------
class CustomerIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    phone: str | None = None
    email: str | None = None
    city: str | None = None
    customer_type: CustomerType = "residential"
    notes: str | None = None


class CustomerUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    city: str | None = None
    customer_type: CustomerType | None = None
    notes: str | None = None


class CustomerOut(ORM):
    id: int
    name: str
    phone: str | None
    email: str | None
    city: str | None
    customer_type: CustomerType
    notes: str | None
    created_at: datetime


# ---------- المشاريع ----------
class LatLon(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


def _twelve(values: list[float] | None) -> list[float] | None:
    if values is not None:
        if len(values) != 12:
            raise ValueError("المطلوب 12 قيمة شهرية")
        if any(v < 0 for v in values):
            raise ValueError("القيم الشهرية لا تكون سالبة")
    return values


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    customer_id: int
    location: LatLon
    address: str | None = None
    city: str | None = None
    tariff_code: str | None = None  # الافتراضي: نوع العميل
    monthly_consumption_kwh: list[float] | None = None
    # بديل الاستهلاك: الفواتير الشهرية بالريال شاملة الضريبة
    monthly_bill_sar: list[float] | None = None
    designer_id: int | None = None

    _check_cons = field_validator("monthly_consumption_kwh", "monthly_bill_sar")(_twelve)

    @model_validator(mode="after")
    def one_consumption_source(self):
        if self.monthly_consumption_kwh is not None and self.monthly_bill_sar is not None:
            raise ValueError("أدخل الاستهلاك أو الفواتير، وليس الاثنين")
        return self


class ProjectUpdate(BaseModel):
    name: str | None = None
    customer_id: int | None = None
    location: LatLon | None = None
    address: str | None = None
    city: str | None = None
    status: ProjectStatus | None = None
    tariff_code: str | None = None
    monthly_consumption_kwh: list[float] | None = None
    monthly_bill_sar: list[float] | None = None
    designer_id: int | None = None

    _check_cons = field_validator("monthly_consumption_kwh", "monthly_bill_sar")(_twelve)


class DesignSummary(ORM):
    id: int
    version_no: int
    name: str
    created_at: datetime


class ProjectOut(BaseModel):
    id: int
    name: str
    customer: CustomerOut
    location: LatLon
    address: str | None
    city: str | None
    status: ProjectStatus
    tariff_code: str
    monthly_consumption_kwh: list[float] | None
    designer: UserOut | None
    designs: list[DesignSummary] = []
    created_at: datetime
    updated_at: datetime | None


# ---------- المكونات والأسعار ----------
class ComponentIn(BaseModel):
    kind: ComponentKind
    manufacturer: str
    model: str
    specs: dict = {}
    price_sar: float = Field(ge=0, default=0)
    price_unit: PriceUnit = "per_unit"
    is_active: bool = True

    @model_validator(mode="after")
    def required_specs(self):
        required = {
            "module": ("power_w", "length_m", "width_m"),
            "inverter": ("ac_power_kw",),
            "racking": (),
        }[self.kind]
        missing = [k for k in required if not isinstance(self.specs.get(k), (int, float)) or self.specs[k] <= 0]
        if missing:
            raise ValueError(f"مواصفات ناقصة: {', '.join(missing)}")
        return self


class ComponentUpdate(BaseModel):
    manufacturer: str | None = None
    model: str | None = None
    specs: dict | None = None
    price_sar: float | None = Field(default=None, ge=0)
    price_unit: PriceUnit | None = None
    is_active: bool | None = None


class ComponentOut(ORM):
    id: int
    kind: ComponentKind
    manufacturer: str
    model: str
    specs: dict
    price_sar: float
    price_unit: PriceUnit
    is_active: bool


class PriceItemIn(BaseModel):
    name: str
    unit: PriceUnit = "per_kwp"
    unit_price_sar: float = Field(ge=0)
    sort_order: int = 0
    is_active: bool = True


class PriceItemOut(ORM):
    id: int
    name: str
    unit: PriceUnit
    unit_price_sar: float
    sort_order: int
    is_active: bool


class TierIO(BaseModel):
    up_to_kwh: float | None = Field(default=None, gt=0)
    rate_sar: float = Field(ge=0)


class TariffIO(ORM):
    code: str
    name: str
    tiers: list[TierIO] = Field(min_length=1)
    vat: float = Field(ge=0, le=1)
    export_rate_sar: float = Field(ge=0)


class BillsIn(BaseModel):
    monthly_bill_sar: list[float]
    _check = field_validator("monthly_bill_sar")(_twelve)


# ---------- التصميم ----------
class GeoPolygon(BaseModel):
    type: Literal["Polygon"]
    coordinates: list[list[list[float]]]

    @field_validator("coordinates")
    @classmethod
    def valid_ring(cls, rings):
        if not rings or len(rings[0]) < 4:
            raise ValueError("المضلع يحتاج 3 نقاط على الأقل")
        return rings


class ModuleIO(BaseModel):
    lon: float
    lat: float
    x: float
    y: float
    z: float = 0.0
    rotation_deg: float = 0.0


class ArrayIO(BaseModel):
    id: int | None = None
    module_id: int
    orientation: Literal["portrait", "landscape"] = "portrait"
    mounting: Literal["tilted_rows", "flush", "ground"] = "tilted_rows"
    tilt_deg: float = Field(ge=0, le=90, default=20)
    azimuth_deg: float = Field(ge=0, lt=360, default=180)
    row_spacing_m: float = Field(ge=0, default=1.0)
    module_gap_m: float = Field(ge=0, default=0.02)
    modules: list[ModuleIO] = []


class RoofAreaIO(BaseModel):
    id: int | None = None
    name: str = ""
    kind: Literal["roof", "ground"] = "roof"
    geometry: GeoPolygon
    height_m: float = Field(ge=0, default=3.0)
    pitch_deg: float = Field(ge=0, le=60, default=0)
    azimuth_deg: float = Field(ge=0, lt=360, default=180)
    setback_m: float = Field(ge=0, default=1.0)
    arrays: list[ArrayIO] = []


class ObstructionIO(BaseModel):
    id: int | None = None
    kind: Literal["keepout", "tank", "wall", "tree", "other"] = "keepout"
    geometry: GeoPolygon
    height_m: float = Field(ge=0, default=0)


class DesignIn(BaseModel):
    name: str = ""
    inverter_id: int | None = None
    inverter_count: int = Field(ge=0, default=1)
    racking_id: int | None = None
    notes: str | None = None
    roof_areas: list[RoofAreaIO] = []
    obstructions: list[ObstructionIO] = []


class DesignCreate(BaseModel):
    name: str = ""
    copy_from_id: int | None = None


class DesignOut(DesignIn):
    id: int
    project_id: int
    version_no: int
    created_at: datetime
    module_count: int
    dc_kwp: float
    ac_kw: float


# ---------- المحاكاة والتقرير ----------
class LossesIn(BaseModel):
    albedo: float = Field(ge=0, le=1, default=0.25)
    soiling_monthly_pct: list[float] = Field(default_factory=lambda: [4.0] * 12)
    mismatch_pct: float = Field(ge=0, le=20, default=2.0)
    dc_wiring_pct: float = Field(ge=0, le=20, default=1.5)
    lid_pct: float = Field(ge=0, le=20, default=1.5)
    ac_wiring_pct: float = Field(ge=0, le=20, default=1.0)
    transformer_pct: float = Field(ge=0, le=20, default=0.0)

    @field_validator("soiling_monthly_pct")
    @classmethod
    def twelve(cls, v):
        if len(v) != 12 or any(x < 0 or x > 50 for x in v):
            raise ValueError("الاتساخ يحتاج 12 نسبة بين 0 و50")
        return v


class SimulateIn(BaseModel):
    losses: LossesIn = LossesIn()


class SimulationOut(ORM):
    id: int
    design_id: int
    weather_meta: dict
    inputs: dict
    results: dict
    created_at: datetime


class FinanceIn(BaseModel):
    discount_pct: float = Field(ge=0, le=100, default=0)
    extra_lines: list[dict] = []  # [{"description": "...", "quantity": 1, "unit_price_sar": 500}]
    override_total_sar: float | None = Field(default=None, gt=0)
    years: int = Field(ge=1, le=40, default=25)
    discount_rate_pct: float = Field(ge=0, le=30, default=6.0)
    degradation_pct: float = Field(ge=0, le=5, default=0.5)
    om_pct: float = Field(ge=0, le=10, default=1.0)
    tariff_escalation_pct: float = Field(ge=-10, le=20, default=0.0)
    inverter_replacement_year: int | None = Field(default=None, ge=1, le=40)
    inverter_replacement_cost_sar: float = Field(ge=0, default=0)


class ReportIn(FinanceIn):
    language: Literal["ar", "en"] = "ar"


class ReportOut(ORM):
    id: int
    simulation_id: int
    language: str
    quote: dict
    financial: dict
    created_at: datetime


class GeocodeResult(BaseModel):
    name: str
    lat: float
    lon: float
