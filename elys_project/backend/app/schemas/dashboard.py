"""
Purpose: Define compact Dashboard summary response schemas.
Related: app/routers/dashboard.py, app/services/dashboard_summary.py, frontend Dashboard.vue.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class DashboardCounts(BaseModel):
    datasets: int
    studies: int
    pipelines: int
    executions: int


class DashboardDatasetStates(BaseModel):
    working: int
    active: int
    error: int


class DashboardStudyStates(BaseModel):
    active: int
    archived: int


class DashboardPipelineStates(BaseModel):
    active: int
    draft: int


class DashboardExecutionStates(BaseModel):
    waiting_user_input: int
    failed: int
    running: int
    queued: int
    pending: int


class DashboardStates(BaseModel):
    datasets: DashboardDatasetStates
    studies: DashboardStudyStates
    pipelines: DashboardPipelineStates
    executions: DashboardExecutionStates


class DashboardStudyMetrics(BaseModel):
    dataset_count: int
    pipeline_count: int
    execution_count: int
    running_execution_count: int
    attention_execution_count: int


class DashboardRecentStudy(BaseModel):
    id: str
    name: str
    code: str | None = None
    description: str | None = None
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metrics: DashboardStudyMetrics


class DashboardActiveExecution(BaseModel):
    id: str
    study_id: str
    pipeline_id: int
    pipeline_name: str
    execution_seq: int
    status: str
    execution_mode: str
    stage_label: str
    started_at: datetime | None = None
    finished_at: datetime | None = None


DashboardActivityObjectKind = Literal["dataset", "study", "pipeline", "execution"]
DashboardActivitySeverity = Literal["info", "success", "warn", "error"]
DashboardActivityGroupKind = Literal["bootstrap", "execution_lifecycle"]


class DashboardActivityItem(BaseModel):
    object_kind: DashboardActivityObjectKind
    object_name: str
    action_label: str
    created_at: datetime | None = None
    target_url: str | None = None
    # 上下文(让用户看到"哪个 Run 在哪个 Pipeline 在哪个 Study"的归属关系)
    study_id: str | None = None
    study_name: str | None = None
    pipeline_id: int | str | None = None
    pipeline_name: str | None = None
    execution_seq: int | None = None
    severity: DashboardActivitySeverity = "info"
    # 折叠组(把"创建 Dataset 并配对 Study"的 4 个 audit 事件合一,Run 生命周期的多次状态合一)
    group_kind: DashboardActivityGroupKind | None = None
    group_summary: str | None = None


class DashboardSummaryResponse(BaseModel):
    counts: DashboardCounts
    states: DashboardStates
    recent_studies: list[DashboardRecentStudy]
    active_executions: list[DashboardActiveExecution]
    recent_activity: list[DashboardActivityItem]
