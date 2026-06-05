"""
Purpose: Define DerivedDataset SQLAlchemy ORM model.

DerivedDataset is the unified user-facing concept that replaces both
pipeline_artifacts (节点产物文件) and analysis_results (Save 登记的正式结果).
每个 Pipeline 节点产出的文件都登记为一条 derived_datasets 行；Save 节点
通过提升 retention_status + 设置 display_name / tags 来把上游派生数据
"晋升"为正式结果。

Related:
- database/schema/05_derived.sql (table definition)
- app/pipeline/derived_dataset_store.py (DerivedDatasetStore)
- app/pipeline/dispatcher.py (writes derived_datasets)
- wiki/docs/3-45-DerivedDataset.md (concept)
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
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


class DerivedDataset(Base):
    __tablename__ = "derived_datasets"
    __table_args__ = (
        Index(
            "idx_derived_study",
            "study_id",
            "retention_status",
            "created_at",
        ),
        Index(
            "idx_derived_subject_type",
            "study_id",
            "bids_subject_id",
            "data_type",
        ),
        Index("idx_derived_execution", "produced_by_execution_id"),
        Index("idx_derived_job", "produced_by_job_id"),
        Index("idx_derived_tags", "tags", postgresql_using="gin"),
        Index(
            "idx_derived_sha256",
            "study_id",
            "sha256",
            unique=True,
            postgresql_where=text("sha256 IS NOT NULL"),
        ),
        Index(
            "idx_derived_retention_expires",
            "retention_expires_at",
            postgresql_where=text("retention_expires_at IS NOT NULL"),
        ),
        # Phase 1 (docs_v2/3-25): 生命周期索引（支持跨 Study 列出可引用的 published 派生数据）
        Index("idx_derived_lifecycle", "lifecycle_state"),
        Index(
            "idx_derived_shared_published",
            "lifecycle_state",
            "visibility",
            postgresql_where=text("lifecycle_state = 'published' AND visibility = 'shared'"),
        ),
        Index(
            "idx_derived_deleted",
            "study_id",
            "deleted_at",
            postgresql_where=text("deleted_at IS NOT NULL"),
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
        ForeignKey("pipeline_executions.id", ondelete="CASCADE"),
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

    # ---- Lifecycle ---------------------------------------------------------
    retention_status = Column(
        String(32),
        nullable=False,
        default="current",
    )
    retention_expires_at = Column(DateTime)

    # Phase 1 (docs_v2/3-25): 派生数据生命周期, 继承自 upstream
    # draft       = upstream draft / 主 Study 调试用, 跨 Study 不可见
    # published   = upstream published 且 owner 升级后, 跨 Study 可见
    # withdrawn   = upstream withdrawn 联动, 新引用禁止
    lifecycle_state = Column(String(32), nullable=False, default="draft")
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

    # ---- Relationships -----------------------------------------------------
    study = relationship("Study", foreign_keys=[study_id])
    execution = relationship(
        "PipelineExecution",
        foreign_keys=[produced_by_execution_id],
        back_populates="derived_datasets",
    )
    job = relationship(
        "PipelineJob",
        foreign_keys=[produced_by_job_id],
        back_populates="derived_datasets",
    )
    subject = relationship("Subject", foreign_keys=[subject_id])
    creator = relationship("User", foreign_keys=[created_by])
