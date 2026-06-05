"""
Purpose: Define Pydantic request/response schemas for the study API area.
Related: app/routers/*, frontend API clients, docs_v2/2-50.
"""

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class StudyCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    storage_quota_gb: int = Field(default=1024, ge=1, le=102400)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("研究项短码不能为空")
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
        if any(ch not in allowed for ch in normalized):
            raise ValueError("研究项短码只能包含字母、数字、短横线和下划线")
        return normalized

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("研究项名称不能为空")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class StudyResponse(BaseModel):
    id: str
    code: str
    name: str
    description: Optional[str]
    status: str
    owner_id: str
    data_root: str
    storage_quota_bytes: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    archived_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None
    delete_reason: Optional[str] = None


class StudyListResponse(BaseModel):
    studies: list[StudyResponse]


StudyMemberRole = Literal["editor", "viewer"]


class StudyMemberUpsert(BaseModel):
    user_id: UUID
    role: StudyMemberRole = "viewer"
    can_run: Optional[bool] = None


class StudyMemberUpdate(BaseModel):
    role: StudyMemberRole
    can_run: Optional[bool] = None


class StudyMemberResponse(BaseModel):
    id: str
    study_id: str
    user_id: str
    username: str
    full_name: Optional[str] = None
    role: str
    can_read: bool
    can_write: bool
    can_delete: bool
    can_export: bool
    can_run: bool
    added_at: Optional[datetime] = None


class StudyMemberListResponse(BaseModel):
    members: list[StudyMemberResponse]


class StudyTrashRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class StudyPurgeRequest(BaseModel):
    confirm_study_id: str = Field(..., min_length=12, max_length=12)


class StudyActionResponse(BaseModel):
    study: StudyResponse
    message: str


class StudySettingsUpdate(BaseModel):
    default_dataset_filter: Optional[dict[str, Any]] = None
    run_policy: Optional[dict[str, Any]] = None
    derived_dataset_retention_policy: Optional[dict[str, Any]] = None
    storage_policy: Optional[dict[str, Any]] = None


class StudySettingsResponse(BaseModel):
    study_id: str
    default_dataset_filter: dict[str, Any]
    run_policy: dict[str, Any]
    derived_dataset_retention_policy: dict[str, Any]
    storage_policy: dict[str, Any]
    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None
