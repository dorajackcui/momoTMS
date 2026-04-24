import { useDeferredValue, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { useAppShell } from "@/app/shell/AppShellContext";
import { getBranchRows, previewBranchReplace, executeBranchReplace } from "@/domains/branches/api";
import type { EffectForecastPreview } from "@/domains/branches/types";
import type { JobDetail } from "@/domains/jobs/types";
import { queryKeys, invalidateProject } from "@/shared/api/queryKeys";
import { buttonClassName, InlineNotice, StatGrid } from "@/shared/ui/primitives";
import { VariantGrid } from "@/shared/ui/VariantGrid";
import { EditPanel } from "@/shared/ui/EditPanel";
import { TrashPanel } from "@/shared/ui/TrashPanel";

import styles from "@/pages/dev/DevPage.module.css";

type DetailTab = "browse" | "edit" | "replace" | "trash";

export function BranchDetail(props: { projectId: number; version: string; onBack: () => void }) {
  const { projectId, version, onBack } = props;
  const shell = useAppShell();
  const queryClient = useQueryClient();
  const branchRef = `dev/${version}`;

  const [tab, setTab] = useState<DetailTab>("browse");
  const [stateFilter, setStateFilter] = useState<"active" | "orphan" | "all">("active");
  const [columnFilters, setColumnFilters] = useState<Record<string, string>>({});
  const [columnToggles, setColumnToggles] = useState({ translations: true, remarks: false, pivot: false });
  const [page, setPage] = useState(1);
  const [replacePreview, setReplacePreview] = useState<EffectForecastPreview | null>(null);

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

  const replacePreviewMut = useMutation({
    mutationFn: () => previewBranchReplace(projectId, branchRef, "rel/current"),
    onSuccess: (data) => setReplacePreview(data),
  });

  const replaceExecMut = useMutation({
    mutationFn: () => executeBranchReplace(projectId, branchRef, "rel/current"),
    onSuccess: async () => {
      await invalidateProject(queryClient, projectId);
      shell.notify("Replace complete", "success");
      setReplacePreview(null);
    },
  });

  async function handleJobCreated(_job: JobDetail) {
    await invalidateProject(queryClient, projectId);
    shell.notify("Operation completed", "success");
    setTab("browse");
  }

  const schema = shell.bootstrap!.schema;

  return (
    <div className={styles.page}>
      <div className={styles.actions}>
        <button className={buttonClassName("ghost")} onClick={onBack}>← Back to list</button>
        <strong>{branchRef}</strong>
      </div>

      <nav style={{ display: "flex", gap: 2 }}>
        {(["browse", "edit", "replace", "trash"] as DetailTab[]).map((t) => (
          <button key={t} className={buttonClassName(tab === t ? "primary" : "ghost")} onClick={() => setTab(t)}>
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
          importBatches={shell.bootstrap?.imports ?? []}
          onJobCreated={handleJobCreated}
        />
      )}

      {tab === "replace" && (
        <div className={styles.page}>
          <p>Replace <strong>{branchRef}</strong> → <strong>rel/current</strong></p>
          {!replacePreview && (
            <button className={buttonClassName("secondary")} disabled={replacePreviewMut.isPending} onClick={() => replacePreviewMut.mutate()}>
              {replacePreviewMut.isPending ? "Loading preview..." : "Preview Replace"}
            </button>
          )}
          {replacePreviewMut.isError && <InlineNotice tone="error">{String(replacePreviewMut.error)}</InlineNotice>}
          {replacePreview && (
            <>
              <StatGrid items={Object.entries(replacePreview.summary).map(([k, v]) => ({ label: k, value: String(v) }))} />
              <table className={styles.table}>
                <thead>
                  <tr>{replacePreview.rows.length > 0 && Object.keys(replacePreview.rows[0]).map((k) => <th key={k}>{k}</th>)}</tr>
                </thead>
                <tbody>
                  {replacePreview.rows.slice(0, 50).map((row, i) => (
                    <tr key={i}>{Object.values(row).map((v, j) => <td key={j}>{String(v ?? "")}</td>)}</tr>
                  ))}
                </tbody>
              </table>
              <button className={buttonClassName("primary")} disabled={replaceExecMut.isPending} onClick={() => replaceExecMut.mutate()}>
                {replaceExecMut.isPending ? "Replacing..." : "Execute Replace"}
              </button>
            </>
          )}
          {replaceExecMut.isError && <InlineNotice tone="error">{String(replaceExecMut.error)}</InlineNotice>}
        </div>
      )}

      {tab === "trash" && (
        <TrashPanel
          projectId={projectId}
          branchRef={branchRef}
          showProjectTrash={false}
          onJobCreated={handleJobCreated}
        />
      )}
    </div>
  );
}
