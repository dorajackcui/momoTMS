import type { ProjectSchema } from "@/domains/projects/types";

export type ImportBatchSummary = {
  import_batch_id: number;
  project_id: number;
  created_at: string;
  meta: Record<string, unknown>;
  rows_scanned: number;
  files_scanned: number;
  issues: number;
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
  suggested_mapping?: ImportSheetSuggestedMapping;
  missing_targets: string[];
  auto_match_ready: boolean;
};

export type ImportUploadPreview = {
  upload_session_id: string;
  schema: ProjectSchema;
  file_count: number;
  sheet_count: number;
  sheet_previews: ImportSheetPreview[];
};
