import { useDeferredValue, useEffect, useState } from "react";

import { useQuery } from "@tanstack/react-query";
import { DataGrid, type Column } from "react-data-grid";
import { useSearchParams } from "react-router-dom";

import { useAppShell } from "@/app/shell/AppShellContext";
import { getProjectVariants } from "@/domains/variants/api";
import { queryKeys } from "@/shared/api/queryKeys";
import { formatNumber } from "@/shared/lib/format";
import { normalizeText } from "@/shared/lib/url";
import {
  Badge,
  EmptyState,
  InlineNotice,
  Panel,
  StatGrid,
  buttonClassName,
  ui,
} from "@/shared/ui/primitives";
import {
  buildOverviewRowsFromProjectVariants,
  overviewColumnKeys,
  type OverviewColumnPreset,
  type OverviewGridRow,
  type OverviewLifecycleFilter,
} from "@/pages/overview/model";

import styles from "@/pages/overview/OverviewPage.module.css";

const ALL_BRANCHES_VALUE = "__all__";
const PAGE_SIZE = 100;

export function OverviewPage() {
  const shell = useAppShell();
  const [searchParams] = useSearchParams();
  const [businessKeyFilter, setBusinessKeyFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [lifecycleFilter, setLifecycleFilter] =
    useState<OverviewLifecycleFilter>("active");
  const [columnPreset, setColumnPreset] =
    useState<OverviewColumnPreset>("translation");
  const requestedBranchRef = normalizeText(searchParams.get("branch"));
  const [branchFilter, setBranchFilter] = useState(
    requestedBranchRef || ALL_BRANCHES_VALUE,
  );
  const [page, setPage] = useState(1);
  useEffect(() => {
    setBranchFilter(requestedBranchRef || ALL_BRANCHES_VALUE);
    setPage(1);
  }, [requestedBranchRef]);

  const deferredBusinessKey = useDeferredValue(businessKeyFilter);
  const deferredSource = useDeferredValue(sourceFilter);
  const branchOptions = Array.from(
    new Set([
      "rel/current",
      ...(shell.bootstrap?.dev_branches || []).map((branch) => branch.branch_ref),
      ...(shell.branchSummary?.branches || []).map((branch) => branch.branch_ref),
    ]),
  );
  const effectiveBranchFilter =
    lifecycleFilter === "orphan" || branchFilter === ALL_BRANCHES_VALUE
      ? undefined
      : branchFilter;

  const variantsQuery = useQuery({
    queryKey:
      shell.projectId !== null
        ? queryKeys.projectVariants(shell.projectId, {
            state: lifecycleFilter,
            branch_ref: effectiveBranchFilter ? [effectiveBranchFilter] : undefined,
            search_business_key: deferredBusinessKey || undefined,
            search_source: deferredSource || undefined,
            page,
            page_size: PAGE_SIZE,
          })
        : ["project-variants", "idle"],
    queryFn: () =>
      getProjectVariants(shell.projectId!, {
        state: lifecycleFilter,
        branch_ref: effectiveBranchFilter ? [effectiveBranchFilter] : undefined,
        search_business_key: deferredBusinessKey || undefined,
        search_source: deferredSource || undefined,
        page,
        page_size: PAGE_SIZE,
      }),
    enabled: shell.projectId !== null,
  });
  const rows = variantsQuery.data
    ? buildOverviewRowsFromProjectVariants(variantsQuery.data)
    : [];

  if (!shell.hasProjects || !shell.projectId || !shell.bootstrap) {
    return (
      <Panel
        kicker="Overview"
        title="Project-first overview"
        description="Create or select a project to open the new spreadsheet surface."
        testId="overview-page"
      >
        <EmptyState
          title="No active project"
          body="The overview becomes available once a project exists and the shell has resolved the project-scoped context."
        />
      </Panel>
    );
  }

  const columns = buildColumns(
    shell.bootstrap.schema,
    columnPreset,
    overviewColumnKeys(shell.bootstrap.schema, columnPreset),
    (businessKey) => shell.setBusinessKey(businessKey),
  );
  const totalRows = variantsQuery.data?.total_rows || 0;
  const totalPages = Math.max(1, Math.ceil(totalRows / PAGE_SIZE));

  return (
    <div className={styles.stack}>
      <Panel
        kicker="Overview"
        title={
          effectiveBranchFilter ? effectiveBranchFilter : "Project-wide variant workspace"
        }
        description="Scan active or orphan variants through one project-scoped grid, then open full variant history in the right drawer."
        actions={
          <div className={ui.toolbar}>
            {lifecycleFilter === "orphan" ? (
              <Badge tone="warning">orphan view</Badge>
            ) : null}
            {!effectiveBranchFilter ? (
              <Badge tone="info">all branches</Badge>
            ) : null}
          </div>
        }
      >
        <StatGrid
          items={[
            {
              label: "matched rows",
              value: formatNumber(totalRows),
              hint:
                effectiveBranchFilter
                  ? "filtered project variants"
                  : "project-wide variant rows",
            },
            {
              label: "loaded page",
              value: formatNumber(rows.length),
              hint: `page ${page} of ${totalPages}`,
            },
            {
              label: "page size",
              value: formatNumber(PAGE_SIZE),
              hint: "server-side pagination",
            },
          ]}
        />
        <div className={styles.filters}>
          <label className={ui.field}>
            <span className={ui.fieldLabel}>Branch filter</span>
            <select
              className={ui.select}
              value={branchFilter}
              onChange={(event) => {
                const nextValue = event.target.value;
                setBranchFilter(nextValue);
                setPage(1);
                shell.setBranchRef(
                  nextValue === ALL_BRANCHES_VALUE ? null : nextValue,
                );
              }}
              data-testid="overview-branch-select"
              disabled={lifecycleFilter === "orphan"}
            >
              <option value={ALL_BRANCHES_VALUE}>All branches</option>
              {branchOptions.map((branch) => (
                <option key={branch} value={branch}>
                  {branch}
                </option>
              ))}
            </select>
          </label>
          <label className={ui.field}>
            <span className={ui.fieldLabel}>Business key</span>
            <input
              className={ui.input}
              value={businessKeyFilter}
              onChange={(event) => {
                setBusinessKeyFilter(event.target.value);
                setPage(1);
              }}
              placeholder="Search key"
            />
          </label>
          <label className={ui.field}>
            <span className={ui.fieldLabel}>Source text</span>
            <input
              className={ui.input}
              value={sourceFilter}
              onChange={(event) => {
                setSourceFilter(event.target.value);
                setPage(1);
              }}
              placeholder="Search source"
            />
          </label>
          <label className={ui.field}>
            <span className={ui.fieldLabel}>State</span>
            <select
              className={ui.select}
              value={lifecycleFilter}
              onChange={(event) => {
                setLifecycleFilter(event.target.value as OverviewLifecycleFilter);
                setPage(1);
              }}
            >
              <option value="active">Active only</option>
              <option value="all">Active + orphan</option>
              <option value="orphan">Orphan only</option>
            </select>
          </label>
          <label className={ui.field}>
            <span className={ui.fieldLabel}>Column preset</span>
            <select
              className={ui.select}
              value={columnPreset}
              onChange={(event) =>
                setColumnPreset(event.target.value as OverviewColumnPreset)
              }
            >
              <option value="core">Core</option>
              <option value="translation">Translation</option>
              <option value="review">Review</option>
            </select>
          </label>
          <div className={ui.field}>
            <span className={ui.fieldLabel}>Page</span>
            <div className={ui.toolbar}>
              <button
                className={buttonClassName("secondary")}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
                disabled={page <= 1}
              >
                Prev
              </button>
              <button
                className={buttonClassName("secondary")}
                onClick={() =>
                  setPage((current) => Math.min(totalPages, current + 1))
                }
                disabled={page >= totalPages}
              >
                Next
              </button>
            </div>
          </div>
        </div>
      </Panel>

      {lifecycleFilter !== "orphan" && !effectiveBranchFilter ? (
        <InlineNotice tone="info" title="Project-wide active view">
          This grid is now backed by the project-scoped variants query. Use a branch
          filter when you want to narrow the active workspace to one binding context.
        </InlineNotice>
      ) : null}

      {variantsQuery.isError ? (
        <InlineNotice tone="error" title="Failed to load project variants">
          {variantsQuery.error instanceof Error ? variantsQuery.error.message : "Request failed."}
        </InlineNotice>
      ) : null}

      <Panel
        kicker="Grid"
        title="Variant workspace"
        description="Schema-driven columns, branch-aware bindings, and drawer drill-down on click."
        testId="overview-page"
      >
        {rows.length === 0 ? (
          <EmptyState
            title="No rows to show"
            body="Try a different state, branch filter, or search query."
          />
        ) : (
          <div className={styles.gridWrap}>
            <DataGrid
              columns={columns}
              rows={rows}
              rowHeight={42}
              headerRowHeight={44}
              rowKeyGetter={(row) => row.id}
              defaultColumnOptions={{
                resizable: true,
              }}
              onCellClick={(args) => shell.setBusinessKey(args.row.businessKey)}
            />
          </div>
        )}
      </Panel>
    </div>
  );
}

function buildColumns(
  schema: { translation_columns: string[]; remark_columns: string[] },
  preset: OverviewColumnPreset,
  visibleKeys: string[],
  onOpenVariant: (businessKey: string) => void,
): Column<OverviewGridRow>[] {
  const columns: Column<OverviewGridRow>[] = [
    {
      key: "businessKey",
      name: "business_key",
      width: 220,
      frozen: true,
      renderCell: ({ row }) => (
        <button
          className={styles.gridCellButton}
          onClick={(event) => {
            event.stopPropagation();
            onOpenVariant(row.businessKey);
          }}
        >
          {row.businessKey}
        </button>
      ),
    },
    {
      key: "fileName",
      name: "file_name",
      width: 180,
      frozen: true,
    },
    {
      key: "source",
      name: "source",
      width: 260,
      frozen: true,
    },
  ];

  if (preset !== "core") {
    for (const lang of schema.translation_columns) {
      columns.push({
        key: `translation:${lang}`,
        name: lang,
        width: 180,
        renderCell: ({ row }) => row.translations[lang] || "",
      });
    }
  }

  if (preset === "review") {
    for (const key of schema.remark_columns) {
      columns.push({
        key: `remark:${key}`,
        name: `remark:${key}`,
        width: 180,
        renderCell: ({ row }) => row.remarks[key] || "",
      });
    }
  }

  columns.push(
    {
      key: "statusSummary",
      name: "status",
      width: 160,
      renderCell: ({ row }) => <span className={styles.pill}>{row.statusSummary}</span>,
    },
    {
      key: "branchesSummary",
      name: "branches",
      width: 170,
      renderCell: ({ row }) => <span className={styles.pill}>{row.branchesSummary}</span>,
    },
  );

  return columns.filter((column) => visibleKeys.includes(column.key));
}
