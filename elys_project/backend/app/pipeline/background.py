"""
Purpose: Implement workflow/Pipeline runtime support for background, including validation, execution, artifacts, cache, or data resolution.
Related: app/routers/pipelines.py, app/tasks/pipeline_tasks.py, app/pipeline/nodes/*.json, docs_v2/5-00 and docs_v2/7-40.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import PipelineDefinition, PipelineJob, PipelineExecution, Study
from app.pipeline.executor import PipelineExecutor
from app.pipeline.execution_manifest import generate_execution_manifest


def run_pipeline_execution_sync(
    db: Session,
    execution_id: str | UUID,
    *,
    commit_progress: bool = True,
    start_topo_index: int = 0,
) -> PipelineExecution:
    resolved_execution_id = UUID(str(execution_id))
    execution = db.query(PipelineExecution).filter(PipelineExecution.id == resolved_execution_id).first()
    if execution is None:
        raise ValueError(f"Pipeline execution not found: {resolved_execution_id}")
    if execution.status == "canceled":
        if commit_progress:
            db.commit()
        else:
            db.flush()
        return execution

    study = db.query(Study).filter(Study.id == execution.study_id).first()
    pipeline = (
        db.query(PipelineDefinition)
        .filter(PipelineDefinition.id == execution.pipeline_id, PipelineDefinition.study_id == execution.study_id)
        .first()
    )
    if study is None or pipeline is None:
        issue = _execution_error_issue(
            "PIPELINE_EXECUTION_CONTEXT_MISSING",
            "Pipeline execution study or pipeline definition is missing.",
        )
        return _mark_execution_failed(db, resolved_execution_id, issue, commit_progress=commit_progress)

    try:
        PipelineExecutor(db).execute_prepared_execution(
            study=study,
            pipeline=pipeline,
            execution=execution,
            commit_progress=commit_progress,
            start_topo_index=start_topo_index,
        )
        if commit_progress:
            db.commit()
        else:
            db.flush()
        return execution
    except Exception as exc:
        db.rollback()
        issue = _execution_error_issue("PIPELINE_EXECUTION_BACKGROUND_ERROR", str(exc))
        return _mark_execution_failed(db, resolved_execution_id, issue, commit_progress=commit_progress)


def _mark_execution_failed(
    db: Session,
    execution_id: UUID,
    issue: dict[str, Any],
    *,
    commit_progress: bool,
) -> PipelineExecution:
    execution = db.query(PipelineExecution).filter(PipelineExecution.id == execution_id).first()
    if execution is None:
        raise ValueError(f"Pipeline execution not found while marking failed: {execution_id}")

    now = datetime.utcnow()
    execution.status = "failed"
    execution.finished_at = now
    execution.error_json = _append_error(execution.error_json, issue)
    result_json = execution.result_json or {}
    execution.result_json = {
        **result_json,
        "mode": result_json.get("mode", "celery"),
        "executor": "PipelineExecutor",
        "message": "Pipeline execution failed before completion. See error_json for details.",
    }

    job = (
        db.query(PipelineJob)
        .filter(PipelineJob.execution_id == execution.id, PipelineJob.status.in_(("running", "pending", "queued")))
        .order_by(PipelineJob.topo_index.asc(), PipelineJob.node_id.asc())
        .first()
    )
    if job is not None:
        node_issue = {
            **issue,
            "node_id": job.node_id,
            "node_type": job.node_type,
        }
        job.status = "failed"
        job.started_at = getattr(job, "started_at", None) or now
        job.finished_at = now
        job.error_json = _append_error(job.error_json, node_issue)
        job.log_tail = node_issue.get("message")
        if getattr(job, "started_at", None):
            job.duration_ms = max(0, int((now - job.started_at).total_seconds() * 1000))

    study = db.query(Study).filter(Study.id == execution.study_id).first()
    pipeline = (
        db.query(PipelineDefinition)
        .filter(PipelineDefinition.id == execution.pipeline_id, PipelineDefinition.study_id == execution.study_id)
        .first()
    )
    if study is not None:
        generate_execution_manifest(db, study=study, pipeline=pipeline, execution=execution)

    if commit_progress:
        db.commit()
    else:
        db.flush()
    return execution


def _execution_error_issue(code: str, message: str) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "severity": "error",
    }


def _append_error(current: Any, issue: dict[str, Any]) -> dict[str, Any]:
    errors = []
    if isinstance(current, dict) and isinstance(current.get("errors"), list):
        errors = [item for item in current["errors"] if isinstance(item, dict)]
    errors.append(issue)
    return {"errors": errors}
