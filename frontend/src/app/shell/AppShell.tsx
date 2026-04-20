import { useEffect, useState } from "react";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { NavLink, Outlet, useLocation, useSearchParams } from "react-router-dom";

import { getBranchSummary } from "@/domains/branches/api";
import type { BranchListResponse } from "@/domains/branches/types";
import { getProjectState, listProjects } from "@/domains/projects/api";
import type { ProductStateResponse, ProjectSummary } from "@/domains/projects/types";
import { VariantDrawer } from "@/features/variant-drawer/VariantDrawer";
import { queryKeys } from "@/shared/api/queryKeys";
import { cx } from "@/shared/lib/cx";
import { formatNumber } from "@/shared/lib/format";
import {
  clearStoredProjectId,
  getStoredProjectId,
  setStoredProjectId,
} from "@/shared/lib/projectStorage";
import { applySearchPatch, normalizeText, parsePositiveInt } from "@/shared/lib/url";
import {
  InlineNotice,
  LoadingBlock,
  buttonClassName,
  ui,
} from "@/shared/ui/primitives";
import {
  AppShellProvider,
  type AppNotice,
  type NoticeTone,
} from "@/app/shell/AppShellContext";

import styles from "@/app/shell/AppShell.module.css";

const NAV_ITEMS = [
  {
    path: "/app/overview",
    label: "Overview",
    hint: "Spreadsheet-like branch surface with variant drill-down.",
  },
  {
    path: "/app/intake",
    label: "Intake",
    hint: "Upload folders, confirm mappings, and inspect import batches.",
  },
  {
    path: "/app/branches",
    label: "Branch Ops",
    hint: "Scope catalog, lookup, apply, replace, and trash flows.",
  },
  {
    path: "/app/runs",
    label: "Runs",
    hint: "Grouped job history with preview rows and artifacts.",
  },
  {
    path: "/app/variants",
    label: "Variants",
    hint: "Orphan history, timeline inspection, and restore actions.",
  },
  {
    path: "/app/project",
    label: "Project",
    hint: "Schema summary, release context, dev branches, and create project.",
  },
];

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

  const branchSummaryQuery = useQuery({
    queryKey:
      resolvedProjectId && resolvedLang
        ? queryKeys.branchSummary(resolvedProjectId, resolvedLang)
        : ["branch-summary", "idle"],
    queryFn: () => getBranchSummary(resolvedProjectId!, resolvedLang),
    enabled: resolvedProjectId !== null && Boolean(resolvedLang),
  });

  const requestedBranch = normalizeText(searchParams.get("branch"));
  const resolvedBranchRef = resolveBranchRef(
    requestedBranch,
    projectStateQuery.data,
    branchSummaryQuery.data,
  );
  const allowOverviewProjectWideBranchless =
    location.pathname === "/app/overview" && requestedBranch === null;

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
        : branchSummaryQuery.error instanceof Error
          ? branchSummaryQuery.error.message
          : null;

  const shellLoading =
    projectsQuery.isLoading ||
    projectStateQuery.isLoading ||
    (Boolean(resolvedProjectId && resolvedLang) && branchSummaryQuery.isLoading);
  const drawerOpen = Boolean(resolvedProjectId && businessKey);

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
    branchSummary: branchSummaryQuery.data || null,
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
        if (resolvedLang) {
          await queryClient.invalidateQueries({
            queryKey: queryKeys.branchSummary(resolvedProjectId, resolvedLang),
          });
        }
      }
    },
  };

  return (
    <AppShellProvider value={shellValue}>
      <div
        className={cx(styles.shell, drawerOpen && styles.shellDrawerOpen)}
        data-testid="product-app"
      >
        <aside className={styles.sidebar}>
          <section className={styles.sidebarCard}>
            <div className={styles.brand}>
              <p className={ui.eyebrow}>Momo TMS</p>
              <h1 className={styles.brandTitle}>Operator Surface</h1>
              <p className={styles.brandBody}>
                Project-first UI for overview scanning, intake, branch decisions,
                async runs, and variant inspection.
              </p>
            </div>
          </section>

          <nav className={styles.nav}>
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.path}
                to={shellValue.buildHref(item.path, {})}
                className={({ isActive }) =>
                  cx(styles.navLink, isActive && styles.navLinkActive)
                }
              >
                <span className={styles.navLabel}>{item.label}</span>
                <span className={styles.navHint}>{item.hint}</span>
              </NavLink>
            ))}
          </nav>

          <section className={styles.sidebarCard}>
            <p className={ui.eyebrow}>Runtime</p>
            <div className={ui.keyValues}>
              <div className={ui.keyValueRow}>
                <span className={ui.keyValueLabel}>projects</span>
                <span>{formatNumber(projects.length)}</span>
              </div>
              <div className={ui.keyValueRow}>
                <span className={ui.keyValueLabel}>selected project</span>
                <span>{resolvedProjectId || "-"}</span>
              </div>
              <div className={ui.keyValueRow}>
                <span className={ui.keyValueLabel}>branch</span>
                <span>{resolvedBranchRef || "-"}</span>
              </div>
            </div>
          </section>
        </aside>

        <main className={styles.main}>
          <header className={styles.topbar}>
            <div className={styles.topbarCopy}>
              <p className={ui.eyebrow}>
                {location.pathname.replace("/app/", "") || "app"}
              </p>
              <h1 className={styles.pageTitle}>
                {projectStateQuery.data?.project.name || "Project workspace"}
              </h1>
              <p className={styles.pageBody}>
                URL state is canonical for project, language, branch, tab, job, and
                business key context.
              </p>
            </div>
            <div className={styles.controls}>
              <label className={styles.fieldGroup}>
                <span className={ui.fieldLabel}>Project</span>
                <select
                  className={ui.select}
                  value={resolvedProjectId || ""}
                  onChange={(event) => shellValue.setProjectId(Number(event.target.value))}
                  disabled={projects.length === 0}
                  data-testid="shell-project-select"
                >
                  {projects.length === 0 ? (
                    <option value="">No projects</option>
                  ) : null}
                  {projects.map((project) => (
                    <option key={project.project_id} value={project.project_id}>
                      {project.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className={styles.fieldGroup}>
                <span className={ui.fieldLabel}>Language</span>
                <select
                  className={ui.select}
                  value={resolvedLang}
                  onChange={(event) => shellValue.setLang(event.target.value)}
                  disabled={availableLangs.length === 0}
                  data-testid="shell-language-select"
                >
                  {availableLangs.length === 0 ? (
                    <option value="">No language</option>
                  ) : null}
                  {availableLangs.map((lang) => (
                    <option key={lang} value={lang}>
                      {lang}
                    </option>
                  ))}
                </select>
              </label>
              <div className={styles.fieldGroup}>
                <span className={ui.fieldLabel}>Actions</span>
                <button
                  className={buttonClassName("secondary")}
                  onClick={() => void shellValue.refreshShell()}
                >
                  Refresh shell
                </button>
              </div>
            </div>
          </header>

          {notice ? (
            <InlineNotice
              tone={notice.tone}
              title="Workspace message"
              action={
                <button className={styles.noticeClose} onClick={shellValue.clearNotice}>
                  Dismiss
                </button>
              }
            >
              {notice.message}
            </InlineNotice>
          ) : null}

          {shellError ? (
            <InlineNotice tone="error" title="Failed to load shell data">
              {shellError}
            </InlineNotice>
          ) : null}

          {shellLoading ? <LoadingBlock label="Refreshing project shell..." /> : null}

          <div className={styles.content}>
            <Outlet />
          </div>
        </main>

        {location.pathname !== "/app/variants" ? (
          <VariantDrawer
            projectId={resolvedProjectId}
            businessKey={businessKey}
            onClose={() => shellValue.setBusinessKey(null)}
          />
        ) : null}
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
  branchSummary: BranchListResponse | undefined,
) {
  if (requestedBranchRef === "rel/current") {
    return requestedBranchRef;
  }
  const branchRefs = new Set<string>(["rel/current"]);
  if (bootstrap?.candidate_dev_branch?.branch_ref) {
    branchRefs.add(bootstrap.candidate_dev_branch.branch_ref);
  }
  bootstrap?.dev_branches.forEach((branch) => branchRefs.add(branch.branch_ref));
  branchSummary?.branches.forEach((branch) => branchRefs.add(branch.branch_ref));
  if (requestedBranchRef && branchRefs.has(requestedBranchRef)) {
    return requestedBranchRef;
  }
  if (!bootstrap && !branchSummary) {
    return null;
  }
  return (
    bootstrap?.candidate_dev_branch?.branch_ref ||
    bootstrap?.dev_branches[0]?.branch_ref ||
    "rel/current"
  );
}
