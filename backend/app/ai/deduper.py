from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import InboxItem, Task

PUNCT_RE = re.compile(r"[\s\W_]+", re.UNICODE)


def normalize_title(title: str) -> str:
    text = unicodedata.normalize("NFKC", title or "").lower()
    text = PUNCT_RE.sub("", text)
    return text[:300]


def fingerprint(title: str) -> str:
    return normalize_title(title)


def _bigrams(text: str) -> set[str]:
    return {text[index : index + 2] for index in range(max(0, len(text) - 1))}


def similarity(left: str, right: str) -> float:
    a = normalize_title(left)
    b = normalize_title(right)
    if not a or not b:
        return 0.0
    scores = [
        float(fuzz.token_set_ratio(a, b)),
        float(fuzz.token_sort_ratio(a, b)),
        float(fuzz.partial_ratio(a, b)),
    ]
    grams_a, grams_b = _bigrams(a), _bigrams(b)
    if grams_a and grams_b:
        scores.append(len(grams_a & grams_b) / len(grams_a | grams_b) * 100)
    return max(scores)


def find_similar(
    db: Session,
    title: str,
    *,
    threshold: float = 82.0,
) -> tuple[int | None, int | None, float]:
    """Return (task_id, inbox_id, score) for the closest existing record."""
    best_score = 0.0
    best_task: int | None = None
    best_inbox: int | None = None

    tasks = db.scalars(
        select(Task)
        .where(Task.deleted_at.is_(None), Task.status != "cancelled")
        .order_by(Task.id.desc())
        .limit(600)
    )
    for task in tasks:
        score = similarity(title, task.title)
        if score > best_score:
            best_score, best_task, best_inbox = score, task.id, None

    items = db.scalars(
        select(InboxItem)
        .where(InboxItem.kind == "task", InboxItem.status == "pending")
        .order_by(InboxItem.id.desc())
        .limit(300)
    )
    for item in items:
        payload = item.payload or {}
        score = similarity(title, str(payload.get("title") or ""))
        if score > best_score:
            best_score, best_task, best_inbox = score, None, item.id

    if best_score < threshold:
        return None, None, best_score
    return best_task, best_inbox, best_score


def dedupe_pending(db: Session, *, threshold: float = 82.0) -> dict:
    """Mark near-duplicate pending task candidates, keeping the highest confidence one."""
    items = list(
        db.scalars(
            select(InboxItem)
            .where(InboxItem.kind == "task", InboxItem.status == "pending")
            .order_by(InboxItem.confidence.desc(), InboxItem.id.asc())
        )
    )
    tasks = list(
        db.scalars(
            select(Task)
            .where(Task.deleted_at.is_(None), Task.status != "cancelled")
            .order_by(Task.id.desc())
            .limit(1000)
        )
    )
    kept: list[tuple[int, str]] = []
    marked = 0
    for item in items:
        title = str((item.payload or {}).get("title") or "").strip()
        if not title:
            continue
        best_score = 0.0
        duplicate_task: int | None = None
        duplicate_inbox: int | None = None
        for task in tasks:
            score = similarity(title, task.title)
            if score > best_score:
                best_score, duplicate_task, duplicate_inbox = score, task.id, None
        for other_id, other_title in kept:
            score = similarity(title, other_title)
            if score > best_score:
                best_score, duplicate_task, duplicate_inbox = score, None, other_id
        if best_score >= threshold:
            item.status = "duplicate"
            item.dedup_of_task_id = duplicate_task
            item.payload = {
                **(item.payload or {}),
                "possible_duplicate": True,
                "dedup_score": round(best_score, 1),
                "duplicate_of_inbox_id": duplicate_inbox,
            }
            marked += 1
        else:
            kept.append((item.id, title))
    db.flush()
    return {"checked": len(items), "marked": marked, "kept": len(kept)}
