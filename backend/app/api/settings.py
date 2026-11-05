from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config
from ..db import DEFAULT_SETTINGS, get_db, set_setting
from ..models import Deliverable, FileIndex, InboxItem, MessageCache, Project, Task

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def get_settings(db: Session = Depends(get_db)):
    from ..db import get_setting

    values = {key: get_setting(db, key, default) for key, default in DEFAULT_SETTINGS.items()}
    return {"settings": values, "defaults": DEFAULT_SETTINGS}


@router.put("")
def update_settings(payload: dict, db: Session = Depends(get_db)):
    allowed_prefixes = (
        "ui.",
        "work.",
        "sync.",
        "extract.",
        "ai.",
        "notify.",
        "files.",
    )
    for key, value in payload.items():
        if not isinstance(key, str) or not key.startswith(allowed_prefixes):
            continue
        set_setting(db, key, None if value is None else str(value))
    db.commit()
    return get_settings(db)


@router.post("/backup")
def backup_database():
    import sqlite3
    import time as _time

    config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = config.BACKUP_DIR / f"workbench-{_time.strftime('%Y%m%d-%H%M%S')}.db"
    source = sqlite3.connect(config.DB_PATH)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    backups = sorted(config.BACKUP_DIR.glob("workbench-*.db"), key=lambda p: p.stat().st_mtime)
    for old in backups[:-7]:
        old.unlink(missing_ok=True)
    return {"ok": True, "path": str(target), "kept": min(len(backups), 7)}


@router.get("/health")
def health(db: Session = Depends(get_db)):
    status = config.hermes_home_status()
    status.update(
        {
            "workbench_db": str(config.DB_PATH),
            "workbench_db_exists": config.DB_PATH.exists(),
            "web_dist_exists": config.WEB_DIST.exists(),
            "tasks": db.scalar(
                select(func.count(Task.id)).where(Task.deleted_at.is_(None))
            )
            or 0,
            "projects": db.scalar(select(func.count(Project.id))) or 0,
            "messages_cached": db.scalar(select(func.count(MessageCache.id))) or 0,
            "files_indexed": db.scalar(select(func.count(FileIndex.id))) or 0,
            "deliverables": db.scalar(select(func.count(Deliverable.id))) or 0,
            "inbox_pending": db.scalar(
                select(func.count(InboxItem.id)).where(InboxItem.status == "pending")
            )
            or 0,
        }
    )
    return status
