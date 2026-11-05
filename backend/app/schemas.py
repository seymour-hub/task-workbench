from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

TaskStatus = Literal["todo", "in_progress", "done", "cancelled"]
TaskPriority = Literal["urgent", "high", "medium", "low"]
IssueSeverity = Literal["blocker", "high", "medium", "low"]
IssueStatus = Literal["open", "resolved", "wontfix"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MemberOut(ORMModel):
    id: int
    name: str
    avatar_color: str
    role: str
    is_me: bool


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    color: str = "#5B7CFA"


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None
    status: str | None = None


class ProjectOut(ORMModel):
    id: int
    name: str
    description: str | None
    color: str
    status: str
    created_at: float
    updated_at: float
    task_count: int = 0
    done_count: int = 0
    overdue_count: int = 0
    progress: int = 0


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    project_id: int | None = None
    assignee_id: int | None = None
    status: TaskStatus = "todo"
    priority: TaskPriority = "medium"
    due_at: float | None = None
    start_at: float | None = None
    started_at: float | None = None
    ended_at: float | None = None
    progress: int = 0
    category: str | None = None
    subcategory: str | None = None
    work_types: list[str] | None = None
    source_type: str = "manual"


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    project_id: int | None = None
    assignee_id: int | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_at: float | None = None
    start_at: float | None = None
    started_at: float | None = None
    ended_at: float | None = None
    progress: int | None = None
    category: str | None = None
    subcategory: str | None = None
    work_types: list[str] | None = None
    sort_order: float | None = None


class TaskStatusUpdate(BaseModel):
    status: TaskStatus
    sort_order: float | None = None


class CommentCreate(BaseModel):
    note: str = Field(min_length=1)


class MilestoneCreate(BaseModel):
    note: str = Field(min_length=1, max_length=500)
    occurred_at: float | None = None


class BoardMove(BaseModel):
    task_id: int
    status: TaskStatus
    sort_order: float | None = None


class IssueCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    detail: str | None = None
    severity: IssueSeverity = "medium"
    source_message_id: int | None = None


class IssueUpdate(BaseModel):
    title: str | None = None
    detail: str | None = None
    severity: IssueSeverity | None = None
    status: IssueStatus | None = None
    resolution: str | None = None


class DeliverableCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    type: Literal["file", "doc", "link", "image", "video", "other"] = "file"
    path_or_url: str = Field(min_length=1)
    source_message_id: int | None = None


class CalendarEventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    start_at: float
    end_at: float | None = None
    all_day: bool = False
    location: str | None = None
    color: str = "#5B7CFA"
    task_id: int | None = None


class CalendarEventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    start_at: float | None = None
    end_at: float | None = None
    all_day: bool | None = None
    location: str | None = None
    color: str | None = None


class InboxAccept(BaseModel):
    title: str | None = None
    description: str | None = None
    project_id: int | None = None
    task_id: int | None = None
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    due_at: float | None = None


class InboxReject(BaseModel):
    reason: str | None = None


class FileRootCreate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    path: str = Field(min_length=1)
    enabled: bool = True
    depth: int = 4
    include_ext: list[str] | None = None
    exclude_globs: list[str] | None = None
    auto_attach: bool = True
    scan_interval_min: int = 30


class FileRootUpdate(BaseModel):
    label: str | None = None
    enabled: bool | None = None
    depth: int | None = None
    include_ext: list[str] | None = None
    exclude_globs: list[str] | None = None
    auto_attach: bool | None = None
    scan_interval_min: int | None = None


class FileAttach(BaseModel):
    task_id: int


class NotifyTest(BaseModel):
    text: str | None = None


# ---------- AI extraction schema ----------

class AITask(BaseModel):
    title: str
    description: str | None = None
    status: Literal["todo", "in_progress", "done"] = "todo"
    priority: Literal["urgent", "high", "medium", "low"] = "medium"
    due_at: str | None = None
    project_hint: str | None = None
    confidence: float = 0.5
    evidence_message_ids: list[int] = []

    @field_validator("confidence")
    @classmethod
    def _clamp(cls, value: float) -> float:
        return max(0.0, min(1.0, float(value)))


class AIIssue(BaseModel):
    title: str
    detail: str | None = None
    severity: Literal["blocker", "high", "medium", "low"] = "medium"
    status: Literal["open", "resolved"] = "open"
    evidence_message_ids: list[int] = []


class AIDeliverable(BaseModel):
    title: str
    type: Literal["file", "doc", "link", "image", "video", "other"] = "file"
    path_or_url: str
    group: str | None = None
    version: str | None = None
    is_final: bool | None = None
    evidence_message_ids: list[int] = []


class AIDecision(BaseModel):
    summary: str
    evidence_message_ids: list[int] = []


class AIMilestone(BaseModel):
    summary: str
    evidence_message_ids: list[int] = []


class ExtractionResult(BaseModel):
    tasks: list[AITask] = []
    issues: list[AIIssue] = []
    deliverables: list[AIDeliverable] = []
    decisions: list[AIDecision] = []
    next_steps: list[AIDecision] = []
    milestones: list[AIMilestone] = []
