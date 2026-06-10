"""
Purpose: Define FastAPI routes for the dataset_versions API area (publish / discard draft / withdraw / emergency takedown).
Related: app/services/dataset_lifecycle.py, app/schemas/dataset_lifecycle.py, docs_v2/3-25.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import (
    DatasetAsset,
    DatasetVersion,
    DatasetVersionReference,
    DatasetWithdrawalRequest,
    StudyDatasetMount,
    User,
)
from app.routers.auth import get_current_user
from app.schemas.dataset_lifecycle import (
    DatasetVersionPublishRequest,
    DatasetVersionPublishResponse,
    DatasetVersionResponse,
    DatasetVersionWithdrawRequest,
    DatasetWithdrawalRequestResponse,
    EmergencyTakedownRequest,
    WithdrawalReviewRequest,
)
from app.services.audit_events import record_audit_event
from app.services.dataset_lifecycle import (
    DatasetLifecyclePermissionError,
    DatasetLifecycleStateError,
    DatasetLifecycleValidationError,
    emergency_takedown_version,
    publish_dataset_version,
    request_version_withdrawal,
    review_withdrawal_request,
)


router = APIRouter(prefix="/api/v1/dataset-versions", tags=["dataset-versions"])
admin_router = APIRouter(prefix="/api/v1/dataset-withdrawals", tags=["dataset-withdrawals"])


# ============================================
# Helpers
# ============================================


def _to_version_response(version: DatasetVersion) -> DatasetVersionResponse:
    return DatasetVersionResponse(
        id=str(version.id),
        dataset_asset_id=str(version.dataset_asset_id),
        version_label=version.version_label,
        state=version.state,
        qa_status=version.qa_status,
        content_hash=version.content_hash,
        version_doi=version.version_doi,
        storage_uri=version.storage_uri,
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
        created_at=version.created_at,
        created_by=str(version.created_by) if version.created_by else None,
    )


def _to_withdrawal_response(req: DatasetWithdrawalRequest) -> DatasetWithdrawalRequestResponse:
    return DatasetWithdrawalRequestResponse(
        id=str(req.id),
        dataset_version_id=str(req.dataset_version_id),
        requested_by=str(req.requested_by),
        requested_at=req.requested_at,
        reason=req.reason,
        reviewed_by=str(req.reviewed_by) if req.reviewed_by else None,
        reviewed_at=req.reviewed_at,
        decision=req.decision,
        admin_notes=req.admin_notes,
        notification_sent_at=req.notification_sent_at,
    )


def _get_version_or_404(db: Session, version_id: UUID) -> DatasetVersion:
    version = db.query(DatasetVersion).filter(DatasetVersion.id == version_id).first()
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据集版本不存在")
    return version


def _get_withdrawal_or_404(db: Session, request_id: UUID) -> DatasetWithdrawalRequest:
    req = (
        db.query(DatasetWithdrawalRequest)
        .filter(DatasetWithdrawalRequest.id == request_id)
        .first()
    )
    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="撤回申请不存在")
    return req


def _translate_lifecycle_error(exc: Exception) -> HTTPException:
    """把 service 层抛的异常统一翻译为 HTTPException。"""
    if isinstance(exc, DatasetLifecyclePermissionError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, DatasetLifecycleStateError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, DatasetLifecycleValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


# ============================================
# Publish
# ============================================


@router.post(
    "/{version_id}/publish",
    response_model=DatasetVersionPublishResponse,
    status_code=status.HTTP_200_OK,
)
def publish_version(
    version_id: UUID,
    payload: DatasetVersionPublishRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    version = _get_version_or_404(db, version_id)
    try:
        result = publish_dataset_version(
            db,
            version=version,
            new_version_label=payload.version_label,
            actor=current_user,
            # 合规关口（规则3 / 决策4）：每次发布都透传脱敏确认 + 伦理 + 版权声明，
            # 缺 / 未确认由 service 抛 ValidationError → 422。
            deidentified_confirmed=payload.deidentified_confirmed,
            ethics_statement=payload.ethics_statement,
            license_statement=payload.license_statement,
            commit=True,
        )
    except (
        DatasetLifecyclePermissionError,
        DatasetLifecycleStateError,
        DatasetLifecycleValidationError,
    ) as exc:
        raise _translate_lifecycle_error(exc) from exc

    return DatasetVersionPublishResponse(
        dataset_version=_to_version_response(result.dataset_version),
        previous_version_label=result.previous_version_label,
        is_first_published_version=result.is_first_published_version,
        concept_doi=result.dataset_asset.concept_doi,
    )


# ============================================
# Discard draft version（丢弃已发布资产上的 v+1 未发布版本，规则4）
# ============================================
#
# 守卫在本路由内自实现（service 层无对应函数）。语义边界（综合报告 §1.5 / 规则4）：
#   - 仅负责人（owner_id == 当前用户）；非 owner → 403。
#   - 仅当该版本 state=='unpublished' 才可丢弃；published / withdraw_requested（撤回审核中）
#     / withdrawn（已撤回）一律 409（已发布历史不可删、只能撤回）。
#   - 仅针对「已发布资产上的 v+1 草稿」：要求该资产已有 ≥1 个 published/withdrawn 版本，
#     即这是前向演进开出的新草稿。纯未发布资产（从未发布过）的初始草稿不走这里——
#     那种应走整体删除 DELETE /dataset-assets/{id}，本端点对其返回 409。
#   - 删除版本行 + 顺手清掉它的 working 物理存储目录（与新建草稿 ensure storage 对称）。
#
# 不可变发布与引用完整性不受影响：草稿从未发布，不可能被其他研究项引用；且
# dataset_version_references.dataset_version_id 为 ON DELETE CASCADE，DB 层兜底。


@router.delete("/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
def discard_draft_version(
    version_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    version = _get_version_or_404(db, version_id)

    asset = version.dataset_asset
    if asset is None:
        asset = (
            db.query(DatasetAsset)
            .filter(DatasetAsset.id == version.dataset_asset_id)
            .first()
        )
    if asset is None:
        # 数据不一致：版本挂的资产已不存在。当 404 处理（无可操作对象）。
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据集版本对应的资产不存在")

    # 仅负责人（与 _ensure_asset_owner 同口径：不含创建者 / 管理员）。
    if asset.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅数据集负责人可丢弃未发布版本")

    # 只有未发布草稿可丢弃；已发布 / 撤回审核中 / 已撤回一律 409。
    if version.state != "unpublished":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"只有未发布版本可丢弃，当前状态: {version.state}（已发布版本只能撤回，不能删除）",
        )

    # 本端点专丢「v+1」：资产须已有 ≥1 个 published/withdrawn 版本，证明这是前向演进草稿。
    # 纯未发布资产的初始草稿不在此处删（应整体删资产），返回 409 引导到资产级删除。
    has_published_history = (
        db.query(DatasetVersion.id)
        .filter(
            DatasetVersion.dataset_asset_id == asset.id,
            DatasetVersion.state.in_(("published", "withdrawn")),
        )
        .first()
        is not None
    )
    if not has_published_history:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该资产从未发布过版本，请整体删除数据集（DELETE /dataset-assets/{id}）而非丢弃单个版本",
        )

    # 防御性：若资产 current_version 指针恰好落在这个草稿上，先摘掉，避免 SET NULL 期窗。
    if asset.current_version_id == version.id:
        asset.current_version_id = None
        db.flush()

    discarded_label = version.version_label
    storage_asset_id = version.dataset_asset_id

    # study_dataset_mounts.dataset_version_id 是 ON DELETE RESTRICT：若有主研究项把这个未发布草稿
    # 挂了调试用，直接 db.delete(version) 会撞 IntegrityError → 500。丢弃草稿时一并清掉指向它的
    # 挂载（草稿挂载本就是主研究项调试用，随草稿一起丢弃合理），再删版本。
    # 同时删掉这些挂载登记的 DatasetVersionReference(kind='mount')；版本自身的引用走 DB 层 CASCADE。
    cleared_mounts = (
        db.query(StudyDatasetMount)
        .filter(StudyDatasetMount.dataset_version_id == version.id)
        .all()
    )
    cleared_mount_count = len(cleared_mounts)
    for _mount in cleared_mounts:
        db.query(DatasetVersionReference).filter(
            DatasetVersionReference.reference_kind == "mount",
            DatasetVersionReference.reference_id == _mount.id,
        ).delete(synchronize_session=False)
        db.delete(_mount)
    if cleared_mount_count:
        db.flush()

    record_audit_event(
        db,
        action="dataset_version.discarded",
        actor_id=current_user.id,
        event_scope="dataset_asset",
        resource_kind="dataset_version",
        resource_id=version.id,
        resource_label=discarded_label,
        # 硬删事件：用 snapshot 留痕，避免行删除后审计无据可查。
        snapshot={
            "dataset_asset_id": str(asset.id),
            "dataset_asset_code": asset.code,
            "version_label": discarded_label,
            "state": version.state,
            "storage_uri": version.storage_uri,
        },
        metadata={
            "dataset_asset_id": str(asset.id),
            "trigger": "discard_v_plus_1_draft",
            # 随草稿一并清掉的主研究项调试挂载数（含其 mount 引用登记）。
            "cleared_mount_count": cleared_mount_count,
        },
    )

    db.delete(version)
    db.commit()

    # 行已删干净后再清物理目录（working slot）。清理失败不回滚已提交的删除——
    # 残留空目录无害，且下次新建草稿 mkdir(exist_ok=True) 会复用。
    try:
        from app.services.dataset_bootstrap import dataset_version_root

        root = dataset_version_root(storage_asset_id, discarded_label, settings_obj=get_settings())
        if root.exists():
            import shutil

            shutil.rmtree(root, ignore_errors=True)
    except Exception:
        # 存储清理是尽力而为，不影响 DB 层丢弃结果。
        pass

    return None


# ============================================
# Withdrawal request (owner)
# ============================================


@router.post(
    "/{version_id}/withdraw-request",
    response_model=DatasetWithdrawalRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def request_withdrawal(
    version_id: UUID,
    payload: DatasetVersionWithdrawRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    version = _get_version_or_404(db, version_id)
    try:
        req = request_version_withdrawal(
            db,
            version=version,
            reason=payload.reason,
            actor=current_user,
            commit=True,
        )
    except (
        DatasetLifecyclePermissionError,
        DatasetLifecycleStateError,
        DatasetLifecycleValidationError,
    ) as exc:
        raise _translate_lifecycle_error(exc) from exc
    return _to_withdrawal_response(req)


# ============================================
# Emergency takedown (管理员 / admin)
# ============================================
# 紧急下架 = 管理员校验（2026-06-09 决策A / 规则9，非 superadmin）。校验在 service 层
# emergency_takedown_version → _ensure_admin(actor) 完成，路由签名无需带角色参数。


@router.post(
    "/{version_id}/emergency-takedown",
    response_model=DatasetWithdrawalRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def emergency_takedown(
    version_id: UUID,
    payload: EmergencyTakedownRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    version = _get_version_or_404(db, version_id)
    try:
        req = emergency_takedown_version(
            db,
            version=version,
            reason=payload.reason,
            actor=current_user,
            commit=True,
        )
    except (
        DatasetLifecyclePermissionError,
        DatasetLifecycleStateError,
        DatasetLifecycleValidationError,
    ) as exc:
        raise _translate_lifecycle_error(exc) from exc
    return _to_withdrawal_response(req)


# ============================================
# Admin: list pending withdrawals + review
# ============================================


@admin_router.get("/pending", response_model=list[DatasetWithdrawalRequestResponse])
def list_pending_withdrawals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.has_role("admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅平台管理员可查看待审核撤回申请")
    pending = (
        db.query(DatasetWithdrawalRequest)
        .filter(DatasetWithdrawalRequest.decision.is_(None))
        .order_by(DatasetWithdrawalRequest.requested_at.desc())
        .all()
    )
    return [_to_withdrawal_response(item) for item in pending]


@admin_router.post(
    "/{request_id}/review",
    response_model=DatasetWithdrawalRequestResponse,
)
def review_withdrawal(
    request_id: UUID,
    payload: WithdrawalReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    req = _get_withdrawal_or_404(db, request_id)
    try:
        updated = review_withdrawal_request(
            db,
            request=req,
            decision=payload.decision,
            admin_notes=payload.admin_notes,
            actor=current_user,
            commit=True,
        )
    except (
        DatasetLifecyclePermissionError,
        DatasetLifecycleStateError,
        DatasetLifecycleValidationError,
    ) as exc:
        raise _translate_lifecycle_error(exc) from exc
    return _to_withdrawal_response(updated)
