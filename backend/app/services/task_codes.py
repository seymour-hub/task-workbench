"""Sequential task codes (T0001, T0002, ...), independent of database ids."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Task


def next_task_code(db: Session) -> str:
    """Return the next code after every code ever issued.

    Deleted tasks keep their code so Hermes' task ledger never sees the same
    number reused for a different task.
    """
    highest = 0
    for code in db.scalars(select(Task.code)):
        if not code or not code.startswith("T"):
            continue
        try:
            highest = max(highest, int(code[1:]))
        except ValueError:
            continue
    return f"T{highest + 1:04d}"
