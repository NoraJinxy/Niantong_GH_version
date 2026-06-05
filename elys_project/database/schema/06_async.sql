-- Purpose: 异步任务与任务事件日志（Celery / 后台任务追踪）。
-- Related: backend/app/models/study.py 中的 AsyncTask / TaskEvent，backend/app/services/async_tasks.py。
-- Notes: 依赖 01_auth.sql (users), 02_studies.sql (studies)；最后加载，与其他模块无依赖关系。

-- ============================================
-- 异步任务主表
-- ============================================

CREATE TABLE IF NOT EXISTS async_tasks (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    celery_task_id      VARCHAR(128),
    task_type           VARCHAR(64) NOT NULL,
    queue_name          VARCHAR(128),
    status              VARCHAR(32) NOT NULL DEFAULT 'queued'
                            CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'canceled', 'retrying')),
    progress            NUMERIC(5,2) NOT NULL DEFAULT 0
                            CHECK (progress >= 0 AND progress <= 100),
    study_id          CHAR(12) REFERENCES studies(id) ON DELETE SET NULL,
    resource_kind       VARCHAR(64) NOT NULL,
    resource_id         UUID,
    payload_json        JSONB NOT NULL DEFAULT '{}',
    result_json         JSONB NOT NULL DEFAULT '{}',
    error_json          JSONB NOT NULL DEFAULT '{}',
    idempotency_key     VARCHAR(128),
    created_by          UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    started_at          TIMESTAMP,
    finished_at         TIMESTAMP,
    attempt             INTEGER NOT NULL DEFAULT 1,
    max_attempts        INTEGER NOT NULL DEFAULT 1
);

-- ============================================
-- 任务事件流（状态变更、进度、错误日志）
-- ============================================

CREATE TABLE IF NOT EXISTS task_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id             UUID NOT NULL REFERENCES async_tasks(id) ON DELETE CASCADE,
    event_type          VARCHAR(64) NOT NULL,
    status              VARCHAR(32)
                            CHECK (status IS NULL OR status IN ('queued', 'running', 'succeeded', 'failed', 'canceled', 'retrying')),
    progress            NUMERIC(5,2)
                            CHECK (progress IS NULL OR (progress >= 0 AND progress <= 100)),
    message             TEXT,
    payload_json        JSONB NOT NULL DEFAULT '{}',
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================
-- 索引
-- ============================================

CREATE UNIQUE INDEX IF NOT EXISTS uq_async_tasks_celery_task_id ON async_tasks(celery_task_id) WHERE celery_task_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_async_tasks_resource ON async_tasks(resource_kind, resource_id);
CREATE INDEX IF NOT EXISTS idx_async_tasks_study_status ON async_tasks(study_id, status);
CREATE INDEX IF NOT EXISTS idx_async_tasks_status_created ON async_tasks(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_async_tasks_created_by ON async_tasks(created_by);
CREATE INDEX IF NOT EXISTS idx_task_events_task_created ON task_events(task_id, created_at);
CREATE INDEX IF NOT EXISTS idx_task_events_status ON task_events(status);
CREATE INDEX IF NOT EXISTS idx_task_events_type ON task_events(event_type);
