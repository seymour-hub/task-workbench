import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, FolderKanban, Paperclip, AlertTriangle } from "lucide-react";
import { api } from "../api/client";
import TaskCard from "../components/tasks/TaskCard";
import { useTaskDrawer } from "../components/tasks/TaskDrawerContext";
import {
  Card,
  EmptyState,
  ProgressBar,
  Skeleton,
  Tabs,
} from "../components/ui/primitives";
import { formatDate } from "../lib/format";

export default function ProjectDetailPage() {
  const { projectId } = useParams();
  const [tab, setTab] = useState("overview");
  const { openTask } = useTaskDrawer();
  const project = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api.project(Number(projectId)),
    enabled: Boolean(projectId),
  });

  if (project.isLoading || !project.data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-[320px] w-full" />
      </div>
    );
  }

  const data = project.data;

  return (
    <div className="space-y-4">
      <Link
        to="/projects"
        className="inline-flex items-center gap-1 text-[12px] text-mist-400 transition hover:text-mist-100"
      >
        <ArrowLeft size={14} /> 返回项目列表
      </Link>

      <Card className="relative overflow-hidden p-5">
        <span className="absolute inset-x-0 top-0 h-1" style={{ background: data.color }} />
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-4">
            <span
              className="flex h-12 w-12 items-center justify-center rounded-2xl"
              style={{ background: `${data.color}25`, color: data.color }}
            >
              <FolderKanban size={23} />
            </span>
            <div>
              <h1 className="text-[20px] font-semibold text-mist-100">{data.name}</h1>
              <p className="mt-1 max-w-xl text-[12px] text-mist-400">
                {data.description || "暂无描述"}
              </p>
            </div>
          </div>
          <div className="grid grid-cols-4 gap-2 text-center">
            {[
              ["任务", data.task_count, "text-mist-100"],
              ["完成", data.done_count, "text-emerald-300"],
              ["逾期", data.overdue_count, "text-red-300"],
              ["进度", `${data.progress}%`, "text-brand-300"],
            ].map(([label, value, tone]) => (
              <div key={String(label)} className="min-w-[64px] rounded-xl bg-ink-900/50 px-3 py-2">
                <p className={`text-[16px] font-semibold ${tone}`}>{value}</p>
                <p className="text-[10px] text-mist-500">{label}</p>
              </div>
            ))}
          </div>
        </div>
        <div className="mt-5 max-w-2xl">
          <ProgressBar value={data.progress} color={data.color} height={8} />
        </div>
      </Card>

      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[
          { key: "overview", label: "概览" },
          { key: "tasks", label: "任务", count: data.tasks.length },
          { key: "issues", label: "问题", count: data.issues.length },
          { key: "deliverables", label: "交付物", count: data.deliverables.length },
        ]}
      />

      {tab === "overview" ? (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <Card className="xl:col-span-2">
            <h2 className="panel-title mb-3">最近任务</h2>
            <div className="space-y-2.5">
              {data.tasks.slice(0, 8).map((task) => (
                <TaskCard key={task.id} task={task} onClick={() => openTask(task.id)} />
              ))}
              {!data.tasks.length ? <EmptyState title="项目还没有任务" /> : null}
            </div>
          </Card>
          <div className="space-y-4">
            <Card>
              <h2 className="panel-title mb-3 flex items-center gap-2">
                <AlertTriangle size={15} className="text-amber-400" /> 待解决问题
              </h2>
              {data.issues.filter((issue) => issue.status !== "resolved").slice(0, 6).map((issue) => (
                <div key={issue.id} className="border-b border-ink-700/40 py-2 last:border-0">
                  <p className="text-[12.5px] text-mist-200">{issue.title}</p>
                  <p className="mt-0.5 text-[10px] text-mist-500">
                    {issue.severity} · {issue.status === "resolved" ? "已解决" : "未解决"}
                  </p>
                </div>
              ))}
              {!data.issues.length ? (
                <p className="py-4 text-center text-[12px] text-mist-500">暂无问题</p>
              ) : null}
            </Card>
            <Card>
              <h2 className="panel-title mb-3 flex items-center gap-2">
                <Paperclip size={15} className="text-emerald-400" /> 最近交付物
              </h2>
              {data.deliverables.slice(0, 6).map((item) => (
                <div key={item.id} className="border-b border-ink-700/40 py-2 last:border-0">
                  <p className="truncate text-[12.5px] text-mist-200">{item.title}</p>
                  <p className="mt-0.5 truncate text-[10px] text-mist-500">{item.path_or_url}</p>
                </div>
              ))}
              {!data.deliverables.length ? (
                <p className="py-4 text-center text-[12px] text-mist-500">暂无交付物</p>
              ) : null}
            </Card>
          </div>
        </div>
      ) : null}

      {tab === "tasks" ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {data.tasks.map((task) => (
            <TaskCard key={task.id} task={task} onClick={() => openTask(task.id)} />
          ))}
        </div>
      ) : null}

      {tab === "issues" ? (
        <Card>
          {data.issues.map((issue) => (
            <div key={issue.id} className="border-b border-ink-700/40 py-3 last:border-0">
              <div className="flex items-center gap-2">
                <span className="text-[13px] text-mist-100">{issue.title}</span>
                <span className="pill bg-ink-750 text-mist-400">{issue.severity}</span>
                <span className="ml-auto text-[11px] text-mist-500">
                  {issue.status === "resolved" ? "已解决" : "未解决"}
                </span>
              </div>
            </div>
          ))}
          {!data.issues.length ? <EmptyState title="项目没有关联问题" /> : null}
        </Card>
      ) : null}

      {tab === "deliverables" ? (
        <Card>
          {data.deliverables.map((item) => (
            <div key={item.id} className="flex items-center gap-3 border-b border-ink-700/40 py-3 last:border-0">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400">
                <Paperclip size={15} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] text-mist-100">{item.title}</p>
                <p className="truncate text-[11px] text-mist-500">{item.path_or_url}</p>
              </div>
              <span className="text-[11px] text-mist-500">{formatDate(item.created_at)}</span>
            </div>
          ))}
          {!data.deliverables.length ? <EmptyState title="项目没有交付物" /> : null}
        </Card>
      ) : null}
    </div>
  );
}
