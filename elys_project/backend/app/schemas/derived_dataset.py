"""
Purpose: Pydantic schemas for DerivedDataset — the unified user-facing replacement
for PipelineArtifact and AnalysisResult.

Related:
- app/models/derived_dataset.py (ORM model)
- app/routers/pipelines.py (HTTP endpoints)
- docs_v2/3-45-DerivedDataset.md (concept)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Read schemas
# ---------------------------------------------------------------------------

class DerivedDatasetResponse(BaseModel):
    """完整的 DerivedDataset 视图。前端列表、详情与抽屉都用它。"""

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

    # 生命周期
    retention_status: str
    retention_expires_at: Optional[datetime] = None

    # 预览
    preview_json: dict[str, Any] = Field(default_factory=dict)

    # 元数据
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None


class DerivedDatasetPreviewResponse(BaseModel):
    """Lightweight preview payload used by the preview endpoint."""

    derived_dataset_id: str
    study_id: str
    produced_by_execution_id: Optional[str] = None
    produced_by_job_id: Optional[str] = None
    data_type: str
    storage_uri: Optional[str] = None
    sha256: Optional[str] = None
    retention_status: Optional[str] = None
    preview_json: dict[str, Any] = Field(default_factory=dict)
    observe_route: str = "/observe"
    observe_query: dict[str, str] = Field(default_factory=dict)
    generated_at: datetime


class DerivedDatasetListResponse(BaseModel):
    derived_datasets: list[DerivedDatasetResponse] = Field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# Write / mutation schemas
# ---------------------------------------------------------------------------

class DerivedDatasetUpdate(BaseModel):
    """PATCH /derived-datasets/{id} — change user-facing label/tags/retention.

    All fields are optional; only sent fields are applied.
    """

    display_name: Optional[str] = Field(default=None, max_length=256)
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    retention_status: Optional[
        Literal["current", "pinned", "cached", "temporary", "deleted"]
    ] = None
    retention_expires_at: Optional[datetime] = None
    reason: Optional[str] = Field(default=None, max_length=500)


class DerivedDatasetBatchUpdate(BaseModel):
    """POST /derived-datasets/batch-update — apply same change to many."""

    ids: list[str] = Field(min_length=1, max_length=500)
    update: DerivedDatasetUpdate


class DerivedDatasetCleanupRequest(BaseModel):
    """POST /derived-datasets/cleanup — kick off a cleanup async task."""

    retention_statuses: list[Literal["temporary", "cached"]] = Field(
        default_factory=lambda: ["temporary", "cached"]
    )
    dry_run: bool = False
    limit: int = Field(default=500, ge=1, le=5000)
    reason: Optional[str] = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# Filter parameters (used by GET list endpoint)
# ---------------------------------------------------------------------------

class DerivedDatasetListQuery(BaseModel):
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
    retention_statuses: Optional[list[str]] = None
    include_deleted: bool = False
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    limit: int = Field(default=200, ge=1, le=2000)
    offset: int = Field(default=0, ge=0)
