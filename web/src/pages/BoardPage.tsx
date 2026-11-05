import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import { api } from "../api/client";
import KanbanBoard from "../components/board/KanbanBoard";
import TaskCreateModal from "../components/tasks/TaskCreateModal";
import { Card, Skeleton } from "../components/ui/primitives";

export default function BoardPage() {
  const [projectId, setProjectId] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [createStatus, setCreateStatus] = useState("todo");
  const queryClient = useQueryClient();

  const projects = useQuery({ queryKey: ["projects"], queryFn: api.projects });
  const board = useQuery({
    queryKey: ["board", projectId],
    queryFn: () => api.board(projectId ? Number(projectId) : undefined),
  });

  const move = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      api.moveTask(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["board"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast.success("任务状态已更新");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[20px] font-semibold text-mist-100">任务看板</h1>
          <p className="mt-1 text-[12px] text-mist-500">
            拖拽卡片到目标列即可更新状态；“已逾期”为派生列，不可直接拖入。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            className="h-9 rounded-lg border border-ink-700 bg-ink-900/60 px-3 text-[12px] text-mist-300 outline-none"
            value={projectId}
            onChange={(event) => setProjectId(event.target.value)}
          >
            <option value="">全部项目</option>
            {projects.data?.items.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
          <button
            className="btn-primary"
            onClick={() => {
              setCreateStatus("todo");
              setCreateOpen(true);
            }}
          >
            <Plus size={16} /> 新建任务
          </button>
        </div>
      </div>

      <Card className="p-3">
        {board.isLoading || !board.data ? (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
            {[0, 1, 2, 3].map((item) => (
              <Skeleton key={item} className="h-[420px] w-full" />
            ))}
          </div>
        ) : (
          <KanbanBoard
            lanes={board.data.lanes}
            counts={board.data.counts}
            onMove={(id, status) => move.mutate({ id, status })}
            onCreate={(status) => {
              setCreateStatus(status === "overdue" ? "todo" : status);
              setCreateOpen(true);
            }}
          />
        )}
      </Card>

      <TaskCreateModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        defaultStatus={createStatus}
      />
    </div>
  );
}
