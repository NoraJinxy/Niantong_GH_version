"""
Purpose: Define SQLAlchemy ORM models for the study database area.
Related: database/init.sql, app/schemas/*, app/routers/*, docs_v2/3-00.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Study(Base):
    __tablename__ = "studies"

    id = Column(String(12), primary_key=True, server_default=text("next_study_id()"))
    code = Column(String(64), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    status = Column(String(16), nullable=False, default="active")
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    data_root = Column(String(512), nullable=False)
    storage_quota_bytes = Column(BigInteger, nullable=False, default=1099511627776)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    archived_at = Column(DateTime)
    deleted_at = Column(DateTime)
    deleted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    delete_reason = Column(Text)

    owner = relationship("User", foreign_keys=[owner_id])
    deleted_by_user = relationship("User", foreign_keys=[deleted_by])
    members = relationship("StudyMember", cascade="all, delete-orphan", back_populates="study")
    subjects = relationship("Subject", cascade="all, delete-orphan", back_populates="study")
    recordings = relationship("Recording", cascade="all, delete-orphan", back_populates="study")
    dataset_files = relationship("DatasetFile", back_populates="study", passive_deletes=True)
    pipelines = relationship("PipelineDefinition", cascade="all, delete-orphan", back_populates="study")
    async_tasks = relationship("AsyncTask", back_populates="study", passive_deletes=True)
    study_locks = relationship("StudyLock", cascade="all, delete-orphan", back_populates="study")
    study_settings = relationship("StudySettings", cascade="all, delete-orphan", back_populates="study", uselist=False)
    dataset_mounts = relationship("StudyDatasetMount", cascade="all, delete-orphan", back_populates="study")

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "owner_id": str(self.owner_id),
            "data_root": self.data_root,
            "storage_quota_bytes": self.storage_quota_bytes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "deleted_by": str(self.deleted_by) if self.deleted_by else None,
            "delete_reason": self.delete_reason,
        }


class AuditEvent(Base):
    """统一审计事件表。2026-05-24 合并旧 StudyAuditEvent —— Study 硬删除快照写入 snapshot 字段。"""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("idx_audit_events_study_time", "study_id", "occurred_at"),
        Index("idx_audit_events_actor_time", "actor_id", "occurred_at"),
        Index("idx_audit_events_action_time", "action", "occurred_at"),
        Index("idx_audit_events_resource", "resource_kind", "resource_id", "occurred_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    study_id = Column(String(12))  # 不引用 studies(id),Study 硬删除后此审计记录仍保留
    event_scope = Column(String(64), nullable=False, default="study")
    action = Column(String(128), nullable=False)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    resource_kind = Column(String(64))
    resource_id = Column(String(128))
    resource_label = Column(String(256))
    snapshot = Column(JSONB, nullable=False, default=dict)  # Study/Dataset/Pipeline 硬删除前的实体快照
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    occurred_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    actor = relationship("User", foreign_keys=[actor_id])


class StudyMember(Base):
    __tablename__ = "study_members"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    study_id = Column(String(12), ForeignKey("studies.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(32), nullable=False, default="viewer")
    can_read = Column(Boolean, nullable=False, default=True)
    can_write = Column(Boolean, nullable=False, default=False)
    can_delete = Column(Boolean, nullable=False, default=False)
    can_export = Column(Boolean, nullable=False, default=False)
    can_run = Column(Boolean, nullable=False, default=False)
    added_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    added_at = Column(DateTime, default=datetime.utcnow)

    study = relationship("Study", foreign_keys=[study_id], back_populates="members")
    user = relationship("User", foreign_keys=[user_id])
    added_by_user = relationship("User", foreign_keys=[added_by])


class StudyLock(Base):
    __tablename__ = "study_locks"
    __table_args__ = (
        Index("idx_study_locks_study_resource", "study_id", "resource_kind", "resource_id", "lock_type"),
        Index("idx_study_locks_locked_by", "locked_by"),
        Index("idx_study_locks_expires", "expires_at"),
        Index(
            "uq_study_locks_active_resource",
            "study_id",
            "resource_kind",
            "resource_id",
            "lock_type",
            unique=True,
            postgresql_where=text("released_at IS NULL"),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    study_id = Column(String(12), ForeignKey("studies.id", ondelete="CASCADE"), nullable=False)
    resource_kind = Column(String(64), nullable=False)
    resource_id = Column(String(128), nullable=False)
    lock_type = Column(String(32), nullable=False)
    locked_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    locked_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    released_at = Column(DateTime)
    released_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)

    study = relationship("Study", foreign_keys=[study_id], back_populates="study_locks")
    locked_by_user = relationship("User", foreign_keys=[locked_by])
    released_by_user = relationship("User", foreign_keys=[released_by])


class StudySettings(Base):
    __tablename__ = "study_settings"
    __table_args__ = (
        Index("idx_study_settings_updated_by", "updated_by"),
    )

    study_id = Column(String(12), ForeignKey("studies.id", ondelete="CASCADE"), primary_key=True)
    default_dataset_filter = Column(
        JSONB,
        nullable=False,
        default=lambda: {
            "subjects": "all",
            "sessions": "all",
            "tasks": "all",
            "runs": "all",
            "qa_status": "all",
            "require_fif": True,
        },
    )
    run_policy = Column(JSONB, nullable=False, default=lambda: {"single_active_pipeline_run": True})
    storage_policy = Column(JSONB, nullable=False, default=dict)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    study = relationship("Study", foreign_keys=[study_id], back_populates="study_settings")
    updated_by_user = relationship("User", foreign_keys=[updated_by])


class DatasetAsset(Base):
    __tablename__ = "dataset_assets"
    __table_args__ = (
        Index("uq_dataset_assets_code", "code", unique=True),
        Index("idx_dataset_assets_owner", "owner_id"),
        Index("idx_dataset_assets_visibility_status", "visibility", "status"),
        Index("idx_dataset_assets_created_by", "created_by"),
        Index("idx_dataset_assets_primary_study", "primary_study_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    name = Column(String(200), nullable=False)
    code = Column(String(64), nullable=False)
    description = Column(Text)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    status = Column(String(32), nullable=False, default="working")
    visibility = Column(String(32), nullable=False, default="private")
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    # Phase 1 (3-25): 生命周期相关字段
    primary_study_id = Column(String(12), ForeignKey("studies.id", ondelete="SET NULL"))
    concept_doi = Column(String(256))
    current_version_id = Column(UUID(as_uuid=True), ForeignKey("dataset_versions.id", ondelete="SET NULL"))
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    owner = relationship("User", foreign_keys=[owner_id])
    created_by_user = relationship("User", foreign_keys=[created_by])
    primary_study = relationship("Study", foreign_keys=[primary_study_id])
    current_version = relationship("DatasetVersion", foreign_keys=[current_version_id], post_update=True)
    mounts = relationship("StudyDatasetMount", back_populates="dataset_asset", passive_deletes=True)
    recordings = relationship("Recording", back_populates="dataset_asset", passive_deletes=True)
    members = relationship(
        "DatasetMember",
        cascade="all, delete-orphan",
        back_populates="dataset_asset",
        foreign_keys="DatasetMember.asset_id",
    )
    versions = relationship(
        "DatasetVersion",
        cascade="all, delete-orphan",
        back_populates="dataset_asset",
        foreign_keys="DatasetVersion.dataset_asset_id",
    )


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (
        Index("idx_dataset_versions_asset", "dataset_asset_id", "state"),
        Index("idx_dataset_versions_created_by", "created_by"),
        Index("idx_dataset_versions_state", "state"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    dataset_asset_id = Column(UUID(as_uuid=True), ForeignKey("dataset_assets.id", ondelete="CASCADE"), nullable=False)
    version_label = Column(String(64), nullable=False, default="working")
    # 发布状态轴：unpublished → published → withdraw_requested → withdrawn
    state = Column(String(32), nullable=False, default="unpublished")
    content_hash = Column(String(64))
    version_doi = Column(String(256))
    published_at = Column(DateTime)
    published_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    qa_status = Column(String(16), nullable=False, default="not_run")
    withdraw_requested_at = Column(DateTime)
    withdraw_requested_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    withdraw_reason = Column(Text)
    withdrawn_at = Column(DateTime)
    withdrawn_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    withdrawal_admin_notes = Column(Text)
    storage_uri = Column(String(1024))
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    dataset_asset = relationship(
        "DatasetAsset",
        foreign_keys=[dataset_asset_id],
        back_populates="versions",
    )
    created_by_user = relationship("User", foreign_keys=[created_by])
    published_by_user = relationship("User", foreign_keys=[published_by])
    withdraw_requested_by_user = relationship("User", foreign_keys=[withdraw_requested_by])
    withdrawn_by_user = relationship("User", foreign_keys=[withdrawn_by])
    files = relationship("DatasetFile", back_populates="dataset_version", passive_deletes=True)


class StudyDatasetMount(Base):
    __tablename__ = "study_dataset_mounts"
    __table_args__ = (
        Index("idx_study_dataset_mounts_study", "study_id", "is_active"),
        Index("idx_study_dataset_mounts_asset", "dataset_asset_id"),
        Index("idx_study_dataset_mounts_mounted_by", "mounted_by"),
        Index("idx_study_dataset_mounts_version", "dataset_version_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    study_id = Column(String(12), ForeignKey("studies.id", ondelete="CASCADE"), nullable=False)
    dataset_asset_id = Column(UUID(as_uuid=True), ForeignKey("dataset_assets.id", ondelete="RESTRICT"), nullable=False)
    # Phase 1 (3-25): nullable，Phase 3 起非空
    dataset_version_id = Column(UUID(as_uuid=True), ForeignKey("dataset_versions.id", ondelete="RESTRICT"))
    mount_name = Column(String(128), nullable=False)
    selection_json = Column(JSONB, nullable=False, default=dict)
    is_active = Column(Boolean, nullable=False, default=True)
    mounted_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    mounted_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    study = relationship("Study", foreign_keys=[study_id], back_populates="dataset_mounts")
    dataset_asset = relationship("DatasetAsset", foreign_keys=[dataset_asset_id], back_populates="mounts")
    dataset_version = relationship("DatasetVersion", foreign_keys=[dataset_version_id])
    mounted_by_user = relationship("User", foreign_keys=[mounted_by])


class DatasetMember(Base):
    """数据集共享授权（邀请制，按用户）。

    可见范围 = shared 时，由负责人按用户逐一授权；被授权者可读该资产、可关联到自己研究项。
    仅 shared 档生效：private 走主研究项成员、public 对任意注册用户放行（详见 wiki/docs/3-25）。
    """

    __tablename__ = "dataset_members"
    __table_args__ = (
        Index("idx_dataset_members_asset", "asset_id"),
        Index("idx_dataset_members_user", "user_id"),
        Index("uq_dataset_members_asset_user", "asset_id", "user_id", unique=True),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    asset_id = Column(UUID(as_uuid=True), ForeignKey("dataset_assets.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    granted_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    granted_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    dataset_asset = relationship("DatasetAsset", foreign_keys=[asset_id], back_populates="members")
    user = relationship("User", foreign_keys=[user_id])
    granted_by_user = relationship("User", foreign_keys=[granted_by])


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    study_id = Column(String(12), ForeignKey("studies.id", ondelete="CASCADE"), nullable=False)
    bids_subject_id = Column(String(32), nullable=False)
    age = Column(Numeric(5, 2))
    sex = Column(String(8))
    group = Column(String(64))
    handedness = Column(String(8))
    extra = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    study = relationship("Study", foreign_keys=[study_id], back_populates="subjects")
    recordings = relationship("Recording", cascade="all, delete-orphan", back_populates="subject")


class Recording(Base):
    """采集记录 —— 一条 BIDS subject/session/task/run 单元。
    原 `Dataset` 类合并到此（A 重构 2026-06-04）。"""

    __tablename__ = "recordings"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    study_id = Column(String(12), ForeignKey("studies.id", ondelete="CASCADE"), nullable=False)
    dataset_asset_id = Column(UUID(as_uuid=True), ForeignKey("dataset_assets.id", ondelete="RESTRICT"))
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    session = Column(String(32))
    task = Column(String(64), nullable=False)
    run = Column(String(32))
    source_format = Column(String(16), nullable=False)
    source_path = Column(String(512), nullable=False)
    fif_path = Column(String(512))
    current_version_id = Column(UUID(as_uuid=True), ForeignKey("recording_versions.id", ondelete="SET NULL"))
    file_size = Column(BigInteger)
    checksum = Column(String(64))
    n_channels = Column(Integer)
    sfreq = Column(Float)
    duration_seconds = Column(Float)
    n_events = Column(Integer)
    qa_status = Column(String(16), nullable=False, default="pending")
    qa_report = Column(JSONB)
    imported_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    imported_at = Column(DateTime, default=datetime.utcnow)

    study = relationship("Study", foreign_keys=[study_id], back_populates="recordings")
    dataset_asset = relationship("DatasetAsset", foreign_keys=[dataset_asset_id], back_populates="recordings")
    subject = relationship("Subject", foreign_keys=[subject_id], back_populates="recordings")
    imported_by_user = relationship("User", foreign_keys=[imported_by])
    current_version = relationship("RecordingVersion", foreign_keys=[current_version_id], post_update=True)
    versions = relationship(
        "RecordingVersion",
        foreign_keys="RecordingVersion.recording_id",
        cascade="all, delete-orphan",
        back_populates="recording",
    )
    files = relationship(
        "DatasetFile",
        foreign_keys="DatasetFile.recording_id",
        back_populates="recording",
        passive_deletes=True,
    )


class RecordingVersion(Base):
    """采集记录的某次上传 / 重传版本。
    原 `DatasetUpload` 类合并到此（A 重构 2026-06-04）。"""

    __tablename__ = "recording_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    recording_id = Column(UUID(as_uuid=True), ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False)
    version_seq = Column(Integer, nullable=False)
    source_dir = Column(String(512), nullable=False)
    source_main_file = Column(String(512), nullable=False)
    source_files = Column(JSONB, nullable=False, default=list)
    source_format = Column(String(16), nullable=False)
    fif_dir = Column(String(512))
    fif_path = Column(String(512))
    sidecar_paths = Column(JSONB, nullable=False, default=dict)
    file_size = Column(BigInteger)
    checksum = Column(String(64))
    status = Column(String(16), nullable=False, default="current")
    qa_status = Column(String(16), nullable=False, default="converted")
    note = Column(Text)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    recording = relationship("Recording", foreign_keys=[recording_id], back_populates="versions")
    uploaded_by_user = relationship("User", foreign_keys=[uploaded_by])
    files = relationship(
        "DatasetFile",
        foreign_keys="DatasetFile.recording_version_id",
        back_populates="recording_version",
        passive_deletes=True,
    )


class DatasetFile(Base):
    __tablename__ = "dataset_files"
    __table_args__ = (
        Index("idx_dataset_files_study_role", "study_id", "file_role"),
        Index("idx_dataset_files_recording_role", "recording_id", "file_role"),
        Index("idx_dataset_files_recording_version", "recording_version_id"),
        Index("idx_dataset_files_version_role", "dataset_version_id", "file_role"),
        Index("idx_dataset_files_logical_path", "dataset_version_id", "logical_path"),
        Index("idx_dataset_files_source_file", "source_file_id"),
        Index("idx_dataset_files_sha256", "sha256"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    study_id = Column(String(12), ForeignKey("studies.id", ondelete="CASCADE"), nullable=False)
    recording_id = Column(UUID(as_uuid=True), ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False)
    recording_version_id = Column(UUID(as_uuid=True), ForeignKey("recording_versions.id", ondelete="CASCADE"), nullable=False)
    dataset_version_id = Column(UUID(as_uuid=True), ForeignKey("dataset_versions.id", ondelete="SET NULL"))
    file_role = Column(String(64), nullable=False)
    storage_uri = Column(String(1024), nullable=False)
    relative_path = Column(String(512), nullable=False)
    logical_path = Column(String(1024))
    source_file_id = Column(UUID(as_uuid=True), ForeignKey("dataset_files.id", ondelete="SET NULL"))
    file_size = Column(BigInteger)
    sha256 = Column(String(64))
    mime_type = Column(String(128))
    metadata_json = Column(JSONB, nullable=False, default=dict)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    study = relationship("Study", foreign_keys=[study_id], back_populates="dataset_files")
    recording = relationship("Recording", foreign_keys=[recording_id], back_populates="files")
    recording_version = relationship("RecordingVersion", foreign_keys=[recording_version_id], back_populates="files")
    dataset_version = relationship("DatasetVersion", foreign_keys=[dataset_version_id], back_populates="files")
    source_file = relationship(
        "DatasetFile",
        remote_side=[id],
        foreign_keys=[source_file_id],
        back_populates="derived_files",
    )
    derived_files = relationship(
        "DatasetFile",
        foreign_keys="DatasetFile.source_file_id",
        back_populates="source_file",
    )
    source_derivations = relationship(
        "DatasetFileDerivation",
        foreign_keys="DatasetFileDerivation.source_file_id",
        back_populates="source_file",
        passive_deletes=True,
    )
    derived_derivations = relationship(
        "DatasetFileDerivation",
        foreign_keys="DatasetFileDerivation.derived_file_id",
        back_populates="derived_file",
        passive_deletes=True,
    )
    created_by_user = relationship("User", foreign_keys=[created_by])


class PipelineDefinition(Base):
    __tablename__ = "pipeline_definitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    study_id = Column(String(12), ForeignKey("studies.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    definition_json = Column(JSONB, nullable=False)
    node_count = Column(Integer, nullable=False, default=0)
    version = Column(Integer, nullable=False, default=1)
    is_template = Column(Boolean, nullable=False, default=False)
    status = Column(String(16), nullable=False, default="active")
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    study = relationship("Study", foreign_keys=[study_id], back_populates="pipelines")
    created_by_user = relationship("User", foreign_keys=[created_by])


class PipelineExecution(Base):
    __tablename__ = "pipeline_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    study_id = Column(String(12), ForeignKey("studies.id", ondelete="CASCADE"), nullable=False)
    pipeline_id = Column(Integer, ForeignKey("pipeline_definitions.id", ondelete="CASCADE"), nullable=False)
    pipeline_version = Column(Integer, nullable=False)
    execution_seq = Column(Integer, nullable=False)
    trigger = Column(String(32), nullable=False, default="manual")
    status = Column(String(32), nullable=False, default="running")
    node_count = Column(Integer, nullable=False, default=0)
    dataset_count = Column(Integer, nullable=False, default=0)
    definition_snapshot = Column(JSONB, nullable=False, default=dict)
    manifest_json = Column(JSONB, nullable=False, default=dict)
    execution_mode = Column(String(32), nullable=False, default="analysis")
    result_json = Column(JSONB, nullable=False, default=dict)
    error_json = Column(JSONB, nullable=False, default=dict)
    started_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime)

    study = relationship("Study", foreign_keys=[study_id])
    pipeline = relationship("PipelineDefinition", foreign_keys=[pipeline_id])
    started_by_user = relationship("User", foreign_keys=[started_by])
    jobs = relationship("PipelineJob", cascade="all, delete-orphan", back_populates="execution")
    study_outputs = relationship(
        "StudyOutput",
        cascade="all, delete-orphan",
        back_populates="execution",
        foreign_keys="StudyOutput.produced_by_execution_id",
    )
    inputs = relationship(
        "PipelineExecutionInput",
        cascade="all, delete-orphan",
        back_populates="execution",
        foreign_keys="PipelineExecutionInput.execution_id",
    )
    dependencies = relationship(
        "PipelineExecutionDependency",
        cascade="all, delete-orphan",
        back_populates="execution",
        foreign_keys="PipelineExecutionDependency.execution_id",
    )
    downstream_dependencies = relationship(
        "PipelineExecutionDependency",
        back_populates="depends_on_execution",
        foreign_keys="PipelineExecutionDependency.depends_on_execution_id",
        passive_deletes=True,
    )


class PipelineJob(Base):
    __tablename__ = "pipeline_jobs"
    __table_args__ = (
        Index("idx_pipeline_jobs_execution_topo", "execution_id", "topo_index"),
        Index("idx_pipeline_jobs_study_status", "study_id", "status"),
        Index("idx_pipeline_jobs_study_hash", "study_id", "node_hash"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    execution_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_executions.id", ondelete="CASCADE"), nullable=False)
    study_id = Column(String(12), ForeignKey("studies.id", ondelete="CASCADE"), nullable=False)
    pipeline_id = Column(Integer, ForeignKey("pipeline_definitions.id", ondelete="CASCADE"), nullable=False)
    node_id = Column(String(128), nullable=False)
    node_type = Column(String(128), nullable=False)
    node_title = Column(String(200))
    status = Column(String(32), nullable=False, default="pending")
    topo_index = Column(Integer, nullable=False, default=0)
    params_json = Column(JSONB, nullable=False, default=dict)
    input_json = Column(JSONB, nullable=False, default=dict)
    output_json = Column(JSONB, nullable=False, default=dict)
    input_hash = Column(String(128))
    params_hash = Column(String(128))
    node_hash = Column(String(128))
    trace_code = Column(String(256))
    error_json = Column(JSONB, nullable=False, default=dict)
    log_tail = Column(Text)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    duration_ms = Column(Integer)

    execution = relationship("PipelineExecution", foreign_keys=[execution_id], back_populates="jobs")
    study = relationship("Study", foreign_keys=[study_id])
    pipeline = relationship("PipelineDefinition", foreign_keys=[pipeline_id])
    study_outputs = relationship(
        "StudyOutput",
        back_populates="job",
        foreign_keys="StudyOutput.produced_by_job_id",
    )


class DatasetFileDerivation(Base):
    __tablename__ = "dataset_file_derivations"
    __table_args__ = (
        Index("idx_dataset_file_derivations_source", "source_file_id"),
        Index("idx_dataset_file_derivations_derived", "derived_file_id"),
        Index("idx_dataset_file_derivations_run", "execution_id"),
        Index("idx_dataset_file_derivations_study_output", "study_output_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    study_id = Column(String(12), ForeignKey("studies.id", ondelete="CASCADE"), nullable=False)
    source_file_id = Column(UUID(as_uuid=True), ForeignKey("dataset_files.id", ondelete="RESTRICT"), nullable=False)
    derived_file_id = Column(UUID(as_uuid=True), ForeignKey("dataset_files.id", ondelete="CASCADE"), nullable=False)
    execution_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_executions.id", ondelete="SET NULL"))
    study_output_id = Column(UUID(as_uuid=True), ForeignKey("study_outputs.id", ondelete="SET NULL"))
    derivation_kind = Column(String(64), nullable=False, default="canonical_fif")
    transform_name = Column(String(128))
    transform_version = Column(String(64))
    parameters_json = Column(JSONB, nullable=False, default=dict)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    study = relationship("Study", foreign_keys=[study_id])
    source_file = relationship(
        "DatasetFile",
        foreign_keys=[source_file_id],
        back_populates="source_derivations",
    )
    derived_file = relationship(
        "DatasetFile",
        foreign_keys=[derived_file_id],
        back_populates="derived_derivations",
    )
    execution = relationship("PipelineExecution", foreign_keys=[execution_id])
    study_output = relationship("StudyOutput", foreign_keys=[study_output_id])


class PipelineExecutionInput(Base):
    __tablename__ = "pipeline_execution_inputs"
    __table_args__ = (
        Index("idx_pipeline_execution_inputs_run", "execution_id"),
        Index("idx_pipeline_execution_inputs_run_node", "execution_id", "node_id", "input_index"),
        Index("idx_pipeline_execution_inputs_study_pipeline", "study_id", "pipeline_id"),
        Index("idx_pipeline_execution_inputs_dataset_asset", "dataset_asset_id"),
        Index("idx_pipeline_execution_inputs_recording", "recording_id"),
        Index("idx_pipeline_execution_inputs_dataset_file", "dataset_file_id"),
        Index("idx_pipeline_execution_inputs_storage_uri", "storage_uri"),
        Index("idx_pipeline_execution_inputs_upstream_dataset", "upstream_dataset_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    execution_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_executions.id", ondelete="CASCADE"), nullable=False)
    study_id = Column(String(12), ForeignKey("studies.id", ondelete="CASCADE"), nullable=False)
    pipeline_id = Column(Integer, ForeignKey("pipeline_definitions.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_jobs.id", ondelete="SET NULL"))
    node_id = Column(String(128))
    node_type = Column(String(128))
    input_slot = Column(String(128), nullable=False)
    input_index = Column(Integer, nullable=False, default=0)
    input_kind = Column(String(32), nullable=False)
    dataset_asset_id = Column(UUID(as_uuid=True), ForeignKey("dataset_assets.id", ondelete="SET NULL"))
    recording_id = Column(UUID(as_uuid=True), ForeignKey("recordings.id", ondelete="SET NULL"))
    recording_version_id = Column(UUID(as_uuid=True), ForeignKey("recording_versions.id", ondelete="SET NULL"))
    dataset_file_id = Column(UUID(as_uuid=True), ForeignKey("dataset_files.id", ondelete="SET NULL"))
    file_role = Column(String(64))
    storage_uri = Column(String(1024))
    logical_path = Column(String(1024))
    upstream_execution_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_executions.id", ondelete="SET NULL"))
    upstream_dataset_id = Column(UUID(as_uuid=True), ForeignKey("study_outputs.id", ondelete="SET NULL"))
    selector_json = Column(JSONB, nullable=False, default=dict)
    resolved_metadata_json = Column(JSONB, nullable=False, default=dict)
    sha256 = Column(String(128))
    created_at = Column(DateTime, default=datetime.utcnow)

    execution = relationship("PipelineExecution", foreign_keys=[execution_id], back_populates="inputs")
    study = relationship("Study", foreign_keys=[study_id])
    pipeline = relationship("PipelineDefinition", foreign_keys=[pipeline_id])
    job = relationship("PipelineJob", foreign_keys=[job_id])
    dataset_asset = relationship("DatasetAsset", foreign_keys=[dataset_asset_id])
    recording = relationship("Recording", foreign_keys=[recording_id])
    recording_version = relationship("RecordingVersion", foreign_keys=[recording_version_id])
    dataset_file = relationship("DatasetFile", foreign_keys=[dataset_file_id])
    upstream_execution = relationship("PipelineExecution", foreign_keys=[upstream_execution_id])
    upstream_study_output = relationship("StudyOutput", foreign_keys=[upstream_dataset_id])


class PipelineExecutionDependency(Base):
    __tablename__ = "pipeline_execution_dependencies"
    __table_args__ = (
        Index("idx_pipeline_execution_dependencies_run", "execution_id"),
        Index("idx_pipeline_execution_dependencies_upstream_execution", "depends_on_execution_id"),
        Index("idx_pipeline_execution_dependencies_upstream_dataset", "upstream_dataset_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    study_id = Column(String(12), ForeignKey("studies.id", ondelete="CASCADE"), nullable=False)
    execution_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_executions.id", ondelete="CASCADE"), nullable=False)
    depends_on_execution_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_executions.id", ondelete="RESTRICT"), nullable=False)
    upstream_dataset_id = Column(UUID(as_uuid=True), ForeignKey("study_outputs.id", ondelete="RESTRICT"))
    dependency_kind = Column(String(64), nullable=False, default="upstream_execution")
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    study = relationship("Study", foreign_keys=[study_id])
    execution = relationship("PipelineExecution", foreign_keys=[execution_id], back_populates="dependencies")
    depends_on_execution = relationship(
        "PipelineExecution",
        foreign_keys=[depends_on_execution_id],
        back_populates="downstream_dependencies",
    )
    upstream_study_output = relationship("StudyOutput", foreign_keys=[upstream_dataset_id])


class AsyncTask(Base):
    __tablename__ = "async_tasks"
    __table_args__ = (
        Index(
            "uq_async_tasks_celery_task_id",
            "celery_task_id",
            unique=True,
            postgresql_where=text("celery_task_id IS NOT NULL"),
        ),
        Index("idx_async_tasks_resource", "resource_kind", "resource_id"),
        Index("idx_async_tasks_study_status", "study_id", "status"),
        Index("idx_async_tasks_status_created", "status", "created_at"),
        Index("idx_async_tasks_created_by", "created_by"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    celery_task_id = Column(String(128))
    task_type = Column(String(64), nullable=False)
    queue_name = Column(String(128))
    status = Column(String(32), nullable=False, default="queued")
    progress = Column(Numeric(5, 2), nullable=False, default=0)
    study_id = Column(String(12), ForeignKey("studies.id", ondelete="SET NULL"))
    resource_kind = Column(String(64), nullable=False)
    resource_id = Column(UUID(as_uuid=True))
    payload_json = Column(JSONB, nullable=False, default=dict)
    result_json = Column(JSONB, nullable=False, default=dict)
    error_json = Column(JSONB, nullable=False, default=dict)
    idempotency_key = Column(String(128))
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    attempt = Column(Integer, nullable=False, default=1)
    max_attempts = Column(Integer, nullable=False, default=1)

    study = relationship("Study", foreign_keys=[study_id], back_populates="async_tasks")
    created_by_user = relationship("User", foreign_keys=[created_by])
    events = relationship(
        "TaskEvent",
        cascade="all, delete-orphan",
        back_populates="task",
        order_by="TaskEvent.created_at",
    )


class TaskEvent(Base):
    __tablename__ = "task_events"
    __table_args__ = (
        Index("idx_task_events_task_created", "task_id", "created_at"),
        Index("idx_task_events_status", "status"),
        Index("idx_task_events_type", "event_type"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    task_id = Column(UUID(as_uuid=True), ForeignKey("async_tasks.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(64), nullable=False)
    status = Column(String(32))
    progress = Column(Numeric(5, 2))
    message = Column(Text)
    payload_json = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("AsyncTask", foreign_keys=[task_id], back_populates="events")


# ============================================
# Phase 1 (docs_v2/3-25) 数据集生命周期相关表
# ============================================


class DatasetVersionReference(Base):
    """版本引用追踪表 (DEC-2026-0531-A).

    mount / execution_input 写入时自动登记, 撤回时遍历通知引用方.
    """

    __tablename__ = "dataset_version_references"
    __table_args__ = (
        Index("idx_dataset_version_references_version", "dataset_version_id"),
        Index("idx_dataset_version_references_referencing_study", "referencing_study_id"),
        Index("idx_dataset_version_references_kind_id", "reference_kind", "reference_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    dataset_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dataset_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    reference_kind = Column(String(32), nullable=False)  # mount / execution_input / external_paper
    reference_id = Column(UUID(as_uuid=True), nullable=False)
    referencing_study_id = Column(String(12), ForeignKey("studies.id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    dataset_version = relationship("DatasetVersion", foreign_keys=[dataset_version_id])
    referencing_study = relationship("Study", foreign_keys=[referencing_study_id])


class DatasetWithdrawalRequest(Base):
    """撤回申请审计表 (DEC-2026-0531-A / D).

    decision = 'emergency' 表示超级管理员紧急下架, 事后补录.
    """

    __tablename__ = "dataset_withdrawal_requests"
    __table_args__ = (
        Index("idx_dataset_withdrawal_requests_version", "dataset_version_id"),
        Index(
            "idx_dataset_withdrawal_requests_pending",
            "requested_at",
            postgresql_where=text("decision IS NULL"),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    dataset_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dataset_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    requested_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reason = Column(Text, nullable=False)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at = Column(DateTime)
    decision = Column(String(16))  # approved / rejected / emergency
    admin_notes = Column(Text)
    notification_sent_at = Column(DateTime)

    dataset_version = relationship("DatasetVersion", foreign_keys=[dataset_version_id])
    requested_by_user = relationship("User", foreign_keys=[requested_by])
    reviewed_by_user = relationship("User", foreign_keys=[reviewed_by])
