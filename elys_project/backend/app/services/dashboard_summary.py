"""
Purpose: Build the compact Dashboard summary with permission-aware aggregation.
Related: app/routers/dashboard.py, app/schemas/dashboard.py, app/models/study.py.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models import (
    AuditEvent,
    DatasetAsset,
    PipelineDefinition,
    PipelineExecution,
    Study,
    StudyMember,
    StudyDatasetMount,
    User,
)
from app.schemas.dashboard import (
    DashboardActiveExecution,
    DashboardActivityItem,
    DashboardCounts,
    DashboardDatasetStates,
    DashboardPipelineStates,
    DashboardRecentStudy,
    DashboardExecutionStates,
    DashboardStates,
    DashboardStudyMetrics,
    DashboardStudyStates,
    DashboardSummaryResponse,
)
from app.services.dataset_assets import list_visible_dataset_assets


DASHBOARD_RECENT_STUDY_LIMIT = 5
DASHBOARD_ACTIVE_EXECUTION_LIMIT = 12
DASHBOARD_ACTIVITY_LIMIT = 8
DASHBOARD_ACTIVITY_QUERY_LIMIT = 40
DASHBOARD_EXECUTION_STATUSES = ("waiting_user_input", "failed", "running", "queued", "pending")
DASHBOARD_ATTENTION_EXECUTION_STATUSES = ("waiting_user_input", "failed")
DASHBOARD_RUNNING_EXECUTION_STATUSES = ("running", "queued", "pending")
DASHBOARD_DATASET_ERROR_STATUSES = {"error", "failed", "quarantined"}
DASHBOARD_EXECUTION_STATUS_PRIORITY = {
    "waiting_user_input": 0,
    "failed": 1,
    "running": 2,
    "queued": 3,
    "pending": 4,
}


def build_dashboard_summary(db: Session, *, current_user: User) -> DashboardSummaryResponse:
    studies = list_visible_dashboard_studies(db, current_user)
    study_ids = [study.id for study in studies]
    dataset_assets = list_dashboard_dataset_assets(db, current_user)

    pipeline_counts = grouped_count(
        db,
        PipelineDefinition.study_id,
        PipelineDefinition.id,
        study_ids,
        PipelineDefinition.status != "deleted",
    )
    execution_counts = grouped_count(db, PipelineExecution.study_id, PipelineExecution.id, study_ids)
    attention_execution_counts = grouped_count(
        db,
        PipelineExecution.study_id,
        PipelineExecution.id,
        study_ids,
        PipelineExecution.status.in_(DASHBOARD_ATTENTION_EXECUTION_STATUSES),
    )
    running_execution_counts = grouped_count(
        db,
        PipelineExecution.study_id,
        PipelineExecution.id,
        study_ids,
        PipelineExecution.status.in_(DASHBOARD_RUNNING_EXECUTION_STATUSES),
    )
    mount_counts = grouped_count(
        db,
        StudyDatasetMount.study_id,
        StudyDatasetMount.id,
        study_ids,
        StudyDatasetMount.is_active.is_(True),
    )

    recent_studies = sorted(
        studies,
        key=lambda study: datetime_sort_value(study.updated_at or study.created_at),
        reverse=True,
    )[:DASHBOARD_RECENT_STUDY_LIMIT]
    recent_studies = [
        DashboardRecentStudy(
            id=study.id,
            name=study.name,
            code=study.code,
            description=study.description,
            status=study.status,
            created_at=study.created_at,
            updated_at=study.updated_at,
            metrics=DashboardStudyMetrics(
                dataset_count=mount_counts.get(study.id, 0),
                pipeline_count=pipeline_counts.get(study.id, 0),
                execution_count=execution_counts.get(study.id, 0),
                running_execution_count=running_execution_counts.get(study.id, 0),
                attention_execution_count=attention_execution_counts.get(study.id, 0),
            ),
        )
        for study in recent_studies
    ]

    active_executions = build_active_executions(db, study_ids)
    recent_activity = build_recent_activity(
        db,
        study_ids=study_ids,
        studies=studies,
        dataset_assets=dataset_assets,
    )

    return DashboardSummaryResponse(
        counts=DashboardCounts(
            datasets=len(dataset_assets),
            studies=len(studies),
            pipelines=count_pipelines(db, study_ids),
            executions=count_executions(db, study_ids),
        ),
        states=DashboardStates(
            datasets=dataset_states(dataset_assets),
            studies=study_states(studies),
            pipelines=pipeline_states(db, study_ids),
            executions=execution_states(db, study_ids),
        ),
        recent_studies=recent_studies,
        active_executions=active_executions,
        recent_activity=recent_activity,
    )


def list_visible_dashboard_studies(db: Session, user: User) -> list[Study]:
    query = db.query(Study).filter(Study.status.in_(("active", "archived")))
    if not user.has_role("admin"):
        query = (
            query.outerjoin(StudyMember, StudyMember.study_id == Study.id)
            .filter(or_(Study.owner_id == user.id, StudyMember.user_id == user.id))
            .distinct()
        )
    return query.order_by(Study.updated_at.desc(), Study.created_at.desc()).all()


def list_dashboard_dataset_assets(db: Session, user: User) -> list[DatasetAsset]:
    if not (user.has_role("admin") or user.has_permission("data:read")):
        return []
    return list_visible_dataset_assets(db, user=user)


def grouped_count(db: Session, study_column, count_column, study_ids: list[str], *filters) -> dict[str, int]:
    if not study_ids:
        return {}
    rows = (
        db.query(study_column, func.count(count_column))
        .filter(study_column.in_(study_ids), *filters)
        .group_by(study_column)
        .all()
    )
    return {str(study_id): int(count) for study_id, count in rows}


def count_pipelines(db: Session, study_ids: list[str]) -> int:
    if not study_ids:
        return 0
    return int(
        db.query(PipelineDefinition)
        .filter(PipelineDefinition.study_id.in_(study_ids), PipelineDefinition.status != "deleted")
        .count()
    )


def count_executions(db: Session, study_ids: list[str]) -> int:
    if not study_ids:
        return 0
    return int(db.query(PipelineExecution).filter(PipelineExecution.study_id.in_(study_ids)).count())


def dataset_states(dataset_assets: Iterable[DatasetAsset]) -> DashboardDatasetStates:
    # status 合并后存活态统一 working（不再有 active），active 永远 0。
    working = error = 0
    for asset in dataset_assets:
        if asset.status == "working":
            working += 1
        elif asset.status in DASHBOARD_DATASET_ERROR_STATUSES:
            error += 1
    return DashboardDatasetStates(working=working, active=0, error=error)


def study_states(studies: Iterable[Study]) -> DashboardStudyStates:
    active = archived = 0
    for study in studies:
        if study.status == "active":
            active += 1
        elif study.status == "archived":
            archived += 1
    return DashboardStudyStates(active=active, archived=archived)


def pipeline_states(db: Session, study_ids: list[str]) -> DashboardPipelineStates:
    if not study_ids:
        return DashboardPipelineStates(active=0, draft=0)
    rows = (
        db.query(PipelineDefinition.status, func.count(PipelineDefinition.id))
        .filter(PipelineDefinition.study_id.in_(study_ids), PipelineDefinition.status != "deleted")
        .group_by(PipelineDefinition.status)
        .all()
    )
    values = {str(status): int(count) for status, count in rows}
    return DashboardPipelineStates(active=values.get("active", 0), draft=values.get("draft", 0))


def execution_states(db: Session, study_ids: list[str]) -> DashboardExecutionStates:
    if not study_ids:
        return DashboardExecutionStates(waiting_user_input=0, failed=0, running=0, queued=0, pending=0)
    rows = (
        db.query(PipelineExecution.status, func.count(PipelineExecution.id))
        .filter(PipelineExecution.study_id.in_(study_ids), PipelineExecution.status.in_(DASHBOARD_EXECUTION_STATUSES))
        .group_by(PipelineExecution.status)
        .all()
    )
    values = {str(status): int(count) for status, count in rows}
    return DashboardExecutionStates(
        waiting_user_input=values.get("waiting_user_input", 0),
        failed=values.get("failed", 0),
        running=values.get("running", 0),
        queued=values.get("queued", 0),
        pending=values.get("pending", 0),
    )


def build_active_executions(db: Session, study_ids: list[str]) -> list[DashboardActiveExecution]:
    if not study_ids:
        return []
    rows = (
        db.query(PipelineExecution, PipelineDefinition.name)
        .join(
            PipelineDefinition,
            and_(
                PipelineDefinition.study_id == PipelineExecution.study_id,
                PipelineDefinition.id == PipelineExecution.pipeline_id,
            ),
        )
        .filter(
            PipelineExecution.study_id.in_(study_ids),
            PipelineExecution.status.in_(DASHBOARD_EXECUTION_STATUSES),
            PipelineDefinition.status != "deleted",
        )
        .order_by(PipelineExecution.started_at.desc(), PipelineExecution.execution_seq.desc())
        .limit(100)
        .all()
    )
    items = [
        DashboardActiveExecution(
            id=str(execution.id),
            study_id=execution.study_id,
            pipeline_id=execution.pipeline_id,
            pipeline_name=pipeline_name,
            execution_seq=execution.execution_seq,
            status=execution.status,
            stage_label=execution_stage_label(execution.status),
            started_at=execution.started_at,
            finished_at=execution.finished_at,
        )
        for execution, pipeline_name in rows
    ]
    return sorted(items, key=dashboard_execution_sort_key)[:DASHBOARD_ACTIVE_EXECUTION_LIMIT]


def dashboard_execution_sort_key(execution) -> tuple[int, float]:
    return (execution_status_priority(execution.status), -datetime_sort_value(execution.started_at or execution.finished_at))


def execution_status_priority(status: str) -> int:
    return DASHBOARD_EXECUTION_STATUS_PRIORITY.get(status, 99)


def execution_stage_label(status: str) -> str:
    labels = {
        "waiting_user_input": "等待人工确认",
        "failed": "运行失败，请查看错误",
        "running": "正在处理",
        "queued": "排队中",
        "pending": "等待调度",
    }
    return labels.get(status, "等待处理")


BOOTSTRAP_ACTIONS = {
    "study.created",
    "dataset_asset.created",
    "study.dataset_mount.created",
    "dataset.bootstrap.completed",
}
BOOTSTRAP_WINDOW_SECONDS = 5

EXECUTION_LIFECYCLE_ACTIONS = {
    "pipeline.execution.queued",
    "pipeline.execution.running",
    "pipeline.execution.waiting_user_input",
    "pipeline.execution.failed",
    "pipeline.execution.completed",
    "pipeline.execution.canceled",
    "pipeline.execution.retry_queued",
    "pipeline.execution.dispatch_failed",
    "pipeline.execution.retry_dispatch_failed",
    "pipeline.execution.task_exception",
}

ERROR_ACTIONS = {
    "pipeline.execution.failed",
    "pipeline.execution.dispatch_failed",
    "pipeline.execution.retry_dispatch_failed",
    "pipeline.execution.task_exception",
}
SUCCESS_ACTIONS = {
    "pipeline.execution.completed",
    "dataset.bootstrap.completed",
    "dataset_asset.created",
    "dataset.uploaded",
    "study.created",
    "pipeline.created",
}
WARN_ACTIONS = {
    "pipeline.execution.waiting_user_input",
    "pipeline.execution.canceled",
    "pipeline.execution.retry_queued",
}


def severity_for_action(action: str) -> str:
    if action in ERROR_ACTIONS:
        return "error"
    if action in SUCCESS_ACTIONS:
        return "success"
    if action in WARN_ACTIONS:
        return "warn"
    return "info"


def build_recent_activity(
    db: Session,
    *,
    study_ids: list[str],
    studies: Iterable[Study],
    dataset_assets: list[DatasetAsset],
) -> list[DashboardActivityItem]:
    asset_id_strings = [str(asset.id) for asset in dataset_assets]
    filters = []
    if study_ids:
        filters.append(AuditEvent.study_id.in_(study_ids))
    if asset_id_strings:
        filters.append(
            and_(
                AuditEvent.resource_kind == "dataset_asset",
                AuditEvent.resource_id.in_(asset_id_strings),
            )
        )

    if not filters:
        return []

    events = (
        db.query(AuditEvent)
        .filter(or_(*filters))
        .order_by(AuditEvent.occurred_at.desc())
        .limit(DASHBOARD_ACTIVITY_QUERY_LIMIT)
        .all()
    )

    study_name_by_id = {study.id: study.name for study in studies}
    dataset_name_by_id = {str(asset.id): asset.name for asset in dataset_assets}

    raw_pairs: list[tuple[AuditEvent, DashboardActivityItem]] = []
    for event in events:
        item = audit_event_to_activity(
            event,
            study_name_by_id=study_name_by_id,
            dataset_name_by_id=dataset_name_by_id,
        )
        if item is None:
            continue
        raw_pairs.append((event, item))

    # 折叠 1: Execution 生命周期 —— 同一 execution_id 的多个状态事件只保留最新一条
    raw_pairs = collapse_execution_lifecycle(raw_pairs)

    # 折叠 2: Bootstrap —— "创建 Dataset + 配对新 Study" 触发的 4 个 audit 事件合一条
    items = collapse_bootstrap(raw_pairs, study_name_by_id=study_name_by_id)

    return items[:DASHBOARD_ACTIVITY_LIMIT]


def audit_event_to_activity(
    event: AuditEvent,
    *,
    study_name_by_id: dict[str, str] | None = None,
    dataset_name_by_id: dict[str, str] | None = None,
) -> DashboardActivityItem | None:
    object_kind = activity_object_kind(event.resource_kind, event.action)
    if object_kind is None:
        return None
    action_label = audit_action_label(event.action)
    if action_label is None:
        return None

    meta = event.metadata_json or {}
    study_id = event.study_id or (meta.get("study_id") if isinstance(meta, dict) else None)
    study_name = (study_name_by_id or {}).get(study_id) if study_id else None

    # 对 Execution 类事件,从 audit metadata 直接取 pipeline_id / execution_seq,resource_label 就是 pipeline_name
    pipeline_id = None
    pipeline_name = None
    execution_seq = None
    if object_kind == "execution":
        if isinstance(meta, dict):
            pipeline_id = meta.get("pipeline_id")
            execution_seq = meta.get("execution_seq")
        pipeline_name = event.resource_label or None

    # Execution 用分析流程名当标题;其余对象名做人话化(BIDS 路径 → 被试名)
    if object_kind == "execution":
        object_name = pipeline_name or default_activity_name(object_kind)
    else:
        object_name = humanize_object_name(object_kind, event.resource_label) or default_activity_name(object_kind)

    return DashboardActivityItem(
        object_kind=object_kind,
        object_name=object_name,
        action_label=action_label,
        created_at=event.occurred_at,
        target_url=activity_target_url(event, object_kind),
        study_id=study_id,
        study_name=study_name,
        pipeline_id=pipeline_id,
        pipeline_name=pipeline_name,
        execution_seq=execution_seq,
        severity=severity_for_action(event.action),
    )


def collapse_execution_lifecycle(
    pairs: list[tuple[AuditEvent, DashboardActivityItem]],
) -> list[tuple[AuditEvent, DashboardActivityItem]]:
    """同一 execution_id 的 N 个 pipeline.execution.* 事件,只保留时间最新的(列表按时间倒序,第一个出现即最新)。"""
    seen_execution_ids: set[str] = set()
    result: list[tuple[AuditEvent, DashboardActivityItem]] = []
    for event, item in pairs:
        if event.action in EXECUTION_LIFECYCLE_ACTIONS and event.resource_id:
            key = str(event.resource_id)
            if key in seen_execution_ids:
                continue
            seen_execution_ids.add(key)
            item.group_kind = "execution_lifecycle"
        result.append((event, item))
    return result


def collapse_bootstrap(
    pairs: list[tuple[AuditEvent, DashboardActivityItem]],
    *,
    study_name_by_id: dict[str, str],
) -> list[DashboardActivityItem]:
    """把 `dataset.bootstrap` 流程产生的 4 个 audit 合并为一条 Dataset+Study 配对卡片。

    判定:同一个 study_id 下,有 `study.created` 作为 anchor,且周围 ±5s 内还有 bootstrap 相关动作。
    """
    # 找每个 study 的 bootstrap anchor (study.created)
    anchor_by_study: dict[str, AuditEvent] = {}
    for event, _ in pairs:
        if event.action == "study.created" and event.study_id:
            existing = anchor_by_study.get(event.study_id)
            if existing is None or (
                event.occurred_at and existing.occurred_at and event.occurred_at > existing.occurred_at
            ):
                anchor_by_study[event.study_id] = event

    # 标出每个 pair 属于哪个 bootstrap group(如果属于)
    group_members: dict[str, list[tuple[int, AuditEvent, DashboardActivityItem]]] = {}
    member_indices: set[int] = set()
    for idx, (event, item) in enumerate(pairs):
        if event.action not in BOOTSTRAP_ACTIONS:
            continue
        if not event.study_id:
            continue
        anchor = anchor_by_study.get(event.study_id)
        if anchor is None or anchor.occurred_at is None or event.occurred_at is None:
            continue
        if abs((event.occurred_at - anchor.occurred_at).total_seconds()) > BOOTSTRAP_WINDOW_SECONDS:
            continue
        group_members.setdefault(event.study_id, []).append((idx, event, item))
        member_indices.add(idx)

    # 至少 2 个事件才合并(单独一条不折叠)
    bootstrap_cards: dict[int, DashboardActivityItem] = {}
    for study_id, members in group_members.items():
        if len(members) < 2:
            for idx, _, _ in members:
                member_indices.discard(idx)
            continue
        anchor_idx = members[0][0]
        bootstrap_cards[anchor_idx] = build_bootstrap_card(
            members,
            study_id=study_id,
            study_name=study_name_by_id.get(study_id),
        )

    # 组装最终列表:遇到 group 锚点输出合并卡片,其它 group 成员跳过,非 group 原样输出
    result: list[DashboardActivityItem] = []
    for idx, (event, item) in enumerate(pairs):
        if idx in bootstrap_cards:
            result.append(bootstrap_cards[idx])
        elif idx in member_indices:
            continue
        else:
            result.append(item)
    return result


def build_bootstrap_card(
    members: list[tuple[int, AuditEvent, DashboardActivityItem]],
    *,
    study_id: str,
    study_name: str | None,
) -> DashboardActivityItem:
    """把一组 bootstrap 事件合并为一条 Dataset+Study 配对卡片。"""
    dataset_name: str | None = None
    latest_at: datetime | None = None
    has_bootstrap_complete = False
    for _, event, _ in members:
        meta = event.metadata_json or {}
        if event.action == "dataset_asset.created":
            dataset_name = event.resource_label or dataset_name
        elif event.action == "dataset.bootstrap.completed":
            has_bootstrap_complete = True
            if dataset_name is None:
                dataset_name = event.resource_label
        elif event.action == "study.dataset_mount.created":
            # mount 事件的 resource_label 是 mount_name(如 'primary'),不当 dataset_name 用
            if dataset_name is None and isinstance(meta, dict):
                dataset_name = meta.get("dataset_asset_code") or dataset_name
        if event.occurred_at and (latest_at is None or event.occurred_at > latest_at):
            latest_at = event.occurred_at

    summary_parts = []
    if dataset_name:
        summary_parts.append(f"数据「{humanize_object_name('dataset', dataset_name)}」")
    if study_name:
        summary_parts.append(f"研究「{study_name}」")
    group_summary = " · ".join(summary_parts) if summary_parts else None

    object_name = study_name or humanize_object_name("dataset", dataset_name) or "新研究"
    action_label = "新建研究并导入数据" if has_bootstrap_complete else "正在新建研究并导入数据"

    return DashboardActivityItem(
        object_kind="dataset",
        object_name=object_name,
        action_label=action_label,
        created_at=latest_at,
        target_url=f"/studies/{study_id}" if study_id else "/datasets",
        study_id=study_id,
        study_name=study_name,
        severity="success" if has_bootstrap_complete else "info",
        group_kind="bootstrap",
        group_summary=group_summary,
    )


def activity_object_kind(resource_kind: str | None, action: str) -> str | None:
    if (resource_kind or "").startswith("dataset") or action.startswith("dataset"):
        return "dataset"
    if resource_kind in {"study", "study_settings"} or action.startswith("study"):
        return "study"
    if resource_kind == "pipeline" or action.startswith("pipeline."):
        if action.startswith("pipeline.execution") or resource_kind == "pipeline_execution":
            return "execution"
        return "pipeline"
    if resource_kind == "pipeline_execution":
        return "execution"
    return None


def audit_action_label(action: str) -> str | None:
    # 只保留临床用户关心的事件、全大白话；其余(创建/更新噪音、执行中间态)返回 None 被过滤掉。
    # 注意:bootstrap 成员(study.created / dataset_asset.created / mount.created / bootstrap.completed)
    # 必须有标签才能进入折叠;若未折叠成一条,它们也会以这里的中文标签独立显示。
    labels = {
        "dataset.bootstrap.completed": "导入完成",
        "dataset.uploaded": "导入完成",
        "dataset_asset.created": "新增数据",
        "study.created": "新建研究",
        "study.dataset_mount.created": "关联数据",
        "pipeline.created": "新建分析流程",
        "pipeline.execution.waiting_user_input": "等待你确认",
        "pipeline.execution.completed": "分析完成，结果就绪",
        "pipeline.execution.failed": "分析失败",
        "pipeline.execution.dispatch_failed": "分析失败",
        "pipeline.execution.retry_dispatch_failed": "分析失败",
        "pipeline.execution.task_exception": "分析失败",
    }
    return labels.get(action)


def activity_target_url(event: AuditEvent, object_kind: str) -> str | None:
    # 容器化 + 术语统一（workflow→pipeline）后，工作流统一进 study 容器子路由:
    # /studies/{study_id}/pipeline?pipeline_id=..&execution_id=..（studyId 进路径，其余进 query）。
    # 旧 /workflow 段已改名 /pipeline 且不留重定向，此处必须用 /pipeline。
    if object_kind == "dataset":
        return "/datasets"
    if object_kind == "study" and event.study_id:
        return f"/studies/{event.study_id}"
    if object_kind == "pipeline" and event.study_id:
        pipeline_id = event.resource_id
        if pipeline_id:
            return f"/studies/{event.study_id}/pipeline?pipeline_id={pipeline_id}"
        return f"/studies/{event.study_id}/pipeline"
    if object_kind == "execution" and event.study_id:
        pipeline_id = (event.metadata_json or {}).get("pipeline_id")
        if pipeline_id and event.resource_id:
            return f"/studies/{event.study_id}/pipeline?pipeline_id={pipeline_id}&execution_id={event.resource_id}"
        return f"/studies/{event.study_id}/pipeline"
    return None


def default_activity_name(object_kind: str) -> str:
    return {
        "dataset": "数据",
        "study": "研究",
        "pipeline": "分析流程",
        "execution": "分析",
    }.get(object_kind, "对象")


def humanize_object_name(object_kind: str, name: str | None) -> str | None:
    """把 BIDS 实体路径(如 sub-01/no-session/task-rest/no-run)收成人话(被试 sub-01)。"""
    if not name:
        return name
    if object_kind == "dataset" and "/" in name:
        for segment in name.split("/"):
            if segment.startswith("sub-"):
                return f"被试 {segment}"
    return name


def datetime_sort_value(value: datetime | None) -> float:
    if value is None:
        return 0
    return value.timestamp()
