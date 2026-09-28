from pydantic import BaseModel


class DailyCount(BaseModel):
    day: str
    registrations: int
    consultations: int
    prescriptions: int


class ReportSummary(BaseModel):
    total_registrations: int
    total_consultations: int
    total_prescriptions: int
    low_stock_drugs: int
    daily_breakdown: list[DailyCount]