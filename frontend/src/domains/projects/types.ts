import type { ImportBatchSummary } from "@/domains/imports/types";
import type { JobSummary } from "@/domains/jobs/types";
import type { DevBranchSummary } from "@/domains/branches/types";

export type ProjectSummary = {
  project_id: number;
  name: string;
  is_default: boolean;
  created_at: string;
};

export type ProjectSchema = {
  schema_id: number;
  project_id: number;
  fixed_columns: Record<string, string>;
  translation_columns: string[];
  remark_columns: string[];
  pivot_language: string | null;
  pivoted_languages: string[];
  created_at: string;
};

export type ProductStateResponse = {
  project: ProjectSummary;
  schema: ProjectSchema;
  release_summary: Record<string, unknown>;
  dev_branches: DevBranchSummary[];
  imports: ImportBatchSummary[];
  jobs: JobSummary[];
};

export type CreateProjectInput = {
  name: string;
  business_key_header?: string;
  source_header?: string;
  translation_columns: string[];
  remark_columns: string[];
  pivot_language?: string | null;
  pivoted_languages?: string[];
};
