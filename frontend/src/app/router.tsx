import { Navigate, createBrowserRouter } from "react-router-dom";

import { AppShell } from "@/app/shell/AppShell";
import { ProjectShell } from "@/app/shell/ProjectShell";
import { useAppShell } from "@/app/shell/AppShellContext";
import { HubPage } from "@/pages/hub/HubPage";
import { WorkspacePage } from "@/pages/workspace/WorkspacePage";
import { ReleasePage } from "@/pages/release/ReleasePage";
import { DevPage } from "@/pages/dev/DevPage";
import { RunsPage } from "@/pages/runs/RunsPage";

function IndexRedirect() {
  const shell = useAppShell();
  if (shell.projectsLoading) return null;
  return (
    <Navigate
      replace
      to={shell.buildHref(shell.hasProjects ? "/app/workspace" : "/app")}
    />
  );
}

export const router = createBrowserRouter([
  {
    path: "/app",
    element: <AppShell />,
    children: [
      { index: true, element: <HubPage /> },
      {
        element: <ProjectShell />,
        children: [
          { path: "workspace", element: <WorkspacePage /> },
          { path: "release", element: <ReleasePage /> },
          { path: "dev", element: <DevPage /> },
          { path: "runs", element: <RunsPage /> },
        ],
      },
    ],
  },
]);
