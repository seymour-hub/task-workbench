from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..services.stats_service import stats_overview

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/overview")
def get_overview(
    period: str = Query(default="week", pattern="^(week|month|quarter)$"),
    db: Session = Depends(get_db),
):
    return stats_overview(db, period=period)


@router.get("/trend")
def get_trend(
    period: str = Query(default="week", pattern="^(week|month|quarter)$"),
    db: Session = Depends(get_db),
):
    return {"items": stats_overview(db, period=period)["trend"]}
