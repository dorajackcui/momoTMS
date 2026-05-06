import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { executeWorkbookWorkflow, previewWorkbookWorkflow } from "@/domains/workbooks/api";
import type { WorkbookIntakePreview, WorkbookMutationType, WorkbookWorkflowKind } from "@/domains/workbooks/types";
import type { JobDetail } from "@/domains/jobs/types";
import { useJobDetailPolling } from "@/domains/jobs/useJobDetailPolling";
import { buttonClassName, InlineNotice, StatGrid } from "@/shared/ui/primitives";
import { WorkbookUpload } from "@/shared/ui/WorkbookUpload";

import styles from "@/shared/ui/WorkbookWorkflowPanel.module.css";

export type WorkbookWorkflowPanelProps = {
  projectId: number;
  workflowKind: WorkbookWorkflowKind;
  branchRef?: string;
  mutationType?: WorkbookMutationType;
  title: string;
  uploadLabel?: string;
  executeLabel: string;
  disabled?: boolean;
  onJobCompleted: (job: JobDetail) => void;
};

export function WorkbookWorkflowPanel(props: WorkbookWorkflowPanelProps) {
  const {
    projectId,
    workflowKind,
    branchRef,
    mutationType,
    onJobCompleted,
    disabled,
    executeLabel,
    title,
    uploadLabel,
  } = props;
  const [files, setFiles] = useState<File[]>([]);
  const [preview, setPreview] = useState<WorkbookIntakePreview | null>(null);
  const [completedJob, setCompletedJob] = useState<JobDetail | null>(null);
  const [activeJobId, setActiveJobId] = useState<number | null>(null);
  const completedJobIdRef = useRef<number | null>(null);

  const previewMut = useMutation({
    mutationFn: () =>
      previewWorkbookWorkflow(projectId, files, {
        workflow_kind: workflowKind,
        branch_ref: branchRef,
        mutation_type: mutationType,
      }),
    onSuccess: (data) => setPreview(data),
  });

  const executeMut = useMutation({
    mutationFn: async () => {
      if (!preview) throw new Error("Preview is required before execute");
      const started = await executeWorkbookWorkflow(projectId, {
        upload_session_id: preview.upload_session_id,
        workflow_kind: workflowKind,
        branch_ref: branchRef,
        mutation_type: mutationType,
      });
      setActiveJobId(started.job.job_id);
      return started;
    },
  });

  const activeJobQuery = useJobDetailPolling(projectId, activeJobId);
  const activeJob =
    activeJobQuery.data ??
    (executeMut.data?.job.job_id === activeJobId ? executeMut.data : null);
  const isRunning = executeMut.isPending || activeJob?.job.status === "running";

  useEffect(() => {
    if (!activeJob) return;
    if (activeJob.job.status === "success") {
      if (completedJobIdRef.current === activeJob.job.job_id) return;
      completedJobIdRef.current = activeJob.job.job_id;
      setCompletedJob(activeJob);
      onJobCompleted(activeJob);
      return;
    }
    if (activeJob.job.status === "failed") {
      setCompletedJob(null);
    }
  }, [activeJob, onJobCompleted]);

  const canPreview = files.length > 0 && !disabled;
  const canExecute =
    preview !== null &&
    preview.missing_required_headers.length === 0 &&
    !disabled &&
    !isRunning;

  return (
    <section className={styles.panel}>
      <div className={styles.header}>
        <h3>{title}</h3>
      </div>
      <WorkbookUpload
        label={uploadLabel ?? "Upload workbook"}
        disabled={disabled}
        onFiles={(nextFiles) => {
          setFiles(nextFiles);
          setPreview(null);
          setCompletedJob(null);
          setActiveJobId(null);
          completedJobIdRef.current = null;
          previewMut.reset();
          executeMut.reset();
        }}
      />
      {files.length > 0 && (
        <p className={styles.meta}>
          {files.length === 1 ? files[0].name : `${files.length} files selected`}
        </p>
      )}
      <div className={styles.actions}>
        <button
          className={buttonClassName("secondary")}
          disabled={!canPreview || previewMut.isPending}
          onClick={() => previewMut.mutate()}
        >
          {previewMut.isPending ? "Checking workbook..." : "Check Workbook"}
        </button>
        {preview && (
          <button
            className={buttonClassName("primary")}
            disabled={!canExecute}
            onClick={() => executeMut.mutate()}
          >
            {isRunning ? "Running..." : executeLabel}
          </button>
        )}
      </div>
      {previewMut.isError && <InlineNotice tone="error">{String(previewMut.error)}</InlineNotice>}
      {executeMut.isError && <InlineNotice tone="error">{String(executeMut.error)}</InlineNotice>}
      {activeJobQuery.isError && (
        <InlineNotice tone="error">{String(activeJobQuery.error)}</InlineNotice>
      )}
      {preview && (
        <div className={styles.preview}>
          <StatGrid
            items={[
              { label: "Files", value: preview.file_count },
              { label: "Sheets", value: preview.sheet_count },
              { label: "Sample issues", value: preview.sampled_issue_count },
            ]}
          />
          {preview.missing_required_headers.length > 0 && (
            <InlineNotice tone="error">
              Missing required headers: {preview.missing_required_headers.join(", ")}
            </InlineNotice>
          )}
        </div>
      )}
      {activeJob && (
        <div className={styles.preview}>
          <p className={styles.meta}>Job #{activeJob.job.job_id}</p>
          <StatGrid
            items={[
              { label: "Job", value: `#${activeJob.job.job_id}` },
              { label: "Status", value: activeJob.job.status },
              ...Object.entries(activeJob.job.summary).map(([label, value]) => ({
                label,
                value: String(value),
              })),
            ]}
          />
          {activeJob.job.status === "failed" && (
            <InlineNotice tone="error">
              {activeJob.job.error_message || "Workbook workflow failed"}
            </InlineNotice>
          )}
        </div>
      )}
      {completedJob && (
        <div className={styles.preview}>
          <StatGrid items={Object.entries(completedJob.job.summary).map(([label, value]) => ({ label, value: String(value) }))} />
        </div>
      )}
    </section>
  );
}
