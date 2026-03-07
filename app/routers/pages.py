from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

APP_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = APP_DIR / "static"


@router.get("/workbench")
def workbench() -> FileResponse:
    return FileResponse(STATIC_DIR / "workbench.html")


@router.get("/variant-workbench")
def variant_workbench() -> FileResponse:
    return FileResponse(STATIC_DIR / "variant-workbench.html")


@router.get("/app")
def product_app() -> FileResponse:
    product_index = STATIC_DIR / "product-app" / "index.html"
    if not product_index.exists():
        raise HTTPException(status_code=503, detail="product app build not found")
    return FileResponse(product_index)


@router.get("/app/{path:path}")
def product_app_subpath(path: str) -> FileResponse:
    return product_app()
