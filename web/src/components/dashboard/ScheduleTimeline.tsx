import { Link } from "react-router-dom";
import { CalendarDays, ChevronRight, MapPin } from "lucide-react";
import type { DashboardSummary } from "../../api/types";
import { formatTime } from "../../lib/format";
import { Card, EmptyState, SectionHeader } from "../ui/primitives";
import { useTaskDrawer } from "../tasks/TaskDrawerContext";

export default function ScheduleTimeline({
  items,
}: {
  items: DashboardSummary["schedule"];
}) {
  const { openTask } = useTaskDrawer();
  return (
    <Card className="flex h-full flex-col">
      <SectionHeader
        title="我的日程"
        action={
          <Link
            to="/calendar"
            className="flex items-center gap-1 text-[11px] text-mist-400 transition hover:text-brand-400"
          >
            日历视图 <ChevronRight size={13} />
          </Link>
        }
      />
      {!items.length ? (
        <EmptyState
          icon={<CalendarDays size={20} />}
          title="今天没有安排"
          description="任务截止时间和手动日程会显示在这里。"
        />
      ) : (
        <div className="relative space-y-0">
          {items.map((item, index) => (
            <button
              key={item.id}
              onClick={() => item.task_id && openTask(item.task_id)}
              className="group flex w-full gap-3 text-left"
            >
              <span className="w-[42px] shrink-0 pt-1 text-right text-[11px] text-mist-500">
                {formatTime(item.start_at)}
              </span>
              <span className="relative flex w-3 shrink-0 justify-center">
                <span
                  className="absolute top-1.5 z-10 h-2.5 w-2.5 rounded-full ring-4 ring-ink-800"
                  style={{ background: item.color }}
                />
                {index < items.length - 1 ? (
                  <span className="absolute top-2 h-full w-px bg-ink-600/80" />
                ) : null}
              </span>
              <span className="min-w-0 flex-1 border-b border-ink-700/40 pb-4">
                <span className="block truncate text-[13px] text-mist-200 transition group-hover:text-mist-100">
                  {item.title}
                </span>
                <span className="mt-0.5 flex items-center gap-1 text-[11px] text-mist-500">
                  {item.location ? (
                    <>
                      <MapPin size={11} /> {item.location}
                    </>
                  ) : item.kind === "deadline" ? (
                    "任务截止"
                  ) : (
                    "日程"
                  )}
                </span>
              </span>
            </button>
          ))}
        </div>
      )}
    </Card>
  );
}
