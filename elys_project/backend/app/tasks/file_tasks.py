"""
Purpose: Run asynchronous Dataset and Artifact file-management tasks.
Related: app/routers/datasets.py, app/routers/pipelines.py, app/services/execution_dependencies.py.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from celery.utils.log import get_task_logger

from app.database import SessionLocal
from app.models import AsyncTask, DatasetAsset, DatasetFile, DerivedDataset, Recording
from app.services.execution_dependencies import artifact_dependency_blockers
from app.services.task_events import find_async_task_by_celery_id, record_task_event
from app.tasks.celery_app import celery_app


logger = get_task_logger(__name__)


@celery_app.task(bind=True, name="app.tasks.file_tasks.run_file_task")
def run_file_task(self, task_id: str) -> dict[str, Any]:
    db = SessionLocal()
    celery_task_id = getattr(getattr(self, "request", None), "id", None)
    try:
        task = _find_task(db, task_id, celery_task_id)
        if task is None:
            raise ValueError(f"Async task not found: {task_id}")
        if celery_task_id and task.celery_task_id != celery_task_id:
            task.celery_task_id = celery_task_id
        if task.status == "canceled":
            return {"task_id": str(task.id), "task_type": task.task_type, "status": task.status}
        record_task_event(
            db,
            task,
            "started",
            status="running",
            progress=5,
            message=f"{task.task_type} task started.",
            payload={"celery_task_id": celery_task_id},
        )
        db.commit()

        if task.task_type == "derived_dataset_cleanup":
            result = run_derived_dataset_cleanup(db, task)
        elif task.task_type == "raw_bids_build":
            result = run_raw_bids_build(db, task)
        elif task.task_type == "canonical_fif_rebuild":
            result = run_canonical_fif_rebuild(db, task)
        elif task.task_type == "dataset_import":
            result = run_dataset_import(db, task)
        else:
            raise ValueError(f"Unsupported file task type: {task.task_type}")

        task.result_json = result
        task.error_json = {}
        record_task_event(
            db,
            task,
            "succeeded",
            status="succeeded",
            progress=100,
            message=f"{task.task_type} task succeeded.",
            payload=result,
        )
        db.commit()
        return {"task_id": str(task.id), "task_type": task.task_type, "status": task.status}
    except Exception as exc:
        db.rollback()
        task = _find_task(db, task_id, celery_task_id)
        if task is not None:
            task.error_json = {
                "errors": [
                    {
                        "code": "FILE_TASK_FAILED",
                        "message": str(exc),
                        "severity": "error",
                    }
                ]
            }
            record_task_event(
                db,
                task,
                "failed",
                status="failed",
                progress=100,
                message=str(exc),
                payload={"celery_task_id": celery_task_id},
            )
            db.commit()
        logger.exception("File task failed: %s", task_id)
        raise
    finally:
        db.close()


def run_derived_dataset_cleanup(db, task: AsyncTask) -> dict[str, Any]:
    """Cleanup derived_datasets whose retention is temporary/cached and (optionally) expired.

    被下游 Execution/节点输入引用的派生数据集会被跳过；其它候选的 retention_status 改为
    "deleted"，物理文件保留以便恢复（实际清盘由后续 garbage collector 完成）。
    """
    payload = task.payload_json or {}
    allowed_statuses = _cleanup_statuses(payload.get("retention_statuses"))
    dry_run = bool(payload.get("dry_run", False))
    limit = int(payload.get("limit") or 500)
    study_id = task.study_id
    if not study_id:
        raise ValueError("derived_dataset_cleanup requires study_id")

    now = datetime.utcnow()
    query = db.query(DerivedDataset).filter(
        DerivedDataset.study_id == study_id,
        DerivedDataset.retention_status.in_(allowed_statuses),
    )
    # 优先回收已过期的临时项；过期为空（pinned/current）的不进
    query = query.order_by(
        DerivedDataset.retention_expires_at.asc().nullslast(),
        DerivedDataset.created_at.asc(),
        DerivedDataset.id.asc(),
    )
    candidates = query.limit(limit).all()

    cleaned = []
    skipped = []
    for dataset in candidates:
        # 没过期且不是 dry_run 的临时项也跳过
        if (
            dataset.retention_expires_at is not None
            and dataset.retention_expires_at > now
            and not dry_run
        ):
            skipped.append(
                {
                    "derived_dataset_id": str(dataset.id),
                    "reason": "not_yet_expired",
                    "retention_expires_at": dataset.retention_expires_at.isoformat(),
                }
            )
            continue
        blockers = artifact_dependency_blockers(db, artifact=dataset, limit=5)
        if blockers:
            skipped.append({
                "derived_dataset_id": str(dataset.id),
                "reason": "has_downstream_dependencies",
                "dependencies": blockers,
            })
            continue
        item = {
            "derived_dataset_id": str(dataset.id),
            "storage_uri": dataset.storage_uri,
            "logical_path": dataset.logical_path,
            "previous_retention_status": dataset.retention_status,
            "retention_expires_at": dataset.retention_expires_at.isoformat() if dataset.retention_expires_at else None,
        }
        cleaned.append(item)
        if not dry_run:
            dataset.retention_status = "deleted"
            dataset.deleted_at = now
            dataset.updated_at = now

    return {
        "dry_run": dry_run,
        "allowed_retention_statuses": allowed_statuses,
        "candidate_count": len(candidates),
        "cleaned_count": len(cleaned),
        "skipped_count": len(skipped),
        "cleaned": cleaned,
        "skipped": skipped,
    }


def run_raw_bids_build(db, task: AsyncTask) -> dict[str, Any]:
    asset_id = _uuid_or_none((task.payload_json or {}).get("dataset_asset_id") or task.resource_id)
    if asset_id is None:
        raise ValueError("raw_bids_build requires dataset_asset_id")
    asset = db.query(DatasetAsset).filter(DatasetAsset.id == asset_id).first()
    if asset is None:
        raise ValueError(f"Dataset asset not found: {asset_id}")
    files = (
        db.query(DatasetFile)
        .join(Recording, DatasetFile.recording_id == Recording.id)
        .filter(Recording.dataset_asset_id == asset.id, DatasetFile.logical_path.like("raw_bids/%"))
        .all()
    )
    return {
        "dataset_asset_id": str(asset.id),
        "task_scope": "raw_bids_logical_view",
        "raw_bids_file_count": len(files),
        "message": "Raw BIDS logical view is already materialized in dataset_files; no file copy was needed.",
    }


def run_canonical_fif_rebuild(db, task: AsyncTask) -> dict[str, Any]:
    asset_id = _uuid_or_none((task.payload_json or {}).get("dataset_asset_id") or task.resource_id)
    if asset_id is None:
        raise ValueError("canonical_fif_rebuild requires dataset_asset_id")
    asset = db.query(DatasetAsset).filter(DatasetAsset.id == asset_id).first()
    if asset is None:
        raise ValueError(f"Dataset asset not found: {asset_id}")
    canonical_files = (
        db.query(DatasetFile)
        .join(Recording, DatasetFile.recording_id == Recording.id)
        .filter(Recording.dataset_asset_id == asset.id, DatasetFile.file_role == "canonical_fif")
        .all()
    )
    return {
        "dataset_asset_id": str(asset.id),
        "canonical_fif_count": len(canonical_files),
        "message": "Canonical FIF async rebuild is queued through the task framework; existing canonical FIF files were indexed.",
        "rebuild_performed": False,
    }


def run_dataset_import(db, task: AsyncTask) -> dict[str, Any]:
    payload = task.payload_json or {}
    return {
        "study_id": task.study_id,
        "dataset_asset_id": payload.get("dataset_asset_id"),
        "staged_upload_uri": payload.get("staged_upload_uri"),
        "message": "Dataset import task was recorded. Synchronous upload remains the active import path until staged upload workers are enabled.",
        "import_performed": False,
    }


def _find_task(db, task_id: str, celery_task_id: str | None) -> AsyncTask | None:
    return find_async_task_by_celery_id(db, celery_task_id) or db.query(AsyncTask).filter(AsyncTask.id == UUID(str(task_id))).first()


def _cleanup_statuses(value: Any) -> list[str]:
    if isinstance(value, list):
        statuses = [str(item) for item in value if str(item) in {"temporary", "cached"}]
        if statuses:
            return statuses
    return ["temporary", "cached"]


def _uuid_or_none(value: Any) -> UUID | None:
    if value in (None, ""):
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None
