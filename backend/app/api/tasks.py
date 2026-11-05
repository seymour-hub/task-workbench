from __future__ import annotations

import os
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Deliverable, Issue, Task, TaskEvent
from ..schemas import (
    BoardMove,
    CommentCreate,
    DeliverableCreate,
    IssueCreate,
    IssueUpdate,
    MilestoneCreate,
    TaskCreate,
    TaskStatusUpdate,
    TaskUpdate,
)
from ..services import task_service

router = APIRouter(tags=["tasks"])
board_router = APIRouter(prefix="/board", tags=["board"])


def _get_task(db: Session, task_id: int) -> Task:
    task = db.get(Task, task_id)
    if not task or task.deleted_at is not None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.get("/tasks")
def list_tasks(
    status: str | None = Query(default=None),
    project_id: int | None = Query(default=None),
    priority: str | None = Query(default=None),
    category: str | None = Query(default=None),
    work_type: str | None = Query(default=None),
    q: str | None = Query(default=None),
    due: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    tasks = task_service.list_tasks(
        db,
        status=status,
        project_id=project_id,
        priority=priority,
        category=category,
        work_type=work_type,
        q=q,
        due=due,
        limit=limit,
        include_cancelled=status == "cancelled",
    )
    return {"items": task_service.serialize_tasks(db, tasks), "total": len(tasks)}


@router.post("/tasks", status_code=201)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    task = task_service.create_task(db, payload)
    db.commit()
    return task_service.serialize_task(db, task)


@router.post("/tasks/merge")
def merge_tasks(payload: dict, db: Session = Depends(get_db)):
    target_id = int(payload.get("target_id") or 0)
    source_ids = [int(value) for value in payload.get("source_ids") or []]
    if not target_id or not source_ids:
        raise HTTPException(status_code=400, detail="需要 target_id 和 source_ids")
    try:
        result = task_service.merge_tasks(
            db, target_id, source_ids, note=payload.get("note")
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return result


@router.get("/tasks/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = _get_task(db, task_id)
    return task_service.get_detail(db, task)


@router.patch("/tasks/{task_id}")
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)):
    task = _get_task(db, task_id)
    task_service.update_task(db, task, payload)
    db.commit()
    return task_service.serialize_task(db, task)


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = _get_task(db, task_id)
    task.deleted_at = time.time()
    db.add(
        TaskEvent(task_id=task.id, type="deleted", actor="me", note="任务已删除")
    )
    db.commit()
    return {"ok": True}


@router.post("/tasks/{task_id}/status")
def change_status(task_id: int, payload: TaskStatusUpdate, db: Session = Depends(get_db)):
    task = _get_task(db, task_id)
    task_service.change_status(db, task, payload.status, payload.sort_order)
    db.commit()
    return task_service.serialize_task(db, task)


@router.post("/tasks/{task_id}/complete")
def complete_task(task_id: int, db: Session = Depends(get_db)):
    task = _get_task(db, task_id)
    task_service.change_status(db, task, "done")
    db.commit()
    return task_service.serialize_task(db, task)


@router.post("/tasks/{task_id}/milestones", status_code=201)
def create_milestone(
    task_id: int, payload: MilestoneCreate, db: Session = Depends(get_db)
):
    task = _get_task(db, task_id)
    event = TaskEvent(
        task_id=task.id,
        type="milestone",
        note=payload.note.strip(),
        actor="me",
        created_at=payload.occurred_at or time.time(),
    )
    db.add(event)
    db.commit()
    return {
        "id": event.id,
        "type": event.type,
        "note": event.note,
        "created_at": event.created_at,
    }


@router.post("/tasks/{task_id}/comments", status_code=201)
def add_comment(task_id: int, payload: CommentCreate, db: Session = Depends(get_db)):
    task = _get_task(db, task_id)
    event = task_service.add_comment(db, task, payload.note)
    db.commit()
    return {
        "id": event.id,
        "type": event.type,
        "note": event.note,
        "actor": event.actor,
        "created_at": event.created_at,
    }


@router.get("/tasks/{task_id}/issues")
def list_issues(task_id: int, db: Session = Depends(get_db)):
    _get_task(db, task_id)
    issues = [
        {
            "id": issue.id,
            "title": issue.title,
            "detail": issue.detail,
            "severity": issue.severity,
            "status": issue.status,
            "resolution": issue.resolution,
            "created_at": issue.created_at,
            "resolved_at": issue.resolved_at,
        }
        for issue in db.query(Issue)
        .filter(Issue.task_id == task_id)
        .order_by(Issue.created_at.desc())
        .all()
    ]
    return {"items": issues}


@router.post("/tasks/{task_id}/issues", status_code=201)
def create_issue(task_id: int, payload: IssueCreate, db: Session = Depends(get_db)):
    task = _get_task(db, task_id)
    issue = Issue(
        task_id=task.id,
        title=payload.title.strip(),
        detail=payload.detail,
        severity=payload.severity,
        source_message_id=payload.source_message_id,
    )
    db.add(issue)
    db.flush()
    db.add(
        TaskEvent(
            task_id=task.id,
            type="issue_added",
            note=issue.title,
            actor="me",
            message_id=payload.source_message_id,
        )
    )
    db.commit()
    return {"id": issue.id, "title": issue.title, "status": issue.status}


@router.patch("/issues/{issue_id}")
def update_issue(issue_id: int, payload: IssueUpdate, db: Session = Depends(get_db)):
    issue = db.get(Issue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="问题不存在")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(issue, key, value)
    if payload.status == "resolved" and issue.resolved_at is None:
        issue.resolved_at = time.time()
    if payload.status == "resolved":
        db.add(
            TaskEvent(
                task_id=issue.task_id,
                type="issue_resolved",
                note=issue.resolution or issue.title,
                actor="me",
            )
        )
    db.commit()
    return {
        "id": issue.id,
        "status": issue.status,
        "resolution": issue.resolution,
        "resolved_at": issue.resolved_at,
    }


@router.get("/tasks/{task_id}/deliverables")
def list_deliverables(task_id: int, db: Session = Depends(get_db)):
    _get_task(db, task_id)
    items = (
        db.query(Deliverable)
        .filter(Deliverable.task_id == task_id)
        .order_by(Deliverable.created_at.desc())
        .all()
    )
    return {
        "items": [
            {
                "id": item.id,
                "title": item.title,
                "type": item.type,
                "path_or_url": item.path_or_url,
                "file_size": item.file_size,
                "exists_flag": item.exists_flag,
                "attach_mode": item.attach_mode,
                "group_key": item.group_key,
                "logical_name": item.logical_name,
                "version_label": item.version_label,
                "version_at": item.version_at,
                "is_final": item.is_final,
                "is_intermediate": item.is_intermediate,
                "created_at": item.created_at,
            }
            for item in items
        ]
    }


@router.post("/tasks/{task_id}/deliverables", status_code=201)
def create_deliverable(
    task_id: int, payload: DeliverableCreate, db: Session = Depends(get_db)
):
    from ..services.deliverable_rules import (
        classify_deliverable,
        file_timestamp,
        is_final_by_name,
        logical_group,
        version_label,
    )

    task = _get_task(db, task_id)
    classification = classify_deliverable(payload.path_or_url, payload.title)
    if not classification["ok"]:
        raise HTTPException(
            status_code=400,
            detail=f"该文件不属于交付物：{classification['reason']}",
        )
    exists = os.path.exists(payload.path_or_url)
    group_key, logical_name = logical_group(payload.title, payload.path_or_url)
    version_at = file_timestamp(payload.path_or_url)
    intermediate = bool(classification["is_intermediate"])
    item = Deliverable(
        task_id=task.id,
        title=payload.title.strip(),
        type=payload.type,
        path_or_url=payload.path_or_url,
        file_size=os.path.getsize(payload.path_or_url) if exists and os.path.isfile(payload.path_or_url) else None,
        exists_flag=exists,
        attach_mode="manual",
        source_message_id=payload.source_message_id,
        group_key=group_key,
        logical_name=logical_name,
        version_label=version_label(payload.path_or_url, payload.title, version_at),
        version_at=version_at,
        is_final=not intermediate and is_final_by_name(payload.title, payload.path_or_url),
        is_intermediate=intermediate,
    )
    db.add(item)
    db.flush()
    db.add(
        TaskEvent(
            task_id=task.id,
            type="deliverable_added",
            note=item.title,
            actor="me",
            message_id=payload.source_message_id,
        )
    )
    from ..services.deliverable_service import recompute_finals

    recompute_finals(db, task.id)
    db.commit()
    return {
        "id": item.id,
        "title": item.title,
        "path_or_url": item.path_or_url,
        "is_final": item.is_final,
    }


@router.patch("/deliverables/{deliverable_id}")
def update_deliverable(
    deliverable_id: int, payload: dict, db: Session = Depends(get_db)
):
    item = db.get(Deliverable, deliverable_id)
    if not item:
        raise HTTPException(status_code=404, detail="交付物不存在")
    if "title" in payload and payload["title"]:
        item.title = str(payload["title"]).strip()[:300]
    if "is_intermediate" in payload:
        item.is_intermediate = bool(payload["is_intermediate"])
        if item.is_intermediate:
            item.is_final = False
    if "is_final" in payload:
        item.is_final = bool(payload["is_final"])
        if item.is_final:
            item.is_intermediate = False
            extension = os.path.splitext(item.path_or_url)[1].lower()
            others = db.scalars(
                select(Deliverable).where(
                    Deliverable.task_id == item.task_id,
                    Deliverable.group_key == item.group_key,
                    Deliverable.id != item.id,
                )
            )
            for other in others:
                if os.path.splitext(other.path_or_url)[1].lower() == extension:
                    other.is_final = False
    db.commit()
    return {
        "id": item.id,
        "title": item.title,
        "is_final": item.is_final,
        "is_intermediate": item.is_intermediate,
    }


@router.delete("/issues/{issue_id}")
def delete_issue(issue_id: int, db: Session = Depends(get_db)):
    issue = db.get(Issue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="问题不存在")
    task_id = issue.task_id
    title = issue.title
    db.delete(issue)
    db.add(
        TaskEvent(
            task_id=task_id, type="issue_removed", note=title[:200], actor="me"
        )
    )
    db.commit()
    return {"ok": True}


@router.delete("/deliverables/{deliverable_id}")
def delete_deliverable(deliverable_id: int, db: Session = Depends(get_db)):
    item = db.get(Deliverable, deliverable_id)
    if not item:
        raise HTTPException(status_code=404, detail="交付物不存在")
    task_id = item.task_id
    title = item.title
    db.delete(item)
    db.add(
        TaskEvent(
            task_id=task_id,
            type="deliverable_removed",
            note=title[:200],
            actor="me",
        )
    )
    db.flush()
    from ..services.deliverable_service import recompute_finals

    recompute_finals(db, task_id)
    db.commit()
    return {"ok": True, "note": "仅从任务移除，磁盘文件未删除"}


@router.delete("/tasks/{task_id}/milestones/{event_id}")
def delete_milestone(task_id: int, event_id: int, db: Session = Depends(get_db)):
    event = db.get(TaskEvent, event_id)
    if (
        not event
        or event.task_id != task_id
        or event.type not in {"milestone", "milestone_start", "milestone_end"}
    ):
        raise HTTPException(status_code=404, detail="里程碑不存在")
    db.delete(event)
    db.commit()
    return {"ok": True}


@router.delete("/tasks/{task_id}/comments/{event_id}")
def delete_comment(task_id: int, event_id: int, db: Session = Depends(get_db)):
    event = db.get(TaskEvent, event_id)
    if not event or event.task_id != task_id or event.type != "comment":
        raise HTTPException(status_code=404, detail="评论不存在")
    db.delete(event)
    db.commit()
    return {"ok": True}


@router.delete("/tasks/{task_id}/events/{event_id}")
def delete_event(task_id: int, event_id: int, db: Session = Depends(get_db)):
    """Remove a comment or an AI note from the timeline (audit events stay)."""
    event = db.get(TaskEvent, event_id)
    if (
        not event
        or event.task_id != task_id
        or event.type not in {"comment", "ai_note"}
    ):
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(event)
    db.commit()
    return {"ok": True}


@board_router.get("")
def get_board(project_id: int | None = Query(default=None), db: Session = Depends(get_db)):
    return task_service.board_data(db, project_id=project_id)


@board_router.post("/move")
def move_task(payload: BoardMove, db: Session = Depends(get_db)):
    task = _get_task(db, payload.task_id)
    if payload.status == "cancelled":
        raise HTTPException(status_code=400, detail="看板不支持直接取消任务")
    task_service.change_status(db, task, payload.status, payload.sort_order)
    db.commit()
    return task_service.serialize_task(db, task)
