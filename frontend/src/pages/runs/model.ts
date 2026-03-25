import type { JobSummary } from "@/domains/jobs/types";
import { groupBy, titleCase } from "@/shared/lib/format";

export function groupJobsForDisplay(jobs: JobSummary[]) {
  const statusGroups = groupBy(jobs, (job) => job.status || "unknown");
  const order = ["running", "success", "failed", "unknown"] as const;
  return order
    .filter((status) => (statusGroups[status] || []).length > 0)
    .map((status) => ({
      status,
      title: titleCase(status),
      jobs: statusGroups[status].slice().sort((left, right) => {
        return right.created_at.localeCompare(left.created_at);
      }),
    }));
}
