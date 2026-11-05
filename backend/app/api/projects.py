from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Deliverable, Issue, Project, Task
from ..schemas import ProjectCreate, ProjectUpdate
from ..services.task_service import is_overdue, serialize_task

router = APIRouter(prefix="/projects", tags=["projects"])


def _project_dict(db: Session, project: Project) -> dict:
    tasks = list(
        db.scalars(
            select(Task).where(
                Task.project_id == project.id, Task.deleted_at.is_(None)
            )
        )
    )
    total = len(tasks)
    done = sum(1 for task in tasks if task.status == "done")
    overdue = sum(1 for task in tasks if is_overdue(task))
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "color": project.color,
        "status": project.status,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "task_count": total,
        "done_count": done,
        "overdue_count": overdue,
        "progress": round(done / total * 100) if total else 0,
    }


@router.get("")
def list_projects(db: Session = Depends(get_db)):
    projects = list(db.scalars(select(Project).order_by(Project.id)))
    return {"items": [_project_dict(db, project) for project in projects]}


@router.post("", status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    existing = db.scalar(select(Project).where(Project.name == payload.name.strip()))
    if existing:
        raise HTTPException(status_code=409, detail="项目名称已存在")
    project = Project(
        name=payload.name.strip(),
        description=payload.description,
        color=payload.color,
    )
    db.add(project)
    db.commit()
    return _project_dict(db, project)


@router.get("/{project_id}")
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    data = _project_dict(db, project)
    tasks = list(
        db.scalars(
            select(Task)
            .where(Task.project_id == project_id, Task.deleted_at.is_(None))
            .order_by(
                case((Task.status == "in_progress", 0), else_=1),
                func.coalesce(
                    Task.ended_at, Task.started_at, Task.created_at
                ).desc(),
                Task.started_at.desc().nullslast(),
                Task.id.desc(),
            )
        )
    )
    task_ids = [task.id for task in tasks]
    issues = list(
        db.scalars(select(Issue).where(Issue.task_id.in_(task_ids))) if task_ids else []
    )
    deliverables = list(
        db.scalars(select(Deliverable).where(Deliverable.task_id.in_(task_ids)))
        if task_ids
        else []
    )
    data["tasks"] = [serialize_task(db, task) for task in tasks]
    data["issues"] = [
        {
            "id": issue.id,
            "title": issue.title,
            "severity": issue.severity,
            "status": issue.status,
            "task_id": issue.task_id,
        }
        for issue in issues
    ]
    data["deliverables"] = [
        {
            "id": item.id,
            "title": item.title,
            "type": item.type,
            "path_or_url": item.path_or_url,
            "task_id": item.task_id,
        }
        for item in deliverables
    ]
    return data


@router.patch("/{project_id}")
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    project.updated_at = time.time()
    db.commit()
    return _project_dict(db, project)


@router.delete("/{project_id}")
def archive_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    project.status = "archived"
    project.updated_at = time.time()
    db.commit()
    return {"ok": True}
