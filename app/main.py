from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.routers import (
    inspection_router,
    imports_jobs_router,
    pages_router,
    projects_state_router,
    scopes_read_models_router,
    workflows_router,
    workbook_workflows_router,
)
from app.services.demo.service import DemoService
from app.services.shared.background_jobs import shutdown_background_jobs

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    DemoService().ensure_sample_files()
    yield
    shutdown_background_jobs(wait=True)


app = FastAPI(title="Momo TMS", version="0.2.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(pages_router)
app.include_router(projects_state_router)
app.include_router(imports_jobs_router)
app.include_router(workbook_workflows_router)
app.include_router(workflows_router)
app.include_router(scopes_read_models_router)
app.include_router(inspection_router)
