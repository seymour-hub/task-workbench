import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  CalendarRange,
  ChevronDown,
  ExternalLink,
  EyeOff,
  FileText,
  FolderOpen,
  FolderPlus,
  Link2,
  Paperclip,
  RefreshCw,
  Search,
  Trash2,
} from "lucide-react";
import { api } from "../api/client";
import type { IndexedFile } from "../api/types";
import FilePreviewModal, {
  type PreviewItem,
} from "../components/files/FilePreviewModal";
import { useTaskDrawer } from "../components/tasks/TaskDrawerContext";
import {
  Card,
  EmptyState,
  Modal,
  Skeleton,
  StatusBadge,
  Tabs,
} from "../components/ui/primitives";
import { groupDeliverablesByTask } from "../lib/deliverables";
import { cn, formatBytes, formatDate, timeAgo } from "../lib/format";
import { CATEGORIES } from "../lib/taxonomy";

export default function FilesPage() {
  const [tab, setTab] = useState("deliverables");
  const [rootId, setRootId] = useState("");
  const [keyword, setKeyword] = useState("");
  const [unlinked, setUnlinked] = useState(false);
  const [includeIntermediate, setIncludeIntermediate] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState("");
  const [expandedTasks, setExpandedTasks] = useState<Set<string>>(new Set());
  const [preview, setPreview] = useState<PreviewItem | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [attachFile, setAttachFile] = useState<IndexedFile | null>(null);
  const [targetTask, setTargetTask] = useState("");
  const [label, setLabel] = useState("");
  const [path, setPath] = useState("");
  const [depth, setDepth] = useState("4");
  const [enabled, setEnabled] = useState(true);
  const queryClient = useQueryClient();
  const { openTask } = useTaskDrawer();

  const roots = useQuery({ queryKey: ["file-roots"], queryFn: api.fileRoots });
  const deliverables = useQuery({
    queryKey: ["deliverables", keyword, includeIntermediate],
    queryFn: () =>
      api.deliverables({
        q: keyword || undefined,
        include_intermediate: includeIntermediate || undefined,
        limit: 1000,
      }),
  });
  const files = useQuery({
    queryKey: ["files", rootId, keyword, unlinked],
    queryFn: () =>
      api.files({
        root_id: rootId || undefined,
        q: keyword || undefined,
        unlinked: unlinked || undefined,
        limit: 500,
      }),
  });
  const tasks = useQuery({ queryKey: ["tasks", "file-select"], queryFn: () => api.tasks({ limit: 500 }) });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["file-roots"] });
    queryClient.invalidateQueries({ queryKey: ["files"] });
    queryClient.invalidateQueries({ queryKey: ["deliverables"] });
    queryClient.invalidateQueries({ queryKey: ["task"] });
  };

  const scanAll = useMutation({
    mutationFn: () => api.scanAll(),
    onSuccess: () => {
      invalidate();
      toast.success("扫描完成");
    },
    onError: (error: Error) => toast.error(error.message),
  });
  const scanRoot = useMutation({
    mutationFn: (id: number) => api.scanRoot(id),
    onSuccess: () => {
      invalidate();
      toast.success("路径已扫描");
    },
    onError: (error: Error) => toast.error(error.message),
  });
  const toggleRoot = useMutation({
    mutationFn: ({ id, value }: { id: number; value: boolean }) =>
      api.updateFileRoot(id, { enabled: value }),
    onSuccess: () => invalidate(),
    onError: (error: Error) => toast.error(error.message),
  });
  const deleteRoot = useMutation({
    mutationFn: (id: number) => api.deleteFileRoot(id),
    onSuccess: () => {
      invalidate();
      toast.success("路径已移除（磁盘文件未受影响）");
    },
    onError: (error: Error) => toast.error(error.message),
  });
  const addRoot = useMutation({
    mutationFn: () =>
      api.createFileRoot({
        label,
        path,
        depth: Number(depth),
        enabled,
      }),
    onSuccess: () => {
      invalidate();
      setAddOpen(false);
      setLabel("");
      setPath("");
      toast.success("路径已添加");
    },
    onError: (error: Error) => toast.error(error.message),
  });
  const attach = useMutation({
    mutationFn: () => api.attachFile(attachFile!.id, Number(targetTask)),
    onSuccess: () => {
      invalidate();
      setAttachFile(null);
      setTargetTask("");
      toast.success("已挂接到任务");
    },
    onError: (error: Error) => toast.error(error.message),
  });
  const ignore = useMutation({
    mutationFn: (id: number) => api.ignoreFile(id),
    onSuccess: () => {
      invalidate();
      toast.success("已忽略该文件");
    },
    onError: (error: Error) => toast.error(error.message),
  });
  const reveal = useMutation({
    mutationFn: (value: string) => api.revealFile(value),
    onError: (error: Error) => toast.error(error.message),
  });

  const rootItems = roots.data?.items || [];
  const taskGroups = useMemo(
    () => groupDeliverablesByTask(deliverables.data?.items || []),
    [deliverables.data],
  );
  const visibleTaskGroups = useMemo(
    () =>
      taskGroups.filter(
        (group) => !categoryFilter || group.project_name === categoryFilter,
      ),
    [taskGroups, categoryFilter],
  );

  const toggleTask = (key: string) => {
    setExpandedTasks((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[20px] font-semibold text-mist-100">文件资料</h1>
          <p className="mt-1 text-[12px] text-mist-500">
            自动索引 Hermes 输出、桌面与工作目录；只读元数据，不复制、不移动、不上传。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button className="btn-ghost h-9" onClick={() => scanAll.mutate()}>
            <RefreshCw size={14} /> 全部扫描
          </button>
          <button className="btn-primary h-9" onClick={() => setAddOpen(true)}>
            <FolderPlus size={15} /> 添加路径
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Tabs
          value={tab}
          onChange={setTab}
          tabs={[
            { key: "deliverables", label: "交付物", count: deliverables.data?.items.length },
            { key: "files", label: "文件索引", count: files.data?.total },
            { key: "roots", label: "路径管理", count: rootItems.length },
          ]}
        />
        <form
          onSubmit={(event) => event.preventDefault()}
          className="ml-auto flex h-9 w-full max-w-[280px] items-center gap-2 rounded-lg border border-ink-700 bg-ink-900/60 px-2.5"
        >
          <Search size={14} className="text-mist-500" />
          <input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="搜索文件名..."
            className="w-full bg-transparent text-[12px] text-mist-100 outline-none placeholder:text-mist-600"
          />
        </form>
        {tab === "deliverables" ? (
          <>
            <select
              className="h-9 rounded-lg border border-ink-700 bg-ink-900/60 px-2 text-[11px] text-mist-300 outline-none"
              value={categoryFilter}
              onChange={(event) => setCategoryFilter(event.target.value)}
            >
              <option value="">全部业务域</option>
              {CATEGORIES.map((item) => (
                <option key={item.name} value={item.name}>
                  {item.name}
                </option>
              ))}
            </select>
            <label className="flex items-center gap-1.5 text-[11px] text-mist-400">
              <input
                type="checkbox"
                className="accent-brand-500"
                checked={includeIntermediate}
                onChange={(event) => setIncludeIntermediate(event.target.checked)}
              />
              含过程版本
            </label>
            <button
              className="text-[11px] text-mist-400 transition hover:text-mist-100"
              onClick={() =>
                setExpandedTasks(new Set(visibleTaskGroups.map((group) => group.key)))
              }
            >
              全部展开
            </button>
            <span className="text-[11px] text-mist-600">/</span>
            <button
              className="text-[11px] text-mist-400 transition hover:text-mist-100"
              onClick={() => setExpandedTasks(new Set())}
            >
              全部收起
            </button>
          </>
        ) : null}
        {tab === "files" ? (
          <>
            <select
              className="h-9 rounded-lg border border-ink-700 bg-ink-900/60 px-2 text-[11px] text-mist-300 outline-none"
              value={rootId}
              onChange={(event) => setRootId(event.target.value)}
            >
              <option value="">全部路径</option>
              {rootItems.map((root) => (
                <option key={root.id} value={root.id}>
                  {root.label}
                </option>
              ))}
            </select>
            <label className="flex items-center gap-1.5 text-[11px] text-mist-400">
              <input
                type="checkbox"
                checked={unlinked}
                onChange={(event) => setUnlinked(event.target.checked)}
              />
              仅未关联
            </label>
          </>
        ) : null}
      </div>

      {tab === "deliverables" ? (
        deliverables.isLoading ? (
          <div className="space-y-3">
            {[0, 1, 2].map((item) => (
              <Skeleton key={item} className="h-[180px] w-full" />
            ))}
          </div>
        ) : !deliverables.data?.items.length ? (
          <Card>
            <EmptyState
              icon={<Paperclip size={20} />}
              title="还没有交付物"
              description="只收最终给人看的结果；脚本、缓存、样片等过程文件不会出现在这里。"
            />
          </Card>
        ) : (
          <div className="space-y-3">
            {visibleTaskGroups.map((group) => {
              const isExpanded = expandedTasks.has(group.key);
              return (
                <div key={group.key} className="card overflow-hidden p-0">
                  <div
                    role="button"
                    tabIndex={0}
                    onClick={() => toggleTask(group.key)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        toggleTask(group.key);
                      }
                    }}
                    className="flex cursor-pointer flex-wrap items-center gap-3 p-4 transition hover:bg-ink-750/40"
                  >
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400">
                      <FolderOpen size={18} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate text-[14px] font-semibold text-mist-100">
                          {group.task_title}
                        </p>
                        {group.task_status ? <StatusBadge status={group.task_status} /> : null}
                      </div>
                      <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10.5px] text-mist-500">
                        <span>
                          {group.project_name || "未归类"} · {group.items.length} 个文件 ·{" "}
                          {group.outputs.length} 组输出物
                          {includeIntermediate ? "" : "（仅最终版）"}
                        </span>
                        {group.started_at || group.ended_at ? (
                          <span className="flex items-center gap-1 text-mist-400">
                            <CalendarRange size={11} />
                            {formatDate(group.started_at)} →{" "}
                            {group.ended_at ? formatDate(group.ended_at) : "进行中"}
                          </span>
                        ) : null}
                      </div>
                      {!isExpanded ? (
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {group.outputs.map((output) => (
                            <span
                              key={output.key}
                              className="pill border border-ink-700/70 bg-ink-750/60 text-mist-400"
                            >
                              {output.name} · {output.items.length}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                    <button
                      className="btn-ghost h-8 shrink-0 px-3 text-[11px]"
                      onClick={(event) => {
                        event.stopPropagation();
                        if (group.task_id) openTask(group.task_id, "deliverables");
                      }}
                      disabled={!group.task_id}
                    >
                      <ExternalLink size={13} /> 打开任务交付物
                    </button>
                    <ChevronDown
                      size={16}
                      className={cn(
                        "shrink-0 text-mist-500 transition-transform",
                        isExpanded && "rotate-180",
                      )}
                    />
                  </div>

                  {isExpanded ? (
                    <div className="space-y-3 border-t border-ink-700/50 p-4 pt-3">
                      {group.outputs.map((output) => (
                        <div
                          key={output.key}
                          className="rounded-xl border border-ink-700/60 bg-ink-900/30 p-3"
                        >
                          <div className="flex items-center gap-2 border-b border-ink-700/40 pb-2">
                            <Paperclip size={14} className="text-brand-300" />
                            <p className="min-w-0 flex-1 truncate text-[12.5px] font-medium text-mist-200">
                              {output.name}
                            </p>
                            <span className="text-[10px] text-mist-500">
                              {output.items.length} 个版本
                            </span>
                          </div>
                          <div className="mt-2 space-y-2">
                            {output.items.map((item) => (
                              <div
                                key={item.id}
                                onClick={() =>
                                  setPreview({
                                    path: item.path_or_url,
                                    title: item.title,
                                  })
                                }
                                className="flex cursor-pointer items-center gap-2.5 rounded-lg px-1 py-1 transition hover:bg-ink-750/50"
                                title="点击直接打开文件"
                              >
                                <FileText
                                  size={14}
                                  className={
                                    item.is_final ? "text-emerald-400" : "text-mist-500"
                                  }
                                />
                                <div className="min-w-0 flex-1">
                                  <p className="truncate text-[12px] text-mist-200">
                                    {item.title}
                                  </p>
                                  <p className="truncate text-[10.5px] text-mist-500">
                                    {item.version_label || formatDate(item.version_at, true)}
                                    {item.file_size
                                      ? ` · ${formatBytes(item.file_size)}`
                                      : ""}
                                    {item.exists_flag ? "" : " · 文件缺失"}
                                  </p>
                                </div>
                                {item.is_final ? (
                                  <span className="pill shrink-0 bg-emerald-500/10 text-emerald-300">
                                    最终版
                                  </span>
                                ) : item.is_intermediate ? (
                                  <span className="pill shrink-0 bg-amber-500/10 text-amber-300">
                                    过程版
                                  </span>
                                ) : null}
                                <button
                                  className="rounded p-1.5 text-mist-400 transition hover:bg-ink-700 hover:text-mist-100"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    setPreview({
                                      path: item.path_or_url,
                                      title: item.title,
                                    });
                                  }}
                                  title="预览文件"
                                >
                                  <ExternalLink size={13} />
                                </button>
                                <button
                                  className="rounded p-1.5 text-mist-400 transition hover:bg-ink-700 hover:text-mist-100"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    reveal.mutate(item.path_or_url);
                                  }}
                                  title="打开所在文件夹"
                                >
                                  <FolderOpen size={13} />
                                </button>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        )
      ) : null}

      {tab === "files" ? (
        <Card className="p-4">
          {files.isLoading ? (
            <div className="space-y-2">
              {[0, 1, 2, 3, 4].map((item) => (
                <Skeleton key={item} className="h-11 w-full" />
              ))}
            </div>
          ) : !files.data?.items.length ? (
            <EmptyState
              icon={<FolderOpen size={20} />}
              title="没有索引到文件"
              description="确认路径已启用，然后点击“全部扫描”。"
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left">
                <thead>
                  <tr className="text-[11px] text-mist-500">
                    <th className="pb-2">文件</th>
                    <th className="w-[160px] pb-2">路径</th>
                    <th className="w-[90px] pb-2">大小</th>
                    <th className="w-[100px] pb-2">修改时间</th>
                    <th className="w-[120px] pb-2">关联任务</th>
                    <th className="w-[120px] pb-2 text-right">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {files.data.items.map((file) => {
                    const root = rootItems.find((item) => item.id === file.root_id);
                    return (
                      <tr key={file.id} className="table-row text-[12px]">
                        <td className="max-w-[280px] py-2.5">
                          <p className="truncate text-mist-100">{file.name}</p>
                          <p className="text-[10px] text-mist-600">{file.ext || "—"}</p>
                        </td>
                        <td className="truncate py-2.5 text-mist-400">{root?.label || "—"}</td>
                        <td className="py-2.5 text-mist-400">{formatBytes(file.size)}</td>
                        <td className="py-2.5 text-mist-500">{formatDate(file.mtime)}</td>
                        <td className="py-2.5">
                          {file.task_id ? (
                            <span className="pill bg-brand-500/10 text-brand-300">已关联</span>
                          ) : (
                            <span className="text-mist-600">未关联</span>
                          )}
                        </td>
                        <td className="py-2.5">
                          <div className="flex justify-end gap-1">
                            <button
                              className="rounded p-1.5 text-mist-400 hover:bg-ink-750 hover:text-brand-300"
                              title="挂接到任务"
                              onClick={() => {
                                setAttachFile(file);
                                setTargetTask("");
                              }}
                            >
                              <Link2 size={14} />
                            </button>
                            <button
                              className="rounded p-1.5 text-mist-400 hover:bg-ink-750 hover:text-mist-100"
                              title="打开所在文件夹"
                              onClick={() => reveal.mutate(file.path)}
                            >
                              <FolderOpen size={14} />
                            </button>
                            <button
                              className="rounded p-1.5 text-mist-400 hover:bg-ink-750 hover:text-red-300"
                              title="忽略"
                              onClick={() => ignore.mutate(file.id)}
                            >
                              <EyeOff size={14} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      ) : null}

      {tab === "roots" ? (
        <div className="space-y-3">
          {rootItems.map((root) => (
            <Card key={root.id} className="p-4">
              <div className="flex flex-wrap items-center gap-3">
                <span
                  className={cn(
                    "flex h-10 w-10 items-center justify-center rounded-xl",
                    root.enabled ? "bg-brand-500/10 text-brand-300" : "bg-ink-750 text-mist-500",
                  )}
                >
                  <FolderOpen size={18} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-[13.5px] font-medium text-mist-100">{root.label}</p>
                    {!root.exists ? (
                      <span className="pill bg-red-500/10 text-red-300">路径不存在</span>
                    ) : null}
                    {root.enabled ? (
                      <span className="pill bg-emerald-500/10 text-emerald-300">已启用</span>
                    ) : (
                      <span className="pill bg-ink-750 text-mist-500">已停用</span>
                    )}
                  </div>
                  <p className="mt-0.5 truncate text-[11px] text-mist-500">{root.path}</p>
                  <p className="mt-1 text-[10.5px] text-mist-600">
                    {root.file_count} 个文件 · 深度 {root.depth} · 上次扫描{" "}
                    {root.last_scan_at ? timeAgo(root.last_scan_at) : "从未"}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <label className="flex items-center gap-1.5 text-[11px] text-mist-400">
                    <input
                      type="checkbox"
                      checked={root.enabled}
                      onChange={(event) =>
                        toggleRoot.mutate({ id: root.id, value: event.target.checked })
                      }
                    />
                    启用
                  </label>
                  <button
                    className="btn-ghost h-8 px-2 text-[11px]"
                    onClick={() => scanRoot.mutate(root.id)}
                  >
                    <RefreshCw size={13} /> 扫描
                  </button>
                  <button
                    className="rounded p-1.5 text-mist-400 hover:bg-ink-750 hover:text-mist-100"
                    onClick={() => reveal.mutate(root.path)}
                  >
                    <FolderOpen size={15} />
                  </button>
                  <button
                    className="rounded p-1.5 text-mist-400 hover:bg-ink-750 hover:text-red-300"
                    onClick={() => deleteRoot.mutate(root.id)}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      ) : null}

      <Modal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title="添加扫描路径"
        footer={
          <>
            <button className="btn-ghost" onClick={() => setAddOpen(false)}>
              取消
            </button>
            <button
              className="btn-primary"
              disabled={!label.trim() || !path.trim() || addRoot.isPending}
              onClick={() => addRoot.mutate()}
            >
              添加
            </button>
          </>
        }
      >
        <div className="space-y-3">
          <label className="block text-xs text-mist-400">
            名称
            <input
              autoFocus
              className="input mt-1"
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              placeholder="例如：项目交付目录"
            />
          </label>
          <label className="block text-xs text-mist-400">
            绝对路径
            <input
              className="input mt-1"
              value={path}
              onChange={(event) => setPath(event.target.value)}
              placeholder="F:\xxx\outputs"
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-xs text-mist-400">
              扫描深度
              <input
                type="number"
                min={1}
                max={10}
                className="input mt-1"
                value={depth}
                onChange={(event) => setDepth(event.target.value)}
              />
            </label>
            <label className="flex items-end gap-2 pb-2 text-xs text-mist-400">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(event) => setEnabled(event.target.checked)}
              />
              立即启用
            </label>
          </div>
          <p className="text-[11px] leading-5 text-mist-500">
            只会读取文件名、大小、修改时间等元数据；不会打开或上传文件内容。
          </p>
        </div>
      </Modal>

      <Modal
        open={Boolean(attachFile)}
        onClose={() => setAttachFile(null)}
        title="挂接到任务"
        footer={
          <>
            <button className="btn-ghost" onClick={() => setAttachFile(null)}>
              取消
            </button>
            <button
              className="btn-primary"
              disabled={!targetTask || attach.isPending}
              onClick={() => attach.mutate()}
            >
              挂接
            </button>
          </>
        }
      >
        <p className="mb-3 truncate rounded-lg bg-ink-900/60 p-3 text-[12px] text-mist-300">
          {attachFile?.path}
        </p>
        <label className="block text-xs text-mist-400">
          选择任务
          <select
            className="input mt-1"
            value={targetTask}
            onChange={(event) => setTargetTask(event.target.value)}
          >
            <option value="">请选择</option>
            {tasks.data?.items.map((task) => (
              <option key={task.id} value={task.id}>
                #{task.id} {task.title}
              </option>
            ))}
          </select>
        </label>
      </Modal>

      <FilePreviewModal item={preview} onClose={() => setPreview(null)} />
    </div>
  );
}
