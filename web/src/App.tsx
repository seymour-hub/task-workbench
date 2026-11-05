import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import { loadPrivateExtensions } from "./lib/extensions";
import { TaskDrawerProvider } from "./components/tasks/TaskDrawerContext";
import DashboardPage from "./pages/DashboardPage";
import TasksPage from "./pages/TasksPage";
import BoardPage from "./pages/BoardPage";
import ProjectsPage from "./pages/ProjectsPage";
import ProjectDetailPage from "./pages/ProjectDetailPage";
import CalendarPage from "./pages/CalendarPage";
import TeamPage from "./pages/TeamPage";
import StatsPage from "./pages/StatsPage";
import FilesPage from "./pages/FilesPage";
import NotificationsPage from "./pages/NotificationsPage";
import SettingsPage from "./pages/SettingsPage";
import InboxPage from "./pages/InboxPage";

export default function App() {
  const privateRoutes = loadPrivateExtensions().routes;
  return (
    <TaskDrawerProvider>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<DashboardPage />} />
          <Route path="tasks" element={<TasksPage />} />
          <Route path="board" element={<BoardPage />} />
          <Route path="projects" element={<ProjectsPage />} />
          <Route path="projects/:projectId" element={<ProjectDetailPage />} />
          <Route path="calendar" element={<CalendarPage />} />
          <Route path="team" element={<TeamPage />} />
          <Route path="stats" element={<StatsPage />} />
          <Route path="files" element={<FilesPage />} />
          <Route path="notifications" element={<NotificationsPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="inbox" element={<InboxPage />} />
          {privateRoutes.map((route) => (
            <Route key={route.path} path={route.path} element={route.element} />
          ))}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </TaskDrawerProvider>
  );
}
