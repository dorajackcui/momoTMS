import type { QueryClient } from "@tanstack/react-query";

export const queryKeys = {
  projects: () => ["projects"] as const,
  projectState: (projectId: number) => ["project-state", projectId] as const,
  branchSummary: (projectId: number, lang: string) =>
    ["branch-summary", projectId, lang] as const,
  devBranchDetail: (projectId: number, version: string) =>
    ["dev-branch-detail", projectId, version] as const,
  branchCompare: (
    projectId: number,
    params: Record<string, unknown>,
  ) => ["branch-compare", projectId, params] as const,
  branchQueue: (projectId: number, params: Record<string, unknown>) =>
    ["branch-queue", projectId, params] as const,
  masterByKey: (projectId: number, businessKey: string) =>
    ["master-by-key", projectId, businessKey] as const,
  masterBySource: (projectId: number, source: string) =>
    ["master-by-source", projectId, source] as const,
  imports: (projectId: number) => ["imports", projectId] as const,
  importReport: (projectId: number, importBatchId: number) =>
    ["import-report", projectId, importBatchId] as const,
  jobs: (projectId: number) => ["jobs", projectId] as const,
  jobDetail: (projectId: number, jobId: number) =>
    ["job-detail", projectId, jobId] as const,
  entryVariants: (projectId: number, businessKey: string) =>
    ["entry-variants", projectId, businessKey] as const,
  orphanVariants: (projectId: number) => ["orphan-variants", projectId] as const,
};

export async function invalidateProjectScope(
  queryClient: QueryClient,
  projectId: number,
  options: {
    devVersion?: string | null;
    businessKey?: string | null;
  } = {},
) {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: queryKeys.projects() }),
    queryClient.invalidateQueries({
      queryKey: queryKeys.projectState(projectId),
    }),
    queryClient.invalidateQueries({
      queryKey: ["branch-summary", projectId],
    }),
    queryClient.invalidateQueries({ queryKey: ["branch-compare", projectId] }),
    queryClient.invalidateQueries({ queryKey: ["branch-queue", projectId] }),
    queryClient.invalidateQueries({
      queryKey: queryKeys.imports(projectId),
    }),
    queryClient.invalidateQueries({ queryKey: queryKeys.jobs(projectId) }),
    queryClient.invalidateQueries({
      queryKey: queryKeys.orphanVariants(projectId),
    }),
    options.businessKey
      ? queryClient.invalidateQueries({
          queryKey: queryKeys.entryVariants(projectId, options.businessKey),
        })
      : Promise.resolve(),
    options.devVersion
      ? queryClient.invalidateQueries({
          queryKey: queryKeys.devBranchDetail(projectId, options.devVersion),
        })
      : Promise.resolve(),
  ]);
}
