import { useMemo, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  BarChart3,
  Bell,
  CalendarDays,
  CheckSquare,
  ChevronLeft,
  ChevronRight,
  Columns3,
  FolderKanban,
  FolderOpen,
  Inbox,
  LayoutDashboard,
  ListTodo,
  Menu,
  RefreshCw,
  Search,
  Settings,
  Sparkles,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api } from "../../api/client";
import { loadPrivateExtensions } from "../../lib/extensions";
import { cn, todayLabel } from "../../lib/format";
import { Avatar } from "../ui/primitives";

type NavItem = {
  to: string;
  label: string;
  icon?: LucideIcon;
  end?: boolean;
  badge?: number;
};

const NAV: NavItem[] = [
  { to: "/", label: "工作台", icon: LayoutDashboard, end: true },
  { to: "/tasks", label: "我的任务", icon: ListTodo },
  { to: "/board", label: "任务看板", icon: Columns3 },
  { to: "/projects", label: "项目管理", icon: FolderKanban },
  { to: "/calendar", label: "日程日历", icon: CalendarDays },
  { to: "/team", label: "团队协作", icon: Users },
  { to: "/stats", label: "统计报表", icon: BarChart3 },
  { to: "/files", label: "文件资料", icon: FolderOpen },
  { to: "/notifications", label: "消息通知", icon: Bell },
  { to: "/settings", label: "设置", icon: Settings },
];

export default function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [keyword, setKeyword] = useState("");

  const refresh = useMutation({
    mutationFn: async () => {
      const check = await api.checkWorkflow(24);
      const extract = await api.runExtract(5);
      return { check, extract };
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries();
      const questions = data.check?.workflow?.intents?.questions || [];
      const sent = questions.filter((item: any) => item.sent).length;
      const failed = questions.filter((item: any) => !item.sent).length;
      if (questions.length) {
        toast.success(
          `发现 ${questions.length} 个新任务，已发送 ${sent} 条飞书确认${
            failed ? `，${failed} 条发送失败，请在候选收件箱处理` : ""
          }`,
        );
      } else if ((data.check?.pending_count ?? 0) > 0) {
        toast.info(
          `工作台有 ${data.check.pending_count} 个待确认任务，请在候选收件箱查看`,
        );
      } else {
        toast.success(
          `已检查最近 24 小时，新增 ${data.check?.sync?.new_messages ?? 0} 条消息，没有发现新任务`,
        );
      }
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const dashboard = useQuery({
    queryKey: ["dashboard"],
    queryFn: api.dashboard,
    refetchInterval: 60_000,
  });
  const notifications = useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: () => api.notifications({ limit: 5 }),
    refetchInterval: 60_000,
  });

  const inboxCount =
    (dashboard.data?.inbox_pending ?? 0) +
    (dashboard.data?.confirmations_pending ?? 0);
  const unread = notifications.data?.unread ?? 0;

  const navItems = useMemo(
    () =>
      [...NAV, ...loadPrivateExtensions().nav].map((item) =>
        item.to === "/notifications" ? { ...item, badge: unread } : item,
      ),
    [unread],
  );

  const submitSearch = (event: React.FormEvent) => {
    event.preventDefault();
    if (!keyword.trim()) return;
    navigate(`/tasks?q=${encodeURIComponent(keyword.trim())}`);
  };

  return (
    <div className="flex min-h-screen">
      {mobileOpen ? (
        <div
          className="fixed inset-0 z-30 bg-black/60 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      ) : null}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-[232px] flex-col border-r border-ink-700/70 bg-ink-900/95 px-3 py-4 backdrop-blur transition-transform lg:static lg:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-center gap-3 px-2 pb-5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-600 shadow-glow">
            <CheckSquare size={21} className="text-white" />
          </div>
          <div className="leading-tight">
            <p className="text-[15px] font-semibold text-mist-100">任务管理</p>
            <p className="text-[11px] tracking-[0.22em] text-mist-500">WORKBENCH</p>
          </div>
        </div>

        <nav className="flex-1 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon || Sparkles;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={() => setMobileOpen(false)}
                className={({ isActive }) =>
                  cn("nav-item", isActive && "nav-item-active")
                }
              >
                <Icon size={18} strokeWidth={1.8} />
                <span className="flex-1">{item.label}</span>
                {item.badge ? (
                  <span className="rounded-full bg-red-500 px-1.5 text-[10px] font-semibold leading-5 text-white">
                    {item.badge > 99 ? "99+" : item.badge}
                  </span>
                ) : null}
                {item.to === "/inbox" ? null : null}
              </NavLink>
            );
          })}
          <NavLink
            to="/inbox"
            onClick={() => setMobileOpen(false)}
            className={({ isActive }) =>
              cn("nav-item", isActive && "nav-item-active")
            }
          >
            <Inbox size={18} strokeWidth={1.8} />
            <span className="flex-1">候选收件箱</span>
            {inboxCount ? (
              <span className="rounded-full bg-amber-400 px-1.5 text-[10px] font-semibold leading-5 text-ink-950">
                {inboxCount > 99 ? "99+" : inboxCount}
              </span>
            ) : null}
          </NavLink>
        </nav>

        <div className="mt-4 rounded-2xl border border-brand-500/20 bg-gradient-to-br from-brand-500/20 via-ink-800 to-ink-850 p-4">
          <Sparkles size={18} className="text-brand-400" />
          <p className="mt-3 text-[13px] font-medium leading-5 text-mist-100">
            高效执行
            <br />
            成就更好的自己
          </p>
          <p className="mt-1 text-[11px] text-mist-500">Hermes · 自动沉淀每一天</p>
        </div>

        <div className="mt-4 flex items-center gap-3 rounded-xl border border-ink-700/70 bg-ink-800/70 px-3 py-2.5">
          <Avatar name="我" color="#5B7CFA" size={32} />
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-medium text-mist-100">我</p>
            <p className="truncate text-[11px] text-mist-500">本地工作台</p>
          </div>
          <ChevronRight size={16} className="text-mist-500" />
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col lg:pl-0">
        <header className="sticky top-0 z-20 flex h-[68px] items-center gap-3 border-b border-ink-700/60 bg-ink-900/80 px-4 backdrop-blur-xl md:px-7">
          <button
            className="rounded-lg p-2 text-mist-300 hover:bg-ink-750 lg:hidden"
            onClick={() => setMobileOpen(true)}
          >
            <Menu size={20} />
          </button>
          <div className="hidden items-center gap-2 text-[12.5px] text-mist-400 sm:flex">
            <span className="font-medium text-mist-200">{todayLabel()}</span>
          </div>

          <form
            onSubmit={submitSearch}
            className="ml-auto flex h-9 w-full max-w-[330px] items-center gap-2 rounded-xl border border-ink-700/80 bg-ink-850/80 px-3 text-mist-400 transition focus-within:border-brand-500/60"
          >
            <Search size={16} />
            <input
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="搜索任务、项目或成员..."
              className="h-full w-full bg-transparent text-[13px] text-mist-100 outline-none placeholder:text-mist-500"
            />
          </form>

          <button
            onClick={() => refresh.mutate()}
            disabled={refresh.isPending}
            title="检查最近 24 小时的新任务"
            className="flex items-center gap-1.5 rounded-xl border border-ink-700/70 bg-ink-850/70 px-2.5 py-2 text-mist-300 transition hover:border-brand-500/40 hover:text-mist-100 disabled:opacity-50"
          >
            <RefreshCw
              size={17}
              className={refresh.isPending ? "animate-spin" : ""}
            />
            <span className="hidden text-[11.5px] sm:inline">检查新任务</span>
          </button>

          <button
            onClick={() => navigate("/notifications")}
            className="relative rounded-xl border border-ink-700/70 bg-ink-850/70 p-2 text-mist-300 transition hover:text-mist-100"
          >
            <Bell size={18} />
            {unread ? (
              <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[9px] font-bold text-white">
                {unread > 9 ? "9+" : unread}
              </span>
            ) : null}
          </button>

          <button
            onClick={() => navigate("/settings")}
            className="flex items-center gap-2 rounded-xl border border-ink-700/70 bg-ink-850/70 py-1 pl-1 pr-2.5 transition hover:border-ink-600"
          >
            <Avatar name="我" color="#5B7CFA" size={28} />
            <span className="hidden text-[13px] text-mist-200 md:block">我</span>
          </button>
        </header>

        <main className="min-w-0 flex-1 px-4 py-5 md:px-7 md:py-6">
          <div className="mx-auto w-full max-w-[1600px]">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
