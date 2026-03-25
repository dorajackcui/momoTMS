import { postFolderForm } from "@/shared/api/http";

import type { JobDetail } from "@/domains/jobs/types";

export function runFillUpload(projectId: number, lang: string, files: File[]) {
  return postFolderForm<JobDetail>(
    `/api/projects/${projectId}/fill/upload-folder`,
    files,
    { lang },
  );
}

export function runQaUpload(projectId: number, lang: string, files: File[]) {
  return postFolderForm<JobDetail>(
    `/api/projects/${projectId}/qa/upload-folder`,
    files,
    { lang },
  );
}
