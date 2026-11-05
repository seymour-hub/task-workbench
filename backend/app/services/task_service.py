from __future__ import annotations

import os
import time
from typing import Any

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from ..models import (
    Deliverable,
    Issue,
    Member,
    Project,
    Task,
    TaskEvent,
)
from ..schemas import TaskCreate, TaskUpdate

STATUS_LABELS = {
    "todo": "待处理",
    "in_progress": "进行中",
    "done": "已完成",
    "cancelled": "已取消",
}


def is_overdue(task: Task, now: float | None = None) -> bool:
    current = now if now is not None else time.time()
    return bool(
        task.due_at
        and task.status not in {"done", "cancelled"}
        and task.due_at < current
    )


def _maps(db: Session, tasks: list[Task]) -> tuple[dict, dict, dict, dict]:
    project_ids = {task.project_id for task in tasks if task.project_id}
    member_ids = {task.assignee_id for task in tasks if task.assignee_id}
    task_ids = [task.id for task in tasks]

    projects = {
        project.id: project
        for project in db.scalars(select(Project).where(Project.id.in_(project_ids)))
    } if project_ids else {}
    members = {
        member.id: member
        for member in db.scalars(select(Member).where(Member.id.in_(member_ids)))
    } if member_ids else {}

    issue_counts = dict(
        db.execute(
            select(Issue.task_id, func.count(Issue.id))
            .where(Issue.task_id.in_(task_ids), Issue.status == "open")
            .group_by(Issue.task_id)
        ).all()
    ) if task_ids else {}
    deliverable_counts = dict(
        db.execute(
            select(Deliverable.task_id, func.count(Deliverable.id))
            .where(Deliverable.task_id.in_(task_ids))
            .group_by(Deliverable.task_id)
        ).all()
    ) if task_ids else {}

    return projects, members, issue_counts, deliverable_counts


def serialize_tasks(db: Session, tasks: list[Task]) -> list[dict[str, Any]]:
    projects, members, issue_counts, deliverable_counts = _maps(db, tasks)
    now = time.time()
    result = []
    for task in tasks:
        project = projects.get(task.project_id)
        member = members.get(task.assignee_id)
        result.append(
            {
                "id": task.id,
                "project_id": task.project_id,
                "project_name": project.name if project else None,
                "project_color": project.color if project else None,
                "assignee_id": task.assignee_id,
                "assignee_name": member.name if member else None,
                "assignee_color": member.avatar_color if member else None,
                "title": task.title,
                "description": task.description,
                "status": task.status,
                "status_label": STATUS_LABELS.get(task.status, task.status),
                "priority": task.priority,
                "due_at": task.due_at,
                "start_at": task.start_at,
                "started_at": task.started_at,
                "ended_at": task.ended_at,
                "completed_at": task.completed_at,
                "progress": task.progress,
                "source_type": task.source_type,
                "source_session_id": task.source_session_id,
                "chat_id": task.chat_id,
                "code": task.code,
                "auto_created": task.auto_created,
                "source_message_ids": task.source_message_ids or [],
                "source_excerpt": task.source_excerpt,
                "ai_confidence": task.ai_confidence,
                "category": task.category,
                "subcategory": task.subcategory,
                "work_types": task.work_types or [],
                "sort_order": task.sort_order,
                "overdue": is_overdue(task, now),
                "issue_count": issue_counts.get(task.id, 0),
                "deliverable_count": deliverable_counts.get(task.id, 0),
                "created_at": task.created_at,
                "updated_at": task.updated_at,
            }
        )
    return result


def serialize_task(db: Session, task: Task) -> dict[str, Any]:
    return serialize_tasks(db, [task])[0]


def list_tasks(
    db: Session,
    *,
    status: str | None = None,
    project_id: int | None = None,
    priority: str | None = None,
    category: str | None = None,
    work_type: str | None = None,
    q: str | None = None,
    due: str | None = None,
    limit: int = 500,
    include_cancelled: bool = False,
) -> list[Task]:
    statement = select(Task).where(Task.deleted_at.is_(None))
    if not include_cancelled and status != "cancelled":
        statement = statement.where(Task.status != "cancelled")
    if status and status not in {"overdue", "today", "open"}:
        statement = statement.where(Task.status == status)
    if status == "open":
        statement = statement.where(Task.status.not_in(["done", "cancelled"]))
    if project_id:
        statement = statement.where(Task.project_id == project_id)
    if priority:
        statement = statement.where(Task.priority == priority)
    if category:
        statement = statement.where(Task.category == category)
    if work_type:
        from sqlalchemy import String, cast

        statement = statement.where(
            cast(Task.work_types, String).like(f'%"{work_type}"%')
        )
    if q:
        like = f"%{q}%"
        statement = statement.where(
            or_(Task.title.like(like), Task.description.like(like))
        )

    now = time.time()
    if status == "overdue":
        statement = statement.where(
            Task.due_at.is_not(None),
            Task.due_at < now,
            Task.status.not_in(["done", "cancelled"]),
        )
    if status == "today":
        start = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
        end = start + 86_400
        statement = statement.where(
            Task.due_at.is_not(None), Task.due_at >= start, Task.due_at < end
        )
    if due == "week":
        end = time.time() + 7 * 86_400
        statement = statement.where(Task.due_at.is_not(None), Task.due_at < end)

    time_order = func.coalesce(
        Task.ended_at, Task.started_at, Task.created_at
    ).desc()
    # Tasks in progress stay pinned above finished work, then newest first.
    status_rank = case((Task.status == "in_progress", 0), else_=1)
    statement = statement.order_by(
        status_rank,
        time_order,
        Task.started_at.desc().nullslast(),
        Task.id.desc(),
    ).limit(limit)
    return list(db.scalars(statement))


def create_task(
    db: Session,
    data: TaskCreate,
    *,
    actor: str = "me",
    source_event: str = "created",
    source_session_id: str | None = None,
    source_message_ids: list[int] | None = None,
    source_excerpt: str | None = None,
    ai_confidence: float | None = None,
) -> Task:
    assignee_id = data.assignee_id
    if assignee_id is None:
        me = db.scalar(select(Member).where(Member.is_me.is_(True)).limit(1))
        assignee_id = me.id if me else None
    task = Task(
        title=data.title.strip(),
        description=data.description,
        project_id=data.project_id,
        assignee_id=assignee_id,
        status=data.status,
        priority=data.priority,
        due_at=data.due_at,
        start_at=data.start_at,
        started_at=data.started_at or time.time(),
        ended_at=data.ended_at,
        progress=data.progress,
        source_type=data.source_type,
        source_session_id=source_session_id,
        source_message_ids=source_message_ids,
        source_excerpt=source_excerpt,
        ai_confidence=ai_confidence,
        category=data.category,
        subcategory=data.subcategory,
        work_types=data.work_types,
        sort_order=time.time() * 1000,
    )
    if task.status == "done":
        task.completed_at = data.ended_at or time.time()
        task.ended_at = data.ended_at or task.completed_at
        task.progress = 100
    db.add(task)
    db.flush()
    db.add(
        TaskEvent(
            task_id=task.id,
            type=source_event,
            to_value=task.status,
            actor=actor,
        )
    )
    db.flush()
    return task


def update_task(db: Session, task: Task, data: TaskUpdate, *, actor: str = "me") -> Task:
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        # sort_order is NOT NULL in the database; a status-only update must
        # not overwrite it with None.
        if field == "sort_order" and value is None:
            continue
        if field == "status":
            old = task.status
            if old != value:
                task.status = value
                if value == "done":
                    task.completed_at = task.ended_at or time.time()
                    task.ended_at = task.completed_at
                    task.progress = 100
                elif old == "done":
                    task.completed_at = None
                    task.ended_at = None
                    task.progress = 0
                db.add(
                    TaskEvent(
                        task_id=task.id,
                        type="status_changed",
                        from_value=old,
                        to_value=value,
                        actor=actor,
                    )
                )
            continue
        if field == "priority":
            old = task.priority
            if old != value:
                task.priority = value
                db.add(
                    TaskEvent(
                        task_id=task.id,
                        type="priority_changed",
                        from_value=old,
                        to_value=value,
                        actor=actor,
                    )
                )
            continue
        if field == "due_at":
            old = task.due_at
            if old != value:
                task.due_at = value
                db.add(
                    TaskEvent(
                        task_id=task.id,
                        type="due_changed",
                        from_value=str(old) if old else None,
                        to_value=str(value) if value else None,
                        actor=actor,
                    )
                )
            continue
        setattr(task, field, value)
    task.updated_at = time.time()
    db.flush()
    return task


def change_status(db: Session, task: Task, status: str, sort_order: float | None = None) -> Task:
    payload: dict[str, Any] = {"status": status}
    if sort_order is not None:
        payload["sort_order"] = sort_order
    return update_task(db, task, TaskUpdate(**payload))


def add_comment(db: Session, task: Task, note: str, *, actor: str = "me") -> TaskEvent:
    event = TaskEvent(task_id=task.id, type="comment", note=note.strip(), actor=actor)
    db.add(event)
    db.flush()
    return event


def get_detail(db: Session, task: Task) -> dict[str, Any]:
    base = serialize_task(db, task)
    events = list(
        db.scalars(
            select(TaskEvent)
            .where(TaskEvent.task_id == task.id)
            .order_by(TaskEvent.created_at.desc())
        )
    )
    issues = list(
        db.scalars(
            select(Issue).where(Issue.task_id == task.id).order_by(Issue.created_at.desc())
        )
    )
    deliverables = list(
        db.scalars(
            select(Deliverable)
            .where(Deliverable.task_id == task.id)
            .order_by(Deliverable.created_at.desc())
        )
    )
    base["timeline"] = [
        {
            "id": event.id,
            "type": event.type,
            "from_value": event.from_value,
            "to_value": event.to_value,
            "note": event.note,
            "message_id": event.message_id,
            "actor": event.actor,
            "created_at": event.created_at,
        }
        for event in events
    ]
    base["milestones"] = [
        {
            "id": event.id,
            "type": event.type,
            "note": event.note,
            "created_at": event.created_at,
            "actor": event.actor,
        }
        for event in sorted(
            (
                event
                for event in events
                if event.type in {"milestone", "milestone_start", "milestone_end"}
            ),
            key=lambda event: event.created_at,
        )
    ]
    base["issues"] = [
        {
            "id": issue.id,
            "title": issue.title,
            "detail": issue.detail,
            "severity": issue.severity,
            "status": issue.status,
            "resolution": issue.resolution,
            "source_message_id": issue.source_message_id,
            "created_at": issue.created_at,
            "resolved_at": issue.resolved_at,
        }
        for issue in issues
    ]
    base["deliverables"] = [
        {
            "id": item.id,
            "task_id": item.task_id,
            "file_id": item.file_id,
            "title": item.title,
            "type": item.type,
            "path_or_url": item.path_or_url,
            "file_size": item.file_size,
            "exists_flag": item.exists_flag,
            "attach_mode": item.attach_mode,
            "confidence": item.confidence,
            "group_key": item.group_key,
            "logical_name": item.logical_name,
            "version_label": item.version_label,
            "version_at": item.version_at,
            "is_final": item.is_final,
            "is_intermediate": item.is_intermediate,
            "created_at": item.created_at,
        }
        for item in deliverables
    ]
    return base


def merge_tasks(
    db: Session,
    target_id: int,
    source_ids: list[int],
    *,
    note: str | None = None,
) -> dict[str, Any]:
    """Merge granular sub-tasks into one project-level task.

    Issues, timeline events and deliverables move to the target; source tasks
    are soft-deleted. Duplicate deliverable paths are collapsed.
    """
    target = db.get(Task, target_id)
    if not target or target.deleted_at is not None:
        raise ValueError("目标任务不存在")
    sources = [
        task
        for task in db.scalars(select(Task).where(Task.id.in_(source_ids)))
        if task.id != target_id and task.deleted_at is None
    ]
    moved_events = 0
    moved_issues = 0
    moved_deliverables = 0
    titles: list[str] = []

    for source in sources:
        titles.append(source.title)
        for event in db.scalars(select(TaskEvent).where(TaskEvent.task_id == source.id)):
            event.task_id = target.id
            moved_events += 1
        for issue in db.scalars(select(Issue).where(Issue.task_id == source.id)):
            issue.task_id = target.id
            moved_issues += 1
        for item in db.scalars(select(Deliverable).where(Deliverable.task_id == source.id)):
            item.task_id = target.id
            moved_deliverables += 1
        source.deleted_at = time.time()
        source.status = "cancelled"

    db.flush()

    # Collapse duplicate deliverable paths after the move.
    items = list(
        db.scalars(
            select(Deliverable).where(Deliverable.task_id == target.id)
        )
    )
    grouped: dict[str, list[Deliverable]] = {}
    for item in items:
        key = os.path.normcase(os.path.normpath(item.path_or_url))
        grouped.setdefault(key, []).append(item)
    removed_duplicates = 0
    for duplicates in grouped.values():
        if len(duplicates) <= 1:
            continue
        duplicates.sort(
            key=lambda item: (
                not item.is_intermediate,
                item.is_final,
                item.version_at or 0,
            ),
            reverse=True,
        )
        keeper = duplicates[0]
        for extra in duplicates[1:]:
            db.delete(extra)
            removed_duplicates += 1
        keeper.is_final = keeper.is_final or not keeper.is_intermediate

    db.add(
        TaskEvent(
            task_id=target.id,
            type="merged",
            note=note
            or f"合并了 {len(sources)} 个过程任务：" + "；".join(titles),
            actor="me",
        )
    )
    db.flush()
    from .deliverable_service import recompute_finals

    recompute_finals(db, target.id)
    db.flush()
    return {
        "target_id": target.id,
        "merged": len(sources),
        "moved_events": moved_events,
        "moved_issues": moved_issues,
        "moved_deliverables": moved_deliverables,
        "removed_duplicates": removed_duplicates,
    }


def board_data(db: Session, *, project_id: int | None = None) -> dict[str, Any]:
    tasks = list_tasks(db, project_id=project_id, limit=1000)
    serialized = serialize_tasks(db, tasks)
    now = time.time()
    lanes: dict[str, list[dict[str, Any]]] = {
        "todo": [],
        "in_progress": [],
        "done": [],
        "overdue": [],
    }
    for item in serialized:
        if item["status"] == "done":
            lanes["done"].append(item)
        elif item["status"] == "cancelled":
            continue
        elif item["overdue"]:
            lanes["overdue"].append(item)
        elif item["status"] == "in_progress":
            lanes["in_progress"].append(item)
        else:
            lanes["todo"].append(item)
    return {
        "lanes": lanes,
        "counts": {key: len(value) for key, value in lanes.items()},
    }
