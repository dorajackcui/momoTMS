import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Outlet, useLocation, useSearchParams } from "react-router-dom";

import { getProjectState, listProjects } from "@/domains/projects/api";
import type { ProductStateResponse, ProjectSummary } from "@/domains/projects/types";
import { queryKeys } from "@/shared/api/queryKeys";
import {
  clearStoredProjectId,
  getStoredProjectId,
  setStoredProjectId,
} from "@/shared/lib/projectStorage";
import { applySearchPatch, normalizeText, parsePositiveInt } from "@/shared/lib/url";
import {
  AppShellProvider,
  type AppNotice,
  type NoticeTone,
} from "@/app/shell/AppShellContext";

export function AppShell() {
  const location = useLocation();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [notice, setNotice] = useState<AppNotice>(null);

  const projectsQuery = useQuery({
    queryKey: queryKeys.projects(),
    queryFn: listProjects,
  });

  const projects = projectsQuery.data || [];
  const requestedProjectId = parsePositiveInt(searchParams.get("project"));
  const storedProjectId = getStoredProjectId();
  const resolvedProjectId = resolveProjectId(
    projects,
    requestedProjectId,
    storedProjectId,
  );

  const projectStateQuery = useQuery({
    queryKey: resolvedProjectId
      ? queryKeys.projectState(resolvedProjectId)
      : ["project-state", "idle"],
    queryFn: () => getProjectState(resolvedProjectId!),
    enabled: resolvedProjectId !== null,
  });

  const requestedLang = normalizeText(searchParams.get("lang"));
  const availableLangs = projectStateQuery.data?.schema.translation_columns || [];
  const resolvedLang =
    requestedLang && availableLangs.includes(requestedLang)
      ? requestedLang
      : availableLangs[0] || "";

  const requestedBranch = normalizeText(searchParams.get("branch"));
  const resolvedBranchRef = resolveBranchRef(requestedBranch, projectStateQuery.data);
  const allowOverviewProjectWideBranchless =
    location.pathname === "/app/workspace" && requestedBranch === null;

  const tab = normalizeText(searchParams.get("tab"));
  const jobId = parsePositiveInt(searchParams.get("job"));
  const businessKey = normalizeText(searchParams.get("business_key"));

  useEffect(() => {
    if (!projectsQuery.isSuccess) {
      return;
    }
    if (projects.length === 0) {
      clearStoredProjectId();
      return;
    }
    if (resolvedProjectId && requestedProjectId !== resolvedProjectId) {
      setSearchParams((current) => applySearchPatch(current, { project: resolvedProjectId }), {
        replace: true,
      });
    }
    if (resolvedProjectId) {
      setStoredProjectId(resolvedProjectId);
    }
  }, [
    projects,
    projectsQuery.isSuccess,
    requestedProjectId,
    resolvedProjectId,
    setSearchParams,
  ]);

  useEffect(() => {
    if (!resolvedProjectId || availableLangs.length === 0) {
      return;
    }
    if (requestedLang !== resolvedLang) {
      setSearchParams((current) => applySearchPatch(current, { lang: resolvedLang }), {
        replace: true,
      });
    }
  }, [
    availableLangs.length,
    requestedLang,
    resolvedLang,
    resolvedProjectId,
    setSearchParams,
  ]);

  useEffect(() => {
    if (allowOverviewProjectWideBranchless) {
      return;
    }
    if (!resolvedBranchRef) {
      return;
    }
    if (requestedBranch !== resolvedBranchRef) {
      setSearchParams((current) => applySearchPatch(current, { branch: resolvedBranchRef }), {
        replace: true,
      });
    }
  }, [
    allowOverviewProjectWideBranchless,
    requestedBranch,
    resolvedBranchRef,
    setSearchParams,
  ]);

  const shellError =
    projectsQuery.error instanceof Error
      ? projectsQuery.error.message
      : projectStateQuery.error instanceof Error
        ? projectStateQuery.error.message
        : null;

  const shellLoading = projectsQuery.isLoading || projectStateQuery.isLoading;

  const shellValue = {
    projects,
    projectId: resolvedProjectId,
    lang: resolvedLang,
    branchRef: resolvedBranchRef,
    tab,
    jobId,
    businessKey,
    hasProjects: projects.length > 0,
    bootstrap: projectStateQuery.data || null,
    projectsLoading: projectsQuery.isLoading,
    shellLoading,
    shellError,
    notice,
    buildHref: (
      pathname: string,
      patch: Record<string, string | number | boolean | null | undefined> = {},
    ) => {
      const next = applySearchPatch(searchParams, patch);
      const search = next.toString();
      return { pathname, search: search ? `?${search}` : "" };
    },
    setProjectId: (projectId: number) => {
      setSearchParams(
        (current) =>
          applySearchPatch(current, {
            project: projectId,
            lang: null,
            branch: null,
            job: null,
            business_key: null,
          }),
        { replace: false },
      );
      setStoredProjectId(projectId);
    },
    setLang: (lang: string) => {
      setSearchParams((current) => applySearchPatch(current, { lang }), {
        replace: false,
      });
    },
    setBranchRef: (branchRef: string | null) => {
      setSearchParams((current) => applySearchPatch(current, { branch: branchRef }), {
        replace: false,
      });
    },
    setTab: (nextTab: string | null) => {
      setSearchParams((current) => applySearchPatch(current, { tab: nextTab }), {
        replace: false,
      });
    },
    setJobId: (nextJobId: number | null) => {
      setSearchParams((current) => applySearchPatch(current, { job: nextJobId }), {
        replace: false,
      });
    },
    setBusinessKey: (nextBusinessKey: string | null) => {
      setSearchParams(
        (current) => applySearchPatch(current, { business_key: nextBusinessKey }),
        {
          replace: false,
        },
      );
    },
    notify: (message: string, tone: NoticeTone = "info") => {
      setNotice({ message, tone });
    },
    clearNotice: () => {
      setNotice(null);
    },
    refreshShell: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.projects() });
      if (resolvedProjectId) {
        await queryClient.invalidateQueries({
          queryKey: queryKeys.projectState(resolvedProjectId),
        });
      }
    },
  };

  return (
    <AppShellProvider value={shellValue}>
      <div data-testid="product-app">
        <Outlet />
      </div>
    </AppShellProvider>
  );
}

function resolveProjectId(
  projects: ProjectSummary[],
  requestedProjectId: number | null,
  storedProjectId: number | null,
) {
  if (projects.length === 0) {
    return null;
  }
  if (requestedProjectId && projects.some((item) => item.project_id === requestedProjectId)) {
    return requestedProjectId;
  }
  if (storedProjectId && projects.some((item) => item.project_id === storedProjectId)) {
    return storedProjectId;
  }
  return projects[0].project_id;
}

function resolveBranchRef(
  requestedBranchRef: string | null,
  bootstrap: ProductStateResponse | undefined,
) {
  const branchRefs = new Set<string>(["rel/current"]);
  bootstrap?.dev_branches.forEach((branch) => branchRefs.add(branch.branch_ref));
  if (requestedBranchRef && branchRefs.has(requestedBranchRef)) {
    return requestedBranchRef;
  }
  if (!bootstrap) {
    return null;
  }
  return bootstrap.dev_branches[0]?.branch_ref || "rel/current";
}
