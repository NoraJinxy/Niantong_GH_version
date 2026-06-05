"""
Purpose: Define FastAPI routes for the datasets API area and translate HTTP requests into services/database calls.
Related: app/schemas/*, app/models/*, app/services/*, app/routers/auth.py, docs_v2/2-50.
"""

from datetime import datetime
from pathlib import Path, PurePosixPath
import hashlib
import json
import shutil
import tempfile
import uuid
from typing import Any, NamedTuple

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

try:
    from fastapi.responses import FileResponse
except Exception:  # pragma: no cover - lightweight test stubs do not provide fastapi.responses
    class FileResponse:  # type: ignore[no-redef]
        def __init__(self, path, **kwargs):
            self.path = path
            self.kwargs = kwargs
from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.models import (
    DatasetAsset,
    DatasetFile,
    DatasetFileDerivation,
    DatasetVersion,
    Study,
    AuditEvent,
    Recording,
    RecordingVersion,
    StudyDatasetMount,
    Subject,
    User,
)
from app.routers.auth import get_current_user
from app.schemas.dataset import (
    DATASET_QA_MODE_MOCK,
    DatasetBootstrapNextUpload,
    DatasetBootstrapRequest,
    DatasetBootstrapResponse,
    DatasetAssetListResponse,
    DatasetAssetResponse,
    DatasetAssetTaskRequest,
    DatasetAssetUpdate,
    DatasetFileListResponse,
    DatasetFileMetadataResponse,
    DatasetFilePreviewResponse,
    DatasetFileResponse,
    DatasetFileTreeResponse,
    DatasetImportTaskRequest,
    DatasetQaHumanReview,
    DatasetQaMockRunResponse,
    DatasetQaReport,
    DatasetQaReviewRequest,
    DatasetQaReviewResponse,
    DatasetQaResponse,
    DatasetQaSummary,
    DatasetVersionListResponse,
    DatasetVersionResponse,
    RecordingListResponse,
    RecordingResponse,
    RecordingUploadResponse,
    RecordingVersionListResponse,
    RecordingVersionResponse,
    StudyDatasetMountCreate,
    StudyDatasetMountListResponse,
    StudyDatasetMountResponse,
    StudyDatasetMountUpdate,
)
from app.schemas.pipeline import AsyncTaskResponse
from app.schemas.study import StudyResponse
from app.services.dataset_qa import build_mock_qa_report
from app.services.audit_events import record_audit_event
from app.services.dataset_assets import (
    DatasetAssetConflictError,
    DatasetMountStateError,
    can_write_dataset_asset,
    compute_asset_stats,
    empty_asset_stats,
    get_active_study_dataset_mount_for_asset,
    get_dataset_asset_for_user,
    get_or_create_working_dataset_asset,
    get_study_dataset_mount,
    get_study_dataset_mount_by_name,
    list_study_dataset_mounts,
    list_visible_dataset_assets,
    mount_dataset_asset_to_study,
    update_study_dataset_mount,
)
from app.services.dataset_bootstrap import (
    DatasetBootstrapStorageError,
    bootstrap_dataset,
)
from app.services.study_access import require_study_read, require_study_write
from app.services.recordings import (
    get_recording_for_study,
    list_recording_versions_for_study,
    list_recordings_for_study,
)
from app.services.file_browser import (
    FileAccessError,
    build_dataset_file_tree,
    dataset_file_metadata,
    dataset_file_preview,
    download_filename,
    resolve_dataset_file_path,
)
from app.services.studies import (
    StudyCreateCodeConflictError,
    StudyCreateIntegrityError,
    StudyStorageSetupError,
    ensure_study_create_permission,
)


router = APIRouter(prefix="/api/v1/studies/{study_id}/datasets", tags=["datasets"])
asset_router = APIRouter(prefix="/api/v1/dataset-assets", tags=["dataset-assets"])
file_router = APIRouter(prefix="/api/v1/dataset-files", tags=["dataset-files"])
recording_router = APIRouter(prefix="/api/v1/studies/{study_id}/recordings", tags=["recordings"])
settings = get_settings()

BRAINVISION_EXTENSIONS = {".vhdr", ".eeg", ".vmrk"}
STANDARD_SINGLE_EXTENSIONS = {".edf": "EDF", ".bdf": "BDF"}
REJECTED_EXTENSIONS = {
    ".set": "暂不接受 EEGLAB .set，请转换为 EDF/BDF/BrainVision 后上传。",
    ".fdt": "暂不接受 EEGLAB .fdt，请转换为 EDF/BDF/BrainVision 后上传。",
    ".fif": "FIF 只能由系统导入流程生成，不接受用户直接上传。",
    ".nii": "暂不接受 NIfTI/MRI 数据，本阶段只导入 EEG 原始数据。",
    ".dcm": "暂不接受 DICOM 数据，本阶段只导入 EEG 原始数据。",
}
ADVANCED_EXTENSIONS = {
    ".cnt": "CNT 需要进入高级导入流程确认 reader、通道和 trigger；当前同步上传入口暂不接收。",
    ".mff": "MFF/Net Station 需要上传完整目录包并进入高级导入流程；当前同步上传入口暂不接收。",
    ".gdf": "GDF 需要进入高级导入流程；当前同步上传入口暂不接收。",
    ".mat": "MAT 需要平台矩阵模板和元数据；当前同步上传入口暂不接收。",
    ".h5": "HDF5 需要平台 schema；当前同步上传入口暂不接收。",
    ".hdf5": "HDF5 需要平台 schema；当前同步上传入口暂不接收。",
    ".csv": "CSV 可作为 events/behavior/phenotype 候选文件，连续 EEG 需要模板化高级导入；当前入口暂不接收。",
    ".tsv": "TSV 可作为 events/behavior/phenotype 候选文件，连续 EEG 需要模板化高级导入；当前入口暂不接收。",
    ".txt": "TXT 可作为说明或行为文件，连续 EEG 需要模板化高级导入；当前入口暂不接收。",
    ".xlsx": "XLSX 可作为行为/表型候选文件；当前入口暂不接收。",
    ".xls": "XLS 可作为行为/表型候选文件；当前入口暂不接收。",
    ".json": "JSON 可作为元数据候选文件；当前入口暂不接收。",
    ".md": "Markdown 可作为任务说明候选文件；当前入口暂不接收。",
}
WORKING_DATASET_VERSION_LABEL = "working"
DATASET_ORIGINAL_UPLOADS_PREFIX = "sourcedata/original_uploads"
DATASET_RAW_BIDS_PREFIX = "raw_bids"
DATASET_CANONICAL_FIF_PREFIX = "derivatives/elys-canonical-fif"
RAW_BIDS_SIDECAR_ROLES = {
    "eeg": "raw_bids_eeg_json",
    "channels": "raw_bids_channels",
    "events": "raw_bids_events",
}


class UploadItem(NamedTuple):
    upload: UploadFile
    relative_path: Path
    extension: str


def normalize_bids_label(value: str, prefix: str | None = None, required: bool = False) -> str | None:
    cleaned = (value or "").strip()
    if not cleaned:
        if required:
            raise HTTPException(status_code=422, detail="必填字段不能为空")
        return None

    if prefix:
        prefix_name = prefix.rstrip("-")
        lower_cleaned = cleaned.lower()
        if lower_cleaned.startswith(prefix.lower()):
            cleaned = cleaned[len(prefix) :]
        elif lower_cleaned.startswith(prefix_name.lower()):
            cleaned = cleaned[len(prefix_name) :]
            if cleaned.startswith("-"):
                cleaned = cleaned[1:]

    allowed = "".join(ch for ch in cleaned if ch.isascii() and ch.isalnum())
    if not allowed:
        raise HTTPException(status_code=422, detail=f"{prefix or 'label'} 只能包含字母和数字")
    return f"{prefix}{allowed}" if prefix else allowed


def require_system_permission(user: User, permission_code: str, message: str) -> None:
    if user.has_role("admin") or user.has_permission(permission_code):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)


def recording_to_response(recording: Recording) -> RecordingResponse:
    return RecordingResponse(
        id=str(recording.id),
        study_id=recording.study_id,
        dataset_asset_id=str(recording.dataset_asset_id) if recording.dataset_asset_id else None,
        subject_id=str(recording.subject_id),
        bids_subject_id=recording.subject.bids_subject_id if recording.subject else "",
        session=recording.session,
        task=recording.task,
        run=recording.run,
        source_format=recording.source_format,
        source_path=recording.source_path,
        fif_path=recording.fif_path,
        current_version_id=str(recording.current_version_id) if recording.current_version_id else None,
        current_version_seq=recording.current_version.version_seq if recording.current_version else None,
        file_size=recording.file_size,
        checksum=recording.checksum,
        n_channels=recording.n_channels,
        sfreq=recording.sfreq,
        duration_seconds=recording.duration_seconds,
        n_events=recording.n_events,
        qa_status=recording.qa_status,
        qa_report=recording.qa_report,
        imported_by=str(recording.imported_by) if recording.imported_by else None,
        imported_at=recording.imported_at,
    )


def recording_version_to_response(version: RecordingVersion, *, study_id: str) -> RecordingVersionResponse:
    return RecordingVersionResponse(
        id=str(version.id),
        recording_id=str(version.recording_id),
        study_id=study_id,
        version_seq=version.version_seq,
        source_dir=version.source_dir,
        source_main_file=version.source_main_file,
        source_files=version.source_files or [],
        source_format=version.source_format,
        fif_dir=version.fif_dir,
        fif_path=version.fif_path,
        sidecar_paths=version.sidecar_paths or {},
        file_size=version.file_size,
        checksum=version.checksum,
        status=version.status,
        qa_status=version.qa_status,
        note=version.note,
        uploaded_by=str(version.uploaded_by) if version.uploaded_by else None,
        uploaded_at=version.uploaded_at,
    )


def dataset_asset_to_response(asset: DatasetAsset, stats: dict | None = None) -> DatasetAssetResponse:
    """把 ORM 转响应模型。UI Phase (docs_v2/6-05) 起接收可选 stats 字典，
    含 subject_count / task_codes / total_duration_seconds / last_imported_at。
    未传时用空值（保持向后兼容）。"""
    s = stats or {
        "subject_count": 0,
        "task_codes": [],
        "total_duration_seconds": 0.0,
        "last_imported_at": None,
    }
    return DatasetAssetResponse(
        id=str(asset.id),
        name=asset.name,
        code=asset.code,
        description=asset.description,
        owner_id=str(asset.owner_id) if asset.owner_id else None,
        status=asset.status,
        visibility=asset.visibility,
        metadata_json=asset.metadata_json or {},
        # Phase 3 (docs_v2/3-25): 生命周期相关字段
        primary_study_id=asset.primary_study_id,
        concept_doi=asset.concept_doi,
        current_version_id=str(asset.current_version_id) if asset.current_version_id else None,
        # UI Phase (docs_v2/6-05): 数据概要聚合字段
        subject_count=s["subject_count"],
        task_codes=s["task_codes"],
        total_duration_seconds=s["total_duration_seconds"],
        last_imported_at=s["last_imported_at"],
        created_by=str(asset.created_by) if asset.created_by else None,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )


def dataset_version_to_response(version: DatasetVersion) -> DatasetVersionResponse:
    return DatasetVersionResponse(
        id=str(version.id),
        dataset_asset_id=str(version.dataset_asset_id),
        version_label=version.version_label,
        status=version.status,
        # Phase 3 (docs_v2/3-25): 生命周期相关字段
        state=version.state,
        qa_status=version.qa_status,
        content_hash=version.content_hash,
        version_doi=version.version_doi,
        published_at=version.published_at,
        published_by=str(version.published_by) if version.published_by else None,
        withdraw_requested_at=version.withdraw_requested_at,
        withdraw_requested_by=(
            str(version.withdraw_requested_by) if version.withdraw_requested_by else None
        ),
        withdraw_reason=version.withdraw_reason,
        withdrawn_at=version.withdrawn_at,
        withdrawn_by=str(version.withdrawn_by) if version.withdrawn_by else None,
        withdrawal_admin_notes=version.withdrawal_admin_notes,
        storage_uri=version.storage_uri,
        metadata_json=version.metadata_json or {},
        created_by=str(version.created_by) if version.created_by else None,
        created_at=version.created_at,
    )


def study_to_response(study: Study) -> StudyResponse:
    return StudyResponse(**study.to_dict())


def study_dataset_mount_to_response(
    mount: StudyDatasetMount,
    asset_stats: dict | None = None,
) -> StudyDatasetMountResponse:
    """UI Phase (docs_v2/6-05): asset_stats 可选传入，用于把数据概要带到嵌套 asset 上。"""
    return StudyDatasetMountResponse(
        id=str(mount.id),
        study_id=mount.study_id,
        dataset_asset_id=str(mount.dataset_asset_id),
        # Phase 3 (docs_v2/3-25) C: 锁定的版本 ID + 嵌套版本对象（前端用来判断 mount 是否可升级）
        dataset_version_id=str(mount.dataset_version_id) if mount.dataset_version_id else None,
        mount_name=mount.mount_name,
        selection_json=mount.selection_json or {},
        is_active=mount.is_active,
        mounted_by=str(mount.mounted_by) if mount.mounted_by else None,
        mounted_at=mount.mounted_at,
        dataset_asset=dataset_asset_to_response(
            mount.dataset_asset,
            stats=asset_stats,
        ) if mount.dataset_asset else None,
        dataset_version=dataset_version_to_response(mount.dataset_version) if mount.dataset_version else None,
    )


def dataset_file_to_response(file_record: DatasetFile) -> DatasetFileResponse:
    return DatasetFileResponse(
        id=str(file_record.id),
        study_id=file_record.study_id,
        dataset_id=str(file_record.recording_id),
        dataset_upload_id=str(file_record.recording_version_id),
        file_role=file_record.file_role,
        storage_uri=file_record.storage_uri,
        relative_path=file_record.relative_path,
        logical_path=file_record.logical_path,
        file_size=file_record.file_size,
        sha256=file_record.sha256,
        mime_type=file_record.mime_type,
        metadata_json=file_record.metadata_json or {},
        created_by=str(file_record.created_by) if file_record.created_by else None,
        created_at=file_record.created_at,
    )


def dataset_file_metadata_to_response(file_record: DatasetFile, *, study: Study | None = None) -> DatasetFileMetadataResponse:
    return DatasetFileMetadataResponse(**dataset_file_metadata(file_record, study=study))


def dataset_file_preview_to_response(file_record: DatasetFile, *, study: Study | None = None) -> DatasetFilePreviewResponse:
    return DatasetFilePreviewResponse(**dataset_file_preview(file_record, study=study))


def get_study_for_dataset_file(db: Session, file_record: DatasetFile) -> Study:
    study = getattr(file_record, "study", None)
    if study is not None:
        return study
    study = db.query(Study).filter(Study.id == file_record.study_id).first()
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset file 所属项目不存在")
    return study


def get_dataset_file_or_404(db: Session, file_id: uuid.UUID) -> DatasetFile:
    file_record = (
        db.query(DatasetFile)
        .options(
            joinedload(DatasetFile.study),
            joinedload(DatasetFile.recording),
            joinedload(DatasetFile.dataset_version),
        )
        .filter(DatasetFile.id == file_id)
        .first()
    )
    if file_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset file 不存在")
    return file_record


def ensure_dataset_file_readable(db: Session, file_record: DatasetFile, current_user: User) -> Study:
    study = get_study_for_dataset_file(db, file_record)
    recording = getattr(file_record, "recording", None)
    dataset_asset_id = getattr(recording, "dataset_asset_id", None)
    if dataset_asset_id:
        asset = get_dataset_asset_for_user(db, asset_id=dataset_asset_id, user=current_user)
        if asset is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset file 不存在或无权访问")
        return study
    require_study_read(study, db, current_user)
    return study


def handle_file_access_error(exc: FileAccessError) -> None:
    raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc


def create_and_dispatch_file_task(
    db: Session,
    *,
    task_type: str,
    study_id: str | None,
    resource_kind: str,
    resource_id: Any | None,
    payload_json: dict[str, Any],
    current_user: User,
) -> AsyncTaskResponse:
    from app.services.async_tasks import async_task_to_response, create_async_task
    from app.tasks.file_tasks import run_file_task

    task = create_async_task(
        db,
        task_type=task_type,
        queue_name=settings.CELERY_WORKFLOW_QUEUE,
        study_id=study_id,
        resource_kind=resource_kind,
        resource_id=resource_id,
        payload_json=payload_json,
        created_by=current_user.id,
    )
    db.flush()
    try:
        celery_result = run_file_task.apply_async(
            args=[str(task.id)],
            queue=settings.CELERY_WORKFLOW_QUEUE,
            task_id=str(task.id),
        )
        if task.celery_task_id != celery_result.id:
            task.celery_task_id = celery_result.id
        record_task_event(
            db,
            task,
            "dispatched",
            message=f"{task_type} task dispatched to Celery.",
            payload={"celery_task_id": celery_result.id, "queue": settings.CELERY_WORKFLOW_QUEUE},
        )
    except Exception as exc:
        task.error_json = {
            "errors": [
                {
                    "code": "FILE_TASK_DISPATCH_FAILED",
                    "message": str(exc),
                    "severity": "error",
                }
            ]
        }
        record_task_event(
            db,
            task,
            "dispatch_failed",
            status="failed",
            progress=100,
            message=str(exc),
            payload={"queue": settings.CELERY_WORKFLOW_QUEUE},
        )
    db.commit()
    db.refresh(task)
    return async_task_to_response(task)


def validate_dataset_filter_shape(dataset_filter: dict[str, Any]) -> None:
    for key in ("subjects", "sessions", "tasks", "runs", "qa_status", "dataset_asset_ids"):
        if key in dataset_filter and dataset_filter[key] != "all" and not isinstance(dataset_filter[key], list):
            raise HTTPException(status_code=422, detail=f"selection_json.dataset_filter.{key} 必须是 all 或数组")
    if "dataset_asset_id" in dataset_filter and not isinstance(dataset_filter["dataset_asset_id"], str):
        raise HTTPException(status_code=422, detail="selection_json.dataset_filter.dataset_asset_id 必须是字符串")
    if "mount_name" in dataset_filter and not isinstance(dataset_filter["mount_name"], str):
        raise HTTPException(status_code=422, detail="selection_json.dataset_filter.mount_name 必须是字符串")
    if "mount_id" in dataset_filter:
        try:
            uuid.UUID(str(dataset_filter["mount_id"]))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="selection_json.dataset_filter.mount_id 必须是 UUID") from exc
    if "require_fif" in dataset_filter and not isinstance(dataset_filter["require_fif"], bool):
        raise HTTPException(status_code=422, detail="selection_json.dataset_filter.require_fif 必须是布尔值")


def validate_mount_selection_json(selection_json: dict[str, Any]) -> None:
    if not isinstance(selection_json, dict):
        raise HTTPException(status_code=422, detail="selection_json 必须是对象")
    dataset_filter = selection_json.get("dataset_filter", selection_json)
    if not isinstance(dataset_filter, dict):
        raise HTTPException(status_code=422, detail="selection_json.dataset_filter 必须是对象")
    validate_dataset_filter_shape(dataset_filter)


def ensure_dataset_asset_uploadable(asset: DatasetAsset, current_user: User) -> None:
    if asset.status in {"deleted", "quarantined", "archived"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Dataset Asset 当前状态不允许上传: {asset.status}",
        )
    if not can_write_dataset_asset(current_user, asset):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权向该 Dataset Asset 上传数据")


def active_study_dataset_mounts(db: Session, *, study: Study) -> list[StudyDatasetMount]:
    return [mount for mount in list_study_dataset_mounts(db, study=study) if mount.is_active]


def active_study_dataset_asset_ids(db: Session, *, study: Study) -> list[uuid.UUID]:
    return [mount.dataset_asset_id for mount in active_study_dataset_mounts(db, study=study)]


def ensure_dataset_asset_active_mounted(
    db: Session,
    *,
    study: Study,
    dataset_asset_id: uuid.UUID,
) -> None:
    mounted_asset_ids = set(active_study_dataset_asset_ids(db, study=study))
    if dataset_asset_id not in mounted_asset_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset Asset 未挂载到当前 Study 或未启用")


def ensure_mount_matches_dataset_asset(
    *,
    mount: StudyDatasetMount,
    dataset_asset_id: uuid.UUID | None,
) -> None:
    if dataset_asset_id is not None and mount.dataset_asset_id != dataset_asset_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="dataset_asset_id 与 Dataset 挂载指向不一致")


def resolve_dataset_asset_filter(
    db: Session,
    *,
    study: Study,
    dataset_asset_id: uuid.UUID | None = None,
    mount_id: uuid.UUID | None = None,
    mount_name: str | None = None,
) -> uuid.UUID | None:
    if mount_id:
        mount = get_study_dataset_mount(db, study=study, mount_id=mount_id)
        if mount is None or not mount.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset 挂载不存在或未启用")
        ensure_mount_matches_dataset_asset(mount=mount, dataset_asset_id=dataset_asset_id)
        return mount.dataset_asset_id
    if mount_name:
        mount = get_study_dataset_mount_by_name(db, study=study, mount_name=mount_name)
        if mount is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset 挂载不存在或未启用")
        ensure_mount_matches_dataset_asset(mount=mount, dataset_asset_id=dataset_asset_id)
        return mount.dataset_asset_id
    if dataset_asset_id:
        ensure_dataset_asset_active_mounted(db, study=study, dataset_asset_id=dataset_asset_id)
    return dataset_asset_id


def resolve_upload_dataset_asset(
    db: Session,
    *,
    study: Study,
    current_user: User,
    dataset_asset_id: uuid.UUID | None,
    mount_name: str | None,
) -> tuple[DatasetAsset, StudyDatasetMount | None]:
    if mount_name:
        mount = get_study_dataset_mount_by_name(db, study=study, mount_name=mount_name)
        if mount is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset 挂载不存在或未启用")
        asset = mount.dataset_asset or db.query(DatasetAsset).filter(DatasetAsset.id == mount.dataset_asset_id).first()
        if asset is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset Asset 不存在")
        if dataset_asset_id is not None and dataset_asset_id != asset.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="dataset_asset_id 与 mount_name 指向不一致")
        ensure_dataset_asset_uploadable(asset, current_user)
        return asset, mount

    if dataset_asset_id is not None:
        asset = get_dataset_asset_for_user(db, asset_id=dataset_asset_id, user=current_user)
        if asset is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset Asset 不存在或无权访问")
        mount = get_active_study_dataset_mount_for_asset(db, study=study, dataset_asset=asset)
        if mount is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Dataset Asset 尚未挂载到当前 Study")
        ensure_dataset_asset_uploadable(asset, current_user)
        return asset, mount

    try:
        asset = get_or_create_working_dataset_asset(db, study=study, user=current_user)
    except DatasetAssetConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    ensure_dataset_asset_uploadable(asset, current_user)
    mount = get_active_study_dataset_mount_for_asset(db, study=study, dataset_asset=asset)
    return asset, mount


def dataset_qa_to_response(dataset: Recording) -> DatasetQaResponse:
    raw_report = dataset.qa_report
    has_report = bool(raw_report)
    qa_report = None

    if isinstance(raw_report, dict) and raw_report:
        try:
            qa_report = DatasetQaReport.model_validate(raw_report)
        except ValidationError:
            qa_report = DatasetQaReport(
                summary=DatasetQaSummary(
                    mock_qc_status="unparsed",
                    level="warning",
                    score=None,
                    warnings=["Stored qa_report does not match the current v1 schema."],
                )
            )

    return DatasetQaResponse(
        dataset_id=str(dataset.id),
        study_id=dataset.study_id,
        qa_status=dataset.qa_status,
        qa_report=qa_report,
        has_report=has_report,
        current_upload_id=str(dataset.current_version_id) if dataset.current_version_id else None,
        imported_at=dataset.imported_at,
    )


def validate_mock_qa_report_payload(report: dict[str, Any]) -> DatasetQaReport:
    try:
        qa_report = DatasetQaReport.model_validate(report)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"模拟质控报告结构无效: {exc}",
        ) from exc

    signal_placeholder = next(
        (stage for stage in qa_report.stages if stage.key == "signal_placeholder"),
        None,
    )
    if (
        qa_report.mode != DATASET_QA_MODE_MOCK
        or qa_report.summary.score is not None
        or signal_placeholder is None
        or signal_placeholder.status != "not_computed"
    ):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="模拟质控报告未满足 mock 模式约定",
        )
    return qa_report


def apply_mock_qa_status(dataset: Recording, qa_report: DatasetQaReport) -> None:
    if qa_report.summary.blocking_issues:
        dataset.qa_status = "failed"


def actor_id_text(user: User) -> str | None:
    actor_id = getattr(user, "id", None)
    return str(actor_id) if actor_id else None


def study_snapshot(study: Study) -> dict[str, Any]:
    to_dict = getattr(study, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return {"id": getattr(study, "id", None)}


def add_qa_report_history(
    qa_report: DatasetQaReport,
    *,
    action: str,
    actor: User,
    occurred_at: datetime,
    status_value: str | None,
) -> None:
    qa_report.history.append(
        {
            "action": action,
            "actor_id": actor_id_text(actor),
            "at": f"{occurred_at.isoformat()}Z",
            "status": status_value,
        }
    )


def add_dataset_qa_audit_event(
    db: Session,
    *,
    study: Study,
    dataset: Recording,
    action: str,
    actor: User,
    occurred_at: datetime,
    old_qa_status: str | None,
    new_qa_status: str | None,
    qa_report: DatasetQaReport,
    conclusion: str | None = None,
) -> None:
    db.add(
        AuditEvent(
            study_id=study.id,
            event_scope="study",
            action=action,
            actor_id=getattr(actor, "id", None),
            resource_kind="dataset",
            resource_id=str(dataset.id),
            resource_label=getattr(dataset, "name", None) or str(dataset.id),
            occurred_at=occurred_at,
            snapshot=study_snapshot(study),
            metadata_json={
                "dataset_id": str(dataset.id),
                "current_upload_id": str(dataset.current_version_id) if dataset.current_version_id else None,
                "old_qa_status": old_qa_status,
                "new_qa_status": new_qa_status,
                "conclusion": conclusion,
                "has_blocking_issues": bool(qa_report.summary.blocking_issues),
            },
        )
    )


def record_dataset_qa_action(
    db: Session,
    *,
    study: Study,
    dataset: Recording,
    qa_report: DatasetQaReport,
    action: str,
    actor: User,
    occurred_at: datetime,
    old_qa_status: str | None,
    conclusion: str | None = None,
) -> None:
    new_qa_status = dataset.qa_status
    add_qa_report_history(
        qa_report,
        action=action,
        actor=actor,
        occurred_at=occurred_at,
        status_value=new_qa_status,
    )
    dataset.qa_report = qa_report.model_dump(mode="json")
    add_dataset_qa_audit_event(
        db,
        study=study,
        dataset=dataset,
        action=action,
        actor=actor,
        occurred_at=occurred_at,
        old_qa_status=old_qa_status,
        new_qa_status=new_qa_status,
        qa_report=qa_report,
        conclusion=conclusion,
    )


def require_existing_qa_report(dataset: Recording) -> DatasetQaReport:
    raw_report = dataset.qa_report
    if not isinstance(raw_report, dict) or not raw_report:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先生成模拟质控报告")
    try:
        return DatasetQaReport.model_validate(raw_report)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"已有质控报告结构无效: {exc}") from exc


def apply_dataset_qa_review(
    dataset: Recording,
    qa_report: DatasetQaReport,
    review: DatasetQaReviewRequest,
    current_user: User,
) -> DatasetQaReport:
    if review.conclusion == "accept":
        if qa_report.summary.blocking_issues:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="存在阻塞问题，不能人工确认通过")
        dataset.qa_status = "checked"
    elif review.conclusion == "reject":
        dataset.qa_status = "rejected"
    elif review.conclusion == "hold" and dataset.qa_status not in {"failed", "rejected"}:
        dataset.qa_status = "converted"

    qa_report.human_review = DatasetQaHumanReview(
        conclusion=review.conclusion,
        notes=review.notes,
        reviewed_by=str(current_user.id) if getattr(current_user, "id", None) else None,
        reviewed_at=datetime.utcnow(),
    )
    dataset.qa_report = qa_report.model_dump(mode="json")
    return qa_report


def get_or_create_subject(db: Session, study: Study, bids_subject_id: str) -> Subject:
    subject = (
        db.query(Subject)
        .filter(Subject.study_id == study.id, Subject.bids_subject_id == bids_subject_id)
        .first()
    )
    if subject:
        return subject

    subject = Subject(study_id=study.id, bids_subject_id=bids_subject_id, extra={})
    db.add(subject)
    db.flush()
    return subject


def safe_upload_relative_path(filename: str | None) -> Path:
    raw = (filename or "upload").replace("\\", "/")
    parts: list[str] = []
    for part in PurePosixPath(raw).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            raise HTTPException(status_code=422, detail="上传文件名不能包含上级目录 ..")
        cleaned = "".join(ch for ch in part.strip().replace("\x00", "") if ch not in '<>:"|?*')
        if cleaned:
            parts.append(cleaned)
    if not parts:
        raise HTTPException(status_code=422, detail="上传文件名无效")
    return Path(*parts)


def classify_uploads(files: list[UploadFile]) -> tuple[str, dict[str, UploadItem]]:
    if not files:
        raise HTTPException(status_code=422, detail="请选择要上传的数据文件")

    items_by_extension: dict[str, UploadItem] = {}
    stems: set[str] = set()
    parent_paths: set[str] = set()

    for upload in files:
        relative_path = safe_upload_relative_path(upload.filename)
        extension = relative_path.suffix.lower()
        filename = relative_path.name

        if filename.lower().endswith(".nii.gz"):
            raise HTTPException(status_code=422, detail="暂不接受 NIfTI/MRI 数据，本阶段只导入 EEG 原始数据。")
        if extension in REJECTED_EXTENSIONS:
            raise HTTPException(status_code=422, detail=REJECTED_EXTENSIONS[extension])
        if extension in ADVANCED_EXTENSIONS:
            raise HTTPException(status_code=422, detail=ADVANCED_EXTENSIONS[extension])
        if extension not in BRAINVISION_EXTENSIONS and extension not in STANDARD_SINGLE_EXTENSIONS:
            raise HTTPException(status_code=422, detail=f"不支持的文件类型: {filename}")
        if extension in items_by_extension:
            raise HTTPException(status_code=422, detail=f"同一次导入不能包含多个 {extension} 文件")

        items_by_extension[extension] = UploadItem(upload, relative_path, extension)
        stems.add(relative_path.stem.lower())
        parent_paths.add(relative_path.parent.as_posix())

    extensions = set(items_by_extension)
    if extensions == BRAINVISION_EXTENSIONS:
        if len(stems) != 1:
            raise HTTPException(status_code=422, detail="BrainVision 三件套必须同名，例如 sub01.vhdr/sub01.eeg/sub01.vmrk")
        if len(parent_paths) != 1:
            raise HTTPException(status_code=422, detail="BrainVision 三件套必须位于同一文件夹")
        return "brainvision", items_by_extension

    if len(extensions) == 1:
        extension = next(iter(extensions))
        if extension in STANDARD_SINGLE_EXTENSIONS:
            return STANDARD_SINGLE_EXTENSIONS[extension].lower(), items_by_extension
        raise HTTPException(status_code=422, detail="BrainVision 数据必须同时包含同名 .vhdr、.eeg、.vmrk")

    raise HTTPException(status_code=422, detail="一次导入只能包含一个 BrainVision 三件套，或一个 EDF/BDF 文件")


def build_fif_stem(
    bids_subject_id: str,
    session: str | None,
    task: str | None,
    run: str | None,
) -> str:
    parts = [bids_subject_id]
    if session:
        parts.append(session)
    if task:
        parts.append(task)
    if run:
        parts.append(run)
    return "_".join(parts)


def build_fif_base_path(
    study: Study,
    bids_subject_id: str,
    session: str | None,
    task: str | None,
    run: str | None,
    upload_seq: int,
) -> Path:
    root = Path(study.data_root) / "fifdata" / bids_subject_id
    if session:
        root = root / session
    root = root / (task or "task-none") / (run or "run-none") / f"upload-{upload_seq:03d}"
    return root / build_fif_stem(bids_subject_id, session, task, run)


def canonical_fif_logical_dir(
    bids_subject_id: str,
    session: str | None,
    task: str | None,
    run: str | None,
    upload_seq: int,
) -> str:
    parts = [DATASET_CANONICAL_FIF_PREFIX, bids_subject_id]
    if session:
        parts.append(session)
    parts.extend([task or "task-none", run or "run-none", f"upload-{upload_seq:03d}"])
    return normalize_storage_logical_path("/".join(parts))


def build_canonical_fif_base_path(
    dataset_version: DatasetVersion,
    bids_subject_id: str,
    session: str | None,
    task: str | None,
    run: str | None,
    upload_seq: int,
) -> Path:
    root = dataset_version_root(dataset_version.dataset_asset_id, dataset_version.version_label)
    logical_dir = canonical_fif_logical_dir(bids_subject_id, session, task, run, upload_seq)
    return root / logical_dir / build_fif_stem(bids_subject_id, session, task, run)


def build_canonical_fif_base_path_for_asset(
    dataset_asset: DatasetAsset,
    bids_subject_id: str,
    session: str | None,
    task: str | None,
    run: str | None,
    upload_seq: int,
    version_label: str = WORKING_DATASET_VERSION_LABEL,
) -> Path:
    root = dataset_version_root(dataset_asset.id, version_label)
    logical_dir = canonical_fif_logical_dir(bids_subject_id, session, task, run, upload_seq)
    return root / logical_dir / build_fif_stem(bids_subject_id, session, task, run)


def make_fif_version_dir(
    study: Study,
    bids_subject_id: str,
    session: str | None,
    task: str,
    run: str | None,
    upload_seq: int,
) -> Path:
    return build_fif_base_path(study, bids_subject_id, session, task, run, upload_seq).parent


def make_canonical_fif_version_dir(
    dataset_version: DatasetVersion,
    bids_subject_id: str,
    session: str | None,
    task: str,
    run: str | None,
    upload_seq: int,
) -> Path:
    return build_canonical_fif_base_path(dataset_version, bids_subject_id, session, task, run, upload_seq).parent


def make_canonical_fif_version_dir_for_asset(
    dataset_asset: DatasetAsset,
    bids_subject_id: str,
    session: str | None,
    task: str,
    run: str | None,
    upload_seq: int,
) -> Path:
    return build_canonical_fif_base_path_for_asset(dataset_asset, bids_subject_id, session, task, run, upload_seq).parent


def make_import_job_id() -> str:
    return f"import-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"


def dataset_version_storage_uri(dataset_asset_id: uuid.UUID | str, version_label: str = WORKING_DATASET_VERSION_LABEL) -> str:
    return f"elys://datasets/{dataset_asset_id}/versions/{version_label}"


def dataset_version_root(dataset_asset_id: uuid.UUID | str, version_label: str = WORKING_DATASET_VERSION_LABEL) -> Path:
    return Path(settings.DATASETS_STORAGE_ROOT) / str(dataset_asset_id) / "versions" / version_label


def dataset_upload_logical_dir(upload_seq: int) -> str:
    return normalize_storage_logical_path(f"{DATASET_ORIGINAL_UPLOADS_PREFIX}/upload-{upload_seq:03d}")


def dataset_storage_uri(dataset_asset_id: uuid.UUID | str, logical_path: str, version_label: str = WORKING_DATASET_VERSION_LABEL) -> str:
    normalized = normalize_storage_logical_path(logical_path)
    base = dataset_version_storage_uri(dataset_asset_id, version_label)
    return f"{base}/{normalized}" if normalized else base


def get_or_create_working_dataset_version(
    db: Session,
    *,
    dataset_asset: DatasetAsset,
    current_user: User,
) -> DatasetVersion:
    version = (
        db.query(DatasetVersion)
        .filter(
            DatasetVersion.dataset_asset_id == dataset_asset.id,
            DatasetVersion.version_label == WORKING_DATASET_VERSION_LABEL,
        )
        .first()
    )
    if version is not None:
        if not version.storage_uri:
            version.storage_uri = dataset_version_storage_uri(dataset_asset.id)
            db.flush()
        return version

    version = DatasetVersion(
        dataset_asset_id=dataset_asset.id,
        version_label=WORKING_DATASET_VERSION_LABEL,
        status="working",
        storage_uri=dataset_version_storage_uri(dataset_asset.id),
        metadata_json={"auto_created": True, "source": "upload"},
        created_by=current_user.id,
    )
    db.add(version)
    db.flush()
    return version


def raw_bids_eeg_dir(bids_subject_id: str, session: str | None) -> str:
    parts = [DATASET_RAW_BIDS_PREFIX, bids_subject_id]
    if session:
        parts.append(session)
    parts.append("eeg")
    return normalize_storage_logical_path("/".join(parts))


def raw_bids_file_stem(
    bids_subject_id: str,
    session: str | None,
    task: str | None,
    run: str | None,
) -> str:
    return build_fif_stem(bids_subject_id, session, task, run)


def raw_bids_data_logical_path(
    source_path: Path,
    *,
    source_format: str,
    bids_subject_id: str,
    session: str | None,
    task: str,
    run: str | None,
) -> str:
    suffix = source_path.suffix.lower()
    if source_format in {"EDF", "BDF"}:
        suffix = ".edf" if source_format == "EDF" else ".bdf"
    directory = raw_bids_eeg_dir(bids_subject_id, session)
    stem = raw_bids_file_stem(bids_subject_id, session, task, run)
    return normalize_storage_logical_path(f"{directory}/{stem}_eeg{suffix}")


def raw_bids_sidecar_logical_path(
    sidecar_key: str,
    *,
    bids_subject_id: str,
    session: str | None,
    task: str,
    run: str | None,
) -> str | None:
    suffix_by_key = {
        "eeg": "_eeg.json",
        "channels": "_channels.tsv",
        "events": "_events.tsv",
    }
    suffix = suffix_by_key.get(sidecar_key)
    if suffix is None:
        return None
    directory = raw_bids_eeg_dir(bids_subject_id, session)
    stem = raw_bids_file_stem(bids_subject_id, session, task, run)
    return normalize_storage_logical_path(f"{directory}/{stem}{suffix}")


def brainvision_component(path: Path) -> str | None:
    suffix = path.suffix.lower()
    return {
        ".vhdr": "header",
        ".eeg": "data",
        ".vmrk": "marker",
    }.get(suffix)


def raw_bids_data_metadata(
    *,
    source_format: str,
    source_path: Path,
    storage_uri: str,
    upload_seq: int,
    is_primary: bool,
) -> dict[str, Any]:
    metadata = {
        "view_kind": "raw_bids_logical",
        "physical_storage_uri": storage_uri,
        "source_format": source_format,
        "is_primary": is_primary,
        "extension": source_path.suffix.lower(),
        "upload_seq": upload_seq,
    }
    if source_format == "BRAINVISION":
        component = brainvision_component(source_path)
        metadata["brainvision_component"] = component
        metadata["requires_reference_rewrite"] = component in {"header", "marker"}
        metadata["rewrite_status"] = "not_rewritten_logical_view"
    return metadata


def make_import_job_dir(
    study: Study,
    bids_subject_id: str,
    session: str | None,
    task: str,
    run: str | None,
    upload_seq: int,
    dataset_asset: DatasetAsset | None = None,
) -> Path:
    if dataset_asset is not None:
        return dataset_version_root(dataset_asset.id) / dataset_upload_logical_dir(upload_seq)

    root = Path(study.data_root) / "source_uploads" / bids_subject_id
    if session:
        root = root / session
    root = root / task / (run or "run-none")
    return root / f"upload-{upload_seq:03d}"


def get_next_upload_seq(
    db: Session,
    *,
    dataset: Recording | None,
    study: Study,
    dataset_asset: DatasetAsset | None,
    bids_subject_id: str,
    session: str | None,
    task: str,
    run: str | None,
) -> int:
    if dataset:
        max_seq = (
            db.query(func.max(RecordingVersion.version_seq))
            .filter(RecordingVersion.recording_id == dataset.id)
            .scalar()
        )
        seq = (max_seq + 1) if max_seq else (2 if dataset.source_path else 1)
    else:
        seq = 1

    while (
        make_import_job_dir(study, bids_subject_id, session, task, run, seq, dataset_asset=dataset_asset).exists()
        or make_fif_version_dir(study, bids_subject_id, session, task, run, seq).exists()
        or (
            dataset_asset is not None
            and make_canonical_fif_version_dir_for_asset(
                dataset_asset,
                bids_subject_id,
                session,
                task,
                run,
                seq,
            ).exists()
        )
    ):
        seq += 1
    return seq


def is_storage_uri(value: str) -> bool:
    return "://" in str(value)


def normalize_storage_logical_path(path_value: str) -> str:
    text = str(path_value or "").replace("\\", "/").strip("/")
    if not text:
        return ""
    return PurePosixPath(text).as_posix()


def dataset_storage_reference_for_path(path: Path) -> tuple[str, str] | None:
    try:
        relative_to_datasets_root = path.resolve().relative_to(Path(settings.DATASETS_STORAGE_ROOT).resolve()).as_posix()
    except ValueError:
        return None

    parts = PurePosixPath(relative_to_datasets_root).parts
    if len(parts) < 3 or parts[1] != "versions":
        return None

    dataset_asset_id = parts[0]
    version_label = parts[2]
    logical_path = normalize_storage_logical_path("/".join(parts[3:]))
    return dataset_storage_uri(dataset_asset_id, logical_path, version_label), logical_path


def dataset_logical_path_from_storage_uri(storage_uri: str | None) -> str | None:
    text = str(storage_uri or "")
    if not text.startswith("elys://datasets/"):
        return None
    without_scheme = text.removeprefix("elys://datasets/")
    parts = PurePosixPath(without_scheme).parts
    if len(parts) < 3 or parts[1] != "versions":
        return None
    return normalize_storage_logical_path("/".join(parts[3:]))


def dataset_logical_path_for_version(dataset_version: DatasetVersion | None, path: Path) -> str | None:
    if dataset_version is None:
        return None
    root = dataset_version_root(dataset_version.dataset_asset_id, dataset_version.version_label)
    try:
        return normalize_storage_logical_path(path.resolve().relative_to(root.resolve()).as_posix())
    except ValueError:
        return None


def relative_to_study(study: Study, path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path(study.data_root).resolve()).as_posix()
    except ValueError:
        dataset_reference = dataset_storage_reference_for_path(resolved)
        if dataset_reference is not None:
            storage_uri, _logical_path = dataset_reference
            return storage_uri
        return resolved.as_posix()


def write_manifest(job_dir: Path, payload: dict[str, Any]) -> None:
    manifest_path = job_dir / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


async def write_upload_file(upload: UploadFile, destination: Path) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    try:
        with destination.open("wb") as handle:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                handle.write(chunk)
    finally:
        await upload.close()

    if total == 0:
        raise HTTPException(status_code=422, detail=f"{upload.filename} 是空文件")
    return total


async def archive_uploads(
    items_by_extension: dict[str, UploadItem],
    job_dir: Path,
    *,
    files_subdir: str | None = "files",
) -> dict[str, Path]:
    files_dir = job_dir / files_subdir if files_subdir else job_dir
    archived: dict[str, Path] = {}
    targets: set[Path] = set()
    for extension, item in items_by_extension.items():
        target = files_dir / item.relative_path
        resolved = target.resolve()
        if resolved in targets:
            raise HTTPException(status_code=422, detail=f"上传文件路径重复: {item.relative_path.as_posix()}")
        targets.add(resolved)
        await write_upload_file(item.upload, target)
        archived[extension] = target
    return archived


def compute_files_checksum(paths: list[Path]) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    for path in sorted(paths, key=lambda item: item.as_posix()):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                total += len(chunk)
                digest.update(chunk)
    return digest.hexdigest(), total


def compute_file_sha256(path: Path) -> tuple[str | None, int | None]:
    if not path.exists() or not path.is_file():
        return None, None
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), size


def normalize_study_relative_path(relative_path: str) -> str:
    text = str(relative_path).replace("\\", "/")
    if is_storage_uri(text):
        return text
    return PurePosixPath(text).as_posix()


def resolve_study_relative_path(study: Study, relative_path: str) -> Path:
    normalized_text = normalize_study_relative_path(relative_path)
    if normalized_text.startswith("elys://datasets/"):
        without_scheme = normalized_text.removeprefix("elys://datasets/")
        parts = PurePosixPath(without_scheme).parts
        if len(parts) >= 3 and parts[1] == "versions":
            return dataset_version_root(parts[0], parts[2]).joinpath(*parts[3:])
    if normalized_text.startswith("study://"):
        without_scheme = normalized_text.removeprefix("study://")
        parts = PurePosixPath(without_scheme).parts
        if len(parts) >= 2 and parts[0] == study.id:
            return Path(study.data_root).joinpath(*parts[1:])
    normalized = PurePosixPath(normalize_study_relative_path(relative_path))
    return Path(study.data_root).joinpath(*normalized.parts)


def study_storage_uri(study: Study, relative_path: str) -> str:
    normalized = normalize_study_relative_path(relative_path)
    if is_storage_uri(normalized):
        return normalized
    return f"study://{study.id}/{normalized}"


def guess_dataset_file_mime_type(relative_path: str) -> str | None:
    suffix = PurePosixPath(relative_path).suffix.lower()
    if suffix == ".json":
        return "application/json"
    if suffix == ".tsv":
        return "text/tab-separated-values"
    if suffix in {".txt", ".vhdr", ".vmrk"}:
        return "text/plain"
    if suffix in {".fif", ".edf", ".bdf", ".eeg"}:
        return "application/octet-stream"
    return None


def add_dataset_file_record(
    db: Session,
    *,
    study: Study,
    dataset: Recording,
    upload_record: RecordingVersion,
    dataset_version: DatasetVersion | None = None,
    file_role: str,
    relative_path: str,
    current_user: User,
    metadata: dict[str, Any] | None = None,
    absolute_path: Path | None = None,
    storage_uri: str | None = None,
    logical_path: str | None = None,
) -> DatasetFile:
    normalized_path = normalize_study_relative_path(relative_path)
    target_path = absolute_path or resolve_study_relative_path(study, normalized_path)
    sha256, file_size = compute_file_sha256(target_path)
    normalized_logical_path = normalize_storage_logical_path(logical_path) if logical_path else None
    resolved_storage_uri = storage_uri or study_storage_uri(study, normalized_path)
    mime_reference = normalized_logical_path or normalized_path
    record = DatasetFile(
        study_id=study.id,
        recording_id=dataset.id,
        recording_version_id=upload_record.id,
        dataset_version_id=dataset_version.id if dataset_version else None,
        file_role=file_role,
        storage_uri=resolved_storage_uri,
        relative_path=normalized_path,
        logical_path=normalized_logical_path,
        file_size=file_size,
        sha256=sha256,
        mime_type=guess_dataset_file_mime_type(mime_reference),
        metadata_json=metadata or {},
        created_by=current_user.id,
    )
    db.add(record)
    return record


def add_dataset_file_derivation_record(
    db: Session,
    *,
    study: Study,
    source_file: DatasetFile,
    derived_file: DatasetFile,
    derivation_kind: str,
    metadata: dict[str, Any] | None = None,
    parameters: dict[str, Any] | None = None,
) -> DatasetFileDerivation:
    record = DatasetFileDerivation(
        study_id=study.id,
        source_file=source_file,
        derived_file=derived_file,
        derivation_kind=derivation_kind,
        transform_name="import.generate_canonical_fif",
        transform_version="mvp",
        parameters_json=parameters or {},
        metadata_json=metadata or {},
    )
    db.add(record)
    return record


def create_dataset_file_records(
    db: Session,
    *,
    study: Study,
    dataset: Recording,
    upload_record: RecordingVersion,
    dataset_version: DatasetVersion | None,
    primary_source: Path,
    source_format: str,
    archived_paths: list[Path],
    conversion: dict[str, Any],
    current_user: User,
    bids_subject_id: str,
    session: str | None,
    task: str,
    run: str | None,
) -> list[DatasetFile]:
    records: list[DatasetFile] = []
    primary_raw_bids_record: DatasetFile | None = None
    raw_bids_sidecar_records: dict[str, DatasetFile] = {}
    canonical_fif_record: DatasetFile | None = None
    canonical_provenance_record: DatasetFile | None = None
    primary_resolved = primary_source.resolve()
    for path in sorted(archived_paths, key=lambda item: item.as_posix()):
        relative_path = relative_to_study(study, path)
        dataset_reference = dataset_storage_reference_for_path(path)
        storage_uri = dataset_reference[0] if dataset_reference else study_storage_uri(study, relative_path)
        logical_path = (
            dataset_reference[1]
            if dataset_reference
            else dataset_logical_path_for_version(dataset_version, path)
        )
        is_primary = path.resolve() == primary_resolved
        original_metadata = {
            "source_format": source_format,
            "is_primary": is_primary,
            "extension": path.suffix.lower(),
            "upload_seq": upload_record.version_seq,
        }
        records.append(
            add_dataset_file_record(
                db,
                study=study,
                dataset=dataset,
                upload_record=upload_record,
                dataset_version=dataset_version,
                file_role="raw_source",
                relative_path=relative_path,
                storage_uri=storage_uri,
                logical_path=logical_path,
                absolute_path=path,
                current_user=current_user,
                metadata={**original_metadata, "compat_role": True, "standard_role": "original_upload"},
            )
        )
        records.append(
            add_dataset_file_record(
                db,
                study=study,
                dataset=dataset,
                upload_record=upload_record,
                dataset_version=dataset_version,
                file_role="original_upload",
                relative_path=relative_path,
                storage_uri=storage_uri,
                logical_path=logical_path,
                absolute_path=path,
                current_user=current_user,
                metadata=original_metadata,
            )
        )
        raw_bids_logical_path = raw_bids_data_logical_path(
            path,
            source_format=source_format,
            bids_subject_id=bids_subject_id,
            session=session,
            task=task,
            run=run,
        )
        raw_bids_record = add_dataset_file_record(
            db,
            study=study,
            dataset=dataset,
            upload_record=upload_record,
            dataset_version=dataset_version,
            file_role="raw_bids_data",
            relative_path=relative_path,
            storage_uri=storage_uri,
            logical_path=raw_bids_logical_path,
            absolute_path=path,
            current_user=current_user,
            metadata=raw_bids_data_metadata(
                source_format=source_format,
                source_path=path,
                storage_uri=storage_uri,
                upload_seq=upload_record.version_seq,
                is_primary=is_primary,
            ),
        )
        records.append(raw_bids_record)
        if is_primary:
            primary_raw_bids_record = raw_bids_record

    provenance = conversion.get("provenance") if isinstance(conversion.get("provenance"), dict) else {}
    conversion_params = provenance.get("ConversionParams") if isinstance(provenance.get("ConversionParams"), dict) else {}
    canonical_fif_path = conversion.get("canonical_fif_path") or conversion.get("fif_path")
    if canonical_fif_path:
        canonical_fif_text = str(canonical_fif_path)
        canonical_fif_storage_uri = canonical_fif_text if is_storage_uri(canonical_fif_text) else None
        canonical_fif_record = add_dataset_file_record(
            db,
            study=study,
            dataset=dataset,
            upload_record=upload_record,
            dataset_version=dataset_version,
            file_role="canonical_fif",
            relative_path=canonical_fif_text,
            storage_uri=canonical_fif_storage_uri,
            logical_path=(
                dataset_logical_path_from_storage_uri(canonical_fif_storage_uri)
                or normalize_study_relative_path(canonical_fif_text)
            ),
            current_user=current_user,
            metadata={
                "canonical_fif_dir": conversion.get("canonical_fif_dir"),
                "legacy_fif_dir": conversion.get("fif_dir"),
                "legacy_fif_path": conversion.get("fif_path"),
                "generated_by": "import.generate_canonical_fif",
                "upload_seq": upload_record.version_seq,
                "provenance": provenance,
            },
        )
        records.append(canonical_fif_record)

    canonical_provenance_path = conversion.get("canonical_provenance_path")
    if canonical_provenance_path:
        canonical_provenance_text = str(canonical_provenance_path)
        canonical_provenance_storage_uri = (
            canonical_provenance_text if is_storage_uri(canonical_provenance_text) else None
        )
        canonical_provenance_record = add_dataset_file_record(
            db,
            study=study,
            dataset=dataset,
            upload_record=upload_record,
            dataset_version=dataset_version,
            file_role="canonical_fif_provenance",
            relative_path=canonical_provenance_text,
            storage_uri=canonical_provenance_storage_uri,
            logical_path=(
                dataset_logical_path_from_storage_uri(canonical_provenance_storage_uri)
                or normalize_study_relative_path(canonical_provenance_text)
            ),
            current_user=current_user,
            metadata={
                "canonical_fif_path": conversion.get("canonical_fif_path"),
                "generated_by": "import.generate_canonical_fif",
                "upload_seq": upload_record.version_seq,
            },
        )
        records.append(canonical_provenance_record)

    sidecar_paths = conversion.get("sidecar_paths") if isinstance(conversion.get("sidecar_paths"), dict) else {}
    canonical_sidecar_paths = (
        conversion.get("canonical_sidecar_paths") if isinstance(conversion.get("canonical_sidecar_paths"), dict) else {}
    )
    for sidecar_key, sidecar_path in sorted(sidecar_paths.items()):
        records.append(
            add_dataset_file_record(
                db,
                study=study,
                dataset=dataset,
                upload_record=upload_record,
                dataset_version=dataset_version,
                file_role="sidecar",
                relative_path=str(sidecar_path),
                logical_path=normalize_study_relative_path(str(sidecar_path)),
                current_user=current_user,
                metadata={
                    "sidecar_key": sidecar_key,
                    "generated_by": "import",
                    "upload_seq": upload_record.version_seq,
                },
            )
        )
        raw_bids_role = RAW_BIDS_SIDECAR_ROLES.get(sidecar_key)
        raw_bids_logical_path = raw_bids_sidecar_logical_path(
            sidecar_key,
            bids_subject_id=bids_subject_id,
            session=session,
            task=task,
            run=run,
        )
        if raw_bids_role and raw_bids_logical_path:
            raw_bids_physical_path = str(canonical_sidecar_paths.get(sidecar_key) or sidecar_path)
            raw_bids_physical_storage_uri = (
                raw_bids_physical_path
                if is_storage_uri(raw_bids_physical_path)
                else study_storage_uri(study, raw_bids_physical_path)
            )
            raw_bids_sidecar_record = add_dataset_file_record(
                db,
                study=study,
                dataset=dataset,
                upload_record=upload_record,
                dataset_version=dataset_version,
                file_role=raw_bids_role,
                relative_path=raw_bids_physical_path,
                storage_uri=raw_bids_physical_storage_uri,
                logical_path=raw_bids_logical_path,
                current_user=current_user,
                metadata={
                    "sidecar_key": sidecar_key,
                    "view_kind": "raw_bids_logical",
                    "physical_storage_uri": raw_bids_physical_storage_uri,
                    "generated_by": "import.generate_canonical_fif",
                    "source_role": "sidecar",
                    "upload_seq": upload_record.version_seq,
                },
            )
            records.append(raw_bids_sidecar_record)
            raw_bids_sidecar_records[sidecar_key] = raw_bids_sidecar_record

    derivation_metadata = {
        "SourceRawBIDS": provenance.get("SourceRawBIDS"),
        "SourceEvents": provenance.get("SourceEvents"),
        "SourceChannels": provenance.get("SourceChannels"),
        "SourceSHA256": provenance.get("SourceSHA256"),
        "GeneratedBy": provenance.get("GeneratedBy"),
        "canonical_fif_path": conversion.get("canonical_fif_path"),
        "canonical_provenance_path": conversion.get("canonical_provenance_path"),
        "upload_seq": upload_record.version_seq,
    }
    if canonical_fif_record is not None and primary_raw_bids_record is not None:
        add_dataset_file_derivation_record(
            db,
            study=study,
            source_file=primary_raw_bids_record,
            derived_file=canonical_fif_record,
            derivation_kind="canonical_fif",
            metadata=derivation_metadata,
            parameters=conversion_params,
        )
    if canonical_provenance_record is not None and primary_raw_bids_record is not None:
        add_dataset_file_derivation_record(
            db,
            study=study,
            source_file=primary_raw_bids_record,
            derived_file=canonical_provenance_record,
            derivation_kind="canonical_fif_provenance",
            metadata=derivation_metadata,
            parameters=conversion_params,
        )
    for sidecar_key, sidecar_record in raw_bids_sidecar_records.items():
        if canonical_fif_record is not None:
            add_dataset_file_derivation_record(
                db,
                study=study,
                source_file=sidecar_record,
                derived_file=canonical_fif_record,
                derivation_kind=f"canonical_fif_{sidecar_key}",
                metadata={
                    **derivation_metadata,
                    "sidecar_key": sidecar_key,
                    "source_logical_path": sidecar_record.logical_path,
                },
                parameters=conversion_params,
            )
        if canonical_provenance_record is not None:
            add_dataset_file_derivation_record(
                db,
                study=study,
                source_file=sidecar_record,
                derived_file=canonical_provenance_record,
                derivation_kind=f"canonical_fif_provenance_{sidecar_key}",
                metadata={
                    **derivation_metadata,
                    "sidecar_key": sidecar_key,
                    "source_logical_path": sidecar_record.logical_path,
                },
                parameters=conversion_params,
            )

    return records


def create_dataset_upload_record(
    db: Session,
    *,
    study: Study,
    dataset: Recording,
    dataset_version: DatasetVersion | None,
    upload_seq: int,
    job_dir: Path,
    primary_source: Path,
    source_format: str,
    archived_paths: list[Path],
    conversion: dict[str, Any],
    total_size: int,
    checksum: str,
    current_user: User,
    bids_subject_id: str,
    session: str | None,
    task: str,
    run: str | None,
    note: str | None = None,
) -> RecordingVersion:
    (
        db.query(RecordingVersion)
        .filter(RecordingVersion.recording_id == dataset.id, RecordingVersion.status == "current")
        .update({"status": "replaced"}, synchronize_session=False)
    )
    upload_record = RecordingVersion(
        recording_id=dataset.id,
        version_seq=upload_seq,
        source_dir=relative_to_study(study, job_dir),
        source_main_file=relative_to_study(study, primary_source),
        source_files=[relative_to_study(study, path) for path in archived_paths],
        source_format=source_format,
        fif_dir=conversion["fif_dir"],
        fif_path=conversion["fif_path"],
        sidecar_paths=conversion["sidecar_paths"],
        file_size=total_size,
        checksum=checksum,
        status="current",
        qa_status="converted",
        uploaded_by=current_user.id,
        note=note,
    )
    db.add(upload_record)
    db.flush()
    dataset.current_version_id = upload_record.id
    create_dataset_file_records(
        db,
        study=study,
        dataset=dataset,
        upload_record=upload_record,
        dataset_version=dataset_version,
        primary_source=primary_source,
        source_format=source_format,
        archived_paths=archived_paths,
        conversion=conversion,
        current_user=current_user,
        bids_subject_id=bids_subject_id,
        session=session,
        task=task,
        run=run,
    )
    return upload_record


def ensure_fif_targets_are_free(fif_base: Path) -> None:
    targets = [
        fif_base.with_name(f"{fif_base.name}_raw.fif"),
        fif_base.with_name(f"{fif_base.name}_eeg.json"),
        fif_base.with_name(f"{fif_base.name}_channels.tsv"),
        fif_base.with_name(f"{fif_base.name}_events.tsv"),
        fif_base.with_name(f"{fif_base.name}_import.json"),
    ]
    for path in targets:
        if path.exists():
            raise HTTPException(status_code=409, detail=f"fifdata 中已存在同名记录，请更换 run 或 subject: {path.name}")


def ensure_canonical_fif_targets_are_free(canonical_fif_base: Path) -> None:
    targets = [
        canonical_fif_base.with_name(f"{canonical_fif_base.name}_raw.fif"),
        canonical_fif_base.with_name(f"{canonical_fif_base.name}_eeg.json"),
        canonical_fif_base.with_name(f"{canonical_fif_base.name}_channels.tsv"),
        canonical_fif_base.with_name(f"{canonical_fif_base.name}_events.tsv"),
        canonical_fif_base.with_name(f"{canonical_fif_base.name}_provenance.json"),
    ]
    for path in targets:
        if path.exists():
            raise HTTPException(
                status_code=409,
                detail=f"canonical FIF 中已存在同名记录，请更换 run 或 subject: {path.name}",
            )


def ensure_fifdata_dataset_files(study: Study, bids_subject_id: str) -> None:
    fif_root = Path(study.data_root) / "fifdata"
    fif_root.mkdir(parents=True, exist_ok=True)

    description = fif_root / "dataset_description.json"
    if not description.exists():
        description.write_text(
            json.dumps(
                {
                    "Name": f"{study.name} ELYS FIF working dataset",
                    "DatasetType": "ELYS-FIF-WorkingDataset",
                    "GeneratedBy": [{"Name": "ELYS", "Description": "Imported raw EEG converted to FIF"}],
                    "BIDSLikeEntities": True,
                    "Note": "This is not an official EEG-BIDS raw dataset. Official BIDS exports are generated under bids_exports/.",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    participants_json = fif_root / "participants.json"
    if not participants_json.exists():
        participants_json.write_text(
            json.dumps(
                {
                    "participant_id": {
                        "Description": "BIDS-like participant identifier used by ELYS FIF working dataset"
                    }
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    participants_tsv = fif_root / "participants.tsv"
    existing: list[str] = []
    if participants_tsv.exists():
        lines = participants_tsv.read_text(encoding="utf-8").splitlines()
        existing = [line.split("\t", 1)[0] for line in lines[1:] if line.strip()]
    if not participants_tsv.exists():
        participants_tsv.write_text("participant_id\n", encoding="utf-8")
    if bids_subject_id not in existing:
        with participants_tsv.open("a", encoding="utf-8", newline="") as handle:
            handle.write(f"{bids_subject_id}\n")


def write_channels_tsv(raw: Any, target: Path) -> None:
    ch_types = raw.get_channel_types() if hasattr(raw, "get_channel_types") else ["EEG"] * len(raw.ch_names)
    bads = set(raw.info.get("bads", []))
    low_cutoff = raw.info.get("highpass", "n/a")
    high_cutoff = raw.info.get("lowpass", "n/a")

    lines = ["name\ttype\tunits\tlow_cutoff\thigh_cutoff\tstatus\tstatus_description"]
    for name, ch_type in zip(raw.ch_names, ch_types):
        units = "uV" if ch_type == "eeg" else "n/a"
        status_value = "bad" if name in bads else "good"
        lines.append(f"{name}\t{ch_type.upper()}\t{units}\t{low_cutoff}\t{high_cutoff}\t{status_value}\t")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_events_tsv(raw: Any, target: Path) -> int:
    annotations = getattr(raw, "annotations", None)
    lines = ["onset\tduration\ttrial_type"]
    count = 0
    if annotations:
        for onset, duration, description in zip(annotations.onset, annotations.duration, annotations.description):
            lines.append(f"{float(onset):.6f}\t{float(duration):.6f}\t{description}")
            count += 1
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return count


def write_eeg_json(
    raw: Any,
    target: Path,
    *,
    task_label: str,
    source_format: str,
    import_job_id: str,
    duration_seconds: float | None,
) -> None:
    payload = {
        "TaskName": task_label.replace("task-", "", 1),
        "SamplingFrequency": float(raw.info["sfreq"]) if raw.info.get("sfreq") else None,
        "EEGChannelCount": len(raw.ch_names),
        "RecordingDuration": duration_seconds,
        "PowerLineFrequency": "n/a",
        "SourceFormat": source_format,
        "ImportJobId": import_job_id,
        "GeneratedBy": "ELYS import pipeline",
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def get_mne_module():
    try:
        from scipy.special import sph_harm as _sph_harm  # noqa: F401
        import mne
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail="服务器 EEG 转换环境异常：MNE/SciPy 依赖不兼容，请重新部署后重试",
        ) from exc
    return mne


def load_raw_for_conversion(upload_kind: str, source_path: Path):
    mne = get_mne_module()

    if upload_kind == "brainvision":
        reader = mne.io.read_raw_brainvision
    elif upload_kind == "edf":
        reader = mne.io.read_raw_edf
    elif upload_kind == "bdf":
        reader = mne.io.read_raw_bdf
    else:
        raise HTTPException(status_code=422, detail=f"{upload_kind} 暂不支持自动转换为 FIF")

    try:
        return reader(str(source_path), preload=True, verbose="ERROR")
    except TypeError:
        try:
            return reader(str(source_path), preload=True)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"FIF 转换失败: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"FIF 转换失败: {exc}") from exc


def generate_canonical_fif(
    *,
    study: Study,
    dataset_version: DatasetVersion,
    upload_kind: str,
    source_path: Path,
    source_format: str,
    canonical_fif_base: Path,
    legacy_fif_base: Path,
    bids_subject_id: str,
    session: str | None,
    task_label: str,
    run: str | None,
    upload_seq: int,
    import_job_id: str,
    archived_files: list[Path],
    checksum: str,
    temp_root: Path,
) -> dict[str, Any]:
    mne = get_mne_module()

    raw = load_raw_for_conversion(upload_kind, source_path)
    temp_dir = Path(tempfile.mkdtemp(prefix="fif-", dir=temp_root))
    canonical_fif_path = canonical_fif_base.with_name(f"{canonical_fif_base.name}_raw.fif")
    canonical_eeg_json_path = canonical_fif_base.with_name(f"{canonical_fif_base.name}_eeg.json")
    canonical_channels_path = canonical_fif_base.with_name(f"{canonical_fif_base.name}_channels.tsv")
    canonical_events_path = canonical_fif_base.with_name(f"{canonical_fif_base.name}_events.tsv")
    canonical_provenance_path = canonical_fif_base.with_name(f"{canonical_fif_base.name}_provenance.json")
    canonical_version_dir = canonical_fif_base.parent
    legacy_fif_path = legacy_fif_base.with_name(f"{legacy_fif_base.name}_raw.fif")
    legacy_eeg_json_path = legacy_fif_base.with_name(f"{legacy_fif_base.name}_eeg.json")
    legacy_channels_path = legacy_fif_base.with_name(f"{legacy_fif_base.name}_channels.tsv")
    legacy_events_path = legacy_fif_base.with_name(f"{legacy_fif_base.name}_events.tsv")
    legacy_import_json_path = legacy_fif_base.with_name(f"{legacy_fif_base.name}_import.json")
    legacy_version_dir = legacy_fif_base.parent
    temp_targets = [
        temp_dir / canonical_fif_path.name,
        temp_dir / canonical_eeg_json_path.name,
        temp_dir / canonical_channels_path.name,
        temp_dir / canonical_events_path.name,
        temp_dir / canonical_provenance_path.name,
    ]
    temp_fif, temp_eeg_json, temp_channels, temp_events, temp_provenance_json = temp_targets
    committed = False

    try:
        if canonical_version_dir.exists():
            raise HTTPException(
                status_code=409,
                detail=f"canonical FIF 版本目录已存在: {relative_to_study(study, canonical_version_dir)}",
            )

        sfreq = float(raw.info["sfreq"]) if raw.info.get("sfreq") else None
        n_times = int(raw.n_times) if getattr(raw, "n_times", None) is not None else None
        duration = float(n_times / sfreq) if sfreq and n_times is not None else None

        raw.save(str(temp_fif), overwrite=True, verbose="ERROR")

        # Re-open the written file so import validation catches write/read incompatibilities.
        check_raw = mne.io.read_raw_fif(str(temp_fif), preload=False, verbose="ERROR")
        check_raw.close()

        n_events = write_events_tsv(raw, temp_events)
        write_channels_tsv(raw, temp_channels)
        write_eeg_json(
            raw,
            temp_eeg_json,
            task_label=task_label,
            source_format=source_format,
            import_job_id=import_job_id,
            duration_seconds=duration,
        )

        source_reference = dataset_storage_reference_for_path(source_path)
        source_storage_uri = source_reference[0] if source_reference else study_storage_uri(study, relative_to_study(study, source_path))
        source_original_logical_path = source_reference[1] if source_reference else None
        source_sha256, source_size = compute_file_sha256(source_path)
        source_raw_bids_logical_path = raw_bids_data_logical_path(
            source_path,
            source_format=source_format,
            bids_subject_id=bids_subject_id,
            session=session,
            task=task_label,
            run=run,
        )
        source_channels_logical_path = raw_bids_sidecar_logical_path(
            "channels",
            bids_subject_id=bids_subject_id,
            session=session,
            task=task_label,
            run=run,
        )
        source_events_logical_path = raw_bids_sidecar_logical_path(
            "events",
            bids_subject_id=bids_subject_id,
            session=session,
            task=task_label,
            run=run,
        )
        provenance = {
            "importJobId": import_job_id,
            "sourceFormat": source_format,
            "SourceRawBIDS": {
                "logical_path": source_raw_bids_logical_path,
                "storage_uri": source_storage_uri,
            },
            "SourceOriginalUpload": {
                "logical_path": source_original_logical_path,
                "storage_uri": source_storage_uri,
                "file_size": source_size,
            },
            "SourceEvents": {"logical_path": source_events_logical_path},
            "SourceChannels": {"logical_path": source_channels_logical_path},
            "SourceSHA256": source_sha256,
            "checksum": checksum,
            "sourceFiles": [relative_to_study(study, path) for path in archived_files],
            "canonicalFifDir": relative_to_study(study, canonical_version_dir),
            "canonicalFifPath": relative_to_study(study, canonical_fif_path),
            "legacyFifDir": relative_to_study(study, legacy_version_dir),
            "legacyFifPath": relative_to_study(study, legacy_fif_path),
            "sidecars": {
                "eeg": relative_to_study(study, canonical_eeg_json_path),
                "channels": relative_to_study(study, canonical_channels_path),
                "events": relative_to_study(study, canonical_events_path),
                "provenance": relative_to_study(study, canonical_provenance_path),
            },
            "legacySidecars": {
                "eeg": relative_to_study(study, legacy_eeg_json_path),
                "channels": relative_to_study(study, legacy_channels_path),
                "events": relative_to_study(study, legacy_events_path),
                "import": relative_to_study(study, legacy_import_json_path),
            },
            "validation": {
                "fifReadable": True,
                "nChannels": len(raw.ch_names),
                "sfreq": sfreq,
                "durationSeconds": duration,
                "nEvents": n_events,
            },
            "GeneratedBy": {
                "Name": "ELYS import pipeline",
                "Step": "generate_canonical_fif",
                "Version": "mvp",
            },
            "GeneratedAt": datetime.utcnow().isoformat() + "Z",
            "ConversionParams": {
                "upload_kind": upload_kind,
                "preload": True,
                "output_format": "FIF",
                "legacy_mirror": True,
            },
            "createdAt": datetime.utcnow().isoformat() + "Z",
        }
        temp_provenance_json.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")

        canonical_version_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(temp_dir), str(canonical_version_dir))
        committed = True
        legacy_version_dir.mkdir(parents=True, exist_ok=True)
        for source, target in (
            (canonical_fif_path, legacy_fif_path),
            (canonical_eeg_json_path, legacy_eeg_json_path),
            (canonical_channels_path, legacy_channels_path),
            (canonical_events_path, legacy_events_path),
            (canonical_provenance_path, legacy_import_json_path),
        ):
            shutil.copy2(source, target)

        return {
            "canonical_fif_dir": relative_to_study(study, canonical_version_dir),
            "canonical_fif_path": relative_to_study(study, canonical_fif_path),
            "canonical_sidecar_paths": {
                "eeg": relative_to_study(study, canonical_eeg_json_path),
                "channels": relative_to_study(study, canonical_channels_path),
                "events": relative_to_study(study, canonical_events_path),
                "provenance": relative_to_study(study, canonical_provenance_path),
            },
            "canonical_provenance_path": relative_to_study(study, canonical_provenance_path),
            "fif_dir": relative_to_study(study, legacy_version_dir),
            "fif_path": relative_to_study(study, legacy_fif_path),
            "sidecar_paths": {
                "eeg": relative_to_study(study, legacy_eeg_json_path),
                "channels": relative_to_study(study, legacy_channels_path),
                "events": relative_to_study(study, legacy_events_path),
                "import": relative_to_study(study, legacy_import_json_path),
            },
            "n_channels": len(raw.ch_names),
            "sfreq": sfreq,
            "duration_seconds": duration,
            "n_events": n_events,
            "provenance": provenance,
            "source_raw_bids_logical_path": source_raw_bids_logical_path,
            "source_raw_bids_storage_uri": source_storage_uri,
            "source_sha256": source_sha256,
            "qa_report": {
                "import": provenance,
                "fif_conversion": {
                    "status": "success",
                    "source_format": source_format,
                    "canonical_fif_path": relative_to_study(study, canonical_fif_path),
                    "legacy_fif_path": relative_to_study(study, legacy_fif_path),
                    "created_at": datetime.utcnow().isoformat() + "Z",
                },
            },
        }
    except Exception:
        if not committed:
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    finally:
        close = getattr(raw, "close", None)
        if callable(close):
            close()
        if not committed:
            shutil.rmtree(temp_dir, ignore_errors=True)


@recording_router.get("", response_model=RecordingListResponse)
def list_recordings(
    study_id: str,
    dataset_asset_id: uuid.UUID | None = None,
    mount_id: uuid.UUID | None = None,
    mount_name: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:read", "当前用户没有查看采集记录权限")
    study = require_study_read(db.query(Study).filter(Study.id == study_id).first(), db, current_user)
    has_asset_filter = dataset_asset_id is not None or mount_id is not None or mount_name is not None
    resolved_asset_id = resolve_dataset_asset_filter(
        db,
        study=study,
        dataset_asset_id=dataset_asset_id,
        mount_id=mount_id,
        mount_name=mount_name,
    )
    recordings = list_recordings_for_study(
        db,
        study=study,
        dataset_asset_id=resolved_asset_id,
        mounted_dataset_asset_ids=None if has_asset_filter else active_study_dataset_asset_ids(db, study=study),
    )
    return RecordingListResponse(recordings=[recording_to_response(recording) for recording in recordings])


@recording_router.get("/{recording_id}/versions", response_model=RecordingVersionListResponse)
def list_recording_versions(
    study_id: str,
    recording_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:read", "当前用户没有查看采集版本权限")
    study = require_study_read(db.query(Study).filter(Study.id == study_id).first(), db, current_user)
    recording = get_recording_for_study(db, study=study, recording_id=recording_id)
    if recording is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="采集记录不存在")
    versions = list_recording_versions_for_study(db, study=study, recording_id=recording_id)
    return RecordingVersionListResponse(
        versions=[recording_version_to_response(version, study_id=study.id) for version in versions],
    )


@recording_router.get("/{recording_id}/files", response_model=DatasetFileListResponse)
def list_recording_files(
    study_id: str,
    recording_id: uuid.UUID,
    file_role: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:read", "当前用户没有查看采集文件权限")
    study = require_study_read(db.query(Study).filter(Study.id == study_id).first(), db, current_user)
    recording = get_recording_for_study(db, study=study, recording_id=recording_id)
    if recording is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="采集记录不存在")
    query = db.query(DatasetFile).filter(DatasetFile.study_id == study.id, DatasetFile.recording_id == recording_id)
    if file_role:
        query = query.filter(DatasetFile.file_role == file_role)
    files = query.order_by(DatasetFile.created_at.desc(), DatasetFile.id.desc()).all()
    return DatasetFileListResponse(files=[dataset_file_to_response(item) for item in files])


@asset_router.post("/bootstrap", response_model=DatasetBootstrapResponse, status_code=status.HTTP_201_CREATED)
def bootstrap_dataset_asset(
    payload: DatasetBootstrapRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    import sys
    sys.stderr.write(
        f"[ELYS-TRACE] bootstrap_dataset_asset ENTERED user={current_user.username} "
        f"dataset_code={payload.dataset.code} paired_mode={payload.paired_study.mode}\n"
    )
    sys.stderr.flush()
    require_system_permission(current_user, "data:write", "当前用户没有创建 Dataset 资产权限")
    paired_study = None
    if payload.paired_study.mode == "create":
        ensure_study_create_permission(current_user)
    else:
        paired_study = require_study_write(
            db.query(Study).filter(Study.id == payload.paired_study.study_id).first(),
            db,
            current_user,
        )
    validate_mount_selection_json(payload.selection_json)

    try:
        result = bootstrap_dataset(
            db,
            dataset_name=payload.dataset.name,
            dataset_code=payload.dataset.code,
            dataset_description=payload.dataset.description,
            dataset_visibility=payload.dataset.visibility,
            dataset_metadata_json=payload.dataset.metadata_json,
            paired_study_mode=payload.paired_study.mode,
            paired_study=paired_study,
            paired_study_code=payload.paired_study.code,
            paired_study_name=payload.paired_study.name,
            paired_study_description=payload.paired_study.description,
            paired_study_storage_quota_gb=payload.paired_study.storage_quota_gb,
            current_user=current_user,
            mount_name=payload.mount_name,
            selection_json=payload.selection_json,
            is_active=payload.is_active,
            settings_obj=settings,
            commit=True,
        )
    except DatasetAssetConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except StudyCreateCodeConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="研究项短码已存在") from exc
    except StudyCreateIntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="研究项创建失败") from exc
    except (StudyStorageSetupError, DatasetBootstrapStorageError) as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Dataset bootstrap 存储初始化失败: {exc}") from exc

    return DatasetBootstrapResponse(
        dataset_asset=dataset_asset_to_response(result.dataset_asset),
        dataset_version=dataset_version_to_response(result.dataset_version),
        study=study_to_response(result.study),
        mount=study_dataset_mount_to_response(result.mount),
        next_upload=DatasetBootstrapNextUpload(**result.next_upload.__dict__),
    )


@asset_router.get("", response_model=DatasetAssetListResponse)
def list_dataset_assets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:read", "当前用户没有查看 Dataset 资产权限")
    assets = list_visible_dataset_assets(db, user=current_user)
    # UI Phase (docs_v2/6-05): 一次性批量聚合统计，避免 N+1
    stats_map = compute_asset_stats(db, [a.id for a in assets])
    return DatasetAssetListResponse(
        assets=[dataset_asset_to_response(asset, stats=stats_map.get(str(asset.id))) for asset in assets],
    )


@asset_router.get("/{asset_id}/versions", response_model=DatasetVersionListResponse)
def list_dataset_asset_versions(
    asset_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Phase 3 (docs_v2/3-25) 列出某个 Asset 的所有版本，供前端展示版本卡片 + 发布按钮。"""
    require_system_permission(current_user, "data:read", "当前用户没有查看 Dataset 资产权限")
    asset = get_dataset_asset_for_user(db, asset_id=asset_id, user=current_user)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset 资产不存在或无权访问")
    versions = (
        db.query(DatasetVersion)
        .filter(DatasetVersion.dataset_asset_id == asset.id)
        .order_by(DatasetVersion.created_at.desc(), DatasetVersion.id.desc())
        .all()
    )
    return DatasetVersionListResponse(
        versions=[dataset_version_to_response(item) for item in versions],
    )


@asset_router.post(
    "/{asset_id}/versions",
    response_model=DatasetVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_new_draft_version(
    asset_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Phase 3 (docs_v2/3-25) 在已发布过版本的 Asset 上新建 draft 版本。

    与 bootstrap 不同: bootstrap 用于首次创建 Asset, 此端点是 owner 在已发布基础上推 v+1。
    新 draft 的 version_label='working' (storage slot 已被上次 publish rename 释放)。
    """
    from app.services.dataset_bootstrap import ensure_dataset_version_storage
    from app.services.dataset_lifecycle import (
        DatasetLifecyclePermissionError,
        DatasetLifecycleStateError,
        DatasetLifecycleValidationError,
        create_new_draft_version as create_draft_service,
    )

    require_system_permission(current_user, "data:write", "当前用户没有创建 Dataset 资产权限")
    asset = get_dataset_asset_for_user(db, asset_id=asset_id, user=current_user)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset 资产不存在或无权访问")

    try:
        result = create_draft_service(
            db,
            asset=asset,
            actor=current_user,
            commit=False,  # 先 flush 拿到 version, 由路由保证目录创建后再 commit
        )
    except DatasetLifecyclePermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except DatasetLifecycleStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DatasetLifecycleValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    try:
        ensure_dataset_version_storage(result.dataset_version, settings_obj=settings)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"新建 draft 版本存储目录创建失败: {exc}",
        ) from exc

    db.commit()
    db.refresh(result.dataset_version)
    return dataset_version_to_response(result.dataset_version)


@asset_router.get("/{asset_id}/files", response_model=DatasetFileListResponse)
def list_dataset_asset_files(
    asset_id: uuid.UUID,
    version_label: str | None = None,
    file_role: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:read", "当前用户没有查看 Dataset 文件权限")
    asset = get_dataset_asset_for_user(db, asset_id=asset_id, user=current_user)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset 资产不存在或无权访问")
    query = (
        db.query(DatasetFile)
        .join(Recording, DatasetFile.recording_id == Recording.id)
        .filter(Recording.dataset_asset_id == asset.id)
    )
    if version_label:
        query = query.join(DatasetVersion, DatasetFile.dataset_version_id == DatasetVersion.id).filter(
            DatasetVersion.version_label == version_label
        )
    if file_role:
        query = query.filter(DatasetFile.file_role == file_role)
    files = query.order_by(DatasetFile.logical_path.asc(), DatasetFile.relative_path.asc(), DatasetFile.id.asc()).all()
    return DatasetFileListResponse(files=[dataset_file_to_response(item) for item in files])


@asset_router.get("/{asset_id}/bids-tree", response_model=DatasetFileTreeResponse)
def get_dataset_asset_bids_tree(
    asset_id: uuid.UUID,
    version_label: str | None = None,
    prefix: str = DATASET_RAW_BIDS_PREFIX,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:read", "当前用户没有查看 Raw BIDS 文件树权限")
    asset = get_dataset_asset_for_user(db, asset_id=asset_id, user=current_user)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset 资产不存在或无权访问")
    query = (
        db.query(DatasetFile)
        .join(Recording, DatasetFile.recording_id == Recording.id)
        .filter(Recording.dataset_asset_id == asset.id)
    )
    if version_label:
        query = query.join(DatasetVersion, DatasetFile.dataset_version_id == DatasetVersion.id).filter(
            DatasetVersion.version_label == version_label
        )
    files = query.order_by(DatasetFile.logical_path.asc(), DatasetFile.relative_path.asc(), DatasetFile.id.asc()).all()
    tree = build_dataset_file_tree(files, prefix=prefix)
    return DatasetFileTreeResponse(
        dataset_asset_id=str(asset.id),
        version_label=version_label,
        prefix=prefix,
        tree=tree,
    )


@recording_router.post("/import-task", response_model=AsyncTaskResponse, status_code=status.HTTP_201_CREATED)
def create_recording_import_task(
    study_id: str,
    payload: DatasetImportTaskRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:write", "当前用户没有创建导入任务权限")
    study = require_study_write(db.query(Study).filter(Study.id == study_id).first(), db, current_user)
    payload = payload or DatasetImportTaskRequest()
    asset = None
    if payload.dataset_asset_id:
        asset = get_dataset_asset_for_user(db, asset_id=payload.dataset_asset_id, user=current_user)
        if asset is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset 资产不存在或无权访问")
        if not can_write_dataset_asset(asset, current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权写入该 Dataset 资产")
    payload_json = {
        "study_id": study.id,
        "dataset_asset_id": str(payload.dataset_asset_id) if payload.dataset_asset_id else None,
        "staged_upload_uri": payload.staged_upload_uri,
        "metadata_json": payload.metadata_json,
        "mode": "async_dataset_import",
        "sync_upload_endpoint": f"/api/v1/studies/{study.id}/recordings/import",
    }
    return create_and_dispatch_file_task(
        db,
        task_type="dataset_import",
        study_id=study.id,
        resource_kind="dataset_asset" if asset else "study",
        resource_id=asset.id if asset else None,
        payload_json=payload_json,
        current_user=current_user,
    )


@asset_router.post("/{asset_id}/raw-bids-build", response_model=AsyncTaskResponse, status_code=status.HTTP_201_CREATED)
def create_raw_bids_build_task(
    asset_id: uuid.UUID,
    payload: DatasetAssetTaskRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:write", "当前用户没有创建 Raw BIDS 构建任务权限")
    asset = get_dataset_asset_for_user(db, asset_id=asset_id, user=current_user)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset 资产不存在或无权访问")
    if not can_write_dataset_asset(asset, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权写入该 Dataset 资产")
    payload = payload or DatasetAssetTaskRequest()
    return create_and_dispatch_file_task(
        db,
        task_type="raw_bids_build",
        study_id=None,
        resource_kind="dataset_asset",
        resource_id=asset.id,
        payload_json={
            "dataset_asset_id": str(asset.id),
            "version_label": payload.version_label,
            "dry_run": payload.dry_run,
            "parameters_json": payload.parameters_json,
        },
        current_user=current_user,
    )


@asset_router.post("/{asset_id}/canonical-fif-rebuild", response_model=AsyncTaskResponse, status_code=status.HTTP_201_CREATED)
def create_canonical_fif_rebuild_task(
    asset_id: uuid.UUID,
    payload: DatasetAssetTaskRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:write", "当前用户没有创建 canonical FIF 重建任务权限")
    asset = get_dataset_asset_for_user(db, asset_id=asset_id, user=current_user)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset 资产不存在或无权访问")
    if not can_write_dataset_asset(asset, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权写入该 Dataset 资产")
    payload = payload or DatasetAssetTaskRequest()
    return create_and_dispatch_file_task(
        db,
        task_type="canonical_fif_rebuild",
        study_id=None,
        resource_kind="dataset_asset",
        resource_id=asset.id,
        payload_json={
            "dataset_asset_id": str(asset.id),
            "version_label": payload.version_label,
            "dry_run": payload.dry_run,
            "parameters_json": payload.parameters_json,
        },
        current_user=current_user,
    )


@asset_router.patch("/{asset_id}", response_model=DatasetAssetResponse)
def update_dataset_asset(
    asset_id: uuid.UUID,
    payload: DatasetAssetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:write", "当前用户没有修改 Dataset 资产权限")
    asset = get_dataset_asset_for_user(db, asset_id=asset_id, user=current_user)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset 资产不存在或无权访问")
    if not (current_user.has_role("admin") or asset.owner_id == current_user.id or asset.created_by == current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权修改该 Dataset 资产")

    fields_set = payload.model_fields_set
    old_status = asset.status
    if "name" in fields_set and payload.name is not None:
        asset.name = payload.name
    if "description" in fields_set:
        asset.description = payload.description
    if "status" in fields_set and payload.status is not None:
        if payload.status == "quarantined" and not current_user.has_role("admin"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有管理员可以隔离 Dataset 资产")
        asset.status = payload.status
    if "visibility" in fields_set and payload.visibility is not None:
        asset.visibility = payload.visibility
    if "metadata_json" in fields_set and payload.metadata_json is not None:
        asset.metadata_json = payload.metadata_json
    asset.updated_at = datetime.utcnow()

    record_audit_event(
        db,
        action="dataset_asset.updated",
        actor_id=current_user.id,
        event_scope="dataset_asset",
        resource_kind="dataset_asset",
        resource_id=asset.id,
        resource_label=asset.name,
        metadata={
            "fields": sorted(fields_set),
            "old_status": old_status,
            "new_status": asset.status,
            "visibility": asset.visibility,
        },
    )
    db.commit()
    db.refresh(asset)
    return dataset_asset_to_response(asset)


@router.get("/mounts", response_model=StudyDatasetMountListResponse)
def list_dataset_mounts(
    study_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:read", "当前用户没有查看 Dataset 挂载权限")
    study = require_study_read(db.query(Study).filter(Study.id == study_id).first(), db, current_user)
    mounts = list_study_dataset_mounts(db, study=study)
    # UI Phase (docs_v2/6-05): 给嵌套 dataset_asset 带上数据概要
    asset_ids = [m.dataset_asset_id for m in mounts]
    stats_map = compute_asset_stats(db, asset_ids)
    return StudyDatasetMountListResponse(
        mounts=[
            study_dataset_mount_to_response(mount, asset_stats=stats_map.get(str(mount.dataset_asset_id)))
            for mount in mounts
        ],
    )


@router.post("/mounts", response_model=StudyDatasetMountResponse, status_code=status.HTTP_201_CREATED)
def mount_dataset_asset(
    study_id: str,
    payload: StudyDatasetMountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:write", "当前用户没有挂载 Dataset 资产权限")
    study = require_study_write(db.query(Study).filter(Study.id == study_id).first(), db, current_user)
    asset = get_dataset_asset_for_user(db, asset_id=payload.dataset_asset_id, user=current_user)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset 资产不存在或无权访问")
    if asset.status in {"deleted", "quarantined"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Dataset Asset 当前状态不允许挂载: {asset.status}")
    validate_mount_selection_json(payload.selection_json)
    # Phase 3 (docs_v2/3-25): 未传 version_id 时默认 asset.current_version_id
    resolved_version_id = payload.dataset_version_id or asset.current_version_id
    try:
        mount = mount_dataset_asset_to_study(
            db,
            study=study,
            dataset_asset=asset,
            mount_name=payload.mount_name,
            selection_json=payload.selection_json,
            is_active=payload.is_active,
            mounted_by=current_user.id,
            dataset_version_id=resolved_version_id,
        )
    except DatasetAssetConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DatasetMountStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    record_audit_event(
        db,
        study_id=study.id,
        action="study.dataset_mount.created",
        actor_id=current_user.id,
        event_scope="study",
        resource_kind="study_dataset_mount",
        resource_id=mount.id,
        resource_label=mount.mount_name,
        metadata={
            "dataset_asset_id": str(asset.id),
            "dataset_asset_code": asset.code,
            "is_active": mount.is_active,
            "selection_json": mount.selection_json or {},
        },
    )
    db.commit()
    db.refresh(mount)
    return study_dataset_mount_to_response(mount)


@router.patch("/mounts/{mount_id}", response_model=StudyDatasetMountResponse)
def update_dataset_mount(
    study_id: str,
    mount_id: uuid.UUID,
    payload: StudyDatasetMountUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:write", "当前用户没有修改 Dataset 挂载权限")
    study = require_study_write(db.query(Study).filter(Study.id == study_id).first(), db, current_user)
    mount = get_study_dataset_mount(db, study=study, mount_id=mount_id)
    if mount is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset 挂载不存在")
    try:
        if payload.selection_json is not None:
            validate_mount_selection_json(payload.selection_json)
        update_study_dataset_mount(
            db,
            study=study,
            mount=mount,
            mount_name=payload.mount_name,
            selection_json=payload.selection_json,
            is_active=payload.is_active,
            # Phase 3 (docs_v2/3-25) C: 版本升级
            dataset_version_id=payload.dataset_version_id,
        )
    except DatasetAssetConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DatasetMountStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    record_audit_event(
        db,
        study_id=study.id,
        action="study.dataset_mount.updated",
        actor_id=current_user.id,
        event_scope="study",
        resource_kind="study_dataset_mount",
        resource_id=mount.id,
        resource_label=mount.mount_name,
        metadata={
            "dataset_asset_id": str(mount.dataset_asset_id),
            "selection_json": mount.selection_json or {},
            "is_active": mount.is_active,
        },
    )
    db.commit()
    db.refresh(mount)
    return study_dataset_mount_to_response(mount)


@router.delete("/mounts/{mount_id}", response_model=StudyDatasetMountResponse)
def deactivate_dataset_mount(
    study_id: str,
    mount_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:write", "当前用户没有停用 Dataset 挂载权限")
    study = require_study_write(db.query(Study).filter(Study.id == study_id).first(), db, current_user)
    mount = get_study_dataset_mount(db, study=study, mount_id=mount_id)
    if mount is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset 挂载不存在")
    update_study_dataset_mount(db, study=study, mount=mount, is_active=False)
    record_audit_event(
        db,
        study_id=study.id,
        action="study.dataset_mount.deactivated",
        actor_id=current_user.id,
        event_scope="study",
        resource_kind="study_dataset_mount",
        resource_id=mount.id,
        resource_label=mount.mount_name,
        metadata={"dataset_asset_id": str(mount.dataset_asset_id)},
    )
    db.commit()
    db.refresh(mount)
    return study_dataset_mount_to_response(mount)


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


@recording_router.get("/{recording_id}/qa", response_model=DatasetQaResponse)
def get_recording_qa_report(
    study_id: str,
    recording_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:read", "当前用户没有查看数据权限")
    study = require_study_read(db.query(Study).filter(Study.id == study_id).first(), db, current_user)
    dataset = (
        db.query(Recording)
        .options(joinedload(Recording.subject), joinedload(Recording.current_version))
        .filter(Recording.study_id == study.id, Recording.id == recording_id)
        .first()
    )
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="采集记录不存在")

    return dataset_qa_to_response(dataset)


@recording_router.post("/{recording_id}/qa/mock-run", response_model=DatasetQaMockRunResponse)
def run_recording_mock_qa_report(
    study_id: str,
    recording_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:write", "当前用户没有写入数据权限")
    study = require_study_write(db.query(Study).filter(Study.id == study_id).first(), db, current_user)
    dataset = (
        db.query(Recording)
        .options(joinedload(Recording.subject), joinedload(Recording.current_version))
        .filter(Recording.study_id == study.id, Recording.id == recording_id)
        .first()
    )
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="采集记录不存在")

    old_qa_status = dataset.qa_status
    qa_report = validate_mock_qa_report_payload(build_mock_qa_report(study, dataset))
    apply_mock_qa_status(dataset, qa_report)
    record_dataset_qa_action(
        db,
        study=study,
        dataset=dataset,
        qa_report=qa_report,
        action="dataset.qa.mock_run",
        actor=current_user,
        occurred_at=datetime.utcnow(),
        old_qa_status=old_qa_status,
    )

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(dataset)

    return DatasetQaMockRunResponse(
        dataset_id=str(dataset.id),
        study_id=dataset.study_id,
        qa_status=dataset.qa_status,
        qa_report=qa_report,
    )


@recording_router.post("/{recording_id}/qa/review", response_model=DatasetQaReviewResponse)
def review_recording_qa_report(
    study_id: str,
    recording_id: uuid.UUID,
    review: DatasetQaReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:write", "当前用户没有写入数据权限")
    study = require_study_write(db.query(Study).filter(Study.id == study_id).first(), db, current_user)
    dataset = (
        db.query(Recording)
        .options(joinedload(Recording.subject), joinedload(Recording.current_version))
        .filter(Recording.study_id == study.id, Recording.id == recording_id)
        .first()
    )
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="采集记录不存在")

    old_qa_status = dataset.qa_status
    qa_report = require_existing_qa_report(dataset)
    qa_report = apply_dataset_qa_review(
        dataset=dataset,
        qa_report=qa_report,
        review=review,
        current_user=current_user,
    )
    record_dataset_qa_action(
        db,
        study=study,
        dataset=dataset,
        qa_report=qa_report,
        action="dataset.qa.review",
        actor=current_user,
        occurred_at=datetime.utcnow(),
        old_qa_status=old_qa_status,
        conclusion=review.conclusion,
    )

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(dataset)

    return DatasetQaReviewResponse(
        dataset_id=str(dataset.id),
        study_id=dataset.study_id,
        qa_status=dataset.qa_status,
        qa_report=qa_report,
    )


@recording_router.post("/import", response_model=RecordingUploadResponse, status_code=status.HTTP_201_CREATED)
async def import_recording(
    study_id: str,
    subject: str = Form(...),
    task: str = Form(...),
    session: str | None = Form(None),
    run: str | None = Form(None),
    replace_existing: bool = Form(False),
    dataset_asset_id: uuid.UUID | None = Form(None),
    mount_name: str | None = Form(None),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:write", "当前用户没有上传数据权限")
    study = require_study_write(db.query(Study).filter(Study.id == study_id).first(), db, current_user)
    target_asset, target_mount = resolve_upload_dataset_asset(
        db,
        study=study,
        current_user=current_user,
        dataset_asset_id=dataset_asset_id,
        mount_name=mount_name,
    )
    target_version = get_or_create_working_dataset_version(db, dataset_asset=target_asset, current_user=current_user)
    upload_kind, items_by_extension = classify_uploads(files)

    bids_subject_id = normalize_bids_label(subject, prefix="sub-", required=True)
    task_label = normalize_bids_label(task, prefix="task-", required=True)
    session_label = normalize_bids_label(session or "", prefix="ses-")
    run_label = normalize_bids_label(run or "", prefix="run-")

    subject_record = (
        db.query(Subject)
        .filter(Subject.study_id == study.id, Subject.bids_subject_id == bids_subject_id)
        .first()
    )
    duplicate = None
    if subject_record:
        duplicate = (
            db.query(Recording)
            .options(joinedload(Recording.current_version))
            .filter(
                Recording.study_id == study.id,
                Recording.subject_id == subject_record.id,
                Recording.session == session_label,
                Recording.task == task_label,
                Recording.run == run_label,
            )
            .first()
        )
    if duplicate and not replace_existing:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "DATASET_EXISTS",
                "message": "该数据位已经存在，可以作为新上传版本导入，并在成功后切换为当前版本。",
                "dataset_id": str(duplicate.id),
                "subject": bids_subject_id,
                "session": session_label,
                "task": task_label,
                "run": run_label,
                "current_upload_seq": duplicate.current_version.version_seq if duplicate.current_version else None,
                "fif_path": duplicate.fif_path,
            },
        )

    job_id = make_import_job_id()
    upload_seq = get_next_upload_seq(
        db,
        dataset=duplicate,
        study=study,
        dataset_asset=target_asset,
        bids_subject_id=bids_subject_id,
        session=session_label,
        task=task_label,
        run=run_label,
    )
    job_dir = make_import_job_dir(
        study,
        bids_subject_id,
        session_label,
        task_label,
        run_label,
        upload_seq,
        dataset_asset=target_asset,
    )
    temp_root = Path(study.data_root) / "upload_staging"
    temp_root.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "jobId": job_id,
        "uploadSeq": upload_seq,
        "status": "archiving",
        "studyId": study.id,
        "replaceExisting": replace_existing,
        "existingDatasetId": str(duplicate.id) if duplicate else None,
        "datasetAssetId": str(target_asset.id),
        "datasetVersionId": str(target_version.id),
        "datasetVersionLabel": target_version.version_label,
        "mountName": target_mount.mount_name if target_mount else None,
        "createdAt": datetime.utcnow().isoformat() + "Z",
        "entities": {
            "subject": bids_subject_id,
            "session": session_label,
            "task": task_label,
            "run": run_label,
        },
        "uploadKind": upload_kind,
        "files": [item.relative_path.as_posix() for item in items_by_extension.values()],
    }
    write_manifest(job_dir, manifest)

    archived: dict[str, Path] = {}
    try:
        archived = await archive_uploads(items_by_extension, job_dir, files_subdir=None)
        archived_paths = list(archived.values())
        checksum, total_size = compute_files_checksum(archived_paths)

        existing_checksum_query = db.query(Recording).filter(
            Recording.study_id == study.id,
            Recording.dataset_asset_id == target_asset.id,
            Recording.checksum == checksum,
        )
        if duplicate:
            existing_checksum_query = existing_checksum_query.filter(Recording.id != duplicate.id)
        existing_checksum = existing_checksum_query.first()
        if existing_checksum:
            manifest.update(
                {
                    "status": "duplicate",
                    "checksum": checksum,
                    "duplicateDatasetId": str(existing_checksum.id),
                    "updatedAt": datetime.utcnow().isoformat() + "Z",
                }
            )
            write_manifest(job_dir, manifest)
            raise HTTPException(status_code=409, detail="检测到完全相同的数据已经导入过，已阻止重复入库")
        if duplicate and duplicate.checksum == checksum:
            manifest.update(
                {
                    "status": "duplicate",
                    "checksum": checksum,
                    "duplicateDatasetId": str(duplicate.id),
                    "updatedAt": datetime.utcnow().isoformat() + "Z",
                }
            )
            write_manifest(job_dir, manifest)
            raise HTTPException(status_code=409, detail="本次上传与当前数据完全相同，无需替换")

        if upload_kind == "brainvision":
            primary_source = archived[".vhdr"]
            source_format = "BRAINVISION"
        else:
            extension = next(iter(archived))
            primary_source = archived[extension]
            source_format = STANDARD_SINGLE_EXTENSIONS[extension]

        fif_base = build_fif_base_path(study, bids_subject_id, session_label, task_label, run_label, upload_seq)
        canonical_fif_base = build_canonical_fif_base_path(
            target_version,
            bids_subject_id,
            session_label,
            task_label,
            run_label,
            upload_seq,
        )
        ensure_fif_targets_are_free(fif_base)
        ensure_canonical_fif_targets_are_free(canonical_fif_base)
        ensure_fifdata_dataset_files(study, bids_subject_id)

        conversion = generate_canonical_fif(
            study=study,
            dataset_version=target_version,
            upload_kind=upload_kind,
            source_path=primary_source,
            source_format=source_format,
            canonical_fif_base=canonical_fif_base,
            legacy_fif_base=fif_base,
            bids_subject_id=bids_subject_id,
            session=session_label,
            task_label=task_label,
            run=run_label,
            upload_seq=upload_seq,
            import_job_id=job_id,
            archived_files=archived_paths,
            checksum=checksum,
            temp_root=temp_root,
        )

        subject_record = subject_record or get_or_create_subject(db, study, bids_subject_id)
        source_path = relative_to_study(study, primary_source)
        now = datetime.utcnow()
        if duplicate:
            dataset = duplicate
            if dataset.dataset_asset_id is None:
                dataset.dataset_asset_id = target_asset.id
            elif dataset.dataset_asset_id != target_asset.id:
                raise HTTPException(
                    status_code=409,
                    detail="该 subject/session/task/run 已存在于另一个 Dataset Asset 中，请调整上传目标或使用新的 run 标签",
                )
            previous_source_path = dataset.source_path
            previous_fif_path = dataset.fif_path
            dataset.source_format = source_format
            dataset.source_path = source_path
            dataset.fif_path = conversion["fif_path"]
            dataset.file_size = total_size
            dataset.checksum = checksum
            dataset.n_channels = conversion["n_channels"]
            dataset.sfreq = conversion["sfreq"]
            dataset.duration_seconds = conversion["duration_seconds"]
            dataset.n_events = conversion["n_events"]
            dataset.qa_status = "converted"
            dataset.qa_report = {
                **conversion["qa_report"],
                "replacement": {
                    "status": "current_version_switched",
                    "upload_seq": upload_seq,
                    "previous_source_path": previous_source_path,
                    "previous_fif_path": previous_fif_path,
                    "replaced_at": now.isoformat() + "Z",
                },
            }
            dataset.imported_by = current_user.id
            dataset.imported_at = now
        else:
            dataset = Recording(
                study_id=study.id,
                dataset_asset_id=target_asset.id,
                subject_id=subject_record.id,
                session=session_label,
                task=task_label,
                run=run_label,
                source_format=source_format,
                source_path=source_path,
                fif_path=conversion["fif_path"],
                file_size=total_size,
                checksum=checksum,
                n_channels=conversion["n_channels"],
                sfreq=conversion["sfreq"],
                duration_seconds=conversion["duration_seconds"],
                n_events=conversion["n_events"],
                qa_status="converted",
                qa_report=conversion["qa_report"],
                imported_by=current_user.id,
            )
            db.add(dataset)
            db.flush()

        upload_record = create_dataset_upload_record(
            db,
            study=study,
            dataset=dataset,
            dataset_version=target_version,
            upload_seq=upload_seq,
            job_dir=job_dir,
            primary_source=primary_source,
            source_format=source_format,
            archived_paths=archived_paths,
            conversion=conversion,
            total_size=total_size,
            checksum=checksum,
            current_user=current_user,
            bids_subject_id=bids_subject_id,
            session=session_label,
            task=task_label,
            run=run_label,
            note="replace_existing" if duplicate else "initial_import",
        )
        record_audit_event(
            db,
            study_id=study.id,
            action="dataset.reuploaded" if duplicate else "dataset.uploaded",
            actor_id=current_user.id,
            resource_kind="dataset",
            resource_id=dataset.id,
            resource_label=f"{bids_subject_id}/{session_label or 'no-session'}/{task_label}/{run_label or 'no-run'}",
            metadata={
                "dataset_upload_id": str(upload_record.id),
                "upload_seq": upload_seq,
                "upload_kind": upload_kind,
                "source_format": source_format,
                "checksum": checksum,
                "file_size": total_size,
                "replace_existing": bool(duplicate),
                "fif_path": dataset.fif_path,
                "canonical_fif_path": conversion.get("canonical_fif_path"),
                "canonical_provenance_path": conversion.get("canonical_provenance_path"),
                "dataset_asset_id": str(dataset.dataset_asset_id) if dataset.dataset_asset_id else None,
                "mount_name": target_mount.mount_name if target_mount else None,
            },
        )
        db.commit()
        db.refresh(dataset)
        dataset.subject = subject_record
        dataset.current_version = upload_record

        manifest.update(
            {
                "status": "done",
                "checksum": checksum,
                "fileSize": total_size,
                "datasetId": str(dataset.id),
                "datasetUploadId": str(upload_record.id),
                "uploadSeq": upload_seq,
                "mode": "replacement" if duplicate else "new",
                "sourcePath": dataset.source_path,
                "fifPath": dataset.fif_path,
                "fifDir": conversion["fif_dir"],
                "sidecars": conversion["sidecar_paths"],
                "canonicalFifPath": conversion.get("canonical_fif_path"),
                "canonicalFifDir": conversion.get("canonical_fif_dir"),
                "canonicalProvenancePath": conversion.get("canonical_provenance_path"),
                "canonicalSidecars": conversion.get("canonical_sidecar_paths"),
                "updatedAt": datetime.utcnow().isoformat() + "Z",
            }
        )
        write_manifest(job_dir, manifest)

        return RecordingUploadResponse(
            message=(
                f"已新增 upload-{upload_seq:03d}，并切换为当前工作版本"
                if duplicate
                else "原始文件已归档到 Dataset 存储，canonical FIF 已生成并保留 fifdata 兼容镜像"
            ),
            recording=recording_to_response(dataset),
        )
    except HTTPException as exc:
        db.rollback()
        next_status = "duplicate" if manifest.get("status") == "duplicate" else "failed"
        manifest.update(
            {
                "status": next_status,
                "error": exc.detail,
                "updatedAt": datetime.utcnow().isoformat() + "Z",
            }
        )
        write_manifest(job_dir, manifest)
        raise
    except Exception as exc:
        db.rollback()
        manifest.update({"status": "failed", "error": str(exc), "updatedAt": datetime.utcnow().isoformat() + "Z"})
        write_manifest(job_dir, manifest)
        raise HTTPException(status_code=500, detail=f"数据导入失败: {exc}") from exc
