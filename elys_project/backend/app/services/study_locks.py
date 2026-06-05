"""
Purpose: Manage short-lived study locks for edit/execution coordination.
Related: app/models/study.py, app/routers/pipelines.py, app/tasks/pipeline_tasks.py, docs_v2/7-30.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import StudyLock


# Study lock TTL：10 分钟。
# - pipeline execution 通常几秒到几分钟跑完，10 分钟足够
# - worker 异常退出（SIGKILL / OOM）导致锁泄漏时，10 分钟内自然过期
# - 之前 24 小时太长，worker crash 后用户要等大半天才能再跑
DEFAULT_STUDY_LOCK_TTL_SECONDS = 10 * 60

# 配合 TTL 使用：pipeline_execution.started_at 超过这个时间还是 'running' → 视为 stale
PIPELINE_EXECUTION_STALE_AFTER_SECONDS = 10 * 60


class StudyLockConflictError(Exception):
    def __init__(self, lock: StudyLock | None = None):
        self.lock = lock
        super().__init__("Study resource is locked")


def release_expired_study_locks(
    db: Session,
    *,
    study_id: str | None = None,
    resource_kind: str | None = None,
    resource_id: str | int | UUID | None = None,
    lock_type: str | None = None,
    now: datetime | None = None,
) -> int:
    now = now or datetime.utcnow()
    query = db.query(StudyLock).filter(StudyLock.released_at.is_(None), StudyLock.expires_at <= now)
    if study_id is not None:
        query = query.filter(StudyLock.study_id == study_id)
    if resource_kind is not None:
        query = query.filter(StudyLock.resource_kind == resource_kind)
    if resource_id is not None:
        query = query.filter(StudyLock.resource_id == str(resource_id))
    if lock_type is not None:
        query = query.filter(StudyLock.lock_type == lock_type)

    count = 0
    for lock in query.all():
        lock.released_at = now
        lock.metadata_json = {
            **(lock.metadata_json or {}),
            "release_reason": "expired",
        }
        count += 1
    if count:
        db.flush()
    return count


def find_active_study_lock(
    db: Session,
    *,
    study_id: str,
    resource_kind: str,
    resource_id: str | int | UUID,
    lock_type: str,
    now: datetime | None = None,
) -> StudyLock | None:
    now = now or datetime.utcnow()
    release_expired_study_locks(
        db,
        study_id=study_id,
        resource_kind=resource_kind,
        resource_id=resource_id,
        lock_type=lock_type,
        now=now,
    )
    return (
        db.query(StudyLock)
        .filter(
            StudyLock.study_id == study_id,
            StudyLock.resource_kind == resource_kind,
            StudyLock.resource_id == str(resource_id),
            StudyLock.lock_type == lock_type,
            StudyLock.released_at.is_(None),
            StudyLock.expires_at > now,
        )
        .order_by(StudyLock.locked_at.asc())
        .first()
    )


def acquire_study_lock(
    db: Session,
    *,
    study_id: str,
    resource_kind: str,
    resource_id: str | int | UUID,
    lock_type: str,
    locked_by: UUID | str | None,
    ttl_seconds: int = DEFAULT_STUDY_LOCK_TTL_SECONDS,
    metadata: dict[str, Any] | None = None,
) -> StudyLock:
    now = datetime.utcnow()
    existing = find_active_study_lock(
        db,
        study_id=study_id,
        resource_kind=resource_kind,
        resource_id=resource_id,
        lock_type=lock_type,
        now=now,
    )
    if existing is not None:
        raise StudyLockConflictError(existing)

    lock = StudyLock(
        study_id=study_id,
        resource_kind=resource_kind,
        resource_id=str(resource_id),
        lock_type=lock_type,
        locked_by=locked_by,
        locked_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
        metadata_json=metadata or {},
    )
    db.add(lock)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        # 只有"同资源已存在未释放的活跃锁"（撞唯一索引 uq_study_locks_active_resource）才算真正的锁冲突。
        # 其它 IntegrityError（外键 / CHECK / 非空约束等）是真实数据问题，照实抛出——别再统一伪装成
        # "锁冲突"。否则像 lock_type CHECK 失败这类错误会被上层当成锁冲突、前端显示"正在被运行"，
        # 把真因彻底盖住、极难定位（2026-06-05 踩过这个坑）。
        conflicting = find_active_study_lock(
            db,
            study_id=study_id,
            resource_kind=resource_kind,
            resource_id=resource_id,
            lock_type=lock_type,
        )
        if conflicting is not None:
            raise StudyLockConflictError(conflicting) from exc
        raise
    return lock


def release_study_lock(
    db: Session,
    lock: StudyLock,
    *,
    released_by: UUID | str | None = None,
    reason: str = "released",
) -> StudyLock:
    if lock.released_at is not None:
        return lock
    lock.released_at = datetime.utcnow()
    lock.released_by = released_by
    lock.metadata_json = {
        **(lock.metadata_json or {}),
        "release_reason": reason,
    }
    db.flush()
    return lock


def refresh_study_lock(
    db: Session,
    lock: StudyLock,
    *,
    ttl_seconds: int = DEFAULT_STUDY_LOCK_TTL_SECONDS,
    refreshed_by: UUID | str | None = None,
    reason: str = "refreshed",
) -> StudyLock:
    now = datetime.utcnow()
    lock.expires_at = now + timedelta(seconds=ttl_seconds)
    lock.metadata_json = {
        **(lock.metadata_json or {}),
        "refresh_reason": reason,
        "refreshed_by": str(refreshed_by) if refreshed_by is not None else None,
        "refreshed_at": now.isoformat(),
    }
    db.flush()
    return lock


def release_study_lock_by_id(
    db: Session,
    lock_id: UUID | str | None,
    *,
    released_by: UUID | str | None = None,
    reason: str = "released",
) -> StudyLock | None:
    if lock_id is None:
        return None
    lock = db.query(StudyLock).filter(StudyLock.id == lock_id).first()
    if lock is None:
        return None
    return release_study_lock(db, lock, released_by=released_by, reason=reason)


def release_study_locks_for_resource(
    db: Session,
    *,
    study_id: str,
    resource_kind: str,
    resource_id: str | int | UUID,
    lock_type: str,
    released_by: UUID | str | None = None,
    reason: str = "released",
) -> list[StudyLock]:
    locks = (
        db.query(StudyLock)
        .filter(
            StudyLock.study_id == study_id,
            StudyLock.resource_kind == resource_kind,
            StudyLock.resource_id == str(resource_id),
            StudyLock.lock_type == lock_type,
            StudyLock.released_at.is_(None),
        )
        .all()
    )
    for lock in locks:
        release_study_lock(db, lock, released_by=released_by, reason=reason)
    return locks


def force_release_stale_pipeline_execution_locks(
    db: Session,
    *,
    study_id: str,
    pipeline_id: str | int | UUID,
    now: datetime | None = None,
) -> int:
    """强制释放 pipeline 的 stale execution 锁。处理 worker 异常退出（SIGKILL/OOM/Python 异常未捕获）
    导致锁泄漏的情况。

    判定 stale 的条件（任一即可）：
    - 锁关联的 PipelineExecution 已经结束（completed / failed / canceled）但锁没释放
    - 锁关联的 PipelineExecution 仍是 'running' 但 started_at 超过 PIPELINE_EXECUTION_STALE_AFTER_SECONDS

    后者情况还会顺手把 stuck execution 也强制标 'failed'。

    返回释放的锁数量。
    """
    from app.models import PipelineExecution  # 延迟导入避免循环

    now = now or datetime.utcnow()
    stale_threshold = now - timedelta(seconds=PIPELINE_EXECUTION_STALE_AFTER_SECONDS)

    locks = (
        db.query(StudyLock)
        .filter(
            StudyLock.study_id == study_id,
            StudyLock.resource_kind == "pipeline",
            StudyLock.resource_id == str(pipeline_id),
            StudyLock.lock_type == "execution",
            StudyLock.released_at.is_(None),
        )
        .all()
    )

    released = 0
    for lock in locks:
        # 找该 pipeline 最近的 running execution
        execution = (
            db.query(PipelineExecution)
            .filter(
                PipelineExecution.study_id == study_id,
                PipelineExecution.pipeline_id == pipeline_id,
            )
            .order_by(PipelineExecution.started_at.desc().nullslast(), PipelineExecution.id.desc())
            .first()
        )

        should_release = False
        release_reason = "stale_lock"

        if execution is None:
            should_release = True
            release_reason = "orphan_lock_no_execution"
        elif execution.status in ("completed", "failed", "canceled"):
            should_release = True
            release_reason = f"execution_already_{execution.status}"
        else:
            # status 还是 'running' / 'queued'，看 started_at 是否超时
            execution_started = execution.started_at or execution.created_at if hasattr(execution, "created_at") else execution.started_at
            if execution_started is None or execution_started < stale_threshold:
                # stuck execution，强制标 failed
                execution.status = "failed"
                execution.finished_at = now
                execution.error_json = {
                    "errors": [
                        {
                            "code": "PIPELINE_EXECUTION_STALE_TIMEOUT",
                            "message": f"Execution 超过 {PIPELINE_EXECUTION_STALE_AFTER_SECONDS // 60} 分钟未完成，"
                                       f"判定为 worker 异常退出。已强制标记为 failed。",
                            "severity": "error",
                        }
                    ]
                }
                should_release = True
                release_reason = "execution_timeout"

        if should_release:
            release_study_lock(db, lock, reason=release_reason)
            released += 1

    if released:
        db.flush()
    return released
