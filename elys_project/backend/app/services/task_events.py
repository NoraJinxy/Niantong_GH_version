"""
Purpose: Track asynchronous task state and event history.
Related: app/models/study.py, app/tasks/pipeline_tasks.py, app/routers/pipelines.py, docs_v2/7-30.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import AsyncTask, PipelineExecution, TaskEvent


TASK_TERMINAL_STATUSES = {"succeeded", "failed", "canceled"}


def normalize_task_progress(progress: float | int | str | Decimal | None) -> Decimal | None:
    if progress is None:
        return None
    try:
        value = Decimal(str(progress))
    except (InvalidOperation, ValueError):
        return None
    return min(Decimal("100"), max(Decimal("0"), value.quantize(Decimal("0.01"))))


def find_async_task_by_celery_id(db: Session, celery_task_id: str | None) -> AsyncTask | None:
    if not celery_task_id:
        return None
    filters = [AsyncTask.celery_task_id == celery_task_id]
    try:
        filters.append(AsyncTask.id == UUID(str(celery_task_id)))
    except ValueError:
        pass
    return db.query(AsyncTask).filter(or_(*filters)).order_by(AsyncTask.created_at.desc()).first()


def find_async_task_for_pipeline_execution(db: Session, execution_id: str | UUID) -> AsyncTask | None:
    resolved_execution_id = UUID(str(execution_id))
    return (
        db.query(AsyncTask)
        .filter(AsyncTask.resource_kind == "pipeline_execution", AsyncTask.resource_id == resolved_execution_id)
        .order_by(AsyncTask.created_at.desc())
        .first()
    )


def task_status_for_pipeline_execution(execution: PipelineExecution) -> str:
    if execution.status in {"completed", "waiting_user_input"}:
        return "succeeded"
    if execution.status == "failed":
        return "failed"
    if execution.status == "canceled":
        return execution.status
    return "running"


def record_task_event(
    db: Session,
    task: AsyncTask,
    event_type: str,
    *,
    status: str | None = None,
    progress: float | int | str | Decimal | None = None,
    message: str | None = None,
    payload: dict[str, Any] | None = None,
) -> TaskEvent:
    now = datetime.utcnow()
    normalized_progress = normalize_task_progress(progress)

    if status is not None:
        task.status = status
        if status in {"running", "retrying"} and task.started_at is None:
            task.started_at = now
        if status in TASK_TERMINAL_STATUSES and task.finished_at is None:
            task.finished_at = now
    if normalized_progress is not None:
        task.progress = normalized_progress

    event = TaskEvent(
        task_id=task.id,
        event_type=event_type,
        status=status if status is not None else task.status,
        progress=normalized_progress if normalized_progress is not None else task.progress,
        message=message,
        payload_json=payload or {},
        created_at=now,
    )
    db.add(event)
    return event
