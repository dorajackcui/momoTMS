import { Navigate, createBrowserRouter } from "react-router-dom";

import { AppShell } from "@/app/shell/AppShell";
import { useAppShell } from "@/app/shell/AppShellContext";
import { BranchOpsPage } from "@/pages/branches/BranchOpsPage";
import { IntakePage } from "@/pages/intake/IntakePage";
import { NotFoundPage } from "@/pages/not-found/NotFoundPage";
import { OverviewPage } from "@/pages/overview/OverviewPage";
import { ProjectPage } from "@/pages/project/ProjectPage";
import { RunsPage } from "@/pages/runs/RunsPage";
import { VariantsPage } from "@/pages/variants/VariantsPage";

function IndexRedirect() {
  const shell = useAppShell();
  if (shell.projectsLoading) {
    return null;
  }
  return (
    <Navigate
      replace
      to={shell.buildHref(shell.hasProjects ? "/app/overview" : "/app/project")}
    />
  );
}

export const router = createBrowserRouter([
  {
    path: "/app",
    element: <AppShell />,
    children: [
      { index: true, element: <IndexRedirect /> },
      { path: "overview", element: <OverviewPage /> },
      { path: "intake", element: <IntakePage /> },
      { path: "branches", element: <BranchOpsPage /> },
      { path: "runs", element: <RunsPage /> },
      { path: "variants", element: <VariantsPage /> },
      { path: "project", element: <ProjectPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
