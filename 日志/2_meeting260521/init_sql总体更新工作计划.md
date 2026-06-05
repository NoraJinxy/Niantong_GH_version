# init.sql 总体更新工作计划

> 本文档用于规划 `elys_version1/database/init.sql` 从当前 v1 schema 逐步演进到 Dataset / Study / Pipeline / Run 标准模型。每一步完成后，都必须回到本文档更新执行状态、实际改动、验证结果和下一步风险。

## 1. 总目标

当前 `init.sql` 能支撑 v1 运行，但存在几个核心问题：

| 问题 | 当前表现 | 目标 |
|---|---|---|
| Dataset 语义混乱 | 当前 `datasets` 实际是单条 `subject/session/task/run` 采集记录 | 引入真正的 Dataset 资产概念，把当前 `datasets` 逐步迁移为 Recording |
| 文件索引分散 | `source_path`、`fif_path`、`sidecar_paths` 分散在 `datasets` / `dataset_uploads` | 新增 `dataset_files`，统一索引 raw、canonical FIF、sidecar、QC 文件 |
| Run 追溯不完整 | `pipeline_runs` 有 `definition_snapshot`，但没有结构化输入快照 | 新增 `pipeline_run_inputs`，冻结每次执行实际输入 |
| Artifact 保留策略不足 | `pipeline_artifacts` 只有 `storage_path`、`checksum` | 增加 `storage_uri`、`sha256`、`retention_status`、`deleted_at` |
| 后台任务不可独立管理 | Celery task id 临时写在 `result_json` | 新增 `async_tasks`、`task_events` |
| Project/Study 命名过渡 | 当前表名是 `projects`，产品语义已改为 Study | 短期保留 `projects`，补注释和兼容字段；中期再迁移为 `studies` |
| init.sql 职责过重 | 建表、兼容迁移、种子数据混在一起 | 先整理分区；后续迁移到 Alembic + seed 脚本 |

## 2. 执行原则

- 优先做非破坏式改造：新增表、新增字段、新增索引，不立即删除旧字段。
- 不在第一轮直接重命名 `projects`、`datasets`、`dataset_uploads`，先用新表和兼容注释承接标准模型。
- 每一步都要同步 ORM、schema、service/router 里必要的字段，否则只改 SQL 会导致运行时不一致。
- 每一步完成后都要运行能运行的验证命令，至少包括 SQL 语法检查、后端启动相关检查或文档构建。
- 每一步完成后都要更新本文档，记录状态、实际变更、验证结果、遗留风险。

## 3. 总体阶段表

| 步骤 | 状态 | 工作目标 | 主要改动 | 验收标准 |
|---|---|---|---|---|
| 第 1 步 | 完成 | 建立 schema 改造基线和安全检查 | 梳理当前表、索引、约束；确认非破坏式迁移顺序 | 已形成 `init_sql第1步基线审计.md`，无破坏式改表 |
| 第 2 步 | 完成 | 增加 Dataset 文件统一索引 | 新增 `dataset_files`，保留旧 `source_path/fif_path` | 新导入流程会登记 raw/canonical/sidecar |
| 第 3 步 | 完成 | 增加 Run 输入快照 | 新增 `pipeline_run_inputs`，Run 创建时冻结输入 | Run 详情可返回输入快照，LoadData 执行优先读取快照 |
| 第 4 步 | 完成 | 增强 Artifact 保留和迁移字段 | 给 `pipeline_artifacts` 增加 `storage_uri/sha256/retention_status/deleted_at` | 新 Artifact 会双写 `storage_uri/sha256/retention_status`，预览可用 |
| 第 5 步 | 完成 | 增加后台任务表 | 新增 `async_tasks`、`task_events`，Celery id 不再只放 `result_json` | Pipeline Run 能关联可查询 Task |
| 第 6 步 | 完成 | 增加 Study 协作和锁能力 | 给成员补 `can_run`，新增 `study_locks`，扩展审计 | 同一 Pipeline 可限制并发编辑/运行 |
| 第 7 步 | 完成 | 引入 Dataset 资产与 Study 挂载 | 新增标准 `dataset_assets` 和 `study_dataset_mounts` | Study 可挂载 Dataset，不复制文件 |
| 第 8 步 | 完成 | 规划 Recording 语义迁移 | 新增 `recordings_view`、`recording_versions_view` 和新命名只读 API | 文档、ORM、API 语义一致，有迁移路线 |
| 第 9 步 | 完成 | 清理 init.sql 工程结构 | 已拆 baseline、兼容迁移、seed；已接入最小 Alembic 框架 | `init.sql` 变为组合入口，种子数据可独立执行 |
| 第 10 步 | 完成 | 全链路回归和文档收口 | 已完成代码级/模型级/文档级回归，真实 PostgreSQL/Celery 端到端受本机环境限制未执行 | `pytest`、`compileall`、mapper、schema 构造和 `mkdocs build` 通过 |

## 4. 分步工作计划与 Codex 提示词

### 第 1 步：建立 schema 改造基线

**工作目标**

- 读取当前 `elys_version1/database/init.sql`、`backend/app/models/`、`services/schema_compat.py`。
- 输出当前表、字段、索引、约束和代码依赖关系。
- 明确哪些改动是非破坏式，哪些需要迁移数据。
- 暂不改业务逻辑，只做基线核对和计划细化。

**具体需要改什么**

- 可新增一份临时或正式的 schema 审计说明。
- 如果发现 `init.sql` 中注释明显过时，可以只改注释，不改表结构。
- 更新本文档中第 1 步状态、实际发现、风险和下一步确认点。

**验收标准**

- 列出当前核心表：`projects`、`subjects`、`datasets`、`dataset_uploads`、`pipeline_definitions`、`pipeline_runs`、`pipeline_node_runs`、`pipeline_artifacts`。
- 列出必须优先非破坏式新增的表/字段。
- 明确当前代码哪些地方直接依赖旧字段。

**Codex 提示词**

```text
第1步：建立 init.sql 改造基线。请读取 elys_version1/database/init.sql、backend/app/models、backend/app/services/schema_compat.py 和相关 routers，整理当前表、字段、索引、约束、代码依赖关系，判断哪些改动可以非破坏式新增，哪些需要后续数据迁移。不要做破坏式改表。完成后更新 日志/2_meeting260521/init_sql总体更新工作计划.md 中第 1 步的状态、实际发现、验证结果、遗留风险和下一步建议。
```

**执行结果（2026-05-21）**

- 状态：完成。
- 新增基线文档：`日志/2_meeting260521/init_sql第1步基线审计.md`。
- 实际发现：
  - 当前 `init.sql` 共有 18 张主要表：`users`、`roles`、`permissions`、`user_roles`、`role_permissions`、`project_id_counters`、`projects`、`project_audit_events`、`project_members`、`subjects`、`datasets`、`dataset_uploads`、`pipeline_definitions`、`pipeline_runs`、`pipeline_node_runs`、`pipeline_artifacts`、`dataset_derivatives`、`analysis_results`。
  - 当前 `projects` 是数据库和 API 的主干对象，产品上可先称为 Study，但短期不应直接重命名表。
  - 当前 `datasets` 实际是单条 `subject/session/task/run` 采集记录，不是真正的平台级 Dataset 资产；`dataset_uploads` 实际是采集记录上传版本。
  - `datasets.source_path`、`datasets.fif_path`、`dataset_uploads.sidecar_paths`、`pipeline_artifacts.storage_path`、`pipeline_runs.result_json` 被 router 和 Pipeline 内部模块直接依赖，不能直接删除或替换。
  - `init.sql` 同时包含 baseline 建表、兼容迁移和 seed；`schema_compat.py` 也有启动期 schema 补丁，二者存在重复。
- 可非破坏式新增：
  - `dataset_files`。
  - `pipeline_run_inputs`。
  - `pipeline_artifacts.storage_uri/sha256/retention_status/deleted_at/deleted_by/last_accessed_at`。
  - `async_tasks`、`task_events`。
  - `project_members.can_run`。
  - `study_locks` 和更通用的审计事件。
- 需要后续迁移：
  - `projects -> studies` 的命名迁移。
  - `datasets -> recordings`、`dataset_uploads -> recording_versions` 的语义迁移。
  - 引入真正 Dataset 资产表和 Study 挂载关系。
  - 将文件事实源从分散路径字段迁移到 `dataset_files`。
  - 将 Artifact 事实源从 `storage_path/checksum` 迁移到 `storage_uri/sha256`。
  - 将 Celery task id 从 `pipeline_runs.result_json` 迁移到独立任务表。
- 验证结果：完成只读审计；未执行 SQL、未运行迁移、未做破坏式改表。第 1 步未涉及业务代码变更，因此未运行后端测试。
- 遗留风险：多处 `ON DELETE CASCADE` 可能导致历史追溯随项目或数据物理删除丢失；Run 仍缺少结构化输入快照；文件索引仍分散；`schema_compat.py` 和 `init.sql` 重复承担迁移职责。
- 下一步建议：进入第 2 步，优先新增 `dataset_files`，采用双写方式登记 raw、canonical FIF、sidecar 文件，同时保留旧字段和旧接口。

### 第 2 步：新增 dataset_files 文件统一索引

**工作目标**

- 让原始上传、canonical FIF、sidecar、QC 报告都有统一文件索引。
- 暂时保留 `datasets.source_path`、`datasets.fif_path`、`dataset_uploads.sidecar_paths`，避免破坏现有导入流程。

**具体需要改什么**

- 在 `init.sql` 新增 `dataset_files` 表。
- 建议字段：
  - `id`
  - `project_id`
  - `dataset_id`
  - `dataset_upload_id`
  - `file_role`
  - `storage_uri`
  - `relative_path`
  - `file_size`
  - `sha256`
  - `mime_type`
  - `metadata_json`
  - `created_by`
  - `created_at`
- 新增索引：
  - `(project_id, file_role)`
  - `(dataset_id, file_role)`
  - `(dataset_upload_id)`
  - `(sha256)`
- 更新 ORM model。
- 更新导入逻辑，让新导入同时写 `dataset_files`。
- 老字段继续保留为兼容字段。

**验收标准**

- 新上传数据后，至少生成 `raw_source` 和 `canonical_fif` 两类 `dataset_files` 记录。
- sidecar 文件能登记为 `sidecar_json/events_tsv/channels_tsv` 等角色。
- 旧接口仍能正常列出 datasets。

**Codex 提示词**

```text
第2步：新增 dataset_files 文件统一索引。请在 elys_version1/database/init.sql 中新增 dataset_files 表和必要索引，在 SQLAlchemy models 中增加对应模型，并在现有数据导入流程中兼容写入 raw_source、canonical_fif、sidecar 文件索引。不要删除 datasets.source_path、datasets.fif_path、dataset_uploads.sidecar_paths。完成后运行可用验证，并更新 日志/2_meeting260521/init_sql总体更新工作计划.md 中第 2 步的状态、实际改动、验证结果、遗留风险和下一步建议。
```

**执行结果（2026-05-21）**

- 状态：完成。
- 实际改动：
  - 在 `elys_version1/database/init.sql` 新增 `dataset_files` 表，字段包括 `project_id`、`dataset_id`、`dataset_upload_id`、`file_role`、`storage_uri`、`relative_path`、`file_size`、`sha256`、`mime_type`、`metadata_json`、`created_by`、`created_at`。
  - 新增索引：`idx_dataset_files_project_role`、`idx_dataset_files_dataset_role`、`idx_dataset_files_upload`、`idx_dataset_files_sha256`。
  - 在 SQLAlchemy 中新增 `DatasetFile` model，并注册到 `app.models`；新增关系使用 `passive_deletes=True`，避免影响当前项目永久删除链路。
  - 在 `schema_compat.py` 中新增 `dataset_files` 的幂等建表和索引创建，兼容已有数据库。
  - 在同步上传导入流程中，创建 `DatasetUpload` 后会同步写入：
    - `raw_source`：所有归档原始文件，metadata 中标记主文件、扩展名、上传序号和源格式。
    - `canonical_fif`：系统生成的 canonical FIF 文件。
    - `sidecar`：系统生成的 eeg/channels/events/import 等 sidecar 文件，metadata 中记录 `sidecar_key`。
  - 保留 `datasets.source_path`、`datasets.fif_path`、`dataset_uploads.sidecar_paths`，旧 API 和 LoadData 仍按原逻辑工作。
- 验证结果：
  - 已运行 `python -m compileall app`，通过。
  - 已运行 `python -c "from app.models import DatasetFile; print(DatasetFile.__tablename__)"`，输出 `dataset_files`。
  - 已运行 `python -c "from sqlalchemy.orm import configure_mappers; import app.models; configure_mappers(); print('mappers ok')"`，输出 `mappers ok`。
  - 当前本地环境没有 `psql` 命令，因此未直接执行 `init.sql` 做 PostgreSQL 语法/建表验证。
- 遗留风险：
  - 现有历史导入数据尚未回填 `dataset_files`，本步只保证新导入双写。
  - `dataset_files` 目前未新增对外 API，主要作为后端统一索引和后续选择器/追溯基础。
  - `storage_uri` 当前使用 `project://{project_id}/{relative_path}` 作为本地存储抽象，未来接入 MinIO/S3 时需要迁移或双写真实对象存储 URI。
  - LoadData 仍读取旧 `datasets.fif_path/source_path`，尚未切换为优先读取 `dataset_files`。
- 下一步建议：进入第 3 步，新增 `pipeline_run_inputs`。第 3 步应在 Run 创建或 `prepare_run` 阶段把 LoadData 解析出的实际 dataset/upload/file 信息冻结下来，并尽量引用本步新增的 `dataset_files`。

### 第 3 步：新增 pipeline_run_inputs 输入快照

**工作目标**

- 每次 Run 都能回答“实际用了哪些数据、哪个上传版本、哪个文件、当时 hash 是什么”。
- 解决 working Dataset 后续变化导致旧 Run 不可追溯的问题。

**具体需要改什么**

- 在 `init.sql` 新增 `pipeline_run_inputs` 表。
- 建议字段：
  - `id`
  - `run_id`
  - `project_id`
  - `pipeline_id`
  - `input_slot`
  - `input_kind`
  - `dataset_id`
  - `dataset_upload_id`
  - `dataset_file_id`
  - `upstream_run_id`
  - `upstream_artifact_id`
  - `selector_json`
  - `resolved_metadata_json`
  - `sha256`
  - `created_at`
- 新增索引：
  - `(run_id)`
  - `(project_id, pipeline_id)`
  - `(dataset_id)`
  - `(dataset_file_id)`
  - `(upstream_artifact_id)`
- 更新 Run 创建或 `PipelineExecutor.prepare_run()`，将 LoadData 解析结果写入该表。

**验收标准**

- 每次 Pipeline Run 创建后，可以查询到本次 Run 的输入快照。
- 后续 Dataset 重传不会改变旧 Run 的输入记录。
- Run 详情接口可考虑返回 inputs，或至少后端可查询。

**Codex 提示词**

```text
第3步：新增 pipeline_run_inputs 输入快照。请在 init.sql 中新增 pipeline_run_inputs 表、索引和外键，在 ORM 中增加模型，并在 Pipeline Run 创建或 prepare_run 阶段，把 LoadData 解析出的实际 dataset/upload/file 信息写入 pipeline_run_inputs。不要依赖“当前数据”作为历史 Run 的事实源。完成后验证一次 Run 能查到输入快照，并更新 日志/2_meeting260521/init_sql总体更新工作计划.md 中第 3 步的状态、实际改动、验证结果、遗留风险和下一步建议。
```

**执行结果（2026-05-21）**

- 状态：完成。
- 实际改动：
  - 在 `elys_version1/database/init.sql` 新增 `pipeline_run_inputs` 表，用于保存 Run 创建时的输入快照。
  - 新增字段覆盖 `run_id`、`project_id`、`pipeline_id`、`node_run_id`、`node_id`、`node_type`、`input_slot`、`input_index`、`input_kind`、`dataset_id`、`dataset_upload_id`、`dataset_file_id`、`upstream_run_id`、`upstream_artifact_id`、`selector_json`、`resolved_metadata_json`、`sha256`、`created_at`。
  - 新增索引：`idx_pipeline_run_inputs_run`、`idx_pipeline_run_inputs_run_node`、`idx_pipeline_run_inputs_project_pipeline`、`idx_pipeline_run_inputs_dataset`、`idx_pipeline_run_inputs_dataset_file`、`idx_pipeline_run_inputs_upstream_artifact`。
  - 在 SQLAlchemy 中新增 `PipelineRunInput` model，并注册到 `app.models`。
  - 在 `schema_compat.py` 中新增 `pipeline_run_inputs` 的幂等建表和索引创建。
  - 在 `PipelineExecutor.prepare_run()` 阶段解析 `eeg/data/load` 节点，写入：
    - `selector`：保存 LoadData 当时的选择器、参数、解析状态、错误和警告。
    - `dataset_file`：能匹配到 `dataset_files` 时，保存 dataset/upload/file 三层引用和文件 hash。
    - `dataset`：历史数据尚未回填 `dataset_files` 时，至少保存 dataset/upload 和当时的 resolved metadata。
  - LoadData 节点执行时优先读取 `pipeline_run_inputs` 快照；没有快照时才退回旧的当前数据解析逻辑，避免 queued Run 到 worker 执行之间数据选择漂移。
  - `GET /api/v1/projects/{project_id}/pipeline-runs/{run_id}` 的详情响应新增 `inputs` 字段，便于查询本次 Run 的输入快照。
- 验证结果：
  - 已运行 `python -m compileall app`，通过。
  - 已运行 `python -c "from sqlalchemy.orm import configure_mappers; import app.models; configure_mappers(); print('mappers ok')"`，输出 `mappers ok`。
  - 已运行 `python -c "from app.pipeline.executor import PipelineExecutor; from app.pipeline.dispatcher import NodeDispatcher; print('pipeline imports ok')"`，输出 `pipeline imports ok`。
  - 已运行 `python -c "from app.schemas.pipeline import PipelineRunDetailResponse, PipelineRunInputResponse; print('pipeline schemas ok')"`，输出 `pipeline schemas ok`。
  - 当前本地环境没有 `psql` 命令，因此未直接执行 `init.sql` 做 PostgreSQL 建表验证。
  - 当前本地 Python 环境缺少 `fastapi`，因此未能导入 `app.main` 做应用路由级启动验证。
- 遗留风险：
  - 已存在的历史 Run 没有输入快照；本步只保证新建 Run 在 `prepare_run()` 时冻结输入。
  - 历史数据如果没有 `dataset_files`，输入快照会降级为 `input_kind='dataset'`，不会有 `dataset_file_id`。
  - `pipeline_run_inputs` 目前覆盖 LoadData 真实输入；后续上游 Artifact 作为输入时，还需要补 `upstream_artifact` 写入。
  - `pipeline_run_inputs` 仍使用 `ON DELETE CASCADE` 跟随 Run 删除；产品层应避免物理删除 Run。
- 下一步建议：进入第 4 步，增强 `pipeline_artifacts` 的 `storage_uri`、`sha256`、`retention_status` 和软删除字段。这样 Run 输入快照和后续 Artifact 输出保留策略才能组成完整追溯链。

### 第 4 步：增强 pipeline_artifacts 输出保留策略

**工作目标**

- 让输出产物可以区分临时、缓存、当前结果、固定结果和已清理。
- 为后续缓存清理和依赖保护做准备。

**具体需要改什么**

- 在 `pipeline_artifacts` 增加字段：
  - `storage_uri`
  - `sha256`
  - `retention_status`
  - `deleted_at`
  - `deleted_by`
  - `last_accessed_at`
- 保留旧 `storage_path` 和 `checksum`，短期兼容。
- 默认迁移规则：
  - 旧 `storage_path` 映射到 `storage_uri`
  - 旧 `checksum` 映射到 `sha256`
  - 旧产物默认 `retention_status='cached'` 或按当前业务设为 `current`
- 更新 ArtifactStore 写入逻辑。

**验收标准**

- 新 Artifact 同时有 `storage_uri` 和 `retention_status`。
- Artifact preview 不受影响。
- 可以查询哪些 Artifact 可清理，哪些应保留。

**Codex 提示词**

```text
第4步：增强 pipeline_artifacts 输出保留策略。请在 init.sql 中为 pipeline_artifacts 增加 storage_uri、sha256、retention_status、deleted_at、deleted_by、last_accessed_at 等字段和必要索引，保留 storage_path/checksum 兼容旧代码，并更新 ArtifactStore 和相关 schema/response。新 Artifact 默认写入 storage_uri 和 retention_status。完成后验证 Artifact 列表和预览仍可用，并更新 日志/2_meeting260521/init_sql总体更新工作计划.md 中第 4 步的状态、实际改动、验证结果、遗留风险和下一步建议。
```

**执行结果（2026-05-21）**

- 状态：完成。
- 实际改动：
  - 在 `elys_version1/database/init.sql` 为 `pipeline_artifacts` 新增 `storage_uri`、`sha256`、`retention_status`、`deleted_at`、`deleted_by`、`last_accessed_at`。
  - 新增约束：`retention_status IN ('current', 'pinned', 'cached', 'deleted')`。
  - 新增索引：`idx_pipeline_artifacts_storage_uri`、`idx_pipeline_artifacts_sha256`、`idx_pipeline_artifacts_retention`、`idx_pipeline_artifacts_deleted`。
  - 增加兼容迁移：旧 `storage_path` 映射为 `project://{project_id}/{storage_path}`，旧 `checksum/content_hash` 映射为 `sha256`。
  - 在 SQLAlchemy `PipelineArtifact` model 中新增对应字段和索引。
  - 在 `schema_compat.py` 中新增幂等补字段、回填、约束重建和索引创建。
  - 更新 `ArtifactStore`：新写入 Artifact 默认 `storage_uri=project://...`、`sha256=checksum`、`retention_status='current'`，同时保留 `storage_path/checksum/content_hash`。
  - 更新 `PipelineCache`：缓存复用产生的 Artifact 记录写入 `storage_uri`、`sha256`，并标记 `retention_status='cached'`。
  - 更新 `ArtifactSummary`、`PipelineArtifactResponse`、`PipelineArtifactPreviewResponse` 和 router 响应映射。
  - 预览接口成功生成 preview 后会更新 `pipeline_artifacts.last_accessed_at`。
- 验证结果：
  - 已运行 `python -m compileall app`，通过。
  - 已运行 `python -c "from sqlalchemy.orm import configure_mappers; import app.models; configure_mappers(); ..."`，Artifact 相关 import 和 mapper 配置通过。
  - 已运行临时 ArtifactStore 行为验证：新 Artifact 会返回 `storage_uri`、`sha256`、`retention_status='current'`。
  - 已运行 preview/schema 构造验证：`build_artifact_preview()`、`PipelineArtifactResponse`、`PipelineArtifactPreviewResponse` 可构造。
  - 当前本地环境没有 `psql` 命令，因此未直接执行 `init.sql` 做 PostgreSQL 建表验证。
  - 当前本地 Python 环境缺少 `fastapi`，因此未能导入 `app.main` 或 router 做应用级启动验证。
- 遗留风险：
  - 本步只补 Artifact 保留状态字段，还没有实现“固定/取消固定/软删除/清理”的 API 和服务逻辑。
  - `pipeline_artifacts` 仍跟随 Run 使用外键级联删除；产品层应避免物理删除 Run，否则追溯记录仍会丢失。
  - `storage_uri` 目前是本地项目存储抽象 `project://...`，未来接入 MinIO/S3 时需要迁移或双写真实对象 URI。
  - 还没有 Artifact 依赖图；清理前仍需要结合后续 dependency 或 Run 输入/输出关系判断是否可删。
- 下一步建议：进入第 5 步，新增 `async_tasks` 和 `task_events`，把 Celery task id 从 `pipeline_runs.result_json` 中独立出来，形成 Run + Task 的结构化追踪链路。

### 第 5 步：新增 async_tasks 与 task_events

**工作目标**

- 把后台任务从 `pipeline_runs.result_json.celery_task_id` 中独立出来。
- 支持任务查询、进度、失败、重试和取消。

**具体需要改什么**

- 新增 `async_tasks` 表。
- 建议字段：
  - `id`
  - `celery_task_id`
  - `task_type`
  - `queue_name`
  - `status`
  - `progress`
  - `resource_kind`
  - `resource_id`
  - `payload_json`
  - `result_json`
  - `error_json`
  - `idempotency_key`
  - `created_by`
  - `created_at`
  - `started_at`
  - `finished_at`
  - `attempt`
  - `max_attempts`
- 新增 `task_events` 表。
- Pipeline Run 派发 Celery 时创建 `async_tasks`。
- Worker 状态变化时写 `task_events`。

**验收标准**

- 创建 Pipeline Run 时能得到或查询关联 Task。
- Celery task id 不再只能从 `result_json` 里取。
- 任务状态至少能记录 queued/running/succeeded/failed。

**Codex 提示词**

```text
第5步：新增 async_tasks 与 task_events。请在 init.sql 中新增 async_tasks 和 task_events 表、索引和状态枚举，在 ORM 中增加模型，并改造 Pipeline Run 派发 Celery 的逻辑：创建 Run 时同步创建 async_tasks，Celery task id 写入 async_tasks.celery_task_id，任务进度或状态变化写入 task_events。保留 result_json 中 celery_task_id 的兼容输出但不要作为唯一事实源。完成后验证 Pipeline Run 能关联 Task，并更新 日志/2_meeting260521/init_sql总体更新工作计划.md 中第 5 步的状态、实际改动、验证结果、遗留风险和下一步建议。
```

**执行结果（2026-05-21）**

- 状态：完成。
- 实际改动：
  - 在 `elys_version1/database/init.sql` 新增 `async_tasks` 表，用于保存 Celery 后台任务事实源；字段包括 `celery_task_id`、`task_type`、`queue_name`、`status`、`progress`、`project_id`、`resource_kind`、`resource_id`、`payload_json`、`result_json`、`error_json`、`idempotency_key`、`created_by`、`created_at`、`started_at`、`finished_at`、`attempt`、`max_attempts`。
  - 在 `elys_version1/database/init.sql` 新增 `task_events` 表，用于保存任务事件流水；字段包括 `task_id`、`event_type`、`status`、`progress`、`message`、`payload_json`、`created_at`。
  - 新增状态约束：`async_tasks.status` 和 `task_events.status` 限定为 `queued/running/succeeded/failed/canceled/cancelled/retrying`，进度限定为 `0..100`。
  - 新增索引：`uq_async_tasks_celery_task_id`、`idx_async_tasks_resource`、`idx_async_tasks_project_status`、`idx_async_tasks_status_created`、`idx_async_tasks_created_by`、`idx_task_events_task_created`、`idx_task_events_status`、`idx_task_events_type`。
  - 在 SQLAlchemy 中新增 `AsyncTask`、`TaskEvent` model，并注册到 `app.models`。
  - 在 `schema_compat.py` 中新增 `async_tasks`、`task_events` 的幂等建表和索引创建，兼容已有数据库启动补表。
  - 新增 `app/services/task_events.py`，集中处理任务查询、进度归一化、任务状态映射和事件写入。
  - 改造 Pipeline Run 创建逻辑：创建 `PipelineRun` 时同步创建 `AsyncTask`，预分配 task id 并写入 `async_tasks.celery_task_id`；Celery 派发成功后写入 `task_events.dispatched`；派发失败时写入失败事件。
  - 保留 `pipeline_runs.result_json.celery_task_id` 和 `task_queue` 兼容输出，同时新增 `async_task_id`，但结构化事实源改为 `async_tasks`。
  - 改造 Celery worker：任务启动时写 `started/running` 事件；执行结束后根据 Run 状态写 `completed/waiting_user_input/failed` 等事件，并更新 `async_tasks.result_json/error_json`。
  - Run 详情响应新增 `tasks` 字段，返回关联的 `AsyncTask` 和其 `TaskEvent` 列表。
- 验证结果：
  - 已运行 `python -m compileall app`，通过。
  - 已运行 SQLAlchemy mapper 配置验证，`AsyncTask` 和 `TaskEvent` 映射通过。
  - 已运行 `task_events` service 导入和行为验证，`record_task_event()` 可更新任务状态并生成事件。
  - 已运行 `app.tasks.pipeline_tasks` 导入验证，Celery task 注册名可读取。
  - 已运行 Run 详情响应结构构造验证，`PipelineRunDetailResponse.tasks` 可承载关联的 Task 和事件。
  - 当前本地环境没有 `psql` 命令，因此未直接执行 `init.sql` 做 PostgreSQL 建表验证。
  - 当前本地 Python 环境缺少 `fastapi`，因此未能导入 `app.routers.pipelines` 做应用级路由验证；已通过编译检查覆盖语法层面。
- 遗留风险：
  - 本步只记录 Run 级别的粗粒度任务事件，暂未把每个 Pipeline Node 的进度百分比持续写入 `task_events`。
  - `async_tasks` 还没有取消、重试、任务列表、任务详情等独立 API；目前主要通过 Run 详情返回关联任务。
  - `waiting_user_input` 的 Run 会使 Celery task 自身结束并标记为 `succeeded`，真实业务等待状态仍以 `pipeline_runs.status` 为准。
  - Celery 派发和 worker 启动之间存在事件时间先后竞争，事件表会保留真实写入顺序；产品展示时应按 `created_at` 解释。
- 下一步建议：进入第 6 步，补 `project_members.can_run`、`study_locks` 和更通用的审计事件，让“谁可以运行、谁正在编辑/运行、关键动作如何留痕”有结构化管理入口。

### 第 6 步：补 Study 协作权限、运行锁和通用审计

**工作目标**

- 支撑“同一 Pipeline 同时只允许一个人编辑或运行”。
- 支撑更通用的审计，不只记录 Project purge。

**具体需要改什么**

- 给 `project_members` 增加 `can_run`。
- 新增 `study_locks` 表。
- 建议字段：
  - `id`
  - `project_id`
  - `resource_kind`
  - `resource_id`
  - `lock_type`
  - `locked_by`
  - `locked_at`
  - `expires_at`
  - `metadata_json`
- 新增通用 `audit_events` 表，或扩展 `project_audit_events` 的使用边界。
- 关键行为写审计：
  - 上传
  - 重传
  - 运行
  - 固定输出
  - 清理输出
  - 权限变化
  - 隔离/下架

**验收标准**

- `project_members` 能表达 can_run。
- 可创建和释放 Pipeline 编辑/运行锁。
- 关键行为有通用审计入口。

**Codex 提示词**

```text
第6步：补 Study 协作权限、运行锁和通用审计。请在 init.sql 中给 project_members 增加 can_run 字段，新增 study_locks 表，并新增或扩展 audit_events 用于上传、重传、运行、固定输出、清理、权限变化等关键行为。更新 ORM、权限检查和必要的 service。确保锁有 expires_at，避免异常后永久占用。完成后验证成员权限和锁表可用，并更新 日志/2_meeting260521/init_sql总体更新工作计划.md 中第 6 步的状态、实际改动、验证结果、遗留风险和下一步建议。
```

**执行结果（2026-05-21）**

- 状态：完成。
- 实际改动：
  - 在 `elys_version1/database/init.sql` 中给 `project_members` 新增 `can_run` 字段，并为旧数据增加兼容回填：`owner/editor/can_write=true` 的成员默认可运行，`viewer` 默认不可运行。
  - 新增 `study_locks` 表，用于表示 Study 内资源的编辑/运行租约；字段包括 `project_id`、`resource_kind`、`resource_id`、`lock_type`、`locked_by`、`locked_at`、`expires_at`、`released_at`、`released_by`、`metadata`。
  - 新增 `audit_events` 通用审计表，用于记录上传、重传、运行、成员权限变化等关键动作；保留旧 `project_audit_events`，不破坏项目永久删除和 QA 审计。
  - 新增索引：`idx_audit_events_project_time`、`idx_audit_events_actor_time`、`idx_audit_events_action_time`、`idx_audit_events_resource`、`idx_study_locks_project_resource`、`idx_study_locks_locked_by`、`idx_study_locks_expires`、`uq_study_locks_active_resource`。
  - 在 SQLAlchemy 中新增 `AuditEvent`、`StudyLock` model，并给 `ProjectMember` 增加 `can_run`。
  - 在 `schema_compat.py` 中新增 `audit_events/study_locks` 的幂等建表、索引创建和 `project_members.can_run` 兼容补列/回填。
  - 新增 `app/services/audit_events.py`，提供 `record_audit_event()` 统一写审计。
  - 新增 `app/services/study_locks.py`，提供锁获取、过期释放、按锁 ID 精准释放和按资源释放能力；默认 TTL 为 24 小时。
  - 更新 `project_access.py`，新增 `ProjectAccess.RUN` 和 `require_project_run()`；Pipeline Run 入口改用运行权限，不再简单等同写权限。
  - 更新项目成员 API schema 和 router：成员响应包含 `can_run`，新增/更新成员时可传 `can_run` 覆盖角色默认值，并写入 `project.member.upsert/updated/removed` 审计。
  - 更新数据上传流程：新上传写 `dataset.uploaded` 审计，重传/替换写 `dataset.reuploaded` 审计。
  - 更新 Pipeline Run 派发：创建 Run 前获取 `study_locks` 的 pipeline 运行锁，锁 ID 写入 `async_tasks.payload_json` 和兼容 `result_json`；派发失败释放锁并写 `pipeline.run.dispatch_failed` 审计。
  - 更新 Celery worker：Run 完成、失败或异常时按 `lock_id` 精准释放运行锁，并写 `pipeline.run.{status}` 或 `pipeline.run.task_exception` 审计。
- 验证结果：
  - 已运行 `python -m compileall app`，通过。
  - 已运行 SQLAlchemy mapper 配置验证，`AuditEvent`、`StudyLock`、`ProjectMember.can_run` 映射通过。
  - 已运行 `audit_events` service 行为验证，`record_audit_event()` 可创建审计事件并规范化 `resource_id`。
  - 已运行 `study_locks` service 行为验证，锁可创建、具有 `expires_at`，并可释放写入 `released_at/release_reason`。
  - 已运行项目成员 schema 验证，`ProjectMemberResponse.can_run` 可正常表达。
  - 当前本地环境没有 `psql` 命令，因此未直接执行 `init.sql` 做 PostgreSQL 建表验证。
  - 当前本地 Python 环境缺少 `fastapi`，因此 `project_access`/router 只能完成编译验证，不能完成应用级导入验证。
- 遗留风险：
  - 本步只把 Pipeline Run 接入运行锁，Pipeline 编辑锁尚未接入前端编辑/保存流程。
  - `audit_events` 已有统一入口，但固定输出、清理输出、隔离/下架等动作的业务 API 还没实现，因此对应审计只能在后续功能落地时接入。
  - 锁释放依赖 worker 正常结束或 TTL 过期；如果 Celery 任务长期丢失，用户需要等 `expires_at` 后再次运行，后续可增加管理员强制释放接口。
  - `can_run` 与 `can_write` 已分离，但现有前端成员管理页面可能还没有展示/编辑 `can_run` 控件。
- 下一步建议：进入第 7 步，引入真正的平台级 Dataset 资产和 Study 挂载关系；同时后续功能模块应把固定输出、清理输出、隔离/下架接入 `audit_events`。

### 第 7 步：引入 Dataset 资产与 Study 挂载

**工作目标**

- 让 Dataset 独立于 Study 存在。
- Study 引用 Dataset，不复制 Dataset 文件。

**具体需要改什么**

- 因当前 `datasets` 名称已被采集记录占用，短期可新增 `dataset_assets` 表作为真正 Dataset 资产表。
- 新增 `study_dataset_mounts`。
- `dataset_assets` 建议字段：
  - `id`
  - `name`
  - `code`
  - `description`
  - `owner_id`
  - `status`
  - `visibility`
  - `metadata_json`
  - `created_by`
  - `created_at`
  - `updated_at`
- `study_dataset_mounts` 建议字段：
  - `id`
  - `project_id`
  - `dataset_asset_id`
  - `mount_name`
  - `selection_json`
  - `is_active`
  - `mounted_by`
  - `mounted_at`
- 暂时让旧 `datasets.project_id` 继续工作，后续再迁移为挂载关系。

**验收标准**

- 可以创建 Dataset 资产。
- 一个 Study 可以挂载一个 Dataset 资产。
- 不复制物理文件。

**Codex 提示词**

```text
第7步：引入 Dataset 资产与 Study 挂载。由于当前 datasets 表实际承担 recording 语义，请先新增 dataset_assets 表作为真正 Dataset 数据资产表，并新增 study_dataset_mounts 表表示 Study/Project 对 Dataset 的引用关系。不要立即删除或重命名旧 datasets.project_id。更新 ORM 和必要 schema/service，保证新结构能与旧导入流程共存。完成后验证可以创建 Dataset 资产并挂载到 Study，并更新 日志/2_meeting260521/init_sql总体更新工作计划.md 中第 7 步的状态、实际改动、验证结果、遗留风险和下一步建议。
```

**执行结果（2026-05-21）**

- 状态：完成。
- 实际改动：
  - 在 `elys_version1/database/init.sql` 新增 `dataset_assets` 表，作为真正的平台级 Dataset 数据资产表；字段包括 `name`、`code`、`description`、`owner_id`、`status`、`visibility`、`metadata`、`created_by`、`created_at`、`updated_at`。
  - 在 `elys_version1/database/init.sql` 新增 `study_dataset_mounts` 表，用于表示 Study/Project 对 Dataset Asset 的引用；字段包括 `project_id`、`dataset_asset_id`、`mount_name`、`selection_json`、`is_active`、`mounted_by`、`mounted_at`。
  - 新增索引：`uq_dataset_assets_code`、`idx_dataset_assets_owner`、`idx_dataset_assets_visibility_status`、`idx_dataset_assets_created_by`、`idx_study_dataset_mounts_project`、`idx_study_dataset_mounts_asset`、`idx_study_dataset_mounts_mounted_by`。
  - 保留旧 `datasets.project_id`、`datasets` 和 `dataset_uploads` 的现有导入流程，不做删除、不做重命名。
  - 在 SQLAlchemy 中新增 `DatasetAsset` 和 `StudyDatasetMount` model，并注册到 `app.models`。
  - 在 `schema_compat.py` 中新增 `dataset_assets/study_dataset_mounts` 的幂等建表和索引创建，兼容已有数据库。
  - 在 `app/schemas/dataset.py` 中新增 `DatasetAssetCreate/Response/ListResponse` 和 `StudyDatasetMountCreate/Response/ListResponse`。
  - 新增 `app/services/dataset_assets.py`，提供 Dataset Asset 创建、可见资产列表、资产访问检查、挂载到 Study 和查询 Study 挂载列表能力。
  - 新增独立 API 路由 `/api/v1/dataset-assets`，用于创建和列出 Dataset Asset；新增 `/api/v1/projects/{project_id}/datasets/mounts`，用于列出和创建 Study 的 Dataset 挂载。
  - 挂载时不复制物理文件，只写 `study_dataset_mounts` 引用关系和 `selection_json`。
  - 创建 Dataset Asset 和创建 Study 挂载时写入 `audit_events`：`dataset_asset.created` 和 `study.dataset_mount.created`。
- 验证结果：
  - 已运行 `python -m compileall app`，通过。
  - 已运行 SQLAlchemy mapper 配置验证，`DatasetAsset` 和 `StudyDatasetMount` 映射通过。
  - 已运行 Dataset Asset / Study Mount schema 验证，通过。
  - 已运行 `dataset_assets` service 导入验证，通过。
  - 已运行 service 级创建 Dataset Asset 并挂载到 Study 的行为验证，通过；验证了挂载只保存 `project_id + dataset_asset_id + mount_name` 引用关系。
  - 已运行 `schema_compat.py` 导入验证，通过。
  - 当前本地环境没有 `psql` 命令，因此未直接执行 `init.sql` 做 PostgreSQL 建表验证。
  - 当前本地 Python 环境缺少 `fastapi`，因此 router 只能完成编译验证，不能完成应用级导入验证。
- 遗留风险：
  - 当前 `DatasetAsset` 还没有和旧 `datasets`/`dataset_uploads` 自动建立 Recording 关系；本步只先建立资产表和挂载表，真正 Recording 语义迁移放到第 8 步。
  - `selection_json` 目前只是结构化挂载选择快照，尚未接入 LoadData 选择器；后续需要让 LoadData 支持按 mount 查询数据。
  - `visibility='workspace'/'shared'/'public'` 已有字段和基础访问判断，但还没有完整的数据发布、授权、分享和下架流程。
  - `dataset_assets.code` 当前是全局唯一，未来如果需要允许不同机构/用户下同名 code，需迁移为命名空间唯一。
- 下一步建议：进入第 8 步，设计 `datasets -> recordings`、`dataset_uploads -> recording_versions` 的兼容迁移方案，让 Dataset Asset、Recording、Recording Version、Dataset File 的层级语义真正统一起来。

### 第 8 步：规划并实施 Recording 语义迁移

**工作目标**

- 把当前 `datasets` 的产品语义改为 Recording。
- 把当前 `dataset_uploads` 的产品语义改为 Recording Version。
- 尽量减少一次性破坏。

**具体需要改什么**

- 可以先新增兼容视图：
  - `recordings_view` -> 当前 `datasets`
  - `recording_versions_view` -> 当前 `dataset_uploads`
- 或新增新表并编写迁移脚本。
- 更新 ORM 命名、schema 命名、API 文案。
- 文档和前端显示使用 Recording / 采集记录。

**验收标准**

- 代码和文档不再把单条 `subject/session/task/run` 误称为 Dataset 资产。
- 旧接口仍可兼容一段时间。
- 新结构能支撑 Dataset Asset -> Recording -> Recording Version -> Dataset File。

**Codex 提示词**

```text
第8步：规划并实施 Recording 语义迁移。请基于前面新增的 dataset_assets、study_dataset_mounts、dataset_files，设计当前 datasets -> recordings、dataset_uploads -> recording_versions 的兼容迁移方案。优先考虑兼容视图或分阶段 ORM/schema 改名，避免一次性破坏旧 API。完成必要代码和文档更新后，验证旧数据导入和新命名都能工作，并更新 日志/2_meeting260521/init_sql总体更新工作计划.md 中第 8 步的状态、实际改动、验证结果、遗留风险和下一步建议。
```

**执行结果（2026-05-21）**

- 状态：完成。
- 实际改动：
  - 新增 `日志/2_meeting260521/recording语义迁移方案.md`，明确 Dataset Asset、Study Dataset Mount、Recording、Recording Version、Dataset File 的命名边界和分阶段迁移路线。
  - 在 `elys_version1/database/init.sql` 新增 `recordings_view`，把当前旧 `datasets` 表投影为只读 Recording 视图；保留 `legacy_dataset_id` 便于追溯旧表来源。
  - 在 `elys_version1/database/init.sql` 新增 `recording_versions_view`，把当前旧 `dataset_uploads` 表投影为只读 Recording Version 视图；保留 `legacy_dataset_upload_id`。
  - 保留旧 `datasets`、`dataset_uploads` 和 `datasets.project_id`，旧上传、旧列表、旧 QA 接口继续使用原路径。
  - 在 SQLAlchemy 中新增 `Recording` 和 `RecordingVersion` view model，分别映射 `recordings_view` 和 `recording_versions_view`。
  - 在 `schema_compat.py` 中新增兼容视图创建，并补齐旧库可能缺少的 `dataset_uploads.fif_dir/fif_path/sidecar_paths` 与 `datasets.current_upload_id`。
  - 在 `app/schemas/dataset.py` 中新增 `RecordingResponse`、`RecordingVersionResponse`、`RecordingListResponse`、`RecordingVersionListResponse`。
  - 新增 `app/services/recordings.py`，提供按 Study 查询 Recording、查询单条 Recording、查询 Recording Version 列表的只读服务。
  - 新增只读 API：
    - `GET /api/v1/projects/{project_id}/recordings`
    - `GET /api/v1/projects/{project_id}/recordings/{recording_id}/versions`
  - 注册 `recording_router` 到主应用；新命名 API 与旧 `datasets` API 并行存在。
- 验证结果：
  - 已运行 `python -m compileall app`，通过。
  - 已运行 SQLAlchemy mapper 配置验证，`Recording`、`RecordingVersion` 与旧 `Dataset`、`DatasetUpload` 可同时存在。
  - 已运行 Recording schema 构造验证，`RecordingResponse` 与 `RecordingVersionResponse` 可表达旧数据的新命名结构。
  - 已运行 `recordings` service 导入验证，列表和版本查询服务可导入。
  - 已运行 `schema_compat.py` 导入验证，通过。
  - 当前本地环境没有 `psql` 命令，因此未直接执行 `init.sql` 做 PostgreSQL 视图创建验证。
  - 当前本地 Python 环境缺少 `fastapi`，因此 router 只能完成编译验证，不能完成应用级导入验证。
- 遗留风险：
  - `recordings_view` 和 `recording_versions_view` 是只读兼容层，写入仍走旧 `datasets` / `dataset_uploads`。
  - 旧代码中仍大量使用 `Dataset` / `DatasetUpload` 命名；第 8 步先提供新读模型和新 API，没有一次性替换全部内部命名。
  - Dataset Asset 与 Recording 暂未建立强关联；当前 Recording 仍按 Study/Project 归属查询。
  - LoadData 数据选择器尚未改为基于 Dataset Asset Mount -> Recording -> Recording Version -> Dataset File 的完整链路。
- 下一步建议：进入第 9 步，拆分 `init.sql` 的 baseline、兼容迁移和 seed 职责，并为这些视图和新增表准备显式迁移路径。

### 第 9 步：拆分 init.sql、迁移逻辑和种子数据

**工作目标**

- 降低 `init.sql` 的职责复杂度。
- 为 Alembic 或其它迁移工具做准备。

**具体需要改什么**

- 把 `init.sql` 整理为 baseline schema。
- 把角色、权限、测试用户移到 seed 脚本或清晰的 seed 分区。
- 把启动期兼容迁移逐步迁到 Alembic migration。
- 梳理 `schema_compat.py`，减少启动时隐式改库。

**验收标准**

- 新库初始化路径清晰。
- 旧库升级路径清晰。
- 种子数据可以独立维护。
- 文档说明如何执行初始化和迁移。

**Codex 提示词**

```text
第9步：拆分 init.sql、迁移逻辑和种子数据。请整理 database/init.sql 的职责，把 baseline schema、兼容迁移、角色权限种子、测试用户种子分清楚；如项目已适合接入 Alembic，请给出并实施最小迁移框架，否则先完成清晰分区和执行说明。同步检查 services/schema_compat.py，减少启动期隐式改库。完成后验证新库初始化仍可用，并更新 日志/2_meeting260521/init_sql总体更新工作计划.md 中第 9 步的状态、实际改动、验证结果、遗留风险和下一步建议。
```

**执行结果（2026-05-21）**

- 状态：完成。
- 实际改动：
  - 将 `elys_version1/database/init.sql` 改为薄入口，通过 `\ir` 依次组合 baseline schema、兼容迁移、角色权限 seed、MVP/demo 用户 seed。
  - 新增 `elys_version1/database/schema/00_current_schema.sql`，作为新库 baseline schema；该文件不再包含角色、权限、测试用户 seed，也移除了明显属于旧库补丁的 `ADD COLUMN` 兼容语句。
  - 新增 `elys_version1/database/migrations/20260521_0001_compat_v1_to_current.sql`，作为旧 v1 库升级到当前 MVP schema 的显式幂等兼容迁移。
  - 新增 `elys_version1/database/seeds/01_roles_permissions.sql` 和 `elys_version1/database/seeds/02_dev_users.sql`，把系统角色权限 seed 与 MVP/demo 用户 seed 分离。
  - 新增 `elys_version1/database/init_core.sql`，用于不写入 demo 用户的生产/准生产初始化。
  - 新增 `elys_version1/database/README.md`，说明新库初始化、旧库升级、seed 执行和 Alembic 使用方式。
  - 在 `backend/requirements.txt` 增加 `alembic==1.13.2`，并新增 `backend/alembic.ini`、`backend/alembic/env.py`、`backend/alembic/script.py.mako` 与两个最小 revision。
  - 重写 `backend/app/services/schema_compat.py`，从启动时内联建表/补字段脚本，改为读取显式兼容迁移 SQL 的可选执行器。
  - 新增 `RUN_SCHEMA_COMPAT_ON_STARTUP` 配置，默认 `False`；`app/main.py` 只有在该开关打开时才会执行兼容迁移，减少启动期隐式改库。
- 验证结果：
  - 已运行 `python -m compileall app alembic`，通过。
  - 已验证 `schema_compat.read_compatibility_sql()` 能读取显式兼容迁移 SQL；默认配置下 `ensure_schema_compatibility()` 返回 `False`，不会隐式改库。
  - 已验证 `database/init.sql` 包含 4 个显式 include，`database/init_core.sql` 包含 3 个显式 include。
  - 已验证 baseline schema 不包含 `INSERT INTO roles`、`INSERT INTO users`，角色权限 seed 和 demo 用户 seed 已分离。
  - 当前本地环境没有 `psql` 命令，因此未直接执行 PostgreSQL 新库初始化。
  - 当前本地环境未安装完整 Alembic CLI 包；已更新 requirements 并完成文件级/语法级验证，实际 `alembic upgrade head` 需在安装依赖后执行。
- 遗留风险：
  - 兼容迁移 SQL 仍然较大，短期是从旧 monolith schema 中抽出的幂等脚本；后续应按版本逐步拆成更小的 Alembic revision。
  - `init.sql` 仍默认执行 `02_dev_users.sql` 以兼容当前 MVP 部署行为；生产环境应改用 `init_core.sql` 或部署脚本显式选择 seed。
  - Alembic 当前 revision 采用执行 SQL 文件的最小框架，尚未使用 `op.create_table` 细粒度建模，也没有 downgrade。
- 下一步建议：进入第 10 步，做登录、创建 Study、上传 EEG、Run、Artifact、Task、Recording API 的全链路回归，并同步 docs_v2 中数据库、文件管理、API、任务队列与后端架构文档。

### 第 10 步：全链路回归与文档收口

**工作目标**

- 验证前 9 步改造后，核心链路仍可运行。
- 把数据库、文件、API、后端架构文档同步到一致状态。

**具体需要改什么**

- 回归验证：
  - 登录
  - 创建 Study/Project
  - 上传 EEG
  - 生成 canonical FIF
  - 写入 `dataset_files`
  - 创建 Pipeline
  - Run 创建
  - 写入 `pipeline_run_inputs`
  - Celery 任务关联 `async_tasks`
  - 写入 Artifact
  - Artifact retention 状态可查
- 更新相关文档：
  - `wiki/docs_v2/3-00` 与 3xx 子页
  - `wiki/docs_v2/4-00` 与 4xx 子页
  - `wiki/docs_v2/7-00` 与 7xx 子页
  - `wiki/docs_v2/2-50`
  - `wiki/docs_v2/2-60`

**验收标准**

- 核心链路通过。
- `mkdocs build` 通过。
- 本文档所有步骤状态完整。

**Codex 提示词**

```text
第10步：全链路回归与文档收口。请对 init.sql 改造后的核心链路做回归验证：登录、创建 Study/Project、上传 EEG、生成 canonical FIF、dataset_files 写入、创建 Pipeline、Run 创建、pipeline_run_inputs 写入、async_tasks 关联、Artifact 写入和 retention_status 查询。同步更新 docs_v2 中数据库、文件管理、API、任务队列、后端架构相关页面。最后运行 mkdocs build，并更新 日志/2_meeting260521/init_sql总体更新工作计划.md 中第 10 步的状态、实际改动、验证结果、遗留风险和最终结论。
```

**执行结果（2026-05-21）**

- 状态：完成。
- 新增回归报告：`日志/2_meeting260521/init_sql第10步全链路回归与文档收口.md`。
- 实际改动：
  - 修复 `backend/tests/test_dataset_qa_mock_run.py` 的测试依赖桩，补齐 `DatasetAsset`、`DatasetFile`、`Recording`、`RecordingVersion`、`StudyDatasetMount` 以及新增 service stub，使现有 QA 路由测试能在缺少 FastAPI 的本地环境继续运行。
  - 同步更新 `wiki/docs_v2/2-50-API设计总览.md`，把当前实际路由数更新为 44 个，并补入 Dataset Asset、Study Mount、Recording 新接口。
  - 同步更新 `wiki/docs_v2/2-60-任务队列与异步架构.md`，把 `async_tasks`、`task_events` 从规划状态改为已落地，并说明 Task 查询/SSE/取消重试仍待补。
  - 同步更新 `wiki/docs_v2/3-00`、`3-20`、`3-40`、`3-50`，明确 `dataset_assets` 是当前真正 Dataset 资产表，旧 `datasets/dataset_uploads` 分别通过 `recordings_view/recording_versions_view` 兼容为 Recording/Recording Version。
  - 同步更新 `wiki/docs_v2/4-00`、`4-20`、`4-30`、`4-40`，明确 `dataset_files`、canonical FIF、Run Artifact、数据选择器与 LoadData 输入冻结的当前落地状态。
  - 同步更新 `wiki/docs_v2/7-00`、`7-10`、`7-40`，明确后端当前 44 个 API、六个 router、启动期 schema 兼容默认关闭、Pipeline Run 已接入 `pipeline_run_inputs/async_tasks/task_events/study_locks`。
- 验证结果：
  - `python -m compileall app alembic` 通过。
  - `python -m pytest -q` 通过：15 passed，17 个 `datetime.utcnow()` deprecation warning。
  - SQLAlchemy mapper 验证通过：`DatasetAsset`、`StudyDatasetMount`、`Recording`、`RecordingVersion`、`DatasetFile`、`PipelineRunInput`、`AsyncTask`、`TaskEvent`、`PipelineArtifact` 可配置。
  - Pipeline 响应 schema 构造通过：`PipelineArtifactResponse`、`PipelineRunInputResponse`、`AsyncTaskResponse`、`TaskEventResponse` 可表达 retention、输入快照和任务事件。
  - 静态统计当前后端实际 44 个 HTTP API：`main.py` 1 个、`auth.py` 4 个、`projects.py` 11 个、`datasets.py` 11 个、`pipelines.py` 17 个。
  - 数据库 SQL 分区检查通过：`init.sql` 4 个 include，`init_core.sql` 3 个 include；baseline schema 不包含 role/user seed。
  - `mkdocs build` 通过；仅输出 Material for MkDocs 关于未来 MkDocs 2.0 的上游提示，不影响构建。
- 未完成的真实集成验证：
  - 本机没有 `psql`，未执行真实 PostgreSQL `database/init.sql` 初始化。
  - 本机没有 `fastapi`，未启动后端做真实 HTTP 登录、创建 Study、上传 EEG 和 Artifact 预览。
  - 本机没有 `alembic` CLI 包，未执行 `alembic upgrade head`。
  - 本机没有 Redis/Celery worker，未验证真实后台任务派发、worker 状态流转和锁释放。
- 遗留风险：
  - Dataset 导入仍是同步 HTTP 流程，真实大文件上传转换需要部署环境补测。
  - `async_tasks/task_events` 已有事实源，但还没有 `/tasks/{task_id}` 查询、取消、重试和 SSE API。
  - Artifact retention 字段已落地，但 pin/unpin/cleanup 服务和依赖保护仍待实现。
  - `recordings_view` / `recording_versions_view` 仍是只读兼容层，写入仍走旧 `datasets/dataset_uploads`。
- 最终结论：init.sql 改造从数据库对象、后端模型、Run 追溯、任务事实源、文件索引和文档结构上已经收口到当前 MVP 标准；下一轮重点应在完整依赖环境中补真实端到端回归，并继续实现 Task API、异步导入和 Artifact 清理服务。

## 5. 状态更新记录

| 时间 | 步骤 | 状态 | 记录 |
|---|---|---|---|
| 2026-05-21 | 文档创建 | 完成 | 建立 init.sql 总体更新工作计划，等待第 1 步执行 |
| 2026-05-21 | 第 1 步 | 完成 | 完成 `init.sql`、ORM、`schema_compat.py`、routers 和 Pipeline 内部依赖的只读基线审计；新增 `init_sql第1步基线审计.md`；未执行 SQL 或破坏式改表 |
| 2026-05-21 | 第 2 步 | 完成 | 新增 `dataset_files` 表、ORM 和 `schema_compat.py` 兼容建表；导入流程已双写 raw_source、canonical_fif、sidecar 文件索引；Python 编译、模型导入和 mapper 配置验证通过 |
| 2026-05-21 | 第 3 步 | 完成 | 新增 `pipeline_run_inputs` 表、ORM 和兼容建表；Run 创建时冻结 LoadData 输入；LoadData 执行优先使用快照；Run 详情响应新增 `inputs` |
| 2026-05-21 | 第 4 步 | 完成 | 增强 `pipeline_artifacts` 保留策略字段；ArtifactStore 和缓存复用已双写 `storage_uri/sha256/retention_status`；Artifact 响应和预览结构已同步 |
| 2026-05-21 | 第 5 步 | 完成 | 新增 `async_tasks/task_events` 表、ORM、schema 和事件服务；Run 创建时同步创建 Task，Celery 派发和 worker 状态变化写入事件；Run 详情响应新增 `tasks` |
| 2026-05-21 | 第 6 步 | 完成 | 新增 `project_members.can_run`、`study_locks` 和 `audit_events`；Pipeline Run 已接入运行权限、运行锁、锁释放和通用审计；上传/重传和成员权限变化已写审计 |
| 2026-05-21 | 第 7 步 | 完成 | 新增 `dataset_assets` 和 `study_dataset_mounts`；提供 Dataset Asset 创建/列表和 Study 挂载 API；旧 `datasets.project_id` 导入链路保持兼容 |
| 2026-05-21 | 第 8 步 | 完成 | 新增 `recordings_view/recording_versions_view`、`Recording/RecordingVersion` ORM、只读 Recording API 和迁移说明文档；旧上传与旧 datasets API 保持兼容 |
| 2026-05-21 | 第 9 步 | 完成 | 拆分 `init.sql` 为组合入口、baseline schema、兼容迁移、角色权限 seed 和 demo 用户 seed；新增 `init_core.sql`、数据库 README 与最小 Alembic 框架；启动期 schema 兼容改为默认关闭的显式迁移 |
| 2026-05-21 | 第 10 步 | 完成 | 完成代码级/模型级/文档级回归和 docs_v2 收口；`pytest`、`compileall`、mapper、schema 构造、路由统计、SQL 分区检查和 `mkdocs build` 通过；真实 PostgreSQL/FastAPI/Celery 端到端受本机环境限制未执行 |

## 6. 风险与注意事项

| 风险 | 说明 | 缓解方式 |
|---|---|---|
| 一次性重命名破坏现有代码 | 当前 router、model、schema 大量依赖 `projects/datasets/dataset_uploads` | 先新增兼容表和字段，后续分阶段改名 |
| 只改 SQL 不改 ORM | 后端运行时不会识别新增字段或表 | 每步都同步 SQLAlchemy model 和必要 schema |
| Run 输入仍依赖当前数据 | Dataset 重传后旧 Run 失真 | 第 3 步必须落地 `pipeline_run_inputs` |
| 历史 Run 没有输入快照 | 第 3 步只对新建 Run 写入 `pipeline_run_inputs` | 可在需要时对旧 Run 读取 `result_json.data_infos_by_node` 做有限回填，但不能伪造精确文件版本 |
| 历史数据未回填 dataset_files | 第 2 步只保证新导入双写，旧数据仍只有 `source_path/fif_path/sidecar_paths` | 后续补一个只读扫描+回填脚本，或在首次访问时懒加载登记 |
| 文件清理误删下游依赖 | Artifact 没有 retention 和 dependency | 第 4 步先补 retention，后续补 dependency |
| Artifact 只有状态字段没有清理服务 | 第 4 步新增了 `retention_status/deleted_at`，但尚未实现固定、软删除和实际清理 API | 后续增加 Artifact retention service，并在清理前检查 Run/Artifact 依赖 |
| Celery 状态不可追踪 | task id 放在 `result_json` 不可查询和取消 | 第 5 步已新增 `async_tasks/task_events`；后续补任务列表、取消、重试 API |
| 锁过期与真实任务状态可能偏离 | worker 丢失时锁只能靠 `expires_at` 过期；过期后可能允许新 Run | 后续增加锁列表、强制释放、心跳续租和任务巡检 |
| 审计覆盖仍不完整 | 本步覆盖上传/重传/运行/权限变化，固定输出、清理、隔离/下架还没有业务入口 | 后续实现对应 API 时必须调用 `record_audit_event()` |
| Dataset Asset 与旧 datasets 语义仍未打通 | 第 7 步只新增资产和挂载表，旧 `datasets` 仍是采集记录但命名未变 | 第 8 步规划并实施 Recording 语义迁移，建立 Asset -> Recording -> Version 兼容路径 |
| Dataset Mount 尚未接入 LoadData | Study 已能挂载 Dataset Asset，但数据选择器仍主要读取旧 `datasets` | 后续让 LoadData 支持按 `study_dataset_mounts.selection_json` 和资产挂载查询 |
| Recording 迁移仍是只读兼容层 | 第 8 步新增视图和新 API，但写入仍走旧 `datasets/dataset_uploads` | 后续分阶段把内部服务和前端命名迁移到 Recording，再考虑物理表改名 |
| init.sql 越来越复杂 | 第 9 步已拆分，但兼容迁移 SQL 仍然较大 | 后续把兼容迁移继续拆成更小的 Alembic revision |
| 启动期隐式改库 | 第 9 步已默认关闭启动期 schema 兼容，但仍保留 `RUN_SCHEMA_COMPAT_ON_STARTUP` 过渡开关 | 正式环境优先执行显式 SQL/Alembic；仅在临时升级旧库时打开开关 |
| 物理删除影响追溯 | 当前多处外键使用 `ON DELETE CASCADE`，项目 purge 还会删除目录 | Run、Artifact 和审计相关对象优先使用软删除、retention 和快照 |
