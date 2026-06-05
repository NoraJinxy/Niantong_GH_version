-- Purpose: 派生数据集与 Pipeline I/O — 由 Pipeline 节点产出的数据、文件派生关系、Run 输入快照与依赖。
-- Related: backend/app/models/derived_dataset.py, backend/app/models/study.py 中的
--          DatasetFileDerivation / PipelineExecutionInput / PipelineExecutionDependency。
-- Notes: 依赖 03_datasets.sql (recordings/recording_versions/dataset_files) 和 04_pipelines.sql (pipeline_executions/jobs)。
--        本文件中 derived_datasets 必须先创建，再创建 dataset_file_derivations / pipeline_execution_inputs /
--        pipeline_execution_dependencies 等引用 derived_datasets 的表。

-- ============================================
-- 派生数据集（取代旧的 pipeline_artifacts + analysis_results）
-- ============================================

CREATE TABLE IF NOT EXISTS derived_datasets (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id               CHAR(12) NOT NULL REFERENCES studies(id) ON DELETE CASCADE,

    -- 来源追溯
    produced_by_execution_id       UUID REFERENCES pipeline_executions(id) ON DELETE CASCADE,
    produced_by_job_id  UUID REFERENCES pipeline_jobs(id) ON DELETE SET NULL,
    produced_by_node_id      VARCHAR(128),
    produced_by_node_type    VARCHAR(128),
    produced_by_params       JSONB NOT NULL DEFAULT '{}',
    upstream_dataset_ids     JSONB NOT NULL DEFAULT '[]',
    upstream_recording_ids   JSONB NOT NULL DEFAULT '[]',

    -- 数据语义
    data_type                VARCHAR(64) NOT NULL,
    subject_id               UUID REFERENCES subjects(id) ON DELETE SET NULL,
    bids_subject_id          VARCHAR(64),
    session                  VARCHAR(64),
    task                     VARCHAR(64),
    run_label                VARCHAR(64),
    condition                VARCHAR(128),

    -- 用户层面
    display_name             VARCHAR(256),
    description              TEXT,
    tags                     JSONB NOT NULL DEFAULT '[]',

    -- 物理存储
    storage_uri              VARCHAR(1024) NOT NULL,
    logical_path             VARCHAR(1024),
    file_role                VARCHAR(64),
    file_size                BIGINT,
    sha256                   VARCHAR(64),
    mime_type                VARCHAR(128),

    -- 生命周期
    retention_status         VARCHAR(32) NOT NULL DEFAULT 'current'
                             CHECK (retention_status IN (
                                'current', 'pinned', 'cached',
                                'temporary', 'deleted', 'quarantined'
                             )),
    retention_expires_at     TIMESTAMP,

    -- Phase 1 (3-25): 派生数据集生命周期。继承 upstream 状态：
    --   upstream draft        → lifecycle_state=draft，跨 Study 不可见
    --   upstream published    → 主 Study owner 可手动升级到 published，跨 Study 可见
    --   upstream withdrawn    → 联动 withdrawn，新引用禁止但旧引用保留
    lifecycle_state          VARCHAR(32) NOT NULL DEFAULT 'draft'
                             CHECK (lifecycle_state IN ('draft', 'published', 'withdrawn')),
    visibility               VARCHAR(32) NOT NULL DEFAULT 'private'
                             CHECK (visibility IN ('private', 'shared')),

    -- 预览索引
    preview_json             JSONB NOT NULL DEFAULT '{}',

    -- 元数据
    created_at               TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by               UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_at               TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at               TIMESTAMP
);

COMMENT ON TABLE derived_datasets IS
    '派生数据集表。Pipeline 各节点产出的文件统一登记于此，取代旧的 pipeline_artifacts + analysis_results。'
    '用户视角通过 display_name + tags 命名分类；retention_status 控制生命周期。';

-- ============================================
-- 数据集文件派生关系
-- ============================================

CREATE TABLE IF NOT EXISTS dataset_file_derivations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id          CHAR(12) NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    source_file_id      UUID NOT NULL REFERENCES dataset_files(id) ON DELETE RESTRICT,
    derived_file_id     UUID NOT NULL REFERENCES dataset_files(id) ON DELETE CASCADE,
    execution_id              UUID REFERENCES pipeline_executions(id) ON DELETE SET NULL,
    derived_dataset_id  UUID REFERENCES derived_datasets(id) ON DELETE SET NULL,
    derivation_kind     VARCHAR(64) NOT NULL DEFAULT 'canonical_fif',
    transform_name      VARCHAR(128),
    transform_version   VARCHAR(64),
    parameters_json     JSONB NOT NULL DEFAULT '{}',
    metadata            JSONB NOT NULL DEFAULT '{}',
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    CHECK (source_file_id <> derived_file_id)
);

COMMENT ON TABLE dataset_file_derivations IS 'Dataset 文件派生关系表。用于记录 raw source 到 canonical FIF、后续派生文件之间的来源关系。';
COMMENT ON COLUMN dataset_file_derivations.derivation_kind IS '派生类型，例如 canonical_fif、raw_bids_view、preprocessed_derivative。';

-- ============================================
-- Pipeline Run 输入快照
-- ============================================

CREATE TABLE IF NOT EXISTS pipeline_execution_inputs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id              UUID NOT NULL REFERENCES pipeline_executions(id) ON DELETE CASCADE,
    study_id          CHAR(12) NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    pipeline_id         INTEGER NOT NULL REFERENCES pipeline_definitions(id) ON DELETE CASCADE,
    job_id         UUID REFERENCES pipeline_jobs(id) ON DELETE SET NULL,
    node_id             VARCHAR(128),
    node_type           VARCHAR(128),
    input_slot          VARCHAR(128) NOT NULL,
    input_index         INTEGER NOT NULL DEFAULT 0,
    input_kind          VARCHAR(32) NOT NULL,
    dataset_asset_id    UUID REFERENCES dataset_assets(id) ON DELETE SET NULL,
    recording_id            UUID REFERENCES recordings(id) ON DELETE SET NULL,
    recording_version_id    UUID REFERENCES recording_versions(id) ON DELETE SET NULL,
    dataset_file_id     UUID REFERENCES dataset_files(id) ON DELETE SET NULL,
    file_role           VARCHAR(64),
    storage_uri         VARCHAR(1024),
    logical_path        VARCHAR(1024),
    upstream_execution_id     UUID REFERENCES pipeline_executions(id) ON DELETE SET NULL,
    upstream_dataset_id UUID REFERENCES derived_datasets(id) ON DELETE SET NULL,
    selector_json       JSONB NOT NULL DEFAULT '{}',
    resolved_metadata_json JSONB NOT NULL DEFAULT '{}',
    sha256              VARCHAR(128),
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE pipeline_execution_inputs IS 'Pipeline Run 输入快照表。Run 创建时冻结 LoadData 解析出的实际数据、上传版本和文件索引，后续执行优先使用本表而不是重新读取当前数据选择器。';
COMMENT ON COLUMN pipeline_execution_inputs.input_kind IS '输入类型。MVP 使用 selector、dataset_file、dataset；后续可扩展 upstream_dataset。';
COMMENT ON COLUMN pipeline_execution_inputs.file_role IS 'Run 创建时冻结的 dataset_files.file_role，例如 canonical_fif。';
COMMENT ON COLUMN pipeline_execution_inputs.storage_uri IS 'Run 创建时冻结的文件 storage_uri，不能依赖后续 dataset_files 当前值。';
COMMENT ON COLUMN pipeline_execution_inputs.logical_path IS 'Run 创建时冻结的 Dataset/Study 逻辑路径，用于历史追溯和文件选择器展示。';
COMMENT ON COLUMN pipeline_execution_inputs.selector_json IS 'LoadData 当时的选择器和参数快照。';
COMMENT ON COLUMN pipeline_execution_inputs.resolved_metadata_json IS 'LoadData 当时解析出的数据元数据快照。';

-- ============================================
-- Pipeline Run 依赖关系（跨 Run 的派生链）
-- ============================================

CREATE TABLE IF NOT EXISTS pipeline_execution_dependencies (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id           CHAR(12) NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    execution_id               UUID NOT NULL REFERENCES pipeline_executions(id) ON DELETE CASCADE,
    depends_on_execution_id    UUID NOT NULL REFERENCES pipeline_executions(id) ON DELETE RESTRICT,
    upstream_dataset_id  UUID REFERENCES derived_datasets(id) ON DELETE RESTRICT,
    dependency_kind      VARCHAR(64) NOT NULL DEFAULT 'upstream_execution',
    metadata             JSONB NOT NULL DEFAULT '{}',
    created_at           TIMESTAMP NOT NULL DEFAULT NOW(),
    CHECK (execution_id <> depends_on_execution_id)
);

-- ============================================
-- 索引
-- ============================================

CREATE INDEX IF NOT EXISTS idx_derived_study ON derived_datasets (study_id, retention_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_derived_subject_type ON derived_datasets (study_id, bids_subject_id, data_type);
CREATE INDEX IF NOT EXISTS idx_derived_execution ON derived_datasets (produced_by_execution_id);
CREATE INDEX IF NOT EXISTS idx_derived_job ON derived_datasets (produced_by_job_id);
CREATE INDEX IF NOT EXISTS idx_derived_tags ON derived_datasets USING GIN (tags);
CREATE UNIQUE INDEX IF NOT EXISTS idx_derived_sha256 ON derived_datasets (study_id, sha256) WHERE sha256 IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_derived_retention_expires ON derived_datasets (retention_expires_at) WHERE retention_expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_derived_deleted ON derived_datasets (study_id, deleted_at) WHERE deleted_at IS NOT NULL;

-- Phase 1 (3-25): 派生数据生命周期索引（支持跨 Study 列出可引用的 published 派生数据）
CREATE INDEX IF NOT EXISTS idx_derived_lifecycle ON derived_datasets (lifecycle_state);
CREATE INDEX IF NOT EXISTS idx_derived_shared_published ON derived_datasets (lifecycle_state, visibility) WHERE lifecycle_state = 'published' AND visibility = 'shared';
CREATE INDEX IF NOT EXISTS idx_dataset_file_derivations_source ON dataset_file_derivations(source_file_id);
CREATE INDEX IF NOT EXISTS idx_dataset_file_derivations_derived ON dataset_file_derivations(derived_file_id);
CREATE INDEX IF NOT EXISTS idx_dataset_file_derivations_execution ON dataset_file_derivations(execution_id);
CREATE INDEX IF NOT EXISTS idx_dataset_file_derivations_derived_dataset ON dataset_file_derivations(derived_dataset_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_execution_inputs_run ON pipeline_execution_inputs(execution_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_execution_inputs_run_node ON pipeline_execution_inputs(execution_id, node_id, input_index);
CREATE INDEX IF NOT EXISTS idx_pipeline_execution_inputs_study_pipeline ON pipeline_execution_inputs(study_id, pipeline_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_execution_inputs_dataset_asset ON pipeline_execution_inputs(dataset_asset_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_execution_inputs_recording ON pipeline_execution_inputs(recording_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_execution_inputs_dataset_file ON pipeline_execution_inputs(dataset_file_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_execution_inputs_storage_uri ON pipeline_execution_inputs(storage_uri);
CREATE INDEX IF NOT EXISTS idx_pipeline_execution_inputs_upstream_dataset ON pipeline_execution_inputs(upstream_dataset_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_execution_dependencies_run ON pipeline_execution_dependencies(execution_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_execution_dependencies_upstream_run ON pipeline_execution_dependencies(depends_on_execution_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_execution_dependencies_upstream_dataset ON pipeline_execution_dependencies(upstream_dataset_id);
