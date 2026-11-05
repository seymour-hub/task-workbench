export type TaskStatus = "todo" | "in_progress" | "done" | "cancelled";
export type Priority = "urgent" | "high" | "medium" | "low";

export interface Task {
  id: number;
  project_id: number | null;
  project_name: string | null;
  project_color: string | null;
  assignee_id: number | null;
  assignee_name: string | null;
  assignee_color: string | null;
  title: string;
  description: string | null;
  status: TaskStatus;
  status_label: string;
  priority: Priority;
  due_at: number | null;
  start_at: number | null;
  started_at: number | null;
  ended_at: number | null;
  completed_at: number | null;
  progress: number;
  source_type: string | null;
  source_session_id: string | null;
  chat_id: string | null;
  code: string | null;
  auto_created: boolean;
  source_message_ids: number[];
  source_excerpt: string | null;
  ai_confidence: number | null;
  category: string | null;
  subcategory: string | null;
  work_types: string[];
  sort_order: number;
  overdue: boolean;
  issue_count: number;
  deliverable_count: number;
  created_at: number;
  updated_at: number;
}

export interface TaskDetail extends Task {
  timeline: TimelineEvent[];
  milestones: TimelineEvent[];
  issues: Issue[];
  deliverables: Deliverable[];
}

export interface TimelineEvent {
  id: number;
  type: string;
  from_value: string | null;
  to_value: string | null;
  note: string | null;
  message_id: number | null;
  actor: string;
  created_at: number;
}

export interface Issue {
  id: number;
  title: string;
  detail: string | null;
  severity: string;
  status: string;
  resolution: string | null;
  source_message_id: number | null;
  created_at: number;
  resolved_at?: number | null;
}

export interface Deliverable {
  id: number;
  task_id?: number | null;
  file_id?: number | null;
  task_title?: string | null;
  task_status?: string | null;
  task_started_at?: number | null;
  task_ended_at?: number | null;
  project_name?: string | null;
  project_color?: string | null;
  title: string;
  type: string;
  path_or_url: string;
  file_size: number | null;
  exists_flag: boolean;
  attach_mode?: string;
  confidence?: number | null;
  group_key?: string | null;
  logical_name?: string | null;
  version_label?: string | null;
  version_at?: number | null;
  is_final?: boolean;
  is_intermediate?: boolean;
  created_at: number;
}

export interface Project {
  id: number;
  name: string;
  description: string | null;
  color: string;
  status: string;
  task_count: number;
  done_count: number;
  overdue_count: number;
  progress: number;
  created_at: number;
  updated_at: number;
}

export interface InboxItem {
  id: number;
  kind: "task" | "issue" | "deliverable" | "project" | "note";
  payload: Record<string, any>;
  confidence: number | null;
  status: string;
  segment_id: number | null;
  source_message_ids: number[] | null;
  dedup_of_task_id: number | null;
  created_at: number;
  reviewed_at: number | null;
}

export interface DashboardSummary {
  stats: {
    total: number;
    completed: number;
    pending: number;
    projects: number;
    active_projects: number;
    cancelled: number;
    overdue: number;
    completion_delta: number;
    completed_this_week: number;
  };
  donut: {
    total: number;
    segments: { key: string; label: string; value: number; color: string }[];
  };
  deadlines: Task[];
  today_tasks: Task[];
  weekly_progress: {
    project_id: number;
    name: string;
    color: string;
    total: number;
    done: number;
    progress: number;
  }[];
  schedule: {
    id: string;
    title: string;
    start_at: number;
    end_at: number | null;
    location: string | null;
    color: string;
    kind: string;
    task_id: number | null;
  }[];
  inbox_pending: number;
  inbox_breakdown: Record<string, number>;
  confirmations_pending: number;
}

export interface CalendarItem {
  id: string;
  event_id: number | null;
  title: string;
  description: string | null;
  start_at: number;
  end_at: number | null;
  all_day: boolean;
  location: string | null;
  color: string;
  task_id: number | null;
  source: string;
  editable: boolean;
}

export interface Member {
  id: number;
  name: string;
  avatar_color: string;
  role: string;
  is_me: boolean;
  active: number;
  done: number;
  overdue: number;
}

export interface StatsOverview {
  period: string;
  kpi: {
    completion_rate: number;
    avg_duration_days: number;
    overdue_rate: number;
    deliverables: number;
    open_issues: number;
    completed: number;
  };
  trend: { date: string; completed: number }[];
  status: Record<string, number>;
  projects: {
    project_id: number;
    name: string;
    color: string;
    total: number;
    done: number;
    progress: number;
  }[];
  members: { member_id: number; name: string; color: string; active: number; overdue: number }[];
}

export interface FileRoot {
  id: number;
  label: string;
  path: string;
  enabled: boolean;
  depth: number;
  include_ext: string[] | null;
  exclude_globs: string[] | null;
  auto_attach: boolean;
  scan_interval_min: number;
  last_scan_at: number | null;
  file_count: number;
  exists: boolean;
}

export interface IndexedFile {
  id: number;
  root_id: number;
  path: string;
  relative_path: string;
  name: string;
  ext: string;
  size: number;
  mtime: number;
  exists_flag: boolean;
  ignored: boolean;
  task_id?: number | null;
}

export interface NotificationItem {
  id: number;
  channel: string;
  kind: string;
  title: string;
  body: string;
  status: string;
  attempts: number;
  last_error: string | null;
  sent_at: number | null;
  read_at: number | null;
  created_at: number;
}

export interface SyncStatus {
  source_exists: boolean;
  source_error: string | null;
  source_messages: number;
  cached_messages: number;
  cached_sessions: number;
  segments_pending: number;
  segments_pending_window: number;
  segments_done: number;
  segments_failed: number;
  cursor: string | null;
  last_sync_at: string | null;
  last_sync_new_messages: string | null;
  last_sync_error: string | null;
  schema_fingerprint: string | null;
}
