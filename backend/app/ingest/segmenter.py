from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import MessageCache, Segment

GAP_SECONDS = 2 * 60 * 60
MAX_MESSAGES = 80
MAX_CHARS = 20_000
MIN_MESSAGES = 3


def _day_key(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")


def segment_messages(messages: list[MessageCache]) -> list[dict]:
    usable = [
        message
        for message in messages
        if message.role in {"user", "assistant", "tool"} and (message.content or "").strip()
    ]
    if not usable:
        return []

    raw: list[list[MessageCache]] = []
    current: list[MessageCache] = []
    current_chars = 0

    for message in usable:
        if current:
            previous = current[-1]
            gap = message.timestamp - previous.timestamp
            day_changed = _day_key(message.timestamp) != _day_key(previous.timestamp)
            if (
                gap > GAP_SECONDS
                or day_changed
                or len(current) >= MAX_MESSAGES
                or current_chars + len(message.content or "") > MAX_CHARS
            ):
                raw.append(current)
                current = []
                current_chars = 0
        current.append(message)
        current_chars += len(message.content or "")
    if current:
        raw.append(current)

    # Merge tiny fragments into the previous chunk when it stays within limits.
    merged: list[list[MessageCache]] = []
    for chunk in raw:
        if (
            merged
            and len(chunk) < MIN_MESSAGES
            and len(merged[-1]) + len(chunk) <= MAX_MESSAGES
        ):
            merged[-1].extend(chunk)
        else:
            merged.append(chunk)

    segments: list[dict] = []
    for chunk in merged:
        if len(chunk) < MIN_MESSAGES:
            continue
        if not any(message.role in {"user", "assistant"} for message in chunk):
            continue
        digest = hashlib.sha256(
            "\x1f".join(
                f"{message.hermes_message_id}:{message.content_hash}" for message in chunk
            ).encode("utf-8")
        ).hexdigest()
        segments.append(
            {
                "session_id": chunk[0].session_id,
                "start_message_id": chunk[0].hermes_message_id,
                "end_message_id": chunk[-1].hermes_message_id,
                "started_at": chunk[0].timestamp,
                "ended_at": chunk[-1].timestamp,
                "message_count": len(chunk),
                "content_hash": digest,
            }
        )
    return segments


def reset_stale_running(db: Session) -> None:
    for segment in db.scalars(select(Segment).where(Segment.extract_status == "running")):
        segment.extract_status = "pending"
        segment.extract_error = None
    db.flush()


def rebuild_segments(db: Session, session_id: str) -> int:
    """Rebuild pending segments for one session without touching extracted ones."""
    done_end = db.scalar(
        select(Segment.end_message_id)
        .where(
            Segment.session_id == session_id,
            Segment.extract_status.in_(["done", "running"]),
        )
        .order_by(Segment.end_message_id.desc())
        .limit(1)
    )
    cutoff = int(done_end or 0)

    db.execute(
        delete(Segment).where(
            Segment.session_id == session_id,
            Segment.extract_status.in_(["pending", "failed"]),
        )
    )

    messages = list(
        db.scalars(
            select(MessageCache)
            .where(
                MessageCache.session_id == session_id,
                MessageCache.hermes_message_id > cutoff,
            )
            .order_by(MessageCache.hermes_message_id.asc())
        )
    )
    if not messages:
        return 0

    created = 0
    for payload in segment_messages(messages):
        db.add(Segment(**payload, extract_status="pending"))
        created += 1
    db.flush()
    return created
