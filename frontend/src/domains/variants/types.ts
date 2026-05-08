export type VariantBindingSummary = {
  branch_ref: string;
  created_at: string;
  updated_at: string;
};

export type PivotStatus = "init" | "changed" | "reviewed";

export type EntryVariantInspection = {
  variant_id: number;
  file_name: string | null;
  source: string;
  translations: Record<string, string | null>;
  remarks: Record<string, string | null>;
  bindings: VariantBindingSummary[];
  is_orphaned: boolean;
  is_trashed: boolean;
  orphaned_at: string | null;
  trashed_at: string | null;
  pivot_status: PivotStatus;
  pivot_changed_by_branch_ref: string | null;
  pivot_changed_at: string | null;
  pivot_reviewed_at: string | null;
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
  translations: Record<string, string | null>;
  remarks: Record<string, string | null>;
  orphaned_at: string;
  updated_at: string;
};

export type OrphanVariantsResponse = {
  project_id: number;
  results: OrphanVariantSummary[];
};

export type ProjectVariantRow = {
  variant_id: number;
  entry_id: number;
  business_key: string;
  file_name: string | null;
  source: string;
  translations: Record<string, string | null>;
  remarks: Record<string, string | null>;
  bindings: VariantBindingSummary[];
  state: "active" | "orphan";
  orphaned_at: string | null;
  pivot_status: PivotStatus;
  pivot_changed_by_branch_ref: string | null;
  pivot_changed_at: string | null;
  pivot_reviewed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ProjectVariantsResponse = {
  rows: ProjectVariantRow[];
  total_rows: number;
  page: number;
  page_size: number;
};

export type VariantGridColumnRef = {
  kind: "field" | "translation" | "remark";
  name: string;
};

export type VariantGridScope =
  | { kind: "project" }
  | { kind: "branch"; branch_ref: string };

export type VariantGridValueMode = "all" | "include" | "exclude";

export type VariantGridColumnFilter = {
  column: VariantGridColumnRef;
  text?: string | null;
  value_mode?: VariantGridValueMode | null;
  value_search?: string | null;
  values?: Array<string | null>;
};

export type VariantGridQueryRequest = {
  scope: VariantGridScope;
  state?: "active" | "orphan" | "all";
  filters?: VariantGridColumnFilter[];
  page?: number;
  page_size?: number;
};

export type ProjectVariantsQueryResponse = ProjectVariantsResponse & {
  has_next_page: boolean;
  total_rows_exact: boolean;
};

export type VariantFilterOptionValue = {
  value: string | null;
  label: string;
  count: number | null;
};

export type VariantFilterOptionsRequest = VariantGridQueryRequest & {
  target_column: VariantGridColumnRef;
  option_search?: string | null;
  limit?: number;
};

export type VariantFilterOptionsResponse = {
  values: VariantFilterOptionValue[];
  limit: number;
  has_more: boolean;
};
