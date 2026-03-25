import { fetchJson, postFolderForm } from "@/shared/api/http";

import type { ImportBatchSummary, ImportUploadPreview } from "@/domains/imports/types";
import type { JobDetail, ReportPayload } from "@/domains/jobs/types";

export function previewImportUpload(projectId: number, files: File[]) {
  return postFolderForm<ImportUploadPreview>(
    `/api/projects/${projectId}/imports/upload-folder/preview`,
    files,
  );
}

export function confirmImportUpload(
  projectId: number,
  uploadSessionId: string,
  columnMappingJson: string | null,
) {
  return fetchJson<JobDetail>(`/api/projects/${projectId}/imports/upload-folder`, {
    method: "POST",
    body: JSON.stringify({
      upload_session_id: uploadSessionId,
      column_mapping_json: columnMappingJson,
    }),
  });
}

export function getImports(projectId: number) {
  return fetchJson<ImportBatchSummary[]>(`/api/projects/${projectId}/imports`);
}

export function getImportReport(projectId: number, importBatchId: number) {
  return fetchJson<ReportPayload>(
    `/api/projects/${projectId}/imports/${importBatchId}/report`,
  );
}
