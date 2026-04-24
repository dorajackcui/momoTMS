import { buildQueryString, fetchJson } from "@/shared/api/http";

import type {
  BranchListResponse,
  BranchLookupResponse,
  BranchMutationInput,
  BranchReplacePreview,
  BranchRowsResponse,
  DevBranchDetail,
  SameSourceCandidatesResponse,
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

export function getScopeRows(
  projectId: number,
  scopeRef: string,
  params: {
    search_business_key?: string;
    search_source?: string;
    page?: number;
    page_size?: number;
  },
) {
  const query = buildQueryString(params);
  return fetchJson<BranchRowsResponse>(
    `/api/projects/${projectId}/scopes/${encodeURIComponent(scopeRef)}/rows?${query}`,
  );
}

export function lookupScope(
  projectId: number,
  scopeRef: string,
  params: {
    business_key?: string;
    source?: string;
  },
) {
  const query = buildQueryString(params);
  return fetchJson<BranchLookupResponse>(
    `/api/projects/${projectId}/scopes/${encodeURIComponent(scopeRef)}/lookup?${query}`,
  );
}

export function getBranchRows(
  projectId: number,
  branchRef: string,
  params: {
    search_business_key?: string;
    search_source?: string;
    page?: number;
    page_size?: number;
  },
) {
  const query = buildQueryString(params);
  return fetchJson<BranchRowsResponse>(
    `/api/projects/${projectId}/branches/${encodeURIComponent(branchRef)}/rows?${query}`,
  );
}

export function lookupBranch(
  projectId: number,
  branchRef: string,
  params: {
    business_key?: string;
    source?: string;
  },
) {
  const query = buildQueryString(params);
  return fetchJson<BranchLookupResponse>(
    `/api/projects/${projectId}/branches/${encodeURIComponent(branchRef)}/lookup?${query}`,
  );
}

export function getSameSourceCandidates(
  projectId: number,
  params: {
    business_key: string;
    source: string;
  },
) {
  const query = buildQueryString(params);
  return fetchJson<SameSourceCandidatesResponse>(
    `/api/projects/${projectId}/history/same-source-candidates?${query}`,
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
