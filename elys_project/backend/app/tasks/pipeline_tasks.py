"""
Purpose: Configure or run Celery background tasks for asynchronous Pipeline execution.
Related: app/pipeline/background.py, app/routers/pipelines.py, deploy/profiles/*.env, docs_v2/2-60.
"""

from __future__ import annotations

from celery.utils.log import get_task_logger

from app.database import SessionLocal
from app.models import PipelineDefinition, PipelineExecution, Study
from app.pipeline.background import run_pipeline_execution_sync
from app.pipeline.execution_manifest import generate_execution_manifest
from app.services.audit_events import record_audit_event
from app.services.study_locks import release_study_lock_by_id, release_study_locks_for_resource
from app.services.task_events import (
    find_async_task_by_celery_id,
    find_async_task_for_pipeline_execution,
    record_task_event,
    task_status_for_pipeline_execution,
)
from app.tasks.celery_app import celery_app


logger = get_task_logger(__name__)


def release_pipeline_execution_lock(db, *, execution: PipelineExecution | None, async_task, reason: str):
    payload_json = async_task.payload_json if async_task is not None else {}
    lock_id = payload_json.get("lock_id") if isinstance(payload_json, dict) else None
    released_by = execution.started_by if execution is not None else None
    released_lock = release_study_lock_by_id(db, lock_id, released_by=released_by, reason=reason)
    if released_lock is not None:
        return [released_lock]
    if execution is None:
        return []
    return release_study_locks_for_resource(
        db,
        study_id=execution.study_id,
        resource_kind="pipeline",
        resource_id=execution.pipeline_id,
        lock_type="execution",
        released_by=released_by,
        reason=reason,
    )


@celery_app.task(bind=True, name="app.tasks.pipeline_tasks.run_pipeline_task")
def run_pipeline_task(self, execution_id: str, study_id: str | None = None) -> dict[str, str | None]:
    db = SessionLocal()
    celery_task_id = getattr(getattr(self, "request", None), "id", None)
    execution = None
    try:
        async_task = find_async_task_by_celery_id(db, celery_task_id) or find_async_task_for_pipeline_execution(db, execution_id)
        if async_task is not None:
            record_task_event(
                db,
                async_task,
                "started",
                status="running",
                progress=5,
                message="Pipeline execution task started.",
                payload={"execution_id": execution_id, "celery_task_id": celery_task_id},
            )
            db.commit()

        execution = run_pipeline_execution_sync(db, execution_id, commit_progress=True)
        async_task = find_async_task_by_celery_id(db, celery_task_id) or find_async_task_for_pipeline_execution(db, execution.id)
        if async_task is not None:
            task_status = task_status_for_pipeline_execution(execution)
            event_type = "failed" if task_status == "failed" else execution.status
            async_task.result_json = {
                "execution_id": str(execution.id),
                "study_id": study_id or execution.study_id,
                "pipeline_id": execution.pipeline_id,
                "execution_status": execution.status,
            }
            async_task.error_json = (execution.error_json or {}) if task_status == "failed" else {}
            record_task_event(
                db,
                async_task,
                event_type,
                status=task_status,
                progress=100,
                message=f"Pipeline execution finished with status: {execution.status}.",
                payload={"execution_id": str(execution.id), "execution_status": execution.status, "celery_task_id": celery_task_id},
            )
        refresh_execution_manifest(db, execution=execution)
        released_locks = release_pipeline_execution_lock(
            db,
            execution=execution,
            async_task=async_task,
            reason=f"execution_{execution.status}",
        )
        record_audit_event(
            db,
            study_id=execution.study_id,
            action=f"pipeline.execution.{execution.status}",
            actor_id=execution.started_by,
            resource_kind="pipeline_execution",
            resource_id=execution.id,
            metadata={
                "pipeline_id": execution.pipeline_id,
                "execution_seq": execution.execution_seq,
                "execution_status": execution.status,
                "celery_task_id": celery_task_id,
                "released_lock_ids": [str(lock.id) for lock in released_locks],
            },
        )
        db.commit()
        return {
            "execution_id": str(execution.id),
            "study_id": study_id or execution.study_id,
            "status": execution.status,
        }
    except Exception as exc:
        db.rollback()
        if execution is None:
            try:
                execution = db.query(PipelineExecution).filter(PipelineExecution.id == execution_id).first()
            except Exception:
                logger.exception("Remedial execution lookup failed during error handling: %s", execution_id)
                execution = None
        async_task = find_async_task_by_celery_id(db, celery_task_id) or find_async_task_for_pipeline_execution(db, execution_id)
        if async_task is not None:
            async_task.error_json = {
                "errors": [
                    {
                        "code": "PIPELINE_CELERY_TASK_ERROR",
                        "message": str(exc),
                        "severity": "error",
                    }
                ]
            }
            record_task_event(
                db,
                async_task,
                "failed",
                status="failed",
                progress=100,
                message=str(exc),
                payload={"execution_id": execution_id, "celery_task_id": celery_task_id},
            )
        try:
            released_locks = release_pipeline_execution_lock(
                db,
                execution=execution,
                async_task=async_task,
                reason="task_exception",
            )
        except Exception:
            logger.exception("Failed to release pipeline execution lock during error handling: %s", execution_id)
            released_locks = []
        if execution is not None:
            record_audit_event(
                db,
                study_id=execution.study_id,
                action="pipeline.execution.task_exception",
                actor_id=execution.started_by,
                resource_kind="pipeline_execution",
                resource_id=execution.id,
                metadata={
                    "pipeline_id": execution.pipeline_id,
                    "execution_seq": execution.execution_seq,
                    "error": str(exc),
                    "celery_task_id": celery_task_id,
                    "released_lock_ids": [str(lock.id) for lock in released_locks],
                },
            )
        if async_task is not None or execution is not None or released_locks:
            if execution is not None:
                refresh_execution_manifest(db, execution=execution)
            db.commit()
        logger.exception("Pipeline execution task failed before DB failure handling completed: %s", execution_id)
        raise
    finally:
        db.close()


def refresh_execution_manifest(db, *, execution: PipelineExecution) -> None:
    study = db.query(Study).filter(Study.id == execution.study_id).first()
    if study is None:
        return
    pipeline = (
        db.query(PipelineDefinition)
        .filter(PipelineDefinition.id == execution.pipeline_id, PipelineDefinition.study_id == execution.study_id)
        .first()
    )
    generate_execution_manifest(db, study=study, pipeline=pipeline, execution=execution)
