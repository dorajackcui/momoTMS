import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { executeWorkbookWorkflow, previewWorkbookWorkflow } from "@/domains/workbooks/api";
import type { WorkbookIntakePreview, WorkbookMutationType, WorkbookWorkflowKind } from "@/domains/workbooks/types";
import type { JobDetail } from "@/domains/jobs/types";
import { waitForJobDetail } from "@/domains/jobs/api";
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
  const [files, setFiles] = useState<File[]>([]);
  const [preview, setPreview] = useState<WorkbookIntakePreview | null>(null);
  const [completedJob, setCompletedJob] = useState<JobDetail | null>(null);

  const previewMut = useMutation({
    mutationFn: () =>
      previewWorkbookWorkflow(props.projectId, files, {
        workflow_kind: props.workflowKind,
        branch_ref: props.branchRef,
        mutation_type: props.mutationType,
      }),
    onSuccess: (data) => setPreview(data),
  });

  const executeMut = useMutation({
    mutationFn: async () => {
      if (!preview) throw new Error("Preview is required before execute");
      const started = await executeWorkbookWorkflow(props.projectId, {
        upload_session_id: preview.upload_session_id,
        workflow_kind: props.workflowKind,
        branch_ref: props.branchRef,
        mutation_type: props.mutationType,
      });
      const completed = await waitForJobDetail(props.projectId, started.job.job_id);
      if (completed.job.status !== "success") {
        throw new Error(completed.job.error_message || "Workbook workflow failed");
      }
      return completed;
    },
    onSuccess: (job) => {
      setCompletedJob(job);
      props.onJobCompleted(job);
    },
  });

  const canPreview = files.length > 0 && !props.disabled;
  const canExecute = preview !== null && preview.missing_required_headers.length === 0 && !props.disabled;

  return (
    <section className={styles.panel}>
      <div className={styles.header}>
        <h3>{props.title}</h3>
      </div>
      <WorkbookUpload
        label={props.uploadLabel ?? "Upload workbook"}
        disabled={props.disabled}
        onFiles={(nextFiles) => {
          setFiles(nextFiles);
          setPreview(null);
          setCompletedJob(null);
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
            disabled={!canExecute || executeMut.isPending}
            onClick={() => executeMut.mutate()}
          >
            {executeMut.isPending ? "Running..." : props.executeLabel}
          </button>
        )}
      </div>
      {previewMut.isError && <InlineNotice tone="error">{String(previewMut.error)}</InlineNotice>}
      {executeMut.isError && <InlineNotice tone="error">{String(executeMut.error)}</InlineNotice>}
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
      {completedJob && (
        <div className={styles.preview}>
          <StatGrid items={Object.entries(completedJob.job.summary).map(([label, value]) => ({ label, value: String(value) }))} />
        </div>
      )}
    </section>
  );
}
