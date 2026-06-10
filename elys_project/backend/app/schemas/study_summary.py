"""
Purpose: Define the aggregated "Study overview" summary response schema.

研究项详情页「概览」tab 一次性展示该 study 的 数据/工作流/运行/结果 全貌。
本 schema 是后端聚合端点 GET /api/v1/studies/{study_id}/summary 的返回模型，
用于替代前端原先并发拼约 12 个请求（N+1）的做法。

复用现有 schema 序列化 mounts / study_outputs：
- mounts -> app.schemas.dataset.StudyDatasetMountResponse
- study_outputs -> app.schemas.study_output.StudyOutputResponse

Related:
- app/routers/studies.py (HTTP endpoint)
- app/services/study_summary.py (aggregation logic)
- app/services/dashboard_summary.py (复用的聚合范式)
- frontend StudyDetail 概览 tab
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.schemas.dataset import StudyDatasetMountResponse
from app.schemas.study_output import StudyOutputResponse


class StudySummaryCounts(BaseModel):
    """该 study 各类对象的计数（数字徽标用）。"""

    recordings: int          # 该 study 通过 active mounts 可见的采集记录数
    pipelines: int           # 非 deleted 的工作流数
    executions: int          # 全部运行数（含已结束）
    members: int             # study_members 行数（不含 owner）
    mounts: int              # active study_dataset_mounts 数
    study_outputs: int    # 非 deleted 的结果数


class StudySummaryPipeline(BaseModel):
    """概览里的工作流卡片（最近 5 条，轻量字段）。"""

    id: int
    name: str
    version: int
    node_count: int
    status: str


class StudySummaryExecution(BaseModel):
    """概览里的运行卡片（最近 5 条，轻量字段）。"""

    id: str
    execution_seq: int
    execution_mode: str
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class StudySummaryResponse(BaseModel):
    """研究项概览聚合返回体。字段名严格 snake_case，前端按此消费。"""

    counts: StudySummaryCounts
    # 挂载数据集覆盖的被试总数；跨 active mount 的 asset 用 COUNT(DISTINCT subject_id) 去重统计
    subject_total: int
    # 运行中的执行数：status in (pending, running, queued, waiting_user_input)
    running_execution_count: int
    # 当前用户在该 study 的角色 owner/editor/viewer/admin；非成员且非 owner/admin 时为 None
    member_role: Optional[str] = None
    can_run: bool

    pipelines: list[StudySummaryPipeline]      # 最近 5 条，时间倒序
    executions: list[StudySummaryExecution]    # 最近 5 条，时间倒序
    mounts: list[StudyDatasetMountResponse]    # 现有 mount 序列化（含 dataset_asset / dataset_version）
    study_outputs: list[StudyOutputResponse]  # 现有结果序列化，最近 12 条
