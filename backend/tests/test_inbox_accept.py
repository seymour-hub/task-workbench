import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.api.inbox import accept_item
from app.models import InboxItem, Task, TaskEvent
from app.schemas import InboxAccept


def _item(**payload):
    return InboxItem(
        kind="task",
        payload={
            "title": "整理项目材料",
            "description": "输出一页纸纪要",
            "status": "todo",
            "priority": "high",
            "due_at": None,
            "confidence": 0.9,
            "evidence_message_ids": [101, 102],
            **payload,
        },
        confidence=0.9,
        status="pending",
        source_message_ids=[101, 102],
    )


def test_accept_creates_task_and_event(db):
    item = _item()
    db.add(item)
    db.commit()

    result = accept_item(item.id, InboxAccept(project_id=1), False, db)
    assert result["title"] == "整理项目材料"
    assert result["assignee_id"] == 1
    assert item.status == "accepted"
    assert db.scalar(select(func.count(Task.id))) == 1
    event_types = set(db.scalars(select(TaskEvent.type)))
    assert "accepted" in event_types


def test_accept_twice_returns_conflict(db):
    item = _item()
    item.status = "accepted"
    db.add(item)
    db.commit()
    with pytest.raises(HTTPException) as exc:
        accept_item(item.id, InboxAccept(), False, db)
    assert exc.value.status_code == 409


def test_duplicate_requires_force(db):
    item = _item()
    item.status = "duplicate"
    db.add(item)
    db.commit()
    with pytest.raises(HTTPException) as exc:
        accept_item(item.id, InboxAccept(), False, db)
    assert exc.value.status_code == 409
    result = accept_item(item.id, InboxAccept(), True, db)
    assert result["id"] >= 1
