from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    CalendarEvent,
    Deliverable,
    InboxItem,
    Issue,
    Member,
    PendingConfirmation,
    Project,
    Task,
)
from .task_service import is_overdue, list_tasks, serialize_tasks


def day_start(timestamp: float | None = None) -> float:
    current = time.localtime(timestamp or time.time())
    return time.mktime(
        (current.tm_year, current.tm_mon, current.tm_mday, 0, 0, 0, 0, 0, -1)
    )


def week_start(timestamp: float | None = None) -> float:
    start = day_start(timestamp)
    weekday = time.localtime(start).tm_wday
    return start - weekday * 86_400


def _task_counts(tasks: list[Task]) -> dict[str, int]:
    now = time.time()
    buckets = {"todo": 0, "in_progress": 0, "done": 0, "overdue": 0, "cancelled": 0}
    for task in tasks:
        if task.status == "cancelled":
            buckets["cancelled"] += 1
        elif task.status == "done":
            buckets["done"] += 1
        elif is_overdue(task, now):
            buckets["overdue"] += 1
        elif task.status == "in_progress":
            buckets["in_progress"] += 1
        else:
            buckets["todo"] += 1
    return buckets


def dashboard_summary(db: Session) -> dict[str, Any]:
    now = time.time()
    today_start = day_start(now)
    today_end = today_start + 86_400
    this_week = week_start(now)
    last_week = this_week - 7 * 86_400

    tasks = list(db.scalars(select(Task).where(Task.deleted_at.is_(None))))
    buckets = _task_counts(tasks)
    total = sum(buckets.values())
    completed = buckets["done"]
    pending = buckets["todo"] + buckets["in_progress"] + buckets["overdue"]
    cancelled = buckets["cancelled"]

    project_ids = {
        task.project_id for task in tasks if task.project_id and task.status != "cancelled"
    }
    active_project_ids = {
        task.project_id
        for task in tasks
        if task.project_id and task.status in {"todo", "in_progress"}
    }

    completed_this_week = sum(
        1
        for task in tasks
        if task.status == "done" and task.completed_at and task.completed_at >= this_week
    )
    completed_last_week = sum(
        1
        for task in tasks
        if task.status == "done"
        and task.completed_at
        and last_week <= task.completed_at < this_week
    )
    if completed_last_week:
        delta = round(
            (completed_this_week - completed_last_week) / completed_last_week * 100
        )
    else:
        delta = 100 if completed_this_week else 0

    deadlines = [
        task
        for task in tasks
        if task.due_at and task.status not in {"done", "cancelled"}
    ]
    deadlines.sort(key=lambda task: task.due_at or 0)

    today_tasks = [
        task
        for task in tasks
        if task.status not in {"done", "cancelled"}
        and (
            (task.due_at and today_start <= task.due_at < today_end)
            or (task.start_at and today_start <= task.start_at < today_end)
        )
    ]
    if len(today_tasks) < 3:
        extra = [
            task
            for task in tasks
            if task.status == "in_progress" and task not in today_tasks
        ]
        today_tasks.extend(extra[: 3 - len(today_tasks)])
    today_tasks.sort(
        key=lambda task: (
            0 if task.status == "in_progress" else 1,
            task.due_at or task.start_at or now,
        )
    )

    projects = list(db.scalars(select(Project).where(Project.status == "active")))
    weekly_progress = []
    for project in projects[:6]:
        project_tasks = [task for task in tasks if task.project_id == project.id]
        if not project_tasks:
            continue
        done = sum(1 for task in project_tasks if task.status == "done")
        weekly_progress.append(
            {
                "project_id": project.id,
                "name": project.name,
                "color": project.color,
                "total": len(project_tasks),
                "done": done,
                "progress": round(done / len(project_tasks) * 100),
            }
        )
    weekly_progress.sort(key=lambda item: item["progress"], reverse=True)

    events = list(
        db.scalars(
            select(CalendarEvent).where(
                CalendarEvent.start_at >= today_start,
                CalendarEvent.start_at < today_end,
            )
        )
    )
    schedule = [
        {
            "id": f"event-{event.id}",
            "title": event.title,
            "start_at": event.start_at,
            "end_at": event.end_at,
            "location": event.location,
            "color": event.color,
            "kind": "event",
            "task_id": event.task_id,
        }
        for event in events
    ]
    for task in today_tasks:
        if task.due_at:
            schedule.append(
                {
                    "id": f"task-{task.id}",
                    "title": task.title,
                    "start_at": task.due_at,
                    "end_at": None,
                    "location": None,
                    "color": "#EF4444",
                    "kind": "deadline",
                    "task_id": task.id,
                }
            )
    schedule.sort(key=lambda item: item["start_at"] or 0)

    inbox_breakdown = dict(
        db.execute(
            select(InboxItem.kind, func.count(InboxItem.id))
            .where(InboxItem.status == "pending")
            .group_by(InboxItem.kind)
        ).all()
    )
    inbox_pending = int(inbox_breakdown.get("task", 0))
    confirmations_pending = int(
        db.scalar(
            select(func.count(PendingConfirmation.id)).where(
                PendingConfirmation.status == "pending",
                PendingConfirmation.expires_at > now,
            )
        )
        or 0
    )

    return {
        "stats": {
            "total": total,
            "completed": completed,
            "pending": pending,
            "projects": len(project_ids),
            "active_projects": len(active_project_ids),
            "cancelled": cancelled,
            "overdue": buckets["overdue"],
            "completion_delta": delta,
            "completed_this_week": completed_this_week,
        },
        "donut": {
            "total": total,
            "segments": [
                {"key": "in_progress", "label": "进行中", "value": buckets["in_progress"], "color": "#4F7DFF"},
                {"key": "done", "label": "已完成", "value": buckets["done"], "color": "#22C55E"},
                {"key": "todo", "label": "待处理", "value": buckets["todo"], "color": "#F59E0B"},
                {"key": "overdue", "label": "已逾期", "value": buckets["overdue"], "color": "#EF4444"},
                {"key": "cancelled", "label": "已取消", "value": cancelled, "color": "#64748B"},
            ],
        },
        "deadlines": serialize_tasks(db, deadlines[:6]),
        "today_tasks": serialize_tasks(db, today_tasks[:8]),
        "weekly_progress": weekly_progress,
        "schedule": schedule,
        "inbox_pending": inbox_pending,
        "inbox_breakdown": inbox_breakdown,
        "confirmations_pending": confirmations_pending,
    }


def stats_overview(db: Session, period: str = "week") -> dict[str, Any]:
    now = time.time()
    if period == "month":
        start = day_start(now) - 29 * 86_400
    elif period == "quarter":
        start = day_start(now) - 89 * 86_400
    else:
        start = week_start(now)

    tasks = list(db.scalars(select(Task).where(Task.deleted_at.is_(None))))
    done = [task for task in tasks if task.status == "done"]
    done_in_period = [
        task for task in done if task.completed_at and task.completed_at >= start
    ]
    overdue = [
        task
        for task in tasks
        if task.status not in {"done", "cancelled"} and is_overdue(task, now)
    ]
    durations = [
        (task.completed_at - task.created_at) / 86_400
        for task in done_in_period
        if task.completed_at and task.completed_at > task.created_at
    ]
    deliverables = int(db.scalar(select(func.count(Deliverable.id))) or 0)
    open_issues = int(
        db.scalar(select(func.count(Issue.id)).where(Issue.status == "open")) or 0
    )

    trend: list[dict[str, Any]] = []
    for offset in range(13, -1, -1):
        day = day_start(now) - offset * 86_400
        day_end = day + 86_400
        count = sum(
            1
            for task in done
            if task.completed_at and day <= task.completed_at < day_end
        )
        trend.append(
            {
                "date": datetime.fromtimestamp(day).strftime("%m-%d"),
                "completed": count,
            }
        )

    projects = list(db.scalars(select(Project)))
    project_progress = []
    for project in projects:
        project_tasks = [task for task in tasks if task.project_id == project.id]
        if not project_tasks:
            continue
        done_count = sum(1 for task in project_tasks if task.status == "done")
        project_progress.append(
            {
                "project_id": project.id,
                "name": project.name,
                "color": project.color,
                "total": len(project_tasks),
                "done": done_count,
                "progress": round(done_count / len(project_tasks) * 100),
            }
        )

    members = list(db.scalars(select(Member)))
    member_load = []
    for member in members:
        member_tasks = [
            task
            for task in tasks
            if task.assignee_id == member.id and task.status not in {"done", "cancelled"}
        ]
        member_load.append(
            {
                "member_id": member.id,
                "name": member.name,
                "color": member.avatar_color,
                "active": len(member_tasks),
                "overdue": sum(1 for task in member_tasks if is_overdue(task, now)),
            }
        )

    total_active = len([task for task in tasks if task.status not in {"done", "cancelled"}])
    return {
        "period": period,
        "kpi": {
            "completion_rate": round(len(done_in_period) / max(1, len(done_in_period) + total_active) * 100),
            "avg_duration_days": round(sum(durations) / len(durations), 1) if durations else 0,
            "overdue_rate": round(len(overdue) / max(1, total_active + len(overdue)) * 100),
            "deliverables": deliverables,
            "open_issues": open_issues,
            "completed": len(done_in_period),
        },
        "trend": trend,
        "status": _task_counts(tasks),
        "projects": project_progress,
        "members": member_load,
    }


def search(db: Session, query: str, limit: int = 20) -> dict[str, Any]:
    like = f"%{query}%"
    tasks = list(
        db.scalars(
            select(Task)
            .where(Task.deleted_at.is_(None), Task.title.like(like))
            .limit(limit)
        )
    )
    projects = list(db.scalars(select(Project).where(Project.name.like(like)).limit(10)))
    deliverables = list(
        db.scalars(
            select(Deliverable).where(Deliverable.title.like(like)).limit(limit)
        )
    )
    return {
        "tasks": serialize_tasks(db, tasks),
        "projects": [
            {"id": project.id, "name": project.name, "color": project.color}
            for project in projects
        ],
        "deliverables": [
            {
                "id": item.id,
                "title": item.title,
                "type": item.type,
                "path_or_url": item.path_or_url,
                "task_id": item.task_id,
            }
            for item in deliverables
        ],
    }
