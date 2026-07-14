"""Query pagination + sorting shared by list endpoints."""

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.schemas.common import PageParams


def apply_sort(stmt: Select, model: Any, sort: str | None, allowed: set[str]) -> Select:
    if not sort:
        return stmt
    descending = sort.startswith("-")
    field = sort.lstrip("-")
    if field not in allowed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot sort by '{field}'. Allowed: {sorted(allowed)}",
        )
    column = getattr(model, field)
    return stmt.order_by(column.desc() if descending else column.asc())


def paginate(db: Session, stmt: Select, params: PageParams) -> tuple[list[Any], int]:
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(stmt.offset(params.offset).limit(params.page_size)).scalars().all()
    return list(rows), total
