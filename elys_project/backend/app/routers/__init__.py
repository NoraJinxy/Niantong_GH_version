"""
Purpose: FastAPI routers entry point.
Related: app/schemas/*, app/models/*, app/services/*, app/routers/auth.py, docs_v2/2-50.
"""

from .auth import router as auth_router
from .dashboard import router as dashboard_router
from .datasets import asset_router as dataset_assets_router
from .datasets import file_router as dataset_files_router
from .datasets import recording_router
from .datasets import router as datasets_router
from .dataset_versions import admin_router as dataset_withdrawals_router
from .dataset_versions import asset_publicize_router as dataset_publicize_router
from .dataset_versions import publicization_admin_router as dataset_publicizations_router
from .dataset_versions import router as dataset_versions_router
from .pipelines import router as pipelines_router
from .studies import router as studies_router

__all__ = [
    "auth_router",
    "dashboard_router",
    "dataset_assets_router",
    "dataset_files_router",
    "datasets_router",
    "dataset_versions_router",
    "dataset_withdrawals_router",
    "dataset_publicize_router",
    "dataset_publicizations_router",
    "pipelines_router",
    "studies_router",
    "recording_router",
]
