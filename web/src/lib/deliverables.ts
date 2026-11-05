import type { Deliverable } from "../api/types";

export interface DeliverableGroup {
  key: string;
  name: string;
  items: Deliverable[];
  hasFinal: boolean;
  latestAt: number;
}

export interface TaskDeliverableGroup {
  key: string;
  task_id: number | null;
  task_title: string;
  task_status?: string | null;
  started_at?: number | null;
  ended_at?: number | null;
  project_name?: string | null;
  project_color?: string | null;
  latest_at: number;
  items: Deliverable[];
  outputs: DeliverableGroup[];
}

export function groupDeliverables(items: Deliverable[]): DeliverableGroup[] {
  const groups = new Map<string, Deliverable[]>();
  items.forEach((item) => {
    const key = item.group_key || item.logical_name || item.title;
    groups.set(key, [...(groups.get(key) || []), item]);
  });
  return [...groups.entries()]
    .map(([key, group]) => ({
      key,
      name: group[0].logical_name || group[0].title,
      items: [...group].sort(
        (left, right) =>
          Number(right.is_final) - Number(left.is_final) ||
          (right.version_at || 0) - (left.version_at || 0),
      ),
      hasFinal: group.some((item) => item.is_final),
      latestAt: Math.max(0, ...group.map((item) => item.version_at || 0)),
    }))
    .sort(
      (left, right) =>
        Number(right.hasFinal) - Number(left.hasFinal) ||
        right.latestAt - left.latestAt ||
        left.name.localeCompare(right.name, "zh"),
    );
}

export function groupDeliverablesByTask(items: Deliverable[]): TaskDeliverableGroup[] {
  const groups = new Map<string, Deliverable[]>();
  items.forEach((item) => {
    const key = item.task_id ? String(item.task_id) : "unassigned";
    groups.set(key, [...(groups.get(key) || []), item]);
  });
  return [...groups.entries()]
    .map(([key, group]) => ({
      key,
      task_id: group[0].task_id ?? null,
      task_title: group[0].task_title || "未关联任务",
      task_status: group[0].task_status,
      started_at: group[0].task_started_at,
      ended_at: group[0].task_ended_at,
      project_name: group[0].project_name,
      project_color: group[0].project_color,
      latest_at: Math.max(0, ...group.map((item) => item.version_at || 0)),
      items: group,
      outputs: groupDeliverables(group),
    }))
    .sort((left, right) => {
      if (left.task_id === null) return 1;
      if (right.task_id === null) return -1;
      // Latest activity wins, so an in-progress task with fresh outputs stays
      // on top instead of being pushed to the bottom for lacking ended_at.
      // Tasks still in progress stay on top, then newest activity first.
      const leftRank = left.task_status === "in_progress" ? 0 : 1;
      const rightRank = right.task_status === "in_progress" ? 0 : 1;
      const leftAt = Math.max(left.ended_at || 0, left.started_at || 0, left.latest_at);
      const rightAt = Math.max(right.ended_at || 0, right.started_at || 0, right.latest_at);
      return (
        leftRank - rightRank ||
        rightAt - leftAt ||
        (right.task_id || 0) - (left.task_id || 0)
      );
    });
}
