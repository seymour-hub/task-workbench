import { Link } from "react-router-dom";
import { ChevronRight, FolderKanban } from "lucide-react";
import type { DashboardSummary } from "../../api/types";
import { Card, EmptyState, ProgressBar, SectionHeader } from "../ui/primitives";

export default function WeeklyProgress({
  projects,
}: {
  projects: DashboardSummary["weekly_progress"];
}) {
  return (
    <Card className="flex h-full flex-col">
      <SectionHeader
        title="本周进度"
        action={
          <Link
            to="/projects"
            className="flex items-center gap-1 text-[11px] text-mist-400 transition hover:text-brand-400"
          >
            本周 <ChevronRight size={13} />
          </Link>
        }
      />
      {!projects.length ? (
        <EmptyState
          icon={<FolderKanban size={20} />}
          title="还没有项目进度"
          description="给任务分配项目后，这里会按项目汇总。"
        />
      ) : (
        <div className="space-y-4">
          {projects.map((project) => (
            <div key={project.project_id}>
              <div className="mb-1.5 flex items-center gap-2 text-[12px]">
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ background: project.color }}
                />
                <span className="min-w-0 flex-1 truncate text-mist-300">
                  {project.name}
                </span>
                <span className="text-mist-100">{project.progress}%</span>
              </div>
              <ProgressBar value={project.progress} color={project.color} height={7} />
              <p className="mt-1 text-right text-[10px] text-mist-600">
                {project.done}/{project.total} 已完成
              </p>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
