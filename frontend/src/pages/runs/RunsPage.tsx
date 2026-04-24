import { useEffect } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAppShell } from "@/app/shell/AppShellContext";
import { getJobDetail, getJobs } from "@/domains/jobs/api";
import { runFillUpload, runQaUpload } from "@/domains/workflows/api";
import { JobDetailPanel } from "@/features/job-detail/JobDetailPanel";
import { invalidateProject, queryKeys } from "@/shared/api/queryKeys";
import { formatTimestamp, summarizeJob, titleCase } from "@/shared/lib/format";
import {
  EmptyState,
  InlineNotice,
  Panel,
  buttonClassName,
  ui,
} from "@/shared/ui/primitives";
import { groupJobsForDisplay } from "@/pages/runs/model";
import { cx } from "@/shared/lib/cx";

import styles from "@/pages/runs/RunsPage.module.css";

const folderInputAttributes = {
  webkitdirectory: "",
  directory: "",
} as Record<string, string>;

export function RunsPage() {
  const shell = useAppShell();
  const queryClient = useQueryClient();

  const jobsQuery = useQuery({
    queryKey: shell.projectId ? queryKeys.jobs(shell.projectId) : ["jobs", "idle"],
    queryFn: () => getJobs(shell.projectId!),
    enabled: shell.projectId !== null,
  });

  const jobs = jobsQuery.data || [];
  const groupedJobs = groupJobsForDisplay(jobs);
  const selectedJobId =
    shell.jobId || jobs.find((job) => job.status === "running")?.job_id || jobs[0]?.job_id || null;

  useEffect(() => {
    if (selectedJobId && selectedJobId !== shell.jobId) {
      shell.setJobId(selectedJobId);
    }
  }, [selectedJobId, shell]);

  const launchJobMutation = useMutation({
    mutationFn: async (run: () => Promise<{ job: { job_id: number } }>) => run(),
    onSuccess: async (detail) => {
      if (!shell.projectId) {
        return;
      }
      await invalidateProject(queryClient, shell.projectId, {
        businessKey: shell.businessKey,
      });
      shell.setJobId(detail.job.job_id);
      shell.notify(`Job #${detail.job.job_id} started.`, "success");
    },
    onError: (error) => {
      shell.notify(error instanceof Error ? error.message : "Run failed.", "error");
    },
  });

  const detailQuery = useQuery({
    queryKey:
      shell.projectId && selectedJobId
        ? queryKeys.jobDetail(shell.projectId, selectedJobId)
        : ["job-detail", "idle"],
    queryFn: () => getJobDetail(shell.projectId!, selectedJobId!),
    enabled: Boolean(shell.projectId && selectedJobId),
    refetchInterval: (query) => {
      const detail = query.state.data;
      return detail && "job" in detail && detail.job.status === "running" ? 1000 : false;
    },
  });

  if (!shell.hasProjects || !shell.projectId) {
    return (
      <Panel kicker="Runs" title="Async workflow history">
        <EmptyState
          title="No project selected"
          body="Runs become available once a project exists and starts producing workflow jobs."
        />
      </Panel>
    );
  }

  return (
    <div className={styles.layout}>
      <div className={styles.launchers}>
        <Panel
          kicker="Launch Fill"
          title="Fill export"
          description="Upload a workbook folder and let the current project history backfill matching translations."
        >
          <label className={ui.field}>
            <span className={ui.fieldLabel}>Fill folder</span>
            <input
              className={ui.input}
              type="file"
              multiple
              {...folderInputAttributes}
              onChange={(event) => {
                const files = Array.from(event.target.files || []);
                if (files.length > 0) {
                  launchJobMutation.mutate(() =>
                    runFillUpload(shell.projectId, shell.lang, files),
                  );
                  event.target.value = "";
                }
              }}
            />
          </label>
        </Panel>

        <Panel
          kicker="Launch QA"
          title="QA scan"
          description="Upload a workbook folder and inspect the generated QA report in the same runs workspace."
        >
          <label className={ui.field}>
            <span className={ui.fieldLabel}>QA folder</span>
            <input
              className={ui.input}
              type="file"
              multiple
              {...folderInputAttributes}
              onChange={(event) => {
                const files = Array.from(event.target.files || []);
                if (files.length > 0) {
                  launchJobMutation.mutate(() =>
                    runQaUpload(shell.projectId, shell.lang, files),
                  );
                  event.target.value = "";
                }
              }}
            />
          </label>
          <button
            className={buttonClassName("ghost")}
            onClick={() => jobsQuery.refetch()}
          >
            Refresh jobs
          </button>
        </Panel>
      </div>

      <Panel
        kicker="Runs"
        title="Job-backed execution feedback"
        description="Every async workflow lands here with grouped history, live polling, preview rows, and artifact links."
      >
        {jobsQuery.isError ? (
          <InlineNotice tone="error" title="Failed to load jobs">
            {jobsQuery.error instanceof Error ? jobsQuery.error.message : "Request failed."}
          </InlineNotice>
        ) : null}
        {jobs.length === 0 ? (
          <EmptyState
            title="No runs yet"
            body="Run import, apply, replace, fill, QA, or trash actions to populate this page."
          />
        ) : (
          <div className={styles.list} data-testid="runs-job-list">
            {groupedJobs.map((group) => (
              <section key={group.status} className={styles.group}>
                <h3 className={styles.groupTitle}>{group.title}</h3>
                {group.jobs.map((job) => (
                  <button
                    key={job.job_id}
                    className={cx(
                      styles.jobButton,
                      selectedJobId === job.job_id && styles.jobButtonActive,
                    )}
                    onClick={() => shell.setJobId(job.job_id)}
                  >
                    <strong>
                      #{job.job_id} · {titleCase(job.job_type)}
                    </strong>
                    <span className={styles.jobMeta}>{job.status}</span>
                    <span className={styles.jobMeta}>{formatTimestamp(job.created_at)}</span>
                    <span className={styles.jobMeta}>{summarizeJob(job)}</span>
                  </button>
                ))}
              </section>
            ))}
          </div>
        )}
      </Panel>

      <Panel
        kicker="Selected Run"
        title={selectedJobId ? `Job #${selectedJobId}` : "Pick a run"}
        description="Running jobs auto-refresh until they settle."
        testId="runs-page"
      >
        {detailQuery.isError ? (
          <InlineNotice tone="error" title="Failed to load run detail">
            {detailQuery.error instanceof Error ? detailQuery.error.message : "Request failed."}
          </InlineNotice>
        ) : null}
        <JobDetailPanel
          projectId={shell.projectId}
          jobDetail={detailQuery.data || null}
        />
      </Panel>
    </div>
  );
}
