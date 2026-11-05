import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowUpRight, FolderKanban, Plus } from "lucide-react";
import { api } from "../api/client";
import {
  Card,
  EmptyState,
  Modal,
  ProgressBar,
  Skeleton,
} from "../components/ui/primitives";
import { cn } from "../lib/format";

const COLORS = ["#5B7CFA", "#22C55E", "#F59E0B", "#EF4444", "#8B5CF6", "#06B6D4", "#EC4899"];

export default function ProjectsPage() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [color, setColor] = useState(COLORS[0]);
  const queryClient = useQueryClient();

  const projects = useQuery({ queryKey: ["projects"], queryFn: api.projects });

  const create = useMutation({
    mutationFn: () => api.createProject({ name, description, color }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success("项目已创建");
      setOpen(false);
      setName("");
      setDescription("");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[20px] font-semibold text-mist-100">项目管理</h1>
          <p className="mt-1 text-[12px] text-mist-500">
            按项目聚合任务、问题与交付物，看清每个方向的推进情况。
          </p>
        </div>
        <button className="btn-primary" onClick={() => setOpen(true)}>
          <Plus size={16} /> 新建项目
        </button>
      </div>

      {projects.isLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((item) => (
            <Skeleton key={item} className="h-[180px] w-full" />
          ))}
        </div>
      ) : !projects.data?.items.length ? (
        <Card>
          <EmptyState
            icon={<FolderKanban size={20} />}
            title="还没有项目"
            description="创建第一个项目，把日常任务按方向归档。"
            action={
              <button className="btn-primary" onClick={() => setOpen(true)}>
                <Plus size={16} /> 新建项目
              </button>
            }
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {projects.data.items.map((project) => (
            <Link
              key={project.id}
              to={`/projects/${project.id}`}
              className={cn(
                "project-card card group relative overflow-hidden p-5 transition hover:border-brand-500/40 hover:bg-ink-750/70",
                project.status !== "active" && "opacity-60",
              )}
            >
              <span
                className="absolute inset-x-0 top-0 h-1"
                style={{ background: project.color }}
              />
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span
                    className="project-icon flex h-10 w-10 items-center justify-center rounded-xl text-white"
                    style={{ background: `${project.color}28`, color: project.color }}
                  >
                    <FolderKanban size={19} />
                  </span>
                  <div>
                    <p className="project-name text-[15px] font-semibold text-mist-100">{project.name}</p>
                    <p className="project-desc mt-0.5 line-clamp-1 text-[11px] text-mist-500">
                      {project.description || "暂无描述"}
                    </p>
                    <p className="project-counts mt-1 text-[10px] text-mist-500">
                      {project.task_count} 任务 · {project.done_count} 完成 ·{" "}
                      {project.overdue_count} 逾期
                    </p>
                  </div>
                </div>
                <ArrowUpRight
                  size={16}
                  className="text-mist-600 transition group-hover:text-brand-400"
                />
              </div>

              <div className="project-progress mt-5">
                <div className="mb-1.5 flex justify-between text-[11px]">
                  <span className="text-mist-500">整体进度</span>
                  <span className="text-mist-200">{project.progress}%</span>
                </div>
                <ProgressBar value={project.progress} color={project.color} height={7} />
              </div>

              <div className="project-stats mt-4 grid grid-cols-3 gap-2 text-center">
                <div className="rounded-lg bg-ink-900/50 py-2">
                  <p className="text-[16px] font-semibold text-mist-100">{project.task_count}</p>
                  <p className="text-[10px] text-mist-500">任务</p>
                </div>
                <div className="rounded-lg bg-ink-900/50 py-2">
                  <p className="text-[16px] font-semibold text-emerald-300">{project.done_count}</p>
                  <p className="text-[10px] text-mist-500">完成</p>
                </div>
                <div className="rounded-lg bg-ink-900/50 py-2">
                  <p className="text-[16px] font-semibold text-red-300">{project.overdue_count}</p>
                  <p className="text-[10px] text-mist-500">逾期</p>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="新建项目"
        footer={
          <>
            <button className="btn-ghost" onClick={() => setOpen(false)}>
              取消
            </button>
            <button
              className="btn-primary"
              disabled={!name.trim() || create.isPending}
              onClick={() => create.mutate()}
            >
              创建
            </button>
          </>
        }
      >
        <div className="space-y-3">
          <label className="block text-xs text-mist-400">
            项目名称
            <input
              autoFocus
              className="input mt-1"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="例如：官网改版项目"
            />
          </label>
          <label className="block text-xs text-mist-400">
            描述
            <textarea
              className="input mt-1 min-h-[80px]"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="这个项目要达成什么？"
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
    </div>
  );
}
