"""
Purpose: Define FastAPI routes for the dataset_versions API area (publish / withdraw / emergency takedown).
Related: app/services/dataset_lifecycle.py, app/schemas/dataset_lifecycle.py, docs_v2/3-25.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    DatasetAsset,
    DatasetVersion,
    DatasetWithdrawalRequest,
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
        status=version.status,
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
# Emergency takedown (superadmin only)
# ============================================


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
