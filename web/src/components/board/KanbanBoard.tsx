import { useState } from "react";
import { Plus } from "lucide-react";
import type { Task } from "../../api/types";
import { cn } from "../../lib/format";
import TaskCard from "../tasks/TaskCard";
import { useTaskDrawer } from "../tasks/TaskDrawerContext";

const LANES = [
  { key: "todo", label: "待处理", color: "#F59E0B", droppable: true },
  { key: "in_progress", label: "进行中", color: "#4F7DFF", droppable: true },
  { key: "done", label: "已完成", color: "#22C55E", droppable: true },
  { key: "overdue", label: "已逾期", color: "#EF4444", droppable: false },
] as const;

export default function KanbanBoard({
  lanes,
  counts,
  onMove,
  maxPerLane,
  compact = false,
  onCreate,
}: {
  lanes: Record<string, Task[]>;
  counts?: Record<string, number>;
  onMove?: (taskId: number, status: string) => void;
  maxPerLane?: number;
  compact?: boolean;
  onCreate?: (status: string) => void;
}) {
  const { openTask } = useTaskDrawer();
  const [dragging, setDragging] = useState<number | null>(null);
  const [overLane, setOverLane] = useState<string | null>(null);

  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
      {LANES.map((lane) => {
        const items = lanes[lane.key] || [];
        const visible = maxPerLane ? items.slice(0, maxPerLane) : items;
        const count = counts?.[lane.key] ?? items.length;
        return (
          <div
            key={lane.key}
            onDragOver={(event) => {
              if (!lane.droppable || !onMove) return;
              event.preventDefault();
              setOverLane(lane.key);
            }}
            onDragLeave={() => setOverLane((current) => (current === lane.key ? null : current))}
            onDrop={(event) => {
              event.preventDefault();
              setOverLane(null);
              if (!lane.droppable || !onMove) return;
              const id = Number(event.dataTransfer.getData("text/task-id") || dragging);
              if (id) onMove(id, lane.key);
              setDragging(null);
            }}
            className={cn(
              "flex min-h-[240px] flex-col rounded-2xl border border-ink-700/60 bg-ink-850/50 p-3 transition",
              overLane === lane.key && "border-brand-500/60 bg-brand-500/5",
            )}
          >
            <div className="mb-3 flex items-center gap-2 px-0.5">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ background: lane.color, boxShadow: `0 0 12px ${lane.color}88` }}
              />
              <span className="text-[13px] font-semibold text-mist-200">{lane.label}</span>
              <span className="rounded-md bg-ink-700/70 px-1.5 text-[11px] text-mist-400">
                {count}
              </span>
              {onCreate ? (
                <button
                  onClick={() => onCreate(lane.key)}
                  className="ml-auto rounded-md p-1 text-mist-500 transition hover:bg-ink-700 hover:text-mist-200"
                >
                  <Plus size={14} />
                </button>
              ) : null}
            </div>
            <div className="space-y-2.5 overflow-y-auto pr-0.5" style={{ maxHeight: 560 }}>
              {visible.map((task) => (
                <div
                  key={task.id}
                  draggable={Boolean(onMove)}
                  onDragStart={(event) => {
                    setDragging(task.id);
                    event.dataTransfer.setData("text/task-id", String(task.id));
                    event.dataTransfer.effectAllowed = "move";
                  }}
                  onDragEnd={() => setDragging(null)}
                  className={cn(dragging === task.id && "opacity-45")}
                >
                  <TaskCard task={task} compact={compact} onClick={() => openTask(task.id)} />
                </div>
              ))}
              {!visible.length ? (
                <div className="flex h-[92px] items-center justify-center rounded-xl border border-dashed border-ink-700/70 text-[11px] text-mist-600">
                  暂无任务
                </div>
              ) : null}
              {maxPerLane && items.length > maxPerLane ? (
                <p className="pt-1 text-center text-[11px] text-mist-500">
                  还有 {items.length - maxPerLane} 项
                </p>
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}
