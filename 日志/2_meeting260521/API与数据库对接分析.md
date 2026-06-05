# API 与数据库对接分析

生成时间：2026-05-21 14:02:34 +08:00

分析目标：检查当前 API、Pydantic schema、SQLAlchemy ORM、数据库 schema 之间是否对齐，尤其关注 `Dataset / Study / Pipeline / Run` 相关功能是否存在“表已建但 API 没接上”“API 能写但业务没消费”“状态和权限不一致”等问题。

参考范围：

- `elys_version1/backend/app/routers/auth.py`
- `elys_version1/backend/app/routers/projects.py`
- `elys_version1/backend/app/routers/datasets.py`
- `elys_version1/backend/app/routers/pipelines.py`
- `elys_version1/backend/app/schemas/*.py`
- `elys_version1/backend/app/models/project.py`
- `elys_version1/backend/app/services/*.py`
- `elys_version1/database/schema/00_current_schema.sql`
- `elys_version1/database/migrations/20260521_0001_compat_v1_to_current.sql`

## 1. 总体结论

当前 API 与数据库已经可以支撑 MVP 的主链路：

1. Study/Project 创建、成员管理、软删除、恢复。
2. Dataset Asset 创建、列表、Study Mount 创建/更新/停用。
3. EEG 上传、生成 legacy `datasets` / `dataset_uploads` / `dataset_files`。
4. Pipeline CRUD、Run 创建、Run detail 查询。
5. Run 输入快照、Artifact、Async Task、Task Event 查询。
6. Artifact retention 标记。

静态统计当前 API 数量：

| Router | 端点数 | 说明 |
| --- | ---: | --- |
| `auth.py` | 4 | 登录、刷新、当前用户、登出 |
| `projects.py` | 13 | Study/Project、成员、settings、删除恢复 |
| `datasets.py` | 16 | Dataset Asset、Mount、Recording、Dataset、dataset_files、QA、上传 |
| `pipelines.py` | 21 | 节点、LoadData resolve、Task、Pipeline、Run、Artifact、交互 |
| 合计 | 54 | 静态路由统计 |

整体判断：

| 模块 | API-DB 对接成熟度 | 判断 |
| --- | --- | --- |
| Study/Project | 中等偏好 | 基础 CRUD、权限、settings 都有接口，purge 已增加数据阻断；settings 的 run_policy 和 artifact_retention_policy 仍未被运行时充分消费。 |
| Dataset | 中等偏好 | Asset/Mount/上传目标、文件索引查询、按 mount/asset 查询数据已接上；create-and-mount、跨 asset 同名实体、完整发布治理仍待后续。 |
| Pipeline | 中等偏好 | Pipeline CRUD 与 DB 对接正常，已补审计和 draft 更新；expected_version 仍是可选，并发编辑保护还可加强。 |
| Run | 中等偏好 | Run detail 能返回 inputs/dependencies/tasks/artifacts，输入预校验和 Artifact deleted 语义已补；运行时自动写入 dependency 仍待实现。 |
| Task | 中等 | 已有只读 API，status 参数已枚举化；cancel/retry 尚未接。 |

## 2. 已对齐的部分

### Study/Project

已对齐：

1. `projects` 表对应 `/api/v1/projects`。
2. `project_members` 对应成员增删改查 API。
3. `project_members.can_run` 已被 `require_project_run` 使用。
4. `study_settings` 已有 `GET/PUT /api/v1/projects/{project_id}/settings`。
5. `project_audit_events` 保留 project purge 前快照。
6. `audit_events` 已用于 settings、mount、run、artifact retention 等新行为。

### Dataset

已对齐：

1. `dataset_assets` 对应 `/api/v1/dataset-assets` 创建和列表。
2. `study_dataset_mounts` 对应 `/api/v1/projects/{project_id}/datasets/mounts` 创建、列表、更新、停用。
3. `datasets.dataset_asset_id` 已进入 ORM 和 `DatasetResponse`。
4. `recordings_view.dataset_asset_id` 已进入 ORM 和 `RecordingResponse`。
5. 上传 EEG 时会写 `datasets`、`dataset_uploads`、`dataset_files`，并关联默认 working Dataset Asset。

### Pipeline

已对齐：

1. `pipeline_definitions` 对应 Pipeline 创建、列表、详情、更新、逻辑删除。
2. `pipeline_definitions.status` 数据库约束与 API 基本一致。
3. `PipelineUpdate.expected_version` 支持乐观并发检查。

### Run / Task / Artifact

已对齐：

1. `pipeline_runs` 对应 Run 创建、列表、详情。
2. `pipeline_node_runs` 对应节点列表、交互接口。
3. `pipeline_run_inputs` 已在 Run detail 中返回。
4. `async_tasks` 和 `task_events` 已有只读 API。
5. `pipeline_artifacts` 已有列表、预览、retention 更新 API。

## 3. 主要问题清单

本节保留本次分析时发现的问题原貌；每项当前修复状态见第 8 节“2026-05-21 修复更新”。

优先级说明：

- P0：可能影响数据事实源、追溯、依赖安全或造成明显错误。
- P1：MVP 应尽快补齐，否则前端或协作体验会受影响。
- P2：暂不阻塞，但会影响一致性或长期维护。

| 编号 | 优先级 | 模块 | 问题 | 影响 | 建议 |
| --- | --- | --- | --- | --- | --- |
| API-DB-DS-01 | P0 | Dataset | 上传 API 总是写入默认 working Dataset Asset，不能指定 `dataset_asset_id` 或 `mount_name`。 | 用户手动创建的 Dataset Asset / Mount 不能作为上传目标，Dataset Asset 概念仍容易被绕过。 | 上传接口增加可选 `dataset_asset_id` 或 `mount_name`，并校验该 asset 已被当前 Study 挂载或用户有写权限。 |
| API-DB-DS-02 | P0 | Dataset | 默认 `working` mount 可能与默认 working Dataset Asset 漂移。`get_or_create_working_dataset_asset` 发现已有 `mount_name='working'` 时不会确认它是否指向默认 asset。 | 如果用户先把 `working` 挂到别的 asset，后续上传会写默认 asset，但 LoadData 用 `mount_name=working` 会读另一个 asset。 | 默认 mount 创建逻辑应校验 `working` mount 的 `dataset_asset_id`，冲突时改用系统保留 mount 或返回冲突。 |
| API-DB-DS-03 | P1 | Dataset | Dataset Asset 有 `status=working/active/archived/deleted/quarantined`，但 API 没有更新状态接口。 | 无法通过 API 归档、隔离、伦理下架 Dataset Asset。 | 增加 Dataset Asset update/status API，至少支持 `archived`、`quarantined`、`deleted` 软状态。 |
| API-DB-DS-04 | P1 | Dataset | `quarantined` 仍可能被列表、读取和挂载。当前可读逻辑只排除 `deleted`。 | 伦理或治理隔离状态不能真正阻止使用。 | `can_read_dataset_asset` 和 mount API 应特殊处理 `quarantined`，普通用户不可见/不可挂载，管理员可治理查看。 |
| API-DB-DS-05 | P1 | Dataset | Dataset/Recording 列表 API 不能按 `dataset_asset_id`、`mount_id`、`mount_name` 过滤。 | 前端数据选择器难以只展示某个挂载数据资产里的数据。 | 给 `/datasets` 和 `/recordings` 增加 asset/mount 过滤参数。 |
| API-DB-DS-06 | P1 | Dataset | `dataset_files` 有表和写入逻辑，但没有查询 API。 | 前端无法查看 raw/canonical_fif/sidecar 文件索引，也难以做文件级选择和排查。 | 增加 `/datasets/{dataset_id}/files` 和 `/recordings/{recording_id}/files`，必要时支持 `file_role` 过滤。 |
| API-DB-DS-07 | P1 | Dataset | `study_dataset_mounts.selection_json` 是自由 JSON，API 不校验结构。 | 前端或调用方写入错误 selector 后，LoadData 可能解析异常或静默匹配不到数据。 | 定义 Mount selection schema，至少校验 `dataset_filter`、subject/session/task/run/qa_status、require_fif。 |
| API-DB-DS-08 | P2 | Dataset | Dataset Asset 创建 API 只创建资产目录，不支持同时挂载到 Study。 | 用户创建 asset 后还要单独调用 mount，体验上容易断。 | 增加 `create_and_mount` 参数或在 Study 内提供创建并挂载接口。 |
| API-DB-DS-09 | P2 | Dataset | EEG 上传重复校验仍是 Project 级 checksum。 | 同一 Study 中不同 Dataset Asset 想保留同一原始数据时会被阻止。 | 后续改为 asset 级去重策略，或允许引用已有文件而不是重复上传。 |
| API-DB-ST-01 | P0 | Study | Project purge API 仍会物理删除 Project，并通过外键级联删除大量数据。 | 会绕过 Run 依赖、Artifact 保留和 Dataset 追溯。 | purge 前检查 Run、Artifact、pipeline_run_dependencies；默认只软删除，硬删除放平台治理后台。 |
| API-DB-ST-02 | P1 | Study | `study_settings` 已有 API，但运行时尚未充分消费。 | settings 成为“能写但不生效”的配置。 | LoadData 默认过滤、运行并发策略、Artifact retention 默认策略应读取 Study Settings。 |
| API-DB-ST-03 | P2 | Study | API 路径仍是 `/projects`，产品语义是 Study。 | 文档、前端命名和后端对象会持续混杂。 | 短期文档说明 Project=Study；中期增加 `/studies` alias。 |
| API-DB-PL-01 | P1 | Pipeline | Pipeline 创建、更新、删除没有写 `audit_events`。 | 多人协作时难以追踪谁改了 Pipeline 定义。 | 在 create/update/delete 中记录 pipeline.created / updated / deleted，并记录 version、字段变更摘要。 |
| API-DB-PL-02 | P1 | Pipeline | `expected_version` 仍是可选。 | 前端漏传时，可能覆盖他人的 Pipeline 修改。 | 后端逐步强制 update 必须传 `expected_version`，或先在前端强制。 |
| API-DB-PL-03 | P2 | Pipeline | DB 支持 `draft`，但创建 API 默认直接 `active`，更新 API 只允许 `active/archived`。 | Pipeline draft 状态目前只是数据库预留，API 不可用。 | 如果产品需要草稿，补 `draft` create/update；否则从 DB 枚举中暂时去掉。 |
| API-DB-RUN-01 | P0 | Run | `pipeline_run_dependencies` 表已建，但当前没有 API 返回，也没有运行时自动写入。 | run3 依赖 run2 的事实还不能被系统保护。 | 当节点使用上游 Run/Artifact 时写入依赖表，并在 Run detail 返回 dependencies。 |
| API-DB-RUN-02 | P1 | Run | `pipeline_run_inputs` 记录了数据项的 `dataset_asset_id`，但 selector 行没有保存“解析后的 mount/asset/filter”。 | 如果 selector 没匹配到数据，可能看不出当时解析的是哪个 mount/asset。 | 在 selector `resolved_metadata_json` 中增加 `resolved_filter`、`mount_id`、`mount_name`、`dataset_asset_id`。 |
| API-DB-RUN-03 | P1 | Run | Run 创建时即使 LoadData 解析有错误，也可能先 queued，再由执行阶段失败。 | 用户体验上像“成功提交”，实际很快失败；也会产生失败 Run 噪音。 | Run 创建前可先做一次强校验；严重输入错误直接 422，或返回 queued_with_warnings 明确状态。 |
| API-DB-RUN-04 | P1 | Artifact | Artifact retention 标记为 `deleted` 后，列表和预览仍未强制排除或阻止。 | “逻辑删除”不等于不可用，用户仍可能看到/预览已删除输出。 | Artifact list 默认排除 deleted，支持 `include_deleted`；preview deleted artifact 返回 409 或 410。 |
| API-DB-RUN-05 | P2 | Artifact | DB 允许 `retention_status='cached'`，API 更新只允许 `current/pinned/deleted`。 | 这是内部状态与外部状态不完全一致。当前不致命，但需文档说明。 | 保持 cached 内部专用，API 文档明确。 |
| API-DB-TASK-01 | P1 | Task | Task API 只有查询，没有 cancel/retry。 | 长耗时 Pipeline Run 出错或卡住时，用户无法通过 API 控制。 | 增加 cancel/retry，并同步 Run 状态、Celery revoke、锁释放、审计。 |
| API-DB-TASK-02 | P2 | Task | Task 列表 `status` 参数是自由字符串。 | 错误状态只会返回空列表，不利于前端排查。 | 使用 Pydantic Literal 枚举约束 task status。 |
| API-DB-GOV-01 | P1 | Governance | `audit_events` 已有，但不是所有关键 API 都写入。 | 协作行为追踪不完整。 | Pipeline CRUD、Dataset Asset status、Task cancel/retry、purge 检查结果都应写 audit。 |

## 4. 按对象细看

### Dataset API 与数据库

当前 Dataset 对接已经从“纯 Project 内上传”推进到“Dataset Asset + Mount + 文件索引查询”的 MVP 链路。

本轮已经让 `/datasets/import` 支持通过 `dataset_asset_id` 或 `mount_name` 指定上传目标，并且 Dataset/Recording 列表可以按 asset/mount 过滤，前端数据选择器可以围绕“当前 Study 挂载的数据资产”来取数。

Dataset Asset 状态治理也补了第一层保护：`quarantined` 对普通用户不可见，不可挂载，也不可作为上传目标；只有管理员可以设置隔离状态。后续仍需要补更完整的下架流程、通知机制和治理后台。

### Study API 与数据库

Study/Project API 的基础对接是较好的。成员权限、can_run、settings 都能写入数据库。

主要剩余问题是两个：

1. settings 还没有完全变成运行时事实源。
2. purge 虽已增加数据阻断，但仍保留“无阻断数据时永久删除”的管理员能力。

`study_settings` 如果只是保存配置，但 LoadData、Run、Artifact retention 不读它，就会让前端误以为设置已经生效。本轮已经让 LoadData 默认过滤读取 `study_settings.default_dataset_filter`；下一步应继续让 Run 并发策略和 Artifact retention 默认策略读取 settings。

purge 则建议继续保持非常谨慎。当前实现已经在存在 Dataset、Run、Artifact、Run dependency 时阻断永久删除并写入审计，但数据库中多个关键表还是 `ON DELETE CASCADE`；这个 API 仍应该只作为平台管理员治理能力，而不是普通业务流程。

### Pipeline API 与数据库

Pipeline CRUD 基本能对上 `pipeline_definitions`，本轮已补齐 Pipeline create/update/delete 的审计写入。

当前已有：

- version 字段。
- expected_version 可选检查。
- status 逻辑删除。

剩余缺口是：

- expected_version 可选。
- DB 和 API 已对齐 `draft`，但 draft 的产品语义还需要前端工作流进一步明确。

建议下一步考虑是否强制 `expected_version`，避免多人编辑时前端漏传版本导致覆盖。

### Run API 与数据库

Run 对接是当前比较完整的一块，尤其是 Run detail 已经能返回 inputs、dependencies、tasks、node_runs、artifacts。

但仍有一个关键缺口：

1. `pipeline_run_dependencies` 表已经能通过 API 输出，但还没有被运行时自动写入。

这个问题和“可追溯”和“避免污染结果”直接相关，优先级仍然较高。Artifact 逻辑删除已经在 list/preview 层补了默认排除和预览阻断。

## 5. 推荐后续修复顺序

### 第一批：直接影响追溯事实源

1. 运行时写入 `pipeline_run_dependencies`。
2. 明确“上游 Artifact 作为输入”的节点契约。
3. 增加依赖存在时的 Run/Artifact 清理保护。

### 第二批：让已有配置真正生效

1. Artifact 创建和清理读取 `study_settings.artifact_retention_policy`。
2. Run 并发策略读取 `study_settings.run_policy`。
3. 将 settings 生效情况写入 Run manifest 或 Run detail，便于追溯。

### 第三批：协作治理

1. Task cancel/retry。
2. Task cancel/retry 同步 Run 状态、Celery revoke、锁释放和审计。
3. Dataset Asset 下架/隔离流程补通知、原因、审批记录。

### 第四批：体验和维护

1. `/studies` API alias。
2. Dataset Asset create-and-mount 组合接口。
3. 强制或半强制 Pipeline update 的 `expected_version`。
4. 跨 Dataset Asset 同名 subject/session/task/run 的唯一约束策略。

## 6. 验证结果

已完成静态和轻量验证：

```bash
python -m compileall app alembic
python -m pytest -q
```

结果：

- `compileall` 通过。
- `pytest` 通过：`15 passed`，当前仍有 17 个 `datetime.utcnow()` 弃用警告。
- SQLAlchemy mapper 检查通过：`mapper-ok`。

未完成验证：

- 本地环境没有安装真实 `fastapi`，无法启动 app 或生成 OpenAPI 做路由级验证。
- 未连接真实 PostgreSQL 执行 schema 和 migration。
- 未跑真实上传、Pipeline Run、Celery、Artifact preview 端到端链路。

## 7. 最终判断

当前 API 与数据库不是“断裂”的状态，MVP 主线已经能走通；真正的问题是，一些新建出来的数据库能力还没有被 API 和运行时完整消费。

最需要警惕的不是表缺不缺，而是这几条连接：

1. 上传 API 是否能明确写入某个 Dataset Asset。
2. 数据选择 API 是否能按 Study Mount / Dataset Asset 快速筛选。
3. Study Settings 是否真的影响 LoadData、Run、Artifact。
4. Run dependency 是否真的写入并保护下游结果。
5. Artifact deleted 是否真的在 API 层不可见或不可用。

这些连起来之后，数据库设计才会真正服务于“多人协作、可追溯、避免污染结果”的目标。

## 8. 2026-05-21 修复更新

本轮已按问题清单做了一次低风险修复，重点优先处理“API 已有数据库支撑但没接上”的部分。

### 已修复或部分修复

| 编号 | 当前状态 | 本轮处理 |
| --- | --- | --- |
| API-DB-DS-01 | 已修复 MVP 版 | `/datasets/import` 增加可选 `dataset_asset_id` 和 `mount_name`，上传可指定目标 Dataset Asset / Mount；未指定时仍使用默认 working asset。 |
| API-DB-DS-02 | 已修复 | 默认 `working` mount 如果已指向其他 Dataset Asset，会返回冲突；如果指向默认 asset 但被停用，会恢复为 active，避免上传目标和 LoadData mount 漂移。 |
| API-DB-DS-03 | 已修复 MVP 版 | 增加 `PATCH /api/v1/dataset-assets/{asset_id}`，支持更新名称、描述、状态、可见性和 metadata。 |
| API-DB-DS-04 | 已修复 MVP 版 | `quarantined` 对普通用户不可见；不可挂载、不可作为上传目标；只有管理员可隔离 Dataset Asset。 |
| API-DB-DS-05 | 已修复 | `/datasets` 和 `/recordings` 支持 `dataset_asset_id`、`mount_id`、`mount_name` 过滤。 |
| API-DB-DS-06 | 已修复 | 增加 `/datasets/{dataset_id}/files` 和 `/recordings/{recording_id}/files`，支持 `file_role` 过滤。 |
| API-DB-DS-07 | 已修复 MVP 版 | 创建/更新 Study Mount 时校验 `selection_json.dataset_filter` 的基本结构。 |
| API-DB-DS-09 | 部分修复 | 上传 checksum 去重改为目标 Dataset Asset 范围；但 subject/session/task/run 仍受 Project 级唯一约束限制。 |
| API-DB-ST-01 | 部分修复 | `project purge` 前检查 Dataset、Run、Artifact、Run dependency；存在数据时阻止普通永久删除并记录 `project.purge_blocked`。 |
| API-DB-ST-02 | 部分修复 | LoadData 默认过滤会读取 `study_settings.default_dataset_filter`；Run 并发策略和 Artifact retention 默认策略仍待接入。 |
| API-DB-PL-01 | 已修复 | Pipeline create/update/delete 写入 `audit_events`。 |
| API-DB-PL-03 | 已修复 | Pipeline update API 允许 `draft` 状态，和数据库枚举对齐。 |
| API-DB-RUN-01 | 部分修复 | Run detail 增加 dependencies 输出；运行时自动写入依赖仍待实现。 |
| API-DB-RUN-02 | 已修复 | LoadData resolve 返回 `resolved_filter`，Run selector snapshot 的 metadata 记录解析后的过滤条件。 |
| API-DB-RUN-03 | 已修复 MVP 版 | Run 创建前执行 Pipeline validation；严重输入错误直接返回 422，不再先创建 queued Run。 |
| API-DB-RUN-04 | 已修复 | Artifact 列表默认排除 `deleted`，可通过 `include_deleted=true` 查看；deleted Artifact 预览返回 409。 |
| API-DB-TASK-02 | 已修复 | Task 列表 `status` 参数改为枚举类型。 |
| API-DB-GOV-01 | 部分修复 | 新增 Pipeline CRUD、Dataset Asset 更新、project purge blocked 等审计；Task cancel/retry 等未实现接口暂无审计。 |

### 本轮新增或变化的 API

Dataset Asset：

- `PATCH /api/v1/dataset-assets/{asset_id}`

Dataset / Recording 文件索引：

- `GET /api/v1/projects/{project_id}/datasets/{dataset_id}/files`
- `GET /api/v1/projects/{project_id}/recordings/{recording_id}/files`

Dataset / Recording 列表过滤：

- `GET /api/v1/projects/{project_id}/datasets?dataset_asset_id=&mount_id=&mount_name=`
- `GET /api/v1/projects/{project_id}/recordings?dataset_asset_id=&mount_id=&mount_name=`

上传目标：

- `POST /api/v1/projects/{project_id}/datasets/import`
- 新增表单字段：`dataset_asset_id`、`mount_name`

Artifact：

- `GET /api/v1/projects/{project_id}/pipeline-runs/{run_id}/artifacts?include_deleted=true`

Run detail：

- `GET /api/v1/projects/{project_id}/pipeline-runs/{run_id}`
- 返回体新增 `dependencies`

### 仍未解决

| 编号 | 原因 | 后续建议 |
| --- | --- | --- |
| API-DB-DS-08 | Dataset Asset 创建接口是平台级入口，没有 Study 上下文，不能安全地自动挂载。 | 增加 Study 内创建并挂载接口，例如 `/projects/{project_id}/dataset-assets`。 |
| API-DB-DS-09 | Project 级 BIDS entity 唯一约束仍限制不同 Dataset Asset 使用同一 subject/session/task/run。 | 如果确实需要同一 Study 内多个 asset 保存同名实体，需要调整唯一约束到 `(project_id, dataset_asset_id, subject_id, session, task, run)`。 |
| API-DB-ST-02 | Run policy 和 Artifact retention policy 涉及运行锁和后台清理策略，未在本轮强行接入。 | 下一步让 Run 创建读取 `study_settings.run_policy`，ArtifactStore 读取 retention 默认策略。 |
| API-DB-ST-03 | `/studies` alias 会影响前端和文档路径，不适合顺手加。 | 前端准备切换时再加兼容 alias。 |
| API-DB-PL-02 | 强制 `expected_version` 可能破坏现有调用。 | 先让前端必传，再后端强制。 |
| API-DB-RUN-01 | 依赖自动写入需要明确“上游 Artifact 作为输入”的节点契约。 | 在节点输入解析层写入 `pipeline_run_dependencies`，不要仅靠推断。 |
| API-DB-TASK-01 | cancel/retry 需要同步 Celery revoke、Run 状态、锁释放和审计。 | 单独做任务控制设计和回归。 |

### 本轮验证

已运行：

```bash
python -m compileall app alembic
python -m pytest -q
```

结果：

- `compileall` 通过。
- `pytest` 通过：`15 passed`，当前仍有 17 个 `datetime.utcnow()` 弃用警告。
- SQLAlchemy mapper 检查通过：`mapper-ok`。
- 静态路由统计更新为 54 个 API。

仍未验证：

- 本地环境仍没有真实 `fastapi` 包，未启动服务生成 OpenAPI。
- 未连接真实 PostgreSQL 执行 schema/migration。
- 未跑真实上传、Celery Pipeline Run、Artifact preview 端到端链路。
