"""
Purpose: Implement workflow/Pipeline runtime support for contracts, including validation, execution, artifacts, cache, or data resolution.
Related: app/routers/pipelines.py, app/tasks/pipeline_tasks.py, app/pipeline/nodes/*.json, docs_v2/5-00 and docs_v2/7-40.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class NodeInput:
    port: str
    data_infos: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    value: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StudyOutputSummary:
    """Lightweight return payload for StudyOutputStore.save_*.

    Mirrors the StudyOutput row fields. dispatcher will read this directly
    to populate output_data_infos and downstream input chains.
    """

    study_output_id: str | None
    study_id: str
    produced_by_execution_id: str | None
    produced_by_job_id: str | None
    produced_by_node_id: str | None
    produced_by_node_type: str | None
    upstream_dataset_ids: list[str] = field(default_factory=list)
    upstream_recording_ids: list[str] = field(default_factory=list)
    data_type: str = ""
    subject_id: str | None = None
    bids_subject_id: str | None = None
    session: str | None = None
    task: str | None = None
    run_label: str | None = None
    condition: str | None = None
    display_name: str | None = None
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    storage_uri: str | None = None
    logical_path: str | None = None
    file_role: str | None = None
    file_size: int | None = None
    sha256: str | None = None
    mime_type: str | None = None
    keep: bool = False
    cache_eligible: bool = False
    retention_expires_at: str | None = None  # ISO timestamp（仅 keep=False 的缓存行）
    preview_json: dict[str, Any] = field(default_factory=dict)
    produced_by_params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        # 输出两套键，便于 dispatcher 在过渡期既能读新字段也能读旧字段：
        # - 新键：study_output_id / data_type / display_name / ...
        # - 旧键（向后兼容）：artifact_id / storage_path / metadata_json / ...
        return {
            "study_output_id": self.study_output_id,
            "artifact_id": self.study_output_id,  # 兼容旧 dispatcher
            "study_id": self.study_id,
            "execution_id": self.produced_by_execution_id,
            "produced_by_execution_id": self.produced_by_execution_id,
            "job_id": self.produced_by_job_id,
            "produced_by_job_id": self.produced_by_job_id,
            "produced_by_node_id": self.produced_by_node_id,
            "produced_by_node_type": self.produced_by_node_type,
            "upstream_dataset_ids": list(self.upstream_dataset_ids),
            "upstream_recording_ids": list(self.upstream_recording_ids),
            "data_type": self.data_type,
            "subject_id": self.subject_id,
            "bids_subject_id": self.bids_subject_id,
            "session": self.session,
            "task": self.task,
            "run_label": self.run_label,
            "condition": self.condition,
            "display_name": self.display_name,
            "description": self.description,
            "tags": list(self.tags),
            "storage_uri": self.storage_uri,
            "logical_path": self.logical_path,
            "file_role": self.file_role,
            "file_size": self.file_size,
            "sha256": self.sha256,
            "checksum": self.sha256,  # 兼容旧 dispatcher
            "content_hash": self.sha256,  # 兼容旧 dispatcher
            "mime_type": self.mime_type,
            "keep": self.keep,
            "cache_eligible": self.cache_eligible,
            "retention_expires_at": self.retention_expires_at,
            "preview_json": self.preview_json,
            "produced_by_params": self.produced_by_params,
            # 兼容旧 dispatcher 的 metadata_json：把 produced_by_params 抛在那
            "metadata_json": {
                "node_id": self.produced_by_node_id,
                "node_type": self.produced_by_node_type,
                "params": self.produced_by_params,
            },
            # 兼容旧 dispatcher：artifact_type / storage_path / source_dataset_id
            "artifact_type": "derivative",
            "storage_path": (self.storage_uri or "").split("/", 3)[-1] if self.storage_uri else None,
            "source_dataset_id": (self.upstream_recording_ids[0] if self.upstream_recording_ids else None),
        }


@dataclass
class NodeOutput:
    node_id: str
    node_type: str
    outputs: dict[str, Any] = field(default_factory=dict)
    data_infos: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_output_json(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "outputs": self.outputs,
            "data_infos": self.data_infos,
            "artifacts": self.artifacts,
            "metadata": self.metadata,
        }


@dataclass
class NodeExecutionContext:
    db: Any
    study: Any
    pipeline: Any
    execution: Any
    job: Any
    node: dict[str, Any]
    params: dict[str, Any] = field(default_factory=dict)
    inputs: dict[str, NodeInput] = field(default_factory=dict)
    work_dir: Path | None = None
    study_output_store: Any = None
    # 节点 spec（从 registry 读到的 JSON 字典），用于 dispatcher 读取 save 子对象
    node_spec: dict[str, Any] = field(default_factory=dict)
    # 整个 pipeline 的拓扑角色映射 {node_id: "leaf" | "intermediate" | "source"}，
    # 用于 save_settings.apply_save_settings 决定默认 retention
    topology: dict[str, str] = field(default_factory=dict)
