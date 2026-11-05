import type {
  CalendarItem,
  DashboardSummary,
  Deliverable,
  FileRoot,
  IndexedFile,
  InboxItem,
  Member,
  NotificationItem,
  Project,
  StatsOverview,
  SyncStatus,
  Task,
  TaskDetail,
} from "./types";

const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    ...init,
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function query(params: Record<string, unknown>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  });
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const api = {
  health: () => request<any>("/health"),
  dashboard: () => request<DashboardSummary>("/dashboard/summary"),
  search: (q: string) => request<any>(`/search${query({ q })}`),

  tasks: (params: Record<string, unknown> = {}) =>
    request<{ items: Task[]; total: number }>(`/tasks${query(params)}`),
  task: (id: number) => request<TaskDetail>(`/tasks/${id}`),
  createTask: (payload: Record<string, unknown>) =>
    request<Task>("/tasks", { method: "POST", body: JSON.stringify(payload) }),
  updateTask: (id: number, payload: Record<string, unknown>) =>
    request<Task>(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteTask: (id: number) => request<{ ok: boolean }>(`/tasks/${id}`, { method: "DELETE" }),
  setStatus: (id: number, status: string, sortOrder?: number) =>
    request<Task>(`/tasks/${id}/status`, {
      method: "POST",
      body: JSON.stringify({ status, sort_order: sortOrder }),
    }),
  completeTask: (id: number) => request<Task>(`/tasks/${id}/complete`, { method: "POST" }),
  addComment: (id: number, note: string) =>
    request<any>(`/tasks/${id}/comments`, { method: "POST", body: JSON.stringify({ note }) }),
  createMilestone: (id: number, payload: Record<string, unknown>) =>
    request<any>(`/tasks/${id}/milestones`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createIssue: (taskId: number, payload: Record<string, unknown>) =>
    request<any>(`/tasks/${taskId}/issues`, { method: "POST", body: JSON.stringify(payload) }),
  updateIssue: (issueId: number, payload: Record<string, unknown>) =>
    request<any>(`/issues/${issueId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteIssue: (issueId: number) =>
    request<any>(`/issues/${issueId}`, { method: "DELETE" }),
  createDeliverable: (taskId: number, payload: Record<string, unknown>) =>
    request<any>(`/tasks/${taskId}/deliverables`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateDeliverable: (id: number, payload: Record<string, unknown>) =>
    request<any>(`/deliverables/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteDeliverable: (id: number) =>
    request<any>(`/deliverables/${id}`, { method: "DELETE" }),
  deleteMilestone: (taskId: number, eventId: number) =>
    request<any>(`/tasks/${taskId}/milestones/${eventId}`, { method: "DELETE" }),
  deleteComment: (taskId: number, eventId: number) =>
    request<any>(`/tasks/${taskId}/comments/${eventId}`, { method: "DELETE" }),
  deleteTaskEvent: (taskId: number, eventId: number) =>
    request<any>(`/tasks/${taskId}/events/${eventId}`, { method: "DELETE" }),

  board: (projectId?: number) =>
    request<{ lanes: Record<string, Task[]>; counts: Record<string, number> }>(
      `/board${query({ project_id: projectId })}`,
    ),
  moveTask: (taskId: number, status: string, sortOrder?: number) =>
    request<Task>("/board/move", {
      method: "POST",
      body: JSON.stringify({ task_id: taskId, status, sort_order: sortOrder }),
    }),

  projects: () => request<{ items: Project[] }>("/projects"),
  project: (id: number) => request<Project & { tasks: Task[]; issues: any[]; deliverables: Deliverable[] }>(`/projects/${id}`),
  createProject: (payload: Record<string, unknown>) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify(payload) }),
  updateProject: (id: number, payload: Record<string, unknown>) =>
    request<Project>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteProject: (id: number) => request<{ ok: boolean }>(`/projects/${id}`, { method: "DELETE" }),

  inbox: (status = "pending", kind?: string) =>
    request<{
      items: InboxItem[];
      counts: { pending: number; duplicate: number };
      by_kind: Record<string, number>;
    }>(`/inbox${query({ status, kind })}`),
  acceptInbox: (id: number, payload: Record<string, unknown> = {}, force = false) =>
    request<any>(`/inbox/${id}/accept${query({ force })}`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  rejectInbox: (id: number) =>
    request<{ ok: boolean }>(`/inbox/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  retryInbox: (id: number) => request<any>(`/inbox/${id}/retry`, { method: "POST" }),
  dedupeInbox: () => request<any>("/inbox/dedupe", { method: "POST" }),
  bulkInbox: (action: "accept" | "reject", ids: number[]) =>
    request<any>(`/inbox/bulk${query({ action, ids: ids.join(",") })}`, { method: "POST" }),

  calendar: (start: number, end: number) =>
    request<{ items: CalendarItem[] }>(`/calendar/events${query({ start, end })}`),
  createEvent: (payload: Record<string, unknown>) =>
    request<any>("/calendar/events", { method: "POST", body: JSON.stringify(payload) }),
  updateEvent: (id: number, payload: Record<string, unknown>) =>
    request<any>(`/calendar/events/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteEvent: (id: number) => request<any>(`/calendar/events/${id}`, { method: "DELETE" }),

  members: () => request<{ items: Member[] }>("/team/members"),
  createMember: (payload: Record<string, unknown>) =>
    request<Member>("/team/members", { method: "POST", body: JSON.stringify(payload) }),

  stats: (period = "week") =>
    request<StatsOverview>(`/stats/overview${query({ period })}`),

  fileRoots: () => request<{ items: FileRoot[] }>("/files/roots"),
  createFileRoot: (payload: Record<string, unknown>) =>
    request<FileRoot>("/files/roots", { method: "POST", body: JSON.stringify(payload) }),
  updateFileRoot: (id: number, payload: Record<string, unknown>) =>
    request<FileRoot>(`/files/roots/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteFileRoot: (id: number) =>
    request<{ ok: boolean }>(`/files/roots/${id}`, { method: "DELETE" }),
  scanRoot: (id: number) => request<any>(`/files/roots/${id}/scan`, { method: "POST" }),
  scanAll: () => request<any>("/files/scan", { method: "POST" }),
  files: (params: Record<string, unknown> = {}) =>
    request<{ items: IndexedFile[]; total: number }>(`/files${query(params)}`),
  deliverables: (params: Record<string, unknown> = {}) =>
    request<{ items: Deliverable[] }>(`/files/deliverables${query(params)}`),
  attachFile: (fileId: number, taskId: number) =>
    request<any>(`/files/${fileId}/attach`, {
      method: "POST",
      body: JSON.stringify({ task_id: taskId }),
    }),
  detachFile: (fileId: number) =>
    request<any>(`/files/${fileId}/attach`, { method: "DELETE" }),
  ignoreFile: (fileId: number) =>
    request<any>(`/files/${fileId}/ignore`, { method: "POST" }),
  openFile: (path: string) =>
    request<any>("/files/open", { method: "POST", body: JSON.stringify({ path }) }),
  revealFile: (path: string) =>
    request<any>("/files/reveal", { method: "POST", body: JSON.stringify({ path }) }),

  notifications: (params: Record<string, unknown> = {}) =>
    request<{ items: NotificationItem[]; unread: number }>(`/notifications${query(params)}`),
  retryNotification: (id: number) =>
    request<any>(`/notifications/${id}/retry`, { method: "POST" }),
  testNotification: (text?: string) =>
    request<any>("/notifications/test", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  sendDigest: () => request<any>("/notifications/digest", { method: "POST" }),
  markRead: (id: number) =>
    request<any>(`/notifications/${id}/read`, { method: "PATCH" }),
  markAllRead: () => request<any>("/notifications/read-all", { method: "POST" }),

  settings: () => request<{ settings: Record<string, string>; defaults: Record<string, string> }>("/settings"),
  updateSettings: (payload: Record<string, string>) =>
    request<any>("/settings", { method: "PUT", body: JSON.stringify(payload) }),
  settingsHealth: () => request<any>("/settings/health"),
  backup: () => request<any>("/settings/backup", { method: "POST" }),

  checkWorkflow: (recentHours = 24) =>
    request<any>("/workflow/check", {
      method: "POST",
      body: JSON.stringify({ recent_hours: recentHours }),
    }),
  pendingConfirmations: () =>
    request<{ items: any[] }>("/workflow/pending"),
  resolveConfirmation: (id: number, action: "accept" | "reject") =>
    request<any>(`/workflow/confirmations/${id}/resolve${query({ action })}`, {
      method: "POST",
    }),
  syncStatus: () => request<SyncStatus>("/sync/status"),
  runSync: (payload: Record<string, unknown> = {}) =>
    request<any>("/sync/run", { method: "POST", body: JSON.stringify(payload) }),
  runExtract: (limit = 5, force = false) =>
    request<any>("/ai/extract", {
      method: "POST",
      body: JSON.stringify({ limit, force }),
    }),
  aiUsage: () => request<any>("/ai/usage"),
  sourceMessages: (ids: number[]) =>
    request<{ items: any[] }>(`/sources/messages${query({ ids: ids.join(",") })}`),
  sessions: (limit = 50) =>
    request<{ items: any[] }>(`/sources/sessions${query({ limit })}`),
  segments: (status?: string) =>
    request<{ items: any[] }>(`/segments${query({ status })}`),
};
