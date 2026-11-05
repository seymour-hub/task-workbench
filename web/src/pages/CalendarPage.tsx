import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ChevronLeft, ChevronRight, Plus, Trash2 } from "lucide-react";
import { api } from "../api/client";
import type { CalendarItem } from "../api/types";
import { useTaskDrawer } from "../components/tasks/TaskDrawerContext";
import { Card, EmptyState, Modal, Skeleton } from "../components/ui/primitives";
import { cn, formatTime, toLocalInput } from "../lib/format";

const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];
const COLORS = ["#5B7CFA", "#22C55E", "#F59E0B", "#EF4444", "#8B5CF6", "#06B6D4"];

function startOfMonth(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function monthDays(month: Date): Date[] {
  const first = startOfMonth(month);
  const offset = (first.getDay() + 6) % 7;
  const start = new Date(first);
  start.setDate(first.getDate() - offset);
  return Array.from({ length: 42 }, (_, index) => {
    const day = new Date(start);
    day.setDate(start.getDate() + index);
    return day;
  });
}

function dayRange(day: Date): [number, number] {
  const start = new Date(day.getFullYear(), day.getMonth(), day.getDate());
  const end = new Date(start);
  end.setDate(start.getDate() + 1);
  return [start.getTime() / 1000, end.getTime() / 1000];
}

export default function CalendarPage() {
  const [month, setMonth] = useState(startOfMonth(new Date()));
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [title, setTitle] = useState("");
  const [date, setDate] = useState("");
  const [startTime, setStartTime] = useState("09:00");
  const [endTime, setEndTime] = useState("10:00");
  const [location, setLocation] = useState("");
  const [color, setColor] = useState(COLORS[0]);
  const { openTask } = useTaskDrawer();
  const queryClient = useQueryClient();

  const days = useMemo(() => monthDays(month), [month]);
  const rangeStart = Math.floor(days[0].getTime() / 1000);
  const rangeEnd = Math.floor(days[days.length - 1].getTime() / 1000) + 86400;

  const events = useQuery({
    queryKey: ["calendar", rangeStart, rangeEnd],
    queryFn: () => api.calendar(rangeStart, rangeEnd),
  });

  const byDay = useMemo(() => {
    const map = new Map<string, CalendarItem[]>();
    (events.data?.items || []).forEach((item) => {
      const key = new Date(item.start_at * 1000).toDateString();
      const list = map.get(key) || [];
      list.push(item);
      map.set(key, list);
    });
    return map;
  }, [events.data]);

  const create = useMutation({
    mutationFn: () => {
      const start = new Date(`${date}T${startTime}:00`);
      const end = new Date(`${date}T${endTime}:00`);
      const payload = {
        title,
        start_at: start.getTime() / 1000,
        end_at: end.getTime() / 1000,
        location: location || null,
        color,
      };
      return editingId
        ? api.updateEvent(editingId, payload)
        : api.createEvent(payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["calendar"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success(editingId ? "日程已更新" : "日程已创建");
      setOpen(false);
      setEditingId(null);
      setTitle("");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const remove = useMutation({
    mutationFn: () => api.deleteEvent(editingId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["calendar"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success("日程已删除");
      setOpen(false);
      setEditingId(null);
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const openCreate = (day?: Date) => {
    const target = day || new Date();
    const value = `${target.getFullYear()}-${`${target.getMonth() + 1}`.padStart(2, "0")}-${`${target.getDate()}`.padStart(2, "0")}`;
    setEditingId(null);
    setTitle("");
    setDate(value);
    setStartTime("09:00");
    setEndTime("10:00");
    setLocation("");
    setColor(COLORS[0]);
    setOpen(true);
  };

  const openEdit = (item: CalendarItem) => {
    if (!item.event_id) return;
    const start = toLocalInput(item.start_at);
    const end = item.end_at ? toLocalInput(item.end_at) : start;
    setEditingId(item.event_id);
    setTitle(item.title);
    setDate(start.slice(0, 10));
    setStartTime(start.slice(11, 16));
    setEndTime(end.slice(11, 16));
    setLocation(item.location || "");
    setColor(item.color);
    setOpen(true);
  };

  const todayKey = new Date().toDateString();

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[20px] font-semibold text-mist-100">日程日历</h1>
          <p className="mt-1 text-[12px] text-mist-500">
            任务截止时间自动显示为红色事件；手动日程可点击日期创建。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="btn-ghost h-9 px-2.5"
            onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}
          >
            <ChevronLeft size={16} />
          </button>
          <span className="min-w-[110px] text-center text-[14px] font-medium text-mist-100">
            {month.getFullYear()} 年 {month.getMonth() + 1} 月
          </span>
          <button
            className="btn-ghost h-9 px-2.5"
            onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))}
          >
            <ChevronRight size={16} />
          </button>
          <button className="btn-ghost h-9" onClick={() => setMonth(startOfMonth(new Date()))}>
            今天
          </button>
          <button className="btn-primary h-9" onClick={() => openCreate()}>
            <Plus size={15} /> 新建日程
          </button>
        </div>
      </div>

      <Card className="p-3">
        <div className="grid grid-cols-7 border-b border-ink-700/60 pb-2 text-center text-[11px] text-mist-500">
          {WEEKDAYS.map((day) => (
            <div key={day}>周{day}</div>
          ))}
        </div>
        {events.isLoading ? (
          <Skeleton className="mt-3 h-[520px] w-full" />
        ) : (
          <div className="grid grid-cols-7">
            {days.map((day) => {
              const key = day.toDateString();
              const items = byDay.get(key) || [];
              const inMonth = day.getMonth() === month.getMonth();
              const isToday = key === todayKey;
              return (
                <button
                  key={key}
                  onClick={() => openCreate(day)}
                  className={cn(
                    "min-h-[112px] border-b border-r border-ink-700/40 p-1.5 text-left transition hover:bg-ink-750/40",
                    !inMonth && "opacity-40",
                  )}
                >
                  <span
                    className={cn(
                      "inline-flex h-6 w-6 items-center justify-center rounded-full text-[11px]",
                      isToday ? "bg-brand-500 font-semibold text-white" : "text-mist-400",
                    )}
                  >
                    {day.getDate()}
                  </span>
                  <div className="mt-1 space-y-1">
                    {items.slice(0, 3).map((item) => (
                      <div
                        key={item.id}
                        onClick={(event) => {
                          event.stopPropagation();
                          if (item.task_id) openTask(item.task_id);
                          else if (item.source === "manual") openEdit(item);
                        }}
                        className="flex items-center gap-1.5 truncate rounded bg-ink-900/60 px-1.5 py-0.5 text-[10.5px] text-mist-300"
                      >
                        <span
                          className="h-1.5 w-1.5 shrink-0 rounded-full"
                          style={{ background: item.color }}
                        />
                        <span className="truncate">
                          {formatTime(item.start_at)} {item.title}
                        </span>
                      </div>
                    ))}
                    {items.length > 3 ? (
                      <p className="pl-1 text-[10px] text-mist-500">还有 {items.length - 3} 项</p>
                    ) : null}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </Card>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editingId ? "编辑日程" : "新建日程"}
        footer={
          <>
            {editingId ? (
              <button
                className="btn-danger mr-auto"
                onClick={() => remove.mutate()}
                disabled={remove.isPending}
              >
                <Trash2 size={14} /> 删除
              </button>
            ) : null}
            <button className="btn-ghost" onClick={() => setOpen(false)}>
              取消
            </button>
            <button
              className="btn-primary"
              disabled={!title.trim() || !date || create.isPending}
              onClick={() => create.mutate()}
            >
              {editingId ? "保存" : "创建"}
            </button>
          </>
        }
      >
        <div className="space-y-3">
          <label className="block text-xs text-mist-400">
            标题
            <input
              autoFocus
              className="input mt-1"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="例如：项目周会"
            />
          </label>
          <div className="grid grid-cols-3 gap-3">
            <label className="block text-xs text-mist-400">
              日期
              <input
                type="date"
                className="input mt-1"
                value={date}
                onChange={(event) => setDate(event.target.value)}
              />
            </label>
            <label className="block text-xs text-mist-400">
              开始
              <input
                type="time"
                className="input mt-1"
                value={startTime}
                onChange={(event) => setStartTime(event.target.value)}
              />
            </label>
            <label className="block text-xs text-mist-400">
              结束
              <input
                type="time"
                className="input mt-1"
                value={endTime}
                onChange={(event) => setEndTime(event.target.value)}
              />
            </label>
          </div>
          <label className="block text-xs text-mist-400">
            地点
            <input
              className="input mt-1"
              value={location}
              onChange={(event) => setLocation(event.target.value)}
              placeholder="会议室 / 线上"
            />
          </label>
          <div className="text-xs text-mist-400">
            颜色
            <div className="mt-2 flex gap-2">
              {COLORS.map((item) => (
                <button
                  key={item}
                  onClick={() => setColor(item)}
                  className={cn(
                    "h-7 w-7 rounded-full border-2 transition",
                    color === item ? "border-white" : "border-transparent",
                  )}
                  style={{ background: item }}
                />
              ))}
            </div>
          </div>
        </div>
      </Modal>

      {!events.data?.items.length && !events.isLoading ? (
        <EmptyState title="这个月还没有日程" description="点击任意日期即可创建。" />
      ) : null}
    </div>
  );
}
