export type BindingSummary = {
  branch_ref: string;
  created_at: string;
  updated_at: string;
};

export type EntryVariantView = {
  variant_id: number;
  entry_id: number;
  project_id: number;
  business_key: string;
  file_name: string | null;
  source: string;
  translations: Record<string, string | null>;
  remarks: Record<string, string | null>;
  bindings: BindingSummary[];
  trashed_at: string | null;
  trash_until: string | null;
  restored_at: string | null;
  created_at: string;
  updated_at: string;
};

export type DevBranchSummary = {
  project_id: number;
  version: string;
  version_series: string;
  branch_ref: string;
  is_candidate_release: boolean;
  entry_count: number;
  created_at: string;
  promoted_at: string | null;
};

export type DevBranchDetail = DevBranchSummary & {
  entries: EntryVariantView[];
};

export type BranchSummaryItem = {
  branch_ref: string;
  entry_count: number;
  status_counts: Record<string, number>;
  version_series: string | null;
  is_candidate_release: boolean | null;
};

export type BranchListResponse = {
  branches: BranchSummaryItem[];
};

export type BranchSide = {
  branch_ref: string;
  variant_id: number;
  file_name: string | null;
  source: string;
  translations: Record<string, string | null>;
  remarks: Record<string, string | null>;
};

export type TranslationPriorityRow = {
  business_key: string;
  priority_status: string;
  state: string;
  diff_categories: string[];
  file_name: string | null;
  source: string;
  target_text: string;
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
  priority_rows: TranslationPriorityRow[];
  total_rows: number;
  total_priority_rows: number;
  page: number;
  page_size: number;
};

export type BranchQueueResponse = {
  target_branch_ref: string;
  lang: string | null;
  status_counts: Record<string, number>;
  rows: TranslationPriorityRow[];
  total_rows: number;
  page: number;
  page_size: number;
};

export type MasterQueryRow = {
  business_key: string;
  branch_ref: string;
  variant_id: number;
  file_name: string | null;
  source: string;
  translations: Record<string, string | null>;
  remarks: Record<string, string | null>;
};

export type MasterEntryResponse = {
  business_key: string;
  entry_id: number;
  results: MasterQueryRow[];
};

export type MasterSearchResponse = {
  source: string;
  results: MasterQueryRow[];
};

export type BranchReplacePreview = {
  source_branch_ref: string;
  target_branch_ref: string;
  target_entry_count: number;
  added_to_target_count: number;
  already_in_target_count: number;
  removed_from_target_count: number;
  cleanup_binding_count: number;
  report_rows: Array<Record<string, unknown>>;
};

export type BranchMutationChange = {
  business_key: string;
  source?: string | null;
  translations_by_lang: Record<string, string>;
  remarks_by_key: Record<string, string>;
  file_name?: string | null;
};

export type BranchMutationInput =
  | {
      kind: "direct";
      changes: BranchMutationChange[];
    }
  | {
      kind: "import_batch";
      import_batch_id: number;
      mark_as_candidate_release: boolean;
    };
