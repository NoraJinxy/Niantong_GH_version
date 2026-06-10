"""
Purpose: Run asynchronous Dataset and Artifact file-management tasks.
Related: app/routers/datasets.py, app/routers/pipelines.py, app/services/execution_dependencies.py.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from celery.utils.log import get_task_logger

from app.database import SessionLocal
from app.models import AsyncTask, DatasetAsset, DatasetFile, StudyOutput, Recording
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

        if task.task_type == "study_output_cleanup":
            result = run_study_output_cleanup(db, task)
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


def run_study_output_cleanup(db, task: AsyncTask) -> dict[str, Any]:
    """Cleanup study_outputs whose retention is temporary/cached and (optionally) expired.

    被下游 Execution/节点输入引用的派生数据集会被跳过；其它候选的 retention_status 改为
    "deleted"，物理文件保留以便恢复（实际清盘由后续 garbage collector 完成）。
    """
    payload = task.payload_json or {}
    allowed_statuses = _cleanup_statuses(payload.get("retention_statuses"))
    dry_run = bool(payload.get("dry_run", False))
    limit = int(payload.get("limit") or 500)
    study_id = task.study_id
    if not study_id:
        raise ValueError("study_output_cleanup requires study_id")

    now = datetime.utcnow()
    query = db.query(StudyOutput).filter(
        StudyOutput.study_id == study_id,
        StudyOutput.retention_status.in_(allowed_statuses),
    )
    # 优先回收已过期的临时项；过期为空（pinned/current）的不进
    query = query.order_by(
        StudyOutput.retention_expires_at.asc().nullslast(),
        StudyOutput.created_at.asc(),
        StudyOutput.id.asc(),
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
                    "study_output_id": str(dataset.id),
                    "reason": "not_yet_expired",
                    "retention_expires_at": dataset.retention_expires_at.isoformat(),
                }
            )
            continue
        blockers = artifact_dependency_blockers(db, artifact=dataset, limit=5)
        if blockers:
            skipped.append({
                "study_output_id": str(dataset.id),
                "reason": "has_downstream_dependencies",
                "dependencies": blockers,
            })
            continue
        item = {
            "study_output_id": str(dataset.id),
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


def _read_import_manifest(job_dir: Path) -> dict[str, Any]:
    """读回请求阶段写的 archiving manifest，让 worker 续写 done/failed 时保留 jobId/entities 等字段。"""
    manifest_path = job_dir / "manifest.json"
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    return {"status": "archiving", "jobDir": str(job_dir)}


def run_dataset_import(db, task: AsyncTask) -> dict[str, Any]:
    """真正干活的异步导入 worker：读 job_dir 里**已暂存**的文件，调用与同步端点同源的
    materialize_recording_import 做 校验→转 canonical FIF→写库，全程 record_task_event 上报进度。

    上下文从 task.payload_json 重建（见 routers/datasets.py import_recording_async 写入的字段）。
    """
    from sqlalchemy.orm import joinedload

    from app.models import DatasetVersion, Study, Subject, User
    # 惰性 import：转换核心与辅助函数都在 routers.datasets 里，顶层 import 会把 router 层拉进
    # worker 进程并可能造成循环 import；在函数体内运行时 import 可避开。
    from app.routers.datasets import (
        ensure_dataset_asset_active_mounted,
        ensure_dataset_asset_uploadable,
        get_active_study_dataset_mount_for_asset,
        materialize_recording_import,
        recording_to_response,
    )

    payload = task.payload_json or {}
    required = (
        "study_id", "dataset_asset_id", "dataset_version_id", "job_dir",
        "archived", "upload_kind", "upload_seq", "job_id", "bids_subject_id", "task_label",
    )
    missing = [key for key in required if payload.get(key) in (None, "")]
    if missing:
        raise ValueError(f"dataset_import 任务 payload 缺字段: {missing}")

    study = db.query(Study).filter(Study.id == payload["study_id"]).first()
    if study is None:
        raise ValueError(f"Study 不存在: {payload['study_id']}")

    importer = None
    if payload.get("importer_user_id"):
        importer = db.query(User).filter(User.id == payload["importer_user_id"]).first()
    if importer is None and task.created_by:
        importer = db.query(User).filter(User.id == task.created_by).first()
    if importer is None:
        raise ValueError("dataset_import 找不到发起用户")

    target_asset = db.query(DatasetAsset).filter(DatasetAsset.id == payload["dataset_asset_id"]).first()
    target_version = db.query(DatasetVersion).filter(DatasetVersion.id == payload["dataset_version_id"]).first()
    if target_asset is None or target_version is None:
        raise ValueError("dataset_import 的 dataset asset / version 不存在")
    # 在 worker 真正写库前重新校验——请求受理到此刻有时间窗，期间 asset 可能被
    # 归档/隔离/删除、mount 可能被停用。同步导入在请求内由 resolve_upload_dataset_asset
    # 做掉这两项校验，异步路径必须补上，否则会把数据写进已不该接受上传的 asset。
    ensure_dataset_asset_uploadable(target_asset, importer)
    ensure_dataset_asset_active_mounted(db, study=study, dataset_asset_id=target_asset.id)
    target_mount = get_active_study_dataset_mount_for_asset(db, study=study, dataset_asset=target_asset)

    duplicate = None
    if payload.get("duplicate_recording_id"):
        duplicate = (
            db.query(Recording)
            .options(joinedload(Recording.current_version))
            .filter(Recording.id == payload["duplicate_recording_id"])
            .first()
        )
    subject_record = None
    if payload.get("subject_record_id"):
        subject_record = db.query(Subject).filter(Subject.id == payload["subject_record_id"]).first()

    archived = {ext: Path(p) for ext, p in (payload.get("archived") or {}).items()}
    job_dir = Path(payload["job_dir"])
    temp_root = Path(study.data_root) / "upload_staging"
    temp_root.mkdir(parents=True, exist_ok=True)
    manifest = _read_import_manifest(job_dir)

    def emit(progress: int, message: str) -> None:
        record_task_event(db, task, "progress", status="running", progress=progress, message=message)
        db.commit()

    emit(10, "文件已暂存，开始导入")
    dataset = materialize_recording_import(
        db,
        study=study,
        current_user=importer,
        target_asset=target_asset,
        target_version=target_version,
        target_mount=target_mount,
        duplicate=duplicate,
        subject_record=subject_record,
        bids_subject_id=payload["bids_subject_id"],
        session_label=payload.get("session_label"),
        task_label=payload["task_label"],
        run_label=payload.get("run_label"),
        upload_kind=payload["upload_kind"],
        upload_seq=payload["upload_seq"],
        job_id=payload["job_id"],
        job_dir=job_dir,
        archived=archived,
        manifest=manifest,
        temp_root=temp_root,
        on_progress=emit,
    )
    return {
        "recording_id": str(dataset.id),
        "recording": recording_to_response(dataset).model_dump(mode="json"),
        "upload_seq": payload["upload_seq"],
        "mode": "replacement" if duplicate else "new",
        "fif_path": dataset.fif_path,
        "import_performed": True,
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
