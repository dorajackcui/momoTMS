export type VariantBindingSummary = {
  branch_ref: string;
  created_at: string;
  updated_at: string;
};

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
  created_at: string;
  updated_at: string;
};

export type ProjectVariantsResponse = {
  rows: ProjectVariantRow[];
  total_rows: number;
  page: number;
  page_size: number;
};
