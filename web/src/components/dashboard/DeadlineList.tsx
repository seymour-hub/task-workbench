import { Link } from "react-router-dom";
import { CalendarClock, ChevronRight } from "lucide-react";
import type { Task } from "../../api/types";
import { formatDeadline } from "../../lib/format";
import {
  Card,
  EmptyState,
  PriorityBadge,
  SectionHeader,
} from "../ui/primitives";
import { useTaskDrawer } from "../tasks/TaskDrawerContext";

export default function DeadlineList({ tasks }: { tasks: Task[] }) {
  const { openTask } = useTaskDrawer();
  return (
    <Card className="flex h-full flex-col">
      <SectionHeader
        title="近期截止任务"
        action={
          <Link
            to="/tasks"
            className="flex items-center gap-1 text-[11px] text-mist-400 transition hover:text-brand-400"
          >
            查看任务 <ChevronRight size={13} />
          </Link>
        }
      />
      {!tasks.length ? (
        <EmptyState
          icon={<CalendarClock size={20} />}
          title="近期没有截止任务"
          description="任务到期前会在这里提醒你。"
        />
      ) : (
        <div className="-mx-2 flex-1 space-y-1">
          {tasks.map((task) => {
            const deadline = formatDeadline(task.due_at);
            return (
              <button
                key={task.id}
                onClick={() => openTask(task.id)}
                className="flex w-full items-center gap-3 rounded-lg px-2 py-2.5 text-left transition hover:bg-ink-750/70"
              >
                <PriorityBadge priority={task.priority} />
                <span className="min-w-0 flex-1 truncate text-[13px] text-mist-200">
                  {task.title}
                </span>
                <span className={`shrink-0 text-[11px] ${deadline.tone}`}>
                  {deadline.text}
                </span>
                <ChevronRight size={14} className="shrink-0 text-mist-600" />
              </button>
            );
          })}
        </div>
      )}
    </Card>
  );
}
