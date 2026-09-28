#push/pull synchronization endpoints, conflict resolution, and data merging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.sync_log import SyncLog
from app.models.user import User
from app.schemas.sync import (
    ConflictResolutionRequest,
    SyncLogRead,
    SyncPullResponse,
    SyncPushRequest,
    SyncPushResponse,
    SyncPushResult,
)
from app.services.sync_service import (
    InvalidPayloadError,
    UnknownEntityTypeError,
    pull_updates,
    push_item,
    resolve_conflict,
)

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/push", response_model=SyncPushResponse)
def push(
    payload: SyncPushRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> SyncPushResponse:
    results: list[SyncPushResult] = []
    for item in payload.items:
        try:
            result = push_item(db, payload.device_id, item)
        except UnknownEntityTypeError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unknown entity_type: {exc}"
            ) from exc
        except InvalidPayloadError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors) from exc
        results.append(result)
    db.commit()
    return SyncPushResponse(results=results)


@router.get("/pull", response_model=SyncPullResponse)
def pull(
    since: datetime | None = Query(default=None, description="Only return records updated after this time"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SyncPullResponse:
    data = pull_updates(db, since)
    return SyncPullResponse(
        server_time=datetime.now(timezone.utc),
        patients=data.get("patient", []),
        appointments=data.get("appointment", []),
        consultations=data.get("consultation", []),
        prescriptions=data.get("prescription", []),
        drug_stock=data.get("drug_stock", []),
    )


@router.post("/conflicts/{entity_type}/{entity_id}/resolve", response_model=SyncPushResult)
def resolve(
    entity_type: str,
    entity_id: str,
    payload: ConflictResolutionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SyncPushResult:
    try:
        result = resolve_conflict(
            db, entity_type, entity_id, keep_local=payload.keep_local, local_data=payload.local_data
        )
    except UnknownEntityTypeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unknown entity_type: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    db.commit()
    return result


@router.get("/log", response_model=list[SyncLogRead])
def get_sync_log(
    limit: int = Query(default=50, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SyncLog]:
    return db.query(SyncLog).order_by(SyncLog.synced_at.desc()).limit(limit).all()