import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Check, ChevronRight, ListChecks } from "lucide-react";
import { api } from "../../api/client";
import type { Task } from "../../api/types";
import { cn, formatTime } from "../../lib/format";
import {
  Card,
  EmptyState,
  PriorityBadge,
  SectionHeader,
} from "../ui/primitives";
import { useTaskDrawer } from "../tasks/TaskDrawerContext";

export default function TodayTasks({ tasks }: { tasks: Task[] }) {
  const { openTask } = useTaskDrawer();
  const queryClient = useQueryClient();
  const complete = useMutation({
    mutationFn: (id: number) => api.completeTask(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["board"] });
      toast.success("任务已完成");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  return (
    <Card className="flex h-full flex-col">
      <SectionHeader
        title="今日任务"
        action={
          <Link
            to="/tasks?status=today"
            className="flex items-center gap-1 text-[11px] text-mist-400 transition hover:text-brand-400"
          >
            查看全部 <ChevronRight size={13} />
          </Link>
        }
      />
      {!tasks.length ? (
        <EmptyState
          icon={<ListChecks size={20} />}
          title="今天没有任务"
          description="享受专注的一天，或从收件箱认领一项工作。"
        />
      ) : (
        <div className="space-y-1">
          {tasks.map((task) => (
            <div
              key={task.id}
              className="group flex items-center gap-2.5 rounded-lg px-1 py-2 transition hover:bg-ink-750/60"
            >
              <button
                onClick={() => complete.mutate(task.id)}
                className={cn(
                  "flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-[5px] border transition",
                  task.status === "done"
                    ? "border-emerald-400 bg-emerald-400 text-ink-950"
                    : "border-ink-500 text-transparent hover:border-emerald-400",
                )}
              >
                <Check size={12} strokeWidth={3} />
              </button>
              <button
                onClick={() => openTask(task.id)}
                className={cn(
                  "min-w-0 flex-1 truncate text-left text-[13px] text-mist-200",
                  task.status === "done" && "text-mist-500 line-through",
                )}
              >
                {task.title}
              </button>
              <PriorityBadge priority={task.priority} />
              <span className="w-[38px] shrink-0 text-right text-[11px] text-mist-500">
                {task.due_at ? formatTime(task.due_at) : "—"}
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
