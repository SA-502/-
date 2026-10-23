from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Component, PriceItem, TariffRow, User
from app.schemas import (
    BillsIn,
    ComponentIn,
    ComponentOut,
    ComponentUpdate,
    PriceItemIn,
    PriceItemOut,
    TariffIO,
)
from app.security import current_user, require_admin
from app.services import tariffs
from app.services.study import tariff_from_row

router = APIRouter(tags=["المكونات والأسعار"])


# ---------- المكونات ----------
@router.get("/components", response_model=list[ComponentOut])
def list_components(
    kind: str | None = None, include_inactive: bool = False, db: Session = Depends(get_db), _: User = Depends(current_user)
):
    stmt = select(Component).order_by(Component.kind, Component.manufacturer, Component.model)
    if kind:
        stmt = stmt.where(Component.kind == kind)
    if not include_inactive:
        stmt = stmt.where(Component.is_active.is_(True))
    return db.scalars(stmt).all()


@router.post("/components", response_model=ComponentOut, status_code=201)
def create_component(body: ComponentIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    comp = Component(**body.model_dump())
    db.add(comp)
    db.commit()
    return comp


@router.patch("/components/{component_id}", response_model=ComponentOut)
def update_component(component_id: int, body: ComponentUpdate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    comp = db.get(Component, component_id)
    if comp is None:
        raise HTTPException(404, "المكون غير موجود")
    data = body.model_dump(exclude_unset=True)
    merged = {
        "kind": comp.kind,
        "manufacturer": comp.manufacturer,
        "model": comp.model,
        "specs": comp.specs,
        "price_sar": comp.price_sar,
        "price_unit": comp.price_unit,
        "is_active": comp.is_active,
    } | data
    ComponentIn.model_validate(merged)  # نفس قواعد الإنشاء
    for key, value in data.items():
        setattr(comp, key, value)
    db.commit()
    return comp


# ---------- قائمة الأسعار ----------
@router.get("/price-items", response_model=list[PriceItemOut])
def list_price_items(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return db.scalars(select(PriceItem).order_by(PriceItem.sort_order, PriceItem.id)).all()


@router.post("/price-items", response_model=PriceItemOut, status_code=201)
def create_price_item(body: PriceItemIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    item = PriceItem(**body.model_dump())
    db.add(item)
    db.commit()
    return item


@router.put("/price-items/{item_id}", response_model=PriceItemOut)
def update_price_item(item_id: int, body: PriceItemIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    item = db.get(PriceItem, item_id)
    if item is None:
        raise HTTPException(404, "البند غير موجود")
    for key, value in body.model_dump().items():
        setattr(item, key, value)
    db.commit()
    return item


# ---------- التعرفة ----------
@router.get("/tariffs", response_model=list[TariffIO])
def list_tariffs(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return db.scalars(select(TariffRow).order_by(TariffRow.code)).all()


@router.put("/tariffs/{code}", response_model=TariffIO)
def update_tariff(code: str, body: TariffIO, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    tiers = [t.model_dump() for t in body.tiers]
    try:
        tariff_from_row(TariffRow(code=code, name=body.name, tiers=tiers, vat=body.vat, export_rate_sar=body.export_rate_sar))
    except ValueError as exc:
        raise HTTPException(422, "الشرائح يجب أن تكون تصاعدية والأخيرة فقط بلا حد") from exc
    row = db.get(TariffRow, code) or TariffRow(code=code)
    row.name, row.tiers, row.vat, row.export_rate_sar = body.name, tiers, body.vat, body.export_rate_sar
    db.add(row)
    db.commit()
    return row


@router.post("/tariffs/{code}/bills-to-kwh")
def bills_to_kwh(code: str, body: BillsIn, db: Session = Depends(get_db), _: User = Depends(current_user)):
    row = db.get(TariffRow, code)
    if row is None:
        raise HTTPException(404, "التعرفة غير موجودة")
    tariff = tariff_from_row(row)
    return {"monthly_consumption_kwh": [round(tariffs.kwh_from_bill(b, tariff), 1) for b in body.monthly_bill_sar]}
