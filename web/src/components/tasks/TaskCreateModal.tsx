import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "../../api/client";
import { PRIORITY } from "../../lib/format";
import { CATEGORIES, WORK_TYPES, subcategoriesFor } from "../../lib/taxonomy";
import { Modal } from "../ui/primitives";

export default function TaskCreateModal({
  open,
  onClose,
  defaultStatus = "todo",
}: {
  open: boolean;
  onClose: () => void;
  defaultStatus?: string;
}) {
  const queryClient = useQueryClient();
  const projects = useQuery({ queryKey: ["projects"], queryFn: api.projects });
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [projectId, setProjectId] = useState("");
  const [priority, setPriority] = useState("medium");
  const [category, setCategory] = useState("");
  const [subcategory, setSubcategory] = useState("");
  const [workTypes, setWorkTypes] = useState<string[]>([]);
  const [due, setDue] = useState("");

  useEffect(() => {
    if (!open) return;
    setTitle("");
    setDescription("");
    setProjectId("");
    setPriority("medium");
    setCategory("");
    setSubcategory("");
    setWorkTypes([]);
    setDue("");
  }, [open]);

  const create = useMutation({
    mutationFn: () =>
      api.createTask({
        title,
        description: description || null,
        project_id: projectId ? Number(projectId) : null,
        priority,
        category: category || null,
        subcategory: subcategory || null,
        work_types: workTypes,
        status: defaultStatus,
        due_at: due ? new Date(due).getTime() / 1000 : null,
        source_type: "manual",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["board"] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast.success("任务已创建");
      onClose();
    },
    onError: (error: Error) => toast.error(error.message),
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="新建任务"
      footer={
        <>
          <button className="btn-ghost" onClick={onClose}>
            取消
          </button>
          <button
            className="btn-primary"
            disabled={!title.trim() || create.isPending}
            onClick={() => create.mutate()}
          >
            创建任务
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
            placeholder="要做什么？"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
          />
        </label>
        <label className="block text-xs text-mist-400">
          描述
          <textarea
            className="input mt-1 min-h-[84px] resize-y"
            placeholder="补充背景、验收标准或过程要求..."
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-xs text-mist-400">
            项目
            <select
              className="input mt-1"
              value={projectId}
              onChange={(event) => setProjectId(event.target.value)}
            >
              <option value="">未归类</option>
              {projects.data?.items.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-xs text-mist-400">
            优先级
            <select
              className="input mt-1"
              value={priority}
              onChange={(event) => setPriority(event.target.value)}
            >
              {Object.entries(PRIORITY).map(([key, value]) => (
                <option key={key} value={key}>
                  {value.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-xs text-mist-400">
            业务域
            <select
              className="input mt-1"
              value={category}
              onChange={(event) => {
                setCategory(event.target.value);
                setSubcategory("");
              }}
            >
              <option value="">未分类</option>
              {CATEGORIES.map((item) => (
                <option key={item.name} value={item.name}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-xs text-mist-400">
            二级分类
            <select
              className="input mt-1"
              value={subcategory}
              disabled={!category}
              onChange={(event) => setSubcategory(event.target.value)}
            >
              <option value="">未分类</option>
              {subcategoriesFor(category).map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="text-xs text-mist-400">
          工作类型
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {WORK_TYPES.map((tag) => {
              const active = workTypes.includes(tag);
              return (
                <button
                  key={tag}
                  onClick={() =>
                    setWorkTypes((current) =>
                      active
                        ? current.filter((value) => value !== tag)
                        : [...current, tag],
                    )
                  }
                  className={
                    active
                      ? "rounded-md border border-brand-500/40 bg-brand-500/15 px-2 py-1 text-[10.5px] text-brand-300"
                      : "rounded-md border border-ink-700 bg-ink-850 px-2 py-1 text-[10.5px] text-mist-400 hover:text-mist-200"
                  }
                >
                  {tag}
                </button>
              );
            })}
          </div>
        </div>
        <label className="block text-xs text-mist-400">
          截止时间
          <input
            type="datetime-local"
            className="input mt-1"
            value={due}
            onChange={(event) => setDue(event.target.value)}
          />
        </label>
      </div>
    </Modal>
  );
}
