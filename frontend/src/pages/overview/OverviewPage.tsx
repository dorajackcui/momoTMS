import { useDeferredValue, useState } from "react";

import { useQuery } from "@tanstack/react-query";
import { DataGrid, type Column } from "react-data-grid";

import { useAppShell } from "@/app/shell/AppShellContext";
import { getBranchCompare, getDevBranchDetail } from "@/domains/branches/api";
import { queryKeys } from "@/shared/api/queryKeys";
import { formatNumber } from "@/shared/lib/format";
import {
  Badge,
  EmptyState,
  InlineNotice,
  Panel,
  StatGrid,
  ui,
} from "@/shared/ui/primitives";
import {
  buildOverviewRowsFromCompare,
  buildOverviewRowsFromDevBranch,
  filterOverviewRows,
  overviewColumnKeys,
  type OverviewColumnPreset,
  type OverviewGridRow,
  type OverviewLifecycleFilter,
} from "@/pages/overview/model";

import styles from "@/pages/overview/OverviewPage.module.css";

const SAMPLE_PAGE_SIZE = 60;

export function OverviewPage() {
  const shell = useAppShell();
  const [businessKeyFilter, setBusinessKeyFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [lifecycleFilter, setLifecycleFilter] =
    useState<OverviewLifecycleFilter>("all");
  const [columnPreset, setColumnPreset] =
    useState<OverviewColumnPreset>("translation");

  const deferredBusinessKey = useDeferredValue(businessKeyFilter);
  const deferredSource = useDeferredValue(sourceFilter);
  const branchOptions = Array.from(
    new Set([
      "rel/current",
      ...(shell.bootstrap?.dev_branches || []).map((branch) => branch.branch_ref),
      ...(shell.branchSummary?.branches || []).map((branch) => branch.branch_ref),
    ]),
  );
  const defaultDevBranch =
    shell.bootstrap?.candidate_dev_branch?.branch_ref ||
    shell.bootstrap?.dev_branches[0]?.branch_ref ||
    null;
  const selectedBranch = shell.branchRef || defaultDevBranch || "rel/current";
  const selectedVersion = selectedBranch.startsWith("dev/")
    ? selectedBranch.slice(4)
    : null;

  const devBranchQuery = useQuery({
    queryKey:
      shell.projectId && selectedVersion
        ? queryKeys.devBranchDetail(shell.projectId, selectedVersion)
        : ["dev-branch-detail", "idle"],
    queryFn: () => getDevBranchDetail(shell.projectId!, selectedVersion!),
    enabled: Boolean(shell.projectId && selectedVersion),
    initialData:
      selectedBranch === shell.bootstrap?.candidate_dev_branch?.branch_ref
        ? shell.bootstrap?.candidate_dev_branch
        : undefined,
  });

  const relCompareQuery = useQuery({
    queryKey:
      shell.projectId && selectedBranch === "rel/current" && defaultDevBranch
        ? queryKeys.branchCompare(shell.projectId, {
            base_branch_ref: "rel/current",
            target_branch_ref: defaultDevBranch,
            lang: shell.lang,
            page: 1,
            page_size: SAMPLE_PAGE_SIZE,
          })
        : ["branch-compare", "idle"],
    queryFn: () =>
      getBranchCompare(shell.projectId!, {
        base_branch_ref: "rel/current",
        target_branch_ref: defaultDevBranch!,
        lang: shell.lang,
        page: 1,
        page_size: SAMPLE_PAGE_SIZE,
      }),
    enabled: Boolean(
      shell.projectId &&
        shell.lang &&
        selectedBranch === "rel/current" &&
        defaultDevBranch,
    ),
  });

  const selectedSummary = shell.branchSummary?.branches.find(
    (branch) => branch.branch_ref === selectedBranch,
  );

  const rawRows =
    selectedVersion && devBranchQuery.data
      ? buildOverviewRowsFromDevBranch(devBranchQuery.data)
      : selectedBranch === "rel/current" && relCompareQuery.data
        ? buildOverviewRowsFromCompare(relCompareQuery.data)
        : [];

  const rows = filterOverviewRows(rawRows, {
    businessKey: deferredBusinessKey,
    source: deferredSource,
    lifecycle: lifecycleFilter,
  });

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

  return (
    <div className={styles.stack}>
      <Panel
        kicker="Overview"
        title={selectedBranch}
        description="Scan one selected branch like a workbook, then open full variant history in the right drawer."
        actions={
          <div className={ui.toolbar}>
            {selectedSummary?.is_candidate_release ? (
              <Badge tone="accent">candidate</Badge>
            ) : null}
            {selectedBranch === "rel/current" ? (
              <Badge tone="info">summary mode</Badge>
            ) : null}
          </div>
        }
      >
        <StatGrid
          items={[
            {
              label: "branch rows",
              value: formatNumber(rawRows.length),
              hint:
                selectedBranch === "rel/current"
                  ? "sampled rows from compare"
                  : "active rows from dev detail",
            },
            {
              label: "entry count",
              value: formatNumber(selectedSummary?.entry_count || rawRows.length),
              hint: "branch summary count",
            },
            {
              label: "filtered rows",
              value: formatNumber(rows.length),
              hint: "current client-side filters",
            },
          ]}
        />
        <div className={styles.filters}>
          <label className={ui.field}>
            <span className={ui.fieldLabel}>Branch</span>
            <select
              className={ui.select}
              value={selectedBranch}
              onChange={(event) => shell.setBranchRef(event.target.value)}
              data-testid="overview-branch-select"
            >
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
              onChange={(event) => setBusinessKeyFilter(event.target.value)}
              placeholder="Search key"
            />
          </label>
          <label className={ui.field}>
            <span className={ui.fieldLabel}>Source text</span>
            <input
              className={ui.input}
              value={sourceFilter}
              onChange={(event) => setSourceFilter(event.target.value)}
              placeholder="Search source"
            />
          </label>
          <label className={ui.field}>
            <span className={ui.fieldLabel}>Lifecycle</span>
            <select
              className={ui.select}
              value={lifecycleFilter}
              onChange={(event) =>
                setLifecycleFilter(event.target.value as OverviewLifecycleFilter)
              }
            >
              <option value="all">All rows</option>
              <option value="active">Active only</option>
              <option value="sampled">Sampled only</option>
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
        </div>
      </Panel>

      {selectedBranch === "rel/current" ? (
        <InlineNotice tone="warning" title="`rel/current` uses sampled summary mode">
          The current APIs do not expose a full release-detail spreadsheet. This page
          shows branch KPIs plus sampled active rows against {defaultDevBranch || "the selected dev branch"}.
        </InlineNotice>
      ) : null}

      {devBranchQuery.isError ? (
        <InlineNotice tone="error" title="Failed to load branch detail">
          {devBranchQuery.error instanceof Error
            ? devBranchQuery.error.message
            : "Request failed."}
        </InlineNotice>
      ) : null}

      {relCompareQuery.isError ? (
        <InlineNotice tone="error" title="Failed to load sampled rows">
          {relCompareQuery.error instanceof Error
            ? relCompareQuery.error.message
            : "Request failed."}
        </InlineNotice>
      ) : null}

      <Panel
        kicker="Grid"
        title="Branch spreadsheet"
        description="Frozen key columns, schema-driven translation and remark columns, and drawer drill-down on click."
        testId="overview-page"
      >
        {rows.length === 0 ? (
          <EmptyState
            title="No rows to show"
            body="Try a different branch or relax the current filters."
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
      key: "branchBadge",
      name: "branch",
      width: 170,
      renderCell: ({ row }) => <span className={styles.pill}>{row.branchBadge}</span>,
    },
  );

  return columns.filter((column) => visibleKeys.includes(column.key));
}
