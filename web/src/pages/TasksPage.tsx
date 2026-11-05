import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Check,
  CheckCircle2,
  ListFilter,
  Plus,
  Search,
  Table2,
  Rows3,
} from "lucide-react";
import { api } from "../api/client";
import type { Task } from "../api/types";
import TaskCreateModal from "../components/tasks/TaskCreateModal";
import { useTaskDrawer } from "../components/tasks/TaskDrawerContext";
import {
  Avatar,
  Card,
  EmptyState,
  PriorityBadge,
  Skeleton,
  StatusBadge,
  Tabs,
} from "../components/ui/primitives";
import { cn, formatDate, formatDeadline } from "../lib/format";
import { PRIORITY } from "../lib/format";
import { CATEGORIES, WORK_TYPES, categoryColor } from "../lib/taxonomy";

const TABS = [
  { key: "all", label: "全部" },
  { key: "open", label: "未完成" },
  { key: "todo", label: "待开始" },
  { key: "in_progress", label: "进行中" },
  { key: "done", label: "已完成" },
  { key: "overdue", label: "已逾期" },
  { key: "today", label: "今天到期" },
  { key: "cancelled", label: "已取消" },
];

export default function TasksPage() {
  const [params, setParams] = useSearchParams();
  const [tab, setTab] = useState(params.get("status") || "all");
  const [projectId, setProjectId] = useState("");
  const [priority, setPriority] = useState("");
  const [category, setCategory] = useState("");
  const [workType, setWorkType] = useState("");
  const [keyword, setKeyword] = useState(params.get("q") || "");
  const [view, setView] = useState<"list" | "table">("table");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [createOpen, setCreateOpen] = useState(false);
  const { openTask } = useTaskDrawer();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (params.get("q")) setKeyword(params.get("q") || "");
  }, [params]);

  const statusParam = params.get("status");
  useEffect(() => {
    setTab(statusParam || "all");
  }, [statusParam]);

  const projects = useQuery({ queryKey: ["projects"], queryFn: api.projects });
  const queryKey = ["tasks", tab, projectId, priority, category, workType, keyword];
  const tasks = useQuery({
    queryKey,
    queryFn: () =>
      api.tasks({
        status: tab === "all" ? undefined : tab,
        project_id: projectId || undefined,
        priority: priority || undefined,
        category: category || undefined,
        work_type: workType || undefined,
        q: keyword || undefined,
        limit: 500,
      }),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["tasks"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    queryClient.invalidateQueries({ queryKey: ["board"] });
    queryClient.invalidateQueries({ queryKey: ["projects"] });
  };

  const bulkComplete = useMutation({
    mutationFn: async (ids: number[]) => {
      await Promise.all(ids.map((id) => api.completeTask(id)));
    },
    onSuccess: () => {
      setSelected(new Set());
      invalidate();
      toast.success("已批量完成");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const items = tasks.data?.items || [];
  const allSelected = items.length > 0 && items.every((task) => selected.has(task.id));

  const toggleAll = () => {
    setSelected(allSelected ? new Set() : new Set(items.map((task) => task.id)));
  };

  const switchTab = (key: string) => {
    setTab(key);
    const next = new URLSearchParams(params);
    if (key === "all") next.delete("status");
    else next.set("status", key);
    setParams(next, { replace: true });
  };

  const submitKeyword = (event: React.FormEvent) => {
    event.preventDefault();
    const next = new URLSearchParams(params);
    if (keyword.trim()) next.set("q", keyword.trim());
    else next.delete("q");
    setParams(next, { replace: true });
    queryClient.invalidateQueries({ queryKey: ["tasks"] });
  };

  const counts = useMemo(
    () => ({
      total: items.length,
      done: items.filter((task) => task.status === "done").length,
      overdue: items.filter((task) => task.overdue).length,
    }),
    [items],
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[20px] font-semibold text-mist-100">我的任务</h1>
          <p className="mt-1 text-[12px] text-mist-500">
            共 {counts.total} 项 · 已完成 {counts.done} · 逾期 {counts.overdue}
          </p>
        </div>
        <button className="btn-primary" onClick={() => setCreateOpen(true)}>
          <Plus size={16} /> 新建任务
        </button>
      </div>

      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Tabs
            value={tab}
            onChange={switchTab}
            tabs={TABS.map((item) => ({
              ...item,
              count: item.key === "all" ? undefined : undefined,
            }))}
          />
          <div className="ml-auto flex items-center gap-2">
            <div className="flex rounded-lg border border-ink-700 bg-ink-900/60 p-0.5">
              <button
                onClick={() => setView("table")}
                className={cn(
                  "rounded-md p-1.5",
                  view === "table" ? "bg-ink-700 text-mist-100" : "text-mist-500",
                )}
              >
                <Table2 size={15} />
              </button>
              <button
                onClick={() => setView("list")}
                className={cn(
                  "rounded-md p-1.5",
                  view === "list" ? "bg-ink-700 text-mist-100" : "text-mist-500",
                )}
              >
                <Rows3 size={15} />
              </button>
            </div>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <form
            onSubmit={submitKeyword}
            className="flex h-9 min-w-[190px] flex-1 items-center gap-2 rounded-lg border border-ink-700 bg-ink-900/60 px-2.5 sm:max-w-[280px]"
          >
            <Search size={14} className="text-mist-500" />
            <input
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="筛选任务标题..."
              className="w-full bg-transparent text-[12px] text-mist-100 outline-none placeholder:text-mist-600"
            />
          </form>
          <div className="flex items-center gap-1 text-[11px] text-mist-500">
            <ListFilter size={13} /> 筛选
          </div>
          <select
            className="h-9 rounded-lg border border-ink-700 bg-ink-900/60 px-2 text-[12px] text-mist-300 outline-none"
            value={projectId}
            onChange={(event) => setProjectId(event.target.value)}
          >
            <option value="">全部项目</option>
            {projects.data?.items.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
          <select
            className="h-9 rounded-lg border border-ink-700 bg-ink-900/60 px-2 text-[12px] text-mist-300 outline-none"
            value={priority}
            onChange={(event) => setPriority(event.target.value)}
          >
            <option value="">全部优先级</option>
            {Object.entries(PRIORITY).map(([key, value]) => (
              <option key={key} value={key}>
                {value.label}
              </option>
            ))}
          </select>
          <select
            className="h-9 rounded-lg border border-ink-700 bg-ink-900/60 px-2 text-[12px] text-mist-300 outline-none"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          >
            <option value="">全部业务域</option>
            {CATEGORIES.map((item) => (
              <option key={item.name} value={item.name}>
                {item.name}
              </option>
            ))}
          </select>
          <select
            className="h-9 rounded-lg border border-ink-700 bg-ink-900/60 px-2 text-[12px] text-mist-300 outline-none"
            value={workType}
            onChange={(event) => setWorkType(event.target.value)}
          >
            <option value="">全部工作类型</option>
            {WORK_TYPES.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          {selected.size ? (
            <button
              className="btn-ghost h-9"
              onClick={() => bulkComplete.mutate([...selected])}
            >
              <CheckCircle2 size={14} /> 完成所选（{selected.size}）
            </button>
          ) : null}
        </div>

        <div className="mt-4">
          {tasks.isLoading ? (
            <div className="space-y-2">
              {[0, 1, 2, 3, 4].map((item) => (
                <Skeleton key={item} className="h-12 w-full" />
              ))}
            </div>
          ) : !items.length ? (
            <EmptyState
              icon={<CheckCircle2 size={20} />}
              title="没有符合条件的任务"
              description="调整筛选条件，或从候选收件箱认领一项工作。"
            />
          ) : view === "table" ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] border-collapse text-left">
                <thead>
                  <tr className="text-[11px] uppercase tracking-wide text-mist-500">
                    <th className="w-9 pb-2">
                      <button
                        onClick={toggleAll}
                        className={cn(
                          "flex h-4 w-4 items-center justify-center rounded border",
                          allSelected
                            ? "border-brand-400 bg-brand-500 text-white"
                            : "border-ink-500 text-transparent",
                        )}
                      >
                        <Check size={11} strokeWidth={3} />
                      </button>
                    </th>
                    <th className="pb-2">任务</th>
                    <th className="w-[120px] pb-2">项目</th>
                    <th className="w-[80px] pb-2">优先级</th>
                    <th className="w-[130px] pb-2">截止</th>
                    <th className="w-[130px] pb-2">周期</th>
                    <th className="w-[80px] pb-2">状态</th>
                    <th className="w-[70px] pb-2">负责人</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((task) => (
                    <TaskRow
                      key={task.id}
                      task={task}
                      selected={selected.has(task.id)}
                      onSelect={() =>
                        setSelected((current) => {
                          const next = new Set(current);
                          if (next.has(task.id)) next.delete(task.id);
                          else next.add(task.id);
                          return next;
                        })
                      }
                      onOpen={() => openTask(task.id)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="space-y-2">
              {items.map((task) => {
                const deadline = formatDeadline(task.due_at);
                return (
                  <button
                    key={task.id}
                    onClick={() => openTask(task.id)}
                    className="flex w-full items-center gap-3 rounded-xl border border-ink-700/50 bg-ink-900/30 px-3 py-2.5 text-left transition hover:border-brand-500/30 hover:bg-ink-750/50"
                  >
                    <span
                      className="h-2 w-2 shrink-0 rounded-full"
                      style={{ background: task.overdue ? "#EF4444" : "#5B7CFA" }}
                    />
                    <span className="min-w-0 flex-1 truncate text-[13px] text-mist-200">
                      {task.title}
                    </span>
                    {task.category ? (
                      <span
                        className="pill shrink-0 border border-ink-700 bg-ink-800"
                        style={{ color: categoryColor(task.category) }}
                        title={task.subcategory || task.category}
                      >
                        {task.category}
                      </span>
                    ) : null}
                    <PriorityBadge priority={task.priority} />
                    <span
                      className={cn(
                        "w-[130px] text-right text-[11px]",
                        task.status === "done" ? "text-mist-500" : deadline.tone,
                      )}
                    >
                      {task.due_at
                        ? deadline.text
                        : task.started_at || task.ended_at
                          ? `${formatDate(task.started_at)} → ${formatDate(task.ended_at)}`
                          : "—"}
                    </span>
                    <StatusBadge status={task.status} />
                    <Avatar name={task.assignee_name || "我"} color={task.assignee_color} size={24} />
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </Card>

      <TaskCreateModal open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  );
}

function TaskRow({
  task,
  selected,
  onSelect,
  onOpen,
}: {
  task: Task;
  selected: boolean;
  onSelect: () => void;
  onOpen: () => void;
}) {
  const deadline = formatDeadline(task.due_at);
  return (
    <tr className="table-row cursor-pointer text-[12.5px]" onClick={onOpen}>
      <td className="py-2.5" onClick={(event) => event.stopPropagation()}>
        <button
          onClick={onSelect}
          className={cn(
            "flex h-4 w-4 items-center justify-center rounded border",
            selected
              ? "border-brand-400 bg-brand-500 text-white"
              : "border-ink-500 text-transparent",
          )}
        >
          <Check size={11} strokeWidth={3} />
        </button>
      </td>
      <td className="max-w-[380px] py-2.5">
        <p
          className={cn(
            "truncate text-mist-100",
            task.status === "done" && "text-mist-500 line-through",
          )}
        >
          {task.title}
        </p>
        <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[10px]">
          {task.category ? (
            <span
              className="flex items-center gap-1 text-mist-500"
              title={task.subcategory || task.category}
            >
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{ background: categoryColor(task.category) }}
              />
              {task.category}
              {task.subcategory ? ` · ${task.subcategory}` : ""}
            </span>
          ) : null}
          {task.source_type === "hermes_session" ? (
            <span className="text-brand-400/80">来自 Hermes 会话</span>
          ) : null}
        </div>
      </td>
      <td className="py-2.5 text-mist-400">
        {task.project_name ? (
          <span className="flex items-center gap-1.5">
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ background: task.project_color || "#5B7CFA" }}
            />
            {task.project_name}
          </span>
        ) : (
          "—"
        )}
      </td>
      <td className="py-2.5">
        <PriorityBadge priority={task.priority} />
      </td>
      <td
        className={cn(
          "py-2.5 text-[11px]",
          task.status === "done" ? "text-mist-500" : deadline.tone,
        )}
      >
        {task.due_at ? deadline.text : "—"}
      </td>
      <td className="py-2.5 text-[11px] text-mist-400">
        {task.started_at || task.ended_at
          ? `${formatDate(task.started_at)} → ${formatDate(task.ended_at)}`
          : "—"}
      </td>
      <td className="py-2.5">
        <StatusBadge status={task.status} />
      </td>
      <td className="py-2.5">
        <Avatar name={task.assignee_name || "我"} color={task.assignee_color} size={24} />
      </td>
    </tr>
  );
}
