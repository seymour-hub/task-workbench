import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  ArrowUpRight,
  CheckCircle2,
  ClipboardList,
  Flag,
  Plus,
  Timer,
} from "lucide-react";
import { api } from "../api/client";
import KanbanBoard from "../components/board/KanbanBoard";
import TaskCreateModal from "../components/tasks/TaskCreateModal";
import DeadlineList from "../components/dashboard/DeadlineList";
import ScheduleTimeline from "../components/dashboard/ScheduleTimeline";
import TaskDonut from "../components/dashboard/TaskDonut";
import TodayTasks from "../components/dashboard/TodayTasks";
import WeeklyProgress from "../components/dashboard/WeeklyProgress";
import { Card, SectionHeader, Skeleton } from "../components/ui/primitives";
import { cn, greeting } from "../lib/format";

const STAT_STYLES = [
  {
    icon: ClipboardList,
    bg: "from-blue-500/25 to-blue-500/5",
    iconBg: "bg-blue-500/90",
    glow: "shadow-[0_16px_40px_-20px_rgba(59,130,246,0.8)]",
  },
  {
    icon: CheckCircle2,
    bg: "from-emerald-500/25 to-emerald-500/5",
    iconBg: "bg-emerald-500/90",
    glow: "shadow-[0_16px_40px_-20px_rgba(16,185,129,0.8)]",
  },
  {
    icon: Timer,
    bg: "from-amber-500/25 to-amber-500/5",
    iconBg: "bg-amber-500/90",
    glow: "shadow-[0_16px_40px_-20px_rgba(245,158,11,0.8)]",
  },
  {
    icon: Flag,
    bg: "from-violet-500/25 to-violet-500/5",
    iconBg: "bg-violet-500/90",
    glow: "shadow-[0_16px_40px_-20px_rgba(139,92,246,0.8)]",
  },
];

export default function DashboardPage() {
  const [createOpen, setCreateOpen] = useState(false);
  const queryClient = useQueryClient();
  const dashboard = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });
  const board = useQuery({ queryKey: ["board"], queryFn: () => api.board() });

  const move = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      api.moveTask(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["board"] });
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      toast.success("任务状态已更新");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  if (dashboard.isLoading || !dashboard.data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24 w-full" />
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          {[0, 1, 2, 3].map((item) => (
            <Skeleton key={item} className="h-[116px] w-full" />
          ))}
        </div>
        <div className="grid grid-cols-12 gap-4">
          <Skeleton className="col-span-12 h-[290px] xl:col-span-7" />
          <Skeleton className="col-span-12 h-[290px] xl:col-span-5" />
        </div>
      </div>
    );
  }

  const data = dashboard.data;
  const stats = data.stats;
  const inProgress = data.donut.segments.find((item) => item.key === "in_progress")?.value || 0;
  const todoCount = data.donut.segments.find((item) => item.key === "todo")?.value || 0;
  const overdueCount = data.donut.segments.find((item) => item.key === "overdue")?.value || 0;
  const cards = [
    {
      label: "我的任务",
      value: stats.total,
      hint: `${inProgress} 个进行中`,
      color: "text-blue-300",
      to: "/tasks",
    },
    {
      label: "已完成",
      value: stats.completed,
      hint: `较上周 ${stats.completion_delta >= 0 ? "+" : ""}${stats.completion_delta}%`,
      color: "text-emerald-300",
      to: "/tasks?status=done",
    },
    {
      label: "未完成",
      value: stats.pending,
      hint: `进行中 ${inProgress} · 待开始 ${todoCount} · 逾期 ${overdueCount}`,
      color: "text-amber-300",
      to: "/tasks?status=open",
    },
    {
      label: "参与项目",
      value: stats.projects,
      hint: `${stats.active_projects} 个项目有进行中任务`,
      color: "text-violet-300",
      to: "/projects",
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-[22px] font-semibold text-mist-100">
            <span>👋</span>
            {greeting()}，专注让工作更高效！
          </h1>
          <p className="mt-1.5 text-[12.5px] text-mist-400">
            合理安排 · 按时完成 · 持续进步
          </p>
        </div>
        <button className="btn-primary h-10 px-5" onClick={() => setCreateOpen(true)}>
          <Plus size={17} /> 新建任务
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((card, index) => {
          const style = STAT_STYLES[index];
          const Icon = style.icon;
          return (
            <Link
              key={card.label}
              to={card.to}
              title={`查看${card.label}`}
              className={cn(
                "card group relative block overflow-hidden bg-gradient-to-br p-4 transition duration-200 hover:-translate-y-0.5 hover:border-brand-500/40 hover:shadow-[0_18px_40px_-24px_rgba(91,124,250,0.55)]",
                style.bg,
              )}
            >
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-[12px] text-mist-400">{card.label}</p>
                  <p className="mt-2 flex items-baseline gap-1.5">
                    <span className="text-[30px] font-semibold leading-none text-mist-100">
                      {card.value}
                    </span>
                    <span className="text-[11px] text-mist-500">个</span>
                  </p>
                </div>
                <span
                  className={cn(
                    "flex h-10 w-10 items-center justify-center rounded-xl text-white",
                    style.iconBg,
                    style.glow,
                  )}
                >
                  <Icon size={19} />
                </span>
              </div>
              <div className="mt-3 flex items-center justify-between gap-2">
                <p className={cn("text-[11px]", card.color)}>{card.hint}</p>
                <ArrowUpRight
                  size={13}
                  className="shrink-0 text-mist-500 opacity-0 transition group-hover:opacity-100"
                />
              </div>
            </Link>
          );
        })}
      </div>

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 xl:col-span-7">
          <TaskDonut total={data.donut.total} segments={data.donut.segments} />
        </div>
        <div className="col-span-12 xl:col-span-5">
          <DeadlineList tasks={data.deadlines} />
        </div>
      </div>

      <Card className="p-4">
        <SectionHeader
          title="任务看板"
          subtitle="每列显示前 4 条，拖拽卡片可直接更新状态"
          action={
            <Link
              to="/board"
              className="flex items-center gap-1 text-[11.5px] text-brand-400 transition hover:text-brand-300"
            >
              查看全部 <ArrowUpRight size={13} />
            </Link>
          }
        />
        {board.isLoading || !board.data ? (
          <Skeleton className="h-[260px] w-full" />
        ) : (
          <KanbanBoard
            lanes={board.data.lanes}
            counts={board.data.counts}
            maxPerLane={4}
            compact
            onMove={(id, status) => move.mutate({ id, status })}
          />
        )}
      </Card>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <TodayTasks tasks={data.today_tasks} />
        <WeeklyProgress projects={data.weekly_progress} />
        <ScheduleTimeline items={data.schedule} />
      </div>

      <TaskCreateModal open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  );
}
