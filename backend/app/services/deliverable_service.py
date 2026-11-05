from __future__ import annotations

import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Deliverable, InboxItem
from .deliverable_rules import (
    classify_deliverable,
    file_timestamp,
    logical_group,
    version_label,
)


def _extension(path: str) -> str:
    return os.path.splitext((path or "").replace("/", "\\"))[1].lower()


def recompute_finals(db: Session, task_id: int | None = None) -> int:
    """Mark one final version per (task, logical output, file format)."""
    statement = select(Deliverable)
    if task_id:
        statement = statement.where(Deliverable.task_id == task_id)
    items = list(db.scalars(statement))
    groups: dict[tuple, list[Deliverable]] = {}
    for item in items:
        key = (item.task_id, item.group_key or "other", _extension(item.path_or_url))
        groups.setdefault(key, []).append(item)

    for group in groups.values():
        for item in group:
            item.is_final = False
        group.sort(
            key=lambda item: item.version_at
            or file_timestamp(item.path_or_url, item.created_at)
        )
        candidates = [item for item in group if not item.is_intermediate]
        if not candidates:
            continue
        # Exactly one final per (task, logical output, format): the newest
        # version wins. Older finals become history instead of all showing
        # the "最终版" badge.
        candidates.sort(
            key=lambda item: (
                item.version_at
                or file_timestamp(item.path_or_url, item.created_at),
                item.id,
            )
        )
        candidates[-1].is_final = True
    db.flush()
    return len(groups)


def dedupe_deliverables(db: Session) -> int:
    """Remove duplicate rows that point at the same file path."""
    items = list(db.scalars(select(Deliverable)))
    grouped: dict[str, list[Deliverable]] = {}
    for item in items:
        key = os.path.normcase(os.path.normpath(item.path_or_url))
        grouped.setdefault(key, []).append(item)
    removed = 0
    for duplicates in grouped.values():
        if len(duplicates) <= 1:
            continue
        duplicates.sort(
            key=lambda item: (
                not item.is_intermediate,
                bool(item.is_final),
                item.version_at or 0,
            ),
            reverse=True,
        )
        keeper = duplicates[0]
        for extra in duplicates[1:]:
            db.delete(extra)
            removed += 1
        keeper.is_final = keeper.is_final or not keeper.is_intermediate
    db.flush()
    return removed


def cleanup_existing(db: Session) -> dict:
    """Reclassify existing deliverables and pending inbox candidates.

    Auto-attached scripts, caches and scratch artifacts are removed from the
    deliverable table (the files themselves are never touched).
    """
    removed = 0
    kept = 0
    rejected_inbox = 0
    enriched_inbox = 0

    for item in list(db.scalars(select(Deliverable))):
        classification = classify_deliverable(item.path_or_url, item.title)
        if not classification["ok"]:
            if item.attach_mode in {"auto_referenced", "auto_matched"}:
                db.delete(item)
                removed += 1
            else:
                item.is_intermediate = True
                item.is_final = False
            continue
        group_key, logical_name = logical_group(item.title, item.path_or_url)
        item.group_key = group_key
        item.logical_name = logical_name
        item.version_at = item.version_at or file_timestamp(
            item.path_or_url, item.created_at
        )
        item.version_label = item.version_label or version_label(
            item.path_or_url, item.title, item.version_at
        )
        item.is_intermediate = bool(classification["is_intermediate"])
        kept += 1

    for item in list(
        db.scalars(
            select(InboxItem).where(
                InboxItem.kind == "deliverable",
                InboxItem.status == "pending",
            )
        )
    ):
        payload = item.payload or {}
        path = str(payload.get("path_or_url") or "")
        title = str(payload.get("title") or "")
        classification = classify_deliverable(path, title)
        if not classification["ok"]:
            item.status = "rejected"
            item.payload = {**payload, "reject_reason": classification["reason"]}
            rejected_inbox += 1
            continue
        group_key, logical_name = logical_group(
            title, path, payload.get("logical_name")
        )
        version_at = payload.get("version_at") or file_timestamp(path)
        item.payload = {
            **payload,
            "group_key": group_key,
            "logical_name": logical_name,
            "version": payload.get("version")
            or version_label(path, title, version_at),
            "version_at": version_at,
            "is_intermediate": classification["is_intermediate"],
            "is_final": bool(payload.get("is_final"))
            and not classification["is_intermediate"],
        }
        enriched_inbox += 1

    db.flush()
    duplicates_removed = dedupe_deliverables(db)
    recompute_finals(db)
    return {
        "deliverables_removed": removed,
        "deliverables_kept": kept,
        "duplicates_removed": duplicates_removed,
        "inbox_rejected": rejected_inbox,
        "inbox_enriched": enriched_inbox,
    }
