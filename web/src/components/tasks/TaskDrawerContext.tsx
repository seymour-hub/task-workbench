import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import TaskDetailDrawer from "./TaskDetailDrawer";

const TaskDrawerContext = createContext<{
  openTask: (id: number, tab?: string) => void;
}>({
  openTask: () => undefined,
});

export function TaskDrawerProvider({ children }: { children: ReactNode }) {
  const [params, setParams] = useSearchParams();
  const [taskId, setTaskId] = useState<number | null>(() => {
    const value = Number(params.get("task"));
    return Number.isFinite(value) && value > 0 ? value : null;
  });
  const [initialTab, setInitialTab] = useState<string | undefined>(
    params.get("tab") || undefined,
  );

  useEffect(() => {
    const value = Number(params.get("task"));
    const tab = params.get("tab") || undefined;
    if (Number.isFinite(value) && value > 0) {
      if (value !== taskId) setTaskId(value);
      setInitialTab(tab);
    }
  }, [params, taskId]);

  const openTask = (id: number, tab?: string) => {
    setTaskId(id);
    setInitialTab(tab);
    const next = new URLSearchParams(window.location.search);
    next.set("task", String(id));
    if (tab) next.set("tab", tab);
    else next.delete("tab");
    setParams(next, { replace: true });
  };

  const close = () => {
    setTaskId(null);
    setInitialTab(undefined);
    const next = new URLSearchParams(window.location.search);
    next.delete("task");
    next.delete("tab");
    setParams(next, { replace: true });
  };

  return (
    <TaskDrawerContext.Provider value={{ openTask }}>
      {children}
      <TaskDetailDrawer
        taskId={taskId}
        initialTab={initialTab}
        onClose={close}
      />
    </TaskDrawerContext.Provider>
  );
}

export const useTaskDrawer = () => useContext(TaskDrawerContext);
