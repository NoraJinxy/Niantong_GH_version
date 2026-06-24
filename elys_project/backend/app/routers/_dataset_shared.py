"""
Purpose: Cross-area shared layer for the datasets router family — module constants,
the UploadItem NamedTuple, and every helper used by 2+ of the split sub-routers
(response converters, permission/404 guards, file-access helpers, mount/asset
resolvers, BIDS-label normaliser).
Related: app/routers/dataset_assets.py, dataset_recordings.py, dataset_mounts.py,
dataset_files.py, dataset_imports.py, docs_v2/2-50.

Split out of the former routers/datasets.py (god-router) — see wiki 9-0x.
"""

import uuid
from typing import Any, NamedTuple

from fastapi import HTTPException, UploadFile, status
from pathlib import Path
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.models import (
    DatasetAsset,
    DatasetFile,
    DatasetVersion,
    Study,
    Recording,
    RecordingVersion,
    StudyDatasetMount,
    StudyMember,
    User,
)
from app.schemas.dataset import (
    DatasetAssetResponse,
    DatasetFileMetadataResponse,
    DatasetFilePreviewResponse,
    DatasetFileResponse,
    DatasetVersionResponse,
    RecordingResponse,
    RecordingVersionResponse,
    StudyDatasetMountResponse,
)
from app.schemas.dataset_lifecycle import DatasetMemberResponse
from app.schemas.pipeline import AsyncTaskResponse
from app.schemas.study import StudyResponse
from app.services.dataset_assets import (
    DatasetAssetConflictError,
    can_write_dataset_asset,
    get_active_study_dataset_mount_for_asset,
    get_dataset_asset_for_user,
    get_or_create_working_dataset_asset,
    get_study_dataset_mount,
    get_study_dataset_mount_by_name,
    list_study_dataset_mounts,
)
from app.services.study_access import require_study_read
from app.services.file_browser import (
    FileAccessError,
    dataset_file_metadata,
    dataset_file_preview,
)

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
# 2026-06-10 两层目录重构：canonical FIF 物理落 BIDSdata/sub-/ses-/eeg/（working）或 ver{label}/...（发布），
# 取代旧 derivatives/elys-canonical-fif/sub/ses/task/run/upload-NNN/。URI/目录不再含 versions/{label} 段。
# raw_bids 不再是目录概念，降为纯逻辑索引（BIDS 实体映射查 recordings 表，原始文件位置查 original_upload 行）。
DATASET_CANONICAL_FIF_PREFIX = "BIDSdata"


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
        "recording_count": 0,
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
        recording_count=s.get("recording_count", 0),
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
        # 发布状态轴（旧 status 列已删，state 为唯一状态来源）
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
        # 规则 12 / 清单 R7：非「全部版本可见者」（admin / owner / 创建者 / 主研究项成员之外的、
        # 经可见范围放行者）只能读已发布版本的文件，未发布 / 撤回审核中 / 已撤回（或无版本归属）
        # 的文件对其一律 404，堵草稿外泄。
        if not _can_see_all_versions(db, asset=asset, user=current_user):
            version = getattr(file_record, "dataset_version", None)
            if version is None or version.state != "published":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Dataset file 不存在或无权访问"
                )
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
    from app.services.task_events import record_task_event
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


# 可见范围开放度（私有 < 共享 < 公开）—— 只升不降，open-visibility 端点据此判 target > current。


VISIBILITY_RANK = {"private": 0, "shared": 1, "public": 2}


def ensure_dataset_asset_owner(asset: DatasetAsset, current_user: User) -> None:
    """开放可见范围 / 授权管理 / 删除 = 仅负责人（不含创建者、不含管理员；综合报告 §D/§E/规则9）。"""
    if asset.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅数据集负责人可执行此操作")


def asset_has_published_version(db: Session, asset: DatasetAsset) -> bool:
    """该资产是否已有 ≥1 个已发布版本（open-visibility 的前置：纯未发布资产无可分享内容）。"""
    return (
        db.query(DatasetVersion.id)
        .filter(
            DatasetVersion.dataset_asset_id == asset.id,
            DatasetVersion.state == "published",
        )
        .first()
        is not None
    )


def asset_has_published_or_withdrawn_version(db: Session, asset: DatasetAsset) -> bool:
    """该资产是否存在任何已发布 / 已撤回历史（整体删除的禁区：只有纯未发布资产可整体删）。

    撤回审核中（withdraw_requested）也属「不可整体删」：那是从 published 出发的进行中流程，
    必须先走完审核，不能绕过历史直接抹掉资产。
    """
    return (
        db.query(DatasetVersion.id)
        .filter(
            DatasetVersion.dataset_asset_id == asset.id,
            DatasetVersion.state.in_(("published", "withdraw_requested", "withdrawn")),
        )
        .first()
        is not None
    )


def dataset_member_to_response(member, *, user_obj: User | None = None) -> DatasetMemberResponse:
    """把 DatasetMember ORM 转响应；user_obj 给定时带上用户名 / 全名（授权面板展示用）。"""
    member_user = user_obj if user_obj is not None else getattr(member, "user", None)
    return DatasetMemberResponse(
        id=str(member.id),
        asset_id=str(member.asset_id),
        user_id=str(member.user_id),
        username=getattr(member_user, "username", None) if member_user else None,
        full_name=getattr(member_user, "full_name", None) if member_user else None,
        granted_by=str(member.granted_by) if member.granted_by else None,
        granted_at=member.granted_at,
    )


def is_asset_primary_study_member(db: Session, *, asset: DatasetAsset, user: User) -> bool:
    """user 是否为该资产「主研究项」的成员（含负责人）。

    与 dataset_assets._is_primary_study_member 同口径，用于文件读链的「仅暴露已发布版本」过滤
    （规则 12、清单 R7）：主研究项成员看全部版本文件，其他访问者（含 admin 经可见范围放行的）
    只能看 state=='published' 版本的文件。
    """
    study_id = asset.primary_study_id
    if study_id is None:
        return False
    owner_id = db.query(Study.owner_id).filter(Study.id == study_id).scalar()
    if owner_id is not None and owner_id == user.id:
        return True
    return (
        db.query(StudyMember.id)
        .filter(
            StudyMember.study_id == study_id,
            StudyMember.user_id == user.id,
            StudyMember.can_read.is_(True),
        )
        .first()
        is not None
    )


def _can_see_all_versions(db: Session, *, asset: DatasetAsset, user: User) -> bool:
    """user 是否有资格看该资产的「全部版本」（含未发布 / 撤回审核中 / 已撤回）文件。

    放行范围：admin（平台兜底）/ 资产 owner（负责人）/ 创建者 / 主研究项成员。
    主研究项在被删（primary_study SET NULL）后负责人不再是「主研究项成员」，故必须显式
    把 admin / owner / 创建者并进来，否则他们读未发布文件会被错误地挡成 404 / 列表空
    （清单 R7、规则 12）。其余可见范围放行进来的访问者仍只能见 state=='published' 版本。
    """
    return (
        user.has_role("admin")
        or asset.owner_id == user.id
        or asset.created_by == user.id
        or is_asset_primary_study_member(db, asset=asset, user=user)
    )


def restrict_dataset_files_to_published(query, *, asset: DatasetAsset, db: Session, current_user: User):
    """对「非全部版本可见者」把文件查询收窄到 state=='published' 的版本（规则 12、清单 R7）。

    可见全部版本者（admin / owner / 创建者 / 主研究项成员，见 _can_see_all_versions）不受限；
    其余可见范围放行进来的访问者只能见已发布版本，避免未发布草稿 / 撤回审核中 / 已撤回内容
    经文件列举 / 树 / 下载外泄。

    用 dataset_version_id ∈ (该资产已发布版本子查询) 过滤，而非 join——避免与端点里
    version_label 的 DatasetVersion join 冲突；NULL version 的文件对非成员一律不暴露。
    """
    if _can_see_all_versions(db, asset=asset, user=current_user):
        return query
    published_version_ids = (
        db.query(DatasetVersion.id)
        .filter(
            DatasetVersion.dataset_asset_id == asset.id,
            DatasetVersion.state == "published",
        )
        .subquery()
    )
    return query.filter(DatasetFile.dataset_version_id.in_(published_version_ids))


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
