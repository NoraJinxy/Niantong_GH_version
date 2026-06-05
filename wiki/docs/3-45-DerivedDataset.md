# 3-45 派生数据集（DerivedDataset）

> 本页定义 `derived_datasets` 表 —— Pipeline 各节点产出的文件统一登记的概念。

<div class="elys-meta" markdown>

定位
: 派生数据集 · 产物登记 · 生命周期管理 · 用户可命名分类的研究输出

事实源
: `database/schema/05_derived.sql` · `backend/app/models/derived_dataset.py` · `backend/app/pipeline/derived_dataset_store.py`

更新
: 2026-06-04 +08:00

</div>

## 1. 核心动机

Pipeline 跑完后产生很多文件：

```text
LoadData → Filter → Epoch → ERP → Save
sub-093 raw → filtered.fif → epochs.fif → erp.fif
```

`derived_datasets` 把所有产物用单一概念统一登记：

- **每个节点产出的文件**都登记一行
- **是否正式保留**通过 `retention_status` 字段控制
- **用户层面**有 `display_name` + `tags` 可以编辑
- **追溯**通过 `upstream_dataset_ids` + `upstream_recording_ids` 两套引用

## 2. 表结构

```sql
CREATE TABLE derived_datasets (
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

  -- 预览索引
  preview_json             JSONB NOT NULL DEFAULT '{}',

  -- 元数据
  created_at               TIMESTAMP NOT NULL DEFAULT NOW(),
  created_by               UUID REFERENCES users(id) ON DELETE SET NULL,
  updated_at               TIMESTAMP NOT NULL DEFAULT NOW(),
  deleted_at               TIMESTAMP
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

**LoadData 不写 derived_datasets 行**。所以一条派生数据的 `upstream_dataset_ids` 在"第一个处理节点"时是空数组，`upstream_recording_ids` 直接指向 `recordings.id`。详见 [4-40 §3](4-40-数据选择器与文件索引.md)。

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
| `storage_uri` | 完整 URI，如 `elys://studies/{study_id}/derived/{sha256[0:2]}/{sha256}/{filename}` |
| `logical_path` | 相对 study root 的逻辑路径 |
| `file_role` | `canonical_fif` / `metadata_json` / `directory` 等 |
| `sha256` | 内容校验值；同 `study_id + sha256` 唯一索引用于潜在去重 |

物理文件按 [DerivedDatasetStore](../../elys_project/backend/app/pipeline/derived_dataset_store.py) 的内容寻址放在 `studies/{study_id}/derived/{sha256[0:2]}/{sha256}/`。

### 3.5 生命周期

`retention_status` 六档：

| 状态 | 含义 | 默认在什么节点出现 |
|---|---|---|
| `current` | 正式结果，长期保留 | Save 节点 promote 后；NodeSpec `save_output=true` 时直接产生 |
| `pinned` | 显式固定，永不被自动清理 | 用户在 `/results` 页 / Execution 抽屉点"固定" |
| `cached` | 中间产物，可被自动清理 | Filter / ICA / Epoch / ERP 等中间节点默认输出 |
| `temporary` | 临时，按 expires 自动清理 | 试跑模式 / 调试节点 |
| `deleted` | 软删除，UI 隐藏；文件仍在磁盘 | 用户点"隐藏" |
| `quarantined` | 隔离 | 校验失败时管理员标记 |

`retention_expires_at`：临时项的过期时间；`cached` 默认值 = 创建时间 + 7 天。

清理任务（`derived_dataset_cleanup`）按 `retention_status + retention_expires_at` 决定回收：

- 跳过未过期项
- 跳过被下游 Execution 依赖的项（依靠 [execution_dependencies](../../elys_project/backend/app/services/execution_dependencies.py)）
- 把命中的项 `retention_status` 改为 `deleted` 并设 `deleted_at`
- 物理文件保留（后续 garbage collector 单独处理）

## 4. 关联表

三张表通过下列字段引用 `derived_datasets`：

| 字段 | 表 |
|---|---|
| `upstream_dataset_id` | `pipeline_execution_inputs` · FK → derived_datasets |
| `upstream_dataset_id` | `pipeline_execution_dependencies` · FK → derived_datasets |
| `derived_dataset_id` | `dataset_file_derivations` · FK → derived_datasets |

`PipelineExecution.derived_datasets` 和 `PipelineJob.derived_datasets` 两个 SQLAlchemy 关系提供 ORM 访问。

## 5. 索引

```sql
CREATE INDEX idx_derived_study           ON derived_datasets (study_id, retention_status, created_at DESC);
CREATE INDEX idx_derived_subject_type    ON derived_datasets (study_id, bids_subject_id, data_type);
CREATE INDEX idx_derived_execution       ON derived_datasets (produced_by_execution_id);
CREATE INDEX idx_derived_job             ON derived_datasets (produced_by_job_id);
CREATE INDEX idx_derived_tags            ON derived_datasets USING GIN (tags);
CREATE UNIQUE INDEX idx_derived_sha256   ON derived_datasets (study_id, sha256) WHERE sha256 IS NOT NULL;
CREATE INDEX idx_derived_retention_expires ON derived_datasets (retention_expires_at) WHERE retention_expires_at IS NOT NULL;
CREATE INDEX idx_derived_deleted         ON derived_datasets (study_id, deleted_at) WHERE deleted_at IS NOT NULL;
CREATE INDEX idx_derived_lifecycle       ON derived_datasets (lifecycle_state);
CREATE INDEX idx_derived_shared_published ON derived_datasets (lifecycle_state, visibility) WHERE lifecycle_state = 'published' AND visibility = 'shared';
```

跨 Execution 浏览的核心查询走 `idx_derived_study` + 后端按 chip 过滤其它字段。

## 6. Save 节点的角色

Save 节点不再写新文件，改为 **promote 上游 derived_dataset**：

1. 读取上游 derived_dataset
2. UPDATE：
   - `retention_status` → `current` 或 `pinned`（去掉 `retention_expires_at`）
   - `display_name` 按用户模板渲染（支持 `{subject} {task} {condition} {data_type} {index}` 占位符）
   - `tags` 默认合并模式（保留原标签 + 加新）

详见 [5-20 §6](5-20-Pipeline工作流管理.md) Save NodeSpec 段、`backend/app/pipeline/save_settings.py`（`apply_save_settings`）和 `DerivedDatasetStore.save_promotion()`。

## 7. API 总览

| 端点 | 用途 |
|---|---|
| `GET /studies/{id}/pipeline-executions/{execution_id}/derived-datasets` | 某次 Execution 的派生数据列表 |
| `GET /studies/{id}/derived-datasets` | 跨 Execution 列出（`/results` 页面用）；支持 `run_ids / node_types / data_types / bids_subject_ids / sessions / tasks / conditions / tags / retention_statuses / limit / offset` 过滤 |
| `GET /studies/{id}/derived-datasets/{id}` | 单条详情 |
| `PATCH /studies/{id}/derived-datasets/{id}` | 统一修改 display_name / description / tags / retention_status |
| `POST /studies/{id}/derived-datasets/batch-update` | 批量改 |
| `POST /studies/{id}/derived-datasets/cleanup` | 异步清理任务 |
| `GET /studies/{id}/derived-datasets/{id}/preview` | 预览 |
| `GET /studies/{id}/derived-datasets/{id}/download` | 下载（display_name 作为下载文件名）|

## 8. 前端入口

- `/pipeline` 页 Execution 抽屉的"派生数据"tab —— 见当次 Execution 产出的数据
- `/results` 页面 —— 跨 Execution 浏览整个研究项的派生数据，含 chip 多维筛选 + 批量动作 + 详情抽屉（来源链可视化）。详见 [6-00 §2](6-00-前端页面总览.md)

## 9. 相关页面

- [3-30 Study 与 Pipeline 表](3-30-Study与Pipeline表.md)
- [3-40 Execution 与 DerivedDataset 追溯表](3-40-Execution与Artifact追溯表.md)
- [4-30 Study 输出与 DerivedDataset](4-30-Study输出与Artifact.md)
- [5-20 Pipeline 工作流管理](5-20-Pipeline工作流管理.md)
- [5-30 Execution 管理](5-30-Execution管理.md)
- [6-00 前端页面总览](6-00-前端页面总览.md)
