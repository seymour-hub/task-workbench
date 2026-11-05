from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Notification
from ..schemas import NotifyTest
from ..services import notify_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _item(notification: Notification) -> dict:
    return {
        "id": notification.id,
        "channel": notification.channel,
        "kind": notification.kind,
        "title": notification.title,
        "body": notification.body,
        "status": notification.status,
        "attempts": notification.attempts,
        "last_error": notification.last_error,
        "sent_at": notification.sent_at,
        "read_at": notification.read_at,
        "created_at": notification.created_at,
    }


@router.get("")
def list_notifications(
    status: str | None = Query(default=None),
    kind: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    statement = select(Notification).order_by(Notification.created_at.desc()).limit(limit)
    if status:
        statement = statement.where(Notification.status == status)
    if kind:
        statement = statement.where(Notification.kind == kind)
    items = list(db.scalars(statement))
    return {
        "items": [_item(notification) for notification in items],
        "unread": db.scalar(
            select(func.count(Notification.id)).where(Notification.read_at.is_(None))
        )
        or 0,
    }


@router.post("/{notification_id}/retry")
def retry(notification_id: int, db: Session = Depends(get_db)):
    notification = db.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="通知不存在")
    result = notify_service.retry_notification(db, notification)
    db.commit()
    return result


@router.post("/test")
def test(payload: NotifyTest, db: Session = Depends(get_db)):
    result = notify_service.test_send(db, payload.text)
    db.commit()
    return result


@router.post("/digest")
def digest(db: Session = Depends(get_db)):
    result = notify_service.send_digest(db)
    db.commit()
    return result


@router.patch("/{notification_id}/read")
def mark_read(notification_id: int, db: Session = Depends(get_db)):
    notification = db.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="通知不存在")
    notification.read_at = time.time()
    db.commit()
    return {"ok": True}


@router.post("/read-all")
def mark_all_read(db: Session = Depends(get_db)):
    db.query(Notification).filter(Notification.read_at.is_(None)).update(
        {"read_at": time.time()}, synchronize_session=False
    )
    db.commit()
    return {"ok": True}
