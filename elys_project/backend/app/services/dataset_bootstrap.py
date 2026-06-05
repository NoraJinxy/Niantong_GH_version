"""
Purpose: Bootstrap Dataset-first imports by creating Dataset assets, paired Studies, mounts, and upload context.
Related: app/routers/datasets.py, app/services/studies.py, app/services/dataset_assets.py, docs_v2/2-50.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import DatasetAsset, DatasetVersion, Study, StudyDatasetMount, User
from app.services.audit_events import record_audit_event
from app.services.dataset_assets import (
    create_dataset_asset,
    mount_dataset_asset_to_study,
)
from app.services.studies import create_study


WORKING_DATASET_VERSION_LABEL = "working"


class DatasetBootstrapStorageError(Exception):
    """Raised when Dataset version storage cannot be initialized."""


@dataclass
class DatasetBootstrapNextUploadContext:
    study_id: str
    dataset_asset_id: str
    dataset_version_id: str
    mount_id: str
    mount_name: str
    upload_endpoint: str
    upload_method: str
    form_fields: dict[str, str]


@dataclass
class DatasetBootstrapResult:
    dataset_asset: DatasetAsset
    dataset_version: DatasetVersion
    study: Study
    mount: StudyDatasetMount
    next_upload: DatasetBootstrapNextUploadContext


def _settings(settings_obj=None):
    return settings_obj or get_settings()


def dataset_version_storage_uri(dataset_asset_id, version_label: str = WORKING_DATASET_VERSION_LABEL) -> str:
    return f"elys://datasets/{dataset_asset_id}/versions/{version_label}"


def dataset_version_root(dataset_asset_id, version_label: str = WORKING_DATASET_VERSION_LABEL, settings_obj=None) -> Path:
    return Path(_settings(settings_obj).DATASETS_STORAGE_ROOT) / str(dataset_asset_id) / "versions" / version_label


def ensure_dataset_version_storage(version: DatasetVersion, settings_obj=None) -> None:
    try:
        dataset_version_root(
            version.dataset_asset_id,
            version.version_label,
            settings_obj=settings_obj,
        ).mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DatasetBootstrapStorageError(str(exc)) from exc


def create_working_dataset_version(
    db: Session,
    *,
    dataset_asset: DatasetAsset,
    current_user: User,
    metadata_json: dict[str, Any] | None = None,
    settings_obj=None,
) -> DatasetVersion:
    # Phase 2 (docs_v2/3-25): version_label='working' 保留作物理 label（兼容现有 storage_uri 路径 + 旧代码查找）；
    # state='draft' 表达生命周期；publish 时 owner 输入 SemVer 版本号（DEC-2026-0531-C），届时 rename version_label。
    version = DatasetVersion(
        dataset_asset_id=dataset_asset.id,
        version_label=WORKING_DATASET_VERSION_LABEL,
        status="working",
        state="draft",
        qa_status="not_run",
        storage_uri=dataset_version_storage_uri(dataset_asset.id),
        metadata_json=metadata_json or {"auto_created": True, "source": "dataset_bootstrap"},
        created_by=current_user.id,
    )
    db.add(version)
    db.flush()
    ensure_dataset_version_storage(version, settings_obj=settings_obj)
    return version


def make_next_upload_context(
    *,
    study: Study,
    dataset_asset: DatasetAsset,
    dataset_version: DatasetVersion,
    mount: StudyDatasetMount,
) -> DatasetBootstrapNextUploadContext:
    upload_endpoint = f"/api/v1/studies/{study.id}/recordings/import"
    return DatasetBootstrapNextUploadContext(
        study_id=study.id,
        dataset_asset_id=str(dataset_asset.id),
        dataset_version_id=str(dataset_version.id),
        mount_id=str(mount.id),
        mount_name=mount.mount_name,
        upload_endpoint=upload_endpoint,
        upload_method="POST",
        form_fields={
            "dataset_asset_id": str(dataset_asset.id),
            "mount_name": mount.mount_name,
        },
    )


def bootstrap_dataset(
    db: Session,
    *,
    dataset_name: str,
    dataset_code: str,
    dataset_description: str | None,
    dataset_visibility: str,
    dataset_metadata_json: dict[str, Any] | None,
    paired_study_mode: str,
    current_user: User,
    mount_name: str,
    selection_json: dict[str, Any] | None = None,
    is_active: bool = True,
    paired_study: Study | None = None,
    paired_study_code: str | None = None,
    paired_study_name: str | None = None,
    paired_study_description: str | None = None,
    paired_study_storage_quota_gb: int = 1024,
    settings_obj=None,
    commit: bool = True,
) -> DatasetBootstrapResult:
    import sys
    sys.stderr.write(
        f"[ELYS-TRACE] bootstrap_dataset enter mode={paired_study_mode} dataset_code={dataset_code}\n"
    )
    sys.stderr.flush()
    config = _settings(settings_obj)
    try:
        sys.stderr.write("[ELYS-TRACE] bootstrap_dataset step=create_dataset_asset\n")
        sys.stderr.flush()
        asset = create_dataset_asset(
            db,
            name=dataset_name,
            code=dataset_code,
            description=dataset_description,
            visibility=dataset_visibility,
            metadata_json={
                **(dataset_metadata_json or {}),
                "bootstrap": {
                    "mode": paired_study_mode,
                    "created_by": str(current_user.id),
                },
            },
            owner_id=current_user.id,
            created_by=current_user.id,
        )
        version = create_working_dataset_version(
            db,
            dataset_asset=asset,
            current_user=current_user,
            settings_obj=config,
        )

        if paired_study_mode == "create":
            study_result = create_study(
                db,
                code=paired_study_code or dataset_code,
                name=paired_study_name or dataset_name,
                description=paired_study_description,
                owner=current_user,
                actor=current_user,
                storage_quota_gb=paired_study_storage_quota_gb,
                settings_obj=config,
                commit=False,
                audit_action="study.created",
            )
            study = study_result.study
        else:
            if paired_study is None:
                raise ValueError("paired_study is required when paired_study_mode='existing'")
            study = paired_study

        # Phase 2 (docs_v2/3-25): 必须早于 mount 创建!
        #   Phase 3-4 mount 校验 _ensure_version_mountable 要求 draft 版本只能挂到
        #   asset.primary_study_id 对应的 Study, 因此先把归属字段写好, 再让 mount 走校验
        #   - primary_study_id: 主 Study（DEC-2026-0531-B），draft 必填，published 后保留作出身记录
        #   - current_version_id: 默认展示版本指针，draft 阶段先指向 working 版本
        asset.primary_study_id = study.id
        asset.current_version_id = version.id
        db.flush()

        mount = mount_dataset_asset_to_study(
            db,
            study=study,
            dataset_asset=asset,
            mount_name=mount_name,
            mounted_by=current_user.id,
            selection_json=selection_json or {},
            is_active=is_active,
            # Phase 2 (docs_v2/3-25): 挂载锁定到刚创建的 working 版本
            dataset_version_id=version.id,
        )

        asset.metadata_json = {
            **(asset.metadata_json or {}),
            "paired_study": {
                "mode": paired_study_mode,
                "study_id": study.id,
                "mount_id": str(mount.id),
                "mount_name": mount.mount_name,
            },
        }
        db.flush()

        audit_metadata = {
            "dataset_asset_id": str(asset.id),
            "dataset_asset_code": asset.code,
            "dataset_version_id": str(version.id),
            "version_label": version.version_label,
            "study_id": study.id,
            "mount_id": str(mount.id),
            "mount_name": mount.mount_name,
            "paired_study_mode": paired_study_mode,
        }
        record_audit_event(
            db,
            action="dataset_asset.created",
            actor_id=current_user.id,
            event_scope="dataset_asset",
            resource_kind="dataset_asset",
            resource_id=asset.id,
            resource_label=asset.name,
            metadata={
                "code": asset.code,
                "visibility": asset.visibility,
                "status": asset.status,
                "source": "dataset_bootstrap",
                "study_id": study.id,
                "mount_name": mount.mount_name,
            },
        )
        record_audit_event(
            db,
            action="dataset_version.created",
            actor_id=current_user.id,
            event_scope="dataset_asset",
            resource_kind="dataset_version",
            resource_id=version.id,
            resource_label=version.version_label,
            metadata=audit_metadata,
        )
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
                "source": "dataset_bootstrap",
            },
        )
        record_audit_event(
            db,
            study_id=study.id,
            action="dataset.bootstrap.completed",
            actor_id=current_user.id,
            event_scope="dataset_asset",
            resource_kind="dataset_asset",
            resource_id=asset.id,
            resource_label=asset.name,
            metadata=audit_metadata,
            occurred_at=datetime.utcnow(),
        )

        next_upload = make_next_upload_context(
            study=study,
            dataset_asset=asset,
            dataset_version=version,
            mount=mount,
        )

        if commit:
            db.commit()
            for item in (asset, version, study, mount):
                db.refresh(item)
        return DatasetBootstrapResult(
            dataset_asset=asset,
            dataset_version=version,
            study=study,
            mount=mount,
            next_upload=next_upload,
        )
    except Exception:
        if commit:
            db.rollback()
        raise
