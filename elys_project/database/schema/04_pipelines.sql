-- Purpose: Pipeline 定义、执行、节点任务 — Pipeline 核心执行链路骨架。
-- Related: backend/app/models/study.py 中的 PipelineDefinition / PipelineExecution / PipelineJob。
-- Notes: 依赖 02_studies.sql (studies)；本文件不含 pipeline_execution_inputs/pipeline_execution_dependencies，
--        它们引用 study_outputs，放在 05_outputs.sql 加载完后再创建。

-- ============================================
-- Pipeline 定义
-- ============================================

CREATE TABLE IF NOT EXISTS pipeline_definitions (
    id              SERIAL PRIMARY KEY,
    study_id      CHAR(12) NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    definition_json JSONB NOT NULL,
    node_count      INTEGER NOT NULL DEFAULT 0,
    version         INTEGER NOT NULL DEFAULT 1,
    is_template     BOOLEAN NOT NULL DEFAULT FALSE,
    status          VARCHAR(16) NOT NULL DEFAULT 'active'
                        CHECK (status IN ('draft', 'active', 'archived', 'deleted')),
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(study_id, name)
);

-- ============================================
-- Pipeline 运行实例
-- ============================================

CREATE TABLE IF NOT EXISTS pipeline_executions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id          CHAR(12) NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    pipeline_id         INTEGER NOT NULL REFERENCES pipeline_definitions(id) ON DELETE CASCADE,
    pipeline_version    INTEGER NOT NULL,
    execution_seq             INTEGER NOT NULL,
    trigger             VARCHAR(32) NOT NULL DEFAULT 'manual',
    status              VARCHAR(32) NOT NULL DEFAULT 'running'
                            CHECK (status IN ('queued', 'running', 'waiting_user_input', 'completed', 'failed', 'canceled')),
    node_count          INTEGER NOT NULL DEFAULT 0,
    dataset_count       INTEGER NOT NULL DEFAULT 0,
    definition_snapshot JSONB NOT NULL DEFAULT '{}',
    manifest_json       JSONB NOT NULL DEFAULT '{}',
    result_json         JSONB NOT NULL DEFAULT '{}',
    error_json          JSONB NOT NULL DEFAULT '{}',
    started_by          UUID REFERENCES users(id),
    started_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    finished_at         TIMESTAMP,
    UNIQUE(study_id, pipeline_id, execution_seq)
);

COMMENT ON COLUMN pipeline_executions.manifest_json IS '执行清单（Execution Manifest）摘要快照。完整文件后续可写入 Study executions/{execution_id}/execution_manifest.json。';

-- ============================================
-- Pipeline 节点运行（每个节点一行）
-- ============================================

CREATE TABLE IF NOT EXISTS pipeline_jobs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id              UUID NOT NULL REFERENCES pipeline_executions(id) ON DELETE CASCADE,
    study_id          CHAR(12) NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    pipeline_id         INTEGER NOT NULL REFERENCES pipeline_definitions(id) ON DELETE CASCADE,
    node_id             VARCHAR(128) NOT NULL,
    node_type           VARCHAR(128) NOT NULL,
    node_title          VARCHAR(200),
    status              VARCHAR(32) NOT NULL DEFAULT 'pending',
    topo_index          INTEGER NOT NULL DEFAULT 0,
    params_json         JSONB NOT NULL DEFAULT '{}',
    input_json          JSONB NOT NULL DEFAULT '{}',
    output_json         JSONB NOT NULL DEFAULT '{}',
    input_hash          VARCHAR(128),
    params_hash         VARCHAR(128),
    node_hash           VARCHAR(128),
    trace_code          VARCHAR(256),
    error_json          JSONB NOT NULL DEFAULT '{}',
    log_tail            TEXT,
    started_at          TIMESTAMP,
    finished_at         TIMESTAMP,
    duration_ms         INTEGER
);

-- ============================================
-- 索引
-- ============================================

CREATE INDEX IF NOT EXISTS idx_pipeline_study ON pipeline_definitions(study_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_executions_pipeline ON pipeline_executions(study_id, pipeline_id, execution_seq DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_execution_topo ON pipeline_jobs(execution_id, topo_index);
CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_study_status ON pipeline_jobs(study_id, status);
CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_study_hash ON pipeline_jobs(study_id, node_hash);
