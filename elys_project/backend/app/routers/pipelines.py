"""
Purpose: Define FastAPI routes for the pipelines API area and translate HTTP requests into services/database calls.
Related: app/schemas/*, app/models/*, app/services/*, app/routers/auth.py, docs_v2/2-50.
"""

import asyncio
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

try:
    from fastapi.responses import FileResponse, StreamingResponse
except Exception:  # pragma: no cover - lightweight test stubs do not provide fastapi.responses
    class FileResponse:  # type: ignore[no-redef]
        def __init__(self, path, **kwargs):
            self.path = path
            self.kwargs = kwargs

    class StreamingResponse:  # type: ignore[no-redef]
        def __init__(self, content, **kwargs):
            self.content = content
            self.kwargs = kwargs
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal, get_db
from app.models import (
    AsyncTask,
    DerivedDataset,
    PipelineDefinition,
    PipelineJob,
    PipelineExecution,
    PipelineExecutionDependency,
    PipelineExecutionInput,
    Study,
    StudyLock,
    StudySettings,
    TaskEvent,
    User,
)
from app.pipeline import get_node_registry
from app.pipeline.background import run_pipeline_execution_sync
from app.pipeline.executor import PipelineExecutor
from app.pipeline.load_data import resolve_load_data_selection
from app.pipeline.previews import (
    DerivedDatasetPreviewError,
    MAX_EVOKED_CHANNELS,
    build_derived_dataset_preview,
    resolve_derived_dataset_path,
    validate_derived_dataset_file,
)
from app.pipeline.timeseries import build_timeseries
from app.pipeline.execution_manifest import ensure_execution_manifest, generate_execution_manifest
from app.pipeline.selection_override import apply_load_data_selection_overrides, normalize_selection_override
from app.pipeline.validator import validate_definition
from app.routers.auth import get_current_user
from app.schemas.derived_dataset import (
    DerivedDatasetBatchUpdate,
    DerivedDatasetCleanupRequest,
    DerivedDatasetListResponse,
    DerivedDatasetPreviewResponse,
    DerivedDatasetResponse,
    DerivedDatasetUpdate,
)
from app.schemas.pipeline import (
    AsyncTaskResponse,
    AsyncTaskListResponse,
    LoadDataResolveRequest,
    LoadDataResolveResponse,
    NodeSpecListResponse,
    NodeSpecResponse,
    PipelineCreate,
    PipelineInteractionDecisionRequest,
    PipelineInteractionDecisionResponse,
    PipelineInteractionResponse,
    PipelineListResponse,
    PipelineJobListResponse,
    PipelineJobResponse,
    PipelineEditLockResponse,
    PipelineExecutionCreate,
    PipelineExecutionDetailResponse,
    PipelineExecutionDependencyResponse,
    PipelineExecutionInputResponse,
    PipelineExecutionLineageResponse,
    PipelineExecutionListResponse,
    PipelineExecutionRetryRequest,
    PipelineExecutionResponse,
    PipelineResumeResponse,
    PipelineResponse,
    PipelineUpdate,
    PipelineValidationResponse,
    TaskEventResponse,
    TaskEventListResponse,
    TaskStatus,
)
from app.services.audit_events import record_audit_event
from app.services.pipeline_execution_rules import pipeline_execution_status_violation
from app.services.study_access import require_study_read, require_study_run, require_study_write
from app.services.study_locks import (
    DEFAULT_STUDY_LOCK_TTL_SECONDS,
    StudyLockConflictError,
    acquire_study_lock,
    find_active_study_lock,
    force_release_stale_pipeline_execution_locks,
    refresh_study_lock,
    release_study_lock,
    release_study_lock_by_id,
    release_study_locks_for_resource,
)
from app.services.execution_dependencies import ArtifactDependencyError, assert_artifact_can_be_deleted
from app.services.task_events import record_task_event, task_status_for_pipeline_execution
from app.tasks.pipeline_tasks import run_pipeline_task


router = APIRouter(prefix="/api/v1", tags=["工作流"])

PIPELINE_EDIT_LOCK_TTL_SECONDS = 30 * 60
RUN_CANCELABLE_STATUSES = {"queued", "running", "waiting_user_input"}
RUN_CANCELLED_STATUS = "canceled"
RUN_RETRYABLE_STATUSES = {"failed", "canceled"}
TASK_CANCELABLE_STATUSES = {"queued", "running", "retrying"}
TASK_RETRYABLE_STATUSES = {"failed", "canceled"}
FILE_TASK_TYPES = {"derived_dataset_cleanup", "dataset_import", "raw_bids_build", "canonical_fif_rebuild"}
TASK_EVENT_STREAM_BATCH_LIMIT = 100
TASK_EVENT_STREAM_POLL_INTERVAL_SECONDS = 1.0
TASK_EVENT_STREAM_HEARTBEAT_SECONDS = 15.0
TASK_EVENT_STREAM_MAX_SECONDS = 300.0
ARTIFACT_DELETED_STATUS = "deleted"
PIPELINE_EXECUTION_MODES = {"auto", "celery", "inline"}


def count_nodes(definition_json: dict[str, Any]) -> int:
    graph = definition_json.get("graph") or {}
    nodes = graph.get("nodes") or []
    return len(nodes) if isinstance(nodes, list) else 0


def pipeline_to_response(pipeline: PipelineDefinition) -> PipelineResponse:
    return PipelineResponse(
        id=pipeline.id,
        study_id=pipeline.study_id,
        name=pipeline.name,
        description=pipeline.description,
        definition_json=pipeline.definition_json,
        node_count=pipeline.node_count,
        version=pipeline.version,
        is_template=pipeline.is_template,
        status=pipeline.status,
        created_by=str(pipeline.created_by) if pipeline.created_by else None,
        created_at=pipeline.created_at,
        updated_at=pipeline.updated_at,
    )


def pipeline_edit_lock_to_response(lock: StudyLock, pipeline_id: int) -> PipelineEditLockResponse:
    return PipelineEditLockResponse(
        id=str(lock.id),
        study_id=lock.study_id,
        pipeline_id=pipeline_id,
        resource_kind=lock.resource_kind,
        resource_id=lock.resource_id,
        lock_type=lock.lock_type,
        locked_by=str(lock.locked_by) if lock.locked_by else None,
        locked_at=lock.locked_at,
        expires_at=lock.expires_at,
        released_at=lock.released_at,
        metadata_json=lock.metadata_json or {},
    )


def pipeline_edit_lock_conflict_detail(
    study: Study,
    pipeline: PipelineDefinition,
    lock: StudyLock | None,
) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "code": "PIPELINE_EDIT_LOCKED",
        "message": "该工作流正在被其他用户编辑，请等待锁释放或过期后再保存。",
        "study_id": study.id,
        "pipeline_id": pipeline.id,
    }
    if lock is not None:
        detail.update(
            {
                "lock_id": str(lock.id),
                "lock_type": lock.lock_type,
                "locked_by": str(lock.locked_by) if lock.locked_by else None,
                "locked_at": lock.locked_at.isoformat() if lock.locked_at else None,
                "expires_at": lock.expires_at.isoformat() if lock.expires_at else None,
            }
        )
    return detail


def is_lock_owned_by(lock: StudyLock, user: User) -> bool:
    return lock.locked_by is not None and str(lock.locked_by) == str(user.id)


def find_active_pipeline_edit_lock(
    db: Session,
    *,
    study: Study,
    pipeline: PipelineDefinition,
) -> StudyLock | None:
    return find_active_study_lock(
        db,
        study_id=study.id,
        resource_kind="pipeline",
        resource_id=pipeline.id,
        lock_type="edit",
    )


def ensure_pipeline_edit_lock_available(
    db: Session,
    *,
    study: Study,
    pipeline: PipelineDefinition,
    current_user: User,
) -> StudyLock | None:
    lock = find_active_pipeline_edit_lock(db, study=study, pipeline=pipeline)
    if lock is not None and not is_lock_owned_by(lock, current_user):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=pipeline_edit_lock_conflict_detail(study, pipeline, lock),
        )
    return lock


def acquire_or_refresh_pipeline_edit_lock(
    db: Session,
    *,
    study: Study,
    pipeline: PipelineDefinition,
    current_user: User,
    reason: str,
) -> tuple[StudyLock, bool]:
    existing = find_active_pipeline_edit_lock(db, study=study, pipeline=pipeline)
    if existing is not None:
        if not is_lock_owned_by(existing, current_user):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=pipeline_edit_lock_conflict_detail(study, pipeline, existing),
            )
        refreshed = refresh_study_lock(
            db,
            existing,
            ttl_seconds=PIPELINE_EDIT_LOCK_TTL_SECONDS,
            refreshed_by=current_user.id,
            reason=reason,
        )
        return refreshed, False

    try:
        lock = acquire_study_lock(
            db,
            study_id=study.id,
            resource_kind="pipeline",
            resource_id=pipeline.id,
            lock_type="edit",
            locked_by=current_user.id,
            ttl_seconds=PIPELINE_EDIT_LOCK_TTL_SECONDS,
            metadata={
                "pipeline_id": pipeline.id,
                "pipeline_version": pipeline.version,
                "reason": reason,
            },
        )
    except StudyLockConflictError as exc:
        if exc.lock is not None and is_lock_owned_by(exc.lock, current_user):
            refreshed = refresh_study_lock(
                db,
                exc.lock,
                ttl_seconds=PIPELINE_EDIT_LOCK_TTL_SECONDS,
                refreshed_by=current_user.id,
                reason=reason,
            )
            return refreshed, False
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=pipeline_edit_lock_conflict_detail(study, pipeline, exc.lock),
        ) from exc
    return lock, True


def pipeline_execution_to_response(execution: PipelineExecution) -> PipelineExecutionResponse:
    return PipelineExecutionResponse(
        id=str(execution.id),
        study_id=execution.study_id,
        pipeline_id=execution.pipeline_id,
        pipeline_version=execution.pipeline_version,
        execution_seq=execution.execution_seq,
        trigger=execution.trigger,
        execution_mode=getattr(execution, "execution_mode", None) or "analysis",
        save_policy=getattr(execution, "save_policy", None) or "current",
        status=execution.status,
        node_count=execution.node_count,
        dataset_count=execution.dataset_count,
        definition_snapshot=execution.definition_snapshot or {},
        manifest_json=execution.manifest_json or {},
        result_json=execution.result_json or {},
        error_json=execution.error_json or {},
        started_by=str(execution.started_by) if execution.started_by else None,
        started_at=execution.started_at,
        finished_at=execution.finished_at,
    )


def pipeline_job_to_response(job: PipelineJob) -> PipelineJobResponse:
    return PipelineJobResponse(
        id=str(job.id),
        execution_id=str(job.execution_id),
        study_id=job.study_id,
        pipeline_id=job.pipeline_id,
        node_id=job.node_id,
        node_type=job.node_type,
        node_title=job.node_title,
        status=job.status,
        topo_index=job.topo_index,
        params_json=job.params_json or {},
        input_json=job.input_json or {},
        output_json=job.output_json or {},
        input_hash=job.input_hash,
        params_hash=job.params_hash,
        node_hash=job.node_hash,
        trace_code=job.trace_code,
        error_json=job.error_json or {},
        log_tail=job.log_tail,
        started_at=job.started_at,
        finished_at=job.finished_at,
        duration_ms=job.duration_ms,
    )


def _to_str_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def derived_dataset_to_response(dataset: DerivedDataset) -> DerivedDatasetResponse:
    return DerivedDatasetResponse(
        id=str(dataset.id),
        study_id=dataset.study_id,
        produced_by_execution_id=str(dataset.produced_by_execution_id) if dataset.produced_by_execution_id else None,
        produced_by_job_id=str(dataset.produced_by_job_id) if dataset.produced_by_job_id else None,
        produced_by_node_id=dataset.produced_by_node_id,
        produced_by_node_type=dataset.produced_by_node_type,
        produced_by_params=dataset.produced_by_params or {},
        upstream_dataset_ids=_to_str_list(dataset.upstream_dataset_ids),
        upstream_recording_ids=_to_str_list(dataset.upstream_recording_ids),
        data_type=dataset.data_type,
        subject_id=str(dataset.subject_id) if dataset.subject_id else None,
        bids_subject_id=dataset.bids_subject_id,
        session=dataset.session,
        task=dataset.task,
        run_label=dataset.run_label,
        condition=dataset.condition,
        display_name=dataset.display_name,
        description=dataset.description,
        tags=_to_str_list(dataset.tags),
        storage_uri=dataset.storage_uri or "",
        logical_path=dataset.logical_path,
        file_role=dataset.file_role,
        file_size=dataset.file_size,
        sha256=dataset.sha256,
        mime_type=dataset.mime_type,
        retention_status=dataset.retention_status,
        retention_expires_at=dataset.retention_expires_at,
        preview_json=dataset.preview_json or {},
        created_at=dataset.created_at,
        created_by=str(dataset.created_by) if dataset.created_by else None,
        updated_at=dataset.updated_at,
        deleted_at=dataset.deleted_at,
    )


def pipeline_execution_input_to_response(execution_input: PipelineExecutionInput) -> PipelineExecutionInputResponse:
    return PipelineExecutionInputResponse(
        id=str(execution_input.id),
        execution_id=str(execution_input.execution_id),
        study_id=execution_input.study_id,
        pipeline_id=execution_input.pipeline_id,
        job_id=str(execution_input.job_id) if execution_input.job_id else None,
        node_id=execution_input.node_id,
        node_type=execution_input.node_type,
        input_slot=execution_input.input_slot,
        input_index=execution_input.input_index,
        input_kind=execution_input.input_kind,
        dataset_asset_id=str(execution_input.dataset_asset_id) if execution_input.dataset_asset_id else None,
        dataset_id=str(execution_input.recording_id) if execution_input.recording_id else None,
        dataset_upload_id=str(execution_input.recording_version_id) if execution_input.recording_version_id else None,
        dataset_file_id=str(execution_input.dataset_file_id) if execution_input.dataset_file_id else None,
        file_role=execution_input.file_role,
        storage_uri=execution_input.storage_uri,
        logical_path=execution_input.logical_path,
        upstream_execution_id=str(execution_input.upstream_execution_id) if execution_input.upstream_execution_id else None,
        upstream_dataset_id=str(execution_input.upstream_dataset_id) if execution_input.upstream_dataset_id else None,
        selector_json=execution_input.selector_json or {},
        resolved_metadata_json=execution_input.resolved_metadata_json or {},
        sha256=execution_input.sha256,
        created_at=execution_input.created_at,
    )


def pipeline_execution_dependency_to_response(dependency: PipelineExecutionDependency) -> PipelineExecutionDependencyResponse:
    return PipelineExecutionDependencyResponse(
        id=str(dependency.id),
        study_id=dependency.study_id,
        execution_id=str(dependency.execution_id),
        depends_on_execution_id=str(dependency.depends_on_execution_id),
        upstream_dataset_id=str(dependency.upstream_dataset_id) if dependency.upstream_dataset_id else None,
        dependency_kind=dependency.dependency_kind,
        metadata_json=dependency.metadata_json or {},
        created_at=dependency.created_at,
    )


def lineage_execution_node_id(execution_id: UUID | str) -> str:
    return f"execution:{execution_id}"


def lineage_input_node_id(input_id: UUID | str) -> str:
    return f"input:{input_id}"


def lineage_derived_dataset_node_id(dataset_id: UUID | str) -> str:
    return f"derived_dataset:{dataset_id}"


# Backward-compatible alias; older code paths may still call this name.
lineage_artifact_node_id = lineage_derived_dataset_node_id


def add_lineage_graph_node(
    nodes: dict[str, dict[str, Any]],
    *,
    node_id: str,
    node_type: str,
    label: str,
    resource_kind: str,
    resource_id: UUID | str,
    status: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    nodes.setdefault(
        node_id,
        {
            "id": node_id,
            "node_type": node_type,
            "label": label,
            "resource_kind": resource_kind,
            "resource_id": str(resource_id),
            "status": status,
            "metadata_json": metadata or {},
        },
    )


def add_lineage_graph_edge(
    edges: dict[str, dict[str, Any]],
    *,
    edge_id: str,
    source: str,
    target: str,
    edge_type: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    edges.setdefault(
        edge_id,
        {
            "id": edge_id,
            "source": source,
            "target": target,
            "edge_type": edge_type,
            "metadata_json": metadata or {},
        },
    )


def task_event_to_response(event: TaskEvent) -> TaskEventResponse:
    return TaskEventResponse(
        id=str(event.id),
        task_id=str(event.task_id),
        event_type=event.event_type,
        status=event.status,
        progress=float(event.progress) if event.progress is not None else None,
        message=event.message,
        payload_json=event.payload_json or {},
        created_at=event.created_at,
    )


def async_task_to_response(task: AsyncTask, events: list[TaskEvent] | None = None) -> AsyncTaskResponse:
    return AsyncTaskResponse(
        id=str(task.id),
        celery_task_id=task.celery_task_id,
        task_type=task.task_type,
        queue_name=task.queue_name,
        status=task.status,
        progress=float(task.progress or 0),
        study_id=task.study_id,
        resource_kind=task.resource_kind,
        resource_id=str(task.resource_id) if task.resource_id else None,
        payload_json=task.payload_json or {},
        result_json=task.result_json or {},
        error_json=task.error_json or {},
        idempotency_key=task.idempotency_key,
        created_by=str(task.created_by) if task.created_by else None,
        created_at=task.created_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
        attempt=task.attempt,
        max_attempts=task.max_attempts,
        events=[task_event_to_response(event) for event in (events or [])],
    )


def get_study_for_read(study_id: str, db: Session, user: User) -> Study:
    study = db.query(Study).filter(Study.id == study_id).first()
    return require_study_read(study, db, user)


def get_study_for_write(study_id: str, db: Session, user: User) -> Study:
    study = db.query(Study).filter(Study.id == study_id).first()
    return require_study_write(study, db, user)


def get_study_for_run(study_id: str, db: Session, user: User) -> Study:
    study = db.query(Study).filter(Study.id == study_id).first()
    return require_study_run(study, db, user)


def get_pipeline_or_404(db: Session, study_id: str, pipeline_id: int) -> PipelineDefinition:
    pipeline = (
        db.query(PipelineDefinition)
        .filter(
            PipelineDefinition.study_id == study_id,
            PipelineDefinition.id == pipeline_id,
            PipelineDefinition.status != "deleted",
        )
        .first()
    )
    if pipeline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")
    return pipeline


def get_pipeline_execution_or_404(db: Session, study_id: str, execution_id: UUID) -> PipelineExecution:
    execution = db.query(PipelineExecution).filter(PipelineExecution.study_id == study_id, PipelineExecution.id == execution_id).first()
    if execution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline execution not found")
    return execution


def get_pipeline_job_or_404(db: Session, study_id: str, execution_id: UUID, job_id: UUID) -> PipelineJob:
    job = (
        db.query(PipelineJob)
        .filter(
            PipelineJob.study_id == study_id,
            PipelineJob.execution_id == execution_id,
            PipelineJob.id == job_id,
        )
        .first()
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline node execution not found")
    return job


def get_derived_dataset_or_404(db: Session, study_id: str, dataset_id: UUID) -> DerivedDataset:
    dataset = (
        db.query(DerivedDataset)
        .filter(DerivedDataset.study_id == study_id, DerivedDataset.id == dataset_id)
        .first()
    )
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Derived dataset not found")
    return dataset


def derived_dataset_hidden_conflict_detail(dataset: DerivedDataset, *, operation: str) -> dict[str, Any]:
    return {
        "code": "DERIVED_DATASET_HIDDEN",
        "message": "已隐藏的派生数据集不能再被 pin/unpin。如果要恢复，请显式调用 PATCH 把 retention_status 切回 current。",
        "derived_dataset_id": str(dataset.id),
        "operation": operation,
        "retention_status": dataset.retention_status,
    }


def record_derived_dataset_action_audit(
    db: Session,
    *,
    study: Study,
    dataset: DerivedDataset,
    current_user: User,
    action: str,
    reason: str | None,
    operation: str,
    previous_status: str,
    target_status: str,
    blocked: bool = False,
    dependencies: list[dict[str, Any]] | None = None,
) -> None:
    record_audit_event(
        db,
        study_id=study.id,
        action=action,
        actor_id=current_user.id,
        resource_kind="derived_dataset",
        resource_id=dataset.id,
        resource_label=dataset.display_name or dataset.storage_uri,
        metadata={
            "operation": operation,
            "previous_status": previous_status,
            "retention_status": target_status,
            "reason": reason,
            "execution_id": str(dataset.produced_by_execution_id) if dataset.produced_by_execution_id else None,
            "blocked": blocked,
            "dependencies": dependencies or [],
        },
    )


def apply_derived_dataset_retention_action(
    db: Session,
    *,
    study: Study,
    dataset: DerivedDataset,
    current_user: User,
    target_status: str,
    action: str,
    reason: str | None = None,
    operation: str = "retention_update",
    allow_restore_deleted: bool = True,
) -> DerivedDataset:
    previous_status = dataset.retention_status
    if previous_status == ARTIFACT_DELETED_STATUS and target_status != ARTIFACT_DELETED_STATUS and not allow_restore_deleted:
        record_derived_dataset_action_audit(
            db,
            study=study,
            dataset=dataset,
            current_user=current_user,
            action=f"{action}.blocked",
            reason=reason,
            operation=operation,
            previous_status=previous_status,
            target_status=target_status,
            blocked=True,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=derived_dataset_hidden_conflict_detail(dataset, operation=operation),
        )
    if target_status == ARTIFACT_DELETED_STATUS:
        try:
            assert_artifact_can_be_deleted(db, artifact=dataset)
        except ArtifactDependencyError as exc:
            record_derived_dataset_action_audit(
                db,
                study=study,
                dataset=dataset,
                current_user=current_user,
                action=f"{action}.blocked",
                reason=reason,
                operation=operation,
                previous_status=previous_status,
                target_status=target_status,
                blocked=True,
                dependencies=exc.blockers,
            )
            db.commit()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.to_detail()) from exc

    dataset.retention_status = target_status
    if target_status == ARTIFACT_DELETED_STATUS:
        dataset.deleted_at = datetime.utcnow()
    else:
        dataset.deleted_at = None
    if target_status in ("current", "pinned"):
        dataset.retention_expires_at = None
    dataset.updated_at = datetime.utcnow()

    record_derived_dataset_action_audit(
        db,
        study=study,
        dataset=dataset,
        current_user=current_user,
        action=action,
        reason=reason,
        operation=operation,
        previous_status=previous_status,
        target_status=dataset.retention_status,
    )
    return dataset


def get_async_task_or_404(db: Session, study_id: str, task_id: UUID) -> AsyncTask:
    task = db.query(AsyncTask).filter(AsyncTask.study_id == study_id, AsyncTask.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


def is_pipeline_execution_task(task: AsyncTask) -> bool:
    return task.task_type == "pipeline_execution" or task.resource_kind == "pipeline_execution"


def task_events_for_response(db: Session, task: AsyncTask) -> list[TaskEvent]:
    return (
        db.query(TaskEvent)
        .filter(TaskEvent.task_id == task.id)
        .order_by(TaskEvent.created_at.asc(), TaskEvent.id.asc())
        .all()
    )


def normalize_task_event_since(db: Session, task_id: UUID, since: str | None) -> datetime | None:
    if not since:
        return None
    try:
        event_id = UUID(str(since))
    except ValueError:
        event_id = None
    if event_id is not None:
        event = db.query(TaskEvent).filter(TaskEvent.task_id == task_id, TaskEvent.id == event_id).first()
        return event.created_at if event is not None else None

    try:
        parsed = datetime.fromisoformat(str(since).replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "TASK_EVENT_CURSOR_INVALID",
                "message": "since must be a task_event id or ISO datetime.",
                "since": since,
            },
        ) from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def query_task_events(
    db: Session,
    task_id: UUID,
    *,
    since: str | None = None,
    limit: int | None = None,
) -> list[TaskEvent]:
    query = db.query(TaskEvent).filter(TaskEvent.task_id == task_id)
    since_at = normalize_task_event_since(db, task_id, since)
    if since_at is not None:
        query = query.filter(TaskEvent.created_at > since_at)
    query = query.order_by(TaskEvent.created_at.asc(), TaskEvent.id.asc())
    if limit is not None:
        query = query.limit(limit)
    return query.all()


def task_event_stream_payload(event: TaskEvent) -> dict[str, Any]:
    return task_event_to_response(event).model_dump(mode="json")


def format_sse_event(
    event_type: str,
    data: dict[str, Any],
    *,
    event_id: str | None = None,
    retry_ms: int | None = None,
) -> str:
    lines: list[str] = []
    if event_id:
        lines.append(f"id: {event_id}")
    if event_type:
        lines.append(f"event: {event_type}")
    if retry_ms is not None:
        lines.append(f"retry: {retry_ms}")
    data_text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    for line in data_text.splitlines() or ["{}"]:
        lines.append(f"data: {line}")
    return "\n".join(lines) + "\n\n"


async def task_event_stream_generator(
    *,
    study_id: str,
    task_id: UUID,
    since: str | None,
    poll_interval_seconds: float,
    heartbeat_seconds: float,
    max_seconds: float,
):
    cursor = since
    stream_started_at = datetime.utcnow()
    last_heartbeat_at = stream_started_at
    retry_ms = max(1000, int(poll_interval_seconds * 1000))
    yield format_sse_event(
        "ready",
        {
            "study_id": study_id,
            "task_id": str(task_id),
            "since": since,
            "stream_started_at": stream_started_at.isoformat() + "Z",
        },
        retry_ms=retry_ms,
    )

    while (datetime.utcnow() - stream_started_at).total_seconds() < max_seconds:
        db = SessionLocal()
        try:
            task_exists = (
                db.query(AsyncTask.id)
                .filter(AsyncTask.study_id == study_id, AsyncTask.id == task_id)
                .first()
                is not None
            )
            if not task_exists:
                yield format_sse_event(
                    "stream_closed",
                    {"task_id": str(task_id), "reason": "task_not_found"},
                    event_id=cursor,
                )
                return
            events = query_task_events(db, task_id, since=cursor, limit=TASK_EVENT_STREAM_BATCH_LIMIT)
        finally:
            db.close()

        if events:
            for event in events:
                cursor = str(event.id)
                yield format_sse_event("task_event", task_event_stream_payload(event), event_id=cursor)
            last_heartbeat_at = datetime.utcnow()
        elif (datetime.utcnow() - last_heartbeat_at).total_seconds() >= heartbeat_seconds:
            yield format_sse_event(
                "heartbeat",
                {
                    "task_id": str(task_id),
                    "cursor": cursor,
                    "created_at": datetime.utcnow().isoformat() + "Z",
                },
                event_id=cursor,
            )
            last_heartbeat_at = datetime.utcnow()

        await asyncio.sleep(poll_interval_seconds)

    yield format_sse_event(
        "stream_closed",
        {"task_id": str(task_id), "cursor": cursor, "reason": "max_seconds"},
        event_id=cursor,
    )


def async_task_cancel_conflict_detail(task: AsyncTask) -> dict[str, Any]:
    return {
        "code": "ASYNC_TASK_NOT_CANCELABLE",
        "message": "该后台任务当前状态不可取消。",
        "task_id": str(task.id),
        "task_type": task.task_type,
        "status": task.status,
        "cancelable_statuses": sorted(TASK_CANCELABLE_STATUSES),
    }


def async_task_retry_conflict_detail(task: AsyncTask) -> dict[str, Any]:
    return {
        "code": "ASYNC_TASK_NOT_RETRYABLE",
        "message": "该后台任务当前状态不可重试。",
        "task_id": str(task.id),
        "task_type": task.task_type,
        "status": task.status,
        "retryable_statuses": sorted(TASK_RETRYABLE_STATUSES),
    }


def async_task_retry_unsupported_detail(task: AsyncTask) -> dict[str, Any]:
    return {
        "code": "ASYNC_TASK_RETRY_UNSUPPORTED",
        "message": "该后台任务类型暂不支持直接重试。",
        "task_id": str(task.id),
        "task_type": task.task_type,
        "supported_task_types": sorted(FILE_TASK_TYPES),
    }


def next_pipeline_execution_seq(db: Session, study_id: str, pipeline_id: int) -> int:
    current = (
        db.query(func.max(PipelineExecution.execution_seq))
        .filter(PipelineExecution.study_id == study_id, PipelineExecution.pipeline_id == pipeline_id)
        .scalar()
    )
    return int(current or 0) + 1


def job_interaction(job: PipelineJob) -> dict[str, Any]:
    output_json = job.output_json or {}
    if isinstance(output_json, dict) and isinstance(output_json.get("interaction"), dict):
        return output_json["interaction"]
    metadata = output_json.get("metadata") if isinstance(output_json, dict) else {}
    if isinstance(metadata, dict) and isinstance(metadata.get("interaction"), dict):
        return metadata["interaction"]
    return {}


def set_job_interaction(job: PipelineJob, interaction: dict[str, Any]) -> None:
    output_json = dict(job.output_json or {})
    metadata = dict(output_json.get("metadata") or {})
    metadata["interaction"] = interaction
    output_json["metadata"] = metadata
    output_json["interaction"] = interaction
    job.output_json = output_json


def interaction_to_response(job: PipelineJob) -> PipelineInteractionResponse:
    interaction = job_interaction(job)
    if not interaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline interaction not found")
    return PipelineInteractionResponse(
        execution_id=str(job.execution_id),
        job_id=str(job.id),
        node_id=job.node_id,
        node_type=job.node_type,
        status=job.status,
        interaction_type=str(interaction.get("type") or "ica_component_selection"),
        decision_version=int(interaction.get("decision_version") or 1),
        components=interaction.get("components") if isinstance(interaction.get("components"), list) else [],
        preview_json=interaction.get("preview_json") if isinstance(interaction.get("preview_json"), dict) else {},
        decision=interaction.get("decision") if isinstance(interaction.get("decision"), dict) else None,
    )


def apply_interaction_decision(
    job: PipelineJob,
    payload: PipelineInteractionDecisionRequest,
    *,
    current_user: User,
) -> None:
    interaction = job_interaction(job)
    if not interaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline interaction not found")
    expected_version = int(interaction.get("decision_version") or 1)
    if payload.decision_version != expected_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "DECISION_CONFLICT",
                "message": "ICA decision version has changed. Refresh the waiting node before submitting again.",
                "expected_version": expected_version,
                "received_version": payload.decision_version,
            },
        )

    excluded_components = sorted({int(item) for item in payload.excluded_components if int(item) >= 0})
    decision = {
        "excluded_components": excluded_components,
        "decision_version": expected_version,
        "submitted_by": str(current_user.id),
        "submitted_at": datetime.utcnow().isoformat() + "Z",
    }
    interaction = {
        **interaction,
        "status": "decision_submitted",
        "decision": decision,
        "decision_version": expected_version + 1,
    }
    set_job_interaction(job, interaction)
    job.params_json = {
        **(job.params_json or {}),
        "excluded_components": excluded_components,
        "decision_version": expected_version,
    }


def mark_execution_dispatch_failed(db: Session, execution: PipelineExecution, message: str) -> None:
    issue = {
        "code": "PIPELINE_EXECUTION_TASK_DISPATCH_FAILED",
        "message": message,
        "severity": "error",
    }
    execution.status = "failed"
    execution.finished_at = datetime.utcnow()
    execution.error_json = {"errors": [issue]}
    execution.result_json = {
        **(execution.result_json or {}),
        "message": "Pipeline execution task dispatch failed. See error_json for details.",
    }
    job = (
        db.query(PipelineJob)
        .filter(PipelineJob.execution_id == execution.id)
        .order_by(PipelineJob.topo_index.asc(), PipelineJob.node_id.asc())
        .first()
    )
    if job is not None:
        job.status = "failed"
        job.started_at = job.started_at or execution.finished_at
        job.finished_at = execution.finished_at
        job.error_json = {
            "errors": [
                {
                    **issue,
                    "node_id": job.node_id,
                    "node_type": job.node_type,
                }
            ]
        }
        job.log_tail = message
        if job.started_at and job.finished_at:
            job.duration_ms = max(0, int((job.finished_at - job.started_at).total_seconds() * 1000))


def normalize_pipeline_execution_mode(value: str | None) -> str:
    mode = str(value or "auto").strip().lower()
    return mode if mode in PIPELINE_EXECUTION_MODES else "auto"


def celery_workers_available(settings) -> tuple[bool, str, dict[str, Any]]:
    try:
        inspector = run_pipeline_task.app.control.inspect(timeout=settings.CELERY_WORKER_PING_TIMEOUT_SECONDS)
        replies = inspector.ping() if inspector is not None else None
    except Exception as exc:
        return False, f"celery_worker_ping_failed: {exc}", {}
    if not replies:
        return False, "no_celery_worker_reply", {}
    return True, "celery_worker_available", replies


def should_execute_pipeline_inline(settings) -> tuple[bool, str, dict[str, Any]]:
    mode = normalize_pipeline_execution_mode(getattr(settings, "PIPELINE_EXECUTION_MODE", "auto"))
    if mode == "inline":
        return True, "configured_inline", {}
    if mode == "celery":
        return False, "configured_celery", {}

    available, reason, worker_info = celery_workers_available(settings)
    if available:
        return False, reason, worker_info
    return True, reason, worker_info


def execute_pipeline_execution_inline(
    db: Session,
    *,
    study: Study,
    pipeline: PipelineDefinition,
    execution: PipelineExecution,
    async_task: AsyncTask,
    current_user: User,
    dispatch_reason: str,
    worker_info: dict[str, Any] | None = None,
    started_message: str = "Pipeline execution task started inline.",
) -> PipelineExecution:
    execution.result_json = {
        **(execution.result_json or {}),
        "mode": "inline",
        "executor": "PipelineExecutor",
        "message": "Pipeline execution is executing inline because no Celery worker is available.",
        "dispatch_mode": "inline",
        "dispatch_reason": dispatch_reason,
        "celery_worker_info": worker_info or {},
    }
    async_task.payload_json = {
        **(async_task.payload_json or {}),
        "dispatch_mode": "inline",
        "dispatch_reason": dispatch_reason,
    }
    record_task_event(
        db,
        async_task,
        "started",
        status="running",
        progress=5,
        message=started_message,
        payload={"execution_id": str(execution.id), "dispatch_mode": "inline", "dispatch_reason": dispatch_reason},
    )
    db.commit()

    execution = run_pipeline_execution_sync(db, execution.id, commit_progress=True)
    db.refresh(execution)
    db.refresh(async_task)

    task_status = task_status_for_pipeline_execution(execution)
    event_type = "failed" if task_status == "failed" else execution.status
    async_task.result_json = {
        "execution_id": str(execution.id),
        "study_id": study.id,
        "pipeline_id": execution.pipeline_id,
        "execution_status": execution.status,
        "dispatch_mode": "inline",
    }
    async_task.error_json = (execution.error_json or {}) if task_status == "failed" else {}
    record_task_event(
        db,
        async_task,
        event_type,
        status=task_status,
        progress=100,
        message=f"Pipeline execution finished inline with status: {execution.status}.",
        payload={"execution_id": str(execution.id), "execution_status": execution.status, "dispatch_mode": "inline"},
    )
    payload_json = async_task.payload_json if isinstance(async_task.payload_json, dict) else {}
    lock_id = payload_json.get("lock_id")
    released_lock = release_study_lock_by_id(
        db,
        lock_id,
        released_by=current_user.id,
        reason=f"inline_execution_{execution.status}",
    )
    released_locks = [released_lock] if released_lock is not None else release_study_locks_for_resource(
        db,
        study_id=execution.study_id,
        resource_kind="pipeline",
        resource_id=execution.pipeline_id,
        lock_type="execution",
        released_by=current_user.id,
        reason=f"inline_execution_{execution.status}",
    )
    generate_execution_manifest(db, study=study, pipeline=pipeline, execution=execution)
    record_audit_event(
        db,
        study_id=execution.study_id,
        action=f"pipeline.execution.{execution.status}",
        actor_id=execution.started_by,
        resource_kind="pipeline_execution",
        resource_id=execution.id,
        resource_label=pipeline.name,
        metadata={
            "pipeline_id": execution.pipeline_id,
            "execution_seq": execution.execution_seq,
            "execution_status": execution.status,
            "dispatch_mode": "inline",
            "dispatch_reason": dispatch_reason,
            "released_lock_ids": [str(lock.id) for lock in released_locks],
        },
    )
    db.commit()
    db.refresh(execution)
    return execution


def pipeline_execution_cancel_conflict_detail(execution: PipelineExecution) -> dict[str, Any]:
    return {
        "code": "PIPELINE_EXECUTION_NOT_CANCELABLE",
        "message": "该执行项当前状态不可取消。",
        "execution_id": str(execution.id),
        "status": execution.status,
        "cancelable_statuses": sorted(RUN_CANCELABLE_STATUSES),
    }


def best_effort_revoke_pipeline_task(async_task: AsyncTask | None) -> dict[str, Any]:
    if async_task is None or not async_task.celery_task_id:
        return {"attempted": False, "reason": "missing_celery_task_id"}
    result = {
        "attempted": True,
        "celery_task_id": async_task.celery_task_id,
        "terminate": False,
    }
    try:
        run_pipeline_task.app.control.revoke(async_task.celery_task_id, terminate=False)
    except Exception as exc:
        return {**result, "status": "failed", "error": str(exc)}
    return {**result, "status": "requested"}


def best_effort_revoke_async_task(async_task: AsyncTask | None) -> dict[str, Any]:
    if async_task is None or not async_task.celery_task_id:
        return {"attempted": False, "reason": "missing_celery_task_id"}
    result = {
        "attempted": True,
        "celery_task_id": async_task.celery_task_id,
        "terminate": False,
    }
    try:
        from app.tasks.celery_app import celery_app

        celery_app.control.revoke(async_task.celery_task_id, terminate=False)
    except Exception as exc:
        return {**result, "status": "failed", "error": str(exc)}
    return {**result, "status": "requested"}


def release_pipeline_execution_locks_for_cancel(
    db: Session,
    *,
    execution: PipelineExecution,
    async_task: AsyncTask | None,
    released_by: UUID | str | None,
) -> list[StudyLock]:
    payload_json = async_task.payload_json if async_task is not None else {}
    lock_id = payload_json.get("lock_id") if isinstance(payload_json, dict) else None
    released_lock = release_study_lock_by_id(
        db,
        lock_id,
        released_by=released_by,
        reason="execution_canceled",
    )
    if released_lock is not None:
        return [released_lock]
    return release_study_locks_for_resource(
        db,
        study_id=execution.study_id,
        resource_kind="pipeline",
        resource_id=execution.pipeline_id,
        lock_type="execution",
        released_by=released_by,
        reason="execution_canceled",
    )


def mark_pipeline_execution_canceled(
    db: Session,
    *,
    execution: PipelineExecution,
    async_task: AsyncTask | None,
    current_user: User,
    revoke_result: dict[str, Any],
) -> None:
    now = datetime.utcnow()
    previous_status = execution.status
    issue = {
        "code": "PIPELINE_EXECUTION_CANCELLED",
        "message": "Pipeline execution was canceled by user request.",
        "severity": "warning",
        "canceled_by": str(current_user.id),
        "canceled_at": now.isoformat() + "Z",
        "previous_status": previous_status,
    }
    execution.status = RUN_CANCELLED_STATUS
    execution.finished_at = now
    execution.result_json = {
        **(execution.result_json or {}),
        "message": "Pipeline execution canceled.",
        "canceled_by": str(current_user.id),
        "canceled_at": issue["canceled_at"],
        "previous_status": previous_status,
        "celery_revoke": revoke_result,
    }
    execution.error_json = {
        **(execution.error_json or {}),
        "canceled": issue,
    }

    jobs = (
        db.query(PipelineJob)
        .filter(
            PipelineJob.execution_id == execution.id,
            PipelineJob.status.in_(("pending", "queued", "running", "waiting_user_input")),
        )
        .all()
    )
    for job in jobs:
        job.status = RUN_CANCELLED_STATUS
        job.started_at = job.started_at or now
        job.finished_at = now
        job.error_json = {
            **(job.error_json or {}),
            "canceled": {
                **issue,
                "node_id": job.node_id,
                "node_type": job.node_type,
            },
        }
        job.log_tail = "Pipeline execution canceled."
        if job.started_at:
            job.duration_ms = max(0, int((now - job.started_at).total_seconds() * 1000))

    if async_task is not None:
        async_task.result_json = {
            **(async_task.result_json or {}),
            "execution_id": str(execution.id),
            "study_id": execution.study_id,
            "pipeline_id": execution.pipeline_id,
            "execution_status": RUN_CANCELLED_STATUS,
            "previous_execution_status": previous_status,
            "celery_revoke": revoke_result,
        }
        event_status = RUN_CANCELLED_STATUS if async_task.status in {"queued", "running", "retrying"} else async_task.status
        event_progress = 100 if event_status == RUN_CANCELLED_STATUS else async_task.progress
        record_task_event(
            db,
            async_task,
            "execution_canceled",
            status=event_status,
            progress=event_progress,
            message="Pipeline execution canceled by user request.",
            payload={
                "execution_id": str(execution.id),
                "previous_status": previous_status,
                "canceled_by": str(current_user.id),
                "celery_revoke": revoke_result,
            },
        )


def pipeline_execution_retry_conflict_detail(execution: PipelineExecution) -> dict[str, Any]:
    return {
        "code": "PIPELINE_EXECUTION_NOT_RETRYABLE",
        "message": "该执行项当前状态不可重试。",
        "execution_id": str(execution.id),
        "status": execution.status,
        "retryable_statuses": sorted(RUN_RETRYABLE_STATUSES),
    }


def retry_snapshot_missing_detail(execution: PipelineExecution) -> dict[str, Any]:
    return {
        "code": "PIPELINE_EXECUTION_INPUT_SNAPSHOT_MISSING",
        "message": "该执行项缺少可复用的输入快照，请使用 input_policy=re_resolve 重新解析输入。",
        "execution_id": str(execution.id),
        "input_policy": "reuse_snapshot",
    }


def definition_has_load_data(definition_json: dict[str, Any]) -> bool:
    graph = definition_json.get("graph") if isinstance(definition_json, dict) else {}
    nodes = graph.get("nodes") if isinstance(graph, dict) else []
    return any(isinstance(node, dict) and node.get("type") == "eeg/data/load" for node in nodes or [])


def clone_pipeline_execution_inputs(
    db: Session,
    *,
    source_execution: PipelineExecution,
    retry_execution: PipelineExecution,
) -> int:
    source_inputs = (
        db.query(PipelineExecutionInput)
        .filter(PipelineExecutionInput.study_id == source_execution.study_id, PipelineExecutionInput.execution_id == source_execution.id)
        .order_by(PipelineExecutionInput.node_id.asc(), PipelineExecutionInput.input_index.asc(), PipelineExecutionInput.created_at.asc())
        .all()
    )
    for item in source_inputs:
        selector_json = deepcopy(item.selector_json or {})
        resolved_metadata_json = deepcopy(item.resolved_metadata_json or {})
        retry_metadata = {
            "retry_of_execution_id": str(source_execution.id),
            "retry_source_input_id": str(item.id),
            "input_policy": "reuse_snapshot",
        }
        if isinstance(resolved_metadata_json, dict):
            resolved_metadata_json["retry"] = retry_metadata
        db.add(
            PipelineExecutionInput(
                execution_id=retry_execution.id,
                study_id=retry_execution.study_id,
                pipeline_id=retry_execution.pipeline_id,
                job_id=None,
                node_id=item.node_id,
                node_type=item.node_type,
                input_slot=item.input_slot,
                input_index=item.input_index,
                input_kind=item.input_kind,
                dataset_asset_id=item.dataset_asset_id,
                recording_id=item.recording_id,
                recording_version_id=item.recording_version_id,
                dataset_file_id=item.dataset_file_id,
                file_role=item.file_role,
                storage_uri=item.storage_uri,
                logical_path=item.logical_path,
                upstream_execution_id=item.upstream_execution_id,
                upstream_dataset_id=item.upstream_dataset_id,
                selector_json=selector_json,
                resolved_metadata_json=resolved_metadata_json,
                sha256=item.sha256,
            )
        )
    db.flush()
    return len(source_inputs)


def attach_retry_input_snapshots_to_jobs(db: Session, *, execution: PipelineExecution) -> None:
    jobs = (
        db.query(PipelineJob)
        .filter(PipelineJob.study_id == execution.study_id, PipelineJob.execution_id == execution.id)
        .all()
    )
    by_node_id = {item.node_id: item.id for item in jobs}
    inputs = (
        db.query(PipelineExecutionInput)
        .filter(PipelineExecutionInput.study_id == execution.study_id, PipelineExecutionInput.execution_id == execution.id)
        .all()
    )
    for item in inputs:
        if item.job_id is None and item.node_id in by_node_id:
            item.job_id = by_node_id[item.node_id]
    if inputs:
        db.flush()


def create_and_dispatch_file_task(
    db: Session,
    *,
    task_type: str,
    study_id: str | None,
    resource_kind: str,
    resource_id: UUID | None,
    payload_json: dict[str, Any],
    current_user: User,
) -> AsyncTaskResponse:
    from app.services.async_tasks import create_async_task
    from app.tasks.file_tasks import run_file_task

    task = create_async_task(
        db,
        task_type=task_type,
        queue_name=get_settings().CELERY_WORKFLOW_QUEUE,
        study_id=study_id,
        resource_kind=resource_kind,
        resource_id=resource_id,
        payload_json=payload_json,
        created_by=current_user.id,
    )
    db.flush()
    try:
        celery_result = run_file_task.apply_async(
            args=[str(task.id)],
            queue=get_settings().CELERY_WORKFLOW_QUEUE,
            task_id=str(task.id),
        )
        if task.celery_task_id != celery_result.id:
            task.celery_task_id = celery_result.id
        record_task_event(
            db,
            task,
            "dispatched",
            message=f"{task_type} task dispatched to Celery.",
            payload={"celery_task_id": celery_result.id, "queue": get_settings().CELERY_WORKFLOW_QUEUE},
        )
    except Exception as exc:
        task.error_json = {
            "errors": [
                {
                    "code": "FILE_TASK_DISPATCH_FAILED",
                    "message": str(exc),
                    "severity": "error",
                }
            ]
        }
        record_task_event(
            db,
            task,
            "dispatch_failed",
            status="failed",
            progress=100,
            message=str(exc),
            payload={"queue": get_settings().CELERY_WORKFLOW_QUEUE},
        )
    db.commit()
    db.refresh(task)
    return async_task_to_response(task)


@router.get("/pipeline/nodes", response_model=NodeSpecListResponse)
def list_node_specs(phase: str | None = Query(default=None)):
    registry = get_node_registry()
    specs = [NodeSpecResponse(**spec) for spec in registry.list_specs(phase=phase)]
    return NodeSpecListResponse(nodes=specs)


@router.post("/studies/{study_id}/pipeline/load-data/resolve", response_model=LoadDataResolveResponse)
def resolve_load_data(
    study_id: str,
    payload: LoadDataResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    return resolve_load_data_selection(
        db=db,
        study=study,
        params=payload.model_dump(mode="json"),
        node_id=payload.node_id,
    )


@router.get("/studies/{study_id}/tasks", response_model=AsyncTaskListResponse)
def list_async_tasks(
    study_id: str,
    task_status: TaskStatus | None = Query(default=None, alias="status"),
    resource_kind: str | None = Query(default=None),
    include_events: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    query = db.query(AsyncTask).filter(AsyncTask.study_id == study.id)
    if task_status:
        query = query.filter(AsyncTask.status == task_status)
    if resource_kind:
        query = query.filter(AsyncTask.resource_kind == resource_kind)
    tasks = query.order_by(AsyncTask.created_at.desc(), AsyncTask.id.desc()).limit(limit).all()

    events_by_task_id: dict[UUID, list[TaskEvent]] = {task.id: [] for task in tasks}
    if include_events and tasks:
        task_events = (
            db.query(TaskEvent)
            .filter(TaskEvent.task_id.in_([task.id for task in tasks]))
            .order_by(TaskEvent.created_at.asc(), TaskEvent.id.asc())
            .all()
        )
        for event in task_events:
            events_by_task_id.setdefault(event.task_id, []).append(event)
    return AsyncTaskListResponse(tasks=[async_task_to_response(task, events_by_task_id.get(task.id, [])) for task in tasks])


@router.get("/studies/{study_id}/tasks/{task_id}", response_model=AsyncTaskResponse)
def get_async_task(
    study_id: str,
    task_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    task = get_async_task_or_404(db, study.id, task_id)
    events = (
        db.query(TaskEvent)
        .filter(TaskEvent.task_id == task.id)
        .order_by(TaskEvent.created_at.asc(), TaskEvent.id.asc())
        .all()
    )
    return async_task_to_response(task, events)


@router.get("/studies/{study_id}/tasks/{task_id}/events", response_model=TaskEventListResponse)
def list_async_task_events(
    study_id: str,
    task_id: UUID,
    since: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    task = get_async_task_or_404(db, study.id, task_id)
    events = query_task_events(db, task.id, since=since)
    return TaskEventListResponse(events=[task_event_to_response(event) for event in events])


@router.get("/studies/{study_id}/tasks/{task_id}/events/stream")
def stream_async_task_events(
    study_id: str,
    task_id: UUID,
    since: str | None = Query(default=None),
    poll_interval_seconds: float = Query(default=TASK_EVENT_STREAM_POLL_INTERVAL_SECONDS, ge=0.25, le=10.0),
    heartbeat_seconds: float = Query(default=TASK_EVENT_STREAM_HEARTBEAT_SECONDS, ge=5.0, le=120.0),
    max_seconds: float = Query(default=TASK_EVENT_STREAM_MAX_SECONDS, ge=1.0, le=3600.0),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    task = get_async_task_or_404(db, study.id, task_id)
    cursor = since or last_event_id
    normalize_task_event_since(db, task.id, cursor)
    return StreamingResponse(
        task_event_stream_generator(
            study_id=study.id,
            task_id=task.id,
            since=cursor,
            poll_interval_seconds=poll_interval_seconds,
            heartbeat_seconds=heartbeat_seconds,
            max_seconds=max_seconds,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/studies/{study_id}/tasks/{task_id}/cancel", response_model=AsyncTaskResponse)
def cancel_async_task(
    study_id: str,
    task_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    task = get_async_task_or_404(db, study.id, task_id)

    if is_pipeline_execution_task(task):
        require_study_run(study, db, current_user)
        execution = None
        if task.resource_id is not None:
            execution = (
                db.query(PipelineExecution)
                .filter(PipelineExecution.study_id == study.id, PipelineExecution.id == task.resource_id)
                .first()
            )
        if execution is not None:
            if execution.status not in RUN_CANCELABLE_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=pipeline_execution_cancel_conflict_detail(execution),
                )
            pipeline = (
                db.query(PipelineDefinition)
                .filter(PipelineDefinition.id == execution.pipeline_id, PipelineDefinition.study_id == study.id)
                .first()
            )
            previous_status = execution.status
            revoke_result = best_effort_revoke_pipeline_task(task)
            released_locks = release_pipeline_execution_locks_for_cancel(
                db,
                execution=execution,
                async_task=task,
                released_by=current_user.id,
            )
            mark_pipeline_execution_canceled(
                db,
                execution=execution,
                async_task=task,
                current_user=current_user,
                revoke_result=revoke_result,
            )
            db.flush()
            generate_execution_manifest(db, study=study, pipeline=pipeline, execution=execution)
            record_audit_event(
                db,
                study_id=study.id,
                action="pipeline.execution.canceled",
                actor_id=current_user.id,
                resource_kind="pipeline_execution",
                resource_id=execution.id,
                resource_label=getattr(pipeline, "name", None),
                metadata={
                    "source": "task_cancel",
                    "pipeline_id": execution.pipeline_id,
                    "execution_seq": execution.execution_seq,
                    "previous_status": previous_status,
                    "new_status": RUN_CANCELLED_STATUS,
                    "async_task_id": str(task.id),
                    "celery_task_id": task.celery_task_id,
                    "celery_revoke": revoke_result,
                    "released_lock_ids": [str(lock.id) for lock in released_locks],
                },
            )
            db.commit()
            db.refresh(task)
            return async_task_to_response(task, task_events_for_response(db, task))
    else:
        require_study_write(study, db, current_user)

    if task.status not in TASK_CANCELABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=async_task_cancel_conflict_detail(task),
        )

    previous_status = task.status
    revoke_result = best_effort_revoke_async_task(task)
    now = datetime.utcnow()
    task.result_json = {
        **(task.result_json or {}),
        "message": "Async task canceled.",
        "canceled_by": str(current_user.id),
        "canceled_at": now.isoformat() + "Z",
        "previous_status": previous_status,
        "celery_revoke": revoke_result,
    }
    record_task_event(
        db,
        task,
        "canceled",
        status="canceled",
        progress=100,
        message="Async task canceled by user request.",
        payload={
            "previous_status": previous_status,
            "canceled_by": str(current_user.id),
            "celery_revoke": revoke_result,
            "orphaned_pipeline_execution": is_pipeline_execution_task(task),
        },
    )
    record_audit_event(
        db,
        study_id=study.id,
        action="async_task.canceled",
        actor_id=current_user.id,
        resource_kind="async_task",
        resource_id=task.id,
        resource_label=task.task_type,
        metadata={
            "task_type": task.task_type,
            "resource_kind": task.resource_kind,
            "resource_id": str(task.resource_id) if task.resource_id else None,
            "previous_status": previous_status,
            "new_status": "canceled",
            "celery_task_id": task.celery_task_id,
            "celery_revoke": revoke_result,
        },
    )
    db.commit()
    db.refresh(task)
    return async_task_to_response(task, task_events_for_response(db, task))


@router.post("/studies/{study_id}/tasks/{task_id}/retry", response_model=AsyncTaskResponse, status_code=status.HTTP_201_CREATED)
def retry_async_task(
    study_id: str,
    task_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    task = get_async_task_or_404(db, study.id, task_id)

    if is_pipeline_execution_task(task):
        # pipeline_execution 类的 retry 本质是"基于旧 execution 建新 execution"，逻辑全在 retry_pipeline_execution 里。
        # 这里直接转发，返回新 execution 对应的 async_task —— 前端拿到 AsyncTaskResponse，
        # 可以继续走 /tasks/{id}/events/stream 监听新任务。
        require_study_run(study, db, current_user)
        source_execution_id = task.resource_id
        if source_execution_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "TASK_RETRY_NO_EXECUTION_ID",
                    "message": "pipeline_execution 后台任务缺少 resource_id，无法重试。",
                    "task_id": str(task.id),
                },
            )
        execution_response = retry_pipeline_execution(
            study_id=study_id,
            execution_id=source_execution_id,
            payload=None,
            db=db,
            current_user=current_user,
        )
        new_task_id_str = (execution_response.result_json or {}).get("async_task_id")
        if not new_task_id_str:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="pipeline_execution retry 未生成新的 async_task。",
            )
        try:
            new_task_uuid = UUID(new_task_id_str)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="pipeline_execution retry 返回了无效的 async_task_id。",
            )
        new_task = db.get(AsyncTask, new_task_uuid)
        if new_task is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="pipeline_execution retry 创建的 async_task 在 db 中找不到。",
            )
        return async_task_to_response(new_task, task_events_for_response(db, new_task))

    require_study_write(study, db, current_user)
    if task.status not in TASK_RETRYABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=async_task_retry_conflict_detail(task),
        )
    if task.task_type not in FILE_TASK_TYPES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=async_task_retry_unsupported_detail(task),
        )

    retry_payload = deepcopy(task.payload_json or {})
    retry_payload.update(
        {
            "retry_of_task_id": str(task.id),
            "retry_source_status": task.status,
            "retry_requested_by": str(current_user.id),
            "retry_requested_at": datetime.utcnow().isoformat() + "Z",
        }
    )
    response = create_and_dispatch_file_task(
        db,
        task_type=task.task_type,
        study_id=study.id,
        resource_kind=task.resource_kind,
        resource_id=task.resource_id,
        payload_json=retry_payload,
        current_user=current_user,
    )
    record_audit_event(
        db,
        study_id=study.id,
        action="async_task.retry_queued",
        actor_id=current_user.id,
        resource_kind="async_task",
        resource_id=response.id,
        resource_label=task.task_type,
        metadata={
            "task_type": task.task_type,
            "retry_of_task_id": str(task.id),
            "source_status": task.status,
            "resource_kind": task.resource_kind,
            "resource_id": str(task.resource_id) if task.resource_id else None,
        },
    )
    db.commit()
    return response


@router.get("/studies/{study_id}/pipelines", response_model=PipelineListResponse)
def list_pipelines(
    study_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    pipelines = (
        db.query(PipelineDefinition)
        .filter(PipelineDefinition.study_id == study.id, PipelineDefinition.status != "deleted")
        .order_by(PipelineDefinition.updated_at.desc(), PipelineDefinition.id.desc())
        .all()
    )
    return PipelineListResponse(pipelines=[pipeline_to_response(item) for item in pipelines])


@router.post("/studies/{study_id}/pipelines", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
def create_pipeline(
    study_id: str,
    payload: PipelineCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_write(study_id, db, current_user)
    definition = payload.definition_json.model_dump(mode="json")
    definition["name"] = payload.name
    definition["description"] = payload.description
    pipeline = PipelineDefinition(
        study_id=study.id,
        name=payload.name,
        description=payload.description,
        definition_json=definition,
        node_count=count_nodes(definition),
        version=1,
        is_template=payload.is_template,
        status="active",
        created_by=current_user.id,
    )
    db.add(pipeline)
    try:
        db.flush()
        record_audit_event(
            db,
            study_id=study.id,
            action="pipeline.created",
            actor_id=current_user.id,
            resource_kind="pipeline",
            resource_id=pipeline.id,
            resource_label=pipeline.name,
            metadata={
                "version": pipeline.version,
                "status": pipeline.status,
                "node_count": pipeline.node_count,
                "is_template": pipeline.is_template,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="同名工作流已存在") from exc
    db.refresh(pipeline)
    return pipeline_to_response(pipeline)


@router.get("/studies/{study_id}/pipelines/{pipeline_id}", response_model=PipelineResponse)
def get_pipeline(
    study_id: str,
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    return pipeline_to_response(get_pipeline_or_404(db, study.id, pipeline_id))


@router.post("/studies/{study_id}/pipelines/{pipeline_id}/edit-lock", response_model=PipelineEditLockResponse)
def acquire_pipeline_edit_lock(
    study_id: str,
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_write(study_id, db, current_user)
    pipeline = get_pipeline_or_404(db, study.id, pipeline_id)
    lock, created = acquire_or_refresh_pipeline_edit_lock(
        db,
        study=study,
        pipeline=pipeline,
        current_user=current_user,
        reason="pipeline_edit_acquire",
    )
    record_audit_event(
        db,
        study_id=study.id,
        action="pipeline.edit_lock.acquired" if created else "pipeline.edit_lock.refreshed",
        actor_id=current_user.id,
        resource_kind="pipeline",
        resource_id=pipeline.id,
        resource_label=pipeline.name,
        metadata={
            "lock_id": str(lock.id),
            "lock_type": lock.lock_type,
            "pipeline_version": pipeline.version,
            "expires_at": lock.expires_at.isoformat(),
        },
    )
    db.commit()
    db.refresh(lock)
    return pipeline_edit_lock_to_response(lock, pipeline.id)


@router.post(
    "/studies/{study_id}/pipelines/{pipeline_id}/edit-lock/refresh",
    response_model=PipelineEditLockResponse,
)
def refresh_pipeline_edit_lock(
    study_id: str,
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_write(study_id, db, current_user)
    pipeline = get_pipeline_or_404(db, study.id, pipeline_id)
    lock = ensure_pipeline_edit_lock_available(db, study=study, pipeline=pipeline, current_user=current_user)
    if lock is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "PIPELINE_EDIT_LOCK_NOT_FOUND",
                "message": "没有可续期的工作流编辑锁，请先获取编辑锁。",
                "study_id": study.id,
                "pipeline_id": pipeline.id,
            },
        )
    lock = refresh_study_lock(
        db,
        lock,
        ttl_seconds=PIPELINE_EDIT_LOCK_TTL_SECONDS,
        refreshed_by=current_user.id,
        reason="pipeline_edit_refresh",
    )
    record_audit_event(
        db,
        study_id=study.id,
        action="pipeline.edit_lock.refreshed",
        actor_id=current_user.id,
        resource_kind="pipeline",
        resource_id=pipeline.id,
        resource_label=pipeline.name,
        metadata={
            "lock_id": str(lock.id),
            "lock_type": lock.lock_type,
            "pipeline_version": pipeline.version,
            "expires_at": lock.expires_at.isoformat(),
        },
    )
    db.commit()
    db.refresh(lock)
    return pipeline_edit_lock_to_response(lock, pipeline.id)


@router.delete("/studies/{study_id}/pipelines/{pipeline_id}/edit-lock", status_code=status.HTTP_204_NO_CONTENT)
def release_pipeline_edit_lock(
    study_id: str,
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_write(study_id, db, current_user)
    pipeline = get_pipeline_or_404(db, study.id, pipeline_id)
    lock = find_active_pipeline_edit_lock(db, study=study, pipeline=pipeline)
    if lock is not None and not is_lock_owned_by(lock, current_user):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=pipeline_edit_lock_conflict_detail(study, pipeline, lock),
        )
    if lock is not None:
        release_study_lock(db, lock, released_by=current_user.id, reason="pipeline_edit_release")
        record_audit_event(
            db,
            study_id=study.id,
            action="pipeline.edit_lock.released",
            actor_id=current_user.id,
            resource_kind="pipeline",
            resource_id=pipeline.id,
            resource_label=pipeline.name,
            metadata={
                "lock_id": str(lock.id),
                "lock_type": lock.lock_type,
                "pipeline_version": pipeline.version,
            },
        )
    db.commit()
    return None


@router.put("/studies/{study_id}/pipelines/{pipeline_id}", response_model=PipelineResponse)
def update_pipeline(
    study_id: str,
    pipeline_id: int,
    payload: PipelineUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_write(study_id, db, current_user)
    pipeline = get_pipeline_or_404(db, study.id, pipeline_id)
    edit_lock = ensure_pipeline_edit_lock_available(db, study=study, pipeline=pipeline, current_user=current_user)
    if payload.expected_version != pipeline.version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="工作流版本已变化，请刷新后再保存")

    fields_set = payload.model_fields_set
    previous_version = pipeline.version
    previous_status = pipeline.status

    if "name" in fields_set and payload.name is not None:
        pipeline.name = payload.name
    if "description" in fields_set:
        pipeline.description = payload.description
    if "definition_json" in fields_set and payload.definition_json is not None:
        definition = payload.definition_json.model_dump(mode="json")
        definition["name"] = pipeline.name
        definition["description"] = pipeline.description
        pipeline.definition_json = definition
        pipeline.node_count = count_nodes(definition)
    if "is_template" in fields_set and payload.is_template is not None:
        pipeline.is_template = payload.is_template
    if "status" in fields_set and payload.status is not None:
        pipeline.status = payload.status

    pipeline.version += 1
    pipeline.updated_at = datetime.utcnow()
    try:
        record_audit_event(
            db,
            study_id=study.id,
            action="pipeline.updated",
            actor_id=current_user.id,
            resource_kind="pipeline",
            resource_id=pipeline.id,
            resource_label=pipeline.name,
            metadata={
                "fields": sorted(fields_set),
                "previous_version": previous_version,
                "new_version": pipeline.version,
                "previous_status": previous_status,
                "new_status": pipeline.status,
                "expected_version": payload.expected_version,
                "edit_lock_id": str(edit_lock.id) if edit_lock is not None else None,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="同名工作流已存在") from exc
    db.refresh(pipeline)
    return pipeline_to_response(pipeline)


@router.delete("/studies/{study_id}/pipelines/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pipeline(
    study_id: str,
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_write(study_id, db, current_user)
    pipeline = get_pipeline_or_404(db, study.id, pipeline_id)
    pipeline.status = "deleted"
    pipeline.version += 1
    pipeline.updated_at = datetime.utcnow()
    record_audit_event(
        db,
        study_id=study.id,
        action="pipeline.deleted",
        actor_id=current_user.id,
        resource_kind="pipeline",
        resource_id=pipeline.id,
        resource_label=pipeline.name,
        metadata={"version": pipeline.version},
    )
    db.commit()
    return None


@router.get("/studies/{study_id}/pipelines/{pipeline_id}/executions", response_model=PipelineExecutionListResponse)
def list_pipeline_executions(
    study_id: str,
    pipeline_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    get_pipeline_or_404(db, study.id, pipeline_id)
    executions = (
        db.query(PipelineExecution)
        .filter(PipelineExecution.study_id == study.id, PipelineExecution.pipeline_id == pipeline_id)
        .order_by(PipelineExecution.execution_seq.desc())
        .limit(limit)
        .all()
    )
    return PipelineExecutionListResponse(executions=[pipeline_execution_to_response(execution) for execution in executions])


def unique_pipeline_execution_ids(*groups: list[UUID | None]) -> list[UUID]:
    seen: set[UUID] = set()
    ordered: list[UUID] = []
    for group in groups:
        for execution_id in group:
            if execution_id is None or execution_id in seen:
                continue
            seen.add(execution_id)
            ordered.append(execution_id)
    return ordered


def load_pipeline_executions_by_ids(db: Session, *, study_id: str, execution_ids: list[UUID]) -> list[PipelineExecution]:
    if not execution_ids:
        return []
    rows = (
        db.query(PipelineExecution)
        .filter(PipelineExecution.study_id == study_id, PipelineExecution.id.in_(execution_ids))
        .order_by(PipelineExecution.started_at.asc(), PipelineExecution.execution_seq.asc())
        .all()
    )
    by_id = {row.id: row for row in rows}
    return [by_id[execution_id] for execution_id in execution_ids if execution_id in by_id]


def build_pipeline_execution_lineage_response(
    db: Session,
    *,
    study: Study,
    execution: PipelineExecution,
) -> PipelineExecutionLineageResponse:
    inputs = (
        db.query(PipelineExecutionInput)
        .filter(PipelineExecutionInput.study_id == study.id, PipelineExecutionInput.execution_id == execution.id)
        .order_by(PipelineExecutionInput.node_id.asc(), PipelineExecutionInput.input_index.asc(), PipelineExecutionInput.created_at.asc())
        .all()
    )
    derived_datasets = (
        db.query(DerivedDataset)
        .filter(DerivedDataset.study_id == study.id, DerivedDataset.produced_by_execution_id == execution.id)
        .order_by(DerivedDataset.created_at.asc(), DerivedDataset.id.asc())
        .all()
    )
    upstream_dependencies = (
        db.query(PipelineExecutionDependency)
        .filter(PipelineExecutionDependency.study_id == study.id, PipelineExecutionDependency.execution_id == execution.id)
        .order_by(PipelineExecutionDependency.created_at.asc(), PipelineExecutionDependency.id.asc())
        .all()
    )

    derived_dataset_ids = [dataset.id for dataset in derived_datasets]
    downstream_dependency_query = db.query(PipelineExecutionDependency).filter(PipelineExecutionDependency.study_id == study.id)
    if derived_dataset_ids:
        downstream_dependency_query = downstream_dependency_query.filter(
            (PipelineExecutionDependency.depends_on_execution_id == execution.id)
            | (PipelineExecutionDependency.upstream_dataset_id.in_(derived_dataset_ids))
        )
    else:
        downstream_dependency_query = downstream_dependency_query.filter(PipelineExecutionDependency.depends_on_execution_id == execution.id)
    downstream_dependencies = downstream_dependency_query.order_by(
        PipelineExecutionDependency.created_at.asc(),
        PipelineExecutionDependency.id.asc(),
    ).all()

    upstream_execution_ids = unique_pipeline_execution_ids(
        [dependency.depends_on_execution_id for dependency in upstream_dependencies],
        [execution_input.upstream_execution_id for execution_input in inputs],
    )
    downstream_execution_ids = unique_pipeline_execution_ids([dependency.execution_id for dependency in downstream_dependencies])
    upstream_executions = load_pipeline_executions_by_ids(db, study_id=study.id, execution_ids=upstream_execution_ids)
    downstream_executions = load_pipeline_executions_by_ids(db, study_id=study.id, execution_ids=downstream_execution_ids)

    graph_nodes: dict[str, dict[str, Any]] = {}
    graph_edges: dict[str, dict[str, Any]] = {}

    add_lineage_graph_node(
        graph_nodes,
        node_id=lineage_execution_node_id(execution.id),
        node_type="execution",
        label=f"Execution #{execution.execution_seq}",
        resource_kind="pipeline_execution",
        resource_id=execution.id,
        status=execution.status,
        metadata={"pipeline_id": execution.pipeline_id, "pipeline_version": execution.pipeline_version, "role": "current"},
    )
    for upstream_execution in upstream_executions:
        add_lineage_graph_node(
            graph_nodes,
            node_id=lineage_execution_node_id(upstream_execution.id),
            node_type="execution",
            label=f"Execution #{upstream_execution.execution_seq}",
            resource_kind="pipeline_execution",
            resource_id=upstream_execution.id,
            status=upstream_execution.status,
            metadata={"pipeline_id": upstream_execution.pipeline_id, "pipeline_version": upstream_execution.pipeline_version, "role": "upstream"},
        )
    for downstream_execution in downstream_executions:
        add_lineage_graph_node(
            graph_nodes,
            node_id=lineage_execution_node_id(downstream_execution.id),
            node_type="execution",
            label=f"Execution #{downstream_execution.execution_seq}",
            resource_kind="pipeline_execution",
            resource_id=downstream_execution.id,
            status=downstream_execution.status,
            metadata={"pipeline_id": downstream_execution.pipeline_id, "pipeline_version": downstream_execution.pipeline_version, "role": "downstream"},
        )
    for execution_input in inputs:
        input_node_id = lineage_input_node_id(execution_input.id)
        add_lineage_graph_node(
            graph_nodes,
            node_id=input_node_id,
            node_type="input",
            label=f"{execution_input.node_id or 'input'}:{execution_input.input_slot}",
            resource_kind="pipeline_execution_input",
            resource_id=execution_input.id,
            metadata={
                "input_kind": execution_input.input_kind,
                "file_role": execution_input.file_role,
                "storage_uri": execution_input.storage_uri,
                "logical_path": execution_input.logical_path,
            },
        )
        add_lineage_graph_edge(
            graph_edges,
            edge_id=f"input:{execution_input.id}:to_execution",
            source=input_node_id,
            target=lineage_execution_node_id(execution.id),
            edge_type="input_to_execution",
            metadata={"input_slot": execution_input.input_slot, "input_kind": execution_input.input_kind},
        )
        if execution_input.upstream_execution_id is not None:
            add_lineage_graph_node(
                graph_nodes,
                node_id=lineage_execution_node_id(execution_input.upstream_execution_id),
                node_type="execution",
                label=f"Execution {execution_input.upstream_execution_id}",
                resource_kind="pipeline_execution",
                resource_id=execution_input.upstream_execution_id,
                metadata={"role": "upstream_input"},
            )
            add_lineage_graph_edge(
                graph_edges,
                edge_id=f"input:{execution_input.id}:upstream_execution",
                source=lineage_execution_node_id(execution_input.upstream_execution_id),
                target=input_node_id,
                edge_type="upstream_execution_input",
            )
        if execution_input.upstream_dataset_id is not None:
            add_lineage_graph_node(
                graph_nodes,
                node_id=lineage_derived_dataset_node_id(execution_input.upstream_dataset_id),
                node_type="derived_dataset",
                label=f"DerivedDataset {execution_input.upstream_dataset_id}",
                resource_kind="derived_dataset",
                resource_id=execution_input.upstream_dataset_id,
                metadata={"role": "upstream_input"},
            )
            add_lineage_graph_edge(
                graph_edges,
                edge_id=f"input:{execution_input.id}:upstream_dataset",
                source=lineage_derived_dataset_node_id(execution_input.upstream_dataset_id),
                target=input_node_id,
                edge_type="upstream_dataset_input",
            )

    for dataset in derived_datasets:
        dataset_node_id = lineage_derived_dataset_node_id(dataset.id)
        add_lineage_graph_node(
            graph_nodes,
            node_id=dataset_node_id,
            node_type="derived_dataset",
            label=dataset.display_name or f"{dataset.data_type} {dataset.bids_subject_id or ''}".strip(),
            resource_kind="derived_dataset",
            resource_id=dataset.id,
            status=dataset.retention_status,
            metadata={
                "job_id": str(dataset.produced_by_job_id) if dataset.produced_by_job_id else None,
                "node_type": dataset.produced_by_node_type,
                "data_type": dataset.data_type,
                "storage_uri": dataset.storage_uri,
                "sha256": dataset.sha256,
                "tags": list(dataset.tags or []),
            },
        )
        add_lineage_graph_edge(
            graph_edges,
            edge_id=f"execution:{execution.id}:derived:{dataset.id}",
            source=lineage_execution_node_id(execution.id),
            target=dataset_node_id,
            edge_type="produces",
            metadata={"retention_status": dataset.retention_status},
        )

    for dependency in upstream_dependencies:
        source = lineage_execution_node_id(dependency.depends_on_execution_id)
        add_lineage_graph_edge(
            graph_edges,
            edge_id=f"dependency:{dependency.id}:upstream_execution",
            source=source,
            target=lineage_execution_node_id(execution.id),
            edge_type=dependency.dependency_kind,
            metadata={"dependency_id": str(dependency.id), **(dependency.metadata_json or {})},
        )
        if dependency.upstream_dataset_id is not None:
            dataset_node_id = lineage_derived_dataset_node_id(dependency.upstream_dataset_id)
            add_lineage_graph_node(
                graph_nodes,
                node_id=dataset_node_id,
                node_type="derived_dataset",
                label=f"DerivedDataset {dependency.upstream_dataset_id}",
                resource_kind="derived_dataset",
                resource_id=dependency.upstream_dataset_id,
                metadata={"role": "upstream_dependency"},
            )
            add_lineage_graph_edge(
                graph_edges,
                edge_id=f"dependency:{dependency.id}:upstream_dataset",
                source=dataset_node_id,
                target=lineage_execution_node_id(execution.id),
                edge_type="uses_derived_dataset",
                metadata={"dependency_id": str(dependency.id), **(dependency.metadata_json or {})},
            )

    for dependency in downstream_dependencies:
        target = lineage_execution_node_id(dependency.execution_id)
        if dependency.upstream_dataset_id is not None:
            source = lineage_derived_dataset_node_id(dependency.upstream_dataset_id)
            edge_type = "derived_dataset_used_by"
        else:
            source = lineage_execution_node_id(execution.id)
            edge_type = dependency.dependency_kind
        add_lineage_graph_edge(
            graph_edges,
            edge_id=f"dependency:{dependency.id}:downstream",
            source=source,
            target=target,
            edge_type=edge_type,
            metadata={"dependency_id": str(dependency.id), **(dependency.metadata_json or {})},
        )

    return PipelineExecutionLineageResponse(
        execution=pipeline_execution_to_response(execution),
        inputs=[pipeline_execution_input_to_response(item) for item in inputs],
        derived_datasets=[derived_dataset_to_response(item) for item in derived_datasets],
        upstream_executions=[pipeline_execution_to_response(item) for item in upstream_executions],
        downstream_executions=[pipeline_execution_to_response(item) for item in downstream_executions],
        upstream_dependencies=[pipeline_execution_dependency_to_response(item) for item in upstream_dependencies],
        downstream_dependencies=[pipeline_execution_dependency_to_response(item) for item in downstream_dependencies],
        graph_nodes=list(graph_nodes.values()),
        graph_edges=list(graph_edges.values()),
    )


@router.get("/studies/{study_id}/pipeline-executions/{execution_id}", response_model=PipelineExecutionDetailResponse)
def get_pipeline_execution(
    study_id: str,
    execution_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    execution = get_pipeline_execution_or_404(db, study.id, execution_id)
    jobs = (
        db.query(PipelineJob)
        .filter(PipelineJob.study_id == study.id, PipelineJob.execution_id == execution.id)
        .order_by(PipelineJob.topo_index.asc(), PipelineJob.node_id.asc())
        .all()
    )
    derived_datasets = (
        db.query(DerivedDataset)
        .filter(
            DerivedDataset.study_id == study.id,
            DerivedDataset.produced_by_execution_id == execution.id,
            DerivedDataset.retention_status != "deleted",
        )
        .order_by(DerivedDataset.created_at.asc(), DerivedDataset.id.asc())
        .all()
    )
    dependencies = (
        db.query(PipelineExecutionDependency)
        .filter(PipelineExecutionDependency.study_id == study.id, PipelineExecutionDependency.execution_id == execution.id)
        .order_by(PipelineExecutionDependency.created_at.asc(), PipelineExecutionDependency.id.asc())
        .all()
    )
    inputs = (
        db.query(PipelineExecutionInput)
        .filter(PipelineExecutionInput.study_id == study.id, PipelineExecutionInput.execution_id == execution.id)
        .order_by(PipelineExecutionInput.node_id.asc(), PipelineExecutionInput.input_index.asc(), PipelineExecutionInput.created_at.asc())
        .all()
    )
    tasks = (
        db.query(AsyncTask)
        .filter(
            AsyncTask.study_id == study.id,
            AsyncTask.resource_kind == "pipeline_execution",
            AsyncTask.resource_id == execution.id,
        )
        .order_by(AsyncTask.created_at.desc(), AsyncTask.id.asc())
        .all()
    )
    task_ids = [task.id for task in tasks]
    task_events_by_task_id: dict[UUID, list[TaskEvent]] = {task.id: [] for task in tasks}
    if task_ids:
        task_events = (
            db.query(TaskEvent)
            .filter(TaskEvent.task_id.in_(task_ids))
            .order_by(TaskEvent.created_at.asc(), TaskEvent.id.asc())
            .all()
        )
        for event in task_events:
            task_events_by_task_id.setdefault(event.task_id, []).append(event)
    return PipelineExecutionDetailResponse(
        **pipeline_execution_to_response(execution).model_dump(),
        inputs=[pipeline_execution_input_to_response(item) for item in inputs],
        dependencies=[pipeline_execution_dependency_to_response(item) for item in dependencies],
        tasks=[async_task_to_response(task, task_events_by_task_id.get(task.id, [])) for task in tasks],
        jobs=[pipeline_job_to_response(item) for item in jobs],
        derived_datasets=[derived_dataset_to_response(item) for item in derived_datasets],
    )


@router.get("/studies/{study_id}/pipeline-executions/{execution_id}/lineage", response_model=PipelineExecutionLineageResponse)
def get_pipeline_execution_lineage(
    study_id: str,
    execution_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    execution = get_pipeline_execution_or_404(db, study.id, execution_id)
    return build_pipeline_execution_lineage_response(db, study=study, execution=execution)


@router.get("/studies/{study_id}/pipeline-executions/{execution_id}/manifest")
def get_pipeline_execution_manifest(
    study_id: str,
    execution_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    execution = get_pipeline_execution_or_404(db, study.id, execution_id)
    pipeline = (
        db.query(PipelineDefinition)
        .filter(PipelineDefinition.id == execution.pipeline_id, PipelineDefinition.study_id == study.id)
        .first()
    )
    manifest = ensure_execution_manifest(db, study=study, pipeline=pipeline, execution=execution)
    db.commit()
    return manifest


@router.post("/studies/{study_id}/pipeline-executions/{execution_id}/cancel", response_model=PipelineExecutionResponse)
def cancel_pipeline_execution(
    study_id: str,
    execution_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_run(study_id, db, current_user)
    execution = get_pipeline_execution_or_404(db, study.id, execution_id)
    if execution.status not in RUN_CANCELABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=pipeline_execution_cancel_conflict_detail(execution),
        )

    async_task = (
        db.query(AsyncTask)
        .filter(
            AsyncTask.study_id == study.id,
            AsyncTask.resource_kind == "pipeline_execution",
            AsyncTask.resource_id == execution.id,
        )
        .order_by(AsyncTask.created_at.desc(), AsyncTask.id.desc())
        .first()
    )
    pipeline = (
        db.query(PipelineDefinition)
        .filter(PipelineDefinition.id == execution.pipeline_id, PipelineDefinition.study_id == study.id)
        .first()
    )
    previous_status = execution.status
    revoke_result = best_effort_revoke_pipeline_task(async_task)
    released_locks = release_pipeline_execution_locks_for_cancel(
        db,
        execution=execution,
        async_task=async_task,
        released_by=current_user.id,
    )
    mark_pipeline_execution_canceled(
        db,
        execution=execution,
        async_task=async_task,
        current_user=current_user,
        revoke_result=revoke_result,
    )
    db.flush()
    generate_execution_manifest(db, study=study, pipeline=pipeline, execution=execution)
    record_audit_event(
        db,
        study_id=study.id,
        action="pipeline.execution.canceled",
        actor_id=current_user.id,
        resource_kind="pipeline_execution",
        resource_id=execution.id,
        resource_label=getattr(pipeline, "name", None),
        metadata={
            "pipeline_id": execution.pipeline_id,
            "execution_seq": execution.execution_seq,
            "previous_status": previous_status,
            "new_status": RUN_CANCELLED_STATUS,
            "async_task_id": str(async_task.id) if async_task is not None else None,
            "celery_task_id": async_task.celery_task_id if async_task is not None else None,
            "celery_revoke": revoke_result,
            "released_lock_ids": [str(lock.id) for lock in released_locks],
        },
    )
    db.commit()
    db.refresh(execution)
    return pipeline_execution_to_response(execution)


@router.post("/studies/{study_id}/pipeline-executions/{execution_id}/retry", response_model=PipelineExecutionResponse)
def retry_pipeline_execution(
    study_id: str,
    execution_id: UUID,
    payload: PipelineExecutionRetryRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = payload or PipelineExecutionRetryRequest()
    study = get_study_for_run(study_id, db, current_user)
    source_execution = get_pipeline_execution_or_404(db, study.id, execution_id)
    if source_execution.status not in RUN_RETRYABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=pipeline_execution_retry_conflict_detail(source_execution),
        )

    pipeline = get_pipeline_or_404(db, study.id, source_execution.pipeline_id)
    definition_snapshot = deepcopy(source_execution.definition_snapshot or pipeline.definition_json or {})
    validation = validate_definition(definition_snapshot, db=db, study=study)
    if not validation.valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "PIPELINE_RETRY_DEFINITION_INVALID",
                "message": "旧执行项的工作流快照校验未通过，不能直接重试。",
                "errors": [issue.model_dump(mode="json") for issue in validation.errors],
                "warnings": [issue.model_dump(mode="json") for issue in validation.warnings],
            },
        )

    has_source_input = (
        db.query(PipelineExecutionInput.id)
        .filter(PipelineExecutionInput.study_id == study.id, PipelineExecutionInput.execution_id == source_execution.id)
        .first()
        is not None
    )
    if payload.input_policy == "reuse_snapshot" and definition_has_load_data(definition_snapshot) and not has_source_input:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=retry_snapshot_missing_detail(source_execution),
        )

    settings = get_settings()
    async_task_id = uuid4()
    try:
        execution_lock = acquire_study_lock(
            db,
            study_id=study.id,
            resource_kind="pipeline",
            resource_id=source_execution.pipeline_id,
            lock_type="execution",
            locked_by=current_user.id,
            ttl_seconds=DEFAULT_STUDY_LOCK_TTL_SECONDS,
            metadata={
                "pipeline_id": source_execution.pipeline_id,
                "pipeline_version": source_execution.pipeline_version,
                "reason": "pipeline_retry",
                "retry_of_execution_id": str(source_execution.id),
                "input_policy": payload.input_policy,
            },
        )
    except StudyLockConflictError as exc:
        lock = exc.lock
        detail = {
            "code": "PIPELINE_EXECUTION_LOCKED",
            "message": "该工作流正在被运行，请等待当前运行结束或锁过期后再试。",
            "study_id": study.id,
            "pipeline_id": source_execution.pipeline_id,
        }
        if lock is not None:
            detail.update(
                {
                    "lock_id": str(lock.id),
                    "locked_by": str(lock.locked_by) if lock.locked_by else None,
                    "locked_at": lock.locked_at.isoformat() if lock.locked_at else None,
                    "expires_at": lock.expires_at.isoformat() if lock.expires_at else None,
                }
            )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    retry_execution = PipelineExecution(
        study_id=study.id,
        pipeline_id=source_execution.pipeline_id,
        pipeline_version=source_execution.pipeline_version,
        execution_seq=next_pipeline_execution_seq(db, study.id, source_execution.pipeline_id),
        trigger="retry",
        execution_mode=source_execution.execution_mode or "analysis",
        save_policy=source_execution.save_policy or "current",
        status="queued",
        node_count=count_nodes(definition_snapshot),
        dataset_count=source_execution.dataset_count if payload.input_policy == "reuse_snapshot" else 0,
        definition_snapshot=definition_snapshot,
        result_json={
            "mode": "celery",
            "executor": "PipelineExecutor",
            "message": "Pipeline retry execution queued.",
            "async_task_id": str(async_task_id),
            "celery_task_id": str(async_task_id),
            "task_queue": settings.CELERY_WORKFLOW_QUEUE,
            "execution_lock_id": str(execution_lock.id),
            "execution_lock_expires_at": execution_lock.expires_at.isoformat(),
            "execution_mode": source_execution.execution_mode or "analysis",
            "save_policy": source_execution.save_policy or "current",
            "retry_of_execution_id": str(source_execution.id),
            "retry_input_policy": payload.input_policy,
            "node_results": [],
            "data_infos_by_node": {},
            "warnings": [],
        },
        error_json={},
        started_by=current_user.id,
    )
    db.add(retry_execution)
    db.flush()

    cloned_input_count = 0
    if payload.input_policy == "reuse_snapshot":
        cloned_input_count = clone_pipeline_execution_inputs(db, source_execution=source_execution, retry_execution=retry_execution)

    retry_dependency = PipelineExecutionDependency(
        study_id=study.id,
        execution_id=retry_execution.id,
        depends_on_execution_id=source_execution.id,
        upstream_dataset_id=None,
        dependency_kind="retry_of",
        metadata_json={
            "source_execution_status": source_execution.status,
            "input_policy": payload.input_policy,
            "cloned_input_count": cloned_input_count,
        },
    )
    db.add(retry_dependency)

    async_task = AsyncTask(
        id=async_task_id,
        celery_task_id=str(async_task_id),
        task_type="pipeline_execution",
        queue_name=settings.CELERY_WORKFLOW_QUEUE,
        status="queued",
        progress=0,
        study_id=study.id,
        resource_kind="pipeline_execution",
        resource_id=retry_execution.id,
        payload_json={
            "execution_id": str(retry_execution.id),
            "study_id": study.id,
            "pipeline_id": retry_execution.pipeline_id,
            "pipeline_version": retry_execution.pipeline_version,
            "execution_seq": retry_execution.execution_seq,
            "trigger": "retry",
            "execution_mode": retry_execution.execution_mode,
            "save_policy": retry_execution.save_policy,
            "retry_of_execution_id": str(source_execution.id),
            "input_policy": payload.input_policy,
            "cloned_input_count": cloned_input_count,
            "lock_id": str(execution_lock.id),
            "lock_expires_at": execution_lock.expires_at.isoformat(),
        },
        result_json={},
        error_json={},
        created_by=current_user.id,
    )
    db.add(async_task)
    record_task_event(
        db,
        async_task,
        "created",
        status="queued",
        progress=0,
        message="Pipeline retry task created.",
        payload={"execution_id": str(retry_execution.id), "retry_of_execution_id": str(source_execution.id), "pipeline_id": retry_execution.pipeline_id},
    )
    record_audit_event(
        db,
        study_id=study.id,
        action="pipeline.execution.retry_queued",
        actor_id=current_user.id,
        resource_kind="pipeline_execution",
        resource_id=retry_execution.id,
        resource_label=pipeline.name,
        metadata={
            "pipeline_id": retry_execution.pipeline_id,
            "pipeline_version": retry_execution.pipeline_version,
            "execution_seq": retry_execution.execution_seq,
            "retry_of_execution_id": str(source_execution.id),
            "source_execution_status": source_execution.status,
            "input_policy": payload.input_policy,
            "cloned_input_count": cloned_input_count,
            "async_task_id": str(async_task.id),
            "lock_id": str(execution_lock.id),
            "lock_expires_at": execution_lock.expires_at.isoformat(),
        },
    )
    PipelineExecutor(db).prepare_execution(study=study, pipeline=pipeline, execution=retry_execution)
    if payload.input_policy == "reuse_snapshot":
        attach_retry_input_snapshots_to_jobs(db, execution=retry_execution)
    db.commit()
    db.refresh(retry_execution)
    db.refresh(async_task)
    execute_inline, dispatch_reason, worker_info = should_execute_pipeline_inline(settings)
    if execute_inline:
        retry_execution = execute_pipeline_execution_inline(
            db,
            study=study,
            pipeline=pipeline,
            execution=retry_execution,
            async_task=async_task,
            current_user=current_user,
            dispatch_reason=dispatch_reason,
            worker_info=worker_info,
            started_message="Pipeline retry task started inline.",
        )
        return pipeline_execution_to_response(retry_execution)
    try:
        task = run_pipeline_task.apply_async(
            args=[str(retry_execution.id)],
            kwargs={"study_id": study.id},
            queue=settings.CELERY_WORKFLOW_QUEUE,
            task_id=str(async_task_id),
        )
        if async_task.celery_task_id != task.id:
            async_task.celery_task_id = task.id
        retry_execution.result_json = {
            **(retry_execution.result_json or {}),
            "async_task_id": str(async_task.id),
            "celery_task_id": task.id,
            "task_queue": settings.CELERY_WORKFLOW_QUEUE,
            "execution_lock_id": str(execution_lock.id),
            "execution_lock_expires_at": execution_lock.expires_at.isoformat(),
        }
        record_task_event(
            db,
            async_task,
            "dispatched",
            message="Pipeline retry task dispatched to Celery.",
            payload={"celery_task_id": task.id, "queue": settings.CELERY_WORKFLOW_QUEUE},
        )
        db.commit()
        db.refresh(retry_execution)
    except Exception as exc:
        mark_execution_dispatch_failed(db, retry_execution, str(exc))
        release_study_lock(db, execution_lock, released_by=current_user.id, reason="dispatch_failed")
        async_task.result_json = {"execution_id": str(retry_execution.id), "execution_status": retry_execution.status}
        async_task.error_json = retry_execution.error_json or {}
        record_task_event(
            db,
            async_task,
            "dispatch_failed",
            status="failed",
            progress=100,
            message=str(exc),
            payload={"execution_id": str(retry_execution.id), "queue": settings.CELERY_WORKFLOW_QUEUE},
        )
        generate_execution_manifest(db, study=study, pipeline=pipeline, execution=retry_execution)
        record_audit_event(
            db,
            study_id=study.id,
            action="pipeline.execution.retry_dispatch_failed",
            actor_id=current_user.id,
            resource_kind="pipeline_execution",
            resource_id=retry_execution.id,
            resource_label=pipeline.name,
            metadata={
                "pipeline_id": retry_execution.pipeline_id,
                "execution_seq": retry_execution.execution_seq,
                "retry_of_execution_id": str(source_execution.id),
                "error": str(exc),
                "lock_id": str(execution_lock.id),
            },
        )
        db.commit()
        db.refresh(retry_execution)
    return pipeline_execution_to_response(retry_execution)


@router.get("/studies/{study_id}/pipeline-executions/{execution_id}/jobs", response_model=PipelineJobListResponse)
def list_pipeline_execution_jobs(
    study_id: str,
    execution_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    execution = get_pipeline_execution_or_404(db, study.id, execution_id)
    jobs = (
        db.query(PipelineJob)
        .filter(PipelineJob.study_id == study.id, PipelineJob.execution_id == execution.id)
        .order_by(PipelineJob.topo_index.asc(), PipelineJob.node_id.asc())
        .all()
    )
    return PipelineJobListResponse(jobs=[pipeline_job_to_response(item) for item in jobs])


# ===========================================================================
# Derived Dataset 路由 — 替代旧 pipeline-artifacts 路由
# ===========================================================================

@router.get(
    "/studies/{study_id}/pipeline-executions/{execution_id}/derived-datasets",
    response_model=DerivedDatasetListResponse,
)
def list_pipeline_execution_derived_datasets(
    study_id: str,
    execution_id: UUID,
    include_deleted: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出某次执行（Execution）产出的所有 derived_datasets。"""
    study = get_study_for_read(study_id, db, current_user)
    execution = get_pipeline_execution_or_404(db, study.id, execution_id)
    query = db.query(DerivedDataset).filter(
        DerivedDataset.study_id == study.id,
        DerivedDataset.produced_by_execution_id == execution.id,
    )
    if not include_deleted:
        query = query.filter(DerivedDataset.retention_status != "deleted")
    datasets = query.order_by(DerivedDataset.created_at.asc(), DerivedDataset.id.asc()).all()
    return DerivedDatasetListResponse(
        derived_datasets=[derived_dataset_to_response(item) for item in datasets],
        total=len(datasets),
    )


@router.get(
    "/studies/{study_id}/derived-datasets",
    response_model=DerivedDatasetListResponse,
)
def list_derived_datasets(
    study_id: str,
    execution_ids: list[str] | None = Query(default=None),
    node_types: list[str] | None = Query(default=None),
    data_types: list[str] | None = Query(default=None),
    bids_subject_ids: list[str] | None = Query(default=None),
    sessions: list[str] | None = Query(default=None),
    tasks: list[str] | None = Query(default=None),
    conditions: list[str] | None = Query(default=None),
    tags: list[str] | None = Query(default=None),
    retention_statuses: list[str] | None = Query(default=None),
    include_deleted: bool = Query(default=False),
    include_cross_study: bool = Query(
        default=False,
        description="Phase 3 (docs_v2/3-25): 列出其他 Study 已发布且共享的派生数据 (lifecycle_state='published' AND visibility='shared')",
    ),
    limit: int = Query(default=200, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """跨执行（Execution）列出研究项的派生数据集，支持多维筛选。用于 /results 页面。

    Phase 3 (docs_v2/3-25):
        include_cross_study=True 时,在本 Study 的派生数据之外,附加列出其他 Study
        中 lifecycle_state='published' AND visibility='shared' 的派生数据,用于
        新建 Pipeline 时选择跨 Study 的上游派生数据。
    """
    from sqlalchemy import and_ as _and, or_ as _or

    study = get_study_for_read(study_id, db, current_user)
    if include_cross_study:
        scope_filter = _or(
            DerivedDataset.study_id == study.id,
            _and(
                DerivedDataset.study_id != study.id,
                DerivedDataset.lifecycle_state == "published",
                DerivedDataset.visibility == "shared",
            ),
        )
        query = db.query(DerivedDataset).filter(scope_filter)
    else:
        query = db.query(DerivedDataset).filter(DerivedDataset.study_id == study.id)
    if not include_deleted:
        query = query.filter(DerivedDataset.retention_status != "deleted")
    if execution_ids:
        query = query.filter(DerivedDataset.produced_by_execution_id.in_(execution_ids))
    if node_types:
        query = query.filter(DerivedDataset.produced_by_node_type.in_(node_types))
    if data_types:
        query = query.filter(DerivedDataset.data_type.in_(data_types))
    if bids_subject_ids:
        query = query.filter(DerivedDataset.bids_subject_id.in_(bids_subject_ids))
    if sessions:
        query = query.filter(DerivedDataset.session.in_(sessions))
    if tasks:
        query = query.filter(DerivedDataset.task.in_(tasks))
    if conditions:
        query = query.filter(DerivedDataset.condition.in_(conditions))
    if retention_statuses:
        query = query.filter(DerivedDataset.retention_status.in_(retention_statuses))
    if tags:
        # JSONB contains: 任一 tag 匹配即可
        from sqlalchemy import or_ as _or
        tag_filters = [DerivedDataset.tags.contains([tag]) for tag in tags]
        query = query.filter(_or(*tag_filters))

    total = query.count()
    datasets = (
        query.order_by(DerivedDataset.created_at.desc(), DerivedDataset.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return DerivedDatasetListResponse(
        derived_datasets=[derived_dataset_to_response(item) for item in datasets],
        total=total,
    )


@router.get(
    "/studies/{study_id}/derived-datasets/{dataset_id}",
    response_model=DerivedDatasetResponse,
)
def get_derived_dataset(
    study_id: str,
    dataset_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    dataset = get_derived_dataset_or_404(db, study.id, dataset_id)
    return derived_dataset_to_response(dataset)


@router.patch(
    "/studies/{study_id}/derived-datasets/{dataset_id}",
    response_model=DerivedDatasetResponse,
)
def update_derived_dataset(
    study_id: str,
    dataset_id: UUID,
    payload: DerivedDatasetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """统一的 PATCH 入口：可改 display_name / description / tags / retention_status。"""
    study = get_study_for_write(study_id, db, current_user)
    dataset = get_derived_dataset_or_404(db, study.id, dataset_id)

    if payload.display_name is not None:
        dataset.display_name = payload.display_name.strip() or None
    if payload.description is not None:
        dataset.description = payload.description.strip() or None
    if payload.tags is not None:
        seen: set[str] = set()
        cleaned: list[str] = []
        for tag in payload.tags:
            text = str(tag).strip()
            if text and text not in seen:
                seen.add(text)
                cleaned.append(text)
        dataset.tags = cleaned
    if payload.retention_status is not None:
        apply_derived_dataset_retention_action(
            db,
            study=study,
            dataset=dataset,
            current_user=current_user,
            target_status=payload.retention_status,
            action=f"derived_dataset.retention.{payload.retention_status}",
            reason=payload.reason,
        )
    if payload.retention_expires_at is not None:
        dataset.retention_expires_at = payload.retention_expires_at
    dataset.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(dataset)
    return derived_dataset_to_response(dataset)


@router.post(
    "/studies/{study_id}/derived-datasets/batch-update",
    response_model=DerivedDatasetListResponse,
)
def batch_update_derived_datasets(
    study_id: str,
    payload: DerivedDatasetBatchUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """对多个 derived_datasets 应用同一组改动。用于 /results 页批量打标签 / 改保留策略。"""
    study = get_study_for_write(study_id, db, current_user)
    datasets = (
        db.query(DerivedDataset)
        .filter(DerivedDataset.study_id == study.id, DerivedDataset.id.in_(payload.ids))
        .all()
    )
    found_ids = {str(d.id) for d in datasets}
    missing = [pid for pid in payload.ids if pid not in found_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "DERIVED_DATASET_BATCH_NOT_FOUND",
                "message": "部分派生数据集不存在",
                "missing_ids": missing,
            },
        )
    upd = payload.update
    # 事务原子性：apply_derived_dataset_retention_action 命中依赖 blocker 时会先 db.commit()
    # 再抛 409。批量循环里若第 N 条撞 blocker，会把前 N-1 条的改动一并提交后抛错，造成
    # "部分成功 + 无回滚"。因此当目标是 deleted 时，先全量预检所有 blocker，任一被挡就
    # 在改动任何数据之前一次性 409，循环内便不会再触发 commit-then-raise。
    if upd.retention_status == ARTIFACT_DELETED_STATUS:
        blocked: list[dict[str, Any]] = []
        for ds in datasets:
            try:
                assert_artifact_can_be_deleted(db, artifact=ds)
            except ArtifactDependencyError as exc:
                blocked.append(
                    {"derived_dataset_id": str(ds.id), "dependencies": exc.blockers}
                )
        if blocked:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "DERIVED_DATASET_BATCH_BLOCKED",
                    "message": "部分派生数据集被下游引用，无法删除/隐藏；批量操作已整体取消。",
                    "blocked": blocked,
                },
            )
    for ds in datasets:
        if upd.display_name is not None:
            ds.display_name = upd.display_name.strip() or None
        if upd.description is not None:
            ds.description = upd.description.strip() or None
        if upd.tags is not None:
            seen: set[str] = set()
            cleaned: list[str] = []
            for tag in upd.tags:
                text = str(tag).strip()
                if text and text not in seen:
                    seen.add(text)
                    cleaned.append(text)
            ds.tags = cleaned
        if upd.retention_status is not None:
            apply_derived_dataset_retention_action(
                db,
                study=study,
                dataset=ds,
                current_user=current_user,
                target_status=upd.retention_status,
                action=f"derived_dataset.batch.retention.{upd.retention_status}",
                reason=upd.reason,
            )
        if upd.retention_expires_at is not None:
            ds.retention_expires_at = upd.retention_expires_at
        ds.updated_at = datetime.utcnow()
    db.commit()
    for ds in datasets:
        db.refresh(ds)
    return DerivedDatasetListResponse(
        derived_datasets=[derived_dataset_to_response(ds) for ds in datasets],
        total=len(datasets),
    )


@router.post(
    "/studies/{study_id}/derived-datasets/cleanup",
    response_model=AsyncTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_derived_dataset_cleanup_task(
    study_id: str,
    payload: DerivedDatasetCleanupRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """派生数据集清理任务：按 retention_status + retention_expires_at 决定回收。"""
    study = get_study_for_write(study_id, db, current_user)
    payload = payload or DerivedDatasetCleanupRequest()
    payload_json = {
        "study_id": study.id,
        "retention_statuses": payload.retention_statuses,
        "dry_run": payload.dry_run,
        "limit": payload.limit,
        "reason": payload.reason,
    }
    return create_and_dispatch_file_task(
        db,
        task_type="derived_dataset_cleanup",
        study_id=study.id,
        resource_kind="study_derived_datasets",
        resource_id=None,
        payload_json=payload_json,
        current_user=current_user,
    )


@router.get(
    "/studies/{study_id}/derived-datasets/{dataset_id}/preview",
    response_model=DerivedDatasetPreviewResponse,
)
def get_derived_dataset_preview(
    study_id: str,
    dataset_id: UUID,
    max_channels: int = Query(default=MAX_EVOKED_CHANNELS, ge=1, le=256),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    dataset = get_derived_dataset_or_404(db, study.id, dataset_id)
    if dataset.retention_status == "deleted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DERIVED_DATASET_DELETED", "message": "派生数据集已被隐藏，预览不可用。"},
        )
    try:
        preview = build_derived_dataset_preview(study, dataset, sample_channels=max_channels)
    except DerivedDatasetPreviewError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "derived_dataset_id": str(dataset_id)},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "DERIVED_DATASET_PREVIEW_ENGINE_UNAVAILABLE", "message": str(exc)},
        ) from exc

    dataset.preview_json = preview["preview_json"]
    dataset.updated_at = datetime.utcnow()
    db.commit()
    # build_derived_dataset_preview 仍以 artifact_id 为字段名输出；映射到 derived_dataset_id
    return DerivedDatasetPreviewResponse(
        derived_dataset_id=preview.get("artifact_id") or str(dataset.id),
        study_id=preview.get("study_id") or study.id,
        produced_by_execution_id=preview.get("execution_id"),
        produced_by_job_id=preview.get("job_id"),
        data_type=preview.get("data_type") or dataset.data_type,
        storage_uri=preview.get("storage_uri"),
        sha256=preview.get("sha256"),
        retention_status=preview.get("retention_status"),
        preview_json=preview.get("preview_json") or {},
        observe_route=preview.get("observe_route") or "/observe",
        observe_query=preview.get("observe_query") or {},
        generated_at=preview.get("generated_at") or datetime.utcnow(),
    )


@router.get("/studies/{study_id}/derived-datasets/{dataset_id}/timeseries")
def get_derived_dataset_timeseries(
    study_id: str,
    dataset_id: UUID,
    tmin: float | None = Query(default=None),
    tmax: float | None = Query(default=None),
    index: int | None = Query(default=None, ge=0),
    max_points: int = Query(default=2000, ge=50, le=8000),
    max_channels: int = Query(default=64, ge=1, le=256),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    dataset = get_derived_dataset_or_404(db, study.id, dataset_id)
    if dataset.retention_status == "deleted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DERIVED_DATASET_DELETED", "message": "派生数据集已被隐藏，时域数据不可用。"},
        )
    try:
        return build_timeseries(
            study,
            dataset,
            tmin=tmin,
            tmax=tmax,
            index=index,
            max_points=max_points,
            max_channels=max_channels,
        )
    except DerivedDatasetPreviewError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "derived_dataset_id": str(dataset_id)},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "DERIVED_DATASET_TIMESERIES_ENGINE_UNAVAILABLE", "message": str(exc)},
        ) from exc


@router.get("/studies/{study_id}/derived-datasets/{dataset_id}/download")
def download_derived_dataset(
    study_id: str,
    dataset_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    dataset = get_derived_dataset_or_404(db, study.id, dataset_id)
    if dataset.retention_status == "deleted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DERIVED_DATASET_DELETED", "message": "派生数据集已被隐藏，下载不可用。"},
        )
    try:
        path = resolve_derived_dataset_path(study, dataset)
        validate_derived_dataset_file(path, dataset)
    except DerivedDatasetPreviewError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "derived_dataset_id": str(dataset_id)},
        ) from exc
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DERIVED_DATASET_DOWNLOAD_DIRECTORY_UNSUPPORTED", "message": "Directory download is not supported."},
        )
    dataset.updated_at = datetime.utcnow()
    db.commit()
    filename = dataset.display_name or Path(str(dataset.logical_path or dataset.storage_uri or "")).name or f"derived-{dataset.id}"
    filename = re.sub(r"[\\/:*?\"<>|]", "_", str(filename))
    return FileResponse(path, media_type="application/octet-stream", filename=filename)


@router.get(
    "/studies/{study_id}/pipeline-executions/{execution_id}/jobs/{job_id}/interaction",
    response_model=PipelineInteractionResponse,
)
def get_pipeline_node_interaction(
    study_id: str,
    execution_id: UUID,
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    execution = get_pipeline_execution_or_404(db, study.id, execution_id)
    job = get_pipeline_job_or_404(db, study.id, execution.id, job_id)
    return interaction_to_response(job)


@router.post(
    "/studies/{study_id}/pipeline-executions/{execution_id}/jobs/{job_id}/decision",
    response_model=PipelineInteractionDecisionResponse,
)
def submit_pipeline_node_decision(
    study_id: str,
    execution_id: UUID,
    job_id: UUID,
    payload: PipelineInteractionDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_write(study_id, db, current_user)
    execution = get_pipeline_execution_or_404(db, study.id, execution_id)
    job = get_pipeline_job_or_404(db, study.id, execution.id, job_id)
    if job.status != "waiting_user_input":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "PIPELINE_NODE_NOT_WAITING", "message": "Pipeline node is not waiting for user input."},
        )
    apply_interaction_decision(job, payload, current_user=current_user)
    db.commit()
    db.refresh(job)
    return interaction_to_response(job)


@router.post(
    "/studies/{study_id}/pipeline-executions/{execution_id}/jobs/{job_id}/resume",
    response_model=PipelineResumeResponse,
)
def resume_pipeline_node(
    study_id: str,
    execution_id: UUID,
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_write(study_id, db, current_user)
    execution = get_pipeline_execution_or_404(db, study.id, execution_id)
    job = get_pipeline_job_or_404(db, study.id, execution.id, job_id)
    interaction = job_interaction(job)
    if not isinstance(interaction.get("decision"), dict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "PIPELINE_DECISION_REQUIRED", "message": "Submit an ICA decision before resuming the execution."},
        )
    run_pipeline_execution_sync(db, execution.id, commit_progress=False, start_topo_index=job.topo_index)
    db.commit()
    db.refresh(execution)
    db.refresh(job)
    return PipelineResumeResponse(
        execution=pipeline_execution_to_response(execution),
        job=pipeline_job_to_response(job),
    )


def _raise_pipeline_execution_locked(lock, study_id: str, pipeline_id: int) -> None:
    """统一抛出 409 PIPELINE_EXECUTION_LOCKED 错误。"""
    detail = {
        "code": "PIPELINE_EXECUTION_LOCKED",
        "message": "该工作流正在被运行，请等待当前运行结束或锁过期后再试。",
        "study_id": study_id,
        "pipeline_id": pipeline_id,
    }
    if lock is not None:
        detail.update(
            {
                "lock_id": str(lock.id),
                "locked_by": str(lock.locked_by) if lock.locked_by else None,
                "locked_at": lock.locked_at.isoformat() if lock.locked_at else None,
                "expires_at": lock.expires_at.isoformat() if lock.expires_at else None,
            }
        )
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _create_pipeline_execution(
    study_id: str,
    pipeline_id: int,
    payload: PipelineExecutionCreate | None,
    db: Session,
    current_user: User,
) -> PipelineExecutionResponse:
    payload = payload or PipelineExecutionCreate()
    study = get_study_for_run(study_id, db, current_user)
    pipeline = get_pipeline_or_404(db, study.id, pipeline_id)
    trigger = payload.trigger
    execution_mode = payload.execution_mode
    save_policy = payload.save_policy
    selection_override = normalize_selection_override(
        payload.model_dump(mode="json", exclude_none=True).get("selection_override")
    )
    status_violation = pipeline_execution_status_violation(pipeline.status, execution_mode)
    if status_violation is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=status_violation)

    definition_for_validation = apply_load_data_selection_overrides(pipeline.definition_json, selection_override)
    validation = validate_definition(definition_for_validation, db=db, study=study)
    if not validation.valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "PIPELINE_EXECUTION_INPUT_INVALID",
                "message": "工作流输入校验未通过，请修正后再运行。",
                "errors": [issue.model_dump(mode="json") for issue in validation.errors],
                "warnings": [issue.model_dump(mode="json") for issue in validation.warnings],
            },
    )
    settings = get_settings()
    async_task_id = uuid4()

    # run_policy.single_active_pipeline_run（默认 True）：整个 Study 同一时刻只允许一个
    # 活跃 Execution。per-pipeline 运行锁只挡同一 Pipeline 的并发，挡不住"同 Study 不同
    # Pipeline 同时跑"，故在此按策略做 Study 级前置检查。
    # 注：这是前置查询，与"拿锁前的瞬间"之间存在极小竞态窗口（同 Pipeline 由下面的运行锁
    # 兜底）；要做成硬互斥需引入 Study 级锁，留待后续。
    settings_row = (
        db.query(StudySettings).filter(StudySettings.study_id == study.id).first()
    )
    run_policy = (
        settings_row.run_policy
        if settings_row is not None and isinstance(settings_row.run_policy, dict)
        else {}
    ) or {}
    if run_policy.get("single_active_pipeline_run", True):
        active_execution = (
            db.query(PipelineExecution)
            .filter(
                PipelineExecution.study_id == study.id,
                PipelineExecution.status.in_(
                    ("queued", "running", "waiting_user_input")
                ),
            )
            .first()
        )
        if active_execution is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "STUDY_EXECUTION_ACTIVE",
                    "message": "该研究项已有正在进行的运行，请等待其结束或在研究项设置中关闭单活跃运行限制。",
                    "active_execution_id": str(active_execution.id),
                    "active_pipeline_id": active_execution.pipeline_id,
                },
            )

    def _try_acquire_lock():
        return acquire_study_lock(
            db,
            study_id=study.id,
            resource_kind="pipeline",
            resource_id=pipeline.id,
            lock_type="execution",
            locked_by=current_user.id,
            ttl_seconds=DEFAULT_STUDY_LOCK_TTL_SECONDS,
            metadata={
                "pipeline_id": pipeline.id,
                "pipeline_version": pipeline.version,
                "trigger": trigger,
                "execution_mode": execution_mode,
                "save_policy": save_policy,
                "reason": "pipeline_execution",
            },
        )

    try:
        execution_lock = _try_acquire_lock()
    except StudyLockConflictError:
        # 第一次失败：尝试清理 stale 锁（worker 异常退出 / 关联 execution 已结束的孤立锁）后重试
        released_count = force_release_stale_pipeline_execution_locks(
            db, study_id=study.id, pipeline_id=pipeline.id,
        )
        if released_count > 0:
            db.flush()
            try:
                execution_lock = _try_acquire_lock()
            except StudyLockConflictError as exc2:
                execution_lock = None
                _raise_pipeline_execution_locked(exc2.lock, study.id, pipeline.id)
        else:
            # 没找到 stale 锁，通常是真有别的 execution 在跑。但在"第一次尝试失败"
            # 与这次重试之间，那个 execution 有可能刚好结束并释放了锁（并发窗口），
            # 此时重试会成功——必须接收返回值采用它，否则 execution_lock 未绑定会
            # 在后面 str(execution_lock.id) 抛 UnboundLocalError，且这把刚拿到的锁
            # 会泄漏到 TTL。
            try:
                execution_lock = _try_acquire_lock()
            except StudyLockConflictError as exc2:
                execution_lock = None
                _raise_pipeline_execution_locked(exc2.lock, study.id, pipeline.id)

    execution = PipelineExecution(
        study_id=study.id,
        pipeline_id=pipeline.id,
        pipeline_version=pipeline.version,
        execution_seq=next_pipeline_execution_seq(db, study.id, pipeline.id),
        trigger=trigger,
        execution_mode=execution_mode,
        save_policy=save_policy,
        status="queued",
        node_count=count_nodes(pipeline.definition_json),
        dataset_count=0,
        definition_snapshot=pipeline.definition_json,
        result_json={
            "mode": "celery",
            "executor": "PipelineExecutor",
            "message": "Pipeline execution queued.",
            "async_task_id": str(async_task_id),
            "celery_task_id": str(async_task_id),
            "task_queue": settings.CELERY_WORKFLOW_QUEUE,
            "execution_lock_id": str(execution_lock.id),
            "execution_lock_expires_at": execution_lock.expires_at.isoformat(),
            "execution_mode": execution_mode,
            "save_policy": save_policy,
            "selection_override": selection_override,
            "node_results": [],
            "data_infos_by_node": {},
            "warnings": [],
        },
        error_json={},
        started_by=current_user.id,
    )
    db.add(execution)
    db.flush()
    async_task = AsyncTask(
        id=async_task_id,
        celery_task_id=str(async_task_id),
        task_type="pipeline_execution",
        queue_name=settings.CELERY_WORKFLOW_QUEUE,
        status="queued",
        progress=0,
        study_id=study.id,
        resource_kind="pipeline_execution",
        resource_id=execution.id,
        payload_json={
            "execution_id": str(execution.id),
            "study_id": study.id,
            "pipeline_id": pipeline.id,
            "pipeline_version": pipeline.version,
            "execution_seq": execution.execution_seq,
            "trigger": trigger,
            "execution_mode": execution_mode,
            "save_policy": save_policy,
            "selection_override": selection_override,
            "lock_id": str(execution_lock.id),
            "lock_expires_at": execution_lock.expires_at.isoformat(),
        },
        result_json={},
        error_json={},
        created_by=current_user.id,
    )
    db.add(async_task)
    record_task_event(
        db,
        async_task,
        "created",
        status="queued",
        progress=0,
        message="Pipeline execution task created.",
        payload={"execution_id": str(execution.id), "pipeline_id": pipeline.id},
    )
    record_audit_event(
        db,
        study_id=study.id,
        action="pipeline.execution.queued",
        actor_id=current_user.id,
        resource_kind="pipeline_execution",
        resource_id=execution.id,
        resource_label=pipeline.name,
        metadata={
            "pipeline_id": pipeline.id,
            "pipeline_version": pipeline.version,
            "execution_seq": execution.execution_seq,
            "trigger": trigger,
            "execution_mode": execution_mode,
            "save_policy": save_policy,
            "async_task_id": str(async_task.id),
            "lock_id": str(execution_lock.id),
            "lock_expires_at": execution_lock.expires_at.isoformat(),
        },
    )
    PipelineExecutor(db).prepare_execution(study=study, pipeline=pipeline, execution=execution)
    db.commit()
    db.refresh(execution)
    db.refresh(async_task)
    execute_inline, dispatch_reason, worker_info = should_execute_pipeline_inline(settings)
    if execute_inline:
        execution = execute_pipeline_execution_inline(
            db,
            study=study,
            pipeline=pipeline,
            execution=execution,
            async_task=async_task,
            current_user=current_user,
            dispatch_reason=dispatch_reason,
            worker_info=worker_info,
            started_message="Pipeline execution task started inline.",
        )
        return pipeline_execution_to_response(execution)
    try:
        task = run_pipeline_task.apply_async(
            args=[str(execution.id)],
            kwargs={"study_id": study.id},
            queue=settings.CELERY_WORKFLOW_QUEUE,
            task_id=str(async_task_id),
        )
        if async_task.celery_task_id != task.id:
            async_task.celery_task_id = task.id
        execution.result_json = {
            **(execution.result_json or {}),
            "async_task_id": str(async_task.id),
            "celery_task_id": task.id,
            "task_queue": settings.CELERY_WORKFLOW_QUEUE,
            "execution_lock_id": str(execution_lock.id),
            "execution_lock_expires_at": execution_lock.expires_at.isoformat(),
        }
        record_task_event(
            db,
            async_task,
            "dispatched",
            message="Pipeline execution task dispatched to Celery.",
            payload={"celery_task_id": task.id, "queue": settings.CELERY_WORKFLOW_QUEUE},
        )
        db.commit()
        db.refresh(execution)
    except Exception as exc:
        mark_execution_dispatch_failed(db, execution, str(exc))
        release_study_lock(db, execution_lock, released_by=current_user.id, reason="dispatch_failed")
        async_task.result_json = {"execution_id": str(execution.id), "execution_status": execution.status}
        async_task.error_json = execution.error_json or {}
        record_task_event(
            db,
            async_task,
            "dispatch_failed",
            status="failed",
            progress=100,
            message=str(exc),
            payload={"execution_id": str(execution.id), "queue": settings.CELERY_WORKFLOW_QUEUE},
        )
        generate_execution_manifest(db, study=study, pipeline=pipeline, execution=execution)
        record_audit_event(
            db,
            study_id=study.id,
            action="pipeline.execution.dispatch_failed",
            actor_id=current_user.id,
            resource_kind="pipeline_execution",
            resource_id=execution.id,
            resource_label=pipeline.name,
            metadata={
                "pipeline_id": pipeline.id,
                "execution_seq": execution.execution_seq,
                "error": str(exc),
                "lock_id": str(execution_lock.id),
            },
        )
        db.commit()
        db.refresh(execution)
    return pipeline_execution_to_response(execution)


@router.post("/studies/{study_id}/pipelines/{pipeline_id}/executions", response_model=PipelineExecutionResponse)
def create_pipeline_execution(
    study_id: str,
    pipeline_id: int,
    payload: PipelineExecutionCreate | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _create_pipeline_execution(
        study_id=study_id,
        pipeline_id=pipeline_id,
        payload=payload,
        db=db,
        current_user=current_user,
    )


@router.post("/studies/{study_id}/pipelines/{pipeline_id}/validate", response_model=PipelineValidationResponse)
def validate_pipeline(
    study_id: str,
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    pipeline = get_pipeline_or_404(db, study.id, pipeline_id)
    return validate_definition(pipeline.definition_json, db=db, study=study)
