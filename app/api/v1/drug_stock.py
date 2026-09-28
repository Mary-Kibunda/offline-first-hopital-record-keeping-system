from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.drug_stock import DrugStock
from app.models.mixins import new_uuid
from app.models.user import User
from app.schemas.drug_stock import DrugStockCreate, DrugStockRead, DrugStockUpdate

router = APIRouter(prefix="/drug-stock", tags=["drug-stock"])


@router.post("", response_model=DrugStockRead, status_code=status.HTTP_201_CREATED)
def create_drug_stock(
    payload: DrugStockCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> DrugStock:
    drug_id = payload.id or new_uuid()
    if db.get(DrugStock, drug_id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A drug stock entry with this id already exists.")

    drug = DrugStock(id=drug_id, **payload.model_dump(exclude={"id"}))
    db.add(drug)
    db.commit()
    db.refresh(drug)
    return drug


@router.get("", response_model=list[DrugStockRead])
def list_drug_stock(
    clinic_id: str | None = Query(default=None),
    low_stock_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DrugStock]:
    query = db.query(DrugStock)
    if clinic_id:
        query = query.filter(DrugStock.clinic_id == clinic_id)
    if low_stock_only:
        query = query.filter(DrugStock.quantity_available <= DrugStock.reorder_threshold)
    return query.order_by(DrugStock.drug_name).all()


@router.patch("/{drug_id}", response_model=DrugStockRead)
def update_drug_stock(
    drug_id: str,
    payload: DrugStockUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DrugStock:
    """Used when dispensing (decrementing quantity_available) or restocking."""
    drug = db.get(DrugStock, drug_id)
    if drug is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drug stock entry not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(drug, key, value)
    drug.version += 1

    db.commit()
    db.refresh(drug)
    return drug