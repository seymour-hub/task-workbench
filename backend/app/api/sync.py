from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..ai.extractor import extract_pending, get_daily_usage, pending_segment_count
from ..db import get_db, get_int_setting
from ..ingest.sync_service import sync_now, sync_status
from ..models import MessageCache, Segment, SessionCache

router = APIRouter(tags=["sync"])


class SyncRunRequest(BaseModel):
    backfill_days: int | None = None
    full: bool = False


class ExtractRunRequest(BaseModel):
    limit: int = 5
    force: bool = False


@router.get("/sync/status")
def get_sync_status(db: Session = Depends(get_db)):
    return sync_status(db)


@router.post("/sync/run")
def run_sync(payload: SyncRunRequest | None = None, db: Session = Depends(get_db)):
    request = payload or SyncRunRequest()
    result = sync_now(db, backfill_days=request.backfill_days, full=request.full)
    if result.get("ok"):
        from ..services.workflow_service import process_after_sync

        result["workflow"] = process_after_sync(db)
    db.commit()
    return result


@router.post("/ai/extract")
def run_extract(payload: ExtractRunRequest | None = None, db: Session = Depends(get_db)):
    from ..services.task_link_service import link_unlinked_segments

    link_unlinked_segments(db)
    request = payload or ExtractRunRequest()
    result = extract_pending(db, limit=request.limit, force=request.force)
    db.commit()
    return result


@router.get("/ai/usage")
def usage(db: Session = Depends(get_db)):
    return {
        "today": get_daily_usage(db),
        "budget": get_int_setting(db, "extract.daily_token_budget", 200_000),
        "pending_segments": pending_segment_count(db),
    }


@router.get("/sources/sessions")
def list_sessions(
    limit: int = Query(default=50, ge=1, le=500), db: Session = Depends(get_db)
):
    sessions = list(
        db.scalars(
            select(SessionCache)
            .order_by(SessionCache.last_activity_at.desc().nullslast())
            .limit(limit)
        )
    )
    return {
        "items": [
            {
                "id": session.id,
                "source": session.source,
                "chat_type": session.chat_type,
                "title": session.title or session.id,
                "message_count": session.message_count,
                "last_activity_at": session.last_activity_at,
                "cwd": session.cwd,
            }
            for session in sessions
        ]
    }


@router.get("/sources/messages")
def source_messages(
    ids: str = Query(description="逗号分隔的 Hermes 消息 id"),
    db: Session = Depends(get_db),
):
    try:
        message_ids = [int(value.strip()) for value in ids.split(",") if value.strip()]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="ids 格式错误") from exc
    if not message_ids:
        return {"items": []}
    rows = list(
        db.scalars(
            select(MessageCache)
            .where(MessageCache.hermes_message_id.in_(message_ids))
            .order_by(MessageCache.hermes_message_id.asc())
        )
    )
    items: list[dict] = []
    seen_hashes: set[str] = set()
    for row in rows:
        if not (row.content or "").strip():
            continue
        if row.content_hash:
            if row.content_hash in seen_hashes:
                continue
            seen_hashes.add(row.content_hash)
        items.append(
            {
                "id": row.hermes_message_id,
                "session_id": row.session_id,
                "role": row.role,
                "content": row.content,
                "tool_name": row.tool_name,
                "timestamp": row.timestamp,
                "truncated": row.truncated,
            }
        )
    return {"items": items}


@router.get("/segments")
def list_segments(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    statement = select(Segment).order_by(Segment.ended_at.desc()).limit(limit)
    if status:
        statement = statement.where(Segment.extract_status == status)
    segments = list(db.scalars(statement))
    return {
        "items": [
            {
                "id": segment.id,
                "session_id": segment.session_id,
                "start_message_id": segment.start_message_id,
                "end_message_id": segment.end_message_id,
                "started_at": segment.started_at,
                "ended_at": segment.ended_at,
                "message_count": segment.message_count,
                "extract_status": segment.extract_status,
                "extract_error": segment.extract_error,
                "extracted_at": segment.extracted_at,
            }
            for segment in segments
        ]
    }


@router.post("/segments/{segment_id}/retry")
def retry_segment(segment_id: int, db: Session = Depends(get_db)):
    segment = db.get(Segment, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="片段不存在")
    segment.extract_status = "pending"
    segment.extract_error = None
    db.commit()
    return {"ok": True}
