"""
Purpose: FastAPI sub-router for Study↔Dataset mount endpoints under
/api/v1/studies/{study_id}/datasets — GET/POST /mounts, PATCH/DELETE
/mounts/{mount_id}.
Related: app/routers/_dataset_shared.py, app/schemas/*, docs_v2/2-50.

Split out of the former routers/datasets.py (god-router) — see wiki 9-0x.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Study, User
from app.routers.auth import get_current_user
from app.schemas.dataset import (
    StudyDatasetMountCreate,
    StudyDatasetMountListResponse,
    StudyDatasetMountResponse,
    StudyDatasetMountUpdate,
)
from app.services.audit_events import record_audit_event
from app.services.dataset_assets import (
    DatasetAssetConflictError,
    DatasetMountStateError,
    compute_asset_stats,
    get_dataset_asset_for_user,
    get_study_dataset_mount,
    list_study_dataset_mounts,
    mount_dataset_asset_to_study,
    update_study_dataset_mount,
)
from app.services.study_access import require_study_read, require_study_write
from app.routers._dataset_shared import (
    require_system_permission,
    study_dataset_mount_to_response,
    validate_mount_selection_json,
)

router = APIRouter(prefix="/api/v1/studies/{study_id}/datasets", tags=["datasets"])


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
            # 可见性网关按当前操作者校验授权（而非原始挂载人）
            actor=current_user,
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
