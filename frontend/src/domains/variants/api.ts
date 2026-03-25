import { fetchJson } from "@/shared/api/http";

import type { JobDetail } from "@/domains/jobs/types";
import type {
  EntryVariantsResponse,
  OrphanVariantsResponse,
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

export function restoreVariants(projectId: number, variantIds: number[]) {
  return fetchJson<JobDetail>(`/api/projects/${projectId}/variants/trash/restore`, {
    method: "POST",
    body: JSON.stringify({ variant_ids: variantIds }),
  });
}
