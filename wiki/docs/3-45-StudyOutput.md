# 3-45 输出（StudyOutput）

> 本页定义 `study_outputs` 表 —— Pipeline 各节点产出的文件统一登记的概念。

<div class="elys-meta" markdown>

定位
: 输出 · 产物登记 · 生命周期管理 · 用户可命名分类的研究输出

事实源
: `database/schema/05_outputs.sql` · `backend/app/models/study_output.py` · `backend/app/pipeline/study_output_store.py`

更新
: 2026-06-10 +08:00

</div>

## 1. 核心动机

Pipeline 跑完后产生很多文件：

```text
LoadData → Filter → Epoch → ERP → Save
sub-093 raw → filtered.fif → epochs.fif → erp.fif
```

`study_outputs` 把所有产物用单一概念统一登记：

- **每个节点产出的文件**都登记一行
- **是否保存**通过 `keep`（布尔，二元开关）控制；**是否缓存**由 `cache_eligible`（系统按算力 / 产物大小自动评分）控制
- **用户层面**有 `display_name` + `tags` 可以编辑
- **追溯**通过 `upstream_dataset_ids` + `upstream_recording_ids` 两套引用

## 2. 表结构

```sql
CREATE TABLE study_outputs (
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

  -- 保存与缓存（三层解耦：keep=用户是否保存 / cache_eligible=系统是否缓存 / deleted_at+purged_at=回收站）
  keep                     BOOLEAN NOT NULL DEFAULT false,
  cache_eligible           BOOLEAN NOT NULL DEFAULT false,
  retention_expires_at     TIMESTAMP,   -- 仅 keep=false 的缓存行 TTL

  -- 发布生命周期（输出自有轴，继承上游状态；详见 §3.6）
  lifecycle_state          VARCHAR(32) NOT NULL DEFAULT 'unpublished'
                           CHECK (lifecycle_state IN ('unpublished', 'published', 'withdrawn')),
  visibility               VARCHAR(32) NOT NULL DEFAULT 'private'
                           CHECK (visibility IN ('private', 'shared')),

  -- 预览索引
  preview_json             JSONB NOT NULL DEFAULT '{}',

  -- 元数据
  created_at               TIMESTAMP NOT NULL DEFAULT NOW(),
  created_by               UUID REFERENCES users(id) ON DELETE SET NULL,
  updated_at               TIMESTAMP NOT NULL DEFAULT NOW(),
  deleted_at               TIMESTAMP,   -- 软删 / 回收站
  purged_at                TIMESTAMP    -- GC 物理清盘磁盘文件后置位（DB 行保留可追溯）
);
```

## 3. 字段语义

### 3.1 来源追溯

| 字段 | 说明 |
|---|---|
| `produced_by_execution_id` | 由哪次 Execution 产出 |
| `produced_by_job_id` | 由哪个 Job（具体节点执行实例）产出 |
| `produced_by_node_id` | Pipeline 图中节点 id（如 `node_3`）|
| `produced_by_node_type` | NodeSpec 类型（如 `eeg/filter/butterworth`） |
| `produced_by_params` | 节点当时的参数快照 |
| `upstream_dataset_ids` | 直接上游派生 dataset id 列表（多个用于 ICA Apply 这种多输入节点） |
| `upstream_recording_ids` | 最终回溯到的原始 recording id 列表 |

**LoadData 不写 study_outputs 行**。所以一条结果的 `upstream_dataset_ids` 在"第一个处理节点"时是空数组，`upstream_recording_ids` 直接指向 `recordings.id`。详见 [4-40 §3](4-40-数据选择器与文件索引.md)。

### 3.2 数据语义

| 字段 | 说明 |
|---|---|
| `data_type` | 枚举：`raw`、`filtered_raw`、`ica_cleaned`、`ica_matrix`、`epochs`、`evoked`、`psd`、`tfr`、`connectivity`、`microstate`、`source_estimate`、`metadata`、`directory` |
| `subject_id / bids_subject_id` | 关联和显示用，与 `recordings` 表一致 |
| `session / task / run_label / condition` | BIDS 维度；`condition` 是分段后的事件条件名（如 `Stimulus/S 9`）|

### 3.3 用户层面

| 字段 | 说明 |
|---|---|
| `display_name` | 用户友好的名字，可在 `/results` 页面或 Execution 抽屉里 inline 编辑 |
| `description` | 文本备注 |
| `tags` | 用户自由标签，例如 `for-paper-1`、`控制组`、`阴性` |

`display_name` 在节点写入时自动按模板（`{data_type} {subject}`）生成，Save 节点可以基于模板二次渲染（支持 `{subject} {task} {condition} ...`）。

### 3.4 物理存储

| 字段 | 说明 |
|---|---|
| `storage_uri` | 完整 URI，如 `elys://studies/{study_id}/outputs/{sha256[0:2]}/{sha256}/{filename}` |
| `logical_path` | 相对 study root 的逻辑路径 |
| `file_role` | `canonical_fif` / `metadata_json` / `directory` 等 |
| `sha256` | 内容校验值；同 `study_id + sha256` 唯一索引用于潜在去重 |

物理文件按 `StudyOutputStore`（源码 `elys_project/backend/app/pipeline/study_output_store.py`）的内容寻址放在 `studies/{study_id}/outputs/{sha256[0:2]}/{sha256}/`。

### 3.5 生命周期

保存 / 缓存 / 回收站 **三层解耦**（取代旧的 `retention_status` 五值状态机；用户只面对「保存 / 不保存」二元，缓存全自动）：

| 维度 | 字段 | 含义 |
|---|---|---|
| **保存意图** | `keep` (bool) | 用户要不要这个产物。leaf（终）节点默认 `true`、中间节点默认 `false`，用户可在节点参数 `keep` 或结果页二元开关覆盖 |
| **系统缓存** | `cache_eligible` (bool) | 系统按 P4 存储优先评分（算力 vs 产物大小）自动判定是否值得缓存，与 `keep` 独立 |
| **回收站** | `deleted_at` / `purged_at` | `deleted_at`＝软删（文件还在、可恢复）；`purged_at`＝GC 物理清盘磁盘文件后置位（DB 行保留可追溯） |

`retention_expires_at`：仅 `keep=false` 的行有 TTL。产出时：值得缓存→7 天、不值得→立即过期。用户动作后（取消保存 / 回收站恢复）重算：缓存档 7 天、非缓存行给 7 天宽限（`USER_ACTION_GRACE_DAYS`）——保证用户刚点的「不保存 / 恢复」不会被下一轮每日 cleanup 立即软删（口径函数 `save_settings.retention_expiry_after_user_action`）。

**清理（软删，`study_output_cleanup`）**：回收 `keep=false AND retention_expires_at<now AND deleted_at IS NULL` 的项，跳过被下游 Execution 依赖的项（`execution_dependencies`，源码 `elys_project/backend/app/services/execution_dependencies.py`），命中项置 `deleted_at`（软删到回收站、文件保留）。

**GC（物理清盘，`study_output_gc`）**：删 `deleted_at` 超 30 天的磁盘文件、置 `purged_at`；content-addressed 去重——同 `sha256` 仍有活跃（未删）行引用时保留物理文件、只标本行 purged。清理 + GC 由 celery beat 每天全局跑（`run_storage_maintenance`），也可手动触发。已清盘的行**不可恢复**：PATCH 恢复（deleted=false）返回 409 `OUTPUT_PURGED`（磁盘文件已没了，恢复只会得到无文件的幽灵行），batch-update 同口径全量预检。

### 3.6 发布生命周期（`lifecycle_state` / `visibility`）

除了上面管「留不留 / 缓存 / 回收」的保留三层，输出还有一根**自己的发布轴**，用来回答「这份产出能不能被本研究项之外的人看到 / 引用」。它和数据集本体（`DatasetAsset` / `DatasetVersion`）那套发布机制是**两码事、各管各的表**：本表这两列只描述结果自己的对外可见性。

| 字段 | 取值（CHECK） | 默认 | 含义 |
|---|---|---|---|
| `lifecycle_state` | `unpublished` / `published` / `withdrawn` | `unpublished` | 输出的发布状态。`unpublished`＝仅本研究项可见；`published`＝可跨研究项被看到 / 引用；`withdrawn`＝已下架，旧引用保留、禁新引用 |
| `visibility` | `private` / `shared` | `private` | 可见范围。`private`＝仅本研究项；`shared`＝被授权的其他研究项可见。仅两档（无 `public`） |

**继承上游状态**（产出时按其直接上游结果决定初值，对应 DDL 注释）：

- 上游 `unpublished` → 本行 `lifecycle_state=unpublished`，跨研究项不可见。
- 上游 `published` → 主研究项负责人可手动把本行升到 `published`，此后跨研究项可见。
- 上游 `withdrawn` → 联动 `withdrawn`，禁止新引用、旧引用保留。

> 说明：这两列是 §5 两个索引（`idx_study_output_lifecycle`、`idx_study_output_shared_published`）的依赖列，用于快速筛「已发布且共享」的结果。输出是否要跟随数据集本体 v2 的「发布≠分享、可见范围只升不降」一并调整（如取消「已发布＋共享」自动模型、补齐公开档），属**待确认项**，本页先如实记录代码现状（详见《数据集生命周期重构_综合报告》§3 P2）。

## 4. 关联表

三张表通过下列字段引用 `study_outputs`：

| 字段 | 表 |
|---|---|
| `upstream_dataset_id` | `pipeline_execution_inputs` · FK → study_outputs |
| `upstream_dataset_id` | `pipeline_execution_dependencies` · FK → study_outputs |
| `study_output_id` | `dataset_file_derivations` · FK → study_outputs |

`PipelineExecution.study_outputs` 和 `PipelineJob.study_outputs` 两个 SQLAlchemy 关系提供 ORM 访问。

## 5. 索引

```sql
CREATE INDEX idx_study_output_study           ON study_outputs (study_id, keep, created_at DESC);
CREATE INDEX idx_study_output_subject_type    ON study_outputs (study_id, bids_subject_id, data_type);
CREATE INDEX idx_study_output_execution       ON study_outputs (produced_by_execution_id);
CREATE INDEX idx_study_output_job             ON study_outputs (produced_by_job_id);
CREATE INDEX idx_study_output_tags            ON study_outputs USING GIN (tags);
CREATE UNIQUE INDEX idx_study_output_sha256   ON study_outputs (study_id, sha256) WHERE sha256 IS NOT NULL;
CREATE INDEX idx_study_output_retention_expires ON study_outputs (retention_expires_at) WHERE retention_expires_at IS NOT NULL;
CREATE INDEX idx_study_output_deleted         ON study_outputs (study_id, deleted_at) WHERE deleted_at IS NOT NULL;
CREATE INDEX idx_study_output_purge_candidate ON study_outputs (deleted_at) WHERE deleted_at IS NOT NULL AND purged_at IS NULL;
CREATE INDEX idx_study_output_lifecycle       ON study_outputs (lifecycle_state);
CREATE INDEX idx_study_output_shared_published ON study_outputs (lifecycle_state, visibility) WHERE lifecycle_state = 'published' AND visibility = 'shared';
```

跨 Execution 浏览的核心查询走 `idx_study_output_study` + 后端按 chip 过滤其它字段。

## 6. 保存设置在派发阶段决定（Save 节点已取消）

没有独立的 Save 节点：每个处理节点的产物在派发（dispatch）阶段由 `apply_save_settings`（`backend/app/pipeline/save_settings.py`）一次性合成保存设置，随登记写入 `study_outputs` 行：

1. **名字**：用户模板 > spec 默认模板 > 兜底 `{subject}_{task}_{node_title}`，渲染 BIDS 占位符（`{subject} {task} {session} {run} {condition}` 等），同名自动加 `(2)(3)` 后缀。
2. **标签**：spec 的 `auto_tags` / `dynamic_tags` 与用户标签三路合并、保序去重。
3. **保存**：`keep` 默认按拓扑角色（leaf=true / intermediate=false），节点参数 `keep` 可覆盖；`cache_eligible` 由 P4 评分自动判定；TTL 按 keep / cache_eligible 计算（口径见 §3.5）。

产物落盘与登记走 `StudyOutputStore.save_file_from_writer` + `register`（content-addressed，同 `(study_id, sha256)` 活跃行复用不重插）。

## 7. API 总览

| 端点 | 用途 |
|---|---|
| `GET /studies/{id}/pipeline-executions/{execution_id}/outputs` | 某次 Execution 的结果列表 |
| `GET /studies/{id}/outputs` | 跨 Execution 列出（`/results` 页面用）；支持 `run_ids / node_types / data_types / bids_subject_ids / sessions / tasks / conditions / tags / keep / include_deleted / limit / offset` 过滤 |
| `GET /studies/{id}/outputs/{id}` | 单条详情 |
| `PATCH /studies/{id}/outputs/{id}` | 统一修改 display_name / description / tags / `keep`（保存）/ `deleted`（软删 / 恢复）|
| `POST /studies/{id}/outputs/batch-update` | 批量改 |
| `POST /studies/{id}/outputs/cleanup` | 异步清理任务（软删 keep=false 且已过期的）|
| `POST /studies/{id}/outputs/gc` | 异步 GC 物理清盘任务（删回收站超 30 天的磁盘文件、置 purged_at）|
| `GET /studies/{id}/outputs/{id}/preview` | 预览 |
| `GET /studies/{id}/outputs/{id}/download` | 下载（display_name 作为下载文件名）|

## 8. 前端入口

- `/pipeline` 页 Execution 抽屉的"结果"tab —— 见当次 Execution 产出的数据
- `/results` 页面 —— 跨 Execution 浏览整个研究项的结果，含 chip 多维筛选 + 批量动作 + 详情抽屉（来源链可视化）。详见 [6-00 §2](6-00-前端页面总览.md)

## 9. 相关页面

- [3-30 Study 与 Pipeline 表](3-30-Study与Pipeline表.md)
- [3-40 Execution 与 StudyOutput 追溯表](3-40-Execution与Artifact追溯表.md)
- [4-30 Study 输出与 StudyOutput](4-30-Study输出与Artifact.md)
- [5-20 Pipeline 工作流管理](5-20-Pipeline工作流管理.md)
- [5-30 Execution 管理](5-30-Execution管理.md)
- [6-00 前端页面总览](6-00-前端页面总览.md)
