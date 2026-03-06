from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.schemas import (
    ActiveSingleRequest,
    DeleteKeysRequest,
    FillReport,
    FillRequest,
    ImportRequest,
    ImportResponse,
    JobDetail,
    JobSummary,
    PassiveSingleRequest,
    PromotePreview,
    PromotePreviewRequest,
    PromoteReport,
    PromoteRequest,
    ReportPayload,
    SampleActionRequest,
    SnapshotCreateRequest,
    SnapshotResponse,
    WorkbenchActiveHotfixRequest,
    WorkbenchPassiveHotfixRequest,
    WorkbenchState,
)
from app.services.demo_service import DemoService
from app.services.fill_service import FillService
from app.services.import_service import ImportService
from app.services.job_service import JobService
from app.services.promote_service import PromoteService
from app.services.snapshot_service import SnapshotService
from app.services.update_service import UpdateService
from app.services.workbench_service import WorkbenchService

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"

app = FastAPI(title="Momo TMS", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    DemoService().ensure_sample_files()


@app.post("/import", response_model=ImportResponse)
def import_batch(payload: ImportRequest) -> ImportResponse:
    svc = ImportService()
    result = svc.import_directory(payload.input_dir, payload.lang, payload.target_col_index)
    return ImportResponse(**result)


@app.get("/import/{import_batch_id}/report")
def import_report(import_batch_id: int) -> list[dict]:
    svc = ImportService()
    return svc.import_report(import_batch_id)


@app.post("/snapshot", response_model=SnapshotResponse)
def create_snapshot(payload: SnapshotCreateRequest) -> SnapshotResponse:
    svc = SnapshotService()
    snapshot_id = svc.create_snapshot(payload.branch, payload.action_type, payload.parent_snapshot_id, payload.meta)
    return SnapshotResponse(snapshot_id=snapshot_id, branch=payload.branch, action_type=payload.action_type)


@app.post("/update/dev")
def update_dev(source_dir: str, lang: str, version_tag: str, parent_snapshot_id: int | None = None, target_col_index: int = 3) -> dict:
    svc = UpdateService()
    snapshot_id = svc.update_dev_from_directory(source_dir, lang, version_tag, parent_snapshot_id, target_col_index)
    return {"snapshot_id": snapshot_id}


@app.post("/update/release/active_single")
def active_single(payload: ActiveSingleRequest) -> dict:
    svc = UpdateService()
    snapshot_id = svc.update_release_active_single(payload.release_snapshot_id, payload.key, payload.lang, payload.target_text)
    return {"snapshot_id": snapshot_id}


@app.post("/update/release/passive_single")
def passive_single(payload: PassiveSingleRequest) -> dict:
    svc = UpdateService()
    snapshot_id = svc.update_release_passive_single(
        payload.release_snapshot_id,
        payload.key,
        payload.src,
        payload.targets_by_lang,
        payload.version_tag,
    )
    return {"snapshot_id": snapshot_id}


@app.post("/promote", response_model=PromoteReport)
def promote(payload: PromoteRequest) -> PromoteReport:
    svc = PromoteService()
    report = svc.promote(payload.dev_last_snapshot_id, payload.current_release_snapshot_id, payload.release_version)
    return PromoteReport(**report)


@app.post("/fill", response_model=FillReport)
def fill(payload: FillRequest) -> FillReport:
    svc = FillService()
    report = svc.fill_and_export(
        payload.source_dir,
        payload.output_zip,
        payload.lang,
        payload.release_snapshot_id,
        payload.master_snapshot_id,
        payload.target_col_index,
    )
    return FillReport(**report)


@app.get("/workbench")
def workbench() -> FileResponse:
    return FileResponse(STATIC_DIR / "workbench.html")


@app.get("/api/workbench/state", response_model=WorkbenchState)
def workbench_state() -> WorkbenchState:
    return _handle(lambda: WorkbenchState(**WorkbenchService().get_state()))


@app.post("/api/demo/reset", response_model=WorkbenchState)
def demo_reset() -> WorkbenchState:
    def run() -> WorkbenchState:
        demo = DemoService()
        demo.reset()
        return WorkbenchState(**WorkbenchService().get_state())

    return _handle(run)


@app.post("/api/workbench/import")
def workbench_import(payload: SampleActionRequest) -> dict:
    return _handle(lambda: WorkbenchService().import_sample(payload.sample_id))


@app.post("/api/workbench/update-dev", response_model=JobDetail)
def workbench_update_dev(payload: SampleActionRequest) -> JobDetail:
    return _handle(lambda: JobDetail(**WorkbenchService().update_dev(payload.sample_id)))


@app.post("/api/workbench/hotfix/active", response_model=JobDetail)
def workbench_active_hotfix(payload: WorkbenchActiveHotfixRequest) -> JobDetail:
    return _handle(lambda: JobDetail(**WorkbenchService().active_hotfix(payload.model_dump())))


@app.post("/api/workbench/hotfix/passive", response_model=JobDetail)
def workbench_passive_hotfix(payload: WorkbenchPassiveHotfixRequest) -> JobDetail:
    return _handle(lambda: JobDetail(**WorkbenchService().passive_hotfix(payload.model_dump())))


@app.post("/api/workbench/promote/preview", response_model=PromotePreview)
def workbench_promote_preview(payload: PromotePreviewRequest) -> PromotePreview:
    return _handle(lambda: PromotePreview(**WorkbenchService().preview_promote(payload.release_version)))


@app.post("/api/workbench/promote/execute", response_model=JobDetail)
def workbench_promote_execute(payload: PromotePreviewRequest) -> JobDetail:
    return _handle(lambda: JobDetail(**WorkbenchService().execute_promote(payload.release_version)))


@app.post("/api/workbench/archive", response_model=JobDetail)
def workbench_archive() -> JobDetail:
    return _handle(lambda: JobDetail(**WorkbenchService().archive_release()))


@app.post("/api/workbench/delete", response_model=JobDetail)
def workbench_delete(payload: DeleteKeysRequest) -> JobDetail:
    return _handle(lambda: JobDetail(**WorkbenchService().delete_keys(payload.branch, payload.keys)))


@app.post("/api/workbench/fill", response_model=JobDetail)
def workbench_fill(payload: SampleActionRequest) -> JobDetail:
    return _handle(lambda: JobDetail(**WorkbenchService().fill_sample(payload.sample_id)))


@app.post("/api/workbench/qa", response_model=JobDetail)
def workbench_qa(payload: SampleActionRequest) -> JobDetail:
    return _handle(lambda: JobDetail(**WorkbenchService().qa_sample(payload.sample_id)))


@app.get("/api/jobs", response_model=list[JobSummary])
def list_jobs() -> list[JobSummary]:
    jobs = JobService().list_jobs()
    return [JobSummary(**job) for job in jobs]


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
