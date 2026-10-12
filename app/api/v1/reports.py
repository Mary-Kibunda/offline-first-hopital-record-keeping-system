#admin: reports

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.database import get_db
from app.schemas.report import ReportSummary
from app.services.report_service import build_summary

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=ReportSummary)
def get_report_summary(
    days: int = Query(default=7, ge=1, le=90), db: Session = Depends(get_db)
) -> ReportSummary:
    return build_summary(db, days=days)