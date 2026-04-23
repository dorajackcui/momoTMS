from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from app.routers.common import handle_errors, read_folder_upload
from app.schemas import (
    BranchBootstrapPreview,
    BranchBootstrapRequest,
    BranchMutationPreview,
    BranchMutationRequest,
    BranchReplacePreview,
    BranchReplaceRequest,
    DevBranchDetail,
    DevBranchSummary,
    FillRequest,
    JobDetail,
    PivotReviewPreview,
    PivotReviewRequest,
    QaRequest,
    BranchTrashDeleteRequest,
    VariantTrashRestoreRequest,
)
from app.services.read_models.derived.branch_catalog import BranchCatalogView
from app.services.workflows.application import WorkflowApplicationService

router = APIRouter()


@router.post("/api/projects/{project_id}/branches/bootstrap/preview", response_model=BranchBootstrapPreview)
def project_branch_bootstrap_preview(project_id: int, payload: BranchBootstrapRequest) -> BranchBootstrapPreview:
    service = WorkflowApplicationService()
    return handle_errors(
        lambda: BranchBootstrapPreview(
            **service.branch_bootstrap_preview(
                payload.branch_ref,
                payload.import_batch_id,
                project_id=project_id,
            )
        )
    )


@router.post("/api/projects/{project_id}/branches/bootstrap", response_model=JobDetail)
def project_branch_bootstrap(project_id: int, payload: BranchBootstrapRequest) -> JobDetail:
    service = WorkflowApplicationService()
    return handle_errors(
        lambda: JobDetail(
            **service.branch_bootstrap(
                payload.branch_ref,
                payload.import_batch_id,
                project_id=project_id,
            )
        )
    )


@router.post("/api/projects/{project_id}/branches/mutations/preview", response_model=BranchMutationPreview)
def project_branch_mutation_preview(project_id: int, payload: BranchMutationRequest) -> BranchMutationPreview:
    service = WorkflowApplicationService()
    return handle_errors(
        lambda: BranchMutationPreview(
            **service.branch_mutation_preview(
                payload.branch_ref,
                payload.input.model_dump(mode="python"),
                project_id=project_id,
            )
        )
    )


@router.post("/api/projects/{project_id}/branches/mutations", response_model=JobDetail)
def project_branch_mutation(project_id: int, payload: BranchMutationRequest) -> JobDetail:
    service = WorkflowApplicationService()
    return handle_errors(
        lambda: JobDetail(
            **service.branch_mutation(
                payload.branch_ref,
                payload.input.model_dump(mode="python"),
                project_id=project_id,
            )
        )
    )


@router.get("/api/projects/{project_id}/branches/dev", response_model=list[DevBranchSummary])
def project_list_dev_branches(project_id: int) -> list[DevBranchSummary]:
    return handle_errors(
        lambda: [
            DevBranchSummary(**item)
            for item in BranchCatalogView().list_dev_branches(project_id=project_id)
        ]
    )


@router.get("/api/projects/{project_id}/branches/dev/{version}", response_model=DevBranchDetail)
def project_get_dev_branch(project_id: int, version: str) -> DevBranchDetail:
    return handle_errors(lambda: DevBranchDetail(**BranchCatalogView().get_dev_branch(version, project_id)))


@router.post("/api/projects/{project_id}/branches/replace/preview", response_model=BranchReplacePreview)
def project_branch_replace_preview(project_id: int, payload: BranchReplaceRequest) -> BranchReplacePreview:
    return handle_errors(
        lambda: BranchReplacePreview(
            **WorkflowApplicationService().branch_replace_preview(
                payload.source_branch_ref,
                payload.target_branch_ref,
                project_id,
            )
        )
    )


@router.post("/api/projects/{project_id}/branches/replace/execute", response_model=JobDetail)
def project_branch_replace_execute(project_id: int, payload: BranchReplaceRequest) -> JobDetail:
    return handle_errors(
        lambda: JobDetail(
            **WorkflowApplicationService().branch_replace_execute(
                payload.source_branch_ref,
                payload.target_branch_ref,
                project_id,
            )
        )
    )


@router.post("/api/projects/{project_id}/variants/trash/delete", response_model=JobDetail)
def project_trash_delete(project_id: int, payload: BranchTrashDeleteRequest) -> JobDetail:
    return handle_errors(
        lambda: JobDetail(
            **WorkflowApplicationService().trash_delete(
                payload.branch_ref,
                payload.business_keys,
                project_id=project_id,
            )
        )
    )


@router.post("/api/projects/{project_id}/variants/trash/restore", response_model=JobDetail)
def project_trash_restore(project_id: int, payload: VariantTrashRestoreRequest) -> JobDetail:
    return handle_errors(
        lambda: JobDetail(
            **WorkflowApplicationService().trash_restore(
                payload.variant_ids,
                project_id=project_id,
            )
        )
    )


@router.post("/api/projects/{project_id}/variants/pivot/review/preview", response_model=PivotReviewPreview)
def project_pivot_review_preview(project_id: int, payload: PivotReviewRequest) -> PivotReviewPreview:
    return handle_errors(
        lambda: PivotReviewPreview(
            **WorkflowApplicationService().pivot_review_preview(
                payload.branch_ref,
                payload.variant_ids,
                project_id=project_id,
            )
        )
    )


@router.post("/api/projects/{project_id}/variants/pivot/review", response_model=JobDetail)
def project_pivot_review(project_id: int, payload: PivotReviewRequest) -> JobDetail:
    return handle_errors(
        lambda: JobDetail(
            **WorkflowApplicationService().pivot_review(
                payload.branch_ref,
                payload.variant_ids,
                project_id=project_id,
            )
        )
    )


@router.post("/api/projects/{project_id}/fill", response_model=JobDetail)
def project_fill(project_id: int, payload: FillRequest) -> JobDetail:
    service = WorkflowApplicationService()
    return handle_errors(lambda: JobDetail(**service.fill(payload.source_dir, payload.lang, payload.output_name, project_id)))


@router.post("/api/projects/{project_id}/fill/upload-folder", response_model=JobDetail)
def project_fill_upload_folder(
    project_id: int,
    lang: str = Form(...),
    output_name: str | None = Form(default=None),
    files: list[UploadFile] = File(...),
    relative_paths: list[str] = Form(...),
) -> JobDetail:
    service = WorkflowApplicationService()
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
    return handle_errors(lambda: JobDetail(**WorkflowApplicationService().qa(payload.source_dir, payload.lang, project_id)))


@router.post("/api/projects/{project_id}/qa/upload-folder", response_model=JobDetail)
def project_qa_upload_folder(
    project_id: int,
    lang: str = Form(...),
    files: list[UploadFile] = File(...),
    relative_paths: list[str] = Form(...),
) -> JobDetail:
    return handle_errors(
        lambda: JobDetail(
            **WorkflowApplicationService().qa_uploaded_folder(
                read_folder_upload(files, relative_paths),
                lang,
                project_id=project_id,
            )
        )
    )
