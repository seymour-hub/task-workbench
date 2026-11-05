from __future__ import annotations

import os
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.deduper import similarity
from ..models import (
    Deliverable,
    InboxItem,
    Issue,
    MessageCache,
    Segment,
    SessionCache,
    Task,
    TaskEvent,
)
from .deliverable_rules import (
    classify_deliverable,
    file_timestamp,
    is_final_by_name,
    logical_group,
    normalize_path,
    version_label,
)

ACTIVE_STATUSES = {"todo", "in_progress"}


def chat_id_for_session(db: Session, session_id: str | None) -> str | None:
    if not session_id:
        return None
    session = db.get(SessionCache, session_id)
    return (session.chat_id if session and session.chat_id else session_id)


def active_tasks_for_chat(db: Session, chat_id: str | None) -> list[Task]:
    if not chat_id:
        return []
    return list(
        db.scalars(
            select(Task)
            .where(
                Task.deleted_at.is_(None),
                Task.chat_id == chat_id,
                Task.status == "in_progress",
            )
            .order_by(Task.started_at.desc().nullslast(), Task.id.desc())
        )
    )


def segment_text(db: Session, segment: Segment) -> str:
    messages = list(
        db.scalars(
            select(MessageCache)
            .where(
                MessageCache.session_id == segment.session_id,
                MessageCache.hermes_message_id >= segment.start_message_id,
                MessageCache.hermes_message_id <= segment.end_message_id,
            )
            .order_by(MessageCache.hermes_message_id.asc())
            .limit(30)
        )
    )
    return "\n".join(
        (message.content or "")[:800] for message in messages if message.content
    )[:8_000]


def link_segment(
    db: Session,
    segment: Segment,
    task: Task,
    *,
    method: str,
    confidence: float = 1.0,
) -> None:
    segment.task_id = task.id
    segment.link_method = method
    segment.link_confidence = confidence
    db.flush()
    if segment.extract_status == "done":
        apply_pending_inbox_to_task(db, task, segment.id)


def apply_pending_inbox_to_task(db: Session, task: Task, segment_id: int) -> dict[str, int]:
    items = list(
        db.scalars(
            select(InboxItem).where(
                InboxItem.segment_id == segment_id,
                InboxItem.status == "pending",
            )
        )
    )
    counts = {"issues": 0, "deliverables": 0, "notes": 0}
    issue_titles = [
        title
        for title in db.scalars(select(Issue.title).where(Issue.task_id == task.id))
    ]
    note_set = {
        note
        for note in db.scalars(
            select(TaskEvent.note).where(
                TaskEvent.task_id == task.id, TaskEvent.type == "ai_note"
            )
        )
        if note
    }
    existing_paths = {
        normalize_path(path).lower()
        for path in db.scalars(
            select(Deliverable.path_or_url).where(Deliverable.task_id == task.id)
        )
    }

    for item in items:
        payload = item.payload or {}
        if item.kind == "task":
            item.status = "accepted"
            item.reviewed_at = time.time()
            continue
        if item.kind == "issue":
            title = str(payload.get("title") or "").strip()[:300]
            if title and not any(similarity(title, value) >= 85 for value in issue_titles):
                db.add(
                    Issue(
                        task_id=task.id,
                        title=title,
                        detail=payload.get("detail"),
                        severity=payload.get("severity") or "medium",
                        source_message_id=(item.source_message_ids or [None])[0],
                    )
                )
                db.add(
                    TaskEvent(
                        task_id=task.id,
                        type="issue_added",
                        note=title[:200],
                        actor="ai",
                    )
                )
                issue_titles.append(title)
                counts["issues"] += 1
            item.status = "accepted"
            item.reviewed_at = time.time()
            continue
        if item.kind == "deliverable":
            path = str(payload.get("path_or_url") or "")
            title = str(payload.get("title") or os.path.basename(path))[:300]
            classification = classify_deliverable(path, title)
            if not classification["ok"]:
                item.status = "rejected"
                item.reviewed_at = time.time()
                item.payload = {**payload, "reject_reason": classification["reason"]}
                continue
            path_key = normalize_path(path).lower()
            if path_key in existing_paths:
                item.status = "accepted"
                item.reviewed_at = time.time()
                continue
            exists = bool(path and os.path.exists(path))
            group_key, logical_name = logical_group(
                title, path, payload.get("logical_name")
            )
            version_at = payload.get("version_at") or file_timestamp(path)
            intermediate = bool(
                payload.get("is_intermediate", classification["is_intermediate"])
            )
            final = payload.get("is_final")
            if final is None:
                final = is_final_by_name(title, path) and not intermediate
            db.add(
                Deliverable(
                    task_id=task.id,
                    file_id=payload.get("file_id"),
                    title=title,
                    type=payload.get("type") or "file",
                    path_or_url=path,
                    file_size=os.path.getsize(path)
                    if exists and os.path.isfile(path)
                    else None,
                    exists_flag=exists,
                    attach_mode="auto_referenced",
                    confidence=0.8,
                    source_message_id=(item.source_message_ids or [None])[0],
                    group_key=group_key,
                    logical_name=logical_name,
                    version_label=payload.get("version")
                    or version_label(path, title, version_at),
                    version_at=version_at,
                    is_final=bool(final),
                    is_intermediate=intermediate,
                )
            )
            db.add(
                TaskEvent(
                    task_id=task.id,
                    type="deliverable_added",
                    note=title[:200],
                    actor="ai",
                )
            )
            existing_paths.add(path_key)
            counts["deliverables"] += 1
            item.status = "accepted"
            item.reviewed_at = time.time()
            continue
        if item.kind == "note":
            summary = str(payload.get("summary") or "").strip()
            if summary:
                note = f"[{payload.get('category') or 'note'}] {summary}"
                if note not in note_set:
                    db.add(
                        TaskEvent(
                            task_id=task.id,
                            type="ai_note",
                            note=note,
                            actor="ai",
                        )
                    )
                    note_set.add(note)
                    counts["notes"] += 1
            item.status = "accepted"
            item.reviewed_at = time.time()
    db.flush()
    if counts["deliverables"]:
        from .deliverable_service import recompute_finals

        recompute_finals(db, task.id)
    return counts


def link_unlinked_segments(db: Session, *, limit: int = 100) -> dict[str, int]:
    segments = list(
        db.scalars(
            select(Segment)
            .where(Segment.task_id.is_(None))
            .order_by(Segment.ended_at.desc())
            .limit(limit)
        )
    )
    linked = 0
    ambiguous = 0
    for segment in segments:
        chat_id = chat_id_for_session(db, segment.session_id)
        tasks = active_tasks_for_chat(db, chat_id)
        # Never attach historical segments to a task that started later.
        tasks = [
            task
            for task in tasks
            if not task.started_at or segment.ended_at >= task.started_at - 300
        ]
        if not tasks:
            continue
        if len(tasks) == 1:
            link_segment(
                db, segment, tasks[0], method="single_active", confidence=1.0
            )
            linked += 1
            continue
        text = segment_text(db, segment)
        scored = sorted(
            ((similarity(text[:3000], task.title), task) for task in tasks),
            key=lambda pair: pair[0],
            reverse=True,
        )
        best_score, best_task = scored[0]
        margin = best_score - (scored[1][0] if len(scored) > 1 else 0)
        if best_score >= 65 and margin >= 8:
            link_segment(
                db,
                segment,
                best_task,
                method="similarity",
                confidence=best_score / 100,
            )
            linked += 1
        else:
            ambiguous += 1
    db.flush()
    return {"linked": linked, "ambiguous": ambiguous}
