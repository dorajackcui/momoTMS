from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from app.routers.common import handle_errors, read_folder_upload
from app.schemas import (
    BranchMutationRequest,
    BranchSyncPreview,
    BranchSyncRequest,
    DevBranchDetail,
    DevBranchSummary,
    FillRequest,
    JobDetail,
    QaRequest,
    ScopedTrashDeleteRequest,
    VariantTrashRestoreRequest,
)
from app.services.branch.service import BranchService
from app.services.workflows.workbench import WorkflowService

router = APIRouter()


@router.post("/api/projects/{project_id}/branches/mutations", response_model=JobDetail)
def project_branch_mutation(project_id: int, payload: BranchMutationRequest) -> JobDetail:
    service = WorkflowService()
    return handle_errors(
        lambda: JobDetail(
            **service.branch_mutation(
                payload.scope_ref,
                payload.input.model_dump(mode="python"),
                project_id=project_id,
            )
        )
    )


@router.get("/api/projects/{project_id}/branches/dev", response_model=list[DevBranchSummary])
def project_list_dev_branches(project_id: int) -> list[DevBranchSummary]:
    return handle_errors(
        lambda: [DevBranchSummary(**item) for item in BranchService().list_dev_branches(project_id=project_id, active_only=True)]
    )


@router.get("/api/projects/{project_id}/branches/dev/{version}", response_model=DevBranchDetail)
def project_get_dev_branch(project_id: int, version: str) -> DevBranchDetail:
    return handle_errors(lambda: DevBranchDetail(**BranchService().get_dev_branch(version, project_id)))


@router.post("/api/projects/{project_id}/branches/sync/preview", response_model=BranchSyncPreview)
def project_branch_sync_preview(project_id: int, payload: BranchSyncRequest) -> BranchSyncPreview:
    return handle_errors(
        lambda: BranchSyncPreview(
            **WorkflowService().branch_sync_preview(
                payload.source_scope_ref,
                payload.target_scope_ref,
                project_id,
            )
        )
    )


@router.post("/api/projects/{project_id}/branches/sync/execute", response_model=JobDetail)
def project_branch_sync_execute(project_id: int, payload: BranchSyncRequest) -> JobDetail:
    return handle_errors(
        lambda: JobDetail(
            **WorkflowService().branch_sync_execute(
                payload.source_scope_ref,
                payload.target_scope_ref,
                project_id,
            )
        )
    )


@router.post("/api/projects/{project_id}/variants/trash/delete", response_model=JobDetail)
def project_trash_delete(project_id: int, payload: ScopedTrashDeleteRequest) -> JobDetail:
    return handle_errors(
        lambda: JobDetail(
            **WorkflowService().trash_delete(
                payload.scope_ref,
                payload.business_keys,
                project_id=project_id,
            )
        )
    )


@router.post("/api/projects/{project_id}/variants/trash/restore", response_model=JobDetail)
def project_trash_restore(project_id: int, payload: VariantTrashRestoreRequest) -> JobDetail:
    return handle_errors(
        lambda: JobDetail(
            **WorkflowService().trash_restore(
                payload.variant_ids,
                project_id=project_id,
            )
        )
    )


@router.post("/api/projects/{project_id}/fill", response_model=JobDetail)
def project_fill(project_id: int, payload: FillRequest) -> JobDetail:
    service = WorkflowService()
    return handle_errors(lambda: JobDetail(**service.fill(payload.source_dir, payload.lang, payload.output_name, project_id)))


@router.post("/api/projects/{project_id}/fill/upload-folder", response_model=JobDetail)
def project_fill_upload_folder(
    project_id: int,
    lang: str = Form(...),
    output_name: str | None = Form(default=None),
    files: list[UploadFile] = File(...),
    relative_paths: list[str] = Form(...),
) -> JobDetail:
    service = WorkflowService()
    return handle_errors(
        lambda: JobDetail(
            **service.fill_uploaded_folder(
                read_folder_upload(files, relative_paths),
                lang,
                output_name=output_name,
                project_id=project_id,
            )
        )
    )


@router.post("/api/projects/{project_id}/qa", response_model=JobDetail)
def project_qa(project_id: int, payload: QaRequest) -> JobDetail:
    return handle_errors(lambda: JobDetail(**WorkflowService().qa(payload.source_dir, payload.lang, project_id)))


@router.post("/api/projects/{project_id}/qa/upload-folder", response_model=JobDetail)
def project_qa_upload_folder(
    project_id: int,
    lang: str = Form(...),
    files: list[UploadFile] = File(...),
    relative_paths: list[str] = Form(...),
) -> JobDetail:
    return handle_errors(
        lambda: JobDetail(
            **WorkflowService().qa_uploaded_folder(
                read_folder_upload(files, relative_paths),
                lang,
                project_id=project_id,
            )
        )
    )
