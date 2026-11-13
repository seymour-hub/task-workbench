"""Reopen an existing task when the user says "restart Txxxx"."""

from __future__ import annotations

import re
import time

from sqlalchemy.orm import Session

from ..models import Task, TaskEvent

RESTART_RE = re.compile(
    r"(?P<before>T\d{4}).{0,30}?(重启|重新启动|重开|继续做|继续)"
    r"|(重启|重新启动|重开|继续做|继续).{0,30}?(?P<after>T\d{4})",
    re.IGNORECASE,
)


def find_restart_code(text: str) -> str | None:
    match = RESTART_RE.search(text or "")
    if not match:
        return None
    code = match.group("before") or match.group("after")
    return code.upper() if code else None


def restart_task(
    db: Session,
    task: Task,
    *,
    note: str,
    actor: str = "ai",
    created_at: float | None = None,
) -> Task:
    """Move a finished task back to in_progress, keeping its code and folder."""
    task.status = "in_progress"
    task.ended_at = None
    task.completed_at = None
    if (task.progress or 0) >= 100:
        task.progress = 50
    task.updated_at = time.time()
    db.add(
        TaskEvent(
            task_id=task.id,
            type="restarted",
            note=(note or "任务重启")[:300],
            actor=actor,
            created_at=created_at or time.time(),
        )
    )
    db.flush()
    return task
