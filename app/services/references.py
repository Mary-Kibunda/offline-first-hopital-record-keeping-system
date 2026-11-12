"""Validation helpers for foreign-key identifiers in API payloads."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session


class MissingReferenceError(ValueError):
    def __init__(self, field: str, value: Any, table: str):
        self.field = field
        self.value = value
        self.table = table
        super().__init__(f"Related record for '{field}' was not found.")


def validate_references(db: Session, model: type, values: dict[str, Any]) -> None:
    """Raise when a provided foreign-key value does not identify a stored row."""
    for column in model.__table__.columns:
        if column.name not in values:
            continue
        value = values[column.name]
        if value is None and column.nullable:
            continue
        for foreign_key in column.foreign_keys:
            target = foreign_key.column
            if db.execute(select(target).where(target == value)).first() is None:
                raise MissingReferenceError(column.name, value, target.table.name)
