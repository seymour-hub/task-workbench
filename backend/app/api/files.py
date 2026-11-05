from __future__ import annotations

import mimetypes
import os
import time

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db, get_int_setting
from ..models import Deliverable, DeliverableRoot, FileIndex, Project, Task
from ..schemas import FileAttach, FileRootCreate, FileRootUpdate
from ..services import file_service

router = APIRouter(prefix="/files", tags=["files"])


def _root_dict(root: DeliverableRoot) -> dict:
    return {
        "id": root.id,
        "label": root.label,
        "path": root.path,
        "enabled": root.enabled,
        "depth": root.depth,
        "include_ext": root.include_ext,
        "exclude_globs": root.exclude_globs,
        "auto_attach": root.auto_attach,
        "scan_interval_min": root.scan_interval_min,
        "last_scan_at": root.last_scan_at,
        "file_count": root.file_count,
        "exists": os.path.isdir(root.path),
    }


@router.get("/roots")
def list_roots(db: Session = Depends(get_db)):
    roots = list(db.scalars(select(DeliverableRoot).order_by(DeliverableRoot.id)))
    return {"items": [_root_dict(root) for root in roots]}


@router.post("/roots", status_code=201)
def create_root(payload: FileRootCreate, db: Session = Depends(get_db)):
    existing = db.scalar(select(DeliverableRoot).where(DeliverableRoot.path == payload.path))
    if existing:
        raise HTTPException(status_code=409, detail="该路径已存在")
    try:
        root = file_service.create_root(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return _root_dict(root)


@router.patch("/roots/{root_id}")
def update_root(root_id: int, payload: FileRootUpdate, db: Session = Depends(get_db)):
    root = db.get(DeliverableRoot, root_id)
    if not root:
        raise HTTPException(status_code=404, detail="路径根不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(root, key, value)
    db.commit()
    return _root_dict(root)


@router.delete("/roots/{root_id}")
def delete_root(root_id: int, db: Session = Depends(get_db)):
    root = db.get(DeliverableRoot, root_id)
    if not root:
        raise HTTPException(status_code=404, detail="路径根不存在")
    file_ids = [
        row.id for row in db.scalars(select(FileIndex).where(FileIndex.root_id == root_id))
    ]
    if file_ids:
        db.query(Deliverable).filter(Deliverable.file_id.in_(file_ids)).update(
            {"file_id": None}, synchronize_session=False
        )
        db.query(FileIndex).filter(FileIndex.root_id == root_id).delete(
            synchronize_session=False
        )
    db.delete(root)
    db.commit()
    return {"ok": True}


@router.post("/roots/{root_id}/scan")
def scan_root(root_id: int, db: Session = Depends(get_db)):
    root = db.get(DeliverableRoot, root_id)
    if not root:
        raise HTTPException(status_code=404, detail="路径根不存在")
    max_files = get_int_setting(db, "files.max_files_per_root", 20_000)
    result = file_service.scan_root(db, root, max_files=max_files)
    db.commit()
    return result


@router.post("/scan")
def scan_all(db: Session = Depends(get_db)):
    max_files = get_int_setting(db, "files.max_files_per_root", 20_000)
    results = file_service.scan_all(db, max_files=max_files)
    db.commit()
    return {"items": results}


@router.get("/deliverables")
def list_deliverables(
    q: str | None = Query(default=None),
    task_id: int | None = Query(default=None),
    include_intermediate: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    statement = select(Deliverable).order_by(
        Deliverable.is_final.desc(), Deliverable.created_at.desc()
    ).limit(limit)
    if not include_intermediate:
        statement = statement.where(Deliverable.is_intermediate.is_(False))
    if task_id:
        statement = statement.where(Deliverable.task_id == task_id)
    if q:
        statement = statement.where(Deliverable.title.like(f"%{q}%"))
    items = list(db.scalars(statement))
    task_ids = {item.task_id for item in items if item.task_id}
    task_map = {
        task.id: task
        for task in db.scalars(select(Task).where(Task.id.in_(task_ids)))
    } if task_ids else {}
    project_ids = {task.project_id for task in task_map.values() if task.project_id}
    project_map = {
        project.id: project
        for project in db.scalars(select(Project).where(Project.id.in_(project_ids)))
    } if project_ids else {}

    def sort_key(item: Deliverable):
        task = task_map.get(item.task_id) if item.task_id else None
        return (
            (task.ended_at or 0) if task else 0,
            (task.started_at or 0) if task else 0,
            int(item.is_final),
            item.version_at or item.created_at,
        )

    items.sort(key=sort_key, reverse=True)
    return {
        "items": [
            {
                "id": item.id,
                "task_id": item.task_id,
                "task_title": task_map[item.task_id].title if item.task_id in task_map else None,
                "task_status": task_map[item.task_id].status if item.task_id in task_map else None,
                "task_started_at": (
                    task_map[item.task_id].started_at
                    if item.task_id in task_map
                    else None
                ),
                "task_ended_at": (
                    task_map[item.task_id].ended_at
                    if item.task_id in task_map
                    else None
                ),
                "project_color": (
                    project_map[task_map[item.task_id].project_id].color
                    if item.task_id in task_map
                    and task_map[item.task_id].project_id in project_map
                    else None
                ),
                "project_name": (
                    project_map[task_map[item.task_id].project_id].name
                    if item.task_id in task_map
                    and task_map[item.task_id].project_id in project_map
                    else None
                ),
                "title": item.title,
                "type": item.type,
                "path_or_url": item.path_or_url,
                "file_size": item.file_size,
                "exists_flag": item.exists_flag and os.path.exists(item.path_or_url),
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


@router.get("")
def list_files(
    root_id: int | None = Query(default=None),
    q: str | None = Query(default=None),
    unlinked: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    filters = [FileIndex.ignored.is_(False)]
    if root_id:
        filters.append(FileIndex.root_id == root_id)
    if q:
        filters.append(FileIndex.name.like(f"%{q}%"))
    if unlinked:
        linked_ids = select(Deliverable.file_id).where(Deliverable.file_id.is_not(None))
        filters.append(~FileIndex.id.in_(linked_ids))

    total = db.scalar(select(func.count(FileIndex.id)).where(*filters)) or 0
    rows = list(
        db.scalars(
            select(FileIndex)
            .where(*filters)
            .order_by(FileIndex.mtime.desc())
            .limit(limit)
        )
    )
    linked = dict(
        db.execute(
            select(Deliverable.file_id, Deliverable.task_id)
            .where(Deliverable.file_id.in_([row.id for row in rows]))
        ).all()
    ) if rows else {}
    return {
        "items": [
            {**file_service.file_to_dict(row), "task_id": linked.get(row.id)}
            for row in rows
        ],
        "total": total,
    }


@router.post("/{file_id}/attach")
def attach(file_id: int, payload: FileAttach, db: Session = Depends(get_db)):
    row = db.get(FileIndex, file_id)
    if not row:
        raise HTTPException(status_code=404, detail="文件不存在")
    try:
        item = file_service.attach_file(db, row, payload.task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return {"id": item.id, "task_id": item.task_id, "title": item.title}


@router.delete("/{file_id}/attach")
def detach(file_id: int, db: Session = Depends(get_db)):
    items = list(db.scalars(select(Deliverable).where(Deliverable.file_id == file_id)))
    for item in items:
        db.delete(item)
    db.commit()
    return {"ok": True, "removed": len(items)}


@router.post("/{file_id}/ignore")
def ignore(file_id: int, db: Session = Depends(get_db)):
    row = db.get(FileIndex, file_id)
    if not row:
        raise HTTPException(status_code=404, detail="文件不存在")
    row.ignored = True
    db.commit()
    return {"ok": True}


@router.get("/serve")
def serve_deliverable(
    path: str = Query(...),
    download: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    target_path = os.path.normcase(os.path.normpath(path))
    allowed = False
    for root in db.scalars(
        select(DeliverableRoot).where(DeliverableRoot.enabled.is_(True))
    ):
        root_norm = os.path.normcase(os.path.normpath(root.path))
        try:
            if os.path.commonpath([target_path, root_norm]) == root_norm:
                allowed = True
                break
        except ValueError:
            continue
    if not allowed:
        raise HTTPException(status_code=403, detail="路径不在已配置的根目录内")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="文件不存在")
    media_type, _ = mimetypes.guess_type(path)
    disposition = "inline"
    if download:
        filename = os.path.basename(path)
        disposition = f"attachment; filename*=UTF-8''{quote(filename)}"
    return FileResponse(
        path,
        media_type=media_type or "application/octet-stream",
        headers={"Content-Disposition": disposition},
    )


@router.post("/open")
def open_deliverable(payload: dict, db: Session = Depends(get_db)):
    path = str(payload.get("path") or "")
    if not path:
        raise HTTPException(status_code=400, detail="缺少 path")
    if path.startswith(("http://", "https://")):
        return file_service.open_file(path)
    target = os.path.normcase(os.path.normpath(path))
    allowed = False
    for root in db.scalars(
        select(DeliverableRoot).where(DeliverableRoot.enabled.is_(True))
    ):
        root_norm = os.path.normcase(os.path.normpath(root.path))
        try:
            if os.path.commonpath([target, root_norm]) == root_norm:
                allowed = True
                break
        except ValueError:
            continue
    if not allowed:
        raise HTTPException(status_code=403, detail="路径不在已配置的根目录内")
    try:
        return file_service.open_file(path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/reveal")
def reveal(payload: dict, db: Session = Depends(get_db)):
    path = str(payload.get("path") or "")
    if not path:
        raise HTTPException(status_code=400, detail="缺少 path")
    roots = [
        DeliverableRoot
        for DeliverableRoot in db.scalars(
            select(DeliverableRoot).where(DeliverableRoot.enabled.is_(True))
        )
    ]
    target = os.path.normcase(os.path.normpath(path))
    allowed = False
    for root in roots:
        root_norm = os.path.normcase(os.path.normpath(root.path))
        try:
            if os.path.commonpath([target, root_norm]) == root_norm:
                allowed = True
                break
        except ValueError:
            continue
    if not allowed:
        raise HTTPException(status_code=403, detail="路径不在已配置的根目录内")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="文件不存在")
    file_service.reveal(path)
    return {"ok": True}
