from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from app.schemas import (
    DevImportRequest,
    DevVersionDetail,
    DevVersionSummary,
    FillRequest,
    JobDetail,
    PromoteExecuteRequest,
    PromotePreview,
    PromotePreviewRequest,
    QaRequest,
    RelHotfixActiveRequest,
    RelHotfixPassiveRequest,
    ScopedTrashDeleteRequest,
    VariantTrashRestoreRequest,
)
from app.services.workflows.dev_versions import DevVersionService
from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.workflows.workbench import WorkbenchService
from app.routers.common import handle_errors, read_folder_upload

router = APIRouter()


@router.post("/api/dev-versions/import", response_model=JobDetail)
def dev_import(payload: DevImportRequest) -> JobDetail:
    service = WorkbenchService()
    return handle_errors(
        lambda: JobDetail(
            **service.dev_import(
                payload.import_batch_id,
                payload.version,
                payload.mark_as_candidate,
                project_id=DEFAULT_PROJECT_ID,
            )
        )
    )


@router.post("/api/projects/{project_id}/dev-versions/import", response_model=JobDetail)
def project_dev_import(project_id: int, payload: DevImportRequest) -> JobDetail:
    service = WorkbenchService()
    return handle_errors(
        lambda: JobDetail(
            **service.dev_import(
                payload.import_batch_id,
                payload.version,
                payload.mark_as_candidate,
                project_id=project_id,
            )
        )
    )


@router.get("/api/dev-versions", response_model=list[DevVersionSummary])
def list_dev_versions() -> list[DevVersionSummary]:
    return [DevVersionSummary(**item) for item in DevVersionService().list_versions(project_id=DEFAULT_PROJECT_ID, active_only=True)]


@router.get("/api/projects/{project_id}/dev-versions", response_model=list[DevVersionSummary])
def project_list_dev_versions(project_id: int) -> list[DevVersionSummary]:
    return [DevVersionSummary(**item) for item in DevVersionService().list_versions(project_id=project_id, active_only=True)]


@router.get("/api/dev-versions/{version}", response_model=DevVersionDetail)
def get_dev_version(version: str) -> DevVersionDetail:
    return handle_errors(lambda: DevVersionDetail(**DevVersionService().get_version(version, DEFAULT_PROJECT_ID)))


@router.get("/api/projects/{project_id}/dev-versions/{version}", response_model=DevVersionDetail)
def project_get_dev_version(project_id: int, version: str) -> DevVersionDetail:
    return handle_errors(lambda: DevVersionDetail(**DevVersionService().get_version(version, project_id)))


@router.post("/api/projects/{project_id}/scopes/rel/current/hotfix/active", response_model=JobDetail)
def project_rel_hotfix_active(project_id: int, payload: RelHotfixActiveRequest) -> JobDetail:
    service = WorkbenchService()
    return handle_errors(
        lambda: JobDetail(
            **service.active_hotfix(
                payload.business_key,
                payload.lang,
                payload.target_text,
                project_id=project_id,
            )
        )
    )


@router.post("/api/projects/{project_id}/scopes/rel/current/hotfix/passive", response_model=JobDetail)
def project_rel_hotfix_passive(project_id: int, payload: RelHotfixPassiveRequest) -> JobDetail:
    service = WorkbenchService()
    return handle_errors(
        lambda: JobDetail(
            **service.passive_hotfix(
                payload.business_key,
                payload.source,
                payload.translations_by_lang,
                payload.remarks_by_key,
                payload.file_name,
                project_id=project_id,
            )
        )
    )


@router.post("/api/promote/preview", response_model=PromotePreview)
def promote_preview(payload: PromotePreviewRequest) -> PromotePreview:
    return handle_errors(lambda: PromotePreview(**WorkbenchService().preview_promote(payload.version, DEFAULT_PROJECT_ID)))


@router.post("/api/projects/{project_id}/promote/preview", response_model=PromotePreview)
def project_promote_preview(project_id: int, payload: PromotePreviewRequest) -> PromotePreview:
    return handle_errors(lambda: PromotePreview(**WorkbenchService().preview_promote(payload.version, project_id)))


@router.post("/api/promote/execute", response_model=JobDetail)
def promote_execute(payload: PromoteExecuteRequest) -> JobDetail:
    return handle_errors(lambda: JobDetail(**WorkbenchService().execute_promote(payload.version, DEFAULT_PROJECT_ID)))


@router.post("/api/projects/{project_id}/promote/execute", response_model=JobDetail)
def project_promote_execute(project_id: int, payload: PromoteExecuteRequest) -> JobDetail:
    return handle_errors(lambda: JobDetail(**WorkbenchService().execute_promote(payload.version, project_id)))


@router.post("/api/projects/{project_id}/variants/trash/delete", response_model=JobDetail)
def project_trash_delete(project_id: int, payload: ScopedTrashDeleteRequest) -> JobDetail:
    return handle_errors(
        lambda: JobDetail(
            **WorkbenchService().trash_delete(
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
            **WorkbenchService().trash_restore(
                payload.variant_ids,
                project_id=project_id,
            )
        )
    )


@router.post("/api/fill", response_model=JobDetail)
def fill(payload: FillRequest) -> JobDetail:
    service = WorkbenchService()
    return handle_errors(lambda: JobDetail(**service.fill(payload.source_dir, payload.lang, payload.output_name, DEFAULT_PROJECT_ID)))


@router.post("/api/projects/{project_id}/fill", response_model=JobDetail)
def project_fill(project_id: int, payload: FillRequest) -> JobDetail:
    service = WorkbenchService()
    return handle_errors(lambda: JobDetail(**service.fill(payload.source_dir, payload.lang, payload.output_name, project_id)))


@router.post("/api/fill/upload-folder", response_model=JobDetail)
def fill_upload_folder(
    lang: str = Form(...),
    output_name: str | None = Form(default=None),
    files: list[UploadFile] = File(...),
    relative_paths: list[str] = Form(...),
) -> JobDetail:
    service = WorkbenchService()
    return handle_errors(
        lambda: JobDetail(
            **service.fill_uploaded_folder(
                read_folder_upload(files, relative_paths),
                lang,
                output_name=output_name,
                project_id=DEFAULT_PROJECT_ID,
            )
        )
    )


@router.post("/api/projects/{project_id}/fill/upload-folder", response_model=JobDetail)
def project_fill_upload_folder(
    project_id: int,
    lang: str = Form(...),
    output_name: str | None = Form(default=None),
    files: list[UploadFile] = File(...),
    relative_paths: list[str] = Form(...),
) -> JobDetail:
    service = WorkbenchService()
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


@router.post("/api/qa", response_model=JobDetail)
def qa(payload: QaRequest) -> JobDetail:
    return handle_errors(lambda: JobDetail(**WorkbenchService().qa(payload.source_dir, payload.lang, DEFAULT_PROJECT_ID)))


@router.post("/api/projects/{project_id}/qa", response_model=JobDetail)
def project_qa(project_id: int, payload: QaRequest) -> JobDetail:
    return handle_errors(lambda: JobDetail(**WorkbenchService().qa(payload.source_dir, payload.lang, project_id)))


@router.post("/api/qa/upload-folder", response_model=JobDetail)
def qa_upload_folder(
    lang: str = Form(...),
    files: list[UploadFile] = File(...),
    relative_paths: list[str] = Form(...),
) -> JobDetail:
    return handle_errors(
        lambda: JobDetail(
            **WorkbenchService().qa_uploaded_folder(
                read_folder_upload(files, relative_paths),
                lang,
                project_id=DEFAULT_PROJECT_ID,
            )
        )
    )


@router.post("/api/projects/{project_id}/qa/upload-folder", response_model=JobDetail)
def project_qa_upload_folder(
    project_id: int,
    lang: str = Form(...),
    files: list[UploadFile] = File(...),
    relative_paths: list[str] = Form(...),
) -> JobDetail:
    return handle_errors(
        lambda: JobDetail(
            **WorkbenchService().qa_uploaded_folder(
                read_folder_upload(files, relative_paths),
                lang,
                project_id=project_id,
            )
        )
    )
