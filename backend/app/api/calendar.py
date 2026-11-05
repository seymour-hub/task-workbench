from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import CalendarEvent, Task
from ..schemas import CalendarEventCreate, CalendarEventUpdate

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/events")
def list_events(
    start: float | None = Query(default=None),
    end: float | None = Query(default=None),
    db: Session = Depends(get_db),
):
    statement = select(CalendarEvent).order_by(CalendarEvent.start_at.asc())
    if start is not None:
        statement = statement.where(CalendarEvent.start_at >= start)
    if end is not None:
        statement = statement.where(CalendarEvent.start_at < end)
    events = list(db.scalars(statement))

    task_statement = select(Task).where(
        Task.deleted_at.is_(None),
        Task.due_at.is_not(None),
        Task.status.not_in(["done", "cancelled"]),
    )
    if start is not None:
        task_statement = task_statement.where(Task.due_at >= start)
    if end is not None:
        task_statement = task_statement.where(Task.due_at < end)
    tasks = list(db.scalars(task_statement))

    items = [
        {
            "id": f"event-{event.id}",
            "event_id": event.id,
            "title": event.title,
            "description": event.description,
            "start_at": event.start_at,
            "end_at": event.end_at,
            "all_day": event.all_day,
            "location": event.location,
            "color": event.color,
            "task_id": event.task_id,
            "source": "manual",
            "editable": True,
        }
        for event in events
    ]
    items.extend(
        {
            "id": f"task-{task.id}",
            "event_id": None,
            "title": task.title,
            "description": task.description,
            "start_at": task.due_at,
            "end_at": None,
            "all_day": False,
            "location": None,
            "color": "#EF4444",
            "task_id": task.id,
            "source": "task",
            "editable": False,
        }
        for task in tasks
    )
    items.sort(key=lambda item: item["start_at"] or 0)
    return {"items": items}


@router.post("/events", status_code=201)
def create_event(payload: CalendarEventCreate, db: Session = Depends(get_db)):
    event = CalendarEvent(
        title=payload.title.strip(),
        description=payload.description,
        start_at=payload.start_at,
        end_at=payload.end_at,
        all_day=payload.all_day,
        location=payload.location,
        color=payload.color,
        task_id=payload.task_id,
        source="manual",
    )
    db.add(event)
    db.commit()
    return {"id": event.id, "title": event.title, "start_at": event.start_at}


@router.patch("/events/{event_id}")
def update_event(event_id: int, payload: CalendarEventUpdate, db: Session = Depends(get_db)):
    event = db.get(CalendarEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="日程不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(event, key, value)
    event.updated_at = time.time()
    db.commit()
    return {"id": event.id, "title": event.title, "start_at": event.start_at}


@router.delete("/events/{event_id}")
def delete_event(event_id: int, db: Session = Depends(get_db)):
    event = db.get(CalendarEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="日程不存在")
    db.delete(event)
    db.commit()
    return {"ok": True}
