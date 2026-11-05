from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..db import get_db
from ..ingest.sync_service import sync_now
from ..models import PendingConfirmation
from ..services.confirmation_service import resolve_confirmation
from ..services.workflow_service import process_after_sync

router = APIRouter(prefix="/workflow", tags=["workflow"])


class CheckRequest(BaseModel):
    recent_hours: int = 24


def _pending_item(item: PendingConfirmation) -> dict:
    payload = item.payload or {}
    return {
        "id": item.id,
        "code": item.code,
        "kind": item.kind,
        "title": payload.get("title") or "",
        "payload": payload,
        "status": item.status,
        "created_at": item.created_at,
        "question_sent": payload.get("question_sent"),
        "question_error": payload.get("question_error"),
    }


@router.post("/check")
def check_workflow(payload: CheckRequest | None = None, db: Session = Depends(get_db)):
    request = payload or CheckRequest()
    recent_hours = max(1, min(168, request.recent_hours))
    sync_result = sync_now(db)
    since = time.time() - recent_hours * 3600
    workflow = process_after_sync(db, since=since)
    pending = list(
        db.scalars(
            select(PendingConfirmation)
            .where(PendingConfirmation.status == "pending")
            .order_by(PendingConfirmation.created_at.desc())
        )
    )
    db.commit()
    return {
        "ok": bool(sync_result.get("ok")),
        "recent_hours": recent_hours,
        "sync": sync_result,
        "workflow": workflow,
        "pending": [_pending_item(item) for item in pending],
        "pending_count": len(pending),
    }


@router.get("/pending")
def pending_confirmations(db: Session = Depends(get_db)):
    items = list(
        db.scalars(
            select(PendingConfirmation)
            .where(
                PendingConfirmation.status == "pending",
                PendingConfirmation.expires_at > time.time(),
            )
            .order_by(PendingConfirmation.created_at.desc())
        )
    )
    return {"items": [_pending_item(item) for item in items]}


@router.post("/confirmations/{confirmation_id}/resolve")
def resolve(
    confirmation_id: int,
    action: str = Query(pattern="^(accept|reject)$"),
    db: Session = Depends(get_db),
):
    confirmation = db.get(PendingConfirmation, confirmation_id)
    if not confirmation or confirmation.status != "pending":
        raise HTTPException(status_code=404, detail="待确认任务不存在或已处理")
    # Claim atomically so a concurrent Feishu scan cannot create it too.
    claimed = db.execute(
        update(PendingConfirmation)
        .where(
            PendingConfirmation.id == confirmation_id,
            PendingConfirmation.status == "pending",
        )
        .values(status="resolving", resolved_at=time.time())
    )
    db.commit()
    if claimed.rowcount != 1:
        raise HTTPException(status_code=409, detail="该确认已被处理")
    db.refresh(confirmation)
    if confirmation.kind == "start_task":
        text = "加入" if action == "accept" else "不用"
    else:
        text = "完成" if action == "accept" else "取消"
    result = resolve_confirmation(
        db, confirmation, text, "yes" if action == "accept" else "no"
    )
    db.commit()
    return result
