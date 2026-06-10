"""
Purpose: Build the aggregated "Study overview" summary for one study.

研究项详情页「概览」tab 需要一次性拿到该 study 的 数据/工作流/运行/结果 全貌。
本服务把 dashboard_summary 的「多 study 聚合」范式改造成「单 study 版」，
让前端用一个请求替代原先并发拼约 12 个请求（N+1）。

复用 dashboard_summary 的现成聚合 helper（不重写 SQL 逻辑）：
- grouped_count：按 study 分组计数（这里只传单个 study_id，取该 study 的计数）。
- DASHBOARD_EXECUTION_STATUSES / pipeline 状态过滤约定（status != "deleted" 等）。
- build_active_executions 的 PipelineExecution⋈PipelineDefinition join 范式
  （本文件 build_recent_executions 复用同一 join 思路，但只取最近 N 条而非按状态优先级排序）。

复用现有 Pydantic 序列化（不新造）：
- mounts -> app.routers.datasets.study_dataset_mount_to_response + compute_asset_stats
- study_outputs -> app.routers.pipelines.study_output_to_response

Related:
- app/routers/studies.py (HTTP endpoint, 复用 require_study_read 权限依赖)
- app/schemas/study_summary.py (response model)
- app/services/dashboard_summary.py (聚合范式来源)
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    StudyOutput,
    PipelineDefinition,
    PipelineExecution,
    Recording,
    Study,
    StudyDatasetMount,
    StudyMember,
    User,
)
from app.schemas.study_summary import (
    StudySummaryCounts,
    StudySummaryExecution,
    StudySummaryPipeline,
    StudySummaryResponse,
)
from app.services.dashboard_summary import grouped_count
from app.services.dataset_assets import compute_asset_stats

# 概览各列表的默认条数（与任务约定一致）。
STUDY_SUMMARY_PIPELINE_LIMIT = 5
STUDY_SUMMARY_EXECUTION_LIMIT = 5
STUDY_SUMMARY_DERIVED_LIMIT = 12

# 「运行中」口径：这些状态算作仍在跑/待处理。
STUDY_SUMMARY_RUNNING_STATUSES = ("pending", "running", "queued", "waiting_user_input")


def build_study_summary(db: Session, *, study: Study, current_user: User) -> StudySummaryResponse:
    """聚合单个 study 的概览。调用方需先用 require_study_read 校验过访问权限。"""
    study_ids = [study.id]

    # --- active mounts（很多计数都依赖它，先取出来）------------------------------
    active_mounts = (
        db.query(StudyDatasetMount)
        .filter(
            StudyDatasetMount.study_id == study.id,
            StudyDatasetMount.is_active.is_(True),
        )
        .order_by(StudyDatasetMount.mounted_at.desc(), StudyDatasetMount.id.desc())
        .all()
    )
    active_asset_ids = [mount.dataset_asset_id for mount in active_mounts]

    # --- counts：复用 dashboard 的 grouped_count（单 study 版即传单元素 study_ids）-----
    pipeline_counts = grouped_count(
        db,
        PipelineDefinition.study_id,
        PipelineDefinition.id,
        study_ids,
        PipelineDefinition.status != "deleted",
    )
    execution_counts = grouped_count(
        db,
        PipelineExecution.study_id,
        PipelineExecution.id,
        study_ids,
    )

    member_count = (
        db.query(func.count(StudyMember.id))
        .filter(StudyMember.study_id == study.id)
        .scalar()
        or 0
    )

    recording_count = recordings_via_active_mounts(db, active_asset_ids)
    subject_total = subject_total_via_active_mounts(db, active_asset_ids)

    derived_count = (
        db.query(func.count(StudyOutput.id))
        .filter(
            StudyOutput.study_id == study.id,
            StudyOutput.retention_status != "deleted",
        )
        .scalar()
        or 0
    )

    running_execution_count = (
        db.query(func.count(PipelineExecution.id))
        .filter(
            PipelineExecution.study_id == study.id,
            PipelineExecution.status.in_(STUDY_SUMMARY_RUNNING_STATUSES),
        )
        .scalar()
        or 0
    )

    counts = StudySummaryCounts(
        recordings=int(recording_count),
        pipelines=int(pipeline_counts.get(study.id, 0)),
        executions=int(execution_counts.get(study.id, 0)),
        members=int(member_count),
        mounts=len(active_mounts),
        study_outputs=int(derived_count),
    )

    # --- 当前用户角色 / 运行权限 -------------------------------------------------
    member_role, can_run = resolve_member_role_and_run(db, study=study, user=current_user)

    return StudySummaryResponse(
        counts=counts,
        subject_total=int(subject_total),
        running_execution_count=int(running_execution_count),
        member_role=member_role,
        can_run=can_run,
        pipelines=recent_pipelines(db, study=study),
        executions=recent_executions(db, study=study),
        mounts=serialize_mounts(db, active_mounts),
        study_outputs=recent_study_outputs(db, study=study),
    )


def recordings_via_active_mounts(db: Session, active_asset_ids: list) -> int:
    """该 study 通过 active mounts 可见的采集记录数。

    Recording 直接挂在 dataset_asset 上（Recording.dataset_asset_id），所以
    「可见记录」= 落在 active mount 锁定的 asset 集合内的 Recording 行数。
    """
    if not active_asset_ids:
        return 0
    return int(
        db.query(func.count(Recording.id))
        .filter(Recording.dataset_asset_id.in_(active_asset_ids))
        .scalar()
        or 0
    )


def subject_total_via_active_mounts(db: Session, active_asset_ids: list) -> int:
    """挂载数据集覆盖的被试总数。

    口径：去重。跨所有 active mount 的 asset 用 COUNT(DISTINCT Recording.subject_id)
    一次聚合，同一被试即便出现在多个挂载数据集里也只计一次（与 compute_asset_stats
    里 per-asset 的 subject_count 写法同源，只是这里去掉 GROUP BY 做跨 asset 去重）。
    """
    if not active_asset_ids:
        return 0
    return int(
        db.query(func.count(func.distinct(Recording.subject_id)))
        .filter(Recording.dataset_asset_id.in_(active_asset_ids))
        .scalar()
        or 0
    )


def recent_pipelines(db: Session, *, study: Study) -> list[StudySummaryPipeline]:
    """最近 5 条非 deleted 工作流，更新时间倒序（与 list_pipelines 排序口径一致）。"""
    rows = (
        db.query(PipelineDefinition)
        .filter(PipelineDefinition.study_id == study.id, PipelineDefinition.status != "deleted")
        .order_by(PipelineDefinition.updated_at.desc(), PipelineDefinition.id.desc())
        .limit(STUDY_SUMMARY_PIPELINE_LIMIT)
        .all()
    )
    return [
        StudySummaryPipeline(
            id=pipeline.id,
            name=pipeline.name,
            version=pipeline.version,
            node_count=pipeline.node_count,
            status=pipeline.status,
        )
        for pipeline in rows
    ]


def recent_executions(db: Session, *, study: Study) -> list[StudySummaryExecution]:
    """最近 5 条运行，时间倒序。

    复用 build_active_executions 的 PipelineExecution⋈PipelineDefinition join 思路，
    但这里不按状态优先级排序、也不限定状态集合——概览要看「最近发生了什么」，
    所以单纯按 started_at / execution_seq 倒序取头 5 条。
    """
    rows = (
        db.query(PipelineExecution)
        .filter(PipelineExecution.study_id == study.id)
        .order_by(PipelineExecution.started_at.desc(), PipelineExecution.execution_seq.desc())
        .limit(STUDY_SUMMARY_EXECUTION_LIMIT)
        .all()
    )
    return [
        StudySummaryExecution(
            id=str(execution.id),
            execution_seq=execution.execution_seq,
            execution_mode=getattr(execution, "execution_mode", None) or "analysis",
            status=execution.status,
            started_at=execution.started_at,
            finished_at=execution.finished_at,
        )
        for execution in rows
    ]


def serialize_mounts(db: Session, active_mounts: list[StudyDatasetMount]) -> list:
    """复用 datasets 路由的 mount 序列化 + compute_asset_stats（给嵌套 asset 带 subject_count）。"""
    # 延迟导入：避免 service 层在模块加载期反向依赖 router 层（routers 会 import services）。
    from app.routers.datasets import study_dataset_mount_to_response

    asset_ids = [mount.dataset_asset_id for mount in active_mounts]
    stats_map = compute_asset_stats(db, asset_ids)
    return [
        study_dataset_mount_to_response(mount, asset_stats=stats_map.get(str(mount.dataset_asset_id)))
        for mount in active_mounts
    ]


def recent_study_outputs(db: Session, *, study: Study) -> list:
    """最近 12 条非 deleted 派生数据集，复用 pipelines 路由的 study_output_to_response。"""
    from app.routers.pipelines import study_output_to_response

    rows = (
        db.query(StudyOutput)
        .filter(
            StudyOutput.study_id == study.id,
            StudyOutput.retention_status != "deleted",
        )
        .order_by(StudyOutput.created_at.desc(), StudyOutput.id.desc())
        .limit(STUDY_SUMMARY_DERIVED_LIMIT)
        .all()
    )
    return [study_output_to_response(item) for item in rows]


def resolve_member_role_and_run(db: Session, *, study: Study, user: User) -> tuple[str | None, bool]:
    """算出当前用户在该 study 的角色与运行权限。

    - admin：系统管理员，角色记 "admin"，can_run=True。
    - owner：study.owner_id == user.id，角色记 "owner"，can_run=True。
    - 普通成员：取 StudyMember.role，can_run 复用 require_study_access 的口径
      （membership.can_run or role == "owner"）。
    - 既非 owner/admin 也无 membership：role=None，can_run=False。
    """
    if user.has_role("admin"):
        return "admin", True
    if study.owner_id == user.id:
        return "owner", True

    membership = (
        db.query(StudyMember)
        .filter(StudyMember.study_id == study.id, StudyMember.user_id == user.id)
        .first()
    )
    if membership is None:
        return None, False
    can_run = bool(membership.can_run or membership.role == "owner")
    return membership.role, can_run
