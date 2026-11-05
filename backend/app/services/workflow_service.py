from __future__ import annotations

import threading
from typing import Any

from sqlalchemy.orm import Session

from .confirmation_service import scan_replies
from .intent_service import scan_intents
from .task_link_service import link_unlinked_segments

# The scheduler and the "检查新任务" button must not run the state machine at
# the same time; overlapping runs used to create duplicate tasks from one
# Feishu reply.
_WORKFLOW_LOCK = threading.Lock()


def process_after_sync(
    db: Session, *, since: float | None = None
) -> dict[str, Any]:
    """Run the Feishu task-confirmation state machine after a sync."""
    if not _WORKFLOW_LOCK.acquire(timeout=90):
        return {
            "skipped": "another workflow run is in progress",
            "replies": {"checked": 0, "resolved": 0},
            "intents": {"checked": 0, "starts": 0, "completes": 0, "questions": []},
            "links": {"linked": 0, "ambiguous": 0},
        }
    try:
        replies = scan_replies(db, since=since)
        intents = scan_intents(db, since=since)
        links = link_unlinked_segments(db)
        db.flush()
        # Commit while still holding the lock so the next run sees the new
        # confirmation statuses and cannot replay the same reply.
        db.commit()
        return {"replies": replies, "intents": intents, "links": links}
    finally:
        _WORKFLOW_LOCK.release()
