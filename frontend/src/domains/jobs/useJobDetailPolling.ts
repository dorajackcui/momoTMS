import { useQuery } from "@tanstack/react-query";

import { getJobDetail } from "@/domains/jobs/api";
import type { JobDetail } from "@/domains/jobs/types";
import { queryKeys } from "@/shared/api/queryKeys";

export function useJobDetailPolling(
  projectId: number,
  jobId: number | null,
  options: { pollMs?: number } = {},
) {
  const pollMs = options.pollMs ?? 1000;

  return useQuery<JobDetail>({
    queryKey:
      jobId === null
        ? ["job-detail", projectId, "idle"]
        : queryKeys.jobDetail(projectId, jobId),
    queryFn: () => getJobDetail(projectId, jobId!),
    enabled: jobId !== null,
    refetchInterval: (query) => {
      const detail = query.state.data;
      return detail?.job.status === "running" ? pollMs : false;
    },
  });
}
