import { useDeferredValue, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { useAppShell } from "@/app/shell/AppShellContext";
import { getProjectVariantFilterOptions, queryProjectVariants } from "@/domains/variants/api";
import { queryKeys, invalidateProject } from "@/shared/api/queryKeys";
import { VariantGrid } from "@/shared/ui/VariantGrid";
import { EditPanel } from "@/shared/ui/EditPanel";
import { TrashPanel } from "@/shared/ui/TrashPanel";
import type { JobDetail } from "@/domains/jobs/types";
import { toApiFilters, type VariantGridFilterState } from "@/shared/ui/variantGridFilters";

import styles from "@/pages/release/ReleasePage.module.css";

type ReleaseTab = "browse" | "edit" | "trash";
const pageSize = 50;

export function ReleasePage() {
  const shell = useAppShell();
  const queryClient = useQueryClient();
  const projectId = shell.projectId!;
  const schema = shell.bootstrap!.schema;
  const branchRef = "rel/current";

  const [tab, setTab] = useState<ReleaseTab>("browse");
  const [stateFilter, setStateFilter] = useState<"active" | "orphan" | "all">("active");
  const [gridFilters, setGridFilters] = useState<VariantGridFilterState>({});
  const [columnToggles, setColumnToggles] = useState({ translations: true, remarks: false, pivot: false });
  const [page, setPage] = useState(1);

  const deferredFilters = useDeferredValue(gridFilters);
  const browseParams = {
    scope: { kind: "branch" as const, branch_ref: branchRef },
    state: stateFilter,
    filters: toApiFilters(deferredFilters),
    page,
    page_size: pageSize,
  };

  const browseQuery = useQuery({
    queryKey: queryKeys.branchRows(projectId, branchRef, browseParams),
    queryFn: () => queryProjectVariants(projectId, browseParams),
    enabled: tab === "browse",
  });

  async function handleJobCreated(_job: JobDetail) {
    await invalidateProject(queryClient, projectId);
    shell.notify("Operation completed", "success");
    setTab("browse");
  }

  return (
    <div>
      <nav className={styles.tabs}>
        {(["browse", "edit", "trash"] as ReleaseTab[]).map((t) => (
          <button key={t} className={`${styles.tab} ${tab === t ? styles.tabActive : ""}`} onClick={() => setTab(t)}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </nav>

      {tab === "browse" && (
        <VariantGrid
          schema={schema}
          rows={browseQuery.data?.rows ?? []}
          totalRows={browseQuery.data?.total_rows ?? 0}
          page={page}
          pageSize={pageSize}
          onPageChange={setPage}
          filters={gridFilters}
          onFiltersChange={(filters) => { setGridFilters(filters); setPage(1); }}
          loadFilterOptions={(targetColumn, optionSearch) =>
            getProjectVariantFilterOptions(projectId, {
              ...browseParams,
              target_column: targetColumn,
              option_search: optionSearch,
              limit: 100,
            })
          }
          stateFilter={stateFilter}
          onStateFilterChange={(s) => { setStateFilter(s); setPage(1); }}
          showStateFilter={false}
          columnToggles={columnToggles}
          onColumnToggleChange={(g, on) => setColumnToggles((p) => ({ ...p, [g]: on }))}
        />
      )}

      {tab === "edit" && (
        <EditPanel
          projectId={projectId}
          branchRef={branchRef}
          allowRange={true}
          onJobCreated={handleJobCreated}
        />
      )}

      {tab === "trash" && (
        <TrashPanel
          projectId={projectId}
          branchRef={branchRef}
          showProjectTrash={true}
          onJobCreated={handleJobCreated}
        />
      )}
    </div>
  );
}
