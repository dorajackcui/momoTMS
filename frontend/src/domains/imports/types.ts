export type ImportBatchSummary = {
  import_batch_id: number;
  project_id: number;
  created_at: string;
  meta: Record<string, unknown>;
  rows_scanned: number;
  files_scanned: number;
  issues: number;
};
