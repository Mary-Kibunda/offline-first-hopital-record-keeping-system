"""Role policies shared by resource and synchronization endpoints."""

from app.models.user import UserRole

CLINICAL_AND_REGISTRY = (
    UserRole.administrator,
    UserRole.clinician,
    UserRole.registry_officer,
)
CLINICAL = (UserRole.administrator, UserRole.clinician)
PHARMACY = (UserRole.administrator, UserRole.pharmacist)
PRESCRIBING = (UserRole.administrator, UserRole.clinician, UserRole.pharmacist)
SYNC_ROLES = (
    UserRole.administrator,
    UserRole.clinician,
    UserRole.pharmacist,
    UserRole.registry_officer,
)

SYNC_ENTITIES_BY_ROLE = {
    UserRole.administrator: frozenset({"patient", "appointment", "consultation", "prescription", "drug_stock"}),
    UserRole.clinician: frozenset({"patient", "appointment", "consultation", "prescription"}),
    UserRole.pharmacist: frozenset({"prescription", "drug_stock"}),
    UserRole.registry_officer: frozenset({"patient", "appointment"}),
}


def sync_entities_for(role: UserRole) -> frozenset[str]:
    return SYNC_ENTITIES_BY_ROLE[role]
