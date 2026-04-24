from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.branch.models import BranchRef
from app.services.branch.mutations import BranchMutationService
from app.services.branch.bootstrap import BranchBootstrapService
from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.shared.background_jobs import submit_background_job
from app.services.shared.jobs import JobService
from app.services.shared.uploads import UploadSessionService
from app.services.workbooks.batches import WorkbookBatchService
from app.services.workbooks.models import WorkbookWorkflowContext
from app.services.workflows.trash import TrashService


class WorkbookWorkflowService:
    def __init__(self) -> None:
        self.batches = WorkbookBatchService()
        self.bootstrap = BranchBootstrapService()
        self.mutations = BranchMutationService()
        self.trash = TrashService()
        self.jobs = JobService()
        self.uploads = UploadSessionService()

    def execute_uploaded_session(
        self,
        *,
        upload_session_id: str,
        workflow_kind: str,
        project_id: int = DEFAULT_PROJECT_ID,
        branch_ref: str | None = None,
        mutation_type: str | None = None,
    ) -> dict[str, Any]:
        self.uploads.require_session(upload_session_id, project_id)
        job_type = f"workbook_{workflow_kind}"
        job_id = self.jobs.create_job(
            job_type,
            {
                "upload_session_id": upload_session_id,
                "workflow_kind": workflow_kind,
                "branch_ref": branch_ref,
                "mutation_type": mutation_type,
                "project_id": project_id,
            },
            project_id=project_id,
        )

        def run() -> None:
            try:
                input_dir = self.uploads.consume_session_into_job(
                    upload_session_id,
                    job_id,
                    project_id,
                    "workbook_input",
                )
                result = self._execute_directory(
                    Path(input_dir),
                    workflow_kind=workflow_kind,
                    project_id=project_id,
                    branch_ref=branch_ref,
                    mutation_type=mutation_type,
                    job_id=job_id,
                )
                if result.get("already_completed_job"):
                    return
                self.jobs.complete_job(
                    job_id,
                    summary=result["summary"],
                    report_payload=result["report"],
                    artifact_path=result.get("artifact_path"),
                )
            except Exception as exc:
                self.jobs.fail_job(job_id, str(exc))

        submit_background_job(run)
        return self.get_job_detail(job_id, project_id=project_id)

    def _execute_directory(
        self,
        input_dir: Path,
        *,
        workflow_kind: str,
        project_id: int,
        branch_ref: str | None,
        mutation_type: str | None,
        job_id: int,
    ) -> dict[str, Any]:
        context = WorkbookWorkflowContext(workflow_kind=workflow_kind, mutation_type=mutation_type)  # type: ignore[arg-type]
        batch = self.batches.create_batch_from_directory(input_dir, project_id, context)
        workbook_batch_id = int(batch["workbook_batch_id"])
        if workflow_kind == "create_branch":
            if not branch_ref:
                raise ValueError("branch_ref is required")
            result = self.bootstrap.bootstrap(
                BranchRef.parse(branch_ref),
                workbook_batch_id,
                project_id=project_id,
                job_id=job_id,
            )
            result["summary"]["workbook_batch_id"] = workbook_batch_id
            self.jobs.patch_job_summary(job_id, {"workbook_batch_id": workbook_batch_id})
            return {"already_completed_job": True, **result}
        if workflow_kind == "branch_mutation":
            if not branch_ref:
                raise ValueError("branch_ref is required")
            if mutation_type not in {"content", "range"}:
                raise ValueError("mutation_type must be content or range")
            result = self.mutations.apply(
                BranchRef.parse(branch_ref),
                {
                    "kind": "workbook_batch",
                    "mutation_type": mutation_type,
                    "workbook_batch_id": workbook_batch_id,
                },
                project_id=project_id,
            )
            return self._wrap(workbook_batch_id, result)
        if workflow_kind == "branch_trash":
            if not branch_ref:
                raise ValueError("branch_ref is required")
            result = self.trash.delete_from_workbook_batch(
                BranchRef.parse(branch_ref),
                workbook_batch_id,
                project_id=project_id,
            )
            return self._wrap(workbook_batch_id, result)
        if workflow_kind == "project_trash":
            result = self.trash.project_trash_from_workbook_batch(workbook_batch_id, project_id=project_id)
            return self._wrap(workbook_batch_id, result)
        raise ValueError(f"unsupported workbook workflow: {workflow_kind}")

    def _wrap(self, workbook_batch_id: int, result: dict[str, Any]) -> dict[str, Any]:
        summary = dict(result["summary"])
        summary["workbook_batch_id"] = workbook_batch_id
        return {
            "summary": summary,
            "report": {"summary": summary, "rows": result.get("report_rows", [])},
        }

    def get_job_detail(self, job_id: int, project_id: int | None = None) -> dict[str, Any]:
        return {
            "job": self.jobs.get_job(job_id, project_id=project_id),
            "report": self.jobs.get_report_preview(job_id, project_id=project_id),
        }
