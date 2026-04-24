import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getImports, getImportReport } from "@/domains/imports/api";
import { queryKeys } from "@/shared/api/queryKeys";
import { buttonClassName, LoadingBlock, InlineNotice, StatGrid } from "@/shared/ui/primitives";

import styles from "@/pages/dev/DevPage.module.css";

export function ImportBatches(props: { projectId: number; onBack: () => void }) {
  const { projectId, onBack } = props;
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(null);

  const batchesQuery = useQuery({
    queryKey: queryKeys.imports(projectId),
    queryFn: () => getImports(projectId),
  });

  const reportQuery = useQuery({
    queryKey: queryKeys.importReport(projectId, selectedBatchId!),
    queryFn: () => getImportReport(projectId, selectedBatchId!),
    enabled: selectedBatchId !== null,
  });

  return (
    <div className={styles.page}>
      <button className={buttonClassName("ghost")} onClick={onBack}>← Back to list</button>
      <h2>Import Batches</h2>

      {batchesQuery.isLoading && <LoadingBlock label="Loading batches..." />}
      {batchesQuery.isError && <InlineNotice tone="error">{String(batchesQuery.error)}</InlineNotice>}

      {batchesQuery.data && (
        <table className={styles.table}>
          <thead>
            <tr><th>ID</th><th>Files</th><th>Rows</th><th>Issues</th><th>Created</th><th></th></tr>
          </thead>
          <tbody>
            {batchesQuery.data.map((b) => (
              <tr key={b.import_batch_id}>
                <td>#{b.import_batch_id}</td>
                <td>{b.files_scanned}</td>
                <td>{b.rows_scanned}</td>
                <td>{b.issues}</td>
                <td>{b.created_at}</td>
                <td>
                  <button className={buttonClassName("ghost")} onClick={() => setSelectedBatchId(b.import_batch_id)}>
                    Report
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {selectedBatchId && reportQuery.data && (
        <div>
          <h3>Batch #{selectedBatchId} Report</h3>
          <StatGrid items={Object.entries(reportQuery.data.summary).map(([k, v]) => ({ label: k, value: String(v) }))} />
          <table className={styles.table}>
            <thead>
              <tr>{reportQuery.data.rows.length > 0 && Object.keys(reportQuery.data.rows[0]).map((k) => <th key={k}>{k}</th>)}</tr>
            </thead>
            <tbody>
              {reportQuery.data.rows.slice(0, 20).map((row, i) => (
                <tr key={i}>{Object.values(row).map((v, j) => <td key={j}>{String(v ?? "")}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
