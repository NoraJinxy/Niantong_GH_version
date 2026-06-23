"""
Purpose: Persist Pipeline Execution upstream Artifact dependencies and guard cleanup.
Related: app/pipeline/executor.py, app/routers/pipelines.py, app/routers/studies.py, docs_v2/5-30.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import StudyOutput, PipelineExecution, PipelineExecutionDependency, PipelineExecutionInput
from app.pipeline.contracts import NodeInput


@dataclass
class ArtifactDependencyError(Exception):
    artifact_id: str
    blockers: list[dict[str, Any]]

    def to_detail(self) -> dict[str, Any]:
        return {
            "code": "DERIVED_DATASET_HAS_DOWNSTREAM_DEPENDENCIES",
            "message": "结果已被下游 Execution 或节点输入引用，不能删除或清理。",
            "study_output_id": self.artifact_id,
            "dependencies": self.blockers,
        }


def record_execution_artifact_dependencies(
    db: Session,
    *,
    study: Any,
    pipeline: Any,
    execution: Any,
    job: Any,
    node: dict[str, Any],
    inputs: dict[str, NodeInput],
) -> int:
    """Freeze artifact inputs and cross-execution dependencies for one node execution."""

    references = _collect_artifact_references(inputs)
    if not references:
        return 0

    existing_inputs = _existing_input_keys(db, execution_id=execution.id, job_id=job.id)
    existing_dependencies = _existing_dependency_keys(db, execution_id=execution.id)
    added = 0
    node_id = str(node.get("id") or getattr(job, "node_id", "") or "")
    node_type = str(node.get("type") or getattr(job, "node_type", "") or "")

    for index, reference in enumerate(references):
        # 兼容新旧 key：StudyOutputSummary.to_dict 同时输出 study_output_id 和 artifact_id
        dataset_id = _uuid_or_none(reference.get("study_output_id") or reference.get("artifact_id"))
        if dataset_id is None:
            continue

        dataset = _study_output_for_reference(db, dataset_id)
        upstream_execution_id = (
            _uuid_or_none(reference.get("pipeline_execution_id"))
            or _uuid_or_none(reference.get("execution_id"))
            or _uuid_or_none(reference.get("produced_by_execution_id"))
            or _uuid_or_none(getattr(dataset, "produced_by_execution_id", None))
        )
        storage_uri = reference.get("storage_uri") or reference.get("artifact_storage_uri") or getattr(dataset, "storage_uri", None)
        storage_path = reference.get("storage_path") or reference.get("artifact_storage_path") or getattr(dataset, "logical_path", None)
        sha256 = reference.get("sha256") or reference.get("content_hash") or reference.get("checksum") or getattr(dataset, "sha256", None)
        input_slot = str(reference.get("input_slot") or reference.get("port") or "input")
        input_index = int(reference.get("input_index") or index)
        input_key = (input_slot, input_index, str(dataset_id), str(upstream_execution_id) if upstream_execution_id else None)
        if input_key not in existing_inputs:
            db.add(
                PipelineExecutionInput(
                    execution_id=execution.id,
                    study_id=study.id,
                    pipeline_id=pipeline.id,
                    job_id=job.id,
                    node_id=node_id,
                    node_type=node_type,
                    input_slot=input_slot,
                    input_index=input_index,
                    input_kind="study_output",
                    dataset_asset_id=_uuid_or_none(reference.get("dataset_asset_id")),
                    recording_id=_uuid_or_none(reference.get("source_dataset_id") or reference.get("dataset_id")),
                    recording_version_id=_uuid_or_none(reference.get("dataset_upload_id") or reference.get("current_upload_id")),
                    dataset_file_id=_uuid_or_none(reference.get("source_dataset_file_id") or reference.get("dataset_file_id")),
                    file_role=reference.get("file_role") or "study_output",
                    storage_uri=storage_uri,
                    logical_path=reference.get("logical_path") or storage_path,
                    upstream_execution_id=upstream_execution_id,
                    upstream_dataset_id=dataset_id,
                    selector_json={
                        "source": "runtime_node_input",
                        "input_slot": input_slot,
                        "source_nodes": reference.get("source_nodes", []),
                    },
                    resolved_metadata_json={
                        "study_output_snapshot": _compact_reference(reference),
                        "upstream_execution_id": str(upstream_execution_id) if upstream_execution_id else None,
                        "upstream_dataset_id": str(dataset_id),
                    },
                    sha256=sha256,
                )
            )
            existing_inputs.add(input_key)
            added += 1

        if upstream_execution_id is None or upstream_execution_id == _uuid_or_none(execution.id):
            continue

        dependency_key = (str(upstream_execution_id), str(dataset_id), "upstream_study_output")
        if dependency_key in existing_dependencies:
            continue
        db.add(
            PipelineExecutionDependency(
                study_id=study.id,
                execution_id=execution.id,
                depends_on_execution_id=upstream_execution_id,
                upstream_dataset_id=dataset_id,
                dependency_kind="upstream_study_output",
                metadata_json={
                    "node_id": node_id,
                    "node_type": node_type,
                    "job_id": str(getattr(job, "id", "")),
                    "input_slot": input_slot,
                    "input_index": input_index,
                    "storage_uri": storage_uri,
                    "storage_path": storage_path,
                    "content_hash": reference.get("content_hash"),
                    "sha256": sha256,
                },
            )
        )
        existing_dependencies.add(dependency_key)
        added += 1

    if added:
        db.flush()
    return added


def assert_artifact_can_be_deleted(
    db: Session,
    *,
    artifact: Any,
    limit: int = 20,
) -> None:
    blockers = artifact_dependency_blockers(db, artifact=artifact, limit=limit)
    if blockers:
        raise ArtifactDependencyError(str(artifact.id), blockers)


def artifact_dependency_blockers(
    db: Session,
    *,
    artifact: Any,
    limit: int = 20,
) -> list[dict[str, Any]]:
    artifact_id = _uuid_or_none(getattr(artifact, "id", None))
    if artifact_id is None:
        return []

    blockers: list[dict[str, Any]] = []
    input_rows = (
        db.query(PipelineExecutionInput)
        .filter(PipelineExecutionInput.upstream_dataset_id == artifact_id)
        .order_by(PipelineExecutionInput.created_at.asc(), PipelineExecutionInput.id.asc())
        .all()
    )
    for row in input_rows:
        blockers.append(_input_blocker(row))
        if len(blockers) >= limit:
            return blockers

    dependency_rows = (
        db.query(PipelineExecutionDependency)
        .filter(PipelineExecutionDependency.upstream_dataset_id == artifact_id)
        .order_by(PipelineExecutionDependency.created_at.asc(), PipelineExecutionDependency.id.asc())
        .all()
    )
    seen = {(item.get("source"), item.get("execution_id"), item.get("upstream_dataset_id")) for item in blockers}
    for row in dependency_rows:
        blocker = _dependency_blocker(row)
        key = (blocker.get("source"), blocker.get("execution_id"), blocker.get("upstream_dataset_id"))
        if key not in seen:
            blockers.append(blocker)
            seen.add(key)
        if len(blockers) >= limit:
            return blockers
    return blockers


def study_downstream_dependency_blockers(
    db: Session,
    *,
    study_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    execution_ids = _ids_for_study(db, PipelineExecution, study_id)
    study_output_ids = _ids_for_study(db, StudyOutput, study_id)
    blockers: list[dict[str, Any]] = []

    if study_output_ids:
        input_rows = (
            db.query(PipelineExecutionInput)
            .filter(PipelineExecutionInput.upstream_dataset_id.in_(study_output_ids))
            .order_by(PipelineExecutionInput.created_at.asc(), PipelineExecutionInput.id.asc())
            .all()
        )
        for row in input_rows:
            blockers.append(_input_blocker(row))
            if len(blockers) >= limit:
                return blockers

    dependency_filters = []
    if execution_ids:
        dependency_filters.append(PipelineExecutionDependency.depends_on_execution_id.in_(execution_ids))
    if study_output_ids:
        dependency_filters.append(PipelineExecutionDependency.upstream_dataset_id.in_(study_output_ids))
    if dependency_filters:
        dependency_rows = (
            db.query(PipelineExecutionDependency)
            .filter(or_(*dependency_filters))
            .order_by(PipelineExecutionDependency.created_at.asc(), PipelineExecutionDependency.id.asc())
            .all()
        )
        for row in dependency_rows:
            blockers.append(_dependency_blocker(row))
            if len(blockers) >= limit:
                return blockers
    return blockers


def _collect_artifact_references(inputs: dict[str, NodeInput]) -> list[dict[str, Any]]:
    """Collect references with study_output_id (or legacy artifact_id) from node inputs."""
    references: list[dict[str, Any]] = []
    for port, node_input in inputs.items():
        source_nodes = node_input.metadata.get("source_nodes", []) if isinstance(node_input.metadata, dict) else []
        for index, data_info in enumerate(node_input.data_infos):
            if not isinstance(data_info, dict):
                continue
            reference = dict(data_info)
            reference["input_slot"] = port
            reference["input_index"] = index
            reference["source_nodes"] = source_nodes
            if reference.get("study_output_id") or reference.get("artifact_id"):
                references.append(reference)
        for index, artifact in enumerate(node_input.artifacts, start=len(node_input.data_infos)):
            if not isinstance(artifact, dict):
                continue
            reference = dict(artifact)
            reference["input_slot"] = port
            reference["input_index"] = index
            reference["source_nodes"] = source_nodes
            if reference.get("study_output_id") or reference.get("artifact_id"):
                references.append(reference)
    return references


def _existing_input_keys(db: Session, *, execution_id: Any, job_id: Any) -> set[tuple[str, int, str, str | None]]:
    try:
        rows = (
            db.query(PipelineExecutionInput)
            .filter(
                PipelineExecutionInput.execution_id == execution_id,
                PipelineExecutionInput.job_id == job_id,
                PipelineExecutionInput.input_kind.in_(("study_output", "artifact")),
            )
            .all()
        )
    except Exception:
        return set()
    keys = set()
    for row in rows:
        keys.add(
            (
                str(getattr(row, "input_slot", "") or ""),
                int(getattr(row, "input_index", 0) or 0),
                str(getattr(row, "upstream_dataset_id", "") or ""),
                str(getattr(row, "upstream_execution_id", "") or None) if getattr(row, "upstream_execution_id", None) else None,
            )
        )
    return keys


def _existing_dependency_keys(db: Session, *, execution_id: Any) -> set[tuple[str, str | None, str]]:
    try:
        rows = db.query(PipelineExecutionDependency).filter(PipelineExecutionDependency.execution_id == execution_id).all()
    except Exception:
        return set()
    keys = set()
    for row in rows:
        keys.add(
            (
                str(getattr(row, "depends_on_execution_id", "") or ""),
                str(getattr(row, "upstream_dataset_id", "") or None) if getattr(row, "upstream_dataset_id", None) else None,
                str(getattr(row, "dependency_kind", "") or ""),
            )
        )
    return keys


def _study_output_for_reference(db: Session, dataset_id: UUID) -> Any | None:
    try:
        return db.query(StudyOutput).filter(StudyOutput.id == dataset_id).first()
    except Exception:
        return None


def _ids_for_study(db: Session, model: type[Any], study_id: str) -> list[Any]:
    try:
        rows = db.query(model.id).filter(model.study_id == study_id).all()
    except Exception:
        return []
    values = []
    for row in rows:
        if isinstance(row, tuple):
            values.append(row[0])
        else:
            values.append(getattr(row, "id", row))
    return values


def _input_blocker(row: Any) -> dict[str, Any]:
    return {
        "source": "pipeline_execution_inputs",
        "execution_id": _string_or_none(getattr(row, "execution_id", None)),
        "study_id": _string_or_none(getattr(row, "study_id", None)),
        "pipeline_id": getattr(row, "pipeline_id", None),
        "node_id": getattr(row, "node_id", None),
        "node_type": getattr(row, "node_type", None),
        "input_slot": getattr(row, "input_slot", None),
        "input_index": getattr(row, "input_index", None),
        "upstream_execution_id": _string_or_none(getattr(row, "upstream_execution_id", None)),
        "upstream_dataset_id": _string_or_none(getattr(row, "upstream_dataset_id", None)),
        "storage_uri": getattr(row, "storage_uri", None),
    }


def _dependency_blocker(row: Any) -> dict[str, Any]:
    return {
        "source": "pipeline_execution_dependencies",
        "execution_id": _string_or_none(getattr(row, "execution_id", None)),
        "study_id": _string_or_none(getattr(row, "study_id", None)),
        "depends_on_execution_id": _string_or_none(getattr(row, "depends_on_execution_id", None)),
        "upstream_dataset_id": _string_or_none(getattr(row, "upstream_dataset_id", None)),
        "dependency_kind": getattr(row, "dependency_kind", None),
        "metadata_json": getattr(row, "metadata_json", None) or {},
    }


def _compact_reference(reference: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "artifact_id",
        "pipeline_execution_id",
        "execution_id",
        "job_id",
        "source_dataset_id",
        "dataset_id",
        "dataset_file_id",
        "source_dataset_file_id",
        "file_role",
        "storage_uri",
        "storage_path",
        "artifact_storage_uri",
        "artifact_storage_path",
        "logical_path",
        "sha256",
        "content_hash",
        "checksum",
        "data_type",
    )
    return {key: reference.get(key) for key in keys if key in reference}


def _uuid_or_none(value: Any) -> UUID | None:
    if value in (None, ""):
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _string_or_none(value: Any) -> str | None:
    return str(value) if value is not None else None
