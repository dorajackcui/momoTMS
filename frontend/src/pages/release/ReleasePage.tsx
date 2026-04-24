import { useDeferredValue, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { useAppShell } from "@/app/shell/AppShellContext";
import { getBranchRows } from "@/domains/branches/api";
import { queryKeys, invalidateProject } from "@/shared/api/queryKeys";
import { VariantGrid } from "@/shared/ui/VariantGrid";
import { EditPanel } from "@/shared/ui/EditPanel";
import { TrashPanel } from "@/shared/ui/TrashPanel";
import type { JobDetail } from "@/domains/jobs/types";

import styles from "@/pages/release/ReleasePage.module.css";

type ReleaseTab = "browse" | "edit" | "trash";

export function ReleasePage() {
  const shell = useAppShell();
  const queryClient = useQueryClient();
  const projectId = shell.projectId!;
  const schema = shell.bootstrap!.schema;
  const branchRef = "rel/current";

  const [tab, setTab] = useState<ReleaseTab>("browse");
  const [stateFilter, setStateFilter] = useState<"active" | "orphan" | "all">("active");
  const [columnFilters, setColumnFilters] = useState<Record<string, string>>({});
  const [columnToggles, setColumnToggles] = useState({ translations: true, remarks: false, pivot: false });
  const [page, setPage] = useState(1);

  const deferredFilters = useDeferredValue(columnFilters);
  const browseParams = {
    search_business_key: deferredFilters["search_business_key"] || undefined,
    search_source: deferredFilters["search_source"] || undefined,
    page,
    page_size: 100,
  };

  const browseQuery = useQuery({
    queryKey: queryKeys.branchRows(projectId, branchRef, browseParams),
    queryFn: () => getBranchRows(projectId, branchRef, browseParams),
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
          pageSize={100}
          onPageChange={setPage}
          columnFilters={columnFilters}
          onColumnFilterChange={(col, val) => { setColumnFilters((p) => ({ ...p, [col]: val })); setPage(1); }}
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
          schema={schema}
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
