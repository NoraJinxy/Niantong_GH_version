"""
Purpose: Pydantic request/response schemas for the dataset lifecycle API area.
Related: app/routers/dataset_versions.py, app/services/dataset_lifecycle.py, docs_v2/3-25.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.services.semver import is_valid_semver


DatasetVersionState = Literal["draft", "published", "withdraw_requested", "withdrawn"]
DatasetVersionQaStatus = Literal["pass", "fail", "not_run"]
WithdrawalDecision = Literal["approved", "rejected", "emergency"]


# ============================================
# Publish
# ============================================


class DatasetVersionPublishRequest(BaseModel):
    """发布 draft 版本时必须指定 SemVer 版本号（DEC-2026-0531-C）。"""

    version_label: str = Field(..., min_length=5, max_length=32, examples=["1.0.0"])

    @field_validator("version_label")
    @classmethod
    def validate_semver(cls, value: str) -> str:
        normalized = value.strip()
        if not is_valid_semver(normalized):
            raise ValueError(
                "版本号必须是 SemVer x.y.z 格式（如 1.0.0；首版可用 0.x.y 表示 pre-release）"
            )
        return normalized


class DatasetVersionResponse(BaseModel):
    id: str
    dataset_asset_id: str
    version_label: str
    state: DatasetVersionState
    status: str  # 旧 status 字段，兼容期保留
    qa_status: DatasetVersionQaStatus
    content_hash: Optional[str] = None
    version_doi: Optional[str] = None
    storage_uri: Optional[str] = None
    published_at: Optional[datetime] = None
    published_by: Optional[str] = None
    withdraw_requested_at: Optional[datetime] = None
    withdraw_requested_by: Optional[str] = None
    withdraw_reason: Optional[str] = None
    withdrawn_at: Optional[datetime] = None
    withdrawn_by: Optional[str] = None
    withdrawal_admin_notes: Optional[str] = None
    created_at: datetime
    created_by: Optional[str] = None


class DatasetVersionPublishResponse(BaseModel):
    dataset_version: DatasetVersionResponse
    previous_version_label: str
    is_first_published_version: bool
    concept_doi: Optional[str] = None  # Asset 的 Concept DOI（首次发布时新生成）


# ============================================
# Withdrawal
# ============================================


class DatasetVersionWithdrawRequest(BaseModel):
    """owner 提交撤回申请，reason 必填。"""

    reason: str = Field(..., min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("撤回原因不能为空")
        return normalized


class DatasetWithdrawalRequestResponse(BaseModel):
    id: str
    dataset_version_id: str
    requested_by: str
    requested_at: datetime
    reason: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    decision: Optional[WithdrawalDecision] = None
    admin_notes: Optional[str] = None
    notification_sent_at: Optional[datetime] = None


class WithdrawalReviewRequest(BaseModel):
    """admin 审核撤回申请。"""

    decision: Literal["approved", "rejected"]
    admin_notes: Optional[str] = Field(default=None, max_length=2000)


class EmergencyTakedownRequest(BaseModel):
    """超级管理员紧急下架（DEC-2026-0531-D）。"""

    reason: str = Field(..., min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("紧急下架必须填写原因（事后审计需要）")
        return normalized
