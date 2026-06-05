"""
Purpose: Define Pydantic request/response schemas for the dataset API area.
Related: app/routers/*, frontend API clients, docs_v2/2-50.
"""

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.study import StudyResponse


DATASET_QA_REPORT_VERSION = "v1"
DATASET_QA_MODE_MOCK = "mock"
DATASET_QA_MODE_REAL = "real"
DATASET_QA_REVIEW_ACCEPT = "accept"
DATASET_QA_REVIEW_REJECT = "reject"
DATASET_QA_REVIEW_HOLD = "hold"

DatasetQaMode = Literal["mock", "real"]
DatasetQaReviewConclusion = Literal["accept", "reject", "hold"]
DatasetQaStageStatus = Literal["pass", "warning", "fail", "not_computed", "skipped", "pending"]
DatasetQaSeverity = Literal["info", "warning", "error"]
DatasetAssetStatus = Literal["working", "active", "archived", "deleted", "quarantined"]
DatasetAssetVisibility = Literal["private", "workspace", "shared", "public"]


class DatasetAssetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=2, max_length=64)
    description: Optional[str] = Field(default=None, max_length=2000)
    visibility: DatasetAssetVisibility = "private"
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Dataset 名称不能为空")
        return normalized

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip()
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
        if not normalized or any(ch not in allowed for ch in normalized):
            raise ValueError("Dataset code 只能包含字母、数字、短横线和下划线")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class DatasetAssetUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[DatasetAssetStatus] = None
    visibility: Optional[DatasetAssetVisibility] = None
    metadata_json: Optional[dict[str, Any]] = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Dataset 名称不能为空")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class DatasetImportTaskRequest(BaseModel):
    dataset_asset_id: Optional[UUID] = None
    staged_upload_uri: Optional[str] = Field(default=None, max_length=1024)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class DatasetAssetTaskRequest(BaseModel):
    version_label: Optional[str] = Field(default="working", max_length=64)
    dry_run: bool = False
    parameters_json: dict[str, Any] = Field(default_factory=dict)


class DatasetAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    code: str
    description: Optional[str] = None
    owner_id: Optional[str] = None
    status: DatasetAssetStatus
    visibility: DatasetAssetVisibility
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    # Phase 3 (docs_v2/3-25): 生命周期相关字段
    primary_study_id: Optional[str] = None
    concept_doi: Optional[str] = None
    current_version_id: Optional[str] = None
    # UI Phase (docs_v2/6-05): 数据概要聚合字段，给前端 L1 区域显示
    # 这三个字段对每个 asset 从 datasets 表聚合得来（compute_asset_stats）
    subject_count: int = 0
    task_codes: list[str] = Field(default_factory=list)
    total_duration_seconds: float = 0.0
    last_imported_at: Optional[datetime] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DatasetAssetListResponse(BaseModel):
    assets: list[DatasetAssetResponse]


class DatasetBootstrapPairedStudy(BaseModel):
    mode: Literal["create", "existing"] = "create"
    study_id: Optional[str] = Field(default=None, min_length=12, max_length=12)
    code: Optional[str] = Field(default=None, min_length=2, max_length=64)
    name: Optional[str] = Field(default=None, min_length=2, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    storage_quota_gb: int = Field(default=1024, ge=1, le=102400)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
        if not normalized or any(ch not in allowed for ch in normalized):
            raise ValueError("研究项短码只能包含字母、数字、短横线和下划线")
        return normalized

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
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

    @model_validator(mode="after")
    def validate_mode_payload(self):
        if self.mode == "create" and (not self.code or not self.name):
            raise ValueError("paired_study.mode=create 时必须提供 code 和 name")
        if self.mode == "existing" and not self.study_id:
            raise ValueError("paired_study.mode=existing 时必须提供 study_id")
        return self


class DatasetBootstrapRequest(BaseModel):
    dataset: DatasetAssetCreate
    paired_study: DatasetBootstrapPairedStudy
    mount_name: str = Field(default="primary", min_length=1, max_length=128)
    selection_json: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True

    @field_validator("mount_name")
    @classmethod
    def normalize_mount_name(cls, value: str) -> str:
        normalized = value.strip()
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
        if not normalized or any(ch not in allowed for ch in normalized):
            raise ValueError("挂载名称只能包含字母、数字、短横线和下划线")
        return normalized


class DatasetVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dataset_asset_id: str
    version_label: str
    status: str
    # Phase 3 (docs_v2/3-25): 生命周期相关字段
    state: Optional[str] = None
    qa_status: Optional[str] = None
    content_hash: Optional[str] = None
    version_doi: Optional[str] = None
    published_at: Optional[datetime] = None
    published_by: Optional[str] = None
    withdraw_requested_at: Optional[datetime] = None
    withdraw_requested_by: Optional[str] = None
    withdraw_reason: Optional[str] = None
    withdrawn_at: Optional[datetime] = None
    withdrawn_by: Optional[str] = None
    withdrawal_admin_notes: Optional[str] = None
    storage_uri: Optional[str] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None


class DatasetVersionListResponse(BaseModel):
    versions: list[DatasetVersionResponse]


class DatasetBootstrapNextUpload(BaseModel):
    study_id: str
    dataset_asset_id: str
    dataset_version_id: str
    mount_id: str
    mount_name: str
    upload_endpoint: str
    upload_method: Literal["POST"] = "POST"
    form_fields: dict[str, str] = Field(default_factory=dict)


class StudyDatasetMountCreate(BaseModel):
    dataset_asset_id: UUID
    # Phase 3 (docs_v2/3-25): 可选；未传则路由层默认 asset.current_version_id
    dataset_version_id: Optional[UUID] = None
    mount_name: str = Field(..., min_length=1, max_length=128)
    selection_json: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True

    @field_validator("mount_name")
    @classmethod
    def normalize_mount_name(cls, value: str) -> str:
        normalized = value.strip()
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
        if not normalized or any(ch not in allowed for ch in normalized):
            raise ValueError("挂载名称只能包含字母、数字、短横线和下划线")
        return normalized


class StudyDatasetMountUpdate(BaseModel):
    mount_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    selection_json: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None
    # Phase 3 (docs_v2/3-25) C: 升级 mount 锁定的版本（draft 仅主 Study；withdrawn 禁止；published OK）
    dataset_version_id: Optional[UUID] = None

    @field_validator("mount_name")
    @classmethod
    def normalize_mount_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
        if not normalized or any(ch not in allowed for ch in normalized):
            raise ValueError("挂载名称只能包含字母、数字、短横线和下划线")
        return normalized


class StudyDatasetMountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    study_id: str
    dataset_asset_id: str
    # Phase 3 (docs_v2/3-25) C: 挂载锁定到的版本（前端用来判断"是否最新可升级"）
    dataset_version_id: Optional[str] = None
    mount_name: str
    selection_json: dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    mounted_by: Optional[str] = None
    mounted_at: Optional[datetime] = None
    dataset_asset: Optional[DatasetAssetResponse] = None
    dataset_version: Optional[DatasetVersionResponse] = None


class StudyDatasetMountListResponse(BaseModel):
    mounts: list[StudyDatasetMountResponse]


class DatasetBootstrapResponse(BaseModel):
    dataset_asset: DatasetAssetResponse
    dataset_version: DatasetVersionResponse
    study: StudyResponse
    mount: StudyDatasetMountResponse
    next_upload: DatasetBootstrapNextUpload


class RecordingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    study_id: str
    dataset_asset_id: Optional[str] = None
    subject_id: str
    bids_subject_id: str
    session: Optional[str] = None
    task: str
    run: Optional[str] = None
    source_format: str
    source_path: str
    fif_path: Optional[str] = None
    current_version_id: Optional[str] = None
    current_version_seq: Optional[int] = None
    file_size: Optional[int] = None
    checksum: Optional[str] = None
    n_channels: Optional[int] = None
    sfreq: Optional[float] = None
    duration_seconds: Optional[float] = None
    n_events: Optional[int] = None
    qa_status: Optional[str] = None
    qa_report: Optional[dict[str, Any]] = None
    imported_by: Optional[str] = None
    imported_at: Optional[datetime] = None


class RecordingVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    recording_id: str
    study_id: str
    version_seq: int
    source_dir: str
    source_main_file: str
    source_files: list[str] = Field(default_factory=list)
    source_format: str
    fif_dir: Optional[str] = None
    fif_path: Optional[str] = None
    sidecar_paths: dict[str, str] = Field(default_factory=dict)
    file_size: Optional[int] = None
    checksum: Optional[str] = None
    status: str
    qa_status: Optional[str] = None
    note: Optional[str] = None
    uploaded_by: Optional[str] = None
    uploaded_at: Optional[datetime] = None


class RecordingListResponse(BaseModel):
    recordings: list[RecordingResponse]


class RecordingVersionListResponse(BaseModel):
    versions: list[RecordingVersionResponse]


class RecordingUploadResponse(BaseModel):
    message: str
    recording: RecordingResponse


class DatasetQaStageItem(BaseModel):
    key: str
    label: str
    status: DatasetQaStageStatus
    severity: DatasetQaSeverity = "info"
    message: Optional[str] = None
    value: Any = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DatasetQaStage(BaseModel):
    key: str
    title: str
    status: DatasetQaStageStatus
    severity: DatasetQaSeverity = "info"
    message: Optional[str] = None
    items: list[DatasetQaStageItem] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DatasetQaSummary(BaseModel):
    mock_qc_status: Optional[str] = None
    level: Optional[str] = None
    score: Optional[float] = None
    blocking_issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DatasetQaHumanReview(BaseModel):
    conclusion: Optional[DatasetQaReviewConclusion] = None
    notes: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None


class DatasetQaReport(BaseModel):
    version: str = DATASET_QA_REPORT_VERSION
    mode: DatasetQaMode = DATASET_QA_MODE_MOCK
    generated_at: Optional[datetime] = None
    summary: DatasetQaSummary = Field(default_factory=DatasetQaSummary)
    stages: list[DatasetQaStage] = Field(default_factory=list)
    human_review: DatasetQaHumanReview = Field(default_factory=DatasetQaHumanReview)
    history: list[dict[str, Any]] = Field(default_factory=list)


class DatasetQaResponse(BaseModel):
    dataset_id: str
    study_id: str
    qa_status: Optional[str] = None
    qa_report: Optional[DatasetQaReport] = None
    has_report: bool = False
    current_upload_id: Optional[str] = None
    imported_at: Optional[datetime] = None


class DatasetQaMockRunResponse(BaseModel):
    dataset_id: str
    study_id: str
    qa_status: str
    qa_report: DatasetQaReport


class DatasetQaReviewRequest(BaseModel):
    conclusion: DatasetQaReviewConclusion
    notes: Optional[str] = None


class DatasetQaReviewResponse(BaseModel):
    dataset_id: str
    study_id: str
    qa_status: str
    qa_report: DatasetQaReport


class DatasetFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    study_id: str
    dataset_id: str
    dataset_upload_id: str
    file_role: str
    storage_uri: str
    relative_path: str
    logical_path: Optional[str] = None
    file_size: Optional[int] = None
    sha256: Optional[str] = None
    mime_type: Optional[str] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None


class DatasetFileListResponse(BaseModel):
    files: list[DatasetFileResponse]


class DatasetFileMetadataResponse(DatasetFileResponse):
    dataset_version_id: Optional[str] = None
    file_name: str
    extension: str = ""
    exists: bool = False
    preview_supported: bool = False
    download_name: str


class DatasetFilePreviewResponse(BaseModel):
    file: DatasetFileMetadataResponse
    preview_json: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime


class DatasetFileTreeNode(BaseModel):
    name: str
    path: str
    kind: Literal["directory", "file"]
    children: list["DatasetFileTreeNode"] = Field(default_factory=list)
    file_id: Optional[str] = None
    file_role: Optional[str] = None
    storage_uri: Optional[str] = None
    relative_path: Optional[str] = None
    logical_path: Optional[str] = None
    file_size: Optional[int] = None
    sha256: Optional[str] = None


class DatasetFileTreeResponse(BaseModel):
    dataset_asset_id: str
    version_label: Optional[str] = None
    prefix: str = "raw_bids"
    tree: DatasetFileTreeNode
