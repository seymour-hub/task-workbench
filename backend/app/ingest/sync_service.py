from __future__ import annotations

import json
import time
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ..db import get_int_setting, get_setting
from ..models import MessageCache, Segment, SessionCache, SyncState
from .hermes_reader import HermesDatabaseError, HermesReader
from .normalizer import normalize_message
from .segmenter import rebuild_segments, reset_stale_running


def get_state(db: Session, key: str, default: str | None = None) -> str | None:
    row = db.get(SyncState, key)
    if row and row.value is not None:
        return row.value
    return default


def set_state(db: Session, key: str, value: str | None) -> None:
    row = db.get(SyncState, key)
    if row is None:
        db.add(SyncState(key=key, value=value))
    else:
        row.value = value


def _upsert_sessions(db: Session, reader: HermesReader) -> int:
    count = 0
    for row in reader.iter_sessions():
        session_id = str(row.get("id") or "")
        if not session_id:
            continue
        db.merge(
            SessionCache(
                id=session_id,
                source=row.get("source"),
                chat_id=row.get("chat_id"),
                chat_type=row.get("chat_type"),
                title=row.get("title"),
                started_at=row.get("started_at"),
                ended_at=row.get("ended_at"),
                message_count=int(row.get("message_count") or 0),
                cwd=row.get("cwd"),
                last_activity_at=row.get("last_activity_at"),
                archived=bool(row.get("archived") or False),
            )
        )
        count += 1
    db.flush()
    return count


def sync_now(
    db: Session,
    *,
    backfill_days: int | None = None,
    full: bool = False,
    batch_size: int = 500,
) -> dict[str, Any]:
    started = time.time()
    reader = HermesReader()
    summary: dict[str, Any] = {
        "ok": False,
        "started_at": started,
        "new_messages": 0,
        "sessions": 0,
        "segments": 0,
        "cursor": 0,
        "error": None,
    }

    try:
        schema = reader.schema_fingerprint()
        set_state(db, "schema_fingerprint", json.dumps(schema, ensure_ascii=False))
        summary["sessions"] = _upsert_sessions(db, reader)

        reset_stale_running(db)

        cursor = 0 if full else int(get_state(db, "cursor.message_id", "0") or 0)
        if cursor == 0 and not full:
            days = (
                backfill_days
                if backfill_days is not None
                else get_int_setting(db, "sync.backfill_days", 90)
            )
            since = time.time() - max(1, days) * 86_400
            first_id = reader.first_message_id_since(since)
            cursor = max(0, first_id - 1)

        before = db.scalar(select(func.count(MessageCache.id))) or 0
        affected_sessions: set[str] = set()
        max_seen = cursor

        while True:
            rows = list(reader.iter_messages(cursor, limit=batch_size))
            if not rows:
                break
            payloads = [normalize_message(row) for row in rows]
            payloads = [payload for payload in payloads if payload]
            if payloads:
                statement = (
                    sqlite_insert(MessageCache)
                    .values(payloads)
                    .on_conflict_do_nothing(index_elements=["hermes_message_id"])
                )
                db.execute(statement)
                affected_sessions.update(
                    payload["session_id"] for payload in payloads if payload["session_id"]
                )
            cursor = int(rows[-1]["id"])
            max_seen = max(max_seen, cursor)
            db.flush()
            if len(rows) < batch_size:
                break

        after = db.scalar(select(func.count(MessageCache.id))) or 0
        summary["new_messages"] = int(after - before)

        for session_id in affected_sessions:
            summary["segments"] += rebuild_segments(db, session_id)

        set_state(db, "cursor.message_id", str(max_seen))
        set_state(db, "last_sync_at", str(time.time()))
        set_state(db, "last_sync_new_messages", str(summary["new_messages"]))
        set_state(db, "last_sync_sessions", str(summary["sessions"]))
        set_state(db, "last_sync_error", "")
        summary["cursor"] = max_seen
        summary["ok"] = True
        db.flush()
    except HermesDatabaseError as exc:
        set_state(db, "last_sync_error", str(exc))
        summary["error"] = str(exc)
        db.flush()
    except Exception as exc:  # noqa: BLE001 - surface any sync failure to the UI
        set_state(db, "last_sync_error", f"{type(exc).__name__}: {exc}")
        summary["error"] = f"{type(exc).__name__}: {exc}"
        db.flush()

    summary["duration_ms"] = int((time.time() - started) * 1000)
    return summary


def sync_status(db: Session) -> dict[str, Any]:
    reader = HermesReader()
    window_days = get_int_setting(db, "extract.window_days", 14)
    window_cutoff = time.time() - max(1, window_days) * 86_400
    try:
        source_messages = reader.count_messages()
        source_exists = True
        source_error = None
    except Exception as exc:  # noqa: BLE001
        source_messages = 0
        source_exists = False
        source_error = str(exc)

    return {
        "source_exists": source_exists,
        "source_error": source_error,
        "source_messages": source_messages,
        "cached_messages": db.scalar(select(func.count(MessageCache.id))) or 0,
        "cached_sessions": db.scalar(select(func.count(SessionCache.id))) or 0,
        "segments_pending": db.scalar(
            select(func.count(Segment.id)).where(Segment.extract_status == "pending")
        )
        or 0,
        "segments_pending_window": db.scalar(
            select(func.count(Segment.id))
            .join(SessionCache, SessionCache.id == Segment.session_id)
            .where(
                Segment.extract_status.in_(["pending", "failed"]),
                Segment.ended_at >= window_cutoff,
                SessionCache.source.in_(
                    [
                        value.strip()
                        for value in (
                            get_setting(db, "extract.sources", "feishu") or "feishu"
                        ).split(",")
                        if value.strip()
                    ]
                ),
            )
        )
        or 0,
        "segments_done": db.scalar(
            select(func.count(Segment.id)).where(Segment.extract_status == "done")
        )
        or 0,
        "segments_failed": db.scalar(
            select(func.count(Segment.id)).where(Segment.extract_status == "failed")
        )
        or 0,
        "cursor": get_state(db, "cursor.message_id", "0"),
        "last_sync_at": get_state(db, "last_sync_at"),
        "last_sync_new_messages": get_state(db, "last_sync_new_messages"),
        "last_sync_error": get_state(db, "last_sync_error", ""),
        "schema_fingerprint": get_state(db, "schema_fingerprint"),
    }
