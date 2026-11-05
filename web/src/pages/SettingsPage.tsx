import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  BellRing,
  CheckCircle2,
  Database,
  Download,
  HardDrive,
  Play,
  RefreshCw,
  Save,
  Sparkles,
  XCircle,
  Zap,
} from "lucide-react";
import { api } from "../api/client";
import {
  Card,
  SectionHeader,
  Skeleton,
} from "../components/ui/primitives";
import { cn, formatDate } from "../lib/format";

const GROUP_TITLES: Record<string, string> = {
  ui: "常规设置",
  sync: "同步设置",
  extract: "抽取设置",
  ai: "模型设置",
  notify: "飞书通知",
  files: "文件扫描",
};

const FIELDS = {
  ui: [
    ["ui.display_name", "显示名称", "text"],
    ["ui.timezone", "时区", "text"],
    ["work.start", "工作开始时间", "time"],
    ["work.end", "工作结束时间", "time"],
  ],
  sync: [
    ["sync.enabled", "启用自动同步", "bool"],
    ["sync.interval_sec", "同步间隔（秒）", "number"],
    ["sync.backfill_days", "首次回填天数", "number"],
  ],
  extract: [
    ["extract.enabled", "启用 AI 抽取", "bool"],
    ["extract.sources", "只抽取这些来源（逗号分隔）", "text"],
    ["extract.window_days", "抽取时间窗（天）", "number"],
    ["extract.daily_token_budget", "每日 token 预算", "number"],
    ["extract.auto_accept_threshold", "自动接受阈值（0=关闭）", "number"],
  ],
  ai: [
    ["ai.enabled", "允许发送片段到模型", "bool"],
    ["ai.base_url", "OpenAI 兼容 Base URL", "text"],
    ["ai.model", "模型名称", "text"],
  ],
  notify: [
    ["notify.enabled", "启用飞书通知", "bool"],
    ["notify.target", "飞书目标（feishu:chat_id）", "text"],
    ["notify.digest_time", "日报时间", "time"],
    ["notify.due_time", "到期提醒时间", "time"],
    ["notify.overdue_time", "逾期提醒时间", "time"],
    ["notify.weekly_time", "周报时间", "time"],
    ["notify.weekly_day", "周报星期（0=周一）", "number"],
  ],
  files: [
    ["files.scan_interval_min", "扫描间隔（分钟）", "number"],
    ["files.max_files_per_root", "单路径文件上限", "number"],
  ],
} as const;

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<Record<string, string>>({});

  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const health = useQuery({ queryKey: ["settings-health"], queryFn: api.settingsHealth });
  const sync = useQuery({ queryKey: ["sync-status"], queryFn: api.syncStatus, refetchInterval: 30_000 });
  const usage = useQuery({ queryKey: ["ai-usage"], queryFn: api.aiUsage, refetchInterval: 60_000 });

  useEffect(() => {
    if (settings.data) setForm(settings.data.settings);
  }, [settings.data]);

  const set = (key: string, value: string) =>
    setForm((current) => ({ ...current, [key]: value }));

  const save = useMutation({
    mutationFn: () => api.updateSettings(form),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      queryClient.invalidateQueries({ queryKey: ["settings-health"] });
      toast.success("设置已保存");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const runSync = useMutation({
    mutationFn: () => api.runSync({}),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["sync-status"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      if (result.ok) toast.success(`同步完成，新增 ${result.new_messages} 条消息`);
      else toast.error(result.error || "同步失败");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const runExtract = useMutation({
    mutationFn: () => api.runExtract(5),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["sync-status"] });
      queryClient.invalidateQueries({ queryKey: ["ai-usage"] });
      queryClient.invalidateQueries({ queryKey: ["inbox"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      if (result.ok) toast.success(`抽取完成：处理 ${result.processed} 个片段`);
      else toast.error(result.error || "抽取失败");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const test = useMutation({
    mutationFn: () => api.testNotification(),
    onSuccess: (result) => {
      if (result.ok) toast.success("测试通知已发送到飞书");
      else toast.error(result.error || "发送失败");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const backup = useMutation({
    mutationFn: () => api.backup(),
    onSuccess: (result) => toast.success(`已备份到 ${result.path}`),
    onError: (error: Error) => toast.error(error.message),
  });

  if (settings.isLoading || !settings.data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-[420px] w-full" />
      </div>
    );
  }

  const healthData = health.data || {};
  const checks = [
    ["Hermes 源库", healthData.hermes_db_exists, healthData.hermes_db],
    ["DeepSeek Key", healthData.deepseek_key_present, "读取自 Hermes .env"],
    ["Hermes 可执行", healthData.hermes_bin_exists, healthData.hermes_bin],
    ["飞书推送目标", Boolean(healthData.feishu_target), healthData.feishu_target || "未检测到"],
  ] as const;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[20px] font-semibold text-mist-100">设置</h1>
          <p className="mt-1 text-[12px] text-mist-500">
            数据源、同步、AI 抽取与飞书通知的统一配置入口。
          </p>
        </div>
        <button className="btn-primary" onClick={() => save.mutate()} disabled={save.isPending}>
          <Save size={15} /> 保存设置
        </button>
      </div>

      <Card>
        <SectionHeader title="系统健康" subtitle="关键依赖的实时检查结果" />
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {checks.map(([label, ok, detail]) => (
            <div key={String(label)} className="rounded-xl border border-ink-700/60 bg-ink-900/40 p-3">
              <div className="flex items-center gap-2">
                {ok ? (
                  <CheckCircle2 size={15} className="text-emerald-400" />
                ) : (
                  <XCircle size={15} className="text-red-400" />
                )}
                <span className="text-[12px] font-medium text-mist-200">{label}</span>
              </div>
              <p className="mt-2 truncate text-[10.5px] text-mist-500" title={String(detail || "")}>
                {detail || "—"}
              </p>
            </div>
          ))}
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3 text-[11px] text-mist-500 sm:grid-cols-4">
          <span>任务 {healthData.tasks ?? 0}</span>
          <span>消息 {healthData.messages_cached ?? 0}</span>
          <span>文件 {healthData.files_indexed ?? 0}</span>
          <span>交付物 {healthData.deliverables ?? 0}</span>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card>
          <SectionHeader
            title="数据同步"
            subtitle="只读读取 Hermes state.db，不写入源库"
            action={
              <button className="btn-ghost h-8 px-2.5 text-[11px]" onClick={() => runSync.mutate()}>
                <RefreshCw size={13} /> 立即同步
              </button>
            }
          />
          {sync.isLoading || !sync.data ? (
            <Skeleton className="h-32 w-full" />
          ) : (
            <>
              <div className="grid grid-cols-2 gap-2 text-[11.5px]">
                {[
                  ["源库消息", sync.data.source_messages],
                  ["已缓存消息", sync.data.cached_messages],
                  ["会话", sync.data.cached_sessions],
                  ["待抽取（时间窗内）", sync.data.segments_pending_window],
                  ["已抽取片段", sync.data.segments_done],
                  ["抽取失败", sync.data.segments_failed],
                ].map(([label, value]) => (
                  <div key={String(label)} className="flex justify-between rounded-lg bg-ink-900/40 px-3 py-2">
                    <span className="text-mist-500">{label}</span>
                    <span className="text-mist-200">{value}</span>
                  </div>
                ))}
              </div>
              <p className="mt-2 text-[10.5px] text-mist-600">
                最近同步：{sync.data.last_sync_at ? formatDate(Number(sync.data.last_sync_at), true) : "从未"}
                {sync.data.last_sync_error ? ` · 错误：${sync.data.last_sync_error}` : ""}
                {sync.data.segments_pending > sync.data.segments_pending_window
                  ? ` · 另有 ${sync.data.segments_pending - sync.data.segments_pending_window} 个窗口外或非飞书来源片段未抽取`
                  : ""}
              </p>
            </>
          )}
        </Card>

        <Card>
          <SectionHeader
            title="AI 抽取"
            subtitle="候选先入收件箱，人工确认后才进入看板"
            action={
              <button
                className="btn-ghost h-8 px-2.5 text-[11px]"
                onClick={() => runExtract.mutate()}
                disabled={runExtract.isPending}
              >
                <Zap size={13} /> 立即抽取
              </button>
            }
          />
          <div className="grid grid-cols-3 gap-2 text-center text-[11.5px]">
            <div className="rounded-lg bg-ink-900/40 py-3">
              <p className="text-[18px] font-semibold text-mist-100">{usage.data?.today.calls ?? 0}</p>
              <p className="text-[10px] text-mist-500">今日调用</p>
            </div>
            <div className="rounded-lg bg-ink-900/40 py-3">
              <p className="text-[18px] font-semibold text-mist-100">
                {(usage.data?.today.prompt ?? 0) + (usage.data?.today.completion ?? 0)}
              </p>
              <p className="text-[10px] text-mist-500">已用 token</p>
            </div>
            <div className="rounded-lg bg-ink-900/40 py-3">
              <p className="text-[18px] font-semibold text-mist-100">{usage.data?.budget ?? 0}</p>
              <p className="text-[10px] text-mist-500">每日预算</p>
            </div>
          </div>
          <p className="mt-3 flex items-center gap-1.5 text-[11px] text-mist-500">
            <Sparkles size={13} className="text-brand-400" />
            默认使用 DeepSeek（密钥读取自 Hermes .env，不落库）。关闭“允许发送片段到模型”即可停用外发。
          </p>
          <div className="mt-3 flex gap-2">
            <button className="btn-ghost h-8 text-[11px]" onClick={() => test.mutate()}>
              <BellRing size={13} /> 测试飞书通知
            </button>
            <button className="btn-ghost h-8 text-[11px]" onClick={() => backup.mutate()}>
              <Download size={13} /> 备份数据库
            </button>
          </div>
        </Card>
      </div>

      {Object.entries(FIELDS).map(([group, fields]) => (
        <Card key={group}>
          <SectionHeader title={GROUP_TITLES[group] || group} />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {fields.map(([key, label, type]) => (
              <label key={key} className="block text-[11.5px] text-mist-400">
                {type === "bool" ? (
                  <span className="flex h-9 items-center gap-2">
                    <input
                      type="checkbox"
                      checked={form[key] === "true"}
                      onChange={(event) => set(key, event.target.checked ? "true" : "false")}
                    />
                    {label}
                  </span>
                ) : (
                  <>
                    {label}
                    <input
                      type={type}
                      className="input mt-1 h-9"
                      value={form[key] ?? ""}
                      onChange={(event) => set(key, event.target.value)}
                    />
                  </>
                )}
              </label>
            ))}
          </div>
        </Card>
      ))}

      <Card className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2 text-[12px] text-mist-400">
          <Database size={15} /> 数据库：{healthData.workbench_db || "—"}
        </div>
        <div className="flex items-center gap-2 text-[12px] text-mist-400">
          <HardDrive size={15} /> Hermes Home：{healthData.hermes_home || "—"}
        </div>
        <div className="ml-auto flex items-center gap-2 text-[11px] text-mist-600">
          <Play size={12} /> v0.1.0 · 本地单用户
        </div>
      </Card>
    </div>
  );
}
