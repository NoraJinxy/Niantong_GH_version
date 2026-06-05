# init.sql 第 1 步基线审计

> 执行时间：2026-05-21  
> 执行范围：只读审计，不执行破坏式改表，不修改业务代码。  
> 目标：为后续 `init.sql` 改造建立当前 schema、ORM、router、service 依赖基线。

## 1. 审计范围

本次读取并核对了以下内容：

| 类型 | 文件或目录 | 观察重点 |
|---|---|---|
| 数据库初始化 | `elys_version1/database/init.sql` | 当前表、字段、索引、约束、兼容性 ALTER、seed 数据 |
| ORM 模型 | `elys_version1/backend/app/models/user.py`、`role.py`、`project.py` | SQLAlchemy 表映射、关系、外键、索引 |
| 启动期兼容 | `elys_version1/backend/app/services/schema_compat.py` | 当前启动时隐式建表、补字段、改约束逻辑 |
| API router | `auth.py`、`projects.py`、`datasets.py`、`pipelines.py` | 代码对旧表名、字段、路径的直接依赖 |
| Pipeline 内部服务 | `pipeline/load_data.py`、`artifacts.py`、`previews.py`、`cache.py`、`executor.py`、`background.py` 等 | Run、Artifact、LoadData 对字段和文件路径的依赖 |

结论：当前 schema 能支撑 v1 MVP 运行，但对象语义仍是“Project + 当前 datasets 工作表”的实现形态，尚未完全变成 Dataset / Study / Pipeline / Run 标准模型。后续应优先采用新增表、新增字段、新增索引的非破坏式路线。

## 2. 当前表结构基线

### 2.1 认证与权限

| 表 | 当前作用 | 关键字段 | 主要约束和索引 | 代码依赖 |
|---|---|---|---|---|
| `users` | 用户 | `id`、`username`、`password_hash`、`is_active`、`is_verified` | `id` PK，`username` UNIQUE，`idx_users_username` | `User` model、`auth.py` 登录/刷新/me |
| `roles` | 系统角色 | `id`、`code`、`name`、`is_system` | `id` PK，`code` UNIQUE | `Role` model，`init.sql` seed |
| `permissions` | 权限码 | `id`、`code`、`name` | `id` PK，`code` UNIQUE | `Permission` model，`init.sql` seed |
| `user_roles` | 用户-角色 | `user_id`、`role_id` | 复合 PK，外键 CASCADE | `User.roles`、`Role.users` |
| `role_permissions` | 角色-权限 | `role_id`、`permission_id` | 复合 PK，外键 CASCADE | `Role.permissions` |

### 2.2 Study/Project 与协作

| 表 | 当前作用 | 关键字段 | 主要约束和索引 | 代码依赖 |
|---|---|---|---|---|
| `project_id_counters` | 生成 12 位 Project ID | `yyyymm`、`last_seq` | `yyyymm` PK | `next_project_id()` |
| `projects` | 当前项目表，产品语义上应逐步解释为 Study | `id`、`code`、`name`、`status`、`owner_id`、`bids_root`、`deleted_at`、`deleted_by` | `id` PK，`code` UNIQUE，`status` CHECK，`idx_projects_owner/status/trash` | `Project` model、`projects.py`、`datasets.py`、`pipelines.py`、文件根目录 |
| `project_members` | 项目成员和权限 | `project_id`、`user_id`、`role`、`can_read`、`can_write`、`can_delete`、`can_export` | `role` CHECK，`UNIQUE(project_id,user_id)`，`idx_project_members_user` | `projects.py` 成员管理、读写权限检查 |
| `project_audit_events` | 项目审计，当前重点服务项目删除/恢复等 | `project_id`、`action`、`actor_id`、`project_snapshot`、`metadata` | 不外键到 `projects`，保留硬删除后的审计；`idx_project_audit_events_*` | `projects.py`、`datasets.py` 写少量审计 |

当前 `projects` 仍是数据库和 API 的主干对象。短期不建议直接改名为 `studies`，否则会同时破坏 ORM、router、前端路径、文件目录和外键。

### 2.3 当前数据采集与上传版本

| 表 | 当前作用 | 关键字段 | 主要约束和索引 | 代码依赖 |
|---|---|---|---|---|
| `subjects` | 被试表 | `project_id`、`bids_subject_id`、`age`、`sex`、`group` | `UNIQUE(project_id,bids_subject_id)`，`idx_subjects_project` | `Dataset.subject`、`datasets.py` 导入 |
| `datasets` | 当前名为 Dataset，但实际是单条采集记录：subject/session/task/run | `project_id`、`subject_id`、`session`、`task`、`run`、`source_path`、`fif_path`、`current_upload_id`、`checksum`、`qa_status`、`qa_report` | `uq_datasets_bids_entities`，`idx_datasets_project/subject`，`current_upload_id` FK | `Dataset` model、`datasets.py` 列表/导入/QA、`pipeline/load_data.py` |
| `dataset_uploads` | 当前 Dataset 的上传版本，实际更像 Recording Version | `dataset_id`、`upload_seq`、`source_dir`、`source_main_file`、`source_files`、`fif_dir`、`fif_path`、`sidecar_paths`、`status`、`qa_status` | `UNIQUE(dataset_id,upload_seq)`，`status` CHECK，`idx_dataset_uploads_dataset` | `DatasetUpload` model、`datasets.py` 重传/版本、`Dataset.current_upload` |

语义判断：

- 当前 `datasets` 不应该被理解为平台级 Dataset 资产，而是一个采集记录。
- 当前 `dataset_uploads` 是一个采集记录的上传/转换版本。
- 现有代码大量直接使用 `datasets.source_path`、`datasets.fif_path`、`dataset_uploads.sidecar_paths`，所以后续新增 `dataset_files` 时必须保留旧字段作为兼容事实源一段时间。

### 2.4 Pipeline / Run / Artifact

| 表 | 当前作用 | 关键字段 | 主要约束和索引 | 代码依赖 |
|---|---|---|---|---|
| `pipeline_definitions` | 工作流定义 | `project_id`、`name`、`definition_json`、`node_count`、`version`、`is_template`、`status` | `UNIQUE(project_id,name)`，`idx_pipeline_project` | `PipelineDefinition` model、`pipelines.py` CRUD |
| `pipeline_runs` | 工作流执行记录 | `project_id`、`pipeline_id`、`pipeline_version`、`run_seq`、`status`、`definition_snapshot`、`result_json`、`error_json` | `UNIQUE(project_id,pipeline_id,run_seq)`，`status` CHECK，`idx_pipeline_runs_pipeline` | `PipelineRun` model、`pipelines.py` run 创建/列表/详情、Celery task id 暂放 `result_json` |
| `pipeline_node_runs` | 节点执行记录 | `run_id`、`node_id`、`node_type`、`params_json`、`input_json`、`output_json`、`node_hash` | `idx_pipeline_node_runs_run_topo/project_status/project_hash` | `PipelineExecutor`、缓存、节点详情 |
| `pipeline_artifacts` | Run 或节点产物索引 | `project_id`、`run_id`、`node_run_id`、`source_dataset_id`、`artifact_type`、`storage_path`、`checksum`、`content_hash`、`preview_json` | `idx_pipeline_artifacts_run/node_run/project_type` | `ArtifactStore`、`previews.py`、`cache.py`、`pipelines.py` artifact 接口 |
| `dataset_derivatives` | 早期派生数据记录 | `source_dataset_id`、`pipeline_id`、`execution_seq`、`file_path` | `idx_derivatives_project` | ORM 有模型，当前不应作为 MVP Derived Dataset 主线 |
| `analysis_results` | 分析结果记录 | `dataset_id`、`pipeline_id`、`run_id`、`node_run_id`、`artifact_id`、`file_path` | `idx_results_project/run/artifact` | ORM 有模型，`schema_compat.py` 会补字段 |

当前 `pipeline_runs` 已经有 `definition_snapshot`，这对“Run 只认固定版本”有基础价值；但它没有结构化输入快照。`LoadData` 现在仍会根据当前 `datasets` 和 `fif_path` 解析数据，后续 Dataset 重传或文件清理后，旧 Run 的真实输入会变得不够清楚。

## 3. 当前索引、约束与兼容逻辑

### 3.1 关键唯一性约束

| 对象 | 约束 |
|---|---|
| 用户 | `users.username` UNIQUE |
| 角色/权限 | `roles.code`、`permissions.code` UNIQUE |
| 项目 | `projects.code` UNIQUE，`projects.id` 由 `next_project_id()` 生成 |
| 被试 | `subjects(project_id,bids_subject_id)` UNIQUE |
| 采集记录 | `uq_datasets_bids_entities`：`project_id + subject_id + session + task + run` |
| 上传版本 | `dataset_uploads(dataset_id,upload_seq)` UNIQUE |
| Pipeline 定义 | `pipeline_definitions(project_id,name)` UNIQUE |
| Run | `pipeline_runs(project_id,pipeline_id,run_seq)` UNIQUE |

### 3.2 关键状态约束

| 表 | 字段 | 当前状态集合 |
|---|---|---|
| `projects` | `status` | `active`、`archived`、`trashed` |
| `project_members` | `role` | `owner`、`editor`、`viewer` |
| `dataset_uploads` | `status` | `current`、`replaced`、`rejected`、`failed` |
| `pipeline_runs` | `status` | `queued`、`running`、`waiting_user_input`、`completed`、`failed`、`canceled`、`cancelled` |

注意：`canceled` 与 `cancelled` 同时存在，是兼容痕迹，后续可以保留兼容但在 API 层统一展示。

### 3.3 `init.sql` 内的兼容改动

当前 `init.sql` 不只是 baseline 建表，还包含多段兼容改动：

- `projects` 增加 `deleted_by`、`delete_reason`，删除旧 `purged_at`、`purged_by`。
- 把旧 `projects.status='deleted'` 改为 `trashed`。
- 重建 `projects_status_check`。
- 将旧成员角色 `pi/researcher/reviewer` 映射为 `owner/editor/viewer`。
- 给 `dataset_uploads` 补 `fif_dir`、`fif_path`、`sidecar_paths`。
- 给 `datasets` 补 `current_upload_id` 和外键。
- 给 `pipeline_definitions` 补 `version`、`is_template`、`status`。
- 末尾还包含角色、权限、测试用户 seed。

风险：`init.sql` 同时承担建库、迁移、seed，后续继续加改动会越来越难判断“新库初始化”和“旧库升级”分别做了什么。

### 3.4 `schema_compat.py` 的重复兼容逻辑

`schema_compat.py` 启动时会：

- 创建或补齐 `pipeline_runs`、`pipeline_node_runs`、`pipeline_artifacts`、`analysis_results`。
- 调整 `pipeline_runs.status` 约束。
- 补 `pipeline_definitions.version/is_template/status`。
- 补 `analysis_results.run_id/node_run_id/artifact_id/result_name`。
- 创建若干 Run、NodeRun、Artifact、Result 索引。

风险：同一 schema 演进逻辑分散在 `init.sql` 和 `schema_compat.py` 两处。短期可以继续保持幂等补丁，长期应迁入 Alembic 或显式 migration。

## 4. 当前代码依赖基线

### 4.1 Router 依赖

| Router | 当前接口职责 | 对 schema 的关键依赖 |
|---|---|---|
| `auth.py` | 登录、刷新、当前用户、登出 | `users`、`roles`、`user_roles` |
| `projects.py` | Project 列表、详情、创建、成员、回收站、恢复、永久删除 | `projects`、`project_members`、`project_audit_events`；创建固定目录；永久删除会物理删除项目目录 |
| `datasets.py` | Dataset 列表、导入、QA mock、QA review | `subjects`、`datasets`、`dataset_uploads`；直接读写 `source_path`、`fif_path`、`current_upload_id`、`sidecar_paths` |
| `pipelines.py` | Pipeline CRUD、LoadData resolve、Run、NodeRun、Artifact、交互节点 | `pipeline_definitions`、`pipeline_runs`、`pipeline_node_runs`、`pipeline_artifacts`；Celery task id 写入 `pipeline_runs.result_json` |

当前 HTTP API 大致为 38 个端点，其中 Pipeline 相关端点最多。后续改 schema 时，必须先保住这些旧接口。

### 4.2 Pipeline 内部依赖

| 模块 | 直接依赖 |
|---|---|
| `pipeline/load_data.py` | 从 `Dataset` 查询并使用 `source_path`、`fif_path`、`current_upload`、`sidecar_paths`；按当前表状态解析输入 |
| `pipeline/executor.py` | 根据 `PipelineDefinition.definition_json` 创建 `PipelineRun` 和 `PipelineNodeRun`；写 `definition_snapshot`、`node_runs` |
| `pipeline/artifacts.py` | 写 `PipelineArtifact.storage_path`、`checksum`、`content_hash`、`preview_json` |
| `pipeline/previews.py` | 通过 `storage_path` 在项目目录内解析文件并校验 checksum |
| `pipeline/cache.py` | 通过 `storage_path` 和 `content_hash` 恢复缓存产物 |
| `pipeline/background.py` | Celery 后台执行已准备好的 Run |
| `pipeline/output.py` | 把节点输出路径写入 `analysis_results.file_path` |

结论：`storage_path` 是当前 Artifact 运行链路的核心字段，后续新增 `storage_uri` 时必须双写，不能立即替换。

## 5. 可以非破坏式新增的改动

以下改动适合在第 2 到第 6 步优先落地，因为它们不要求删除或重命名旧表字段：

| 改动 | 方式 | 价值 | 注意事项 |
|---|---|---|---|
| 新增 `dataset_files` | 新表 + 索引 + ORM | 统一 raw、canonical FIF、sidecar、QC 文件索引 | 导入流程双写；保留旧 `source_path/fif_path/sidecar_paths` |
| 新增 `pipeline_run_inputs` | 新表 + 索引 + ORM | 冻结每次 Run 实际输入 | 需要在 LoadData resolve 或 `prepare_run` 阶段写入 |
| 扩展 `pipeline_artifacts` | 新字段：`storage_uri`、`sha256`、`retention_status`、`deleted_at`、`deleted_by`、`last_accessed_at` | 支持保留策略和未来对象存储 | 短期继续使用 `storage_path/checksum` |
| 新增 `async_tasks`、`task_events` | 新表 + ORM + service | 后台任务独立可查，可支持取消/重试/进度 | 保留 `result_json.celery_task_id` 兼容输出 |
| 给 `project_members` 增加 `can_run` | 新字段 | 区分编辑权限和运行权限 | 默认可按 `can_write` 回填 |
| 新增 `study_locks` | 新表 | 支持 Pipeline 编辑/运行锁 | 需要 `expires_at`，避免异常永久占用 |
| 扩展审计 | 新增通用 `audit_events` 或扩大 `project_audit_events` 使用 | 记录上传、重传、运行、固定输出、清理、权限变化 | 如果保留硬删除审计，要避免强 FK 阻断 |

## 6. 需要后续数据迁移的改动

以下改动不建议现在直接做，应该先新增兼容层，等全链路验证后再迁移：

| 目标改动 | 为什么需要迁移 | 建议路线 |
|---|---|---|
| `projects` 语义迁移为 `studies` | 当前外键、ORM、router、文件目录都依赖 `projects` | 短期产品文案叫 Study，数据库保留 `projects`；中期加兼容视图或新表迁移 |
| `datasets` 改为 `recordings` | 当前 `datasets` 名称被大量代码依赖，且表里存的是采集记录 | 先新增 `dataset_files`；再增加 `recordings_view` 或逐步改 ORM 命名 |
| `dataset_uploads` 改为 `recording_versions` | 当前重传逻辑依赖 `DatasetUpload` | 先保持表名；后续加兼容 view/model alias |
| 引入真正 Dataset 资产 | 当前没有独立 Dataset 资产表，Study 数据都在 `datasets.project_id` 下 | 后续新增 `dataset_assets`、`study_dataset_mounts`，再迁移已有项目数据 |
| 将文件路径全部迁到 `dataset_files` | 旧导入、LoadData、QA 依赖旧字段 | 先双写，再回填历史数据，最后读逻辑切换 |
| 将 Artifact 路径从 `storage_path` 换为 `storage_uri` | 当前预览、缓存、输出都使用 `storage_path` | 先新增并双写；确认后再把读取逻辑改为优先 `storage_uri` |
| 将 Celery task id 从 `result_json` 迁到 `async_tasks` | 当前 run 创建和失败派发逻辑直接写 `result_json` | 新建任务表，双写一段时间 |
| 拆分 `init.sql` 与 seed/migration | 当前 `init.sql` 夹杂迁移和测试用户 seed | 第 9 步整理 baseline、seed、兼容迁移，考虑 Alembic |

## 7. 遗留风险

| 风险 | 说明 | 建议 |
|---|---|---|
| Cascade 删除历史 | 多个表对 `projects`、`datasets`、`pipeline_runs` 使用 `ON DELETE CASCADE`，如果物理删除项目或数据，历史 Run/Artifact 可能一起消失 | MVP 可以保留，但要减少业务层物理删除；Run 产物清理应走软删除/retention |
| Run 输入不够结构化 | 目前只有 `definition_snapshot` 和节点 input/output JSON，缺少独立输入快照表 | 第 3 步优先新增 `pipeline_run_inputs` |
| 文件索引分散 | raw、FIF、sidecar 分散在多个字段，缺少统一 hash/role/status | 第 2 步新增 `dataset_files` |
| Artifact 清理没有保护 | `pipeline_artifacts` 没有 retention 状态和软删除字段 | 第 4 步新增保留策略字段 |
| 后台任务不可独立管理 | Celery task id 在 `result_json` 中，不利于查询、取消、重试 | 第 5 步新增 `async_tasks/task_events` |
| 启动期隐式改库 | `schema_compat.py` 与 `init.sql` 均会改 schema | 后续逐步迁入 Alembic 或显式 migration |
| 时间字段没有时区 | 大多使用 `TIMESTAMP`，协作平台跨时区时可能不清楚 | 后续标准化为 `TIMESTAMPTZ`，需要迁移计划 |
| 测试用户写在初始化脚本 | `init.sql` 包含固定测试账号和密码 hash | 第 9 步拆 seed，区分开发/生产初始化 |

## 8. 验证结果

本次验证属于文档和代码阅读级验证：

- 已读取 `init.sql` 中的建表、索引、约束、兼容 ALTER、seed 区块。
- 已读取 ORM model，确认主要表和字段均有 SQLAlchemy 映射。
- 已读取 `schema_compat.py`，确认其与 `init.sql` 对 Pipeline/Analysis 相关 schema 有重复兼容逻辑。
- 已检索相关 routers 和 Pipeline 内部模块，确认旧字段依赖点。
- 未执行数据库 SQL，未运行迁移，未修改业务表结构。
- 未运行后端测试；第 1 步不涉及代码行为变化。

## 9. 下一步建议

第 2 步建议先做 `dataset_files`：

1. 在 `init.sql` 新增 `dataset_files` 表和索引。
2. 在 SQLAlchemy models 中新增 `DatasetFile`。
3. 在导入流程中双写 `raw_source`、`canonical_fif`、`sidecar` 文件记录。
4. 保持旧 `datasets.source_path`、`datasets.fif_path`、`dataset_uploads.sidecar_paths` 不变。
5. 增加最小验证：导入一条数据后，旧接口仍能列出 Dataset，新表能查到文件索引。
