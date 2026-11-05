import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api/client";
import { Card, ProgressBar, Skeleton } from "../components/ui/primitives";
import { cn } from "../lib/format";

const STATUS_COLORS: Record<string, string> = {
  todo: "#F59E0B",
  in_progress: "#4F7DFF",
  done: "#22C55E",
  overdue: "#EF4444",
  cancelled: "#64748B",
};

const STATUS_LABELS: Record<string, string> = {
  todo: "待处理",
  in_progress: "进行中",
  done: "已完成",
  overdue: "已逾期",
  cancelled: "已取消",
};

const tooltipStyle = {
  background: "#0B1426",
  border: "1px solid #24365A",
  borderRadius: 10,
  color: "#E6ECF7",
  fontSize: 12,
};

export default function StatsPage() {
  const [period, setPeriod] = useState("week");
  const stats = useQuery({
    queryKey: ["stats", period],
    queryFn: () => api.stats(period),
  });

  if (stats.isLoading || !stats.data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-56" />
        <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
          {[0, 1, 2, 3].map((item) => (
            <Skeleton key={item} className="h-24 w-full" />
          ))}
        </div>
        <Skeleton className="h-[320px] w-full" />
      </div>
    );
  }

  const data = stats.data;
  const statusData = Object.entries(data.status)
    .filter(([, value]) => value > 0)
    .map(([key, value]) => ({
      key,
      name: STATUS_LABELS[key] || key,
      value,
      color: STATUS_COLORS[key] || "#64748B",
    }));

  const kpis = [
    { label: "完成率", value: `${data.kpi.completion_rate}%`, tone: "text-emerald-300" },
    { label: "平均完成时长", value: `${data.kpi.avg_duration_days} 天`, tone: "text-brand-300" },
    { label: "逾期率", value: `${data.kpi.overdue_rate}%`, tone: "text-red-300" },
    { label: "交付物", value: `${data.kpi.deliverables}`, tone: "text-amber-300" },
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[20px] font-semibold text-mist-100">统计报表</h1>
          <p className="mt-1 text-[12px] text-mist-500">
            从任务、问题与交付物中沉淀出的工作数据。
          </p>
        </div>
        <div className="flex rounded-xl border border-ink-700 bg-ink-900/60 p-0.5">
          {[
            ["week", "本周"],
            ["month", "本月"],
            ["quarter", "本季度"],
          ].map(([key, label]) => (
            <button
              key={key}
              onClick={() => setPeriod(key)}
              className={cn(
                "rounded-lg px-3 py-1.5 text-[12px] transition",
                period === key ? "bg-ink-700 text-mist-100" : "text-mist-400",
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        {kpis.map((item) => (
          <Card key={item.label} className="p-4">
            <p className="text-[12px] text-mist-400">{item.label}</p>
            <p className={cn("mt-2 text-[26px] font-semibold", item.tone)}>{item.value}</p>
            <p className="mt-1 text-[10px] text-mist-600">
              {item.label === "交付物" ? `未解决问题 ${data.kpi.open_issues}` : `本期完成 ${data.kpi.completed} 项`}
            </p>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <h2 className="panel-title mb-4">完成趋势（近 14 天）</h2>
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.trend} margin={{ left: -18, right: 8, top: 8 }}>
                <defs>
                  <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#5B7CFA" stopOpacity={0.5} />
                    <stop offset="100%" stopColor="#5B7CFA" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#1E2A44" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="date" stroke="#6D7E9E" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke="#6D7E9E" fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
                <Tooltip contentStyle={tooltipStyle} />
                <Area
                  type="monotone"
                  dataKey="completed"
                  name="完成数"
                  stroke="#7B96FF"
                  strokeWidth={2}
                  fill="url(#trendFill)"
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <h2 className="panel-title mb-3">状态分布</h2>
          <div className="relative h-[220px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={statusData}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={62}
                  outerRadius={88}
                  paddingAngle={3}
                  stroke="none"
                  isAnimationActive={false}
                >
                  {statusData.map((item) => (
                    <Cell key={item.key} fill={item.color} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-[24px] font-semibold text-mist-100">
                {statusData.reduce((sum, item) => sum + item.value, 0)}
              </span>
              <span className="text-[10px] text-mist-500">任务</span>
            </div>
          </div>
          <div className="space-y-1.5">
            {statusData.map((item) => (
              <div key={item.key} className="flex items-center gap-2 text-[11px]">
                <span className="h-2 w-2 rounded-full" style={{ background: item.color }} />
                <span className="flex-1 text-mist-400">{item.name}</span>
                <span className="text-mist-200">{item.value}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card>
          <h2 className="panel-title mb-3">项目进度</h2>
          <div className="h-[260px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.projects} layout="vertical" margin={{ left: 10, right: 12 }}>
                <CartesianGrid stroke="#1E2A44" strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" domain={[0, 100]} stroke="#6D7E9E" fontSize={11} axisLine={false} tickLine={false} />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={100}
                  stroke="#8A9AB8"
                  fontSize={11}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip contentStyle={tooltipStyle} />
                <Bar
                  dataKey="progress"
                  name="进度"
                  radius={[0, 6, 6, 0]}
                  barSize={14}
                  isAnimationActive={false}
                >
                  {data.projects.map((item) => (
                    <Cell key={item.project_id} fill={item.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <h2 className="panel-title mb-3">成员负荷</h2>
          <div className="space-y-4">
            {data.members.map((member) => {
              const max = Math.max(1, ...data.members.map((item) => item.active));
              return (
                <div key={member.member_id}>
                  <div className="mb-1.5 flex items-center gap-2 text-[12px]">
                    <span className="h-2 w-2 rounded-full" style={{ background: member.color }} />
                    <span className="flex-1 text-mist-300">{member.name}</span>
                    <span className="text-mist-400">{member.active} 项进行中</span>
                    {member.overdue ? (
                      <span className="text-red-300">{member.overdue} 逾期</span>
                    ) : null}
                  </div>
                  <ProgressBar
                    value={(member.active / max) * 100}
                    color={member.color}
                    height={7}
                  />
                </div>
              );
            })}
            {!data.members.length ? (
              <p className="py-8 text-center text-[12px] text-mist-500">暂无成员数据</p>
            ) : null}
          </div>
        </Card>
      </div>
    </div>
  );
}
