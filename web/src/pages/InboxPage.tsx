import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  AlertTriangle,
  Check,
  Eye,
  Inbox,
  Paperclip,
  RefreshCw,
  Sparkles,
  StickyNote,
  X,
} from "lucide-react";
import { api } from "../api/client";
import type { InboxItem } from "../api/types";
import { useTaskDrawer } from "../components/tasks/TaskDrawerContext";
import {
  Card,
  EmptyState,
  Modal,
  PriorityBadge,
  Skeleton,
  Tabs,
} from "../components/ui/primitives";
import { cn, formatDate, formatDeadline, PRIORITY, toLocalInput } from "../lib/format";

const KIND_META: Record<string, { label: string; icon: any; color: string }> = {
  task: { label: "任务", icon: Sparkles, color: "text-brand-300 bg-brand-500/10" },
  issue: { label: "问题", icon: AlertTriangle, color: "text-amber-300 bg-amber-500/10" },
  deliverable: { label: "交付物", icon: Paperclip, color: "text-emerald-300 bg-emerald-500/10" },
  note: { label: "决策/后续", icon: StickyNote, color: "text-violet-300 bg-violet-500/10" },
};

export default function InboxPage() {
  const [status, setStatus] = useState("pending");
  const [kind, setKind] = useState("task");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [accepting, setAccepting] = useState<InboxItem | null>(null);
  const [evidence, setEvidence] = useState<InboxItem | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [projectId, setProjectId] = useState("");
  const [priority, setPriority] = useState("medium");
  const [taskStatus, setTaskStatus] = useState("todo");
  const [due, setDue] = useState("");
  const [targetTask, setTargetTask] = useState("");
  const queryClient = useQueryClient();
  const { openTask } = useTaskDrawer();

  const inbox = useQuery({
    queryKey: ["inbox", status, kind],
    queryFn: () => api.inbox(status, kind || undefined),
  });
  const projects = useQuery({ queryKey: ["projects"], queryFn: api.projects });
  const tasks = useQuery({ queryKey: ["tasks", "inbox-select"], queryFn: () => api.tasks({ limit: 500 }) });
  const messages = useQuery({
    queryKey: ["evidence", evidence?.id],
    queryFn: () => api.sourceMessages(evidence?.source_message_ids || []),
    enabled: Boolean(evidence),
  });
  const confirmations = useQuery({
    queryKey: ["pending-confirmations"],
    queryFn: api.pendingConfirmations,
    refetchInterval: 30_000,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["inbox"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    queryClient.invalidateQueries({ queryKey: ["tasks"] });
    queryClient.invalidateQueries({ queryKey: ["board"] });
    queryClient.invalidateQueries({ queryKey: ["projects"] });
  };

  const accept = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      api.acceptInbox(accepting!.id, payload, true),
    onSuccess: () => {
      invalidate();
      setAccepting(null);
      toast.success("已接受，任务已进入看板");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const reject = useMutation({
    mutationFn: (id: number) => api.rejectInbox(id),
    onSuccess: () => {
      invalidate();
      toast.success("已忽略该候选");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const retry = useMutation({
    mutationFn: (id: number) => api.retryInbox(id),
    onSuccess: () => {
      invalidate();
      toast.success("已重置片段，等待重新抽取");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const resolveConfirmation = useMutation({
    mutationFn: ({
      id,
      action,
    }: {
      id: number;
      action: "accept" | "reject";
    }) => api.resolveConfirmation(id, action),
    onSuccess: (_data, variables) => {
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["pending-confirmations"] });
      toast.success(variables.action === "accept" ? "已确认" : "已忽略");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const dedupe = useMutation({
    mutationFn: () => api.dedupeInbox(),
    onSuccess: (result) => {
      invalidate();
      toast.success(`已标记 ${result.marked} 条重复候选`);
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const bulk = useMutation({
    mutationFn: (action: "accept" | "reject") => api.bulkInbox(action, [...selected]),
    onSuccess: () => {
      invalidate();
      setSelected(new Set());
      toast.success("批量操作完成");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const items = inbox.data?.items || [];

  const openAccept = (item: InboxItem) => {
    setAccepting(item);
    const payload = item.payload || {};
    setTitle(payload.title || "");
    setDescription(payload.description || "");
    setProjectId(payload.project_id ? String(payload.project_id) : "");
    setPriority(payload.priority || "medium");
    setTaskStatus(payload.status || "todo");
    setDue(toLocalInput(payload.due_at));
    setTargetTask("");
  };

  const submitAccept = () => {
    if (!accepting) return;
    if (accepting.kind === "task") {
      accept.mutate({
        title,
        description,
        project_id: projectId ? Number(projectId) : null,
        priority,
        status: taskStatus,
        due_at: due ? new Date(due).getTime() / 1000 : null,
      });
    } else if (["issue", "deliverable", "note"].includes(accepting.kind)) {
      if (!targetTask) {
        toast.error("请选择要挂接的任务");
        return;
      }
      accept.mutate({ task_id: Number(targetTask) });
    } else {
      accept.mutate({});
    }
  };

  const toggle = (id: number) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[20px] font-semibold text-mist-100">候选收件箱</h1>
          <p className="mt-1 text-[12px] text-mist-500">
            AI 从 Hermes 会话中抽取的工作项。默认需要人工确认，避免编造任务污染看板。
          </p>
        </div>
        <div className="flex items-center gap-2">
          {selected.size ? (
            <>
              <button className="btn-ghost h-9" onClick={() => bulk.mutate("reject")}>
                <X size={14} /> 忽略所选（{selected.size}）
              </button>
              <button className="btn-primary h-9" onClick={() => bulk.mutate("accept")}>
                <Check size={14} /> 全部接受
              </button>
            </>
          ) : null}
          <button
            className="btn-ghost h-9"
            onClick={() => dedupe.mutate()}
            disabled={dedupe.isPending}
          >
            <RefreshCw size={14} /> 合并重复
          </button>
          <span className="rounded-lg border border-ink-700 bg-ink-900/60 px-3 py-1.5 text-[11px] text-mist-400">
            待确认 {inbox.data?.counts.pending ?? 0} · 任务{" "}
            {inbox.data?.by_kind?.task ?? 0} · 疑似重复 {inbox.data?.counts.duplicate ?? 0}
          </span>
        </div>
      </div>

      {confirmations.data?.items?.length ? (
        <Card className="border-amber-500/20 bg-amber-500/5 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <Sparkles size={15} className="text-amber-300" />
            <p className="text-[13px] font-semibold text-mist-100">飞书待确认</p>
            <span className="text-[11px] text-mist-500">
              共 {confirmations.data.items.length} 条 · 也可以在飞书里回复
            </span>
          </div>
          <div className="mt-3 space-y-2">
            {confirmations.data.items.map((item: any) => (
              <div
                key={item.id}
                className="flex flex-wrap items-center gap-2 rounded-xl border border-ink-700/60 bg-ink-900/40 p-3"
              >
                <span className="pill bg-amber-500/10 text-amber-300">
                  {item.kind === "start_task" ? "新任务" : "完成确认"}
                </span>
                <span className="min-w-0 flex-1 truncate text-[13px] text-mist-100">
                  {item.title}
                </span>
                <span className="text-[10px] text-mist-500">#{item.code}</span>
                {item.question_sent === false ? (
                  <span
                    className="pill bg-red-500/10 text-red-300"
                    title={item.question_error || "飞书确认消息发送失败"}
                  >
                    飞书发送失败
                  </span>
                ) : null}
                <div className="ml-auto flex items-center gap-2">
                  <button
                    className="btn-ghost h-7 px-2.5 text-[11px]"
                    onClick={() =>
                      resolveConfirmation.mutate({ id: item.id, action: "reject" })
                    }
                  >
                    <X size={13} />{" "}
                    {item.kind === "start_task" ? "忽略" : "取消"}
                  </button>
                  <button
                    className="btn-primary h-7 px-2.5 text-[11px]"
                    onClick={() =>
                      resolveConfirmation.mutate({ id: item.id, action: "accept" })
                    }
                  >
                    <Check size={13} />{" "}
                    {item.kind === "start_task" ? "加入" : "完成"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      ) : null}

      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Tabs
            value={status}
            onChange={(key) => {
              setStatus(key);
              setSelected(new Set());
            }}
            tabs={[
              { key: "pending", label: "待确认" },
              { key: "auto_accepted", label: "已自动加入" },
              { key: "duplicate", label: "疑似重复" },
              { key: "accepted", label: "已接受" },
              { key: "rejected", label: "已忽略" },
              { key: "all", label: "全部" },
            ]}
          />
          <select
            className="ml-auto h-8 rounded-lg border border-ink-700 bg-ink-900/60 px-2 text-[11px] text-mist-300 outline-none"
            value={kind}
            onChange={(event) => setKind(event.target.value)}
          >
            <option value="">全部类型（{inbox.data?.counts.pending ?? 0}）</option>
            <option value="task">任务（{inbox.data?.by_kind?.task ?? 0}）</option>
            <option value="issue">问题（{inbox.data?.by_kind?.issue ?? 0}）</option>
            <option value="deliverable">交付物（{inbox.data?.by_kind?.deliverable ?? 0}）</option>
            <option value="note">决策/后续（{inbox.data?.by_kind?.note ?? 0}）</option>
          </select>
        </div>

        <div className="mt-4 space-y-2.5">
          {inbox.isLoading ? (
            [0, 1, 2, 3].map((item) => <Skeleton key={item} className="h-24 w-full" />)
          ) : !items.length ? (
            <EmptyState
              icon={<Inbox size={20} />}
              title="收件箱是空的"
              description="点击设置页的“立即同步 + 立即抽取”，或等待定时任务处理新的 Hermes 会话。"
            />
          ) : (
            items.map((item) => {
              const payload = item.payload || {};
              const meta = KIND_META[item.kind] || KIND_META.note;
              const Icon = meta.icon;
              const isTask = item.kind === "task";
              return (
                <div
                  key={item.id}
                  className={cn(
                    "rounded-xl border border-ink-700/70 bg-ink-900/40 p-3.5 transition hover:border-ink-600",
                    selected.has(item.id) && "border-brand-500/40 bg-brand-500/5",
                  )}
                >
                  <div className="flex items-start gap-3">
                    <button
                      onClick={() => toggle(item.id)}
                      className={cn(
                        "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border",
                        selected.has(item.id)
                          ? "border-brand-400 bg-brand-500 text-white"
                          : "border-ink-500 text-transparent",
                      )}
                    >
                      <Check size={11} strokeWidth={3} />
                    </button>
                    <span className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-lg", meta.color)}>
                      <Icon size={15} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-[11px] text-mist-500">{meta.label}</span>
                        {isTask ? <PriorityBadge priority={payload.priority || "medium"} /> : null}
                        {payload.project_hint ? (
                          <span className="pill bg-ink-750 text-mist-400">
                            {payload.project_hint}
                          </span>
                        ) : null}
                        {payload.possible_duplicate || item.status === "duplicate" ? (
                          <span className="pill bg-amber-500/10 text-amber-300">
                            可能重复 {payload.dedup_score ? `(${payload.dedup_score})` : ""}
                          </span>
                        ) : null}
                        <span className="ml-auto text-[10px] text-mist-600">
                          置信度 {Math.round((item.confidence || 0) * 100)}%
                        </span>
                      </div>
                      <p className="mt-1.5 text-[13.5px] font-medium leading-5 text-mist-100">
                        {isTask ? payload.title : payload.title || payload.summary}
                      </p>
                      {isTask && payload.description ? (
                        <p className="mt-1 line-clamp-2 text-[11.5px] leading-4 text-mist-500">
                          {payload.description}
                        </p>
                      ) : null}
                      {!isTask && payload.path_or_url ? (
                        <p className="mt-1 truncate text-[11px] text-mist-500">
                          {payload.path_or_url}
                          {payload.exists ? " · 文件存在" : " · 文件不存在"}
                        </p>
                      ) : null}
                      {!isTask && payload.detail ? (
                        <p className="mt-1 line-clamp-2 text-[11.5px] leading-4 text-mist-500">
                          {payload.detail}
                        </p>
                      ) : null}
                      <div className="mt-2 flex flex-wrap items-center gap-3 text-[10.5px] text-mist-500">
                        <span>{formatDate(item.created_at, true)}</span>
                        <span>证据 {item.source_message_ids?.length || 0} 条</span>
                        {isTask && payload.due_at ? (
                          <span>{formatDeadline(payload.due_at).text}</span>
                        ) : null}
                        <button
                          className="flex items-center gap-1 text-brand-400/80 hover:text-brand-300"
                          onClick={() => setEvidence(item)}
                        >
                          <Eye size={12} /> 查看证据
                        </button>
                        <div className="ml-auto flex items-center gap-2">
                          {item.status === "auto_accepted" ? (
                            <>
                              <span className="pill bg-emerald-500/10 text-emerald-300">
                                已自动加入
                              </span>
                              {payload.task_id ? (
                                <button
                                  className="btn-primary h-7 px-2.5 text-[11px]"
                                  onClick={() => openTask(Number(payload.task_id))}
                                >
                                  <Check size={13} /> 打开任务
                                </button>
                              ) : null}
                            </>
                          ) : (
                            <>
                              <button
                                className="rounded px-2 py-1 text-mist-400 transition hover:bg-ink-750 hover:text-mist-200"
                                onClick={() => retry.mutate(item.id)}
                                title="重新抽取该片段"
                              >
                                <RefreshCw size={13} />
                              </button>
                              <button
                                className="rounded px-2 py-1 text-mist-400 transition hover:bg-ink-750 hover:text-red-300"
                                onClick={() => reject.mutate(item.id)}
                              >
                                <X size={14} />
                              </button>
                              <button
                                className="btn-primary h-7 px-2.5 text-[11px]"
                                onClick={() => openAccept(item)}
                                disabled={item.status === "accepted" || item.status === "rejected"}
                              >
                                <Check size={13} /> 接受
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </Card>

      <Modal
        open={Boolean(accepting)}
        onClose={() => setAccepting(null)}
        title={
          accepting?.kind === "task"
            ? "接受为任务"
            : accepting?.kind === "issue"
              ? "接受问题并挂接任务"
              : accepting?.kind === "deliverable"
                ? "接受交付物并挂接任务"
                : accepting?.kind === "note"
                  ? "接受笔记并挂接任务"
                  : "确认该条目"
        }
        footer={
          <>
            <button className="btn-ghost" onClick={() => setAccepting(null)}>
              取消
            </button>
            <button className="btn-primary" disabled={accept.isPending} onClick={submitAccept}>
              确认接受
            </button>
          </>
        }
      >
        {accepting?.kind === "task" ? (
          <div className="space-y-3">
            <label className="block text-xs text-mist-400">
              标题
              <input
                className="input mt-1"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
              />
            </label>
            <label className="block text-xs text-mist-400">
              描述
              <textarea
                className="input mt-1 min-h-[80px]"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block text-xs text-mist-400">
                项目
                <select
                  className="input mt-1"
                  value={projectId}
                  onChange={(event) => setProjectId(event.target.value)}
                >
                  <option value="">未归类</option>
                  {projects.data?.items.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-xs text-mist-400">
                优先级
                <select
                  className="input mt-1"
                  value={priority}
                  onChange={(event) => setPriority(event.target.value)}
                >
                  {Object.entries(PRIORITY).map(([key, value]) => (
                    <option key={key} value={key}>
                      {value.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-xs text-mist-400">
                初始状态
                <select
                  className="input mt-1"
                  value={taskStatus}
                  onChange={(event) => setTaskStatus(event.target.value)}
                >
                  <option value="todo">待处理</option>
                  <option value="in_progress">进行中</option>
                  <option value="done">已完成</option>
                </select>
              </label>
              <label className="block text-xs text-mist-400">
                截止时间
                <input
                  type="datetime-local"
                  className="input mt-1"
                  value={due}
                  onChange={(event) => setDue(event.target.value)}
                />
              </label>
            </div>
          </div>
        ) : ["issue", "deliverable", "note"].includes(accepting?.kind || "") ? (
          <div className="space-y-3">
            <p className="rounded-lg bg-ink-900/60 p-3 text-[12.5px] leading-5 text-mist-300">
              {accepting?.payload?.title || accepting?.payload?.summary}
            </p>
            <label className="block text-xs text-mist-400">
              挂接到任务
              <select
                className="input mt-1"
                value={targetTask}
                onChange={(event) => setTargetTask(event.target.value)}
              >
                <option value="">请选择任务</option>
                {tasks.data?.items.map((task) => (
                  <option key={task.id} value={task.id}>
                    #{task.id} {task.title}
                  </option>
                ))}
              </select>
            </label>
          </div>
        ) : (
          <p className="rounded-lg bg-ink-900/60 p-3 text-[12.5px] leading-5 text-mist-300">
            {accepting?.payload?.summary}
          </p>
        )}
      </Modal>

      <Modal
        open={Boolean(evidence)}
        onClose={() => setEvidence(null)}
        title="来源证据"
        width="max-w-2xl"
      >
        <div className="max-h-[60vh] space-y-3 overflow-y-auto">
          {messages.isLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : (
            messages.data?.items.map((message) => (
              <div
                key={message.id}
                className="rounded-xl border border-ink-700/70 bg-ink-900/40 p-3"
              >
                <div className="mb-1.5 flex items-center gap-2 text-[11px] text-mist-500">
                  <span className="pill bg-ink-750 text-mist-300">{message.role}</span>
                  {message.tool_name ? <span>{message.tool_name}</span> : null}
                  <span className="ml-auto">
                    #{message.id} · {formatDate(message.timestamp, true)}
                  </span>
                </div>
                <p className="whitespace-pre-wrap text-[12px] leading-5 text-mist-300">
                  {message.content}
                </p>
              </div>
            ))
          )}
          {!messages.isLoading && !messages.data?.items.length ? (
            <EmptyState title="没有可展示的来源消息" />
          ) : null}
        </div>
      </Modal>
    </div>
  );
}
