"""
Purpose: Build immutable Pipeline Execution manifests and write them into Study storage.
Related: app/pipeline/executor.py, app/tasks/pipeline_tasks.py, app/routers/pipelines.py, docs_v2/5-30.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import (
    AsyncTask,
    StudyOutput,
    PipelineDefinition,
    PipelineJob,
    PipelineExecution,
    PipelineExecutionDependency,
    PipelineExecutionInput,
    Study,
    TaskEvent,
)
from app.services.storage import StorageService


MANIFEST_VERSION = "elys-execution-manifest-v1"
MANIFEST_FILENAME = "execution_manifest.json"
MANIFEST_TERMINAL_STATUSES = {"completed", "failed", "waiting_user_input", "canceled"}


def should_generate_execution_manifest(execution: PipelineExecution) -> bool:
    return str(getattr(execution, "status", "") or "") in MANIFEST_TERMINAL_STATUSES


def execution_manifest_relative_path(execution_id: str | UUID) -> str:
    return f"executions/{execution_id}/{MANIFEST_FILENAME}"


def execution_logs_relative_path(execution_id: str | UUID) -> str:
    return f"executions/{execution_id}/logs"


def execution_manifest_storage_uri(study_id: str, execution_id: str | UUID) -> str:
    return f"elys://studies/{study_id}/{execution_manifest_relative_path(execution_id)}"


def execution_logs_storage_uri(study_id: str, execution_id: str | UUID) -> str:
    return f"elys://studies/{study_id}/{execution_logs_relative_path(execution_id)}"


def execution_manifest_path(study_id: str, execution_id: str | UUID) -> Path:
    return StorageService().study_root(study_id) / execution_manifest_relative_path(execution_id)


def execution_logs_path(study_id: str, execution_id: str | UUID) -> Path:
    return StorageService().study_root(study_id) / execution_logs_relative_path(execution_id)


def generate_execution_manifest(
    db: Session,
    *,
    study: Study,
    execution: PipelineExecution,
    pipeline: PipelineDefinition | None = None,
) -> dict[str, Any]:
    """Write an execution manifest into Study storage and update pipeline_executions.manifest_json."""

    inputs = _query_inputs(db, study_id=study.id, execution_id=execution.id)
    dependencies = _query_dependencies(db, study_id=study.id, execution_id=execution.id)
    jobs = _query_jobs(db, study_id=study.id, execution_id=execution.id)
    artifacts = _query_artifacts(db, study_id=study.id, execution_id=execution.id)
    tasks, task_events_by_task_id = _query_tasks(db, study_id=study.id, execution_id=execution.id)

    definition_snapshot = _jsonable(getattr(execution, "definition_snapshot", None) or {})
    definition_hash = _stable_sha256(definition_snapshot)
    errors = _list_from_json(getattr(execution, "error_json", None), "errors")
    warnings = _list_from_json(getattr(execution, "result_json", None), "warnings")
    manifest_uri = execution_manifest_storage_uri(study.id, execution.id)
    logs_uri = execution_logs_storage_uri(study.id, execution.id)
    generated_at = _utc_now_iso()

    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "generated_at": generated_at,
        "study": {
            "id": str(study.id),
            "name": getattr(study, "name", None),
        },
        "execution": {
            "id": str(execution.id),
            "study_id": str(getattr(execution, "study_id", study.id)),
            "pipeline_id": getattr(execution, "pipeline_id", None),
            "pipeline_version": getattr(execution, "pipeline_version", None),
            "execution_seq": getattr(execution, "execution_seq", None),
            "trigger": getattr(execution, "trigger", None),
            "status": getattr(execution, "status", None),
            "execution_mode": getattr(execution, "execution_mode", None),
            "node_count": getattr(execution, "node_count", None),
            "dataset_count": getattr(execution, "dataset_count", None),
            "started_by": _string_or_none(getattr(execution, "started_by", None)),
            "started_at": _iso_or_none(getattr(execution, "started_at", None)),
            "finished_at": _iso_or_none(getattr(execution, "finished_at", None)),
        },
        "pipeline": {
            "id": getattr(pipeline, "id", getattr(execution, "pipeline_id", None)),
            "name": getattr(pipeline, "name", None) if pipeline is not None else None,
            "version": getattr(pipeline, "version", getattr(execution, "pipeline_version", None)),
        },
        "definition_snapshot": definition_snapshot,
        "definition_snapshot_hash": definition_hash,
        "inputs": [_serialize_execution_input(item) for item in inputs],
        "outputs": {
            "jobs": [_serialize_job(item) for item in jobs],
            "artifacts": [_serialize_artifact(item) for item in artifacts],
            "data_infos_by_node": _jsonable((getattr(execution, "result_json", None) or {}).get("data_infos_by_node", {})),
            "node_results": _jsonable((getattr(execution, "result_json", None) or {}).get("node_results", [])),
        },
        "dependencies": [_serialize_dependency(item) for item in dependencies],
        "tasks": [_serialize_task(item, task_events_by_task_id.get(item.id, [])) for item in tasks],
        "software": _software_snapshot(),
        "storage": {
            "manifest_uri": manifest_uri,
            "manifest_path": execution_manifest_relative_path(execution.id),
            "logs_uri": logs_uri,
            "logs_path": execution_logs_relative_path(execution.id),
        },
        "errors": _jsonable(errors),
        "warnings": _jsonable(warnings),
    }

    manifest_path = execution_manifest_path(study.id, execution.id)
    logs_path = execution_logs_path(study.id, execution.id)
    logs_path.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(manifest_path, manifest)

    execution.manifest_json = {
        "manifest_version": MANIFEST_VERSION,
        "manifest_uri": manifest_uri,
        "manifest_path": execution_manifest_relative_path(execution.id),
        "logs_uri": logs_uri,
        "logs_path": execution_logs_relative_path(execution.id),
        "generated_at": generated_at,
        "execution_id": str(execution.id),
        "status": getattr(execution, "status", None),
        "definition_snapshot_hash": definition_hash,
        "input_count": len(inputs),
        "artifact_count": len(artifacts),
        "dependency_count": len(dependencies),
        "task_count": len(tasks),
        "job_count": len(jobs),
        "error_count": len(errors),
        "warning_count": len(warnings),
    }
    return manifest


def read_execution_manifest(study: Study, execution: PipelineExecution) -> dict[str, Any]:
    path = execution_manifest_path(study.id, execution.id)
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return _jsonable(data)


def ensure_execution_manifest(
    db: Session,
    *,
    study: Study,
    execution: PipelineExecution,
    pipeline: PipelineDefinition | None = None,
) -> dict[str, Any]:
    path = execution_manifest_path(study.id, execution.id)
    if path.exists():
        return read_execution_manifest(study, execution)
    return generate_execution_manifest(db, study=study, execution=execution, pipeline=pipeline)


def _query_inputs(db: Session, *, study_id: str, execution_id: str | UUID) -> list[PipelineExecutionInput]:
    return (
        db.query(PipelineExecutionInput)
        .filter(PipelineExecutionInput.study_id == study_id, PipelineExecutionInput.execution_id == execution_id)
        .order_by(PipelineExecutionInput.node_id.asc(), PipelineExecutionInput.input_index.asc(), PipelineExecutionInput.created_at.asc())
        .all()
    )


def _query_dependencies(db: Session, *, study_id: str, execution_id: str | UUID) -> list[PipelineExecutionDependency]:
    return (
        db.query(PipelineExecutionDependency)
        .filter(PipelineExecutionDependency.study_id == study_id, PipelineExecutionDependency.execution_id == execution_id)
        .order_by(PipelineExecutionDependency.created_at.asc(), PipelineExecutionDependency.id.asc())
        .all()
    )


def _query_jobs(db: Session, *, study_id: str, execution_id: str | UUID) -> list[PipelineJob]:
    return (
        db.query(PipelineJob)
        .filter(PipelineJob.study_id == study_id, PipelineJob.execution_id == execution_id)
        .order_by(PipelineJob.topo_index.asc(), PipelineJob.node_id.asc())
        .all()
    )


def _query_artifacts(db: Session, *, study_id: str, execution_id: str | UUID) -> list[StudyOutput]:
    return (
        db.query(StudyOutput)
        .filter(StudyOutput.study_id == study_id, StudyOutput.produced_by_execution_id == execution_id)
        .order_by(StudyOutput.created_at.asc(), StudyOutput.id.asc())
        .all()
    )


def _query_tasks(
    db: Session,
    *,
    study_id: str,
    execution_id: str | UUID,
) -> tuple[list[AsyncTask], dict[UUID, list[TaskEvent]]]:
    tasks = (
        db.query(AsyncTask)
        .filter(AsyncTask.study_id == study_id, AsyncTask.resource_kind == "pipeline_execution", AsyncTask.resource_id == execution_id)
        .order_by(AsyncTask.created_at.asc(), AsyncTask.id.asc())
        .all()
    )
    task_events_by_task_id: dict[UUID, list[TaskEvent]] = {task.id: [] for task in tasks}
    task_ids = [task.id for task in tasks]
    if task_ids:
        events = (
            db.query(TaskEvent)
            .filter(TaskEvent.task_id.in_(task_ids))
            .order_by(TaskEvent.created_at.asc(), TaskEvent.id.asc())
            .all()
        )
        for event in events:
            task_events_by_task_id.setdefault(event.task_id, []).append(event)
    return tasks, task_events_by_task_id


def _serialize_execution_input(item: PipelineExecutionInput) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "node_id": item.node_id,
        "node_type": item.node_type,
        "input_slot": item.input_slot,
        "input_index": item.input_index,
        "input_kind": item.input_kind,
        "dataset_asset_id": _string_or_none(item.dataset_asset_id),
        "dataset_id": _string_or_none(item.recording_id),
        "dataset_upload_id": _string_or_none(item.recording_version_id),
        "dataset_file_id": _string_or_none(item.dataset_file_id),
        "file_role": item.file_role,
        "storage_uri": item.storage_uri,
        "logical_path": item.logical_path,
        "upstream_execution_id": _string_or_none(item.upstream_execution_id),
        "upstream_dataset_id": _string_or_none(item.upstream_dataset_id),
        "selector_json": _jsonable(item.selector_json or {}),
        "resolved_metadata_json": _jsonable(item.resolved_metadata_json or {}),
        "sha256": item.sha256,
        "created_at": _iso_or_none(item.created_at),
    }


def _serialize_dependency(item: PipelineExecutionDependency) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "depends_on_execution_id": _string_or_none(item.depends_on_execution_id),
        "upstream_dataset_id": _string_or_none(item.upstream_dataset_id),
        "dependency_kind": item.dependency_kind,
        "metadata_json": _jsonable(item.metadata_json or {}),
        "created_at": _iso_or_none(item.created_at),
    }


def _serialize_job(item: PipelineJob) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "node_id": item.node_id,
        "node_type": item.node_type,
        "node_title": item.node_title,
        "status": item.status,
        "topo_index": item.topo_index,
        "params_json": _jsonable(item.params_json or {}),
        "input_json": _jsonable(item.input_json or {}),
        "output_json": _jsonable(item.output_json or {}),
        "input_hash": item.input_hash,
        "params_hash": item.params_hash,
        "node_hash": item.node_hash,
        "trace_code": item.trace_code,
        "error_json": _jsonable(item.error_json or {}),
        "log_tail": item.log_tail,
        "started_at": _iso_or_none(item.started_at),
        "finished_at": _iso_or_none(item.finished_at),
        "duration_ms": item.duration_ms,
    }


def _serialize_artifact(item: StudyOutput) -> dict[str, Any]:
    """Serialise a StudyOutput row to its Execution manifest snapshot."""
    return {
        "id": str(item.id),
        "study_output_id": str(item.id),
        "produced_by_job_id": _string_or_none(item.produced_by_job_id),
        "produced_by_node_id": item.produced_by_node_id,
        "produced_by_node_type": item.produced_by_node_type,
        "produced_by_params": _jsonable(item.produced_by_params or {}),
        "upstream_dataset_ids": list(item.upstream_dataset_ids or []),
        "upstream_recording_ids": list(item.upstream_recording_ids or []),
        "data_type": item.data_type,
        "subject_id": _string_or_none(item.subject_id),
        "bids_subject_id": item.bids_subject_id,
        "session": item.session,
        "task": item.task,
        "run_label": item.run_label,
        "condition": item.condition,
        "display_name": item.display_name,
        "tags": list(item.tags or []),
        "storage_uri": item.storage_uri,
        "logical_path": item.logical_path,
        "file_role": item.file_role,
        "file_size": item.file_size,
        "sha256": item.sha256,
        "mime_type": item.mime_type,
        "retention_status": item.retention_status,
        "retention_expires_at": _iso_or_none(item.retention_expires_at),
        "deleted_at": _iso_or_none(item.deleted_at),
        "preview_json": _jsonable(item.preview_json or {}),
        "created_at": _iso_or_none(item.created_at),
        "updated_at": _iso_or_none(item.updated_at),
    }


def _serialize_task(item: AsyncTask, events: list[TaskEvent]) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "celery_task_id": item.celery_task_id,
        "task_type": item.task_type,
        "queue_name": item.queue_name,
        "status": item.status,
        "progress": _jsonable(item.progress),
        "resource_kind": item.resource_kind,
        "resource_id": _string_or_none(item.resource_id),
        "payload_json": _jsonable(item.payload_json or {}),
        "result_json": _jsonable(item.result_json or {}),
        "error_json": _jsonable(item.error_json or {}),
        "idempotency_key": item.idempotency_key,
        "created_by": _string_or_none(item.created_by),
        "created_at": _iso_or_none(item.created_at),
        "started_at": _iso_or_none(item.started_at),
        "finished_at": _iso_or_none(item.finished_at),
        "attempt": item.attempt,
        "max_attempts": item.max_attempts,
        "events": [_serialize_task_event(event) for event in events],
    }


def _serialize_task_event(item: TaskEvent) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "event_type": item.event_type,
        "status": item.status,
        "progress": _jsonable(item.progress),
        "message": item.message,
        "payload_json": _jsonable(item.payload_json or {}),
        "created_at": _iso_or_none(item.created_at),
    }


def _software_snapshot() -> dict[str, Any]:
    packages = {}
    for package_name in ("fastapi", "sqlalchemy", "pydantic", "celery", "mne"):
        packages[package_name] = _package_version(package_name)
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": packages,
    }


def _package_version(package_name: str) -> str | None:
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    text = json.dumps(_jsonable(payload), ensure_ascii=False, indent=2, sort_keys=True)
    temp_path.write_text(text + "\n", encoding="utf-8")
    temp_path.replace(path)


def _stable_sha256(payload: Any) -> str:
    encoded = json.dumps(_jsonable(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value


def _list_from_json(value: Any, key: str) -> list[Any]:
    if isinstance(value, dict) and isinstance(value.get(key), list):
        return value[key]
    return []


def _iso_or_none(value: Any) -> str | None:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value) if value else None


def _string_or_none(value: Any) -> str | None:
    return str(value) if value is not None else None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
