"""
Purpose: FastAPI sub-router for Dataset Asset endpoints under
/api/v1/dataset-assets — bootstrap / list / versions (list + create) / files /
bids-tree / canonical-fif-rebuild / patch / open-visibility / members (list, add,
remove) / delete. Plus asset-only helpers (owner/uploadable guards, published-
version predicates, member response, all-versions visibility gate).
Related: app/routers/_dataset_shared.py, app/schemas/*, docs_v2/2-50.

Split out of the former routers/datasets.py (god-router) — see wiki 9-0x.
"""

from datetime import datetime
from pathlib import Path
import shutil
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import (
    DatasetFile,
    DatasetVersion,
    DatasetVersionReference,
    Recording,
    Study,
    StudyDatasetMount,
    User,
)
from app.routers.auth import get_current_user
from app.schemas.dataset import (
    DatasetBootstrapNextUpload,
    DatasetBootstrapRequest,
    DatasetBootstrapResponse,
    DatasetAssetListResponse,
    DatasetAssetResponse,
    DatasetAssetTaskRequest,
    DatasetAssetUpdate,
    DatasetFileListResponse,
    DatasetFileTreeResponse,
    DatasetVersionListResponse,
    DatasetVersionResponse,
)
from app.schemas.dataset_lifecycle import (
    DatasetMemberAddRequest,
    DatasetMemberListResponse,
    DatasetMemberResponse,
    OpenVisibilityRequest,
)
from app.schemas.pipeline import AsyncTaskResponse
from app.services.audit_events import record_audit_event
from app.services.dataset_assets import (
    DatasetAssetConflictError,
    can_write_dataset_asset,
    compute_asset_stats,
    get_dataset_asset_for_user,
    grant_member,
    list_members,
    list_visible_dataset_assets,
    revoke_member,
)
from app.services.dataset_bootstrap import (
    DatasetBootstrapStorageError,
    bootstrap_dataset,
)
from app.services.study_access import require_study_write
from app.services.studies import (
    StudyCreateCodeConflictError,
    StudyCreateIntegrityError,
    StudyStorageSetupError,
    ensure_study_create_permission,
)
from app.routers._dataset_shared import (
    require_system_permission,
    dataset_asset_to_response,
    dataset_version_to_response,
    study_to_response,
    study_dataset_mount_to_response,
    dataset_file_to_response,
    create_and_dispatch_file_task,
    validate_mount_selection_json,
    ensure_dataset_asset_owner,
    asset_has_published_version,
    asset_has_published_or_withdrawn_version,
    dataset_member_to_response,
    restrict_dataset_files_to_published,
    VISIBILITY_RANK,
)
from app.services.file_browser import build_dataset_file_tree

settings = get_settings()

asset_router = APIRouter(prefix="/api/v1/dataset-assets", tags=["dataset-assets"])


@asset_router.post("/bootstrap", response_model=DatasetBootstrapResponse, status_code=status.HTTP_201_CREATED)
def bootstrap_dataset_asset(
    payload: DatasetBootstrapRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
def create_new_version_endpoint(
    asset_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """在已发布过版本的 Asset 上新建未发布版本（v+1 前向演进）。

    与 bootstrap 不同: bootstrap 用于首次创建 Asset, 此端点是负责人在已发布基础上推 v+1。
    新版本的 version_label='working' (storage slot 已被上次 publish rename 释放)。
    """
    from app.services.dataset_bootstrap import ensure_dataset_version_storage
    from app.services.dataset_lifecycle import (
        DatasetLifecyclePermissionError,
        DatasetLifecycleStateError,
        DatasetLifecycleValidationError,
        create_new_version as create_draft_service,
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
    # 规则 12 / 清单 R7：非主研究项访问者只见已发布版本的文件（堵草稿外泄）
    query = restrict_dataset_files_to_published(query, asset=asset, db=db, current_user=current_user)
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
    prefix: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 两层重构：raw_bids 视图下线，prefix 缺省 None = 展示全部逻辑路径（BIDSdata/ + sourcedata/）。
    require_system_permission(current_user, "data:read", "当前用户没有查看数据集文件树权限")
    asset = get_dataset_asset_for_user(db, asset_id=asset_id, user=current_user)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset 资产不存在或无权访问")
    query = (
        db.query(DatasetFile)
        .join(Recording, DatasetFile.recording_id == Recording.id)
        .filter(Recording.dataset_asset_id == asset.id)
    )
    # 规则 12 / 清单 R7：非主研究项访问者只见已发布版本的文件（堵草稿外泄）
    query = restrict_dataset_files_to_published(query, asset=asset, db=db, current_user=current_user)
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
    if not can_write_dataset_asset(current_user, asset):
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
    # 改名 / 描述 = 负责人 + 管理员（管理员作平台兜底，可改错别字 / 接管离职负责人；
    # 综合报告 §D / 清单 R2）。不含创建者。可见范围不在此端点处理（见 open-visibility）。
    if not (current_user.has_role("admin") or asset.owner_id == current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权修改该 Dataset 资产")

    fields_set = payload.model_fields_set
    old_status = asset.status
    if "name" in fields_set and payload.name is not None:
        asset.name = payload.name
    if "description" in fields_set:
        asset.description = payload.description
    if "status" in fields_set and payload.status is not None:
        # 通用 PATCH 只允许管理员在「隔离 / 解除隔离」之间切换，堵掉用 status='deleted'/'archived'
        # 把已发布资产硬隐藏、绕过 DELETE 端点「已发布历史→409」守卫的后门（清单 R？/ 综合报告 §D）。
        # 删除一律走 DELETE /dataset-assets/{id}；归档等其它语义未开放。
        if not current_user.has_role("admin"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有管理员可以修改 Dataset 资产状态")
        if payload.status not in ("quarantined", "working"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="status 仅支持 'quarantined'（隔离）或 'working'（解除隔离）；删除请走 DELETE /dataset-assets/{id} 端点",
            )
        asset.status = payload.status
    # 可见范围（visibility）已移出通用 PATCH——只升不降，走专门的 open-visibility 端点
    # （堵降级口子；综合报告 §E/§I、规则 5、清单 R1）。
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
        },
    )
    db.commit()
    db.refresh(asset)
    return dataset_asset_to_response(asset)


@asset_router.post("/{asset_id}/open-visibility", response_model=DatasetAssetResponse)
def open_dataset_asset_visibility(
    asset_id: uuid.UUID,
    payload: OpenVisibilityRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """负责人显式开放可见范围（只升不降，无降级接口；综合报告 §E/§I、规则 5、清单 R3）。

    约束：仅负责人；target ∈ {shared, public} 且严格高于当前可见范围（可跳级 private→public，禁降级）；
    资产须已有 ≥1 个已发布版本（纯未发布资产恒私有，无可分享内容；规则 J）。
    """
    require_system_permission(current_user, "data:write", "当前用户没有修改 Dataset 资产权限")
    asset = get_dataset_asset_for_user(db, asset_id=asset_id, user=current_user)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset 资产不存在或无权访问")
    ensure_dataset_asset_owner(asset, current_user)

    # 转公开（public）= 全网曝光，需先审后开（2026-06-10 Q1）：不在本端点直接升，引导走申请端点。
    # 本端点只处理自助的 private → shared（邀请制协作，不算全网曝光）。
    if payload.target == "public":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="转公开（public）需经审核：请改用 POST /dataset-assets/{asset_id}/publicize-request 申请（调试期自动通过）",
        )

    current_rank = VISIBILITY_RANK.get(asset.visibility, 0)
    target_rank = VISIBILITY_RANK[payload.target]
    if target_rank <= current_rank:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"可见范围只升不降：当前为「{asset.visibility}」，不能开放为「{payload.target}」。"
                "如需可撤销的协作，请保持私有并把人加入主研究项团队"
            ),
        )
    if not asset_has_published_version(db, asset):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="资产尚无已发布版本，无可分享内容；请先发布至少一个版本再开放可见范围",
        )

    old_visibility = asset.visibility
    asset.visibility = payload.target
    asset.updated_at = datetime.utcnow()
    record_audit_event(
        db,
        action="dataset_asset.visibility_opened",
        actor_id=current_user.id,
        event_scope="dataset_asset",
        resource_kind="dataset_asset",
        resource_id=asset.id,
        resource_label=asset.name,
        metadata={"old_visibility": old_visibility, "new_visibility": asset.visibility},
    )
    db.commit()
    db.refresh(asset)
    return dataset_asset_to_response(asset)


@asset_router.get("/{asset_id}/members", response_model=DatasetMemberListResponse)
def list_dataset_asset_members(
    asset_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出共享授权名单（dataset_members，邀请制；规则 7、清单 R4）。仅负责人可见。"""
    require_system_permission(current_user, "data:read", "当前用户没有查看 Dataset 资产权限")
    asset = get_dataset_asset_for_user(db, asset_id=asset_id, user=current_user)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset 资产不存在或无权访问")
    ensure_dataset_asset_owner(asset, current_user)

    members = list_members(db, asset=asset)
    # 批量取用户，避免 N+1（授权面板要展示用户名 / 全名）
    user_ids = [m.user_id for m in members]
    users_by_id = {
        u.id: u
        for u in (db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else [])
    }
    return DatasetMemberListResponse(
        members=[
            dataset_member_to_response(m, user_obj=users_by_id.get(m.user_id))
            for m in members
        ],
    )


@asset_router.post(
    "/{asset_id}/members",
    response_model=DatasetMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_dataset_asset_member(
    asset_id: uuid.UUID,
    payload: DatasetMemberAddRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """授权一个用户访问该数据集（shared 邀请制；规则 7、清单 R4）。仅负责人。幂等。"""
    require_system_permission(current_user, "data:write", "当前用户没有修改 Dataset 资产权限")
    asset = get_dataset_asset_for_user(db, asset_id=asset_id, user=current_user)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset 资产不存在或无权访问")
    ensure_dataset_asset_owner(asset, current_user)

    # 解析 user_identifier：先当 UUID（按 User.id 查），否则按 User.username 查
    # （普通用户填不出 UUID，故支持按用户名授权；User 模型无 email 字段）。
    identifier = payload.user_identifier.strip()
    target_user = None
    try:
        parsed_uuid = uuid.UUID(identifier)
    except (ValueError, AttributeError, TypeError):
        parsed_uuid = None
    if parsed_uuid is not None:
        target_user = db.query(User).filter(User.id == parsed_uuid).first()
    if target_user is None:
        target_user = db.query(User).filter(User.username == identifier).first()
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到该用户（可填用户名 / 用户 ID）",
        )

    member = grant_member(db, asset=asset, user_id=target_user.id, granted_by=current_user.id)
    record_audit_event(
        db,
        action="dataset_asset.member_granted",
        actor_id=current_user.id,
        event_scope="dataset_asset",
        resource_kind="dataset_asset",
        resource_id=asset.id,
        resource_label=asset.name,
        metadata={"user_id": str(target_user.id)},
    )
    db.commit()
    db.refresh(member)
    return dataset_member_to_response(member, user_obj=target_user)


@asset_router.delete("/{asset_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_dataset_asset_member(
    asset_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """取消某用户对该数据集的授权（规则 7、清单 R4）。仅负责人。"""
    require_system_permission(current_user, "data:write", "当前用户没有修改 Dataset 资产权限")
    asset = get_dataset_asset_for_user(db, asset_id=asset_id, user=current_user)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset 资产不存在或无权访问")
    ensure_dataset_asset_owner(asset, current_user)

    removed = revoke_member(db, asset=asset, user_id=user_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该用户未被授权，无需取消")
    record_audit_event(
        db,
        action="dataset_asset.member_revoked",
        actor_id=current_user.id,
        event_scope="dataset_asset",
        resource_kind="dataset_asset",
        resource_id=asset.id,
        resource_label=asset.name,
        metadata={"user_id": str(user_id)},
    )
    db.commit()
    return None


@asset_router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset_asset(
    asset_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """整体真删除纯未发布资产（行 + 物理文件；仅负责人；规则 4、清单 R5）。

    守卫：资产存在任何已发布 / 撤回审核中 / 已撤回版本 → 409（已发布历史不可删，只能撤回）。
    仅「无任何已发布/撤回历史」的纯未发布资产可整体删。删除是真删除：先按外键顺序清掉
    RESTRICT 拦路项（挂载、采集记录），再删资产行（versions / members 等 CASCADE 自动清），
    最后 best-effort 清物理存储目录。审计事件用 snapshot 留痕（行已删，无法事后回查）。
    """
    require_system_permission(current_user, "data:write", "当前用户没有删除 Dataset 资产权限")
    asset = get_dataset_asset_for_user(db, asset_id=asset_id, user=current_user)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset 资产不存在或无权访问")
    ensure_dataset_asset_owner(asset, current_user)

    if asset_has_published_or_withdrawn_version(db, asset):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="资产存在已发布 / 撤回审核中 / 已撤回版本，不能整体删除；已发布历史只能撤回",
        )

    # 行已删后无法事后回查，先取 snapshot 供审计留痕。
    asset_code = asset.code
    asset_name = asset.name

    # 1) 先删该资产的挂载（study_dataset_mounts 对 asset_id / version_id 均 ON DELETE RESTRICT，
    #    不先删会 IntegrityError）。每个 mount 先删其 mount 类版本引用，再删 mount 本身。
    mounts = (
        db.query(StudyDatasetMount)
        .filter(StudyDatasetMount.dataset_asset_id == asset.id)
        .all()
    )
    for mount in mounts:
        db.query(DatasetVersionReference).filter(
            DatasetVersionReference.reference_kind == "mount",
            DatasetVersionReference.reference_id == mount.id,
        ).delete(synchronize_session=False)
        db.delete(mount)

    # 2) 再删采集记录（recordings 对 asset 是 RESTRICT；删 recordings 会级联清掉
    #    recording_versions / dataset_files —— 二者对 recording 是 CASCADE）。
    recordings = (
        db.query(Recording)
        .filter(Recording.dataset_asset_id == asset.id)
        .all()
    )
    for recording in recordings:
        db.delete(recording)

    # 3) 断开自引用外键（current_version_id → dataset_versions），避免删版本时被阻塞。
    asset.current_version_id = None
    db.flush()

    # 4) 删资产行：dataset_versions / dataset_members 对 asset 是 CASCADE 自动删；
    #    versions 的 version_references / withdrawal_requests 也 CASCADE。
    db.delete(asset)

    record_audit_event(
        db,
        action="dataset_asset.deleted",
        actor_id=current_user.id,
        event_scope="dataset_asset",
        resource_kind="dataset_asset",
        resource_id=asset_id,
        resource_label=asset_name,
        metadata={"code": asset_code, "name": asset_name, "hard_deleted": True},
    )
    db.commit()

    # 6) best-effort 清物理存储：资产存储根 = DATASETS_STORAGE_ROOT / {asset_id}
    #    两层重构后该根下直接是 sourcedata/、BIDSdata/、ver{label}/，整根删即清掉全部版本物理文件。
    #    清理失败不回滚已提交的删除。
    try:
        storage_root = Path(settings.DATASETS_STORAGE_ROOT) / str(asset_id)
        shutil.rmtree(storage_root, ignore_errors=True)
    except Exception:
        pass

    return None
