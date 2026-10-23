from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Customer, User
from app.schemas import CustomerIn, CustomerOut, CustomerUpdate
from app.security import current_user

router = APIRouter(prefix="/customers", tags=["العملاء"])


@router.get("", response_model=list[CustomerOut])
def list_customers(q: str | None = None, limit: int = 100, db: Session = Depends(get_db), _: User = Depends(current_user)):
    stmt = select(Customer).order_by(Customer.created_at.desc()).limit(min(limit, 500))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Customer.name.ilike(like), Customer.phone.ilike(like), Customer.city.ilike(like)))
    return db.scalars(stmt).all()


@router.post("", response_model=CustomerOut, status_code=201)
def create_customer(body: CustomerIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    customer = Customer(**body.model_dump(), created_by_id=user.id)
    db.add(customer)
    db.commit()
    return customer


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(404, "العميل غير موجود")
    return customer


@router.patch("/{customer_id}", response_model=CustomerOut)
def update_customer(customer_id: int, body: CustomerUpdate, db: Session = Depends(get_db), _: User = Depends(current_user)):
    customer = get_customer(customer_id, db)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(customer, key, value)
    db.commit()
    return customer
