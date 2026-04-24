import { fetchJson, postFolderForm } from "@/shared/api/http";

import type {
  WorkbookExecuteRequest,
  WorkbookExecuteResult,
  WorkbookIntakePreview,
  WorkbookMutationType,
  WorkbookWorkflowKind,
} from "@/domains/workbooks/types";

export function previewWorkbookWorkflow(
  projectId: number,
  files: File[],
  request: {
    workflow_kind: WorkbookWorkflowKind;
    branch_ref?: string;
    mutation_type?: WorkbookMutationType;
  },
) {
  return postFolderForm<WorkbookIntakePreview>(
    `/api/projects/${projectId}/workbooks/intake/preview`,
    files,
    request,
  );
}

export function executeWorkbookWorkflow(
  projectId: number,
  request: WorkbookExecuteRequest,
) {
  return fetchJson<WorkbookExecuteResult>(
    `/api/projects/${projectId}/workbooks/intake/execute`,
    {
      method: "POST",
      body: JSON.stringify(request),
    },
  );
}
