"""
Purpose: Pydantic schemas for StudyOutput — the unified user-facing replacement
for PipelineArtifact and AnalysisResult.

Related:
- app/models/study_output.py (ORM model)
- app/routers/pipelines.py (HTTP endpoints)
- docs_v2/3-45-StudyOutput.md (concept)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Read schemas
# ---------------------------------------------------------------------------

class StudyOutputResponse(BaseModel):
    """完整的 StudyOutput 视图。前端列表、详情与抽屉都用它。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    study_id: str

    # 来源追溯
    produced_by_execution_id: Optional[str] = None
    produced_by_job_id: Optional[str] = None
    produced_by_node_id: Optional[str] = None
    produced_by_node_type: Optional[str] = None
    produced_by_params: dict[str, Any] = Field(default_factory=dict)
    upstream_dataset_ids: list[str] = Field(default_factory=list)
    upstream_recording_ids: list[str] = Field(default_factory=list)

    # 来源工作流（由 produced_by_execution_id join PipelineExecution→PipelineDefinition 注入；
    # 历史行 / 无关联执行时为空）。结果页据此显示「哪个工作流 · 哪一版」并支持筛选。
    pipeline_id: Optional[int] = None
    pipeline_name: Optional[str] = None
    pipeline_version: Optional[int] = None  # 执行当时的工作流版本号
    execution_seq: Optional[int] = None  # 该工作流的第几次运行

    # 数据语义
    data_type: str
    subject_id: Optional[str] = None
    bids_subject_id: Optional[str] = None
    session: Optional[str] = None
    task: Optional[str] = None
    run_label: Optional[str] = None
    condition: Optional[str] = None

    # 用户层面
    display_name: Optional[str] = None
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)

    # 物理存储
    storage_uri: str
    logical_path: Optional[str] = None
    file_role: Optional[str] = None
    file_size: Optional[int] = None
    sha256: Optional[str] = None
    mime_type: Optional[str] = None

    # 保留与缓存（三层解耦）
    keep: bool = False
    cache_eligible: bool = False
    retention_expires_at: Optional[datetime] = None

    # 预览
    preview_json: dict[str, Any] = Field(default_factory=dict)

    # 元数据
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None


class StudyOutputPreviewResponse(BaseModel):
    """Lightweight preview payload used by the preview endpoint."""

    study_output_id: str
    study_id: str
    produced_by_execution_id: Optional[str] = None
    produced_by_job_id: Optional[str] = None
    data_type: str
    storage_uri: Optional[str] = None
    sha256: Optional[str] = None
    keep: bool = False
    preview_json: dict[str, Any] = Field(default_factory=dict)
    observe_route: str = "/observe"
    observe_query: dict[str, str] = Field(default_factory=dict)
    generated_at: datetime


class StudyOutputListResponse(BaseModel):
    study_outputs: list[StudyOutputResponse] = Field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# Write / mutation schemas
# ---------------------------------------------------------------------------

class StudyOutputUpdate(BaseModel):
    """PATCH /outputs/{id} — change user-facing label/tags/keep/deleted.

    All fields are optional; only sent fields are applied.
    - keep:    用户保留意图（true=保留 / false=不保留，交回系统缓存/TTL 管理）
    - deleted: 回收站软删（true=删到回收站 / false=恢复）
    """

    display_name: Optional[str] = Field(default=None, max_length=256)
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    keep: Optional[bool] = None
    deleted: Optional[bool] = None
    reason: Optional[str] = Field(default=None, max_length=500)


class StudyOutputBatchUpdate(BaseModel):
    """POST /outputs/batch-update — apply same change to many."""

    ids: list[str] = Field(min_length=1, max_length=500)
    update: StudyOutputUpdate


class StudyOutputCleanupRequest(BaseModel):
    """POST /outputs/cleanup — 回收 keep=false 且已过期(retention_expires_at<now)的输出。

    清理条件固定（keep=false AND retention_expires_at<now AND deleted_at IS NULL），
    不再按 retention_status 枚举筛选。
    """

    dry_run: bool = False
    limit: int = Field(default=500, ge=1, le=5000)
    reason: Optional[str] = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# Filter parameters (used by GET list endpoint)
# ---------------------------------------------------------------------------

class StudyOutputListQuery(BaseModel):
    """Query params for cross-Execution derived-dataset listing.

    Most fields accept a list — interpret as IN clause.
    """

    study_id: Optional[str] = None
    execution_ids: Optional[list[str]] = None
    node_types: Optional[list[str]] = None
    data_types: Optional[list[str]] = None
    subject_ids: Optional[list[str]] = None
    bids_subject_ids: Optional[list[str]] = None
    sessions: Optional[list[str]] = None
    tasks: Optional[list[str]] = None
    conditions: Optional[list[str]] = None
    tags: Optional[list[str]] = None
    keep: Optional[bool] = None
    include_deleted: bool = False
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    limit: int = Field(default=200, ge=1, le=2000)
    offset: int = Field(default=0, ge=0)
