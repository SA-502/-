from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.geo import point_from_db, point_to_db
from app.models import Customer, Project, TariffRow, User
from app.schemas import CustomerOut, DesignSummary, ProjectIn, ProjectOut, ProjectUpdate, UserOut
from app.security import current_user
from app.services import tariffs
from app.services.study import tariff_from_row

router = APIRouter(prefix="/projects", tags=["المشاريع"])

PIPELINE = ("new", "designing", "simulated", "quoted")


def advance_status(project: Project, status: str) -> None:
    """يتقدم المشروع في مراحل العمل ولا يرجع، ولا يغيّر مشروعًا مغلقًا (فاز/خسر)."""
    if project.status in PIPELINE and PIPELINE.index(status) > PIPELINE.index(project.status):
        project.status = status


def project_out(project: Project) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        name=project.name,
        customer=CustomerOut.model_validate(project.customer),
        location=point_from_db(project.location),
        address=project.address,
        city=project.city,
        status=project.status,
        tariff_code=project.tariff_code,
        monthly_consumption_kwh=project.monthly_consumption_kwh,
        designer=UserOut.model_validate(project.designer) if project.designer else None,
        designs=[DesignSummary.model_validate(d) for d in project.designs],
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def load_project(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "المشروع غير موجود")
    return project


def _tariff_row(db: Session, code: str) -> TariffRow:
    row = db.get(TariffRow, code)
    if row is None:
        raise HTTPException(422, f"التعرفة غير موجودة: {code}")
    return row


def _consumption(db: Session, code: str, kwh: list[float] | None, bills: list[float] | None) -> list[float] | None:
    if bills is not None:
        tariff = tariff_from_row(_tariff_row(db, code))
        return [round(tariffs.kwh_from_bill(b, tariff), 1) for b in bills]
    return kwh


@router.get("", response_model=list[ProjectOut])
def list_projects(
    q: str | None = None,
    status: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    stmt = (
        select(Project)
        .join(Customer)
        .options(selectinload(Project.customer), selectinload(Project.designs), selectinload(Project.designer))
        .order_by(Project.updated_at.desc())
        .limit(min(limit, 500))
    )
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Project.name.ilike(like), Customer.name.ilike(like), Project.city.ilike(like)))
    if status:
        stmt = stmt.where(Project.status == status)
    return [project_out(p) for p in db.scalars(stmt).all()]


@router.get("/stats")
def project_stats(db: Session = Depends(get_db), _: User = Depends(current_user)):
    rows = db.execute(select(Project.status, func.count()).group_by(Project.status)).all()
    return {status: count for status, count in rows}


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    customer = db.get(Customer, body.customer_id)
    if customer is None:
        raise HTTPException(422, "العميل غير موجود")
    code = body.tariff_code or customer.customer_type
    _tariff_row(db, code)
    project = Project(
        name=body.name,
        customer_id=customer.id,
        location=point_to_db(body.location.lat, body.location.lon),
        address=body.address,
        city=body.city or customer.city,
        tariff_code=code,
        monthly_consumption_kwh=_consumption(db, code, body.monthly_consumption_kwh, body.monthly_bill_sar),
        designer_id=body.designer_id or (user.id if user.role == "engineer" else None),
    )
    db.add(project)
    db.commit()
    return project_out(project)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    return project_out(load_project(db, project_id))


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, body: ProjectUpdate, db: Session = Depends(get_db), _: User = Depends(current_user)):
    project = load_project(db, project_id)
    data = body.model_dump(exclude_unset=True)
    if "customer_id" in data and db.get(Customer, data["customer_id"]) is None:
        raise HTTPException(422, "العميل غير موجود")
    if "tariff_code" in data:
        _tariff_row(db, data["tariff_code"])
    location = data.pop("location", None)
    if location:
        project.location = point_to_db(location["lat"], location["lon"])
    bills = data.pop("monthly_bill_sar", None)
    kwh = data.pop("monthly_consumption_kwh", None)
    for key, value in data.items():
        setattr(project, key, value)
    if bills is not None or kwh is not None:
        project.monthly_consumption_kwh = _consumption(db, project.tariff_code, kwh, bills)
    db.commit()
    db.refresh(project)
    return project_out(project)
