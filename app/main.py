from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.schemas import (
    DevImportRequest,
    DevVersionDetail,
    DevVersionSummary,
    FillRequest,
    ImportBatchSummary,
    ImportDirectoryRequest,
    JobDetail,
    JobSummary,
    PromoteExecuteRequest,
    PromotePreview,
    PromotePreviewRequest,
    QaRequest,
    RelHotfixActiveRequest,
    RelHotfixPassiveRequest,
    ReportPayload,
    StateResponse,
    StringDetail,
    TrashDeleteRequest,
    TrashRestoreRequest,
)
from app.services.demo_service import DemoService
from app.services.dev_version_service import DevVersionService
from app.services.import_service import ImportService
from app.services.job_service import JobService
from app.services.string_service import StringService
from app.services.workbench_service import WorkbenchService

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"

app = FastAPI(title="Momo TMS", version="0.2.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    DemoService().ensure_sample_files()


@app.get("/workbench")
def workbench() -> FileResponse:
    return FileResponse(STATIC_DIR / "workbench.html")


@app.get("/api/state", response_model=StateResponse)
def state() -> StateResponse:
    return _handle(lambda: StateResponse(**WorkbenchService().get_state()))


@app.post("/api/demo/reset", response_model=StateResponse)
def demo_reset() -> StateResponse:
    def run() -> StateResponse:
        DemoService().reset()
        return StateResponse(**WorkbenchService().get_state())

    return _handle(run)


@app.get("/api/strings", response_model=list[StringDetail])
def list_strings(
    search: str | None = Query(default=None),
    include_deleted: bool = Query(default=False),
) -> list[StringDetail]:
    strings = StringService().list_strings(search=search, include_deleted=include_deleted)
    return [StringDetail(**item) for item in strings]


@app.get("/api/strings/{business_key}", response_model=StringDetail)
def get_string(business_key: str) -> StringDetail:
    def run() -> StringDetail:
        item = StringService().get_string(business_key, include_deleted=True)
        if not item:
            raise KeyError(f"string not found: {business_key}")
        return StringDetail(**item)

    return _handle(run)


@app.post("/api/imports/directory", response_model=JobDetail)
def import_directory(payload: ImportDirectoryRequest) -> JobDetail:
    return _handle(lambda: JobDetail(**WorkbenchService().import_directory(payload.input_dir)))


@app.get("/api/imports", response_model=list[ImportBatchSummary])
def list_imports() -> list[ImportBatchSummary]:
    return [ImportBatchSummary(**item) for item in ImportService().list_batches()]


@app.get("/api/imports/{import_batch_id}/report", response_model=ReportPayload)
def import_report(import_batch_id: int) -> ReportPayload:
    return _handle(lambda: ReportPayload(**ImportService().import_report(import_batch_id, issues_only=False)))


@app.post("/api/dev-versions/import", response_model=JobDetail)
def dev_import(payload: DevImportRequest) -> JobDetail:
    service = WorkbenchService()
    return _handle(
        lambda: JobDetail(
            **service.dev_import(
                payload.import_batch_id,
                payload.version,
                payload.mark_as_candidate,
            )
        )
    )


@app.get("/api/dev-versions", response_model=list[DevVersionSummary])
def list_dev_versions() -> list[DevVersionSummary]:
    return [DevVersionSummary(**item) for item in DevVersionService().list_versions(active_only=True)]


@app.get("/api/dev-versions/{version}", response_model=DevVersionDetail)
def get_dev_version(version: str) -> DevVersionDetail:
    return _handle(lambda: DevVersionDetail(**DevVersionService().get_version(version)))


@app.post("/api/rel/hotfix/active", response_model=JobDetail)
def rel_hotfix_active(payload: RelHotfixActiveRequest) -> JobDetail:
    service = WorkbenchService()
    return _handle(
        lambda: JobDetail(
            **service.active_hotfix(
                payload.business_key,
                payload.lang,
                payload.target_text,
            )
        )
    )


@app.post("/api/rel/hotfix/passive", response_model=JobDetail)
def rel_hotfix_passive(payload: RelHotfixPassiveRequest) -> JobDetail:
    service = WorkbenchService()
    return _handle(
        lambda: JobDetail(
            **service.passive_hotfix(
                payload.business_key,
                payload.source,
                payload.translations_by_lang,
                payload.remarks_by_key,
                payload.file_name,
            )
        )
    )


@app.post("/api/promote/preview", response_model=PromotePreview)
def promote_preview(payload: PromotePreviewRequest) -> PromotePreview:
    return _handle(lambda: PromotePreview(**WorkbenchService().preview_promote(payload.version)))


@app.post("/api/promote/execute", response_model=JobDetail)
def promote_execute(payload: PromoteExecuteRequest) -> JobDetail:
    return _handle(lambda: JobDetail(**WorkbenchService().execute_promote(payload.version)))


@app.post("/api/trash/delete", response_model=JobDetail)
def trash_delete(payload: TrashDeleteRequest) -> JobDetail:
    return _handle(lambda: JobDetail(**WorkbenchService().trash_delete(payload.business_keys)))


@app.post("/api/trash/restore", response_model=JobDetail)
def trash_restore(payload: TrashRestoreRequest) -> JobDetail:
    return _handle(lambda: JobDetail(**WorkbenchService().trash_restore(payload.business_keys)))


@app.post("/api/fill", response_model=JobDetail)
def fill(payload: FillRequest) -> JobDetail:
    service = WorkbenchService()
    return _handle(lambda: JobDetail(**service.fill(payload.source_dir, payload.lang, payload.output_name)))


@app.post("/api/qa", response_model=JobDetail)
def qa(payload: QaRequest) -> JobDetail:
    return _handle(lambda: JobDetail(**WorkbenchService().qa(payload.source_dir, payload.lang)))


@app.get("/api/jobs", response_model=list[JobSummary])
def list_jobs() -> list[JobSummary]:
    return [JobSummary(**item) for item in JobService().list_jobs()]


@app.get("/api/jobs/{job_id}", response_model=JobDetail)
def job_detail(job_id: int) -> JobDetail:
    return _handle(lambda: JobDetail(**WorkbenchService().get_job_detail(job_id)))


@app.get("/api/jobs/{job_id}/report", response_model=ReportPayload)
def job_report(job_id: int) -> ReportPayload:
    return _handle(lambda: ReportPayload(**JobService().get_report(job_id)))


@app.get("/api/jobs/{job_id}/artifact/{name}")
def job_artifact(job_id: int, name: str) -> FileResponse:
    def run() -> FileResponse:
        job = JobService().get_job(job_id)
        artifact_path = job.get("artifact_path")
        if not artifact_path:
            raise FileNotFoundError(f"job has no artifact: {job_id}")
        path = Path(artifact_path)
        if not path.exists() or path.name != name:
            raise FileNotFoundError(f"artifact not found: {name}")
        return FileResponse(path)

    return _handle(run)


def _handle(fn):
    try:
        return fn()
    except (KeyError, ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
