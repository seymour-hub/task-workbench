import clsx from "clsx";

export const cn = clsx;

export const PRIORITY: Record<
  string,
  { label: string; text: string; bg: string; dot: string }
> = {
  urgent: {
    label: "紧急",
    text: "text-red-300",
    bg: "bg-red-500/15 border border-red-500/25",
    dot: "bg-red-400",
  },
  high: {
    label: "高",
    text: "text-orange-300",
    bg: "bg-orange-500/15 border border-orange-500/25",
    dot: "bg-orange-400",
  },
  medium: {
    label: "中",
    text: "text-sky-300",
    bg: "bg-sky-500/15 border border-sky-500/25",
    dot: "bg-sky-400",
  },
  low: {
    label: "低",
    text: "text-slate-300",
    bg: "bg-slate-500/20 border border-slate-500/25",
    dot: "bg-slate-400",
  },
};

export const STATUS: Record<string, { label: string; color: string; bg: string }> = {
  todo: { label: "待处理", color: "text-amber-300", bg: "bg-amber-500/15" },
  in_progress: { label: "进行中", color: "text-blue-300", bg: "bg-blue-500/15" },
  done: { label: "已完成", color: "text-emerald-300", bg: "bg-emerald-500/15" },
  cancelled: { label: "已取消", color: "text-slate-300", bg: "bg-slate-500/15" },
};

export function dayStart(timestamp?: number | null): number {
  const date = timestamp ? new Date(timestamp * 1000) : new Date();
  date.setHours(0, 0, 0, 0);
  return Math.floor(date.getTime() / 1000);
}

export function isToday(timestamp?: number | null): boolean {
  if (!timestamp) return false;
  const start = dayStart();
  return timestamp >= start && timestamp < start + 86400;
}

export function formatDate(timestamp?: number | null, withTime = false): string {
  if (!timestamp) return "—";
  const date = new Date(timestamp * 1000);
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  if (!withTime) return `${month}-${day}`;
  const hours = `${date.getHours()}`.padStart(2, "0");
  const minutes = `${date.getMinutes()}`.padStart(2, "0");
  return `${month}-${day} ${hours}:${minutes}`;
}

export function formatTime(timestamp?: number | null): string {
  if (!timestamp) return "";
  const date = new Date(timestamp * 1000);
  return `${`${date.getHours()}`.padStart(2, "0")}:${`${date.getMinutes()}`.padStart(2, "0")}`;
}

export function formatDeadline(timestamp?: number | null): {
  text: string;
  tone: string;
} {
  if (!timestamp) return { text: "未设置", tone: "text-mist-500" };
  const now = new Date();
  const date = new Date(timestamp * 1000);
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startTarget = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const days = Math.round((startTarget.getTime() - startToday.getTime()) / 86400000);
  if (days < 0) return { text: `${formatDate(timestamp, true)}（已逾期）`, tone: "text-red-300" };
  if (days === 0)
    return { text: `今天 ${formatTime(timestamp)}`, tone: "text-red-300" };
  if (days === 1)
    return { text: `明天 ${formatTime(timestamp)}`, tone: "text-orange-300" };
  if (days <= 3) return { text: formatDate(timestamp, true), tone: "text-amber-300" };
  return { text: formatDate(timestamp, false), tone: "text-mist-400" };
}

export function toLocalInput(timestamp?: number | null): string {
  if (!timestamp) return "";
  const date = new Date(timestamp * 1000);
  const pad = (value: number) => `${value}`.padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

export function formatBytes(value?: number | null): string {
  if (!value) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let size = value;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

export function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 6) return "凌晨好";
  if (hour < 12) return "上午好";
  if (hour < 14) return "中午好";
  if (hour < 18) return "下午好";
  return "晚上好";
}

export function todayLabel(): string {
  const date = new Date();
  const weekdays = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"];
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日  ${weekdays[date.getDay()]}`;
}

export function timeAgo(timestamp?: number | null): string {
  if (!timestamp) return "—";
  const diff = Date.now() / 1000 - timestamp;
  if (diff < 60) return "刚刚";
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
  if (diff < 86400 * 30) return `${Math.floor(diff / 86400)} 天前`;
  return formatDate(timestamp);
}
