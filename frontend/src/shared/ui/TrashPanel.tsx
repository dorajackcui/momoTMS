import type { JobDetail } from "@/domains/jobs/types";
import { WorkbookWorkflowPanel } from "@/shared/ui/WorkbookWorkflowPanel";

export function TrashPanel(props: {
  projectId: number;
  branchRef: string;
  showProjectTrash: boolean;
  onJobCreated: (job: JobDetail) => void;
}) {
  return (
    <div>
      <WorkbookWorkflowPanel
        projectId={props.projectId}
        workflowKind="branch_trash"
        branchRef={props.branchRef}
        title={`Delete from ${props.branchRef}`}
        uploadLabel="Upload key workbook"
        executeLabel="Delete From Branch"
        onJobCompleted={props.onJobCreated}
      />
      {props.showProjectTrash && (
        <WorkbookWorkflowPanel
          projectId={props.projectId}
          workflowKind="project_trash"
          title="Trash orphan variants"
          uploadLabel="Upload key workbook"
          executeLabel="Trash Orphans"
          onJobCompleted={props.onJobCreated}
        />
      )}
    </div>
  );
}
