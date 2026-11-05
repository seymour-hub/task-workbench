from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..models import InboxItem, MessageCache, Task

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    status = config.hermes_home_status()
    return {
        "ok": status["hermes_db_exists"],
        "service": "任务管理工作台",
        "hermes": status,
        "counts": {
            "tasks": db.scalar(
                select(func.count(Task.id)).where(Task.deleted_at.is_(None))
            )
            or 0,
            "messages": db.scalar(select(func.count(MessageCache.id))) or 0,
            "inbox_pending": db.scalar(
                select(func.count(InboxItem.id)).where(InboxItem.status == "pending")
            )
            or 0,
        },
    }


@router.get("/healthz")
def healthz():
    return {"ok": True}
