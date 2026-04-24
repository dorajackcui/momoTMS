import type { JobDetail } from "@/domains/jobs/types";

export type WorkbookWorkflowKind =
  | "create_branch"
  | "branch_mutation"
  | "branch_trash"
  | "project_trash";

export type WorkbookMutationType = "content" | "range";

export type WorkbookSheetPreview = {
  sheet_key: string;
  file_path: string;
  sheet_name: string;
  available_headers: string[];
  missing_required_headers: string[];
  sampled_issue_count: number;
};

export type WorkbookIntakePreview = {
  upload_session_id: string;
  workflow_kind: WorkbookWorkflowKind;
  mutation_type: WorkbookMutationType | null;
  file_count: number;
  sheet_count: number;
  missing_required_headers: string[];
  sampled_issue_count: number;
  sheet_previews: WorkbookSheetPreview[];
};

export type WorkbookExecuteRequest = {
  upload_session_id: string;
  workflow_kind: WorkbookWorkflowKind;
  branch_ref?: string;
  mutation_type?: WorkbookMutationType;
};

export type WorkbookExecuteResult = JobDetail;
