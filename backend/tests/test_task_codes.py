from __future__ import annotations

from app.schemas import TaskCreate
from app.services.task_codes import next_task_code
from app.services.task_service import create_task


def test_codes_are_sequential_not_id_based(db):
    first = create_task(db, TaskCreate(title="第一项工作"))
    db.commit()
    second = create_task(db, TaskCreate(title="第二项工作"))
    db.commit()

    assert first.code == "T0001"
    assert second.code == "T0002"
    assert next_task_code(db) == "T0003"


def test_create_task_makes_output_folder(db, tmp_path):
    from app.models import DeliverableRoot

    (tmp_path / "documents").mkdir()
    db.add(
        DeliverableRoot(
            label="Hermes 输出",
            path=str(tmp_path),
            enabled=True,
            depth=4,
        )
    )
    db.commit()

    task = create_task(db, TaskCreate(title="新建文件夹测试"))
    db.commit()

    folder = tmp_path / "documents" / f"{task.code}-新建文件夹测试"
    assert folder.is_dir()
