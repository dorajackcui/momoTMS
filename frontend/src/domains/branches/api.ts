import { buildQueryString, fetchJson } from "@/shared/api/http";

import type {
  BranchCompareResponse,
  BranchListResponse,
  BranchMutationInput,
  BranchReplacePreview,
  BranchQueueResponse,
  DevBranchDetail,
  MasterEntryResponse,
  MasterSearchResponse,
} from "@/domains/branches/types";
import type { JobDetail } from "@/domains/jobs/types";

export function getBranchSummary(projectId: number, lang: string) {
  const query = buildQueryString({ lang });
  return fetchJson<BranchListResponse>(
    `/api/projects/${projectId}/branches?${query}`,
  );
}

export function getDevBranchDetail(projectId: number, version: string) {
  return fetchJson<DevBranchDetail>(
    `/api/projects/${projectId}/branches/dev/${encodeURIComponent(version)}`,
  );
}

export function getBranchCompare(
  projectId: number,
  params: {
    base_branch_ref: string;
    target_branch_ref: string;
    lang: string;
    search?: string;
    state?: string[];
    diff_category?: string[];
    priority_status?: string[];
    page?: number;
    page_size?: number;
  },
) {
  const query = buildQueryString(params);
  return fetchJson<BranchCompareResponse>(
    `/api/projects/${projectId}/branches/compare?${query}`,
  );
}

export function getBranchQueue(
  projectId: number,
  params: {
    target_branch_ref: string;
    lang: string;
    search?: string;
    priority_status?: string[];
    page?: number;
    page_size?: number;
  },
) {
  const query = buildQueryString(params);
  return fetchJson<BranchQueueResponse>(
    `/api/projects/${projectId}/branches/queue?${query}`,
  );
}

export function lookupMasterByKey(projectId: number, businessKey: string) {
  return fetchJson<MasterEntryResponse>(
    `/api/projects/${projectId}/branches/master/entries/${encodeURIComponent(
      businessKey,
    )}`,
  );
}

export function lookupMasterBySource(projectId: number, source: string) {
  const query = buildQueryString({ source });
  return fetchJson<MasterSearchResponse>(
    `/api/projects/${projectId}/branches/master/search?${query}`,
  );
}

export function runBranchMutation(
  projectId: number,
  branchRef: string,
  input: BranchMutationInput,
) {
  return fetchJson<JobDetail>(`/api/projects/${projectId}/branches/mutations`, {
    method: "POST",
    body: JSON.stringify({
      branch_ref: branchRef,
      input,
    }),
  });
}

export function previewBranchReplace(
  projectId: number,
  sourceBranchRef: string,
  targetBranchRef: string,
) {
  return fetchJson<BranchReplacePreview>(
    `/api/projects/${projectId}/branches/replace/preview`,
    {
      method: "POST",
      body: JSON.stringify({
        source_branch_ref: sourceBranchRef,
        target_branch_ref: targetBranchRef,
      }),
    },
  );
}

export function executeBranchReplace(
  projectId: number,
  sourceBranchRef: string,
  targetBranchRef: string,
) {
  return fetchJson<JobDetail>(
    `/api/projects/${projectId}/branches/replace/execute`,
    {
      method: "POST",
      body: JSON.stringify({
        source_branch_ref: sourceBranchRef,
        target_branch_ref: targetBranchRef,
      }),
    },
  );
}

export function deleteBranchBusinessKeys(
  projectId: number,
  branchRef: string,
  businessKeys: string[],
) {
  return fetchJson<JobDetail>(`/api/projects/${projectId}/variants/trash/delete`, {
    method: "POST",
    body: JSON.stringify({
      branch_ref: branchRef,
      business_keys: businessKeys,
    }),
  });
}
