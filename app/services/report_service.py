from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.consultation import Consultation
from app.models.drug_stock import DrugStock
from app.models.patient import Patient
from app.models.perscription import Prescription
from app.schemas.report import DailyCount, ReportSummary


def build_summary(db: Session, *, days: int = 7) -> ReportSummary:
    since = datetime.now(timezone.utc) - timedelta(days=days)

    total_registrations = db.query(func.count(Patient.id)).filter(Patient.updated_at >= since).scalar() or 0
    total_consultations = db.query(func.count(Consultation.id)).filter(Consultation.updated_at >= since).scalar() or 0
    total_prescriptions = db.query(func.count(Prescription.id)).filter(Prescription.updated_at >= since).scalar() or 0
    low_stock_drugs = (
        db.query(func.count(DrugStock.id)).filter(DrugStock.quantity_available <= DrugStock.reorder_threshold).scalar()
        or 0
    )

    daily_breakdown = _daily_breakdown(db, since)

    return ReportSummary(
        total_registrations=total_registrations,
        total_consultations=total_consultations,
        total_prescriptions=total_prescriptions,
        low_stock_drugs=low_stock_drugs,
        daily_breakdown=daily_breakdown,
    )


def _daily_breakdown(db: Session, since: datetime) -> list[DailyCount]:
    def counts_by_day(model, date_column) -> dict[str, int]:
        rows = (
            db.query(func.date(date_column).label("day"), func.count(model.id))
            .filter(date_column >= since)
            .group_by("day")
            .all()
        )
        return {str(day): count for day, count in rows}

    regs = counts_by_day(Patient, Patient.updated_at)
    cons = counts_by_day(Consultation, Consultation.updated_at)
    presc = counts_by_day(Prescription, Prescription.updated_at)

    all_days = sorted(set(regs) | set(cons) | set(presc))
    return [
        DailyCount(
            day=day,
            registrations=regs.get(day, 0),
            consultations=cons.get(day, 0),
            prescriptions=presc.get(day, 0),
        )
        for day in all_days
    ]