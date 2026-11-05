from app.models import Deliverable, Issue, Task, TaskEvent
from app.services.task_service import merge_tasks


def test_merge_moves_details_and_soft_deletes_sources(db):
    target = Task(title="官网改版交付", status="done", project_id=1)
    source = Task(title="修复字幕错位", status="todo", project_id=1)
    db.add_all([target, source])
    db.commit()

    issue = Issue(task_id=source.id, title="字幕错位")
    deliverable = Deliverable(
        task_id=source.id,
        title="视频最终版",
        path_or_url=r"F:\outputs\video.mp4",
        is_final=True,
        version_at=10,
    )
    event = TaskEvent(task_id=source.id, type="comment", note="修正时间轴")
    db.add_all([issue, deliverable, event])
    db.commit()

    result = merge_tasks(db, target.id, [source.id], note="合并过程任务")
    assert result["merged"] == 1
    assert result["moved_issues"] == 1
    assert result["moved_deliverables"] == 1

    db.refresh(source)
    db.refresh(issue)
    db.refresh(deliverable)
    db.refresh(event)
    assert source.deleted_at is not None
    assert issue.task_id == target.id
    assert deliverable.task_id == target.id
    assert event.task_id == target.id


def test_merge_collapses_duplicate_deliverable_paths(db):
    target = Task(title="项目级任务", project_id=1)
    source = Task(title="过程任务", project_id=1)
    db.add_all([target, source])
    db.commit()

    path = r"F:\outputs\same.mp4"
    keeper = Deliverable(
        task_id=target.id,
        title="最终版",
        path_or_url=path,
        is_final=True,
        version_at=20,
    )
    duplicate = Deliverable(
        task_id=source.id,
        title="过程版",
        path_or_url=path,
        is_intermediate=True,
        version_at=10,
    )
    db.add_all([keeper, duplicate])
    db.commit()

    result = merge_tasks(db, target.id, [source.id])
    assert result["removed_duplicates"] == 1
    rows = db.query(Deliverable).filter(Deliverable.task_id == target.id).all()
    assert len(rows) == 1
    assert rows[0].title == "最终版"
