export type ReportPayload = {
  summary: Record<string, unknown>;
  rows: Array<Record<string, unknown>>;
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
  finished_at: string | null;
};

export type JobDetail = {
  job: JobSummary;
  report: ReportPayload;
};

export type JobStageSummary = {
  stage: string;
  elapsed_ms: number;
  meta: Record<string, unknown>;
};
