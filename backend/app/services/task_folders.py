"""Create the per-task output folder as soon as a task gets its code."""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import DeliverableRoot, Task

INVALID = re.compile(r'[\\/:*?"<>|]')


def task_folder_name(task: Task) -> str:
    title = INVALID.sub("-", task.title or "未命名任务")
    title = re.sub(r"\s+", " ", title).strip().rstrip(" .")
    return f"{task.code}-{title}"


def ensure_task_folder(db: Session, task: Task) -> Path | None:
    """Create outputs/documents/<code>-<title>/ when an output root exists."""
    if not task.code:
        return None
    root = db.scalar(
        select(DeliverableRoot)
        .where(
            DeliverableRoot.enabled.is_(True),
            DeliverableRoot.label.like("%Hermes 输出%"),
        )
        .order_by(DeliverableRoot.id)
        .limit(1)
    )
    if root is None or not root.path:
        return None
    base = Path(root.path)
    documents = base / "documents"
    if documents.is_dir():
        base = documents
    folder = base / task_folder_name(task)
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    return folder
