from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse

from app.schemas import (
    ImportBatchSummary,
    ImportDirectoryRequest,
    ImportUploadPreview,
    JobDetail,
    JobSummary,
    ReportPayload,
)
from app.services.imports.service import ImportService
from app.services.shared.jobs import JobService
from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.workflows.workbench import WorkbenchService
from app.routers.common import handle_errors, parse_column_mapping_json, read_folder_upload

router = APIRouter()


@router.post("/api/imports/directory", response_model=JobDetail)
def import_directory(payload: ImportDirectoryRequest) -> JobDetail:
    return handle_errors(lambda: JobDetail(**WorkbenchService().import_directory(payload.input_dir)))


@router.post("/api/projects/{project_id}/imports/directory", response_model=JobDetail)
def project_import_directory(project_id: int, payload: ImportDirectoryRequest) -> JobDetail:
    return handle_errors(lambda: JobDetail(**WorkbenchService().import_directory(payload.input_dir, project_id=project_id)))


@router.post("/api/imports/upload-folder", response_model=JobDetail)
def import_upload_folder(
    files: list[UploadFile] = File(...),
    relative_paths: list[str] = Form(...),
    column_mapping_json: str | None = Form(default=None),
) -> JobDetail:
    return handle_errors(
        lambda: JobDetail(
            **WorkbenchService().import_uploaded_folder(
                read_folder_upload(files, relative_paths),
                project_id=DEFAULT_PROJECT_ID,
                mapping_overrides=parse_column_mapping_json(column_mapping_json),
            )
        )
    )


@router.post("/api/projects/{project_id}/imports/upload-folder", response_model=JobDetail)
def project_import_upload_folder(
    project_id: int,
    files: list[UploadFile] = File(...),
    relative_paths: list[str] = Form(...),
    column_mapping_json: str | None = Form(default=None),
) -> JobDetail:
    return handle_errors(
        lambda: JobDetail(
            **WorkbenchService().import_uploaded_folder(
                read_folder_upload(files, relative_paths),
                project_id=project_id,
                mapping_overrides=parse_column_mapping_json(column_mapping_json),
            )
        )
    )


@router.post("/api/imports/upload-folder/preview", response_model=ImportUploadPreview)
def import_upload_folder_preview(
    files: list[UploadFile] = File(...),
    relative_paths: list[str] = Form(...),
) -> ImportUploadPreview:
    return handle_errors(
        lambda: ImportUploadPreview(
            **WorkbenchService().preview_import_uploaded_folder(
                read_folder_upload(files, relative_paths),
                project_id=DEFAULT_PROJECT_ID,
            )
        )
    )


@router.post("/api/projects/{project_id}/imports/upload-folder/preview", response_model=ImportUploadPreview)
def project_import_upload_folder_preview(
    project_id: int,
    files: list[UploadFile] = File(...),
    relative_paths: list[str] = Form(...),
) -> ImportUploadPreview:
    return handle_errors(
        lambda: ImportUploadPreview(
            **WorkbenchService().preview_import_uploaded_folder(
                read_folder_upload(files, relative_paths),
                project_id=project_id,
            )
        )
    )


@router.get("/api/imports", response_model=list[ImportBatchSummary])
def list_imports() -> list[ImportBatchSummary]:
    return [ImportBatchSummary(**item) for item in ImportService().list_batches(project_id=DEFAULT_PROJECT_ID)]


@router.get("/api/projects/{project_id}/imports", response_model=list[ImportBatchSummary])
def project_list_imports(project_id: int) -> list[ImportBatchSummary]:
    return [ImportBatchSummary(**item) for item in ImportService().list_batches(project_id=project_id)]


@router.get("/api/imports/{import_batch_id}/report", response_model=ReportPayload)
def import_report(import_batch_id: int) -> ReportPayload:
    return handle_errors(lambda: ReportPayload(**ImportService().import_report(import_batch_id, issues_only=False)))


@router.get("/api/projects/{project_id}/imports/{import_batch_id}/report", response_model=ReportPayload)
def project_import_report(project_id: int, import_batch_id: int) -> ReportPayload:
    def run() -> ReportPayload:
        ImportService().require_batch_project(import_batch_id, project_id)
        return ReportPayload(**ImportService().import_report(import_batch_id, issues_only=False))

    return handle_errors(run)


@router.get("/api/jobs", response_model=list[JobSummary])
def list_jobs() -> list[JobSummary]:
    return [JobSummary(**item) for item in JobService().list_jobs(project_id=DEFAULT_PROJECT_ID)]


@router.get("/api/projects/{project_id}/jobs", response_model=list[JobSummary])
def project_list_jobs(project_id: int) -> list[JobSummary]:
    return [JobSummary(**item) for item in JobService().list_jobs(project_id=project_id)]


@router.get("/api/jobs/{job_id}", response_model=JobDetail)
def job_detail(job_id: int) -> JobDetail:
    return handle_errors(lambda: JobDetail(**WorkbenchService().get_job_detail(job_id, project_id=DEFAULT_PROJECT_ID)))


@router.get("/api/projects/{project_id}/jobs/{job_id}", response_model=JobDetail)
def project_job_detail(project_id: int, job_id: int) -> JobDetail:
    return handle_errors(lambda: JobDetail(**WorkbenchService().get_job_detail(job_id, project_id=project_id)))


@router.get("/api/jobs/{job_id}/report", response_model=ReportPayload)
def job_report(job_id: int) -> ReportPayload:
    return handle_errors(lambda: ReportPayload(**JobService().get_report(job_id, project_id=DEFAULT_PROJECT_ID)))


@router.get("/api/projects/{project_id}/jobs/{job_id}/report", response_model=ReportPayload)
def project_job_report(project_id: int, job_id: int) -> ReportPayload:
    return handle_errors(lambda: ReportPayload(**JobService().get_report(job_id, project_id=project_id)))


@router.get("/api/jobs/{job_id}/artifact/{name}")
def job_artifact(job_id: int, name: str) -> FileResponse:
    def run() -> FileResponse:
        job = JobService().get_job(job_id, project_id=DEFAULT_PROJECT_ID)
        artifact_path = job.get("artifact_path")
        if not artifact_path:
            raise FileNotFoundError(f"job has no artifact: {job_id}")
        path = Path(artifact_path)
        if not path.exists() or path.name != name:
            raise FileNotFoundError(f"artifact not found: {name}")
        return FileResponse(path)

    return handle_errors(run)


@router.get("/api/projects/{project_id}/jobs/{job_id}/artifact/{name}")
def project_job_artifact(project_id: int, job_id: int, name: str) -> FileResponse:
    def run() -> FileResponse:
        job = JobService().get_job(job_id, project_id=project_id)
        artifact_path = job.get("artifact_path")
        if not artifact_path:
            raise FileNotFoundError(f"job has no artifact: {job_id}")
        path = Path(artifact_path)
        if not path.exists() or path.name != name:
            raise FileNotFoundError(f"artifact not found: {name}")
        return FileResponse(path)

    return handle_errors(run)
