from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.designs import load_design
from app.api.projects import advance_status, load_project
from app.db import get_db
from app.models import DesignVersion, Report, Simulation, User
from app.schemas import FinanceIn, ReportIn, ReportOut, SimulateIn, SimulationOut
from app.security import current_user, require_designer
from app.services import report as report_service
from app.services.study import StudyError, WeatherFetcher, default_fetcher, financial_study, run_simulation

router = APIRouter(tags=["المحاكاة والتقارير"])


def get_weather_fetcher() -> WeatherFetcher:
    return default_fetcher


def load_simulation(db: Session, simulation_id: int) -> Simulation:
    sim = db.get(Simulation, simulation_id)
    if sim is None:
        raise HTTPException(404, "المحاكاة غير موجودة")
    return sim


@router.post("/designs/{design_id}/simulate", response_model=SimulationOut, status_code=201)
def simulate_design(
    design_id: int,
    body: SimulateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_designer),
    fetcher: WeatherFetcher = Depends(get_weather_fetcher),
):
    design = load_design(db, design_id)
    try:
        sim = run_simulation(db, design, body.losses.model_dump(), fetcher, user.id)
    except StudyError as exc:
        raise HTTPException(422, str(exc)) from exc
    advance_status(design.project, "simulated")
    db.commit()
    return sim


@router.get("/designs/{design_id}/simulations", response_model=list[SimulationOut])
def list_simulations(design_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    load_design(db, design_id)
    return db.scalars(select(Simulation).where(Simulation.design_id == design_id).order_by(Simulation.id.desc())).all()


@router.get("/simulations/{simulation_id}", response_model=SimulationOut)
def get_simulation(simulation_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    return load_simulation(db, simulation_id)


@router.post("/simulations/{simulation_id}/financial")
def preview_financial(simulation_id: int, body: FinanceIn, db: Session = Depends(get_db), _: User = Depends(current_user)):
    """معاينة عرض السعر والدراسة المالية بدون حفظ، لضبط الأسعار قبل إصدار التقرير."""
    sim = load_simulation(db, simulation_id)
    try:
        quote, financial = financial_study(db, sim, body.model_dump())
    except StudyError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"quote": quote, "financial": financial}


@router.post("/simulations/{simulation_id}/reports", response_model=ReportOut, status_code=201)
def create_report(simulation_id: int, body: ReportIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    sim = load_simulation(db, simulation_id)
    params = body.model_dump()
    language = params.pop("language")
    try:
        quote, financial = financial_study(db, sim, params, language)
    except StudyError as exc:
        raise HTTPException(422, str(exc)) from exc
    report = Report(simulation_id=sim.id, language=language, quote=quote, financial=financial, pdf=b"", created_by_id=user.id)
    db.add(report)
    db.flush()
    report.pdf = report_service.render_pdf(sim, report, user)
    advance_status(sim.design.project, "quoted")
    db.commit()
    return report


@router.get("/projects/{project_id}/reports", response_model=list[ReportOut])
def list_reports(project_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    load_project(db, project_id)
    stmt = (
        select(Report)
        .join(Simulation)
        .join(DesignVersion)
        .where(DesignVersion.project_id == project_id)
        .order_by(Report.id.desc())
    )
    return db.scalars(stmt).all()


@router.get("/reports/{report_id}/pdf")
def download_report(report_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(404, "التقرير غير موجود")
    filename = f"solar-study-{report.simulation.design.project_id}-{report.id}.pdf"
    return Response(report.pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{filename}"'})
