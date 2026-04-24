import { fetchJson } from "@/shared/api/http";

import type { ImportBatchSummary } from "@/domains/imports/types";
import type { ReportPayload } from "@/domains/jobs/types";

export function getImports(projectId: number) {
  return fetchJson<ImportBatchSummary[]>(`/api/projects/${projectId}/imports`);
}

export function getImportReport(projectId: number, importBatchId: number) {
  return fetchJson<ReportPayload>(
    `/api/projects/${projectId}/imports/${importBatchId}/report`,
  );
}
