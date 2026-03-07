from app.routers.inspection import router as inspection_router
from app.routers.imports_jobs import router as imports_jobs_router
from app.routers.pages import router as pages_router
from app.routers.projects_state import router as projects_state_router
from app.routers.scopes_read_models import router as scopes_read_models_router
from app.routers.workflows import router as workflows_router

__all__ = [
    "inspection_router",
    "imports_jobs_router",
    "pages_router",
    "projects_state_router",
    "scopes_read_models_router",
    "workflows_router",
]
