"""
Purpose: Aggregate platform-wide runtime/load/health signals for the admin ops console.
Related: app/routers/admin.py, app/services/study_locks.py, app/tasks/celery_app.py, app/services/dashboard_summary.py.

与「用户工作台」(dashboard_summary) 的根本区别：本模块面向平台管理员/运维，**不做按用户的
可见性过滤**——查的是全平台原始数据（所有 Study 的执行、所有用户、所有审计）。第一期纯只读：
只读取与探测，不做任何干预（强制释放锁 / 取消执行 / 清缓存等留作第二期）。
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, func
from sqlalchemy.orm import Session
from sqlalchemy.sql import text

from app.models import (
    AsyncTask,
    AuditEvent,
    DatasetAsset,
    DatasetPublicizationRequest,
    DatasetVersion,
    DatasetWithdrawalRequest,
    PipelineDefinition,
    PipelineExecution,
    Recording,
    Study,
    StudyLock,
    StudyOutput,
    Subject,
    User,
)
from app.services.study_locks import PIPELINE_EXECUTION_STALE_AFTER_SECONDS

# 出现在「运行中」实时列表里的执行状态（去掉 failed —— 失败单独走「最近失败」聚合，避免历史
# 失败把实时列表淹没）。
LIVE_EXECUTION_STATUSES = ("waiting_user_input", "running", "queued", "pending")
# 队列计数 / 状态分布要覆盖的全部执行状态。
ALL_EXECUTION_STATUSES = (
    "running",
    "queued",
    "pending",
    "waiting_user_input",
    "failed",
    "completed",
    "canceled",
)
DISK_WARNING_PERCENT = 80.0
DISK_CRITICAL_PERCENT = 92.0
FAILURE_WINDOW_HOURS = 24
PLATFORM_EXECUTION_LIMIT = 60
FAILURE_TOP_LIMIT = 12

# celery inspect 探测结果短 TTL 缓存（每进程一份）：总览灯 + 运行面板可能在几秒内各探一次，
# 用 3s 缓存去重，避免对 broker 重复广播。按 light/full 两档分别缓存（总览只要 ping，运行面板才要
# active/reserved）。
_CELERY_PROBE_TTL_SECONDS = 3.0
_celery_probe_cache: dict[str, dict[str, Any]] = {}


# --------------------------------------------------------------------------- #
# 健康探测
# --------------------------------------------------------------------------- #
def probe_db(db: Session) -> dict[str, Any]:
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "down", "error": str(exc)}


def probe_redis(settings) -> dict[str, Any]:
    try:
        import redis  # noqa: PLC0415  (celery[redis] 已带此依赖)

        client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=(settings.REDIS_PASSWORD or None),
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
        client.ping()
        return {"status": "healthy"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "down", "error": str(exc)}


def probe_celery(settings, *, with_tasks: bool = True) -> dict[str, Any]:
    """探测 Celery worker：在线与否、worker 数，可选 active/reserved 任务数。

    每次 `inspect` 是一次「广播 + 等满超时收集回复」，所以多调一次方法就多等一个超时。总览只需要
    「worker 在不在线」→ `with_tasks=False` 只做一次 ping（首屏不再串三次广播被拖到 ~10s）；运行与
    负荷 tab 才 `with_tasks=True` 取 active/reserved。结果按档分别带 3s TTL 缓存。worker 离线 =
    平台正在 inline 降级跑（web 请求线程同步整条 pipeline），是「上传与跑流程抢同一队列」总根因
    最直接的运维读数。
    """
    key = "full" if with_tasks else "light"
    now = time.monotonic()
    cached = _celery_probe_cache.get(key)
    if cached is not None and (now - float(cached.get("checked_at") or 0.0)) < _CELERY_PROBE_TTL_SECONDS:
        return cached["value"]

    result: dict[str, Any] = {
        "online": False,
        "worker_count": 0,
        "active": 0,
        "reserved": 0,
        "workers": [],
        "error": None,
    }
    try:
        from app.tasks.celery_app import celery_app  # noqa: PLC0415

        timeout = float(getattr(settings, "CELERY_WORKER_PING_TIMEOUT_SECONDS", 0.5) or 0.5)
        inspector = celery_app.control.inspect(timeout=timeout)
        ping = inspector.ping() or {}
        if ping:
            result["online"] = True
            result["worker_count"] = len(ping)
            if with_tasks:
                active = inspector.active() or {}
                reserved = inspector.reserved() or {}
                total_active = total_reserved = 0
                workers: list[dict[str, Any]] = []
                for name in ping.keys():
                    a = len(active.get(name, []) or [])
                    r = len(reserved.get(name, []) or [])
                    total_active += a
                    total_reserved += r
                    workers.append({"name": name, "active": a, "reserved": r})
                result["active"] = total_active
                result["reserved"] = total_reserved
                result["workers"] = workers
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)

    _celery_probe_cache[key] = {"checked_at": now, "value": result}
    return result


def read_disk(settings) -> dict[str, Any] | None:
    """只读存储盘用量（shutil，瞬时，不依赖 psutil）。总览的磁盘灯与运行面板共用。"""
    try:
        import shutil  # noqa: PLC0415

        root = settings.ELYS_STORAGE_ROOT
        du = shutil.disk_usage(root)
        return {
            "path": root,
            "total": int(du.total),
            "used": int(du.used),
            "free": int(du.free),
            "percent": round(du.used / du.total * 100, 1) if du.total else None,
        }
    except Exception:  # noqa: BLE001
        return None


def read_resources(settings) -> dict[str, Any]:
    """读取计算服系统负荷：CPU / 内存 / 磁盘。

    后端进程跑在计算服（8C16G 全家桶），故 psutil 读到的就是计算服实时负荷。磁盘走 shutil，
    即便 psutil 未安装也能拿到存储盘余量。"""
    res: dict[str, Any] = {
        "psutil_available": False,
        "cpu_percent": None,
        "cpu_count": None,
        "load_avg": None,
        "mem": None,
        "disk": None,
        "error": None,
    }
    try:
        import psutil  # noqa: PLC0415

        res["psutil_available"] = True
        res["cpu_percent"] = round(psutil.cpu_percent(interval=0.2), 1)
        res["cpu_count"] = psutil.cpu_count()
        vm = psutil.virtual_memory()
        res["mem"] = {
            "total": int(vm.total),
            "used": int(vm.total - vm.available),
            "available": int(vm.available),
            "percent": round(vm.percent, 1),
        }
        try:
            res["load_avg"] = [round(x, 2) for x in psutil.getloadavg()]
        except Exception:  # noqa: BLE001  (Windows 等平台无 loadavg)
            res["load_avg"] = None
    except Exception as exc:  # noqa: BLE001
        res["error"] = str(exc)

    res["disk"] = read_disk(settings)
    return res


def _disk_status(disk: dict[str, Any] | None) -> str:
    if not disk or disk.get("percent") is None:
        return "unknown"
    pct = disk["percent"]
    if pct >= DISK_CRITICAL_PERCENT:
        return "critical"
    if pct >= DISK_WARNING_PERCENT:
        return "warning"
    return "healthy"


# --------------------------------------------------------------------------- #
# 计数与状态分布
# --------------------------------------------------------------------------- #
def _count(db: Session, model, *filters) -> int:
    q = db.query(func.count()).select_from(model)
    if filters:
        q = q.filter(*filters)
    return int(q.scalar() or 0)


def _group_count(db: Session, column) -> dict[str, int]:
    rows = db.query(column, func.count()).group_by(column).all()
    return {str(value): int(count) for value, count in rows}


def build_counts(db: Session) -> dict[str, Any]:
    study_states = _group_count(db, Study.status)
    execution_states = _group_count(db, PipelineExecution.status)
    dataset_states = _group_count(db, DatasetAsset.status)
    version_states = _group_count(db, DatasetVersion.state)
    return {
        "users": {
            "total": _count(db, User),
            "active": _count(db, User, User.is_active.is_(True)),
            "admins": _count(db, User, User.roles.any(code="admin")),
        },
        "studies": {
            "total": _count(db, Study, Study.status != "deleted"),
            "active": study_states.get("active", 0),
            "archived": study_states.get("archived", 0),
        },
        "datasets": {
            "total": _count(db, DatasetAsset),
            "by_status": dataset_states,
        },
        "dataset_versions": {
            "total": _count(db, DatasetVersion),
            "published": version_states.get("published", 0),
            "by_state": version_states,
        },
        "recordings": _count(db, Recording),
        "subjects": _count(db, Subject),
        "study_outputs": {
            "total": _count(db, StudyOutput, StudyOutput.deleted_at.is_(None)),
            "kept": _count(db, StudyOutput, StudyOutput.keep.is_(True), StudyOutput.deleted_at.is_(None)),
        },
        "pipelines": _count(db, PipelineDefinition, PipelineDefinition.status != "deleted"),
        "executions": {
            "total": _count(db, PipelineExecution),
            "by_status": execution_states,
        },
        "pending_reviews": {
            "withdrawals": _count(db, DatasetWithdrawalRequest, DatasetWithdrawalRequest.decision.is_(None)),
            "publicizations": _count(db, DatasetPublicizationRequest, DatasetPublicizationRequest.decision.is_(None)),
        },
        "async_tasks": {
            "queued": _count(db, AsyncTask, AsyncTask.status == "queued"),
            "running": _count(db, AsyncTask, AsyncTask.status == "running"),
        },
    }


def execution_state_distribution(db: Session) -> dict[str, int]:
    rows = (
        db.query(PipelineExecution.status, func.count(PipelineExecution.id))
        .group_by(PipelineExecution.status)
        .all()
    )
    values = {str(status): int(count) for status, count in rows}
    return {status: values.get(status, 0) for status in ALL_EXECUTION_STATUSES}


# --------------------------------------------------------------------------- #
# 执行 / 队列 / 锁 / 失败
# --------------------------------------------------------------------------- #
def _age_seconds(started: datetime | None, now: datetime) -> int | None:
    if started is None:
        return None
    return max(int((now - started).total_seconds()), 0)


def build_platform_executions(db: Session, now: datetime, limit: int = PLATFORM_EXECUTION_LIMIT) -> list[dict[str, Any]]:
    rows = (
        db.query(PipelineExecution, PipelineDefinition.name, Study.name)
        .join(
            PipelineDefinition,
            and_(
                PipelineDefinition.study_id == PipelineExecution.study_id,
                PipelineDefinition.id == PipelineExecution.pipeline_id,
            ),
        )
        .join(Study, Study.id == PipelineExecution.study_id)
        .filter(PipelineExecution.status.in_(LIVE_EXECUTION_STATUSES))
        .order_by(PipelineExecution.started_at.desc().nullslast(), PipelineExecution.execution_seq.desc())
        .limit(limit)
        .all()
    )
    items: list[dict[str, Any]] = []
    for execution, pipeline_name, study_name in rows:
        age = _age_seconds(execution.started_at, now)
        items.append(
            {
                "id": str(execution.id),
                "study_id": execution.study_id,
                "study_name": study_name,
                "pipeline_id": execution.pipeline_id,
                "pipeline_name": pipeline_name,
                "execution_seq": execution.execution_seq,
                "status": execution.status,
                "trigger": execution.trigger,
                "node_count": execution.node_count,
                "started_at": execution.started_at,
                "age_seconds": age,
                "suspected_stuck": bool(
                    execution.status == "running"
                    and age is not None
                    and age > PIPELINE_EXECUTION_STALE_AFTER_SECONDS
                ),
            }
        )
    return items


def build_execution_locks(db: Session, now: datetime) -> list[dict[str, Any]]:
    """列出所有未释放的 pipeline execution 锁（只读）。stale 判定复刻 force_release 的口径，
    但这里**只展示、不释放**——强制释放是第二期的干预动作。"""
    locks = (
        db.query(StudyLock, Study.name)
        .outerjoin(Study, Study.id == StudyLock.study_id)
        .filter(
            StudyLock.lock_type == "execution",
            StudyLock.resource_kind == "pipeline",
            StudyLock.released_at.is_(None),
        )
        .order_by(StudyLock.locked_at.asc())
        .all()
    )
    items: list[dict[str, Any]] = []
    for lock, study_name in locks:
        age = _age_seconds(lock.locked_at, now)
        expired = bool(lock.expires_at and lock.expires_at <= now)
        items.append(
            {
                "id": str(lock.id),
                "study_id": lock.study_id,
                "study_name": study_name,
                "resource_id": lock.resource_id,
                "locked_at": lock.locked_at,
                "expires_at": lock.expires_at,
                "age_seconds": age,
                "expired": expired,
            }
        )
    return items


def _first_error_message(error_json: Any) -> str | None:
    if isinstance(error_json, dict):
        errors = error_json.get("errors")
        if isinstance(errors, list) and errors:
            first = errors[0]
            if isinstance(first, dict):
                return first.get("message") or first.get("code")
            return str(first)
        if error_json.get("message"):
            return str(error_json["message"])
    return None


def build_recent_failures(db: Session, now: datetime, limit: int = FAILURE_TOP_LIMIT) -> list[dict[str, Any]]:
    window_start = now - timedelta(hours=FAILURE_WINDOW_HOURS)
    rows = (
        db.query(PipelineExecution, PipelineDefinition.name, Study.name)
        .join(
            PipelineDefinition,
            and_(
                PipelineDefinition.study_id == PipelineExecution.study_id,
                PipelineDefinition.id == PipelineExecution.pipeline_id,
            ),
        )
        .join(Study, Study.id == PipelineExecution.study_id)
        .filter(
            PipelineExecution.status == "failed",
            PipelineExecution.finished_at >= window_start,
        )
        .order_by(PipelineExecution.finished_at.desc().nullslast())
        .limit(limit)
        .all()
    )
    items: list[dict[str, Any]] = []
    for execution, pipeline_name, study_name in rows:
        items.append(
            {
                "id": str(execution.id),
                "study_id": execution.study_id,
                "study_name": study_name,
                "pipeline_id": execution.pipeline_id,
                "pipeline_name": pipeline_name,
                "execution_seq": execution.execution_seq,
                "finished_at": execution.finished_at,
                "error_message": _first_error_message(execution.error_json),
            }
        )
    return items


# --------------------------------------------------------------------------- #
# 顶层构建器
# --------------------------------------------------------------------------- #
def build_admin_overview(db: Session, settings) -> dict[str, Any]:
    now = datetime.utcnow()
    counts = build_counts(db)
    states = execution_state_distribution(db)

    # 总览只要「worker 在不在线」→ ping-only（不取 active/reserved，省两次广播超时）；磁盘只读
    # shutil（瞬时，不跑 psutil）。CPU/内存等重采样留给「运行与负荷」tab。
    db_health = probe_db(db)
    redis_health = probe_redis(settings)
    celery = probe_celery(settings, with_tasks=False)
    disk = read_disk(settings)
    disk_state = _disk_status(disk)

    stuck_count = _count(
        db,
        PipelineExecution,
        PipelineExecution.status == "running",
        PipelineExecution.started_at < now - timedelta(seconds=PIPELINE_EXECUTION_STALE_AFTER_SECONDS),
    )
    failed_recent = _count(
        db,
        PipelineExecution,
        PipelineExecution.status == "failed",
        PipelineExecution.finished_at >= now - timedelta(hours=FAILURE_WINDOW_HOURS),
    )
    waiting = states.get("waiting_user_input", 0)

    health = {
        "api": {"status": "healthy"},
        "db": db_health,
        "redis": redis_health,
        "worker": {
            "status": "healthy" if celery["online"] else "degraded",
            "online": celery["online"],
            "worker_count": celery["worker_count"],
            "note": None if celery["online"] else "worker 离线，平台正在 inline 降级执行",
        },
        "disk": {
            "status": disk_state,
            "percent": disk.get("percent") if disk else None,
            "free": disk.get("free") if disk else None,
            "total": disk.get("total") if disk else None,
        },
    }

    attention: list[dict[str, Any]] = []
    if failed_recent:
        attention.append({"kind": "failed", "severity": "danger", "count": failed_recent, "label": f"{failed_recent} 条执行近 24h 失败"})
    if stuck_count:
        attention.append({"kind": "stuck", "severity": "danger", "count": stuck_count, "label": f"{stuck_count} 条执行疑似卡死（running 超 {PIPELINE_EXECUTION_STALE_AFTER_SECONDS // 60} 分钟）"})
    if not celery["online"]:
        attention.append({"kind": "worker_offline", "severity": "warn", "count": 0, "label": "计算 worker 离线，正在 inline 降级执行"})
    if disk_state in ("warning", "critical"):
        attention.append({"kind": "disk", "severity": "danger" if disk_state == "critical" else "warn", "count": 0, "label": f"磁盘占用 {disk.get('percent')}%"})
    if waiting:
        attention.append({"kind": "waiting", "severity": "warn", "count": waiting, "label": f"{waiting} 条执行等待人工确认"})

    return {
        "generated_at": now,
        "counts": counts,
        "execution_states": states,
        "health": health,
        "attention": attention,
        "resources_summary": {
            "cpu_percent": None,
            "mem_percent": None,
            "disk_percent": disk.get("percent") if disk else None,
        },
    }


def build_admin_runtime(db: Session, settings) -> dict[str, Any]:
    now = datetime.utcnow()
    states = execution_state_distribution(db)
    celery = probe_celery(settings)
    resources = read_resources(settings)
    executions = build_platform_executions(db, now)
    locks = build_execution_locks(db, now)
    failures = build_recent_failures(db, now)
    stuck = [item for item in executions if item["suspected_stuck"]]

    queue = {
        "running": states.get("running", 0),
        "queued": states.get("queued", 0) + states.get("pending", 0),
        "waiting_user_input": states.get("waiting_user_input", 0),
        "failed_recent": _count(
            db,
            PipelineExecution,
            PipelineExecution.status == "failed",
            PipelineExecution.finished_at >= now - timedelta(hours=FAILURE_WINDOW_HOURS),
        ),
        "async_queued": _count(db, AsyncTask, AsyncTask.status == "queued"),
        "async_running": _count(db, AsyncTask, AsyncTask.status == "running"),
    }

    return {
        "generated_at": now,
        "queue": queue,
        "workers": celery,
        "resources": resources,
        "executions": executions,
        "stuck_executions": stuck,
        "locks": locks,
        "recent_failures": failures,
    }


# --------------------------------------------------------------------------- #
# 审计事件查询
# --------------------------------------------------------------------------- #
def query_audit_events(
    db: Session,
    *,
    action: str | None = None,
    actor_id: str | None = None,
    resource_kind: str | None = None,
    study_id: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    q = db.query(AuditEvent)
    if action:
        q = q.filter(AuditEvent.action == action)
    if actor_id:
        q = q.filter(AuditEvent.actor_id == actor_id)
    if resource_kind:
        q = q.filter(AuditEvent.resource_kind == resource_kind)
    if study_id:
        q = q.filter(AuditEvent.study_id == study_id)
    if since:
        q = q.filter(AuditEvent.occurred_at >= since)
    if until:
        q = q.filter(AuditEvent.occurred_at <= until)

    total = int(q.count())
    rows = q.order_by(AuditEvent.occurred_at.desc()).offset(offset).limit(limit).all()

    actor_ids = {row.actor_id for row in rows if row.actor_id}
    actors: dict[Any, str] = {}
    if actor_ids:
        for user in db.query(User).filter(User.id.in_(actor_ids)).all():
            actors[user.id] = user.full_name or user.username

    events = [
        {
            "id": str(row.id),
            "action": row.action,
            "event_scope": row.event_scope,
            "actor_id": str(row.actor_id) if row.actor_id else None,
            "actor_name": actors.get(row.actor_id),
            "resource_kind": row.resource_kind,
            "resource_id": row.resource_id,
            "resource_label": row.resource_label,
            "study_id": row.study_id,
            "occurred_at": row.occurred_at,
            "metadata": row.metadata_json or {},
            "has_snapshot": bool(row.snapshot),
        }
        for row in rows
    ]
    return {"events": events, "total": total, "limit": limit, "offset": offset}


def audit_facets(db: Session) -> dict[str, Any]:
    actions = [row[0] for row in db.query(AuditEvent.action).distinct().order_by(AuditEvent.action).all() if row[0]]
    kinds = [row[0] for row in db.query(AuditEvent.resource_kind).distinct().all() if row[0]]
    return {"actions": actions, "resource_kinds": sorted(kinds)}
