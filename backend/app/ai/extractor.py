from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config
from ..db import get_bool_setting, get_int_setting, get_setting
from ..ingest.normalizer import message_prompt_text
from ..models import (
    Deliverable,
    FileIndex,
    InboxItem,
    Issue,
    MessageCache,
    Project,
    Segment,
    SessionCache,
    SyncState,
    Task,
    TaskEvent,
)
from ..services.deliverable_rules import (
    classify_deliverable,
    file_timestamp,
    is_final_by_name,
    logical_group,
    normalize_path,
    version_label,
)
from .client import AIError, chat_json
from .deduper import (
    dedupe_pending,
    fingerprint,
    find_similar,
    normalize_title,
    similarity,
)
from .prompts import SYSTEM_PROMPT, build_user_prompt
from .validator import parse_due_at, validate_extraction

PROMPT_CHAR_BUDGET = 12_000


def _usage_key() -> str:
    return "extract.usage." + datetime.now().strftime("%Y-%m-%d")


def get_daily_usage(db: Session) -> dict[str, int]:
    row = db.get(SyncState, _usage_key())
    if not row or not row.value:
        return {"prompt": 0, "completion": 0, "calls": 0}
    try:
        data = json.loads(row.value)
        return {
            "prompt": int(data.get("prompt", 0)),
            "completion": int(data.get("completion", 0)),
            "calls": int(data.get("calls", 0)),
        }
    except (ValueError, TypeError):
        return {"prompt": 0, "completion": 0, "calls": 0}


def add_daily_usage(db: Session, tokens: dict[str, int]) -> None:
    usage = get_daily_usage(db)
    usage["prompt"] += int(tokens.get("prompt", 0))
    usage["completion"] += int(tokens.get("completion", 0))
    usage["calls"] += 1
    key = _usage_key()
    row = db.get(SyncState, key)
    value = json.dumps(usage, ensure_ascii=False)
    if row is None:
        db.add(SyncState(key=key, value=value))
    else:
        row.value = value


def budget_remaining(db: Session) -> int:
    budget = get_int_setting(db, "extract.daily_token_budget", 200_000)
    usage = get_daily_usage(db)
    return max(0, budget - usage["prompt"] - usage["completion"])


def _build_message_text(messages: list[MessageCache]) -> tuple[str, set[int]]:
    lines: list[str] = []
    allowed: set[int] = set()
    used = 0
    for message in messages:
        if message.role not in {"user", "assistant", "tool"}:
            continue
        text = message_prompt_text(
            message, max_chars=800 if message.role == "tool" else 2_500
        )
        if used + len(text) > PROMPT_CHAR_BUDGET:
            remaining = PROMPT_CHAR_BUDGET - used
            if remaining > 200:
                lines.append(text[:remaining])
                allowed.add(message.hermes_message_id)
            break
        lines.append(text)
        allowed.add(message.hermes_message_id)
        used += len(text) + 1
    return "\n".join(lines), allowed


def _existing_project_names(db: Session) -> list[str]:
    return [name for name in db.scalars(select(Project.name).order_by(Project.id))]


def _recent_task_titles(db: Session, limit: int = 30) -> list[str]:
    return [
        title
        for title in db.scalars(
            select(Task.title)
            .where(Task.deleted_at.is_(None))
            .order_by(Task.id.desc())
            .limit(limit)
        )
    ]


def _existing_deliverable_paths(db: Session) -> set[str]:
    paths: set[str] = set()
    for row in db.scalars(select(Deliverable).limit(5_000)):
        paths.add(normalize_path(row.path_or_url).lower())
    for item in db.scalars(
        select(InboxItem)
        .where(
            InboxItem.kind == "deliverable",
            InboxItem.status.in_(["pending", "accepted"]),
        )
        .limit(2_000)
    ):
        value = (item.payload or {}).get("path_or_url")
        if value:
            paths.add(normalize_path(str(value)).lower())
    return paths


def _evidence_time(db: Session, message_ids: list[int] | None, default: float) -> float:
    if not message_ids:
        return default
    row = db.scalar(
        select(MessageCache)
        .where(MessageCache.hermes_message_id.in_(message_ids))
        .order_by(MessageCache.timestamp.asc())
        .limit(1)
    )
    return row.timestamp if row and row.timestamp else default


def _apply_to_task(
    db: Session, task: Task, result, segment: Segment
) -> dict[str, int]:
    counts = {"tasks": 0, "issues": 0, "deliverables": 0, "notes": 0, "milestones": 0}
    issue_titles = [
        title
        for title in db.scalars(select(Issue.title).where(Issue.task_id == task.id))
    ]
    for issue in result.issues:
        title = issue.title.strip()[:300]
        if not title or any(similarity(title, value) >= 85 for value in issue_titles):
            continue
        db.add(
            Issue(
                task_id=task.id,
                title=title,
                detail=issue.detail,
                severity=issue.severity,
                status=issue.status,
                source_message_id=(issue.evidence_message_ids or [None])[0],
            )
        )
        db.add(TaskEvent(task_id=task.id, type="issue_added", note=title[:200], actor="ai"))
        issue_titles.append(title)
        counts["issues"] += 1

    existing_paths = {
        normalize_path(path).lower()
        for path in db.scalars(
            select(Deliverable.path_or_url).where(Deliverable.task_id == task.id)
        )
    }
    for deliverable in result.deliverables:
        path = deliverable.path_or_url.strip()
        classification = classify_deliverable(path, deliverable.title)
        if not classification["ok"]:
            continue
        path_key = normalize_path(path).lower()
        if path_key in existing_paths:
            continue
        exists = bool(path and os.path.exists(path))
        group_key, logical_name = logical_group(
            deliverable.title, path, deliverable.group
        )
        version_at = file_timestamp(path)
        intermediate = bool(classification["is_intermediate"])
        if deliverable.is_final is True:
            final = True
        elif deliverable.is_final is False:
            final = False
        else:
            final = is_final_by_name(deliverable.title, path) and not intermediate
        db.add(
            Deliverable(
                task_id=task.id,
                file_id=_find_file_id(db, path) if exists else None,
                title=deliverable.title.strip()[:300],
                type=deliverable.type,
                path_or_url=path,
                file_size=os.path.getsize(path) if exists and os.path.isfile(path) else None,
                exists_flag=exists,
                attach_mode="auto_referenced",
                confidence=0.8,
                source_message_id=(deliverable.evidence_message_ids or [None])[0],
                group_key=group_key,
                logical_name=logical_name,
                version_label=deliverable.version
                or version_label(path, deliverable.title, version_at),
                version_at=version_at,
                is_final=final,
                is_intermediate=intermediate,
            )
        )
        db.add(
            TaskEvent(
                task_id=task.id,
                type="deliverable_added",
                note=deliverable.title.strip()[:200],
                actor="ai",
            )
        )
        existing_paths.add(path_key)
        counts["deliverables"] += 1

    if counts["deliverables"]:
        db.flush()
        from ..services.deliverable_service import recompute_finals

        recompute_finals(db, task.id)

    note_set = {
        note
        for note in db.scalars(
            select(TaskEvent.note).where(
                TaskEvent.task_id == task.id, TaskEvent.type == "ai_note"
            )
        )
        if note
    }
    for category, items in (
        ("decision", result.decisions),
        ("next_step", result.next_steps),
    ):
        for item in items:
            summary = (item.summary or "").strip()
            if not summary:
                continue
            note = f"[{category}] {summary}"
            if note in note_set:
                continue
            db.add(TaskEvent(task_id=task.id, type="ai_note", note=note, actor="ai"))
            note_set.add(note)
            counts["notes"] += 1

    milestone_set = {
        note
        for note in db.scalars(
            select(TaskEvent.note).where(
                TaskEvent.task_id == task.id, TaskEvent.type == "milestone"
            )
        )
        if note
    }
    for item in result.milestones:
        summary = (item.summary or "").strip()
        if not summary or summary in milestone_set:
            continue
        db.add(
            TaskEvent(
                task_id=task.id,
                type="milestone",
                note=summary[:500],
                actor="ai",
                created_at=_evidence_time(
                    db, item.evidence_message_ids, segment.started_at or time.time()
                ),
            )
        )
        milestone_set.add(summary)
        counts["milestones"] += 1

    return counts


def _find_file_id(db: Session, path: str) -> int | None:
    normalized = os.path.normcase(os.path.normpath(path))
    rows = db.scalars(select(FileIndex).where(FileIndex.exists_flag.is_(True)).limit(5000))
    for row in rows:
        if os.path.normcase(os.path.normpath(row.path)) == normalized:
            return row.id
    return None


def extract_segment(db: Session, segment: Segment, *, force: bool = False) -> dict[str, Any]:
    if segment.extract_status == "done" and not force:
        return {"skipped": True, "reason": "already done"}

    api_key = config.get_secret("DEEPSEEK_API_KEY")
    if not api_key:
        raise AIError("DEEPSEEK_API_KEY not found in Hermes .env or environment")

    segment.extract_status = "running"
    segment.extract_error = None
    db.flush()

    try:
        messages = list(
            db.scalars(
                select(MessageCache)
                .where(
                    MessageCache.session_id == segment.session_id,
                    MessageCache.hermes_message_id >= segment.start_message_id,
                    MessageCache.hermes_message_id <= segment.end_message_id,
                )
                .order_by(MessageCache.hermes_message_id.asc())
            )
        )
        message_text, allowed_ids = _build_message_text(messages)
        if not message_text.strip():
            segment.extract_status = "skipped"
            db.flush()
            return {"skipped": True, "reason": "empty segment"}

        session_title = segment.session_id
        cached_session = db.get(SessionCache, segment.session_id)
        if cached_session and cached_session.title:
            session_title = cached_session.title

        prompt = build_user_prompt(
            session_title=session_title,
            segment_start=datetime.fromtimestamp(segment.started_at).strftime("%Y-%m-%d %H:%M"),
            segment_end=datetime.fromtimestamp(segment.ended_at).strftime("%Y-%m-%d %H:%M"),
            message_text=message_text,
            projects=_existing_project_names(db),
            recent_tasks=_recent_task_titles(db),
        )

        raw, tokens = chat_json(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            api_key=api_key,
            base_url=get_setting(db, "ai.base_url", config.DEFAULT_DEEPSEEK_BASE_URL) or "",
            model=get_setting(db, "ai.model", config.DEFAULT_DEEPSEEK_MODEL) or "",
        )
        add_daily_usage(db, tokens)

        result = validate_extraction(raw, allowed_ids)
        if segment.task_id:
            task = db.get(Task, segment.task_id)
            if task and task.deleted_at is None:
                counts = _apply_to_task(db, task, result, segment)
                segment.extract_status = "done"
                segment.extracted_at = time.time()
                db.flush()
                return {
                    "skipped": False,
                    "counts": counts,
                    "tokens": tokens,
                    "task_id": task.id,
                }
            segment.task_id = None

        counts = {
            "tasks": 0,
            "issues": 0,
            "deliverables": 0,
            "deliverables_skipped": 0,
            "notes": 0,
        }

        for task in result.tasks:
            title = task.title.strip()
            fp = fingerprint(title)
            task_id, inbox_id, score = find_similar(db, title)
            is_exact = bool(task_id) and normalize_title(title) == normalize_title(
                db.get(Task, task_id).title if task_id else ""
            )
            payload = {
                "title": title,
                "description": task.description or "",
                "status": task.status,
                "priority": task.priority,
                "due_at": parse_due_at(task.due_at),
                "due_text": task.due_at,
                "project_hint": task.project_hint or "",
                "confidence": task.confidence,
                "evidence_message_ids": task.evidence_message_ids,
                "segment_id": segment.id,
                "dedup_score": round(score, 1),
                "possible_duplicate": bool(task_id or inbox_id),
            }
            db.add(
                InboxItem(
                    kind="task",
                    payload=payload,
                    confidence=task.confidence,
                    status="duplicate" if is_exact else "pending",
                    segment_id=segment.id,
                    source_message_ids=task.evidence_message_ids,
                    dedup_of_task_id=task_id,
                )
            )
            counts["tasks"] += 1

        for issue in result.issues:
            payload = {
                "title": issue.title.strip(),
                "detail": issue.detail or "",
                "severity": issue.severity,
                "status": issue.status,
                "evidence_message_ids": issue.evidence_message_ids,
                "segment_id": segment.id,
            }
            db.add(
                InboxItem(
                    kind="issue",
                    payload=payload,
                    confidence=0.6,
                    segment_id=segment.id,
                    source_message_ids=issue.evidence_message_ids,
                )
            )
            counts["issues"] += 1

        existing_paths = _existing_deliverable_paths(db)
        for deliverable in result.deliverables:
            path = deliverable.path_or_url.strip()
            classification = classify_deliverable(path, deliverable.title)
            if not classification["ok"]:
                counts["deliverables_skipped"] += 1
                continue
            if normalize_path(path).lower() in existing_paths:
                counts["deliverables_skipped"] += 1
                continue
            exists = os.path.exists(path) if os.path.isabs(path) else False
            group_key, logical_name = logical_group(
                deliverable.title, path, deliverable.group
            )
            version_at = file_timestamp(path)
            intermediate = bool(classification["is_intermediate"])
            if deliverable.is_final is True:
                final = True
            elif deliverable.is_final is False:
                final = False
            else:
                final = is_final_by_name(deliverable.title, path) and not intermediate
            payload = {
                "title": deliverable.title.strip(),
                "type": deliverable.type,
                "path_or_url": path,
                "exists": exists,
                "file_id": _find_file_id(db, path) if exists else None,
                "group_key": group_key,
                "logical_name": logical_name,
                "version": deliverable.version
                or version_label(path, deliverable.title, version_at),
                "version_at": version_at,
                "is_final": final,
                "is_intermediate": intermediate,
                "evidence_message_ids": deliverable.evidence_message_ids,
                "segment_id": segment.id,
            }
            db.add(
                InboxItem(
                    kind="deliverable",
                    payload=payload,
                    confidence=0.7,
                    segment_id=segment.id,
                    source_message_ids=deliverable.evidence_message_ids,
                )
            )
            existing_paths.add(normalize_path(path).lower())
            counts["deliverables"] += 1

        for note in result.decisions:
            db.add(
                InboxItem(
                    kind="note",
                    payload={
                        "summary": note.summary.strip(),
                        "category": "decision",
                        "evidence_message_ids": note.evidence_message_ids,
                        "segment_id": segment.id,
                    },
                    confidence=0.5,
                    segment_id=segment.id,
                    source_message_ids=note.evidence_message_ids,
                )
            )
            counts["notes"] += 1

        for note in result.next_steps:
            db.add(
                InboxItem(
                    kind="note",
                    payload={
                        "summary": note.summary.strip(),
                        "category": "next_step",
                        "evidence_message_ids": note.evidence_message_ids,
                        "segment_id": segment.id,
                    },
                    confidence=0.5,
                    segment_id=segment.id,
                    source_message_ids=note.evidence_message_ids,
                )
            )
            counts["notes"] += 1

        for milestone in result.milestones:
            summary = (milestone.summary or "").strip()
            if not summary:
                continue
            db.add(
                InboxItem(
                    kind="note",
                    payload={
                        "summary": summary,
                        "category": "milestone",
                        "evidence_message_ids": milestone.evidence_message_ids,
                        "segment_id": segment.id,
                    },
                    confidence=0.6,
                    segment_id=segment.id,
                    source_message_ids=milestone.evidence_message_ids,
                )
            )
            counts["notes"] += 1

        segment.extract_status = "done"
        segment.extracted_at = time.time()
        db.flush()
        return {"skipped": False, "counts": counts, "tokens": tokens}
    except Exception as exc:  # noqa: BLE001
        segment.extract_status = "failed"
        segment.extract_error = f"{type(exc).__name__}: {exc}"
        db.flush()
        raise


def extract_pending(db: Session, *, limit: int = 5, force: bool = False) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "ok": False,
        "processed": 0,
        "failed": 0,
        "skipped": 0,
        "results": [],
        "budget_remaining": budget_remaining(db),
        "error": None,
    }
    if not get_bool_setting(db, "extract.enabled", True):
        summary["error"] = "extraction disabled"
        return summary
    if not force and budget_remaining(db) <= 0:
        summary["error"] = "daily token budget exhausted"
        return summary

    window_days = get_int_setting(db, "extract.window_days", 14)
    cutoff = time.time() - max(1, window_days) * 86_400
    sources = _extract_sources(db)
    statement = (
        select(Segment)
        .join(SessionCache, SessionCache.id == Segment.session_id)
        .where(
            Segment.extract_status.in_(["pending", "failed"]),
            Segment.ended_at >= cutoff,
        )
        .order_by(Segment.ended_at.desc())
        .limit(limit)
    )
    if sources:
        statement = statement.where(SessionCache.source.in_(sources))
    segments = list(db.scalars(statement))
    if not segments:
        summary["ok"] = True
        return summary

    for segment in segments:
        try:
            result = extract_segment(db, segment, force=force)
            if result.get("skipped"):
                summary["skipped"] += 1
            else:
                summary["processed"] += 1
                summary["results"].append(
                    {"segment_id": segment.id, **result.get("counts", {})}
                )
        except AIError as exc:
            summary["failed"] += 1
            summary["error"] = str(exc)
            break
        except Exception as exc:  # noqa: BLE001
            summary["failed"] += 1
            summary["error"] = f"{type(exc).__name__}: {exc}"
    if summary["processed"]:
        summary["deduped"] = dedupe_pending(db)["marked"]
    summary["ok"] = summary["failed"] == 0
    summary["budget_remaining"] = budget_remaining(db)
    return summary


def _extract_sources(db: Session) -> list[str]:
    raw = get_setting(db, "extract.sources", "feishu") or "feishu"
    return [value.strip() for value in raw.split(",") if value.strip()]


def pending_segment_count(db: Session) -> int:
    sources = _extract_sources(db)
    statement = (
        select(func.count(Segment.id))
        .join(SessionCache, SessionCache.id == Segment.session_id)
        .where(Segment.extract_status.in_(["pending", "failed"]))
    )
    if sources:
        statement = statement.where(SessionCache.source.in_(sources))
    return int(db.scalar(statement) or 0)
