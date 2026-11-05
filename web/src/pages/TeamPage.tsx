import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { UserPlus, Users } from "lucide-react";
import { api } from "../api/client";
import {
  Avatar,
  Card,
  EmptyState,
  Modal,
  ProgressBar,
  Skeleton,
} from "../components/ui/primitives";
import { cn } from "../lib/format";

export default function TeamPage() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [role, setRole] = useState("成员");
  const [color, setColor] = useState("#5B7CFA");
  const queryClient = useQueryClient();
  const members = useQuery({ queryKey: ["members"], queryFn: api.members });

  const create = useMutation({
    mutationFn: () => api.createMember({ name, role, avatar_color: color }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["members"] });
      toast.success("成员已添加");
      setOpen(false);
      setName("");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const items = members.data?.items || [];
  const maxActive = Math.max(1, ...items.map((member) => member.active));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[20px] font-semibold text-mist-100">团队协作</h1>
          <p className="mt-1 text-[12px] text-mist-500">
            当前为本地单用户模式；可手动添加协作者并把任务分配给他们。
          </p>
        </div>
        <button className="btn-primary" onClick={() => setOpen(true)}>
          <UserPlus size={16} /> 添加成员
        </button>
      </div>

      {members.isLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2].map((item) => (
            <Skeleton key={item} className="h-[170px] w-full" />
          ))}
        </div>
      ) : !items.length ? (
        <Card>
          <EmptyState icon={<Users size={20} />} title="还没有成员" />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {items.map((member) => (
            <Card key={member.id} className="relative overflow-hidden">
              <div className="flex items-center gap-3">
                <Avatar name={member.name} color={member.avatar_color} size={44} />
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-2 text-[14px] font-semibold text-mist-100">
                    {member.name}
                    {member.is_me ? (
                      <span className="pill bg-brand-500/15 text-brand-300">本人</span>
                    ) : null}
                  </p>
                  <p className="text-[11px] text-mist-500">{member.role}</p>
                </div>
                <span
                  className={cn(
                    "h-2 w-2 rounded-full",
                    member.active ? "bg-emerald-400" : "bg-ink-500",
                  )}
                />
              </div>

              <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                <div className="rounded-lg bg-ink-900/50 py-2">
                  <p className="text-[16px] font-semibold text-mist-100">{member.active}</p>
                  <p className="text-[10px] text-mist-500">进行中</p>
                </div>
                <div className="rounded-lg bg-ink-900/50 py-2">
                  <p className="text-[16px] font-semibold text-emerald-300">{member.done}</p>
                  <p className="text-[10px] text-mist-500">已完成</p>
                </div>
                <div className="rounded-lg bg-ink-900/50 py-2">
                  <p className="text-[16px] font-semibold text-red-300">{member.overdue}</p>
                  <p className="text-[10px] text-mist-500">逾期</p>
                </div>
              </div>

              <div className="mt-4">
                <div className="mb-1 flex justify-between text-[10px] text-mist-500">
                  <span>当前负荷</span>
                  <span>{Math.round((member.active / maxActive) * 100)}%</span>
                </div>
                <ProgressBar
                  value={(member.active / maxActive) * 100}
                  color={member.avatar_color}
                  height={6}
                />
              </div>
            </Card>
          ))}
        </div>
      )}

      {items.length <= 1 ? (
        <Card className="border-dashed">
          <p className="text-center text-[12px] leading-6 text-mist-500">
            目前只有你一个人使用工作台。等有协作场景时，再添加成员并把任务指派给他们即可；
            在此之前，“团队协作”不会伪造任何数据。
          </p>
        </Card>
      ) : null}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="添加成员"
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
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <label className="block text-xs text-mist-400">
            角色
            <input
              className="input mt-1"
              value={role}
              onChange={(event) => setRole(event.target.value)}
            />
          </label>
          <label className="block text-xs text-mist-400">
            头像颜色
            <input
              type="color"
              className="mt-1 h-9 w-16 rounded border border-ink-700 bg-ink-900"
              value={color}
              onChange={(event) => setColor(event.target.value)}
            />
          </label>
        </div>
      </Modal>
    </div>
  );
}
