"""
Purpose: Define Pydantic request/response schemas for the pipeline API area.
Related: app/routers/*, frontend API clients, docs_v2/2-50.
"""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


NodePhase = Literal["phase1", "phase2", "phase3"]
TaskStatus = Literal["queued", "running", "succeeded", "failed", "canceled", "retrying"]
PipelineExecutionMode = Literal["trial", "analysis", "replay", "system"]


class NodePort(BaseModel):
    name: str
    type: str
    label: Optional[str] = None
    required: bool = True
    cardinality: Optional[str] = None


class NodeProperty(BaseModel):
    name: str
    label: Optional[str] = None
    type: str
    default: Any = None
    required: bool = False
    unit: Optional[str] = None
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None
    options: Optional[list[dict[str, Any]]] = None
    hash: bool = True
    description: Optional[str] = None
    help: Optional[str] = None
    # 前端节点控件 / 检查器靠这两个字段做「高级折叠」和「条件显示」；漏了会被 Pydantic 过滤掉，
    # 导致前端收不到 → 该藏的参数全显出来（如带通滤波器误显「工频」）。
    advanced: bool = False
    visible_when: Optional[dict[str, list[Any]]] = None


class NodeSpecResponse(BaseModel):
    schema_version: str
    type: str
    title: str
    category: str
    phase: NodePhase
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    inputs: list[NodePort] = Field(default_factory=list)
    outputs: list[NodePort]
    properties: list[NodeProperty] = Field(default_factory=list)
    backend: dict[str, Any]
    cache: dict[str, Any] = Field(default_factory=dict)
    # P0 引入的保存配置（step_label / auto_tags / name_template / split_supported / ...）
    # 前端节点参数面板的"保存设置"折叠区依赖这个字段。
    save: dict[str, Any] = Field(default_factory=dict)
    ui: dict[str, Any] = Field(default_factory=dict)


class NodeSpecListResponse(BaseModel):
    nodes: list[NodeSpecResponse]


class PipelineDefinitionPayload(BaseModel):
    schema_version: str = "1.0"
    app_version: Optional[str] = None
    engine_version: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    graph: dict[str, Any] = Field(default_factory=lambda: {"nodes": [], "links": []})
    settings: dict[str, Any] = Field(default_factory=dict)


class PipelineCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    definition_json: PipelineDefinitionPayload = Field(default_factory=PipelineDefinitionPayload)
    is_template: bool = False

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("工作流名称不能为空")
        return normalized


class PipelineUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    definition_json: Optional[PipelineDefinitionPayload] = None
    is_template: Optional[bool] = None
    status: Optional[Literal["draft", "active", "archived"]] = None
    expected_version: int = Field(..., ge=1)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("工作流名称不能为空")
        return normalized


class PipelineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    study_id: str
    name: str
    description: Optional[str] = None
    definition_json: dict[str, Any]
    node_count: int
    version: int
    is_template: bool
    status: str
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PipelineListResponse(BaseModel):
    pipelines: list[PipelineResponse]


class PipelineEditLockResponse(BaseModel):
    id: str
    study_id: str
    pipeline_id: int
    resource_kind: str
    resource_id: str
    lock_type: str
    locked_by: Optional[str] = None
    locked_at: datetime
    expires_at: datetime
    released_at: Optional[datetime] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class PipelineValidationIssue(BaseModel):
    code: str
    message: str
    node_id: Optional[str] = None
    node_type: Optional[str] = None
    severity: Literal["error", "warning"] = "error"


class PipelineValidationResponse(BaseModel):
    valid: bool
    errors: list[PipelineValidationIssue] = Field(default_factory=list)
    warnings: list[PipelineValidationIssue] = Field(default_factory=list)


class LoadDataSelectionOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection_mode: Optional[Literal["filter", "explicit"]] = None
    dataset_filter: Optional[dict[str, Any]] = None
    dataset_ids: Optional[list[str]] = None
    dataset_file_ids: Optional[list[str]] = None
    selector_json: Optional[dict[str, Any]] = None


class PipelineExecutionCreate(BaseModel):
    trigger: Literal["manual"] = "manual"
    execution_mode: PipelineExecutionMode = "analysis"
    selection_override: dict[str, LoadDataSelectionOverride] = Field(default_factory=dict)


class PipelineExecutionRetryRequest(BaseModel):
    input_policy: Literal["reuse_snapshot", "re_resolve"] = "reuse_snapshot"


class PipelineExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    study_id: str
    pipeline_id: int
    pipeline_version: int
    execution_seq: int
    trigger: str
    execution_mode: PipelineExecutionMode = "analysis"
    status: str
    node_count: int
    dataset_count: int
    definition_snapshot: dict[str, Any] = Field(default_factory=dict)
    manifest_json: dict[str, Any] = Field(default_factory=dict)
    result_json: dict[str, Any] = Field(default_factory=dict)
    error_json: dict[str, Any] = Field(default_factory=dict)
    started_by: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class PipelineJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    execution_id: str
    study_id: str
    pipeline_id: int
    node_id: str
    node_type: str
    node_title: Optional[str] = None
    status: str
    topo_index: int
    params_json: dict[str, Any] = Field(default_factory=dict)
    input_json: dict[str, Any] = Field(default_factory=dict)
    output_json: dict[str, Any] = Field(default_factory=dict)
    input_hash: Optional[str] = None
    params_hash: Optional[str] = None
    node_hash: Optional[str] = None
    trace_code: Optional[str] = None
    error_json: dict[str, Any] = Field(default_factory=dict)
    log_tail: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None


class PipelineExecutionInputResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    execution_id: str
    study_id: str
    pipeline_id: int
    job_id: Optional[str] = None
    node_id: Optional[str] = None
    node_type: Optional[str] = None
    input_slot: str
    input_index: int
    input_kind: str
    dataset_asset_id: Optional[str] = None
    dataset_id: Optional[str] = None
    dataset_upload_id: Optional[str] = None
    dataset_file_id: Optional[str] = None
    file_role: Optional[str] = None
    storage_uri: Optional[str] = None
    logical_path: Optional[str] = None
    upstream_execution_id: Optional[str] = None
    upstream_dataset_id: Optional[str] = None
    selector_json: dict[str, Any] = Field(default_factory=dict)
    resolved_metadata_json: dict[str, Any] = Field(default_factory=dict)
    sha256: Optional[str] = None
    created_at: Optional[datetime] = None


class PipelineExecutionDependencyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    study_id: str
    execution_id: str
    depends_on_execution_id: str
    upstream_dataset_id: Optional[str] = None
    dependency_kind: str
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


class TaskEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    event_type: str
    status: Optional[str] = None
    progress: Optional[float] = None
    message: Optional[str] = None
    payload_json: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


class AsyncTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    celery_task_id: Optional[str] = None
    task_type: str
    queue_name: Optional[str] = None
    status: str
    progress: float = 0
    study_id: Optional[str] = None
    resource_kind: str
    resource_id: Optional[str] = None
    payload_json: dict[str, Any] = Field(default_factory=dict)
    result_json: dict[str, Any] = Field(default_factory=dict)
    error_json: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    attempt: int = 1
    max_attempts: int = 1
    events: list[TaskEventResponse] = Field(default_factory=list)


class AsyncTaskListResponse(BaseModel):
    tasks: list[AsyncTaskResponse]


class TaskEventListResponse(BaseModel):
    events: list[TaskEventResponse]


class PipelineExecutionDetailResponse(PipelineExecutionResponse):
    inputs: list[PipelineExecutionInputResponse] = Field(default_factory=list)
    dependencies: list[PipelineExecutionDependencyResponse] = Field(default_factory=list)
    tasks: list[AsyncTaskResponse] = Field(default_factory=list)
    jobs: list[PipelineJobResponse] = Field(default_factory=list)
    study_outputs: list["StudyOutputResponse"] = Field(default_factory=list)


class PipelineExecutionLineageGraphNode(BaseModel):
    id: str
    node_type: str
    label: str
    resource_kind: str
    resource_id: str
    status: Optional[str] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class PipelineExecutionLineageGraphEdge(BaseModel):
    id: str
    source: str
    target: str
    edge_type: str
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class PipelineExecutionLineageResponse(BaseModel):
    execution: PipelineExecutionResponse
    inputs: list[PipelineExecutionInputResponse] = Field(default_factory=list)
    study_outputs: list["StudyOutputResponse"] = Field(default_factory=list)
    upstream_executions: list[PipelineExecutionResponse] = Field(default_factory=list)
    downstream_executions: list[PipelineExecutionResponse] = Field(default_factory=list)
    upstream_dependencies: list[PipelineExecutionDependencyResponse] = Field(default_factory=list)
    downstream_dependencies: list[PipelineExecutionDependencyResponse] = Field(default_factory=list)
    graph_nodes: list[PipelineExecutionLineageGraphNode] = Field(default_factory=list)
    graph_edges: list[PipelineExecutionLineageGraphEdge] = Field(default_factory=list)


class PipelineExecutionListResponse(BaseModel):
    executions: list[PipelineExecutionResponse]


class PipelineJobListResponse(BaseModel):
    jobs: list[PipelineJobResponse]


class PipelineInteractionResponse(BaseModel):
    execution_id: str
    job_id: str
    node_id: str
    node_type: str
    status: str
    interaction_type: str = "ica_component_selection"
    decision_version: int = 1
    components: list[dict[str, Any]] = Field(default_factory=list)
    preview_json: dict[str, Any] = Field(default_factory=dict)
    decision: Optional[dict[str, Any]] = None


class PipelineInteractionDecisionRequest(BaseModel):
    excluded_components: list[int] = Field(default_factory=list)
    decision_version: int = Field(..., ge=1)


class PipelineInteractionDecisionResponse(PipelineInteractionResponse):
    pass


class PipelineResumeResponse(BaseModel):
    execution: PipelineExecutionResponse
    job: PipelineJobResponse


class LoadDataResolveRequest(BaseModel):
    node_id: Optional[str] = None
    selection_mode: Literal["filter", "explicit"] = "filter"
    dataset_filter: dict[str, Any] = Field(
        default_factory=lambda: {
            "subjects": "all",
            "sessions": "all",
            "tasks": "all",
            "runs": "all",
            "qa_status": "all",
            "require_fif": True,
        }
    )
    dataset_ids: list[str] = Field(default_factory=list)


class LoadDataDataInfo(BaseModel):
    dataset_id: str
    study_id: str
    dataset_asset_id: Optional[str] = None
    dataset_version_id: Optional[str] = None
    dataset_file_id: Optional[str] = None
    file_role: Optional[str] = None
    storage_uri: Optional[str] = None
    logical_path: Optional[str] = None
    sha256: Optional[str] = None
    mount_id: Optional[str] = None
    mount_name: Optional[str] = None
    subject_id: str
    subject: str
    bids_subject_id: str
    session: Optional[str] = None
    task: str
    run: Optional[str] = None
    source_format: str
    source_path: str
    source_abs_path: Optional[str] = None
    source_exists: bool = False
    fif_path: Optional[str] = None
    fif_abs_path: Optional[str] = None
    fif_exists: bool = False
    current_upload_id: Optional[str] = None
    current_upload_seq: Optional[int] = None
    current_fif_dir: Optional[str] = None
    sidecar_paths: Optional[dict[str, str]] = None
    file_size: Optional[int] = None
    checksum: Optional[str] = None
    n_channels: Optional[int] = None
    sfreq: Optional[float] = None
    duration_seconds: Optional[float] = None
    n_events: Optional[int] = None
    qa_status: Optional[str] = None
    imported_at: Optional[datetime] = None
    content_hash: str
    data_type: str = "raw"
    event_labels: list[str] = Field(default_factory=list)
    event_counts: dict[str, int] = Field(default_factory=dict)
    # 自动收成的可勾选 condition 分组（前端 Epoch chips 用）：[{name,pattern,mode,count,sample}]
    condition_groups: list[dict[str, Any]] = Field(default_factory=list)
    # 通道名列表（从 FIF info 读出，供下游 Re-reference / pick_channels 等节点提供候选）
    ch_names: list[str] = Field(default_factory=list)


class LoadDataResolveResponse(BaseModel):
    valid: bool
    study_id: str
    node_id: Optional[str] = None
    selection_mode: str
    dataset_count: int
    resolved_filter: dict[str, Any] = Field(default_factory=dict)
    data_infos: list[LoadDataDataInfo] = Field(default_factory=list)
    errors: list[PipelineValidationIssue] = Field(default_factory=list)
    warnings: list[PipelineValidationIssue] = Field(default_factory=list)
    missing_dataset_ids: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Forward references resolved at import time
# ---------------------------------------------------------------------------
from app.schemas.study_output import StudyOutputResponse  # noqa: E402  pyright: ignore

PipelineExecutionDetailResponse.model_rebuild()
PipelineExecutionLineageResponse.model_rebuild()
