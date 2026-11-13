from __future__ import annotations

from app.schemas import TaskCreate
from app.services.task_codes import next_task_code
from app.services.task_restart import find_restart_code, restart_task
from app.services.task_service import create_task


def test_find_restart_code():
    assert find_restart_code("T0031任务重新启动") == "T0031"
    assert find_restart_code("重启 T0031，按最新订单刷新") == "T0031"
    assert find_restart_code("T0031 继续") == "T0031"
    assert find_restart_code("T0031 这份报告已完成") is None


def test_restart_reopens_same_task(db):
    task = create_task(
        db,
        TaskCreate(title="麒麟OS合作签署报价与26年价格分析", status="done", progress=100),
    )
    db.commit()
    code = task.code

    restart_task(db, task, note="用户要求重启")
    db.commit()

    assert task.code == code
    assert task.status == "in_progress"
    assert task.ended_at is None
    assert next_task_code(db) == "T0002"
