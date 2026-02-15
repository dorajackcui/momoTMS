from __future__ import annotations

from fastapi import FastAPI

from app.db import init_db
from app.schemas import (
    ActiveSingleRequest,
    FillReport,
    FillRequest,
    ImportRequest,
    ImportResponse,
    PassiveSingleRequest,
    PromoteReport,
    PromoteRequest,
    SnapshotCreateRequest,
    SnapshotResponse,
)
from app.services.fill_service import FillService
from app.services.import_service import ImportService
from app.services.promote_service import PromoteService
from app.services.snapshot_service import SnapshotService
from app.services.update_service import UpdateService

app = FastAPI(title="Momo TMS", version="0.1.0")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


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
