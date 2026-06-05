"""
Purpose: Shared helpers for creating and serializing async_tasks records.
Related: app/models/study.py, app/services/task_events.py, app/routers/pipelines.py.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import AsyncTask, TaskEvent
from app.schemas.pipeline import AsyncTaskResponse, TaskEventResponse
from app.services.task_events import record_task_event


def create_async_task(
    db: Session,
    *,
    task_type: str,
    queue_name: str,
    study_id: str | None,
    resource_kind: str,
    resource_id: Any | None,
    payload_json: dict[str, Any] | None = None,
    created_by: Any | None = None,
    idempotency_key: str | None = None,
) -> AsyncTask:
    task_id = uuid4()
    task = AsyncTask(
        id=task_id,
        celery_task_id=str(task_id),
        task_type=task_type,
        queue_name=queue_name,
        status="queued",
        progress=0,
        study_id=study_id,
        resource_kind=resource_kind,
        resource_id=resource_id,
        payload_json=payload_json or {},
        result_json={},
        error_json={},
        idempotency_key=idempotency_key,
        created_by=created_by,
    )
    db.add(task)
    record_task_event(
        db,
        task,
        "created",
        status="queued",
        progress=0,
        message=f"{task_type} task created.",
        payload=payload_json or {},
    )
    return task


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
        progress=_progress_float(task.progress),
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


def _progress_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
