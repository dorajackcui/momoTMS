import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import type { JobDetail } from "@/domains/jobs/types";
import { invalidateProject } from "@/shared/api/queryKeys";
import { buttonClassName, InlineNotice, StatGrid } from "@/shared/ui/primitives";
import { WorkbookWorkflowPanel } from "@/shared/ui/WorkbookWorkflowPanel";

import styles from "@/pages/dev/DevPage.module.css";

export function CreateBranch(props: {
  projectId: number;
  lang: string;
  onBack: () => void;
  onCreated: (version: string) => void;
}) {
  const { projectId, onBack, onCreated } = props;
  const queryClient = useQueryClient();
  const [version, setVersion] = useState("");
  const [result, setResult] = useState<JobDetail | null>(null);
  const branchRef = `dev/${version}`;

  async function handleCompleted(job: JobDetail) {
    setResult(job);
    await invalidateProject(queryClient, projectId);
  }

  return (
    <div className={styles.page}>
      <button className={buttonClassName("ghost")} onClick={onBack}>← Back</button>
      <h2>Create Branch</h2>
      <label>
        Version number
        <input value={version} onChange={(e) => setVersion(e.target.value)} placeholder="2.2.3" />
      </label>
      <p style={{ color: "var(--muted)", fontSize: 13 }}>Branch will be created as <strong>{branchRef}</strong></p>
      {!version.trim() && <InlineNotice tone="warning">Enter a version before uploading the workbook.</InlineNotice>}
      <WorkbookWorkflowPanel
        projectId={projectId}
        workflowKind="create_branch"
        branchRef={branchRef}
        title="Create branch from workbook"
        uploadLabel="Upload workbook"
        executeLabel="Create Branch"
        disabled={!version.trim()}
        onJobCompleted={handleCompleted}
      />
      {result && (
        <div className={styles.actions}>
          <StatGrid items={Object.entries(result.job.summary).map(([label, value]) => ({ label, value: String(value) }))} />
          <button className={buttonClassName("primary")} onClick={() => onCreated(version)}>
            Go to Branch
          </button>
        </div>
      )}
    </div>
  );
}
