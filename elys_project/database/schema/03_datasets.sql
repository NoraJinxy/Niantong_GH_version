-- Purpose: 数据集资产、版本、subjects、采集记录（recordings）、上传版本、文件等数据层骨架。
-- Related: backend/app/models/study.py 中的 DatasetAsset / DatasetVersion / Subject / Recording / RecordingVersion / DatasetFile 等。
-- Notes: 依赖 01_auth.sql (users) 和 02_studies.sql (studies)；必须在 04_pipelines.sql 之前加载。

-- ============================================
-- 数据集资产（跨研究项可挂载）
-- ============================================

CREATE TABLE IF NOT EXISTS dataset_assets (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                VARCHAR(200) NOT NULL,
    code                VARCHAR(64) NOT NULL,
    description         TEXT,
    owner_id            UUID REFERENCES users(id) ON DELETE SET NULL,
    status              VARCHAR(32) NOT NULL DEFAULT 'working'
                            CHECK (status IN ('working', 'archived', 'deleted', 'quarantined')),
    -- 可见范围（用户可见徽章轴）：private 私有 / shared 共享 / public 公开。
    -- 发布≠分享：发布后可见范围保持不变，默认私有；只升不降、无降级接口（负责人显式开放，见 routers/datasets.py open-visibility）。
    -- shared = 邀请制（dataset_members 按用户授权）；public = 任意注册用户。workspace 档已废弃（6-05 B 方案）。
    visibility          VARCHAR(32) NOT NULL DEFAULT 'private'
                            CHECK (visibility IN ('private', 'shared', 'public')),
    metadata            JSONB NOT NULL DEFAULT '{}',
    -- Phase 1 (3-25): 生命周期相关字段，unpublished 时 primary_study_id 必填，published 后保留作出身记录
    primary_study_id    CHAR(12) REFERENCES studies(id) ON DELETE SET NULL,
    concept_doi         VARCHAR(256),                  -- Concept DOI，永远指向最新 published 版本（Zenodo 模式）
    current_version_id  UUID,                          -- 当前默认版本指针；外键在 dataset_versions 创建后延后添加
    created_by          UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

COMMENT ON COLUMN dataset_assets.primary_study_id IS '主 Study（DEC-2026-0531-B）。unpublished 时必填，published 后保留作出身记录。';
COMMENT ON COLUMN dataset_assets.concept_doi IS 'Concept DOI，永远指向 Asset 最新 published 版本（Zenodo 双 DOI 模式）。';
COMMENT ON COLUMN dataset_assets.current_version_id IS '当前默认展示版本，通常指向最新 published 版本。';

-- ============================================
-- 数据集版本（Working / Published / 历史快照）
-- ============================================

CREATE TABLE IF NOT EXISTS dataset_versions (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_asset_id            UUID NOT NULL REFERENCES dataset_assets(id) ON DELETE CASCADE,
    version_label               VARCHAR(64) NOT NULL DEFAULT 'working',
    -- 发布状态轴（生命周期）：unpublished → published → withdraw_requested → withdrawn。
    state                       VARCHAR(32) NOT NULL DEFAULT 'unpublished'
                                    CHECK (state IN ('unpublished', 'published', 'withdraw_requested', 'withdrawn')),
    content_hash                VARCHAR(64),                       -- 整版本 fingerprint，发布时异步计算
    version_doi                 VARCHAR(256),                      -- 该版本独有的 Version DOI
    published_at                TIMESTAMP,
    published_by                UUID REFERENCES users(id) ON DELETE SET NULL,
    qa_status                   VARCHAR(16) NOT NULL DEFAULT 'not_run'
                                    CHECK (qa_status IN ('pass', 'fail', 'not_run')),
    -- 撤回流程字段（DEC-2026-0531-A）
    withdraw_requested_at       TIMESTAMP,
    withdraw_requested_by       UUID REFERENCES users(id) ON DELETE SET NULL,
    withdraw_reason             TEXT,
    withdrawn_at                TIMESTAMP,
    withdrawn_by                UUID REFERENCES users(id) ON DELETE SET NULL,
    withdrawal_admin_notes      TEXT,
    storage_uri                 VARCHAR(1024),
    metadata                    JSONB NOT NULL DEFAULT '{}',
    created_by                  UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at                  TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(dataset_asset_id, version_label)
);

COMMENT ON TABLE dataset_versions IS 'Dataset 数据资产版本表。state 字段进入 unpublished/published/withdraw_requested/withdrawn 生命周期（详见 wiki/docs/3-25）。';
COMMENT ON COLUMN dataset_versions.version_label IS '版本标签，强制 SemVer x.y.z（DEC-2026-0531-C）。首版默认 1.0.0，允许 0.x.y 表示 pre-release。';
COMMENT ON COLUMN dataset_versions.state IS '生命周期状态：unpublished → published → withdraw_requested → withdrawn。withdrawn 是终态，要修改必须开新版本。';
COMMENT ON COLUMN dataset_versions.content_hash IS '整版本指纹，published 时异步计算（per-file SHA-256 + manifest hash）。';
COMMENT ON COLUMN dataset_versions.version_doi IS '该版本独有的 DOI（DataCite Version DOI）。';
COMMENT ON COLUMN dataset_versions.qa_status IS '展示用，不阻塞发布（DEC-2026-0531-C）。';
COMMENT ON COLUMN dataset_versions.withdraw_reason IS '撤回理由，owner 申请时填写。';
COMMENT ON COLUMN dataset_versions.withdrawal_admin_notes IS '审核管理员备注 / 紧急下架原因。紧急下架由管理员触发（2026-06-09 v2：归管理员，superadmin 另作平台治理）。';
COMMENT ON COLUMN dataset_versions.storage_uri IS '版本 FIF 根 URI（2026-06-10 新方案，不再含 versions/ 段）。working 版指向 elys://datasets/{id}/BIDSdata；发布后指向 elys://datasets/{id}/ver{label}。sourcedata 为 asset 级共享、不随版本。';

-- ============================================
-- 研究项对数据集资产的挂载
-- ============================================

CREATE TABLE IF NOT EXISTS study_dataset_mounts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id            CHAR(12) NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    dataset_asset_id    UUID NOT NULL REFERENCES dataset_assets(id) ON DELETE RESTRICT,
    -- Phase 1 (3-25): 挂载锁定到具体版本；Phase 1 nullable，Phase 3 起非空。unpublished 版本仅主 Study 可挂
    dataset_version_id  UUID REFERENCES dataset_versions(id) ON DELETE RESTRICT,
    mount_name          VARCHAR(128) NOT NULL,
    selection_json      JSONB NOT NULL DEFAULT '{}',
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    mounted_by          UUID REFERENCES users(id) ON DELETE SET NULL,
    mounted_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(study_id, mount_name)
);

COMMENT ON COLUMN study_dataset_mounts.dataset_version_id IS '挂载锁定到的具体版本。Phase 1 nullable 兼容历史 mount，Phase 3 起非空（DEC-2026-0531 Q-6 待定历史回填策略）。';

-- ============================================
-- 数据集共享授权（邀请制，按用户）
-- ============================================
-- 可见范围 = shared 时，由负责人按用户逐一授权；被授权者可读该资产、可把它关联到自己的研究项。
-- 仅 shared 档生效：private 走主研究项成员、public 对任意注册用户放行（详见 wiki/docs/3-25）。

CREATE TABLE IF NOT EXISTS dataset_members (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id            UUID NOT NULL REFERENCES dataset_assets(id) ON DELETE CASCADE,
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    granted_by          UUID REFERENCES users(id) ON DELETE SET NULL,
    granted_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(asset_id, user_id)
);

COMMENT ON TABLE dataset_members IS '数据集共享授权表（邀请制，按用户）。可见范围 shared 时由负责人授权；被授权者可读该资产、可关联到自己研究项。';
COMMENT ON COLUMN dataset_members.granted_by IS '执行授权的用户（通常为负责人）。';

-- ============================================
-- 受试者（BIDS subjects）
-- ============================================

CREATE TABLE IF NOT EXISTS subjects (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id          CHAR(12) NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    bids_subject_id     VARCHAR(32) NOT NULL,
    age                 NUMERIC(5,2),
    sex                 VARCHAR(8),
    "group"             VARCHAR(64),
    handedness          VARCHAR(8),
    extra               JSONB NOT NULL DEFAULT '{}',
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(study_id, bids_subject_id)
);

-- ============================================
-- 采集记录（BIDS recordings）—— 一条 subject/session/task/run 的 EEG 采集
-- ============================================

CREATE TABLE IF NOT EXISTS recordings (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id            CHAR(12) NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    dataset_asset_id    UUID REFERENCES dataset_assets(id) ON DELETE RESTRICT,
    subject_id          UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    session             VARCHAR(32),
    task                VARCHAR(64) NOT NULL,
    run                 VARCHAR(32),
    source_format       VARCHAR(16) NOT NULL,
    source_path         VARCHAR(512) NOT NULL,
    fif_path            VARCHAR(512),
    current_version_id  UUID,
    file_size           BIGINT,
    checksum            VARCHAR(64),
    n_channels          INTEGER,
    sfreq               REAL,
    duration_seconds    REAL,
    n_events            INTEGER,
    qa_status           VARCHAR(16) NOT NULL DEFAULT 'pending',
    qa_report           JSONB,
    imported_by         UUID REFERENCES users(id),
    imported_at         TIMESTAMP NOT NULL DEFAULT NOW()
);

COMMENT ON COLUMN recordings.source_path IS '原始上传文件路径（sourcedata/original_uploads 中）。';
COMMENT ON COLUMN recordings.fif_path IS '系统生成的 canonical FIF 工作数据路径。';
COMMENT ON COLUMN recordings.current_version_id IS '当前有效上传版本指针 → recording_versions.id。';

-- ============================================
-- 采集记录版本（多次上传 / 重传 / 转换）
-- ============================================

CREATE TABLE IF NOT EXISTS recording_versions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recording_id        UUID NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    version_seq         INTEGER NOT NULL,
    source_dir          VARCHAR(512) NOT NULL,
    source_main_file    VARCHAR(512) NOT NULL,
    source_files        JSONB NOT NULL DEFAULT '[]',
    source_format       VARCHAR(16) NOT NULL,
    fif_dir             VARCHAR(512),
    fif_path            VARCHAR(512),
    sidecar_paths       JSONB NOT NULL DEFAULT '{}',
    file_size           BIGINT,
    checksum            VARCHAR(64),
    status              VARCHAR(16) NOT NULL DEFAULT 'current'
                            CHECK (status IN ('current', 'replaced', 'rejected', 'failed')),
    qa_status           VARCHAR(16) NOT NULL DEFAULT 'converted',
    note                TEXT,
    uploaded_by         UUID REFERENCES users(id),
    uploaded_at         TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(recording_id, version_seq)
);

-- ============================================
-- 数据集文件统一索引
-- ============================================

CREATE TABLE IF NOT EXISTS dataset_files (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id                CHAR(12) NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    recording_id            UUID NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    recording_version_id    UUID NOT NULL REFERENCES recording_versions(id) ON DELETE CASCADE,
    dataset_version_id      UUID REFERENCES dataset_versions(id) ON DELETE SET NULL,
    file_role               VARCHAR(64) NOT NULL,
    storage_uri             VARCHAR(1024) NOT NULL,
    relative_path           VARCHAR(512) NOT NULL,
    logical_path            VARCHAR(1024),
    file_size               BIGINT,
    sha256                  VARCHAR(64),
    mime_type               VARCHAR(128),
    metadata_json           JSONB NOT NULL DEFAULT '{}',
    created_by              UUID REFERENCES users(id),
    created_at              TIMESTAMP NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE dataset_files IS '数据文件统一索引表。登记 Dataset Version 下的 original upload、Raw BIDS 逻辑视图、canonical FIF、sidecar 等。';
COMMENT ON COLUMN dataset_files.file_role IS '文件角色（2026-06-10 精简）。original_upload = sourcedata 原始上传；canonical FIF 及其 BIDS sidecar = fif / fif_eeg_json / fif_channels / fif_events / fif_provenance。raw_bids 视图降为纯逻辑（不落物理、不单独登记 file_role），BIDS 实体映射查 recordings 表 + original_upload 行。';
COMMENT ON COLUMN dataset_files.storage_uri IS '存储抽象 URI。数据集文件统一用 elys://datasets/{dataset_asset_id}/{logical_path}（asset 级根；logical_path 形如 sourcedata/original_uploads/... 或 BIDSdata/sub-/ses-/eeg/... 或 ver{label}/sub-/...）。由 StorageService.resolve_uri 解析。';
COMMENT ON COLUMN dataset_files.relative_path IS '相对于研究项 data_root 的 POSIX 路径。';
COMMENT ON COLUMN dataset_files.logical_path IS '相对于 Dataset Version 根或 Study 根的稳定逻辑路径。';

-- ============================================
-- 自定义电极位置文件（montage）：数据集资产级，供 Pipeline「通道定位」节点选用
-- ============================================
-- 用户上传的电极坐标文件（.elc/.sfp/.bvef/.tsv/.csv 等），跟随 dataset_asset 走（同 BIDS：电极
-- 位置本属于数据集）。一次上传，该资产被挂到的所有研究项里「通道定位」节点都可选；删资产级联清掉。
CREATE TABLE IF NOT EXISTS dataset_montages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_asset_id    UUID NOT NULL REFERENCES dataset_assets(id) ON DELETE CASCADE,
    name                VARCHAR(200) NOT NULL,
    original_filename   VARCHAR(512),
    file_format         VARCHAR(16) NOT NULL,
    storage_uri         VARCHAR(1024) NOT NULL,
    relative_path       VARCHAR(512) NOT NULL,
    n_electrodes        INTEGER,
    file_size           BIGINT,
    sha256              VARCHAR(64),
    metadata_json       JSONB NOT NULL DEFAULT '{}',
    created_by          UUID REFERENCES users(id),
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_dataset_montages_asset ON dataset_montages(dataset_asset_id);

COMMENT ON TABLE dataset_montages IS '自定义电极位置文件（montage），数据集资产级。供 Pipeline「通道定位」节点 montage=custom 时按 id 引用，执行器读 storage 后 set_montage。';
COMMENT ON COLUMN dataset_montages.relative_path IS '相对 dataset_asset 根（DATASETS_STORAGE_ROOT/{asset_id}）的 POSIX 路径，形如 montages/{id}.elc。';
COMMENT ON COLUMN dataset_montages.file_format IS '扩展名（去点小写）：elc / sfp / bvef / tsv / csv / txt / loc 等，决定 mne.read_custom_montage 解析方式。';

-- ============================================
-- 版本文件清单（version ↔ file 多对多，支持「逻辑链接」复用旧版本物理文件）
-- ============================================
-- 物理文件只存一份（dataset_files 一行，storage_uri 指向其真实所在目录：BIDSdata/ 或 ver{label}/）；
-- 「某版本包含哪些文件」由本清单表表达。发布 v+1 时：改动文件落新物理行 + 清单条目；未改动文件
-- 直接复用旧版本 dataset_file_id 的清单条目（即「逻辑链接」，无需文件系统 symlink）。
-- GC 物理清盘判定：某 dataset_file 无任何清单行引用 AND 无 pipeline_execution_inputs 冻结引用 → 可删盘。

CREATE TABLE IF NOT EXISTS dataset_version_files (
    dataset_version_id  UUID NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
    dataset_file_id     UUID NOT NULL REFERENCES dataset_files(id)    ON DELETE RESTRICT,
    added_at            TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (dataset_version_id, dataset_file_id)
);

COMMENT ON TABLE dataset_version_files IS
    '版本文件清单。version↔file 多对多：一个物理文件可被多个版本引用（未改动文件跨版本复用 = 逻辑链接）。'
    'dataset_files.dataset_version_id 表示「物理诞生于哪个版本目录」，本表表示「成员关系」。';

-- ============================================
-- 延后添加外键（避免循环依赖）
-- ============================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'recordings_current_version_id_fkey'
          AND conrelid = 'recordings'::regclass
    ) THEN
        ALTER TABLE recordings
            ADD CONSTRAINT recordings_current_version_id_fkey
            FOREIGN KEY (current_version_id)
            REFERENCES recording_versions(id)
            ON DELETE SET NULL;
    END IF;

    -- Phase 1 (3-25): dataset_assets.current_version_id → dataset_versions.id
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'dataset_assets_current_version_id_fkey'
          AND conrelid = 'dataset_assets'::regclass
    ) THEN
        ALTER TABLE dataset_assets
            ADD CONSTRAINT dataset_assets_current_version_id_fkey
            FOREIGN KEY (current_version_id)
            REFERENCES dataset_versions(id)
            ON DELETE SET NULL;
    END IF;
END;
$$;

-- ============================================
-- Phase 1 (3-25): 引用追踪表 - 撤回时遍历此表通知引用方
-- ============================================

CREATE TABLE IF NOT EXISTS dataset_version_references (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id      UUID NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
    reference_kind          VARCHAR(32) NOT NULL
                                CHECK (reference_kind IN ('mount', 'execution_input', 'external_paper')),
    reference_id            UUID NOT NULL,
    referencing_study_id    CHAR(12) REFERENCES studies(id) ON DELETE SET NULL,
    created_at              TIMESTAMP NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE dataset_version_references IS '版本引用追踪表（DEC-2026-0531-A）。mount / execution_input 写入时自动登记，撤回时遍历通知引用方。';
COMMENT ON COLUMN dataset_version_references.reference_kind IS 'mount = StudyDatasetMount；execution_input = PipelineExecutionInput；external_paper = 论文引用（Phase 4+）。';
COMMENT ON COLUMN dataset_version_references.reference_id IS '对应 mount_id / execution_id / paper_id，依 reference_kind 含义不同。';

-- ============================================
-- Phase 1 (3-25): 撤回申请审计表
-- ============================================

CREATE TABLE IF NOT EXISTS dataset_withdrawal_requests (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id      UUID NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
    requested_by            UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    requested_at            TIMESTAMP NOT NULL DEFAULT NOW(),
    reason                  TEXT NOT NULL,
    reviewed_by             UUID REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at             TIMESTAMP,
    decision                VARCHAR(16)
                                CHECK (decision IN ('approved', 'rejected', 'emergency')),
    admin_notes             TEXT,
    notification_sent_at    TIMESTAMP
);

COMMENT ON TABLE dataset_withdrawal_requests IS '撤回申请审计表（DEC-2026-0531-A / D）。decision = emergency 表示管理员紧急下架，事后补录。';
COMMENT ON COLUMN dataset_withdrawal_requests.decision IS 'approved / rejected = 管理员正常审核结果；emergency = 紧急下架补审计。';

-- ============================================
-- 转公开审核申请（shared → public 先审后开，2026-06-10 Q1 定稿）
-- ============================================
-- 发布 = 自助（即时冻结 + DOI，可见范围 private/shared，无审核）；转公开 = 先审后开：
-- shared → public 需管理员批准。批准前数据集「已发布 + 可邀请」，能私下传 DOI 链接但不进搜索/不对全网开放。
-- 调试期默认 auto-approve（无管理员策略时自动通过，decision='auto' 留痕）。镜像 dataset_withdrawal_requests。

CREATE TABLE IF NOT EXISTS dataset_publicization_requests (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id                UUID NOT NULL REFERENCES dataset_assets(id) ON DELETE CASCADE,
    requested_by            UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    requested_at            TIMESTAMP NOT NULL DEFAULT NOW(),
    reason                  TEXT,
    reviewed_by             UUID REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at             TIMESTAMP,
    decision                VARCHAR(16)
                                CHECK (decision IN ('approved', 'rejected', 'auto')),
    admin_notes             TEXT,
    notified_at             TIMESTAMP
);

COMMENT ON TABLE dataset_publicization_requests IS
    '转公开审核申请表（Q1 定稿）。asset 级（可见范围在 asset 上）。decision: approved/rejected=管理员审核；auto=调试期自动通过留痕。';
COMMENT ON COLUMN dataset_publicization_requests.decision IS 'approved / rejected = 管理员审核结果；auto = 调试期无策略时自动通过。NULL = 待审。';

-- ============================================
-- 索引
-- ============================================

CREATE UNIQUE INDEX IF NOT EXISTS uq_dataset_assets_code ON dataset_assets(code);
CREATE INDEX IF NOT EXISTS idx_dataset_assets_owner ON dataset_assets(owner_id);
CREATE INDEX IF NOT EXISTS idx_dataset_assets_visibility_status ON dataset_assets(visibility, status);
CREATE INDEX IF NOT EXISTS idx_dataset_assets_created_by ON dataset_assets(created_by);
CREATE INDEX IF NOT EXISTS idx_dataset_versions_asset ON dataset_versions(dataset_asset_id, state);
CREATE INDEX IF NOT EXISTS idx_dataset_versions_created_by ON dataset_versions(created_by);
CREATE INDEX IF NOT EXISTS idx_study_dataset_mounts_study ON study_dataset_mounts(study_id, is_active);
CREATE INDEX IF NOT EXISTS idx_study_dataset_mounts_asset ON study_dataset_mounts(dataset_asset_id);
CREATE INDEX IF NOT EXISTS idx_study_dataset_mounts_mounted_by ON study_dataset_mounts(mounted_by);
CREATE INDEX IF NOT EXISTS idx_dataset_members_asset ON dataset_members(asset_id);
CREATE INDEX IF NOT EXISTS idx_dataset_members_user ON dataset_members(user_id);
CREATE INDEX IF NOT EXISTS idx_subjects_study ON subjects(study_id);
CREATE INDEX IF NOT EXISTS idx_recordings_study ON recordings(study_id);
CREATE INDEX IF NOT EXISTS idx_recordings_subject ON recordings(subject_id);
CREATE INDEX IF NOT EXISTS idx_recordings_dataset_asset ON recordings(dataset_asset_id);
CREATE INDEX IF NOT EXISTS idx_recordings_study_asset ON recordings(study_id, dataset_asset_id);
CREATE INDEX IF NOT EXISTS idx_recording_versions_recording ON recording_versions(recording_id);
CREATE INDEX IF NOT EXISTS idx_dataset_files_study_role ON dataset_files(study_id, file_role);
CREATE INDEX IF NOT EXISTS idx_dataset_files_recording_role ON dataset_files(recording_id, file_role);
CREATE INDEX IF NOT EXISTS idx_dataset_files_recording_version ON dataset_files(recording_version_id);
CREATE INDEX IF NOT EXISTS idx_dataset_files_version_role ON dataset_files(dataset_version_id, file_role);
CREATE INDEX IF NOT EXISTS idx_dataset_files_logical_path ON dataset_files(dataset_version_id, logical_path);
CREATE INDEX IF NOT EXISTS idx_dataset_files_sha256 ON dataset_files(sha256);
CREATE UNIQUE INDEX IF NOT EXISTS uq_recordings_bids_entities
    ON recordings(study_id, subject_id, COALESCE(session, ''), task, COALESCE(run, ''));

-- Phase 1 (3-25): 生命周期相关索引
CREATE INDEX IF NOT EXISTS idx_dataset_assets_primary_study ON dataset_assets(primary_study_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_dataset_assets_concept_doi ON dataset_assets(concept_doi) WHERE concept_doi IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_dataset_versions_state ON dataset_versions(state);
CREATE INDEX IF NOT EXISTS idx_dataset_versions_published ON dataset_versions(dataset_asset_id, state, published_at DESC) WHERE state = 'published';
CREATE UNIQUE INDEX IF NOT EXISTS uq_dataset_versions_version_doi ON dataset_versions(version_doi) WHERE version_doi IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_study_dataset_mounts_version ON study_dataset_mounts(dataset_version_id);
CREATE INDEX IF NOT EXISTS idx_dataset_version_references_version ON dataset_version_references(dataset_version_id);
CREATE INDEX IF NOT EXISTS idx_dataset_version_references_referencing_study ON dataset_version_references(referencing_study_id);
CREATE INDEX IF NOT EXISTS idx_dataset_version_references_kind_id ON dataset_version_references(reference_kind, reference_id);
CREATE INDEX IF NOT EXISTS idx_dataset_withdrawal_requests_version ON dataset_withdrawal_requests(dataset_version_id);
CREATE INDEX IF NOT EXISTS idx_dataset_version_files_version ON dataset_version_files(dataset_version_id);
CREATE INDEX IF NOT EXISTS idx_dataset_version_files_file ON dataset_version_files(dataset_file_id);
CREATE INDEX IF NOT EXISTS idx_dataset_publicization_requests_asset ON dataset_publicization_requests(asset_id);
CREATE INDEX IF NOT EXISTS idx_dataset_publicization_requests_pending ON dataset_publicization_requests(asset_id) WHERE decision IS NULL;
