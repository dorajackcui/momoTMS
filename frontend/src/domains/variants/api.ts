import { buildQueryString, fetchJson } from "@/shared/api/http";

import type { JobDetail } from "@/domains/jobs/types";
import type {
  EntryVariantsResponse,
  OrphanVariantsResponse,
  ProjectVariantsResponse,
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
    page?: number;
    page_size?: number;
  },
) {
  const query = buildQueryString(params);
  return fetchJson<ProjectVariantsResponse>(
    `/api/projects/${projectId}/variants?${query}`,
  );
}

export function restoreVariants(projectId: number, variantIds: number[]) {
  return fetchJson<JobDetail>(`/api/projects/${projectId}/variants/trash/restore`, {
    method: "POST",
    body: JSON.stringify({ variant_ids: variantIds }),
  });
}
