import { useEffect, type ReactNode } from "react";
import { X } from "lucide-react";
import { cn, PRIORITY, STATUS } from "../../lib/format";

export function Card({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <section className={cn("card p-5", className)}>{children}</section>;
}

export function SectionHeader({
  title,
  subtitle,
  action,
  className,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mb-4 flex items-start justify-between gap-3", className)}>
      <div>
        <h2 className="panel-title">{title}</h2>
        {subtitle ? <p className="mt-1 text-xs text-mist-500">{subtitle}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function PriorityBadge({ priority }: { priority: string }) {
  const config = PRIORITY[priority] || PRIORITY.medium;
  return (
    <span className={cn("pill", config.bg, config.text)}>
      <span className={cn("h-1.5 w-1.5 rounded-full", config.dot)} />
      {config.label}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const config = STATUS[status] || STATUS.todo;
  return (
    <span className={cn("pill", config.bg, config.color)}>{config.label}</span>
  );
}

export function ProgressBar({
  value,
  color = "#5B7CFA",
  height = 6,
}: {
  value: number;
  color?: string;
  height?: number;
}) {
  return (
    <div
      className="w-full overflow-hidden rounded-full bg-ink-700/80"
      style={{ height }}
    >
      <div
        className="h-full rounded-full transition-all duration-500"
        style={{
          width: `${Math.max(0, Math.min(100, value))}%`,
          background: `linear-gradient(90deg, ${color}bb, ${color})`,
        }}
      />
    </div>
  );
}

export function Avatar({
  name,
  color = "#5B7CFA",
  size = 28,
}: {
  name?: string | null;
  color?: string | null;
  size?: number;
}) {
  const initial = (name || "我").trim().slice(-1);
  return (
    <span
      className="inline-flex items-center justify-center rounded-full border border-white/10 font-semibold text-white"
      style={{
        width: size,
        height: size,
        background: `linear-gradient(135deg, ${color || "#5B7CFA"}, ${color || "#5B7CFA"}99)`,
        fontSize: size * 0.42,
      }}
      title={name || "我"}
    >
      {initial}
    </span>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
      {icon ? (
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-ink-750 text-mist-400">
          {icon}
        </div>
      ) : null}
      <div>
        <p className="text-sm font-medium text-mist-200">{title}</p>
        {description ? (
          <p className="mt-1 max-w-sm text-xs leading-5 text-mist-500">{description}</p>
        ) : null}
      </div>
      {action}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-xl bg-ink-750/80",
        className,
      )}
    />
  );
}

export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  width = "max-w-lg",
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  width?: string;
}) {
  useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />
      <div
        className={cn(
          "animate-in relative w-full rounded-2xl border border-ink-600 bg-ink-850 p-5 shadow-2xl",
          width,
        )}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-base font-semibold text-mist-100">{title}</h3>
          <button
            className="rounded-lg p-1.5 text-mist-400 transition hover:bg-ink-750 hover:text-mist-100"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </div>
        {children}
        {footer ? <div className="mt-5 flex justify-end gap-2">{footer}</div> : null}
      </div>
    </div>
  );
}

export function Drawer({
  open,
  onClose,
  title,
  children,
  width = "w-[560px]",
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  width?: string;
}) {
  useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/65 backdrop-blur-[2px]" onClick={onClose} />
      <aside
        className={cn(
          "animate-in absolute right-0 top-0 flex h-full max-w-[92vw] flex-col border-l border-ink-600 bg-ink-850 shadow-2xl",
          width,
        )}
      >
        <header className="flex items-center justify-between border-b border-ink-700 px-5 py-4">
          <h3 className="text-base font-semibold text-mist-100">{title}</h3>
          <button
            className="rounded-lg p-1.5 text-mist-400 transition hover:bg-ink-750 hover:text-mist-100"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
      </aside>
    </div>
  );
}

export function Tabs({
  tabs,
  value,
  onChange,
  className,
}: {
  tabs: { key: string; label: string; count?: number }[];
  value: string;
  onChange: (key: string) => void;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap gap-1 rounded-xl bg-ink-900/60 p-1", className)}>
      {tabs.map((tab) => (
        <button
          key={tab.key}
          onClick={() => onChange(tab.key)}
          className={cn(
            "rounded-lg px-3 py-1.5 text-xs font-medium transition",
            value === tab.key
              ? "bg-ink-700 text-mist-100 shadow"
              : "text-mist-400 hover:text-mist-200",
          )}
        >
          {tab.label}
          {typeof tab.count === "number" ? (
            <span className="ml-1.5 rounded bg-ink-600/80 px-1.5 text-[10px] text-mist-300">
              {tab.count}
            </span>
          ) : null}
        </button>
      ))}
    </div>
  );
}
