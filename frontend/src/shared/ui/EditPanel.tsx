import { useState } from "react";

import type { JobDetail } from "@/domains/jobs/types";
import type { WorkbookMutationType } from "@/domains/workbooks/types";
import { WorkbookWorkflowPanel } from "@/shared/ui/WorkbookWorkflowPanel";

import styles from "@/shared/ui/EditPanel.module.css";

export type EditPanelProps = {
  projectId: number;
  branchRef: string;
  allowRange: boolean;
  onJobCreated: (job: JobDetail) => void;
};

export function EditPanel(props: EditPanelProps) {
  const [mutationType, setMutationType] = useState<WorkbookMutationType>("content");
  const rangeDisabled = !props.allowRange;

  return (
    <div className={styles.panel}>
      <fieldset className={styles.fieldset}>
        <legend>Mutation type</legend>
        <label>
          <input
            type="radio"
            checked={mutationType === "content"}
            onChange={() => setMutationType("content")}
          />
          Content
        </label>
        <label>
          <input
            type="radio"
            checked={mutationType === "range"}
            disabled={rangeDisabled}
            onChange={() => setMutationType("range")}
          />
          Range
        </label>
      </fieldset>
      <WorkbookWorkflowPanel
        projectId={props.projectId}
        workflowKind="branch_mutation"
        branchRef={props.branchRef}
        mutationType={mutationType}
        title={`${mutationType === "content" ? "Content" : "Range"} mutation from workbook`}
        uploadLabel="Upload workbook"
        executeLabel="Apply Mutation"
        onJobCompleted={props.onJobCreated}
      />
    </div>
  );
}
