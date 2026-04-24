from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from app.routers.common import handle_errors
from app.schemas import JobDetail, WorkbookIntakeExecuteRequest, WorkbookIntakePreview
from app.services.shared.uploads import UploadSessionService
from app.services.workbooks.models import WorkbookWorkflowContext
from app.services.workbooks.parser import WorkbookParser
from app.services.workbooks.workflows import WorkbookWorkflowService

router = APIRouter()


@router.post("/api/projects/{project_id}/workbooks/intake/preview", response_model=WorkbookIntakePreview)
def workbook_intake_preview(
    project_id: int,
    workflow_kind: str = Form(...),
    branch_ref: str | None = Form(default=None),
    mutation_type: str | None = Form(default=None),
    files: list[UploadFile] = File(...),
    relative_paths: list[str] = Form(...),
) -> WorkbookIntakePreview:
    def run() -> WorkbookIntakePreview:
        sessions = UploadSessionService()
        session = sessions.create_session(files, relative_paths, project_id)
        try:
            context = WorkbookWorkflowContext(workflow_kind=workflow_kind, mutation_type=mutation_type)  # type: ignore[arg-type]
            precheck = WorkbookParser().precheck_directory(
                sessions.session_input_dir(session["upload_session_id"]),
                project_id,
                context,
            )
            return WorkbookIntakePreview(
                upload_session_id=session["upload_session_id"],
                workflow_kind=workflow_kind,
                mutation_type=mutation_type,
                file_count=precheck.file_count,
                sheet_count=precheck.sheet_count,
                missing_required_headers=precheck.missing_required_headers,
                sampled_issue_count=precheck.sampled_issue_count,
                sheet_previews=[
                    {
                        "sheet_key": sheet.sheet_key,
                        "file_path": sheet.file_path,
                        "sheet_name": sheet.sheet_name,
                        "available_headers": sheet.available_headers,
                        "missing_required_headers": sheet.missing_required_headers,
                        "sampled_issue_count": sheet.sampled_issue_count,
                    }
                    for sheet in precheck.sheet_previews
                ],
            )
        except Exception:
            sessions.discard_session(session["upload_session_id"])
            raise

    return handle_errors(run)


@router.post("/api/projects/{project_id}/workbooks/intake/execute", response_model=JobDetail)
def workbook_intake_execute(project_id: int, payload: WorkbookIntakeExecuteRequest) -> JobDetail:
    return handle_errors(
        lambda: JobDetail(
            **WorkbookWorkflowService().execute_uploaded_session(
                upload_session_id=payload.upload_session_id,
                workflow_kind=payload.workflow_kind,
                branch_ref=payload.branch_ref,
                mutation_type=payload.mutation_type,
                project_id=project_id,
            )
        )
    )
