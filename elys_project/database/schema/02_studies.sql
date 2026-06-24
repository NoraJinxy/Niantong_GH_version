-- Purpose: 研究项骨架表 — 研究项元数据、成员、审计事件、资源锁、研究设置。
-- Related: backend/app/models/study.py 中的 Study / StudyMember / AuditEvent / StudyLock / StudySettings 等。
-- Notes: 依赖 01_auth.sql（users 表）；本文件必须在 03+ 之前加载。
--        2026-05-24 重命名：projects → studies（核心实体改名）。

-- ============================================
-- 研究项 ID 生成（YYYYMM + 6 位序号）
-- ============================================

CREATE TABLE IF NOT EXISTS study_id_counters (
    yyyymm          CHAR(6) PRIMARY KEY,
    last_seq        INTEGER NOT NULL DEFAULT 0,
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION next_study_id()
RETURNS CHAR(12)
LANGUAGE plpgsql
AS $$
DECLARE
    v_yyyymm CHAR(6);
    v_seq INTEGER;
BEGIN
    v_yyyymm := TO_CHAR(NOW(), 'YYYYMM');

    INSERT INTO study_id_counters (yyyymm, last_seq)
    VALUES (v_yyyymm, 1)
    ON CONFLICT (yyyymm)
    DO UPDATE SET
        last_seq = study_id_counters.last_seq + 1,
        updated_at = NOW()
    RETURNING last_seq INTO v_seq;

    RETURN v_yyyymm || LPAD(v_seq::TEXT, 6, '0');
END;
$$;

-- ============================================
-- 研究项主表
-- ============================================

CREATE TABLE IF NOT EXISTS studies (
    id                  CHAR(12) PRIMARY KEY DEFAULT next_study_id(),
    code                VARCHAR(64) UNIQUE NOT NULL,
    name                VARCHAR(200) NOT NULL,
    description         TEXT,
    status              VARCHAR(16) NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'archived', 'trashed')),
    owner_id            UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    data_root           VARCHAR(512) NOT NULL,
    storage_quota_bytes BIGINT NOT NULL DEFAULT 1099511627776,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    archived_at         TIMESTAMP,
    deleted_at          TIMESTAMP,
    deleted_by          UUID REFERENCES users(id),
    delete_reason       TEXT
);

COMMENT ON TABLE studies IS '平台研究项表。id 为 12 位 Study ID: YYYYMM + 6 位当月序号, 同时作为研究项数据根目录名。';
COMMENT ON COLUMN studies.id IS '12 位研究项 ID, 例如 202605000001。';
COMMENT ON COLUMN studies.code IS '业务短码, 仅用于 UI 展示和搜索, 不参与数据路径生成。';
COMMENT ON COLUMN studies.data_root IS '研究项数据根目录, 例如 /mnt/elys_data/studies/202605000001/。';

-- ============================================
-- 通用审计事件（含研究项硬删除快照,2026-05-24 合并旧 study_audit_events）
-- ============================================

CREATE TABLE IF NOT EXISTS audit_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id        CHAR(12),
    event_scope     VARCHAR(64) NOT NULL DEFAULT 'study',
    action          VARCHAR(128) NOT NULL,
    actor_id        UUID REFERENCES users(id) ON DELETE SET NULL,
    resource_kind   VARCHAR(64),
    resource_id     VARCHAR(128),
    resource_label  VARCHAR(256),
    snapshot        JSONB NOT NULL DEFAULT '{}',
    metadata        JSONB NOT NULL DEFAULT '{}',
    occurred_at     TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================
-- 研究项成员与权限
-- ============================================

CREATE TABLE IF NOT EXISTS study_members (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id        CHAR(12) NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role            VARCHAR(32) NOT NULL DEFAULT 'viewer'
                        CHECK (role IN ('owner', 'editor', 'viewer')),
    can_read        BOOLEAN NOT NULL DEFAULT TRUE,
    can_write       BOOLEAN NOT NULL DEFAULT FALSE,
    can_delete      BOOLEAN NOT NULL DEFAULT FALSE,
    can_export      BOOLEAN NOT NULL DEFAULT FALSE,
    can_run         BOOLEAN NOT NULL DEFAULT FALSE,
    added_by        UUID REFERENCES users(id),
    added_at        TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(study_id, user_id)
);

-- ============================================
-- 资源锁（编辑锁、运行锁）
-- ============================================

CREATE TABLE IF NOT EXISTS study_locks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id        CHAR(12) NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    resource_kind   VARCHAR(64) NOT NULL,
    resource_id     VARCHAR(128) NOT NULL,
    lock_type       VARCHAR(32) NOT NULL
                        CHECK (lock_type IN ('edit', 'execution')),
    locked_by       UUID REFERENCES users(id) ON DELETE SET NULL,
    locked_at       TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMP NOT NULL,
    released_at     TIMESTAMP,
    released_by     UUID REFERENCES users(id) ON DELETE SET NULL,
    metadata        JSONB NOT NULL DEFAULT '{}'
);

-- ============================================
-- 研究设置（per-study 配置）
-- ============================================

CREATE TABLE IF NOT EXISTS study_settings (
    study_id                    CHAR(12) PRIMARY KEY REFERENCES studies(id) ON DELETE CASCADE,
    default_dataset_filter      JSONB NOT NULL DEFAULT '{"subjects":"all","sessions":"all","tasks":"all","runs":"all","qa_status":"all","require_fif":true}',
    run_policy                  JSONB NOT NULL DEFAULT '{"single_active_pipeline_run":true}',
    storage_policy              JSONB NOT NULL DEFAULT '{}',
    updated_by                  UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_at                  TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================
-- 索引
-- ============================================

CREATE INDEX IF NOT EXISTS idx_studies_owner ON studies(owner_id);
CREATE INDEX IF NOT EXISTS idx_studies_status ON studies(status) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_studies_trash ON studies(status, deleted_at) WHERE status = 'trashed';
CREATE INDEX IF NOT EXISTS idx_study_members_user ON study_members(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_study_time ON audit_events(study_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_actor_time ON audit_events(actor_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_action_time ON audit_events(action, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_resource ON audit_events(resource_kind, resource_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_study_locks_study_resource ON study_locks(study_id, resource_kind, resource_id, lock_type);
CREATE INDEX IF NOT EXISTS idx_study_locks_locked_by ON study_locks(locked_by);
CREATE INDEX IF NOT EXISTS idx_study_locks_expires ON study_locks(expires_at) WHERE released_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_study_settings_updated_by ON study_settings(updated_by);
CREATE UNIQUE INDEX IF NOT EXISTS uq_study_locks_active_resource
    ON study_locks(study_id, resource_kind, resource_id, lock_type)
    WHERE released_at IS NULL;
