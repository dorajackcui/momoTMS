import { fetchJson } from "@/shared/api/http";

import type { JobDetail, JobSummary } from "@/domains/jobs/types";

export function getJobs(projectId: number) {
  return fetchJson<JobSummary[]>(`/api/projects/${projectId}/jobs`);
}

export function getJobDetail(projectId: number, jobId: number) {
  return fetchJson<JobDetail>(`/api/projects/${projectId}/jobs/${jobId}`);
}

export async function waitForJobDetail(
  projectId: number,
  jobId: number,
  options: { pollMs?: number; maxAttempts?: number } = {},
) {
  const pollMs = options.pollMs ?? 500;
  const maxAttempts = options.maxAttempts ?? 120;

  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const detail = await getJobDetail(projectId, jobId);
    if (detail.job.status !== "running") {
      return detail;
    }
    await delay(pollMs);
  }

  throw new Error(`job #${jobId} did not finish before the preview timeout`);
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

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}
