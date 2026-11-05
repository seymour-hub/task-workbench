from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Member, Task
from ..schemas import MemberOut
from ..services.task_service import is_overdue

router = APIRouter(prefix="/team", tags=["team"])


@router.get("/members")
def list_members(db: Session = Depends(get_db)):
    members = list(db.scalars(select(Member).order_by(Member.id)))
    tasks = list(db.scalars(select(Task).where(Task.deleted_at.is_(None))))
    items = []
    for member in members:
        owned = [task for task in tasks if task.assignee_id == member.id]
        items.append(
            {
                "id": member.id,
                "name": member.name,
                "avatar_color": member.avatar_color,
                "role": member.role,
                "is_me": member.is_me,
                "active": sum(
                    1 for task in owned if task.status not in {"done", "cancelled"}
                ),
                "done": sum(1 for task in owned if task.status == "done"),
                "overdue": sum(1 for task in owned if is_overdue(task)),
            }
        )
    return {"items": items}


@router.post("/members", status_code=201)
def create_member(payload: dict, db: Session = Depends(get_db)):
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="成员名称不能为空")
    member = Member(
        name=name,
        role=str(payload.get("role") or "成员"),
        avatar_color=str(payload.get("avatar_color") or "#5B7CFA"),
    )
    db.add(member)
    db.commit()
    return MemberOut.model_validate(member).model_dump()


@router.patch("/members/{member_id}")
def update_member(member_id: int, payload: dict, db: Session = Depends(get_db)):
    member = db.get(Member, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    for key in ("name", "role", "avatar_color"):
        if key in payload:
            setattr(member, key, payload[key])
    db.commit()
    return MemberOut.model_validate(member).model_dump()
