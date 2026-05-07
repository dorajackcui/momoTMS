import { buildQueryString, fetchJson } from "@/shared/api/http";

import type { JobDetail } from "@/domains/jobs/types";
import type {
  EntryVariantsResponse,
  OrphanVariantsResponse,
  PivotStatus,
  ProjectVariantsQueryResponse,
  ProjectVariantsResponse,
  VariantFilterOptionsRequest,
  VariantFilterOptionsResponse,
  VariantGridQueryRequest,
} from "@/domains/variants/types";

export function getEntryVariants(projectId: number, businessKey: string) {
  return fetchJson<EntryVariantsResponse>(
    `/api/projects/${projectId}/entries/${encodeURIComponent(businessKey)}/variants`,
  );
}

export function getOrphanVariants(projectId: number) {
  return fetchJson<OrphanVariantsResponse>(
    `/api/projects/${projectId}/orphan-variants`,
  );
}

export function getProjectVariants(
  projectId: number,
  params: {
    state?: "active" | "orphan" | "all";
    branch_ref?: string[];
    search_business_key?: string;
    search_source?: string;
    pivot_status?: PivotStatus;
    pivot_changed_by_branch_ref?: string;
    page?: number;
    page_size?: number;
  },
) {
  const query = buildQueryString(params);
  return fetchJson<ProjectVariantsResponse>(
    `/api/projects/${projectId}/variants?${query}`,
  );
}

export function queryProjectVariants(
  projectId: number,
  payload: VariantGridQueryRequest,
) {
  return fetchJson<ProjectVariantsQueryResponse>(
    `/api/projects/${projectId}/variants/query`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function getProjectVariantFilterOptions(
  projectId: number,
  payload: VariantFilterOptionsRequest,
) {
  return fetchJson<VariantFilterOptionsResponse>(
    `/api/projects/${projectId}/variants/filter-options`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function reviewPivotVariants(
  projectId: number,
  branchRef: string,
  variantIds: number[],
) {
  return fetchJson<JobDetail>(`/api/projects/${projectId}/variants/pivot/review`, {
    method: "POST",
    body: JSON.stringify({ branch_ref: branchRef, variant_ids: variantIds }),
  });
}
