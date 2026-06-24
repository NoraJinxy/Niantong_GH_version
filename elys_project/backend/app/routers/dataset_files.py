"""
Purpose: FastAPI sub-router for Dataset File endpoints under
/api/v1/dataset-files — {id}/metadata, {id}/preview, {id}/download.
Related: app/routers/_dataset_shared.py, app/services/file_browser.py, docs_v2/2-50.

Split out of the former routers/datasets.py (god-router) — see wiki 9-0x.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

try:
    from fastapi.responses import FileResponse
except Exception:  # pragma: no cover - lightweight test stubs do not provide fastapi.responses
    class FileResponse:  # type: ignore[no-redef]
        def __init__(self, path, **kwargs):
            self.path = path
            self.kwargs = kwargs
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.routers.auth import get_current_user
from app.schemas.dataset import (
    DatasetFileMetadataResponse,
    DatasetFilePreviewResponse,
)
from app.routers._dataset_shared import (
    require_system_permission,
    get_dataset_file_or_404,
    ensure_dataset_file_readable,
    handle_file_access_error,
    dataset_file_metadata_to_response,
    dataset_file_preview_to_response,
)
from app.services.file_browser import (
    FileAccessError,
    download_filename,
    resolve_dataset_file_path,
)

file_router = APIRouter(prefix="/api/v1/dataset-files", tags=["dataset-files"])


@file_router.get("/{file_id}/metadata", response_model=DatasetFileMetadataResponse)
def get_dataset_file_metadata(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:read", "当前用户没有查看 Dataset 文件权限")
    file_record = get_dataset_file_or_404(db, file_id)
    study = ensure_dataset_file_readable(db, file_record, current_user)
    return dataset_file_metadata_to_response(file_record, study=study)


@file_router.get("/{file_id}/preview", response_model=DatasetFilePreviewResponse)
def get_dataset_file_preview(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:read", "当前用户没有预览 Dataset 文件权限")
    file_record = get_dataset_file_or_404(db, file_id)
    study = ensure_dataset_file_readable(db, file_record, current_user)
    try:
        return dataset_file_preview_to_response(file_record, study=study)
    except FileAccessError as exc:
        handle_file_access_error(exc)


@file_router.get("/{file_id}/download")
def download_dataset_file(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:read", "当前用户没有下载 Dataset 文件权限")
    file_record = get_dataset_file_or_404(db, file_id)
    study = ensure_dataset_file_readable(db, file_record, current_user)
    try:
        path = resolve_dataset_file_path(file_record, study=study)
    except FileAccessError as exc:
        handle_file_access_error(exc)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DATASET_FILE_MISSING", "message": "Dataset file does not exist."},
        )
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DATASET_FILE_DOWNLOAD_DIRECTORY_UNSUPPORTED", "message": "Directory download is not supported."},
        )
    return FileResponse(
        path,
        media_type=file_record.mime_type or "application/octet-stream",
        filename=download_filename(file_record),
    )
