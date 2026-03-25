export type AppRoute =
  | "overview"
  | "compare"
  | "queue"
  | "master"
  | "imports"
  | "inspection"
  | "project-new";

export type ProjectSummary = {
  project_id: number;
  name: string;
  is_default: boolean;
  created_at: string;
};

export type ImportBatchSummary = {
  import_batch_id: number;
  project_id: number;
  created_at: string;
  meta: Record<string, unknown>;
  rows_scanned: number;
  files_scanned: number;
  issues: number;
};

export type JobStageSummary = {
  stage: string;
  elapsed_ms: number;
  meta: Record<string, unknown>;
};

export type JobSummary = {
  job_id: number;
  project_id: number;
  job_type: string;
  status: string;
  input: Record<string, unknown>;
  summary: Record<string, unknown>;
  report_path: string | null;
  artifact_path: string | null;
  error_message: string | null;
  created_at: string;
  finished_at?: string | null;
};

export type JobDetail = {
  job: JobSummary;
  report: { summary: Record<string, unknown>; rows: Array<Record<string, unknown>> };
};

export type ProductBootstrapResponse = {
  project: ProjectSummary;
  schema: { translation_columns: string[]; remark_columns: string[] };
  release_summary: { entry_count: number };
  candidate_dev_branch: { version: string } | null;
  dev_branches: Array<{
    version: string;
    version_series: string;
    is_candidate_release: boolean;
    branch_ref: string;
  }>;
  imports: ImportBatchSummary[];
  jobs: JobSummary[];
};

export type BranchSummaryResponse = {
  branches: Array<{
    branch_ref: string;
    entry_count: number;
    status_counts: Record<string, number>;
    version_series?: string | null;
    is_candidate_release?: boolean | null;
  }>;
};

export type BranchSide = {
  branch_ref: string;
  file_name: string | null;
  source: string;
  translations: Record<string, string>;
  remarks: Record<string, string>;
};

export type BranchCompareRow = {
  business_key: string;
  state: string;
  diff_categories: string[];
  priority_status: string;
  base: BranchSide | null;
  target: BranchSide | null;
};

export type BranchCompareResponse = {
  base_branch_ref: string;
  target_branch_ref: string;
  status_counts: Record<string, number>;
  rows: BranchCompareRow[];
  total_rows: number;
  page: number;
  page_size: number;
};

export type QueueRow = {
  business_key: string;
  priority_status: string;
  state: string;
  diff_categories: string[];
  file_name: string | null;
  source: string;
  target_text: string;
};

export type TranslationQueueResponse = {
  target_branch_ref: string;
  lang: string | null;
  status_counts: Record<string, number>;
  rows: QueueRow[];
  total_rows: number;
  page: number;
  page_size: number;
};

export type MasterRow = {
  business_key: string;
  branch_ref: string;
  file_name: string | null;
  source: string;
  translations: Record<string, string>;
  remarks: Record<string, string>;
};

export type MasterResponse = {
  results: MasterRow[];
};

export type ImportSheetMapping = {
  business_key: string;
  source: string;
  translation_columns: Record<string, string>;
  remark_columns: Record<string, string>;
};

export type ImportSheetSuggestedMapping = {
  business_key?: string;
  source?: string;
  translation_columns?: Record<string, string>;
  remark_columns?: Record<string, string>;
};

export type ImportSheetPreview = {
  sheet_key: string;
  file_path: string;
  derived_file_name: string;
  sheet_name: string;
  available_headers: string[];
  missing_targets: string[];
  auto_match_ready: boolean;
  suggested_mapping?: ImportSheetSuggestedMapping;
};

export type ImportPreview = {
  upload_session_id: string;
  schema: { translation_columns: string[]; remark_columns: string[] };
  file_count: number;
  sheet_count: number;
  sheet_previews: ImportSheetPreview[];
};

export type BranchReplacePreview = Record<string, unknown> & {
  report_rows?: Array<Record<string, unknown>>;
};

export type VariantBindingSummary = {
  branch_ref: string;
  created_at: string;
  updated_at: string;
};

export type EntryVariantInspection = {
  variant_id: number;
  file_name: string | null;
  source: string;
  translations: Record<string, string>;
  remarks: Record<string, string>;
  bindings: VariantBindingSummary[];
  is_orphaned: boolean;
  is_trashed: boolean;
  orphaned_at: string | null;
  trashed_at: string | null;
  trash_until: string | null;
  restored_at: string | null;
  created_at: string;
  updated_at: string;
};

export type EntryVariantsResponse = {
  project_id: number;
  entry_id: number;
  business_key: string;
  variants: EntryVariantInspection[];
};

export type OrphanVariantSummary = {
  project_id: number;
  entry_id: number;
  business_key: string;
  variant_id: number;
  file_name: string | null;
  source: string;
  translations: Record<string, string>;
  remarks: Record<string, string>;
  orphaned_at: string;
  updated_at: string;
};

export type OrphanVariantsResponse = {
  project_id: number;
  results: OrphanVariantSummary[];
};

export type FlashState = {
  message: string;
  error: boolean;
};

export type BranchOption = {
  value: string;
  label: string;
};
