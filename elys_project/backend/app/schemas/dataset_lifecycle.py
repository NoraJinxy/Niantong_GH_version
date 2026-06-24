"""
Purpose: Pydantic request/response schemas for the dataset lifecycle API area.
Related: app/routers/dataset_versions.py, app/services/dataset_lifecycle.py, docs_v2/3-25.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.dataset import DatasetVersionResponse
from app.services.semver import is_valid_semver


WithdrawalDecision = Literal["approved", "rejected", "emergency"]
# 可见范围开放目标（只升不降，私有不在内——私有是发布默认态、非可开放目标）
OpenVisibilityTarget = Literal["shared", "public"]


# ============================================
# Publish
# ============================================


class DatasetVersionPublishRequest(BaseModel):
    """发布未发布版本时必须指定 SemVer 版本号，并通过脱敏/伦理/版权合规关口（规则 3、综合报告 §L）。

    发布是 PII/伦理/版权关口：每次发布都需重做声明（每个已发布版本都是独立不可变制品）。
    """

    version_label: str = Field(..., min_length=5, max_length=32, examples=["1.0.0"])
    # 已脱敏确认：必须为 True，否则 422（发布即对外不可逆释放，须先确认无 PII）
    deidentified_confirmed: bool = Field(
        ..., description="已确认数据去标识化/脱敏（必须勾选，否则不能发布）"
    )
    # 伦理声明：发布者声明该数据采集与共享符合伦理要求
    ethics_statement: str = Field(
        ..., min_length=1, max_length=2000, description="伦理声明（采集与共享符合伦理要求）"
    )
    # 版权 / 许可声明：发布者声明对该数据拥有发布与授权的权利
    license_statement: str = Field(
        ..., min_length=1, max_length=2000, description="版权 / 许可声明"
    )

    @field_validator("version_label")
    @classmethod
    def validate_semver(cls, value: str) -> str:
        normalized = value.strip()
        if not is_valid_semver(normalized):
            raise ValueError(
                "版本号必须是 SemVer x.y.z 格式（如 1.0.0；首版可用 0.x.y 表示 pre-release）"
            )
        return normalized

    @field_validator("deidentified_confirmed")
    @classmethod
    def require_deidentified(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("发布前必须确认数据已脱敏 / 去标识化")
        return value

    @field_validator("ethics_statement", "license_statement")
    @classmethod
    def normalize_statement(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("发布前必须填写伦理与版权声明（事后审计需要）")
        return normalized


class DatasetVersionPublishResponse(BaseModel):
    dataset_version: DatasetVersionResponse
    previous_version_label: str
    is_first_published_version: bool
    concept_doi: Optional[str] = None  # Asset 的 Concept DOI（首次发布时新生成）


# ============================================
# Visibility（可见范围 · 只升不降）
# ============================================


class OpenVisibilityRequest(BaseModel):
    """负责人显式开放数据集可见范围（只升不降、无降级接口；规则 5、综合报告 §E/§I）。

    target 仅可为 shared / public；路由层另校验 target > 当前可见范围（可跳级、禁降级），
    且要求资产已有 ≥1 个已发布版本（规则 J）。
    """

    target: OpenVisibilityTarget


# ============================================
# DatasetMember（共享邀请制授权 · 按用户）
# ============================================


class DatasetMemberAddRequest(BaseModel):
    """负责人按标识符授权一个数据集的共享访问（规则 7、综合报告 §B）。

    user_identifier 接受用户名或用户 ID（UUID 字符串）；路由层解析为具体 User
    （普通用户填不出 UUID，故支持按用户名授权）。
    """

    user_identifier: str


class DatasetMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    asset_id: str
    user_id: str
    # 便于授权面板展示被授权人（参照 StudyMemberResponse）
    username: Optional[str] = None
    full_name: Optional[str] = None
    granted_by: Optional[str] = None
    granted_at: Optional[datetime] = None


class DatasetMemberListResponse(BaseModel):
    members: list[DatasetMemberResponse]


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
    """管理员紧急下架：跳过撤回审核、事后补审计（规则 9、综合报告 §A）。"""

    reason: str = Field(..., min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("紧急下架必须填写原因（事后审计需要）")
        return normalized


# ============================================
# Publicization（转公开审核 · shared → public，2026-06-10 Q1 定稿）
# ============================================


PublicizationDecision = Literal["approved", "rejected", "auto"]


class PublicizationRequestBody(BaseModel):
    """owner 申请把数据集可见范围升到 public（shared → public）。reason 可选。"""

    reason: Optional[str] = Field(default=None, max_length=2000)


class DatasetPublicizationRequestResponse(BaseModel):
    id: str
    asset_id: str
    requested_by: str
    requested_at: datetime
    reason: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    decision: Optional[PublicizationDecision] = None  # auto = 调试期自动通过
    admin_notes: Optional[str] = None
    notified_at: Optional[datetime] = None


class PublicizationReviewRequest(BaseModel):
    """admin 审核转公开申请。"""

    decision: Literal["approved", "rejected"]
    admin_notes: Optional[str] = Field(default=None, max_length=2000)
