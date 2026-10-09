from fastapi import APIRouter

from app.api.v1 import (
    appointment as appointments,
    auth,
    clinic as clinics,
    consultation as consultations,
    drug_stock,
    patient as patients,
    perscription as prescriptions,
    reports,
    sync,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(clinics.router)
api_router.include_router(patients.router)
api_router.include_router(appointments.router)
api_router.include_router(consultations.router)
api_router.include_router(prescriptions.router)
api_router.include_router(drug_stock.router)
api_router.include_router(users.router)
api_router.include_router(reports.router)
api_router.include_router(sync.router)