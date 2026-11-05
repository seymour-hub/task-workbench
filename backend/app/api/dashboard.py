from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..services.stats_service import dashboard_summary, search

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/summary")
def get_summary(db: Session = Depends(get_db)):
    return dashboard_summary(db)


@router.get("/dashboard/deadlines")
def get_deadlines(limit: int = Query(default=6, ge=1, le=50), db: Session = Depends(get_db)):
    data = dashboard_summary(db)
    return {"items": data["deadlines"][:limit]}


@router.get("/search")
def global_search(q: str = Query(min_length=1), db: Session = Depends(get_db)):
    return search(db, q)
