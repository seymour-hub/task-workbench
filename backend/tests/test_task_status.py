from __future__ import annotations

from app.models import Task
from app.services.task_service import change_status


def test_status_change_keeps_sort_order(db):
    task = Task(title="状态测试", status="todo", sort_order=123.0, project_id=1)
    db.add(task)
    db.commit()

    change_status(db, task, "in_progress")
    db.commit()
    db.refresh(task)

    assert task.status == "in_progress"
    assert task.sort_order == 123.0


def test_done_sets_and_reset_clears_completion_time(db):
    task = Task(title="完成测试", status="in_progress", sort_order=1.0, project_id=1)
    db.add(task)
    db.commit()

    change_status(db, task, "done")
    db.commit()
    db.refresh(task)
    assert task.status == "done"
    assert task.completed_at is not None
    assert task.progress == 100

    change_status(db, task, "todo")
    db.commit()
    db.refresh(task)
    assert task.status == "todo"
    assert task.completed_at is None
    assert task.ended_at is None


def test_explicit_sort_order_is_applied(db):
    task = Task(title="排序测试", status="todo", sort_order=1.0, project_id=1)
    db.add(task)
    db.commit()

    change_status(db, task, "in_progress", sort_order=42.0)
    db.commit()
    db.refresh(task)
    assert task.sort_order == 42.0
