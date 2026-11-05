import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Bell,
  Check,
  CheckCheck,
  RefreshCw,
  Send,
  Settings2,
  TriangleAlert,
} from "lucide-react";
import { api } from "../api/client";
import {
  Card,
  EmptyState,
  Skeleton,
  Tabs,
} from "../components/ui/primitives";
import { cn, formatDate } from "../lib/format";

const KIND_LABEL: Record<string, string> = {
  digest: "每日摘要",
  due: "到期提醒",
  overdue: "逾期提醒",
  weekly: "周报",
  test: "测试通知",
  sync: "同步异常",
  extract: "抽取异常",
};

export default function NotificationsPage() {
  const [tab, setTab] = useState("all");
  const [expanded, setExpanded] = useState<number | null>(null);
  const autoMarked = useRef(false);
  const queryClient = useQueryClient();

  const notifications = useQuery({
    queryKey: ["notifications", tab],
    queryFn: () => api.notifications(tab === "all" ? {} : { status: tab }),
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["notifications"] });

  const test = useMutation({
    mutationFn: () => api.testNotification(),
    onSuccess: (result) => {
      invalidate();
      if (result.ok) toast.success("测试通知已发送到飞书");
      else toast.error(result.error || "发送失败");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const digest = useMutation({
    mutationFn: () => api.sendDigest(),
    onSuccess: (result) => {
      invalidate();
      if (result.ok) toast.success("日报已发送");
      else if (result.deduplicated) toast.info("今天的日报已经发送过");
      else toast.error(result.error || "发送失败");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const retry = useMutation({
    mutationFn: (id: number) => api.retryNotification(id),
    onSuccess: () => {
      invalidate();
      toast.success("已重试");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const readAll = useMutation({
    mutationFn: () => api.markAllRead(),
    onSuccess: () => {
      invalidate();
      toast.success("已全部标记为已读");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const markOne = useMutation({
    mutationFn: (id: number) => api.markRead(id),
    onSuccess: () => invalidate(),
    onError: (error: Error) => toast.error(error.message),
  });

  const autoRead = useMutation({
    mutationFn: () => api.markAllRead(),
    onSuccess: () => invalidate(),
  });

  useEffect(() => {
    if (autoMarked.current) return;
    if ((notifications.data?.unread ?? 0) <= 0) return;
    autoMarked.current = true;
    autoRead.mutate();
  }, [notifications.data?.unread]);

  const items = notifications.data?.items || [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[20px] font-semibold text-mist-100">消息通知</h1>
          <p className="mt-1 text-[12px] text-mist-500">
            日报、到期与逾期提醒统一通过 Hermes 的飞书通道发送；所有记录可追溯、可重试。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button className="btn-ghost h-9" onClick={() => readAll.mutate()}>
            <CheckCheck size={14} /> 全部已读
          </button>
          <button className="btn-ghost h-9" onClick={() => digest.mutate()}>
            <Send size={14} /> 发送日报
          </button>
          <button className="btn-primary h-9" onClick={() => test.mutate()}>
            <Bell size={14} /> 测试通知
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        {[
          ["消息总数", items.length, "text-mist-100"],
          ["发送成功", items.filter((item) => item.status === "sent").length, "text-emerald-300"],
          ["发送失败", items.filter((item) => item.status === "failed").length, "text-red-300"],
          ["未读", notifications.data?.unread ?? 0, "text-amber-300"],
        ].map(([label, value, tone]) => (
          <Card key={String(label)} className="p-4">
            <p className="text-[11.5px] text-mist-400">{label}</p>
            <p className={cn("mt-1.5 text-[24px] font-semibold", tone)}>{value}</p>
          </Card>
        ))}
      </div>

      <Card className="p-4">
        <div className="flex items-center justify-between gap-2">
          <Tabs
            value={tab}
            onChange={setTab}
            tabs={[
              { key: "all", label: "全部" },
              { key: "sent", label: "已发送" },
              { key: "failed", label: "失败" },
              { key: "pending", label: "待发送" },
            ]}
          />
          <button
            className="flex items-center gap-1 text-[11px] text-mist-400 hover:text-mist-100"
            onClick={() => window.location.assign("/settings")}
          >
            <Settings2 size={13} /> 通知设置
          </button>
        </div>

        <div className="mt-4 space-y-2">
          {notifications.isLoading ? (
            [0, 1, 2, 3].map((item) => <Skeleton key={item} className="h-16 w-full" />)
          ) : !items.length ? (
            <EmptyState
              icon={<Bell size={20} />}
              title="还没有通知记录"
              description="点击“测试通知”验证飞书通道；之后日报和提醒会自动出现在这里。"
            />
          ) : (
            items.map((item) => (
              <div
                key={item.id}
                className={cn(
                  "rounded-xl border border-ink-700/60 bg-ink-900/40 p-3.5 transition",
                  item.read_at === null && "border-brand-500/25",
                )}
              >
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      "flex h-8 w-8 items-center justify-center rounded-lg",
                      item.status === "failed"
                        ? "bg-red-500/10 text-red-300"
                        : "bg-brand-500/10 text-brand-300",
                    )}
                  >
                    {item.status === "failed" ? <TriangleAlert size={15} /> : <Bell size={15} />}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="flex items-center gap-2 text-[13px] font-medium text-mist-100">
                      {item.read_at === null ? (
                        <span
                          className="h-1.5 w-1.5 shrink-0 rounded-full bg-brand-400"
                          title="未读"
                        />
                      ) : null}
                      {item.title}
                      <span className="pill bg-ink-750 text-mist-400">
                        {KIND_LABEL[item.kind] || item.kind}
                      </span>
                      <span
                        className={cn(
                          "pill",
                          item.status === "sent"
                            ? "bg-emerald-500/10 text-emerald-300"
                            : item.status === "failed"
                              ? "bg-red-500/10 text-red-300"
                              : "bg-amber-500/10 text-amber-300",
                        )}
                      >
                        {item.status === "sent" ? "已发送" : item.status === "failed" ? "失败" : "待发送"}
                      </span>
                    </p>
                    <p className="mt-0.5 line-clamp-1 text-[11px] text-mist-500">
                      {item.body}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <span className="text-[10.5px] text-mist-600">
                      {formatDate(item.created_at, true)}
                    </span>
                    {item.read_at === null ? (
                      <button
                        className="rounded px-2 py-1 text-[11px] text-brand-300 transition hover:bg-ink-750"
                        onClick={() => markOne.mutate(item.id)}
                      >
                        <Check size={12} className="inline" /> 标为已读
                      </button>
                    ) : null}
                    <button
                      className="rounded px-2 py-1 text-[11px] text-mist-400 transition hover:bg-ink-750 hover:text-mist-100"
                      onClick={() => {
                        if (item.read_at === null) markOne.mutate(item.id);
                        setExpanded(expanded === item.id ? null : item.id);
                      }}
                    >
                      {expanded === item.id ? "收起" : "详情"}
                    </button>
                    {item.status === "failed" ? (
                      <button
                        className="rounded px-2 py-1 text-[11px] text-brand-300 transition hover:bg-ink-750"
                        onClick={() => retry.mutate(item.id)}
                      >
                        <RefreshCw size={12} className="inline" /> 重试
                      </button>
                    ) : null}
                  </div>
                </div>
                {expanded === item.id ? (
                  <div className="mt-3 rounded-lg bg-ink-950/50 p-3">
                    <pre className="whitespace-pre-wrap break-words font-sans text-[12px] leading-5 text-mist-300">
                      {item.body}
                    </pre>
                    {item.last_error ? (
                      <p className="mt-2 text-[11px] text-red-300">
                        错误：{item.last_error}（尝试 {item.attempts} 次）
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ))
          )}
        </div>
      </Card>
    </div>
  );
}
