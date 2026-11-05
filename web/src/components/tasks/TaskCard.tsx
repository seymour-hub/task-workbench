import {
  CalendarClock,
  CalendarRange,
  MessageSquareWarning,
  Paperclip,
} from "lucide-react";
import type { Task } from "../../api/types";
import { cn, formatDate, formatDeadline, PRIORITY } from "../../lib/format";
import { Avatar, PriorityBadge, ProgressBar } from "../ui/primitives";

export default function TaskCard({
  task,
  onClick,
  compact = false,
  draggable = false,
}: {
  task: Task;
  onClick?: () => void;
  compact?: boolean;
  draggable?: boolean;
}) {
  const deadline = formatDeadline(task.due_at);
  const deadlineTone = task.status === "done" ? "text-mist-500" : deadline.tone;
  const accent = task.overdue
    ? "#EF4444"
    : task.status === "done"
      ? "#22C55E"
      : task.status === "in_progress"
        ? "#4F7DFF"
        : "#F59E0B";
  return (
    <div
      onClick={onClick}
      draggable={draggable}
      className={cn(
        "group cursor-pointer rounded-xl border border-ink-700/70 bg-ink-800/90 p-3.5 transition hover:border-brand-500/40 hover:bg-ink-750/80",
        compact && "p-3",
      )}
      style={{ borderLeft: `3px solid ${accent}` }}
    >
      <div className="flex items-start justify-between gap-2">
        <p
          className={cn(
            "line-clamp-2 text-[13.5px] font-medium leading-5 text-mist-100",
            task.status === "done" && "text-mist-400 line-through",
          )}
        >
          {task.title}
        </p>
        <PriorityBadge priority={task.priority} />
      </div>

      {task.description && !compact ? (
        <p className="mt-2 line-clamp-2 text-[11.5px] leading-4 text-mist-500">
          {task.description}
        </p>
      ) : null}

      {task.status === "in_progress" ? (
        <div className="mt-3">
          <div className="mb-1 flex justify-between text-[10px] text-mist-500">
            <span>进度</span>
            <span>{task.progress}%</span>
          </div>
          <ProgressBar value={task.progress} color={PRIORITY[task.priority]?.dot === "bg-red-400" ? "#EF4444" : "#4F7DFF"} />
        </div>
      ) : null}

      <div className="mt-3 flex items-center gap-3 text-[11px] text-mist-500">
        {task.source_type === "hermes_session" ? (
          <span className="flex items-center gap-1 text-brand-400/80">
            <span className="h-1.5 w-1.5 rounded-full bg-brand-400" /> Hermes
          </span>
        ) : null}
        {task.project_name ? (
          <span className="flex max-w-[110px] items-center gap-1 truncate">
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ background: task.project_color || "#5B7CFA" }}
            />
            <span className="truncate">{task.project_name}</span>
          </span>
        ) : null}
        {task.due_at ? (
          <span className={cn("ml-auto flex items-center gap-1", deadlineTone)}>
            <CalendarClock size={12} />
            {deadline.text}
          </span>
        ) : task.started_at || task.ended_at ? (
          <span className="ml-auto flex items-center gap-1 text-mist-500">
            <CalendarRange size={12} />
            {formatDate(task.started_at)} → {formatDate(task.ended_at)}
          </span>
        ) : null}
      </div>

      <div className="mt-3 flex items-center gap-2 border-t border-ink-700/50 pt-2.5">
        {task.issue_count ? (
          <span className="flex items-center gap-1 text-[10.5px] text-amber-300/80">
            <MessageSquareWarning size={12} /> {task.issue_count}
          </span>
        ) : null}
        {task.deliverable_count ? (
          <span className="flex items-center gap-1 text-[10.5px] text-emerald-300/80">
            <Paperclip size={12} /> {task.deliverable_count}
          </span>
        ) : null}
        <div className="ml-auto">
          <Avatar
            name={task.assignee_name || "我"}
            color={task.assignee_color || "#5B7CFA"}
            size={22}
          />
        </div>
      </div>
    </div>
  );
}
