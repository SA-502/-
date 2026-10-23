from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2.shape import to_shape
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.projects import advance_status, load_project
from app.db import get_db
from app.geo import point_to_db, polygon_from_db, polygon_to_db
from app.models import Array, Component, DesignVersion, ModulePlacement, Obstruction, RoofArea, User
from app.schemas import (
    ArrayIO,
    DesignCreate,
    DesignIn,
    DesignOut,
    DesignSummary,
    ModuleIO,
    ObstructionIO,
    RoofAreaIO,
)
from app.security import current_user, require_designer
from app.services.study import design_totals

router = APIRouter(tags=["التصميم"])


def load_design(db: Session, design_id: int) -> DesignVersion:
    design = db.get(DesignVersion, design_id)
    if design is None:
        raise HTTPException(404, "التصميم غير موجود")
    return design


def design_content(design: DesignVersion) -> DesignIn:
    return DesignIn(
        name=design.name,
        inverter_id=design.inverter_id,
        inverter_count=design.inverter_count,
        racking_id=design.racking_id,
        notes=design.notes,
        roof_areas=[
            RoofAreaIO(
                id=area.id,
                name=area.name,
                kind=area.kind,
                geometry=polygon_from_db(area.geometry),
                height_m=area.height_m,
                pitch_deg=area.pitch_deg,
                azimuth_deg=area.azimuth_deg,
                setback_m=area.setback_m,
                arrays=[
                    ArrayIO(
                        id=arr.id,
                        module_id=arr.module_id,
                        orientation=arr.orientation,
                        mounting=arr.mounting,
                        tilt_deg=arr.tilt_deg,
                        azimuth_deg=arr.azimuth_deg,
                        row_spacing_m=arr.row_spacing_m,
                        module_gap_m=arr.module_gap_m,
                        modules=[_module_io(m) for m in arr.modules],
                    )
                    for arr in area.arrays
                ],
            )
            for area in design.roof_areas
        ],
        obstructions=[
            ObstructionIO(id=o.id, kind=o.kind, geometry=polygon_from_db(o.geometry), height_m=o.height_m)
            for o in design.obstructions
        ],
    )


def _module_io(module: ModulePlacement) -> ModuleIO:
    point = to_shape(module.position)
    return ModuleIO(lon=point.x, lat=point.y, x=module.x, y=module.y, z=module.z, rotation_deg=module.rotation_deg)


def design_out(design: DesignVersion) -> DesignOut:
    return DesignOut(
        **design_content(design).model_dump(),
        id=design.id,
        project_id=design.project_id,
        version_no=design.version_no,
        created_at=design.created_at,
        **design_totals(design),
    )


def _component(db: Session, component_id: int | None, kind: str) -> Component | None:
    if component_id is None:
        return None
    comp = db.get(Component, component_id)
    if comp is None or comp.kind != kind:
        raise HTTPException(422, f"المكون {component_id} غير موجود أو ليس من نوع {kind}")
    return comp


def apply_content(db: Session, design: DesignVersion, body: DesignIn) -> None:
    _component(db, body.inverter_id, "inverter")
    _component(db, body.racking_id, "racking")
    design.name = body.name
    design.inverter_id = body.inverter_id
    design.inverter_count = body.inverter_count
    design.racking_id = body.racking_id
    design.notes = body.notes
    design.roof_areas.clear()
    design.obstructions.clear()
    db.flush()
    try:
        for area_in in body.roof_areas:
            area = RoofArea(
                name=area_in.name,
                kind=area_in.kind,
                geometry=polygon_to_db(area_in.geometry.model_dump()),
                height_m=area_in.height_m,
                pitch_deg=area_in.pitch_deg,
                azimuth_deg=area_in.azimuth_deg,
                setback_m=area_in.setback_m,
            )
            for arr_in in area_in.arrays:
                _component(db, arr_in.module_id, "module")
                arr = Array(**arr_in.model_dump(exclude={"id", "modules"}))
                arr.modules = [
                    ModulePlacement(
                        position=point_to_db(m.lat, m.lon), x=m.x, y=m.y, z=m.z, rotation_deg=m.rotation_deg
                    )
                    for m in arr_in.modules
                ]
                area.arrays.append(arr)
            design.roof_areas.append(area)
        for obs_in in body.obstructions:
            design.obstructions.append(
                Obstruction(kind=obs_in.kind, geometry=polygon_to_db(obs_in.geometry.model_dump()), height_m=obs_in.height_m)
            )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/projects/{project_id}/designs", response_model=list[DesignSummary])
def list_designs(project_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    return load_project(db, project_id).designs


@router.post("/projects/{project_id}/designs", response_model=DesignOut, status_code=201)
def create_design(project_id: int, body: DesignCreate, db: Session = Depends(get_db), user: User = Depends(require_designer)):
    project = load_project(db, project_id)
    next_no = (db.scalar(select(func.max(DesignVersion.version_no)).where(DesignVersion.project_id == project.id)) or 0) + 1
    design = DesignVersion(project_id=project.id, version_no=next_no, name=body.name or f"النسخة {next_no}", created_by_id=user.id)
    db.add(design)
    db.flush()
    if body.copy_from_id is not None:
        source = load_design(db, body.copy_from_id)
        if source.project_id != project.id:
            raise HTTPException(422, "لا يمكن النسخ من تصميم مشروع آخر")
        content = design_content(source)
        content.name = design.name
        apply_content(db, design, content)
    advance_status(project, "designing")
    db.commit()
    db.refresh(design)
    return design_out(design)


@router.get("/designs/{design_id}", response_model=DesignOut)
def get_design(design_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    return design_out(load_design(db, design_id))


@router.put("/designs/{design_id}", response_model=DesignOut)
def save_design(design_id: int, body: DesignIn, db: Session = Depends(get_db), _: User = Depends(require_designer)):
    design = load_design(db, design_id)
    apply_content(db, design, body)
    advance_status(design.project, "designing")
    db.commit()
    db.refresh(design)
    return design_out(design)
