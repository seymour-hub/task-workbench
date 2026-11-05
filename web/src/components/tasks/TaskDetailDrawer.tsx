import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  CalendarRange,
  CheckCircle2,
  CircleDot,
  Clock3,
  ExternalLink,
  FileText,
  Flag,
  FolderOpen,
  MessageSquare,
  Paperclip,
  PlayCircle,
  Plus,
  RotateCcw,
  Sparkles,
  AlertTriangle,
  Trash2,
} from "lucide-react";
import { api } from "../../api/client";
import type { TaskStatus } from "../../api/types";
import FilePreviewModal, {
  type PreviewItem,
} from "../files/FilePreviewModal";
import { groupDeliverables } from "../../lib/deliverables";
import {
  CATEGORIES,
  WORK_TYPES,
  subcategoriesFor,
} from "../../lib/taxonomy";
import {
  cn,
  formatBytes,
  formatDate,
  formatDeadline,
  formatTime,
  PRIORITY,
  toLocalInput,
} from "../../lib/format";
import {
  Avatar,
  Drawer,
  EmptyState,
  PriorityBadge,
  Skeleton,
  StatusBadge,
  Tabs,
} from "../ui/primitives";

const TIMELINE_LABEL: Record<string, string> = {
  created: "创建任务",
  ai_extracted: "AI 抽取",
  accepted: "接受候选",
  status_changed: "状态变更",
  priority_changed: "优先级变更",
  due_changed: "截止时间变更",
  comment: "评论",
  issue_added: "添加问题",
  issue_resolved: "解决问题",
  issue_removed: "删除问题",
  deliverable_added: "添加交付物",
  deliverable_removed: "移除交付物",
  deleted: "删除任务",
  imported: "从飞书复盘导入",
  milestone: "里程碑",
  milestone_start: "任务开始",
  milestone_end: "任务结束",
};

function timelineIcon(type: string) {
  if (type.startsWith("milestone")) return Flag;
  if (type === "accepted" || type === "ai_extracted" || type === "imported") return Sparkles;
  if (type === "status_changed") return CircleDot;
  if (type === "comment") return MessageSquare;
  if (type.includes("issue")) return AlertTriangle;
  if (type.includes("deliverable")) return Paperclip;
  return Clock3;
}

export default function TaskDetailDrawer({
  taskId,
  initialTab,
  onClose,
}: {
  taskId: number | null;
  initialTab?: string;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState(initialTab || "timeline");
  const [title, setTitle] = useState("");
  const [comment, setComment] = useState("");
  const [issueTitle, setIssueTitle] = useState("");
  const [deliverableTitle, setDeliverableTitle] = useState("");
  const [deliverablePath, setDeliverablePath] = useState("");
  const [milestoneNote, setMilestoneNote] = useState("");
  const [milestoneAt, setMilestoneAt] = useState(toLocalInput(Date.now() / 1000));
  const [preview, setPreview] = useState<PreviewItem | null>(null);

  const detail = useQuery({
    queryKey: ["task", taskId],
    queryFn: () => api.task(taskId!),
    enabled: taskId !== null,
  });
  const projects = useQuery({ queryKey: ["projects"], queryFn: api.projects });
  const members = useQuery({ queryKey: ["members"], queryFn: api.members });
  const source = useQuery({
    queryKey: ["source-messages", detail.data?.source_message_ids],
    queryFn: () => api.sourceMessages(detail.data!.source_message_ids),
    enabled: Boolean(detail.data?.source_message_ids?.length),
  });

  useEffect(() => {
    if (detail.data) setTitle(detail.data.title);
  }, [detail.data?.id]);

  useEffect(() => {
    if (taskId !== null) setTab(initialTab || "timeline");
  }, [taskId, initialTab]);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["task", taskId] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    queryClient.invalidateQueries({ queryKey: ["tasks"] });
    queryClient.invalidateQueries({ queryKey: ["board"] });
    queryClient.invalidateQueries({ queryKey: ["projects"] });
    queryClient.invalidateQueries({ queryKey: ["inbox"] });
  };

  const update = useMutation({
    mutationFn: (payload: Record<string, unknown>) => api.updateTask(taskId!, payload),
    onSuccess: () => {
      invalidate();
      toast.success("已保存");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const statusMutation = useMutation({
    mutationFn: (status: TaskStatus) => api.setStatus(taskId!, status),
    onSuccess: () => {
      invalidate();
      toast.success("状态已更新");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const addMilestone = useMutation({
    mutationFn: () =>
      api.createMilestone(taskId!, {
        note: milestoneNote.trim(),
        occurred_at: milestoneAt
          ? new Date(milestoneAt).getTime() / 1000
          : null,
      }),
    onSuccess: () => {
      setMilestoneNote("");
      invalidate();
      toast.success("里程碑已添加");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const commentMutation = useMutation({
    mutationFn: () => api.addComment(taskId!, comment),
    onSuccess: () => {
      setComment("");
      invalidate();
      toast.success("评论已添加");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const issueMutation = useMutation({
    mutationFn: () =>
      api.createIssue(taskId!, { title: issueTitle, severity: "medium" }),
    onSuccess: () => {
      setIssueTitle("");
      invalidate();
      toast.success("问题已添加");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const deleteTask = useMutation({
    mutationFn: () => api.deleteTask(taskId!),
    onSuccess: () => {
      queryClient.invalidateQueries();
      toast.success("任务已删除");
      onClose();
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const deleteIssue = useMutation({
    mutationFn: (issueId: number) => api.deleteIssue(issueId),
    onSuccess: () => {
      invalidate();
      toast.success("问题已删除");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const deleteMilestone = useMutation({
    mutationFn: (eventId: number) => api.deleteMilestone(taskId!, eventId),
    onSuccess: () => {
      invalidate();
      toast.success("里程碑已删除");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const deleteDeliverable = useMutation({
    mutationFn: (deliverableId: number) => api.deleteDeliverable(deliverableId),
    onSuccess: () => {
      invalidate();
      toast.success("已从任务移除，磁盘文件未删除");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const deleteComment = useMutation({
    mutationFn: (eventId: number) => api.deleteComment(taskId!, eventId),
    onSuccess: () => {
      invalidate();
      toast.success("评论已删除");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const deleteNote = useMutation({
    mutationFn: (eventId: number) => api.deleteTaskEvent(taskId!, eventId),
    onSuccess: () => {
      invalidate();
      toast.success("记录已删除");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const resolveIssue = useMutation({
    mutationFn: (issueId: number) =>
      api.updateIssue(issueId, { status: "resolved" }),
    onSuccess: () => {
      invalidate();
      toast.success("问题已解决");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const deliverableMutation = useMutation({
    mutationFn: () =>
      api.createDeliverable(taskId!, {
        title: deliverableTitle,
        path_or_url: deliverablePath,
        type: "file",
      }),
    onSuccess: () => {
      setDeliverableTitle("");
      setDeliverablePath("");
      invalidate();
      toast.success("交付物已添加");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const reveal = useMutation({
    mutationFn: (path: string) => api.revealFile(path),
    onError: (error: Error) => toast.error(error.message),
  });

  const setFinal = useMutation({
    mutationFn: (deliverableId: number) =>
      api.updateDeliverable(deliverableId, { is_final: true }),
    onSuccess: () => {
      invalidate();
      toast.success("已设为最终版");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const deliverableGroups = useMemo(
    () => groupDeliverables(detail.data?.deliverables || []),
    [detail.data?.deliverables],
  );

  const task = detail.data;

  const durationDays =
    detail.data?.started_at && detail.data?.ended_at
      ? Math.max(
          0.1,
          (detail.data.ended_at - detail.data.started_at) / 86_400,
        )
      : null;

  const toggleWorkType = (tag: string) => {
    if (!detail.data) return;
    const current = detail.data.work_types || [];
    const next = current.includes(tag)
      ? current.filter((value) => value !== tag)
      : [...current, tag];
    update.mutate({ work_types: next });
  };

  return (
    <>
      <Drawer
        open={taskId !== null}
        onClose={onClose}
        title="任务详情"
        width="w-[600px]"
      >
      {detail.isLoading || !task ? (
        <div className="space-y-3">
          <Skeleton className="h-6 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : (
        <div className="space-y-5">
          <div>
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              onBlur={() => {
                if (title.trim() && title !== task.title) update.mutate({ title: title.trim() });
              }}
              className="w-full bg-transparent text-[17px] font-semibold leading-6 text-mist-100 outline-none focus:border-b focus:border-brand-500/50"
            />
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <StatusBadge status={task.status} />
              <PriorityBadge priority={task.priority} />
              {task.code ? (
                <span className="pill border border-ink-700 bg-ink-800 text-mist-300">
                  #{task.code}
                </span>
              ) : null}
              {task.project_name ? (
                <span className="pill border border-ink-700 bg-ink-800 text-mist-300">
                  <span
                    className="h-1.5 w-1.5 rounded-full"
                    style={{ background: task.project_color || "#5B7CFA" }}
                  />
                  {task.project_name}
                </span>
              ) : null}
              {task.source_type === "hermes_session" ? (
                <span className="pill border border-brand-500/25 bg-brand-500/10 text-brand-300">
                  <Sparkles size={11} /> 来自 Hermes
                </span>
              ) : null}
              {task.source_type === "feishu_intent" ? (
                <span className="pill border border-brand-500/25 bg-brand-500/10 text-brand-300">
                  <Sparkles size={11} /> 飞书自动创建
                </span>
              ) : null}
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-mist-500">
              <span>
                开始：
                <span className="text-mist-300">
                  {task.started_at ? formatDate(task.started_at, true) : "—"}
                </span>
              </span>
              <span>
                结束：
                <span className="text-mist-300">
                  {task.ended_at ? formatDate(task.ended_at, true) : "—"}
                </span>
              </span>
              {durationDays ? (
                <span className="text-brand-300/80">
                  持续{" "}
                  {durationDays < 1
                    ? `${Math.round(durationDays * 24)} 小时`
                    : `${durationDays.toFixed(1)} 天`}
                </span>
              ) : null}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 rounded-xl border border-ink-700/70 bg-ink-900/40 p-3">
            <label className="text-xs text-mist-500">
              状态
              <select
                value={task.status}
                onChange={(event) => statusMutation.mutate(event.target.value as TaskStatus)}
                className="input mt-1 h-8 py-1"
              >
                <option value="todo">待处理</option>
                <option value="in_progress">进行中</option>
                <option value="done">已完成</option>
                <option value="cancelled">已取消</option>
              </select>
            </label>
            <label className="text-xs text-mist-500">
              优先级
              <select
                value={task.priority}
                onChange={(event) => update.mutate({ priority: event.target.value })}
                className="input mt-1 h-8 py-1"
              >
                {Object.entries(PRIORITY).map(([key, value]) => (
                  <option key={key} value={key}>
                    {value.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs text-mist-500">
              项目
              <select
                value={task.project_id || ""}
                onChange={(event) =>
                  update.mutate({
                    project_id: event.target.value ? Number(event.target.value) : null,
                  })
                }
                className="input mt-1 h-8 py-1"
              >
                <option value="">未归类</option>
                {projects.data?.items.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs text-mist-500">
              业务域
              <select
                value={task.category || ""}
                onChange={(event) =>
                  update.mutate({
                    category: event.target.value || null,
                    subcategory: null,
                  })
                }
                className="input mt-1 h-8 py-1"
              >
                <option value="">未分类</option>
                {CATEGORIES.map((item) => (
                  <option key={item.name} value={item.name}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs text-mist-500">
              二级分类
              <select
                value={task.subcategory || ""}
                onChange={(event) =>
                  update.mutate({ subcategory: event.target.value || null })
                }
                className="input mt-1 h-8 py-1"
                disabled={!task.category}
              >
                <option value="">未分类</option>
                {subcategoriesFor(task.category).map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs text-mist-500">
              负责人
              <select
                value={task.assignee_id || ""}
                onChange={(event) =>
                  update.mutate({
                    assignee_id: event.target.value ? Number(event.target.value) : null,
                  })
                }
                className="input mt-1 h-8 py-1"
              >
                <option value="">未分配</option>
                {members.data?.items.map((member) => (
                  <option key={member.id} value={member.id}>
                    {member.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs text-mist-500">
              开始时间
              <input
                type="datetime-local"
                value={toLocalInput(task.started_at)}
                onChange={(event) =>
                  update.mutate({
                    started_at: event.target.value
                      ? new Date(event.target.value).getTime() / 1000
                      : null,
                  })
                }
                className="input mt-1 h-8 py-1"
              />
            </label>
            <label className="text-xs text-mist-500">
              结束时间
              <input
                type="datetime-local"
                value={toLocalInput(task.ended_at)}
                onChange={(event) =>
                  update.mutate({
                    ended_at: event.target.value
                      ? new Date(event.target.value).getTime() / 1000
                      : null,
                  })
                }
                className="input mt-1 h-8 py-1"
              />
            </label>
            <label className="text-xs text-mist-500">
              截止时间
              <input
                type="datetime-local"
                value={toLocalInput(task.due_at)}
                onChange={(event) =>
                  update.mutate({
                    due_at: event.target.value
                      ? new Date(event.target.value).getTime() / 1000
                      : null,
                  })
                }
                className="input mt-1 h-8 py-1"
              />
            </label>
          </div>

          <div className="rounded-xl border border-ink-700/70 bg-ink-900/40 p-3">
            <p className="text-xs text-mist-500">工作类型</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {WORK_TYPES.map((tag) => {
                const active = (task.work_types || []).includes(tag);
                return (
                  <button
                    key={tag}
                    onClick={() => toggleWorkType(tag)}
                    className={cn(
                      "rounded-md border px-2 py-1 text-[10.5px] transition",
                      active
                        ? "border-brand-500/40 bg-brand-500/15 text-brand-300"
                        : "border-ink-700 bg-ink-850 text-mist-400 hover:text-mist-200",
                    )}
                  >
                    {tag}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              className="btn-ghost"
              onClick={() => statusMutation.mutate("in_progress")}
            >
              <PlayCircle size={15} /> 开始处理
            </button>
            <button
              className="btn-primary"
              onClick={() => statusMutation.mutate("done")}
            >
              <CheckCircle2 size={15} /> 标记完成
            </button>
            <span className="ml-auto self-center text-[11px] text-mist-500">
              截止：{formatDeadline(task.due_at).text}
            </span>
            <button
              className="self-center rounded-lg border border-red-500/25 px-2.5 py-1.5 text-[11px] text-red-300 transition hover:bg-red-500/10 disabled:opacity-50"
              disabled={deleteTask.isPending}
              title="删除任务（软删除，历史保留）"
              onClick={() => {
                if (
                  window.confirm(
                    `删除任务《${task.title}》？\n软删除后不再出现在列表中，过程记录仍在数据库中保留。`,
                  )
                ) {
                  deleteTask.mutate();
                }
              }}
            >
              <Trash2 size={13} className="mr-1 inline" /> 删除任务
            </button>
          </div>

          {task.description ? (
            <p className="whitespace-pre-wrap rounded-xl border border-ink-700/60 bg-ink-900/40 p-3 text-[13px] leading-6 text-mist-300">
              {task.description}
            </p>
          ) : null}

          <div className="flex items-center justify-between">
            <Tabs
              value={tab}
              onChange={setTab}
              tabs={[
                { key: "timeline", label: "时间线", count: task.timeline.length },
                { key: "milestones", label: "里程碑", count: task.milestones.length },
                { key: "issues", label: "问题", count: task.issues.length },
                { key: "deliverables", label: "交付物", count: task.deliverables.length },
                { key: "source", label: "来源会话", count: task.source_message_ids.length },
                { key: "comment", label: "评论" },
              ]}
            />
          </div>

          {tab === "milestones" ? (
            <div className="mb-3 grid grid-cols-[150px_1fr_auto] gap-2">
              <input
                type="datetime-local"
                className="input h-9 py-1"
                value={milestoneAt}
                onChange={(event) => setMilestoneAt(event.target.value)}
              />
              <input
                className="input h-9"
                placeholder="记录一个关键节点..."
                value={milestoneNote}
                onChange={(event) => setMilestoneNote(event.target.value)}
              />
              <button
                className="btn-primary h-9 px-3 text-[11px]"
                disabled={!milestoneNote.trim() || addMilestone.isPending}
                onClick={() => addMilestone.mutate()}
              >
                <Plus size={14} /> 添加
              </button>
            </div>
          ) : null}

          {tab === "milestones" ? (
            <ol className="space-y-0">
              {task.milestones.map((milestone, index) => {
                const isStart = milestone.type === "milestone_start";
                const isEnd = milestone.type === "milestone_end";
                const note = (milestone.note || "")
                  .replace(/^\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2}\s*/, "")
                  .replace(/^\d{1,2}:\d{2}\s*/, "");
                return (
                  <li key={milestone.id} className="flex gap-3">
                    <div className="flex w-[64px] shrink-0 flex-col items-end pt-0.5">
                      <span className="text-[11px] text-mist-400">
                        {formatDate(milestone.created_at)}
                      </span>
                      <span className="text-[10px] text-mist-600">
                        {formatTime(milestone.created_at)}
                      </span>
                    </div>
                    <div className="relative flex w-4 shrink-0 justify-center">
                      <span
                        className={cn(
                          "absolute top-1.5 z-10 h-2.5 w-2.5 rounded-full ring-4 ring-ink-800",
                          isStart
                            ? "bg-emerald-400"
                            : isEnd
                              ? "bg-brand-400"
                              : "bg-amber-400",
                        )}
                      />
                      {index < task.milestones.length - 1 ? (
                        <span className="absolute top-2 h-full w-px bg-ink-600/80" />
                      ) : null}
                    </div>
                    <div className="min-w-0 flex-1 border-b border-ink-700/40 pb-4">
                      <div className="flex items-start gap-2">
                        <div className="min-w-0 flex-1">
                          <p className="text-[12.5px] leading-5 text-mist-200">
                            {note || milestone.note}
                          </p>
                          <p className="mt-0.5 text-[10px] text-mist-500">
                            {TIMELINE_LABEL[milestone.type] || "里程碑"}
                          </p>
                        </div>
                        <button
                          className="rounded p-1 text-mist-500 transition hover:bg-ink-750 hover:text-red-300"
                          title="删除里程碑"
                          onClick={() => {
                            if (window.confirm(`删除里程碑「${note || milestone.note}」？`)) {
                              deleteMilestone.mutate(milestone.id);
                            }
                          }}
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </div>
                  </li>
                );
              })}
              {!task.milestones.length ? (
                <EmptyState
                  title="还没有里程碑"
                  description="导入工作复盘或手动记录关键节点后会出现在这里。"
                />
              ) : null}
            </ol>
          ) : null}

          {tab === "timeline" ? (
            <ol className="space-y-3">
              {task.timeline.map((event) => {
                const Icon = timelineIcon(event.type);
                return (
                  <li key={event.id} className="flex gap-3">
                    <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-ink-750 text-mist-400">
                      <Icon size={14} />
                    </span>
                    <div className="min-w-0 flex-1 border-b border-ink-700/40 pb-3">
                      <div className="flex items-center gap-2 text-[12.5px] text-mist-200">
                        <span className="font-medium">
                          {TIMELINE_LABEL[event.type] || event.type}
                        </span>
                        {event.from_value || event.to_value ? (
                          <span className="text-[11px] text-mist-500">
                            {event.from_value} → {event.to_value}
                          </span>
                        ) : null}
                        <span className="ml-auto text-[11px] text-mist-500">
                          {formatDate(event.created_at, true)}
                        </span>
                        {event.type === "comment" || event.type === "ai_note" ? (
                          <button
                            className="rounded p-0.5 text-mist-500 transition hover:text-red-300"
                            title="删除这条过程记录"
                            onClick={() => {
                              if (window.confirm("删除这条过程记录？")) {
                                deleteNote.mutate(event.id);
                              }
                            }}
                          >
                            <Trash2 size={12} />
                          </button>
                        ) : null}
                      </div>
                      {event.note ? (
                        <p className="mt-1 text-[12px] leading-5 text-mist-400">
                          {event.note}
                        </p>
                      ) : null}
                    </div>
                  </li>
                );
              })}
              {!task.timeline.length ? (
                <EmptyState title="还没有过程记录" description="接受候选任务或修改状态后会自动记录。" />
              ) : null}
            </ol>
          ) : null}

          {tab === "issues" ? (
            <div className="space-y-3">
              <div className="flex gap-2">
                <input
                  className="input"
                  placeholder="描述一个阻塞或风险..."
                  value={issueTitle}
                  onChange={(event) => setIssueTitle(event.target.value)}
                />
                <button
                  className="btn-ghost shrink-0"
                  disabled={!issueTitle.trim() || issueMutation.isPending}
                  onClick={() => issueMutation.mutate()}
                >
                  <Plus size={15} /> 添加
                </button>
              </div>
              {task.issues.map((issue) => (
                <div
                  key={issue.id}
                  className="rounded-xl border border-ink-700/70 bg-ink-900/40 p-3"
                >
                  <div className="flex items-center gap-2">
                    <AlertTriangle
                      size={14}
                      className={issue.status === "resolved" ? "text-emerald-400" : "text-amber-400"}
                    />
                    <span className="text-[13px] font-medium text-mist-100">
                      {issue.title}
                    </span>
                    <span className="pill ml-auto bg-ink-750 text-mist-400">
                      {issue.severity}
                    </span>
                  </div>
                  {issue.detail ? (
                    <p className="mt-1.5 text-[12px] leading-5 text-mist-400">
                      {issue.detail}
                    </p>
                  ) : null}
                  <div className="mt-2 flex items-center gap-2">
                    <span className="text-[11px] text-mist-500">
                      {issue.status === "resolved" ? "已解决" : "未解决"} ·{" "}
                      {formatDate(issue.created_at, true)}
                    </span>
                    <div className="ml-auto flex items-center gap-3">
                      {issue.status !== "resolved" ? (
                        <button
                          className="text-[11px] text-emerald-300 hover:underline"
                          onClick={() => resolveIssue.mutate(issue.id)}
                        >
                          标记已解决
                        </button>
                      ) : null}
                      <button
                        className="rounded p-0.5 text-mist-500 transition hover:text-red-300"
                        title="删除问题"
                        onClick={() => {
                          if (window.confirm(`删除问题「${issue.title}」？`)) {
                            deleteIssue.mutate(issue.id);
                          }
                        }}
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
              {!task.issues.length ? (
                <EmptyState title="没有关联问题" description="抽取到的问题会出现在这里。" />
              ) : null}
            </div>
          ) : null}

          {tab === "deliverables" ? (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2 rounded-xl border border-ink-700/60 bg-ink-900/40 px-3 py-2 text-[11px] text-mist-500">
                <CalendarRange size={13} className="text-brand-300" />
                <span>任务周期：</span>
                <span className="text-mist-300">
                  {task.started_at ? formatDate(task.started_at, true) : "—"} →{" "}
                  {task.ended_at ? formatDate(task.ended_at, true) : "—"}
                </span>
              </div>
              <div className="grid grid-cols-[1fr_1.4fr_auto] gap-2">
                <input
                  className="input"
                  placeholder="名称"
                  value={deliverableTitle}
                  onChange={(event) => setDeliverableTitle(event.target.value)}
                />
                <input
                  className="input"
                  placeholder="文件路径或链接"
                  value={deliverablePath}
                  onChange={(event) => setDeliverablePath(event.target.value)}
                />
                <button
                  className="btn-ghost"
                  disabled={
                    !deliverableTitle.trim() ||
                    !deliverablePath.trim() ||
                    deliverableMutation.isPending
                  }
                  onClick={() => deliverableMutation.mutate()}
                >
                  <Plus size={15} />
                </button>
              </div>
              {deliverableGroups.map((group) => (
                <div
                  key={group.key}
                  className="rounded-xl border border-ink-700/70 bg-ink-900/40 p-3"
                >
                  <div className="flex items-center gap-2 border-b border-ink-700/50 pb-2">
                    <FolderOpen size={14} className="text-brand-300" />
                    <p className="min-w-0 flex-1 truncate text-[12.5px] font-medium text-mist-100">
                      {group.name}
                    </p>
                    <span className="text-[10.5px] text-mist-500">
                      {group.items.length} 个版本
                    </span>
                  </div>
                  <div className="mt-2 space-y-2">
                    {group.items.map((item) => (
                      <div
                        key={item.id}
                        onClick={() =>
                          setPreview({
                            path: item.path_or_url,
                            title: item.title,
                          })
                        }
                        className="flex cursor-pointer items-center gap-2.5 rounded-lg px-1 py-1 transition hover:bg-ink-750/50"
                        title="点击直接打开文件"
                      >
                        <FileText
                          size={14}
                          className={item.is_final ? "text-emerald-400" : "text-mist-500"}
                        />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-[12px] text-mist-200">{item.title}</p>
                          <p className="truncate text-[10.5px] text-mist-500">
                            {item.version_label || formatDate(item.version_at, true)}
                            {item.file_size ? ` · ${formatBytes(item.file_size)}` : ""}
                          </p>
                        </div>
                        {item.is_final ? (
                          <span className="pill shrink-0 bg-emerald-500/10 text-emerald-300">
                            最终版
                          </span>
                        ) : item.is_intermediate ? (
                          <span className="pill shrink-0 bg-amber-500/10 text-amber-300">
                            过程版
                          </span>
                        ) : (
                          <button
                            className="shrink-0 text-[10.5px] text-brand-300 hover:underline"
                            onClick={(event) => {
                              event.stopPropagation();
                              setFinal.mutate(item.id);
                            }}
                          >
                            设为最终版
                          </button>
                        )}
                        <button
                          className="rounded p-1.5 text-mist-400 transition hover:bg-ink-700 hover:text-mist-100"
                          onClick={(event) => {
                            event.stopPropagation();
                            setPreview({
                              path: item.path_or_url,
                              title: item.title,
                            });
                          }}
                          title="预览文件"
                        >
                          <ExternalLink size={13} />
                        </button>
                        <button
                          className="rounded p-1.5 text-mist-400 transition hover:bg-ink-700 hover:text-mist-100"
                          onClick={(event) => {
                            event.stopPropagation();
                            reveal.mutate(item.path_or_url);
                          }}
                          title="打开所在文件夹"
                        >
                          <FolderOpen size={13} />
                        </button>
                        <button
                          className="rounded p-1.5 text-mist-500 transition hover:bg-ink-700 hover:text-red-300"
                          onClick={(event) => {
                            event.stopPropagation();
                            if (
                              window.confirm(
                                `从任务中移除「${item.title}」？\n只删除关联记录，不会删除磁盘文件。`,
                              )
                            ) {
                              deleteDeliverable.mutate(item.id);
                            }
                          }}
                          title="从任务移除（不删除文件）"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
              {!task.deliverables.length ? (
                <EmptyState
                  title="还没有交付物"
                  description="只收最终给人看的结果；脚本、缓存、样片等过程文件不会自动挂到这里。"
                />
              ) : null}
            </div>
          ) : null}

          {tab === "source" ? (
            <div className="space-y-3">
              {task.source_excerpt ? (
                <div className="rounded-xl border border-brand-500/20 bg-brand-500/5 p-3 text-[12px] leading-5 text-mist-300">
                  <p className="mb-1 text-[11px] font-medium text-brand-300">来源摘要</p>
                  {task.source_excerpt}
                </div>
              ) : null}
              {source.data?.items.map((message) => (
                <div
                  key={message.id}
                  className="rounded-xl border border-ink-700/70 bg-ink-900/40 p-3"
                >
                  <div className="mb-1.5 flex items-center gap-2 text-[11px] text-mist-500">
                    <span className="pill bg-ink-750 text-mist-300">{message.role}</span>
                    {message.tool_name ? <span>{message.tool_name}</span> : null}
                    <span className="ml-auto">#{message.id} · {formatDate(message.timestamp, true)}</span>
                  </div>
                  <p className="max-h-48 overflow-y-auto whitespace-pre-wrap text-[12px] leading-5 text-mist-300">
                    {message.content}
                  </p>
                </div>
              ))}
              {!task.source_message_ids.length ? (
                <EmptyState title="没有来源消息" description="手动创建的任务没有 Hermes 来源。" />
              ) : null}
            </div>
          ) : null}

          {tab === "comment" ? (
            <div className="space-y-3">
              <textarea
                className="input min-h-[90px] resize-y"
                placeholder="写一条过程记录或备注..."
                value={comment}
                onChange={(event) => setComment(event.target.value)}
              />
              <button
                className="btn-primary"
                disabled={!comment.trim() || commentMutation.isPending}
                onClick={() => commentMutation.mutate()}
              >
                <MessageSquare size={15} /> 添加评论
              </button>
              {task.timeline
                .filter((event) => event.type === "comment")
                .map((event) => (
                  <div
                    key={event.id}
                    className="rounded-xl border border-ink-700/70 bg-ink-900/40 p-3"
                  >
                    <div className="flex items-start gap-2">
                      <div className="min-w-0 flex-1">
                        <p className="text-[12px] leading-5 text-mist-200">{event.note}</p>
                        <p className="mt-1 text-[11px] text-mist-500">
                          {event.actor} · {formatDate(event.created_at, true)}
                        </p>
                      </div>
                      <button
                        className="rounded p-1 text-mist-500 transition hover:bg-ink-750 hover:text-red-300"
                        title="删除评论"
                        onClick={() => {
                          if (window.confirm("删除这条评论？")) {
                            deleteComment.mutate(event.id);
                          }
                        }}
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>
                ))}
            </div>
          ) : null}

          <div className="flex items-center gap-2 border-t border-ink-700/60 pt-3 text-[11px] text-mist-500">
            <RotateCcw size={12} />
            创建于 {formatDate(task.created_at, true)}
            {task.completed_at ? ` · 完成于 ${formatDate(task.completed_at, true)}` : ""}
            <span className="ml-auto">#{task.id}</span>
          </div>
        </div>
      )}
      </Drawer>
      <FilePreviewModal item={preview} onClose={() => setPreview(null)} />
    </>
  );
}
