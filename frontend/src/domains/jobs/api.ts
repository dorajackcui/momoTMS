import { fetchJson } from "@/shared/api/http";

import type { JobDetail, JobSummary } from "@/domains/jobs/types";

export function getJobs(projectId: number) {
  return fetchJson<JobSummary[]>(`/api/projects/${projectId}/jobs`);
}

export function getJobDetail(projectId: number, jobId: number) {
  return fetchJson<JobDetail>(`/api/projects/${projectId}/jobs/${jobId}`);
}

export function buildJobReportHref(projectId: number, jobId: number) {
  return `/api/projects/${projectId}/jobs/${jobId}/report`;
}

export function buildJobArtifactHref(
  projectId: number,
  job: JobSummary,
): string | null {
  if (!job.artifact_path) {
    return null;
  }
  const artifactName = job.artifact_path.split("/").pop();
  if (!artifactName) {
    return null;
  }
  return `/api/projects/${projectId}/jobs/${job.job_id}/artifact/${encodeURIComponent(
    artifactName,
  )}`;
}
