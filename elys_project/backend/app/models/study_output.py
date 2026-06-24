"""
Purpose: Define StudyOutput SQLAlchemy ORM model.

StudyOutput is the unified user-facing concept that replaces both
pipeline_artifacts (节点产物文件) and analysis_results (Save 登记的正式结果).
每个 Pipeline 节点产出的文件都登记为一条 study_outputs 行；keep=true
的行在结果页作为正式输出展示，keep=false 的为缓存/临时产物。

Related:
- database/schema/05_outputs.sql (table definition)
- app/pipeline/study_output_store.py (StudyOutputStore)
- app/pipeline/dispatcher.py (writes study_outputs)
- wiki/docs/3-45-StudyOutput.md (concept)
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class StudyOutput(Base):
    __tablename__ = "study_outputs"
    __table_args__ = (
        Index(
            "idx_study_output_study",
            "study_id",
            "keep",
            "created_at",
        ),
        Index(
            "idx_study_output_subject_type",
            "study_id",
            "bids_subject_id",
            "data_type",
        ),
        Index("idx_study_output_execution", "produced_by_execution_id"),
        Index("idx_study_output_job", "produced_by_job_id"),
        Index("idx_study_output_tags", "tags", postgresql_using="gin"),
        Index(
            "idx_study_output_sha256",
            "study_id",
            "sha256",
            unique=True,
            postgresql_where=text("sha256 IS NOT NULL"),
        ),
        Index(
            "idx_study_output_retention_expires",
            "retention_expires_at",
            postgresql_where=text("retention_expires_at IS NOT NULL"),
        ),
        # Phase 1 (docs_v2/3-25): 生命周期索引（支持跨 Study 列出可引用的 published 结果）
        Index("idx_study_output_lifecycle", "lifecycle_state"),
        Index(
            "idx_study_output_shared_published",
            "lifecycle_state",
            "visibility",
            postgresql_where=text("lifecycle_state = 'published' AND visibility = 'shared'"),
        ),
        Index(
            "idx_study_output_deleted",
            "study_id",
            "deleted_at",
            postgresql_where=text("deleted_at IS NOT NULL"),
        ),
        Index(
            "idx_study_output_purge_candidate",
            "deleted_at",
            postgresql_where=text("deleted_at IS NOT NULL AND purged_at IS NULL"),
        ),
    )

    # ---- Identity ----------------------------------------------------------
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    study_id = Column(
        String(12),
        ForeignKey("studies.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ---- Provenance --------------------------------------------------------
    produced_by_execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_executions.id", ondelete="SET NULL"),
    )
    produced_by_job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_jobs.id", ondelete="SET NULL"),
    )
    produced_by_node_id = Column(String(128))
    produced_by_node_type = Column(String(128))
    produced_by_params = Column(JSONB, nullable=False, default=dict)
    upstream_dataset_ids = Column(JSONB, nullable=False, default=list)
    upstream_recording_ids = Column(JSONB, nullable=False, default=list)

    # ---- Semantics ---------------------------------------------------------
    data_type = Column(String(64), nullable=False)
    subject_id = Column(
        UUID(as_uuid=True),
        ForeignKey("subjects.id", ondelete="SET NULL"),
    )
    bids_subject_id = Column(String(64))
    session = Column(String(64))
    task = Column(String(64))
    run_label = Column(String(64))
    condition = Column(String(128))

    # ---- User-facing -------------------------------------------------------
    display_name = Column(String(256))
    description = Column(Text)
    tags = Column(JSONB, nullable=False, default=list)

    # ---- Physical storage --------------------------------------------------
    storage_uri = Column(String(1024), nullable=False)
    logical_path = Column(String(1024))
    file_role = Column(String(64))
    file_size = Column(BigInteger)
    sha256 = Column(String(64))
    mime_type = Column(String(128))

    # ---- 保留与缓存（三层解耦） --------------------------------------------
    # keep           = 用户是否保留（true=结果页可见、永不自动清；false=缓存/临时）
    # cache_eligible = 系统是否值得缓存（= is_cache_eligible(node_spec)，P4 存储优先评分）
    # retention_expires_at = 仅 keep=false 的缓存行 TTL；keep=true 恒为 None（永久）
    keep = Column(Boolean, nullable=False, default=False)
    cache_eligible = Column(Boolean, nullable=False, default=False)
    retention_expires_at = Column(DateTime)

    # 结果生命周期, 继承自 upstream（与 DatasetVersion.state 同口径，2026-06-09 v2）
    # unpublished = upstream 未发布 / 主研究项调试用, 跨研究项不可见
    # published   = upstream published 且 owner 升级后, 跨研究项可见
    # withdrawn   = upstream withdrawn 联动, 新引用禁止
    lifecycle_state = Column(String(32), nullable=False, default="unpublished")
    visibility = Column(String(32), nullable=False, default="private")

    # ---- Preview index -----------------------------------------------------
    preview_json = Column(JSONB, nullable=False, default=dict)

    # ---- Metadata ----------------------------------------------------------
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    deleted_at = Column(DateTime)
    # GC 物理清盘磁盘文件后置位；DB 行保留可追溯（仅文件没了、预览/下载不可用）
    purged_at = Column(DateTime)

    # ---- Relationships -----------------------------------------------------
    study = relationship("Study", foreign_keys=[study_id])
    execution = relationship(
        "PipelineExecution",
        foreign_keys=[produced_by_execution_id],
        back_populates="study_outputs",
    )
    job = relationship(
        "PipelineJob",
        foreign_keys=[produced_by_job_id],
        back_populates="study_outputs",
    )
    subject = relationship("Subject", foreign_keys=[subject_id])
    creator = relationship("User", foreign_keys=[created_by])


class ExecutionOutput(Base):
    """execution ↔ study_output 多对多关联边。

    一条 study_output 按 (study_id, sha256) content-addressed 去重，全 study 只有一行，
    produced_by_execution_id / produced_by_job_id 永远指向"最早产出它的那次执行"。重跑（结果
    字节相同→去重命中）或缓存命中时，新执行不会新建 study_output 行，于是按
    produced_by_execution_id 统计"本次执行产物"会漏掉这些复用行（运行面板显示 0）。

    本表为每次"某执行的某 job 产出/复用某 study_output"记一条边：
    - relation='created'：本次执行 INSERT 了该行（首产者）。
    - relation='reused'：本次执行去重 / 缓存命中复用了已存在的行。

    运行面板/执行详情改从这里统计，既修显示又不动 study_outputs 的 canonical 血缘。
    """

    __tablename__ = "execution_outputs"
    __table_args__ = (
        Index("idx_execution_outputs_execution", "execution_id"),
        Index("idx_execution_outputs_job", "job_id"),
        Index("idx_execution_outputs_output", "study_output_id"),
        Index(
            "idx_execution_outputs_unique",
            "execution_id",
            "job_id",
            "study_output_id",
            unique=True,
        ),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    study_id = Column(
        String(12),
        ForeignKey("studies.id", ondelete="CASCADE"),
        nullable=False,
    )
    execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_executions.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_jobs.id", ondelete="SET NULL"),
    )
    study_output_id = Column(
        UUID(as_uuid=True),
        ForeignKey("study_outputs.id", ondelete="CASCADE"),
        nullable=False,
    )
    node_id = Column(String(128))
    node_type = Column(String(128))
    # created = 本次执行新建该行；reused = 本次执行去重/缓存命中复用已存在行
    relation = Column(String(16), nullable=False, default="created")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    study_output = relationship("StudyOutput", foreign_keys=[study_output_id])
