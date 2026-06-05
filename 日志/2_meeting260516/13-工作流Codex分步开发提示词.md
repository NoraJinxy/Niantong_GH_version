# 工作流 Codex 分步开发提示词

> 文档性质：工作流专题讨论稿，可随方案讨论随时修改。  
> 本文是 `08-工作流当前进度与开发路线.md` 的执行手册，专门记录每一步在 Codex 中可以如何提示。  
> 当前代码位置默认省略 `elys_version1/` 前缀。

## 使用方式

建议一次只执行一个 Step。每个 Step 完成后，先让 Codex 跑测试或说明未能测试的原因，再进入下一步。

提示词中的路径可以直接复制。若代码状态已变化，让 Codex 先重新审计相关文件，再按目标调整。

## Step 0：基线审计

目标：确认当前工作流模块现状，建立开发前基线，不做功能修改。

修改范围：原则上不修改代码；可新增一份审计记录到 `2_meeting260516`，也可只让 Codex 输出结论。

实现要点：

- 检查 `backend/app/routers/pipelines.py`。
- 检查 `backend/app/schemas/pipeline.py`。
- 检查 `backend/app/models/project.py`。
- 检查 `backend/app/pipeline/load_data.py`。
- 检查 `frontend/elys-web/src/views/PipelinePage.vue`。
- 检查 `frontend/elys-web/src/api/pipelines.ts`。
- 检查 `database/init.sql` 和 `backend/app/services/schema_compat.py`。

测试：

- 后端至少运行 Python 导入检查或现有测试。
- 前端运行 `npm run build`。
- 如果环境无法跑服务，说明原因并列出静态检查结果。

Codex 提示词：

```text
请基于 elys_version1 当前代码，审计工作流模块现状，不要做功能修改。

重点检查：
1. backend/app/routers/pipelines.py 当前 validate/run/load-data 的实现边界。
2. backend/app/schemas/pipeline.py 和 backend/app/models/project.py 中 pipeline 相关 schema/model。
3. backend/app/pipeline/load_data.py 和 backend/app/pipeline/nodes/*.json。
4. frontend/elys-web/src/views/PipelinePage.vue、src/api/pipelines.ts、src/types/index.ts。
5. database/init.sql 和 backend/app/services/schema_compat.py。

请输出：
- 当前已经实现的能力。
- 当前缺失的能力。
- 后续新增 pipeline_node_runs、pipeline_artifacts、PipelineExecutor 时的影响范围。
- 你实际运行了哪些检查或测试。

不要重构，不要改 UI，不要引入 Celery。
```

完成标准：

- 明确当前 `/run` 只真实执行 LoadData。
- 明确普通节点执行器未实现。
- 明确 node_run/artifact/异步/缓存/人工节点均未实现。

Step 0 实际审计记录（2026-05-17，Step 1 前基线）：

- 审计对象：`backend/app/routers/pipelines.py`、`backend/app/schemas/pipeline.py`、`backend/app/models/project.py`、`backend/app/pipeline/load_data.py`、`backend/app/pipeline/nodes/*.json`、`frontend/elys-web/src/views/PipelinePage.vue`、`frontend/elys-web/src/api/pipelines.ts`、`frontend/elys-web/src/types/index.ts`、`database/init.sql`、`backend/app/services/schema_compat.py`。
- 已确认能力：Pipeline CRUD、节点库、保存、validate、run list、LoadData resolve 已接通；`validate_definition()` 已覆盖结构、端口、必填输入、环路和 LoadData 数据解析；`pipeline_runs` 已存在。
- 已确认边界：`/run` 当前是同步 `synchronous-preflight`，只真实执行 `eeg/data/load`；其它节点统一返回 `PIPELINE_NODE_EXECUTOR_NOT_IMPLEMENTED`。
- 已确认缺口：Step 0 基线时没有 `PipelineExecutor`、`pipeline_node_runs`、`pipeline_artifacts`、run detail API、artifact lineage、普通 EEG 节点执行器和前端节点级状态展示。
- 后续影响范围：数据库 init/schema compat、SQLAlchemy model、Pydantic schema、pipeline router/service、`backend/app/pipeline/*` 执行器模块、前端 API/types 和 `PipelinePage.vue` 的最小状态展示。
- 实际检查：Python AST 语法检查通过 5 个目标文件；NodeRegistry 成功加载 10 个 NodeSpec；`rg` 在 Step 0 基线时确认未发现 `pipeline_node_runs`、`pipeline_artifacts`、`PipelineExecutor` 实现。
- 未完成检查：后端 import smoke test 因当前 Python 环境缺少 `fastapi` 未能执行；前端 `vue-tsc --noEmit` 因 `frontend/elys-web` 缺少 `tsconfig.json` 未能进入类型检查；当前目录不是 git 工作区，无法用 `git status` 核对。
- 本次审计未修改代码、未改 UI、未引入 Celery。

## Step 1：新增节点级运行表和 artifact 表

目标：建立后续工作流运行的事实层。

修改范围：

- `database/init.sql`
- `backend/app/models/project.py`
- `backend/app/schemas/pipeline.py`
- `backend/app/services/schema_compat.py`
- 必要时更新 `backend/app/models/__init__.py`

实现要点：

- 新增 `PipelineNodeRun` SQLAlchemy model。
- 新增 `PipelineArtifact` SQLAlchemy model。
- 新增 Pydantic response schema。
- 扩展 `pipeline_runs.status` 语义，但要注意已有 CHECK 约束兼容。
- `schema_compat.py` 要能在没有 Alembic 的情况下幂等补表。
- 不要先写完整 executor，只做数据结构。

测试：

- Python 导入 model/schema。
- 如果有数据库连接，运行 schema compatibility。
- 至少静态检查 SQL 语法和枚举状态。

Codex 提示词：

```text
请在 elys_version1 中为工作流新增节点级运行记录和产物索引的数据结构。

目标：
1. 新增 pipeline_node_runs 表和 PipelineNodeRun model。
2. 新增 pipeline_artifacts 表和 PipelineArtifact model。
3. 在 backend/app/schemas/pipeline.py 中增加 PipelineNodeRunResponse、PipelineArtifactResponse、PipelineRunDetailResponse 等必要 schema。
4. 更新 backend/app/services/schema_compat.py，使没有 Alembic 时也能幂等创建新表和索引。
5. 保持现有 pipeline_definitions、pipeline_runs API 行为不变。

建议字段：
- pipeline_node_runs: id, run_id, project_id, pipeline_id, node_id, node_type, node_title, status, topo_index, params_json, input_json, output_json, input_hash, params_hash, node_hash, trace_code, error_json, log_tail, started_at, finished_at, duration_ms。
- pipeline_artifacts: id, project_id, run_id, node_run_id, source_dataset_id, artifact_type, data_type, storage_path, file_size, checksum, metadata_json, preview_json, content_hash, created_at。

请补充必要索引：
- node_runs: run_id/topo_index, project_id/status。
- artifacts: run_id, node_run_id, project_id/artifact_type。

测试：
- 运行能证明 model/schema 可导入的命令。
- 如果无法连接数据库，请至少运行 Python 编译检查并说明未执行 DB 检查的原因。

不要实现执行器，不要改前端 UI。
```

完成标准：

- 新表和模型存在。
- schema 可被 API 使用。
- 现有 pipeline API 不破坏。

本次执行记录（2026-05-17）：

- 已完成：`database/init.sql` 新增 `pipeline_node_runs`、`pipeline_artifacts` 和必要索引。
- 已完成：`backend/app/models/project.py` 新增 `PipelineNodeRun`、`PipelineArtifact`，并给 `PipelineRun` 增加 `node_runs`、`artifacts` 关系。
- 已完成：`backend/app/models/__init__.py` 导出新增 model。
- 已完成：`backend/app/schemas/pipeline.py` 新增 `PipelineNodeRunResponse`、`PipelineArtifactResponse`、`PipelineRunDetailResponse`、`PipelineNodeRunListResponse`、`PipelineArtifactListResponse`。
- 已完成：`backend/app/schemas/__init__.py` 导出新增 schema。
- 已完成：`backend/app/services/schema_compat.py` 幂等创建新表和索引。
- 保持不变：没有实现执行器，没有改 `/run` 行为，没有改前端 UI，没有引入 Celery。
- 注意：本次没有扩展 `pipeline_runs.status`，以避免和现有数据库 CHECK 约束产生兼容风险；后续进入后台任务和状态机时再单独迁移。

实际检查：

- `python` AST 检查通过目标 5 个文件。
- `python -m py_compile` 通过目标 5 个文件。
- schema import 通过：`PipelineNodeRunResponse`、`PipelineArtifactResponse`、`PipelineRunDetailResponse`。
- model import 通过：测试脚本 mock `app.database.Base` 后可导入 `PipelineNodeRun`、`PipelineArtifact`；直接导入 `app.models` 会因当前 Python 环境缺少 `psycopg2` 导致 PostgreSQL engine 初始化失败。
- DB schema compatibility 未执行：当前环境没有可用 PostgreSQL 连接，且缺少 `psycopg2`。

## Step 2：拆分校验器和拓扑排序

目标：把工作流校验从 router 中拆出，为 executor 做准备；保持行为不变。

修改范围：

- `backend/app/routers/pipelines.py`
- 新增 `backend/app/pipeline/validator.py`
- 必要时新增 `backend/app/pipeline/types.py` 或 `errors.py`

实现要点：

- 移出 `port_types_compatible()`。
- 移出 `validate_load_data_params()`。
- 移出 `validate_definition()`。
- 移出 `topological_node_order()`。
- Router 只调用 validator。
- 不改变错误码和 response 结构。

测试：

- 现有 validate API 行为不变。
- 对空 graph、端口错误、环路、LoadData 参数错误做最小测试。

Codex 提示词：

```text
请把工作流校验逻辑从 backend/app/routers/pipelines.py 拆到 backend/app/pipeline/validator.py，保持外部行为不变。

要求：
1. validate_definition、topological_node_order、port_types_compatible、validate_load_data_params 移到 validator.py。
2. routers/pipelines.py 只保留 API 编排和数据库查询。
3. 所有现有错误码、PipelineValidationResponse 结构、LoadData 解析逻辑保持兼容。
4. 不要实现新节点执行器，不要新增异步任务。

请补充或运行测试：
- 空 graph 返回 NODES_EMPTY。
- 缺必需输入返回 INPUT_REQUIRED。
- 端口类型不匹配返回 LINK_PORT_TYPE_MISMATCH。
- graph 中有环返回 PIPELINE_CYCLE。

最后说明你改了哪些文件、如何确认行为没有变化。
```

完成标准：

- Router 变薄。
- 校验相关函数有独立模块。
- validate API 可继续使用。

本次执行记录（2026-05-17）：

- 已完成：新增 `backend/app/pipeline/validator.py`。
- 已完成：将 `validate_definition()`、`topological_node_order()`、`port_types_compatible()`、`validate_load_data_params()` 移入 validator。
- 已完成：`backend/app/routers/pipelines.py` 改为从 validator 导入校验和拓扑排序，删除内联校验函数。
- 保持不变：`PipelineValidationResponse` 结构、现有错误码、LoadData 参数校验和真实数据解析逻辑保持兼容。
- 保持不变：未实现新节点执行器，未新增异步任务，未改前端 UI。

实际检查：

- `python -m py_compile backend/app/routers/pipelines.py backend/app/pipeline/validator.py` 通过。
- validator import 通过：`topological_node_order`、`validate_definition`、`port_types_compatible`、`validate_load_data_params`。
- 空 graph 返回 `NODES_EMPTY`。
- 缺必需输入返回 `INPUT_REQUIRED`。
- 端口类型不匹配返回 `LINK_PORT_TYPE_MISMATCH`；按既有逻辑，该无效连线不计入必需输入，因此同一结果也包含 `INPUT_REQUIRED`。
- graph 中有环返回 `PIPELINE_CYCLE`。

## Step 3：定义 ArtifactStore 和 NodeOutput 契约

目标：统一节点输出、文件保存、metadata、checksum 和 artifact 登记规则。

修改范围：

- 新增 `backend/app/pipeline/artifacts.py`
- 新增 `backend/app/pipeline/contracts.py` 或 `types.py`
- 必要时补 `backend/app/pipeline/hash.py`
- 不必接前端

实现要点：

- 定义 `NodeOutput`、`NodeInput`、`NodeExecutionContext`。
- ArtifactStore 支持创建 run 工作目录。
- 支持写 JSON metadata。
- 支持临时目录写入后原子发布。
- 支持 sha256 checksum。
- 支持登记 `PipelineArtifact` 行。
- 先支持 `data_infos` 和普通文件引用，不必一次覆盖所有 MNE 类型。

测试：

- 用临时目录保存一个 JSON artifact。
- 验证 checksum、storage_path、metadata_json。
- 验证失败时不登记半成品 artifact。

Codex 提示词：

```text
请为工作流执行器增加统一的节点输出和 ArtifactStore 基础设施。

目标：
1. 新增 backend/app/pipeline/contracts.py，定义 NodeInput、NodeOutput、NodeExecutionContext 等轻量 dataclass。
2. 新增 backend/app/pipeline/artifacts.py，实现 ArtifactStore：
   - 根据 project.bids_root 或项目根目录创建 pipeline_runs/{run_id}/nodes/{node_id}/ 目录。
   - 写入临时文件或临时目录。
   - 计算 sha256。
   - 原子发布到最终 storage_path。
   - 写入 PipelineArtifact。
   - 返回可放进 data_infos/output_json 的 artifact 摘要。
3. 先支持 JSON metadata 和普通文件路径，不需要完成所有 MNE 类型。
4. 不改前端。

测试：
- 用 tempfile 构造一个 ArtifactStore 单元测试或最小脚本。
- 验证 artifact 文件存在、checksum 正确、metadata_json 可读。
- 验证异常时不会留下已登记但文件缺失的 artifact。

请保持实现简洁，避免引入大范围重构。
```

完成标准：

- 后续 executor 可以通过 ArtifactStore 保存输出。
- 输出契约和 artifact DB 记录一致。

本次执行记录（2026-05-17）：

- 已完成：新增 `backend/app/pipeline/contracts.py`，定义 `NodeInput`、`ArtifactSummary`、`NodeOutput`、`NodeExecutionContext`。
- 已完成：新增 `backend/app/pipeline/artifacts.py`，实现 `ArtifactStore`，按项目根目录创建 `pipeline_runs/{run_id}/nodes/{node_id}/`，支持 JSON metadata、普通文件、目录发布、sha256、原子发布、`PipelineArtifact` 登记和 artifact 摘要返回。
- 保持边界：未实现 `PipelineExecutor`、未接 `NodeDispatcher`、未改前端、未引入异步任务、未完成 Raw/Epochs/Evoked 等 MNE 类型保存。
- 实际检查：`python -m py_compile backend/app/pipeline/contracts.py backend/app/pipeline/artifacts.py` 通过。
- 实际检查：contract import 通过，可导入 `NodeInput`、`NodeOutput`、`NodeExecutionContext`、`ArtifactSummary`、`ArtifactStore`。
- 实际检查：tempfile 最小脚本通过，验证 artifact 文件存在、checksum 正确、`metadata_json`/`preview_json` 可读、普通文件发布可用、目录发布可用、writer 异常不登记 artifact、模拟 flush 异常时清理已发布文件。
- 未执行真实 DB 检查：当前环境未提供可用 PostgreSQL 连接，且真实 DB 栈仍受本机依赖限制；本步骤用 fake DB session 验证 ArtifactStore 自身契约。

## Step 4：新增 run detail、node run、artifact 查询 API

目标：给前端提供后端状态事实源。

修改范围：

- `backend/app/routers/pipelines.py` 或新增 `backend/app/routers/pipeline_runs.py`
- `backend/app/schemas/pipeline.py`
- `frontend/elys-web/src/api/pipelines.ts`
- `frontend/elys-web/src/types/index.ts`

实现要点：

- 新增 `GET /projects/{project_id}/pipeline-runs/{run_id}`。
- 新增 `GET /projects/{project_id}/pipeline-runs/{run_id}/nodes`。
- 新增 `GET /projects/{project_id}/pipeline-runs/{run_id}/artifacts`。
- 保持项目权限检查。
- 前端先只封装 API 和类型，不要求 UI 接入。

测试：

- 无权限/不存在项目/不存在 run 返回正确错误。
- 空 node_runs/artifacts 返回空数组。
- API response 字段符合前端类型。

Codex 提示词：

```text
请为工作流运行新增查询 API 和前端 API 封装。

后端目标：
1. GET /api/v1/projects/{project_id}/pipeline-runs/{run_id}
2. GET /api/v1/projects/{project_id}/pipeline-runs/{run_id}/nodes
3. GET /api/v1/projects/{project_id}/pipeline-runs/{run_id}/artifacts
4. 复用现有项目权限检查，确保 run 属于该 project。
5. 空 node_run/artifact 时返回空列表，不报错。

前端目标：
1. 在 frontend/elys-web/src/types/index.ts 增加 PipelineRunDetail、PipelineNodeRun、PipelineArtifact 等类型。
2. 在 frontend/elys-web/src/api/pipelines.ts 增加 getRun、listRunNodes、listRunArtifacts。

暂时不要改 PipelinePage.vue UI。

测试：
- 后端导入检查。
- 如果有测试环境，请模拟一个 run 查询空 node/artifact。
- 前端 npm run build。
```

完成标准：

- 前端可以调用新 API。
- 下一步 UI 有状态数据来源。

本次执行记录（2026-05-17）：

- 已完成：`backend/app/routers/pipelines.py` 新增 `GET /api/v1/projects/{project_id}/pipeline-runs/{run_id}`、`GET /api/v1/projects/{project_id}/pipeline-runs/{run_id}/nodes`、`GET /api/v1/projects/{project_id}/pipeline-runs/{run_id}/artifacts`。
- 已完成：新 API 复用项目读权限，并通过 `PipelineRun.project_id == project.id` 与 `run_id` 共同约束 run 归属。
- 已完成：空 `pipeline_node_runs` / `pipeline_artifacts` 返回空数组，不报错。
- 已完成：`frontend/elys-web/src/types/index.ts` 增加 `PipelineRunDetail`、`PipelineNodeRun`、`PipelineArtifact`、列表 response 类型。
- 已完成：`frontend/elys-web/src/api/pipelines.ts` 增加 `getRun()`、`listRunNodes()`、`listRunArtifacts()`。
- 保持边界：未修改 `PipelinePage.vue`，未实现 executor，未新增 preview/download/resume/cancel/run-from API。
- 实际检查：`python -m py_compile backend/app/routers/pipelines.py backend/app/schemas/pipeline.py` 通过。
- 实际检查：schema import 通过；直接 router import 因当前环境缺少 `fastapi` 未通过，随后 mock `fastapi` 和 DB 初始化后 router import 通过，并确认 3 个新路由注册。
- 实际检查：fake DB 模拟 run 存在但无 node/artifact 时，run detail、nodes、artifacts 均返回空数组。
- 实际检查：`npm run build` 通过；仅有 Vite CJS、litegraph eval、chunk size 既有警告。

## Step 5：实现 PipelineExecutor 骨架，只真实执行 LoadData

目标：把当前同步 LoadData 运行迁移到 executor，并写入 node_run。

修改范围：

- 新增 `backend/app/pipeline/executor.py`
- 新增 `backend/app/pipeline/dispatcher.py`
- `backend/app/routers/pipelines.py`
- `backend/app/schemas/pipeline.py`

实现要点：

- `PipelineExecutor.execute()` 接收 project、pipeline、run，并持有 db。
- 创建每个节点的 `PipelineNodeRun`，状态初始 pending。
- 按拓扑顺序执行。
- LoadData 调 `resolve_load_data_selection()`，写 node_run success/failed。
- 未实现节点写 node_run failed，错误码 `PIPELINE_NODE_EXECUTOR_NOT_IMPLEMENTED`。
- run.status 由 node_run 聚合。
- 保留 `pipeline_runs.result_json` 兼容摘要。

测试：

- 纯 LoadData 工作流 run completed。
- LoadData + FIR 工作流 run failed，FIR node_run failed。
- definition_snapshot 保持。
- run_seq 自增。

Codex 提示词：

```text
请实现新版 PipelineExecutor 骨架，把现有同步 /run 中的执行逻辑从 router 迁移出来，但第一版只真实执行 LoadData。

要求：
1. 新增 backend/app/pipeline/executor.py，提供 PipelineExecutor。
2. 新增 backend/app/pipeline/dispatcher.py，预留按 node_type 分发的结构。
3. /projects/{project_id}/pipelines/{pipeline_id}/run 仍可同步返回 PipelineRunResponse，但内部调用 PipelineExecutor。
4. 每个图节点都创建 pipeline_node_runs。
5. eeg/data/load 调用 resolve_load_data_selection，成功时 node_run.status=success，输出 data_infos 写入 output_json。
6. 其它节点 node_run.status=failed，error_json 使用 PIPELINE_NODE_EXECUTOR_NOT_IMPLEMENTED。
7. run.status 根据节点聚合，纯 LoadData 可 completed，含未实现节点为 failed。
8. 保留 result_json 中的 node_results/data_infos_by_node 兼容现有前端。

测试：
- 构造或使用现有 API 验证纯 LoadData 工作流完成。
- 验证含 FIR 节点的工作流会失败，并且失败落在对应 node_run。
- 验证 run_seq 和 definition_snapshot 仍正确。

不要接 Celery，不要实现 FIR/ERP。
```

完成标准：

- 运行事实从 run 级扩展到 node 级。
- Router 不再直接承担执行细节。

本次执行记录（2026-05-17）：

- 已完成：新增 `backend/app/pipeline/executor.py`，提供 `PipelineExecutor`，负责校验、拓扑排序、创建每个图节点的 `PipelineNodeRun`、执行节点、聚合 run 状态。
- 已完成：新增 `backend/app/pipeline/dispatcher.py`，提供 `NodeDispatcher`、`NodeDispatchResult`、`NodeExecutorNotImplemented`；当前只注册 `eeg/data/load`。
- 已完成：`backend/app/routers/pipelines.py` 删除旧的内联 `execute_pipeline_run()`；Step 5 当时为创建 `PipelineRun` 后同步调用 `PipelineExecutor`，Step 10 已改为后台运行过渡版。
- 已完成：纯 LoadData 工作流成功时 `node_run.status=success`，`output_json.data_infos` 写入 LoadData 解析结果，`run.status=completed`。
- 已完成：含 FIR 等未实现节点时，对应 `node_run.status=failed`，`error_json.errors[0].code=PIPELINE_NODE_EXECUTOR_NOT_IMPLEMENTED`，`run.status=failed`。
- 已完成：保留 `result_json.node_results`、`result_json.data_infos_by_node` 兼容现有前端，并保留 `mode=synchronous-preflight`。
- 保持边界：未接 Celery/Redis，未实现 FIR/ERP，未调用 `ArtifactStore`，未改前端 UI。
- 实际检查：`python -m py_compile backend/app/routers/pipelines.py backend/app/pipeline/executor.py backend/app/pipeline/dispatcher.py backend/app/pipeline/validator.py` 通过。
- 实际检查：纯 LoadData executor mock 通过，验证 run completed、node_run success、data_infos 写入 output_json。
- 实际检查：LoadData + FIR executor mock 通过，验证 FIR node_run failed、错误码正确、run failed。
- 实际检查：mocked `/run` route 通过，验证 run_seq、pipeline_version、definition_snapshot 仍正确，并确认内部写 node_run。
- 实际检查：`npm run build` 通过；仅有 Vite CJS、litegraph eval、chunk size 既有警告。

## Step 6：建立 MNE IO 与 synthetic 测试工具

目标：为真实 EEG 节点执行准备文件驱动基础。

修改范围：

- 新增 `backend/app/engine/io.py` 或 `backend/app/engine/io/fif.py`
- 新增 `backend/app/engine/testing.py` 或测试 helper
- 必要时新增 `backend/app/engine/__init__.py`

实现要点：

- 读取 `LoadDataDataInfo.fif_abs_path`。
- 返回 MNE Raw，必要时 preload。
- 生成 Raw/Epochs/Evoked 的 metadata 摘要。
- 保存 Raw/Epochs/Evoked 的函数可以先放 ArtifactStore 或 engine io 中。
- 使用 synthetic Raw 写测试，避免依赖真实数据。

测试：

- synthetic Raw 保存为 FIF 后再读出。
- metadata 中包含 ch_names、n_channels、sfreq、duration。

Codex 提示词：

```text
请为工作流节点执行增加 MNE IO 基础模块和 synthetic 测试工具。

目标：
1. 新建 backend/app/engine/ 包。
2. 增加读取 FIF 的函数，例如 read_raw_from_data_info(data_info, preload=True)。
3. 增加 Raw/Epochs/Evoked metadata 摘要函数。
4. 增加保存 Raw/Epochs/Evoked 到指定路径的基础函数，命名符合 MNE 习惯。
5. 增加 synthetic Raw 构造 helper，用于后续节点测试。

要求：
- 不依赖旧版 session_manager。
- 不把大对象存进数据库。
- 文件路径必须通过 data_info/artifact 引用。

测试：
- 构造 synthetic Raw。
- 保存为 FIF。
- 再读取并验证采样率、通道数、时长。

不要实现完整 PipelineExecutor 改造，只做 IO 基础。
```

完成标准：

- 后续 FIR/Resample/Epoch 节点可以基于文件输入输出。

本次执行记录（2026-05-17）：

- 已完成：新增 `backend/app/engine/__init__.py`，建立 engine 包。
- 已完成：新增 `backend/app/engine/io.py`，实现 `read_raw_from_data_info(data_info, preload=True)`，从 `fif_abs_path` / `fif_path` 读取 FIF。
- 已完成：实现 Raw/Epochs/Evoked metadata 摘要函数：`summarize_raw()`、`summarize_epochs()`、`summarize_evoked()`、`summarize_mne_object()`。
- 已完成：实现 Raw/Epochs/Evoked 保存函数：`save_raw_fif()`、`save_epochs_fif()`、`save_evoked_fif()`，使用 MNE 习惯后缀 `*-raw.fif`、`*-epo.fif`、`*-ave.fif`。
- 已完成：新增 `backend/app/engine/testing.py`，提供 `make_synthetic_raw()`。
- 保持边界：不依赖旧版 `session_manager`，不把 MNE 大对象写入数据库，不改 `PipelineExecutor`，不实现 FIR/ERP，不改前端 UI。
- 实际检查：当前 Python 环境可导入 `mne`。
- 实际检查：`python -m py_compile backend/app/engine/__init__.py backend/app/engine/io.py backend/app/engine/testing.py` 通过。
- 实际检查：engine import 通过。
- 实际检查：synthetic Raw 保存为 FIF 后，通过 `read_raw_from_data_info({'fif_abs_path': ...})` 读回，采样率、通道数、时长验证通过。
- 实际检查：Epochs/Evoked 保存与 metadata 摘要通过。

## Step 7：实现 FIR、Resample、Re-reference 节点

目标：完成最小预处理节点。

修改范围：

- `backend/app/engine/preprocess/filters.py`
- `backend/app/engine/preprocess/resample.py`
- `backend/app/engine/preprocess/reference.py`
- `backend/app/pipeline/dispatcher.py`
- 可能调整 ArtifactStore 保存 Raw FIF

实现要点：

- 参数名与 NodeSpec 对齐。
- 每个节点接收上游 `data_infos` 或 artifact data_infos。
- 输出新的 artifact 和新的 data_infos。
- 不改写 `fifdata` 原始工作数据。
- 输出写到 run 目录或 derivatives/pipeline_runs 目录。

测试：

- synthetic Raw -> FIR。
- synthetic Raw -> Resample。
- synthetic Raw -> Re-reference。
- PipelineExecutor 跑 `LoadData -> FIR`。

Codex 提示词：

```text
请实现工作流 Phase 1 的三个预处理节点执行器：FIR Filter、Resample、Re-reference。

范围：
1. backend/app/engine/preprocess/filters.py
2. backend/app/engine/preprocess/resample.py
3. backend/app/engine/preprocess/reference.py
4. backend/app/pipeline/dispatcher.py 接入 node_type：
   - eeg/filter/fir
   - eeg/preproc/resample
   - eeg/preproc/rereference
5. 通过 ArtifactStore 保存输出 FIF，并生成派生 data_infos。

要求：
- 节点参数必须与 backend/app/pipeline/nodes/*.json 对齐。
- 输入来自上游 node output_json/data_infos，不依赖 session 变量。
- 输出不能覆盖 fifdata，只能写 pipeline artifact/derivatives。
- 每个 dataset 独立处理，单个 dataset 失败时先按节点 failed 处理，后续再做 partial policy。

测试：
- synthetic Raw 单元测试：FIR 后 Raw 可保存；Resample 后 sfreq 变化；Re-reference 后可读。
- 集成测试或最小脚本：LoadData -> FIR 生成 artifact。

不要接 ICA、Epoch、Celery、缓存。
```

完成标准：

- 至少一条 LoadData -> FIR 链路真实产生 artifact。

本次执行记录（2026-05-17）：

- 已完成：新增 `backend/app/engine/preprocess/filters.py`，提供 `run_fir_filter()`，参数与 `eeg_filter_fir.json` 对齐，支持 `bandpass`、`lowpass`、`highpass` 和 `phase`。
- 已完成：新增 `backend/app/engine/preprocess/resample.py`，提供 `run_resample()`，参数与 `eeg_preproc_resample.json` 对齐，按 `sfreq` 重采样。
- 已完成：新增 `backend/app/engine/preprocess/reference.py`，提供 `run_rereference()`，参数与 `eeg_preproc_rereference.json` 对齐，支持 average 和 selected channels。
- 已完成：新增 `backend/app/engine/preprocess/__init__.py`，导出三个预处理函数。
- 已完成：`backend/app/pipeline/dispatcher.py` 注册 `eeg/filter/fir`、`eeg/preproc/resample`、`eeg/preproc/rereference`；执行时从上游 `NodeInput.data_infos` 读 FIF，通过 ArtifactStore 写入 pipeline artifact，并生成派生 `data_infos`。
- 已完成：`backend/app/pipeline/executor.py` 增加上游 `NodeOutput` 到下游 `NodeInput` 的传递，并向节点上下文注入 `ArtifactStore`。
- 当前行为：输出写入 `pipeline_runs/{run_id}/nodes/{node_id}/`，不覆盖 `fifdata`；派生 `data_info` 包含 `artifact_id`、`artifact_storage_path`、`fif_path`、`fif_abs_path`、`checksum`、`content_hash`、`sfreq`、`n_channels`、`duration_seconds`。
- 当前失败策略：单个 dataset 失败时节点整体 failed，错误码 `PIPELINE_NODE_DATASET_FAILED`；partial policy 后续再做。
- 保持边界：未接 ICA、Epoch、Celery、缓存，未改前端 UI。
- 实际检查：`python -m py_compile backend/app/engine/preprocess/__init__.py backend/app/engine/preprocess/filters.py backend/app/engine/preprocess/resample.py backend/app/engine/preprocess/reference.py backend/app/pipeline/dispatcher.py backend/app/pipeline/executor.py` 通过。
- 实际检查：synthetic Raw -> FIR/Resample/Re-reference 通过，FIR 后 Raw 可保存，Resample 后 `sfreq` 变化，Re-reference 后可读。
- 实际检查：LoadData -> FIR dispatcher 最小脚本通过，生成 artifact 文件和派生 `data_info`。
- 实际检查：PipelineExecutor LoadData -> FIR 最小脚本通过，run completed，创建 2 条 node_run、1 条 artifact。
- 环境说明：当前本机 Python 环境缺少 `psycopg2`，直接导入真实 `app.models` 会触发数据库 driver 缺失；本次集成脚本使用 fake DB/models 隔离数据库连接，仅验证 executor/dispatcher 数据流和文件 artifact 行为。

## Step 8：实现 Epoch、ERP Average、Save Result

目标：打通第一条分析闭环。

修改范围：

- `backend/app/engine/analysis/epoching.py`
- `backend/app/engine/analysis/erp.py`
- `backend/app/pipeline/output.py`
- `backend/app/pipeline/dispatcher.py`
- `backend/app/models/project.py` 中 `AnalysisResult` 使用

实现要点：

- Epoch 从 Raw artifact 读取事件。
- ERP 从 Epochs artifact 生成 Evoked。
- Save Result 把上游 artifact 登记到 `analysis_results`。
- `eeg/analysis/erp` 输出 `evoked`，可接 `Save Result`。

测试：

- synthetic Raw 带 annotations/events。
- Epoch 输出 epochs FIF。
- ERP 输出 evoked FIF。
- Save Result 写 analysis_results。
- 完整链路 `LoadData -> FIR -> Epoch -> ERP -> Save Result`。

Codex 提示词：

```text
请实现工作流第一条真实分析链路中的 Epoch、ERP Average、Save Result。

范围：
1. 新增 backend/app/engine/analysis/epoching.py，实现 eeg/epoch/segment。
2. 新增 backend/app/engine/analysis/erp.py，实现 eeg/analysis/erp。
3. 新增或完善 backend/app/pipeline/output.py，实现 eeg/output/save_result。
4. 更新 backend/app/pipeline/dispatcher.py。
5. 通过 ArtifactStore 保存 epochs/evoked 输出。
6. Save Result 将结果登记到 analysis_results，并保留 artifact_id/run_id/node_run_id 的追溯信息。

要求：
- 参数与 NodeSpec 对齐：event_id、tmin、tmax、baseline_start、baseline_end、condition、channels。
- 事件缺失要返回节点级错误，不要静默成功。
- 输出 data_infos 必须包含 artifact_id、source_dataset_id、data_type、storage_path、content_hash。

测试：
- 使用 synthetic Raw + annotations/events。
- 单测 Epoch 输出 Epochs。
- 单测 ERP 输出 Evoked。
- 集成测试 LoadData -> FIR -> Epoch -> ERP -> Save Result。

不要做 ICA，不要做缓存，不要接 Celery。
```

完成标准：

- 第一条完整 EEG 链路可在测试数据上跑通。

本次执行记录（2026-05-18）：

- 已完成：新增 `backend/app/engine/analysis/epoching.py`，提供 `run_epoch_segment()`，参数与 `eeg_epoch_segment.json` 对齐，支持 `event_id`、`tmin`、`tmax`、`baseline_start`、`baseline_end`。
- 已完成：新增 `backend/app/engine/analysis/erp.py`，提供 `run_erp_average()`，参数与 `eeg_analysis_erp.json` 对齐，支持 `condition` 和 `channels`。
- 已完成：新增 `backend/app/engine/analysis/__init__.py`。
- 已完成：`backend/app/engine/io.py` 新增 `read_epochs_from_data_info()`、`read_evoked_from_data_info()`。
- 已完成：新增 `backend/app/pipeline/output.py`，提供 `run_save_result()`，将上游 analysis artifact 登记到 `analysis_results`。
- 已完成：`backend/app/pipeline/dispatcher.py` 注册 `eeg/epoch/segment`、`eeg/analysis/erp`、`eeg/output/save_result`；Epochs/Evoked 通过 ArtifactStore 保存，并返回派生 `data_infos`。
- 已完成：`backend/app/models/project.py`、`database/init.sql`、`backend/app/services/schema_compat.py` 为 `analysis_results` 补齐 `run_id`、`node_run_id`、`artifact_id`、`result_name` 追溯字段和索引。
- 当前行为：输出 `data_infos` 包含 `artifact_id`、`source_dataset_id`、`data_type`、`storage_path`、`content_hash`；Save Result 会补 `analysis_result_id`。
- 当前错误策略：事件或 condition 缺失时节点 failed，不静默成功；缺失事件最小脚本验证错误码为 `PIPELINE_NODE_DATASET_FAILED`。
- 保持边界：未做 ICA、未做缓存、未接 Celery，未改前端 UI。
- 实际检查：`python -m py_compile backend/app/engine/io.py backend/app/engine/analysis/__init__.py backend/app/engine/analysis/epoching.py backend/app/engine/analysis/erp.py backend/app/pipeline/output.py backend/app/pipeline/dispatcher.py backend/app/models/project.py backend/app/services/schema_compat.py` 通过。
- 实际检查：synthetic Raw + annotations/events 生成 Epochs、ERP Evoked，并保存/读回通过。
- 实际检查：`LoadData -> FIR -> Epoch -> ERP -> Save Result` fake DB/models 集成脚本通过，run completed，生成 3 个 artifact，登记 1 条 `analysis_result`。
- 环境说明：当前本机 Python 环境缺少 `psycopg2`，真实 DB 导入/连接检查未执行；集成脚本使用 fake DB/models 隔离数据库连接。

## Step 9：前端接入节点级运行状态

目标：让用户看到真实节点状态和产物入口。

修改范围：

- `frontend/elys-web/src/views/PipelinePage.vue`
- `frontend/elys-web/src/api/pipelines.ts`
- `frontend/elys-web/src/types/index.ts`

实现要点：

- 运行后保存 `currentRunId`。
- 轮询 run detail、node runs 和 artifacts。
- 根据 `node_run.status` 设置 LiteGraph 节点颜色/标记。
- 底部面板展示节点列表、状态、错误、耗时、artifact 数量。
- 节点选中后显示最近一次 node_run 摘要。

测试：

- `npm run build`。
- 手动：运行 LoadData-only 工作流，节点变成功。
- 手动：运行含未实现或错误参数节点，节点显示失败。

Codex 提示词：

```text
请在 PipelinePage.vue 中接入后端节点级运行状态展示。

目标：
1. 点击运行后保存 run_id。
2. 使用 pipelineApi.getRun、listRunNodes、listRunArtifacts 轮询状态。
3. LiteGraph 节点根据 node_run.status 显示颜色或状态标记。
4. 底部运行面板展示：
   - run status
   - 每个节点 status
   - duration_ms
   - error message
   - artifact 数量
5. 选中节点时，右侧面板显示该节点最近一次 node_run 摘要。

要求：
- 不大拆 PipelinePage.vue，只做最小可维护修改。
- 前端状态以后端 node_run 为准，不使用前端假状态。
- 轮询间隔建议 1-2 秒，完成/失败后停止。

测试：
- npm run build。
- 手动验证 LoadData-only 工作流节点显示 success。
- 手动验证含错误节点时能看到具体错误。
```

完成标准：

- 用户能定位是哪个节点失败。
- UI 不再只有 run 级成功/失败。

本次落地记录（2026-05-18）：

- 已完成：`PipelinePage.vue` 点击运行后保存后端返回的 `run_id`，并以 1.5 秒间隔轮询 `getRun`、`listRunNodes`、`listRunArtifacts`。
- 已完成：轮询状态以后端 `node_run.status` 为准；run 进入 `completed/failed/canceled/cancelled` 后停止轮询。
- 已完成：LiteGraph 节点颜色和角标由最近一次 `node_run.status` 驱动，避免使用前端假状态。
- 已完成：底部运行面板展示 run status、每个节点 status、duration_ms、错误信息和 artifact 数量。
- 已完成：右侧选中节点面板展示该节点最近一次 `node_run` 摘要。
- 保持边界：未大拆 `PipelinePage.vue`，未改后端执行器，未接 Celery，未新增 artifact preview/download。
- 实际检查：`npm run build` 通过；仅保留既有 Vite CJS、litegraph eval 和 chunk size 警告。
- 未完成手动联调：当前环境没有可用的已登录前端会话、后端服务和测试项目数据，因此未实际运行 LoadData-only 或错误节点工作流；后续有运行环境时需补一次手动 E2E。

## Step 10：把 `/run` 改成后台运行过渡版

目标：避免 HTTP 请求等待完整 EEG 计算。

修改范围：

- `backend/app/routers/pipelines.py`
- `backend/app/pipeline/executor.py`
- 可能新增 `backend/app/pipeline/background.py`

实现要点：

- `POST /run` 创建 run 和 node_run 后立即返回。
- 后台任务继续执行 executor。
- run 初始为 queued/running。
- 前端通过 Step 9 的轮询查看进度。
- 先不引入 Celery 也可，重点是 API 语义改造。

测试：

- `/run` 快速返回。
- 轮询可看到 running -> completed/failed。
- 后台异常能写回 run/node_run。

Codex 提示词：

```text
请把工作流 /run 改成后台运行的过渡版本，但暂时不要接 Celery。

目标：
1. POST /projects/{project_id}/pipelines/{pipeline_id}/run 创建 pipeline_run 和 node_run 后尽快返回 run_id。
2. 使用 FastAPI BackgroundTasks 或一个受控后台执行方式调用 PipelineExecutor。
3. run.status 从 queued/running 到 completed/failed。
4. node_run 状态在后台执行过程中更新。
5. 前端已有轮询 API 能看到状态变化。

要求：
- 不引入 Redis/Celery。
- 后台任务中必须重新获取 DB session，避免复用请求 session。
- 异常必须写入 run.error_json 和对应 node_run.error_json。
- 保留一个可测试的同步执行函数，便于单元测试。

测试：
- 调用 /run 应快速返回，不等待所有节点执行结束。
- 轮询 run detail 看到状态变化。
- 构造异常节点，确认 run 最终 failed 且 error_json 有内容。
```

完成标准：

- 长任务不阻塞 HTTP。
- 状态展示闭环成立。

本次落地记录（2026-05-18）：

- 已完成：`POST /projects/{project_id}/pipelines/{pipeline_id}/run` 创建 `pipeline_runs`、冻结 `definition_snapshot`、预创建 pending `pipeline_node_runs` 后提交事务，并以 `run.status=queued` 返回。
- 已完成：新增 `backend/app/pipeline/background.py`，提供 `execute_pipeline_run_background()` 和可测试的 `execute_pipeline_run_sync()`；后台任务重新打开 DB session，不复用请求 session。
- 已完成：`PipelineExecutor` 拆出 `prepare_run()` 和 `execute_prepared_run()`，并保留 `execute()` 作为同步执行入口；后台执行时 run 从 `queued` 到 `running`，最终到 `completed/failed`。
- 已完成：node_run 在后台执行中从 `pending` 到 `running`，再到 `success/failed`，并写入 `duration_ms`、`output_json`、`error_json`。
- 已完成：后台致命异常会写入 `run.error_json`，并尽量写入当前 running/pending 的对应 `node_run.error_json`。
- 已完成：`PipelinePage.vue` 轮询逻辑兼容 `queued`，非终态继续轮询，完成/失败/取消后停止。
- 保持边界：未引入 Redis/Celery，未实现取消、恢复、重试、缓存或正式 worker 管理。
- 实际检查：`python -m py_compile backend/app/pipeline/executor.py backend/app/pipeline/background.py backend/app/routers/pipelines.py` 通过。
- 实际检查：fake DB 同步执行脚本通过，验证 prepare 阶段先创建 pending node_run，异常/未知节点最终让 run 和 node_run failed 且写入 error_json。
- 实际检查：fake DB 致命异常脚本通过，验证 executor 崩溃会写 `PIPELINE_RUN_BACKGROUND_ERROR` 到 run 和对应 node_run。
- 实际检查：`npm run build` 通过；仅保留既有 Vite CJS、litegraph eval 和 chunk size 警告。
- 未完成真实联调：当前环境没有可用 PostgreSQL/后端服务、已登录前端会话和测试项目数据，因此未实际调用真实 `/run` 后轮询状态变化。

## Step 11：接入 Celery + Redis

目标：把过渡后台任务升级为正式队列。

修改范围：

- `backend/app/tasks/celery_app.py`
- `backend/app/tasks/pipeline_tasks.py`
- `backend/app/config.py`
- `backend/requirements.txt`
- 部署脚本或 README

实现要点：

- Redis broker/backend 配置。
- `run_pipeline_task(run_id)`。
- `/run` 投递 Celery task。
- 记录 task_id。
- Worker 可单独启动。
- 先单队列 `workflow.default`，不要一开始做 DAG 并行。

测试：

- Redis 可连接。
- Celery worker 启动。
- `/run` 投递任务，worker 执行。
- worker 异常时 run failed。

Codex 提示词：

```text
请把工作流后台运行从过渡 BackgroundTasks 升级为 Celery + Redis。

目标：
1. 新增 backend/app/tasks/celery_app.py。
2. 新增 backend/app/tasks/pipeline_tasks.py，提供 run_pipeline_task(run_id)。
3. 配置 Redis broker/backend，读取 app config/env。
4. /run 创建 run 后投递 Celery task，并记录 task_id（如需要可扩展 pipeline_runs 字段或 result_json）。
5. Worker 内重新创建 DB session，调用 PipelineExecutor。
6. 第一版只使用 workflow.default 单队列，按拓扑顺序串行执行。

要求：
- 不做复杂 DAG 并行。
- 不把 EEG 大对象传进 Celery 消息，只传 run_id/project_id 等引用。
- 失败必须写回 DB。
- 文档中说明如何启动 worker。

测试：
- redis ping 或连接测试。
- 启动 celery worker。
- 调用 /run，确认 worker 执行并更新 run/node_run。
- npm run build 如前端类型受影响。
```

完成标准：

- 正式任务队列可运行。
- 后端事实仍保存在数据库。

2026-05-18 落地记录：

- 已完成：新增 `backend/app/tasks/celery_app.py`，创建 Celery app，默认 Redis broker/backend 为 `redis://localhost:6379/0`，默认队列为 `workflow.default`。
- 已完成：新增 `backend/app/tasks/pipeline_tasks.py`，提供 `run_pipeline_task(run_id, project_id=None)`；worker 内重新创建 DB session，调用 `execute_pipeline_run_sync()` / `PipelineExecutor`。
- 已完成：`backend/app/config.py` 新增 Redis/Celery 配置项，支持通过 env 覆盖 `CELERY_BROKER_URL`、`CELERY_RESULT_BACKEND`、`CELERY_WORKFLOW_QUEUE`。
- 已完成：`POST /projects/{project_id}/pipelines/{pipeline_id}/run` 创建 run/node_run 后投递 Celery task，不再使用 FastAPI `BackgroundTasks`；`pipeline_runs.result_json` 记录 `mode=celery`、`celery_task_id` 和 `task_queue`。
- 已完成：投递失败会写 `run.error_json`，错误码为 `PIPELINE_RUN_TASK_DISPATCH_FAILED`，并尽量把第一个 node_run 标为 failed。
- 已完成：`backend/requirements.txt` 新增 `celery[redis]==5.5.3`；`psycopg2-binary` 调整为 `2.9.10` 以兼容本机 Python 3.13 安装。
- 保持边界：不做复杂 DAG 并行，不把 EEG 大对象传进 Celery 消息，不接缓存，不做 ICA/PSD/TFR，不改前端 UI。

Worker 启动命令：

```powershell
# Windows 本地调试
$env:PYTHONPATH=(Join-Path $PWD 'backend')
python -m celery -A app.tasks.celery_app:celery_app worker -Q workflow.default --pool=solo --loglevel=INFO
```

```bash
# Linux/服务器
export PYTHONPATH=backend
celery -A app.tasks.celery_app:celery_app worker -Q workflow.default --loglevel=INFO
```

实际检查：

- 已运行：`python -m py_compile backend/app/config.py backend/app/tasks/__init__.py backend/app/tasks/celery_app.py backend/app/tasks/pipeline_tasks.py backend/app/pipeline/background.py backend/app/pipeline/executor.py backend/app/routers/pipelines.py`，通过。
- 已运行：Celery 导入冒烟脚本，确认 broker/backend 为 `redis://localhost:6379/0`，默认队列为 `workflow.default`，任务名为 `app.tasks.pipeline_tasks.run_pipeline_task`。
- 已运行：`python -m celery -A app.tasks.celery_app:celery_app report`，通过，能看到 redis transport 和 task route。
- 已运行：`redis-cli ping`，未通过，原因是本机没有 `redis-cli`。
- 已运行：Python socket 连接 `127.0.0.1:6379`，未通过，连接被拒绝，说明本机未启动 Redis。
- 已尝试启动 worker：因 Redis 不可达，worker 不能进入实际消费状态。
- 已运行：`npm run build`，通过，仅有既有 Vite CJS、litegraph eval 和 chunk size 警告。
- 未执行：真实 `/run` + worker 端到端验证，原因是当前环境没有可用 Redis/PostgreSQL/后端服务、已登录会话和测试项目数据。

## Step 12：实现缓存与增量执行

目标：参数和输入不变时复用已有 artifact。

修改范围：

- `backend/app/pipeline/hash.py`
- `backend/app/pipeline/cache.py`
- `backend/app/pipeline/executor.py`
- `backend/app/pipeline/artifacts.py`
- 前端状态展示可新增 cached 标记

实现要点：

- `params_hash` 只包含 `hash != false` 参数。
- `input_hash` 来自上游 artifact/content_hash。
- `node_hash = spec + engine version + params_hash + input_hash`。
- 缓存命中必须检查 DB 记录和文件存在、checksum。
- 命中也要写 node_run，status=`cached`。
- 修改节点参数后下游自然 hash 变化。

测试：

- 同一工作流跑两次，第二次预处理节点 cached。
- 改 FIR 参数后 FIR 和下游重跑。
- 删除 artifact 文件后缓存不命中。

Codex 提示词：

```text
请为工作流执行器实现第一版节点级缓存和增量执行。

目标：
1. 新增 backend/app/pipeline/hash.py：
   - canonical_json
   - params_hash，忽略 NodeSpec properties 中 hash=false 的参数
   - input_hash
   - node_hash
   - trace_code 初版
2. 新增 backend/app/pipeline/cache.py：
   - 按 node_hash 查找可复用 artifact
   - 校验 artifact 文件存在
   - 校验 checksum
   - 返回可恢复的 data_infos
3. PipelineExecutor 在执行节点前检查缓存。
4. 缓存命中时不调用 engine，写 node_run.status=cached，并登记本次 run 的输出引用。

要求：
- Redis 不保存 EEG artifact。
- localStorage 不作为缓存命中依据。
- 缓存命中必须留下本次 node_run 审计记录。

测试：
- 同一 pipeline 连续运行两次，第二次对应节点为 cached。
- 修改 FIR l_freq/h_freq 后，该节点和下游不命中。
- 人为删除 artifact 文件后，缓存自动失效并重跑。
```

完成标准：

- 后端增量缓存可证明生效。

2026-05-18 落地记录：

- 已完成：新增 `backend/app/pipeline/hash.py`，提供 `canonical_json`、`params_hash`、`input_hash`、`node_hash` 和初版 `trace_code`。
- 已完成：`params_hash` 会读取 NodeSpec properties，忽略 `hash=false` 参数；例如 FIR/Resample/Epoch/ERP 的 `save_output` 不影响缓存，Save Result 的 `retention` 不影响 hash。
- 已完成：`input_hash` 基于上游 `data_infos/artifacts` 的 `content_hash/checksum/storage_path/artifact_id/data_type/processing` 等轻量签名生成，不依赖 localStorage。
- 已完成：新增 `backend/app/pipeline/cache.py`，按 `node_hash` 查找历史 success/cached node_run，校验 artifact 文件存在和 checksum。
- 已完成：缓存命中时为本次 run 新登记 `pipeline_artifacts` 引用，恢复可传给下游的 `data_infos`，并把当前 `node_run.status` 写为 `cached`。
- 已完成：`PipelineExecutor` 在执行节点前写入 `params_hash/input_hash/node_hash/trace_code`，缓存命中时跳过 dispatcher/engine。
- 已完成：新增 `idx_pipeline_node_runs_project_hash(project_id, node_hash)` 索引，并同步到 model、`database/init.sql` 和 `schema_compat.py`。
- 保持边界：Redis 不保存 EEG artifact；localStorage 不作为缓存命中依据；不做 run-from、缓存统计、手动失效 API、partial policy。

实际检查：

- 已运行：`python -m py_compile backend/app/pipeline/hash.py backend/app/pipeline/cache.py backend/app/pipeline/executor.py backend/app/models/project.py backend/app/services/schema_compat.py`，通过。
- 已运行：hash 冒烟脚本，确认 `save_output` 改变不影响 `params_hash`、FIR `l_freq` 改变会影响 `params_hash`、上游 `processing.params` 改变会影响 `input_hash`。
- 已运行：tempfile cache restore 脚本，确认 artifact 文件存在、checksum 校验、命中时登记本次 artifact 引用、恢复 data_info 当前 `node_run_id`。
- 已运行：删除 artifact 文件后的 cache miss 脚本，确认文件缺失会让缓存自动失效，且不会登记新的 artifact 引用。
- 已运行：executor/cache import smoke，通过。
- 未执行：同一 pipeline 连续运行两次的真实 E2E、修改 FIR 后下游 E2E，原因是当前环境没有可用 PostgreSQL/后端服务、已登录会话和测试项目数据；本次用 hash/cache 最小脚本覆盖核心判定逻辑。

## Step 13：实现 ICA 人工交互节点

目标：支持 waiting/resume/decision。

修改范围：

- `backend/app/engine/ica/compute.py`
- `backend/app/engine/ica/apply.py`
- `backend/app/pipeline/interactions.py`
- `backend/app/routers/pipelines.py` 或 `pipeline_runs.py`
- `frontend/elys-web/src/views/PipelinePage.vue` 或后续组件

实现要点：

- Compute ICA 生成 ICA artifact 和 preview。
- Apply ICA 若缺少 decision，进入 `waiting_user_input`。
- 新增 interaction/decision/resume API。
- decision 参与 hash。
- 前端提供成分选择表单。

测试：

- synthetic Raw 跑 ICA compute。
- Apply ICA 无 decision -> waiting。
- 提交 decision -> resume -> success。
- decision_version 冲突返回错误。

Codex 提示词：

```text
请实现工作流 ICA 人工交互节点的第一版。

目标：
1. 实现 eeg/ica/compute：读取 Raw，拟合 ICA，保存 ICA artifact 和组件预览 metadata。
2. 实现 eeg/ica/apply：如果没有 excluded_components/decision，则 node_run.status=waiting_user_input。
3. 新增 interaction/decision/resume API：
   - GET 当前 waiting 节点需要的组件预览。
   - POST 用户 decision（excluded_components、decision_version）。
   - POST resume 继续该节点或下游执行。
4. decision 必须写入 node_run.output_json 或独立 interaction 记录，并参与后续 hash。
5. 前端在选中 waiting 节点时显示 ICA 成分选择面板。

要求：
- 不阻塞 worker 等待用户。
- 用户 decision 有版本号，避免多人提交冲突。
- Apply ICA 输出 cleaned Raw artifact。

测试：
- Compute ICA 生成 artifact。
- Apply ICA 无 decision 进入 waiting_user_input。
- 提交 decision 后 resume 成功。
- decision_version 冲突时返回 DECISION_CONFLICT。
```

完成标准：

- 人工节点可以暂停和继续。

2026-05-18 落地记录：

- 已完成：新增 `backend/app/engine/ica/compute.py`、`backend/app/engine/ica/apply.py` 和 `backend/app/engine/ica/__init__.py`，实现 `eeg/ica/compute` 拟合 MNE ICA、保存 `-ica.fif` artifact，并生成组件预览 metadata；实现 `eeg/ica/apply` 根据 decision 应用 ICA 并输出 cleaned Raw artifact。
- 已完成：扩展 `backend/app/engine/io.py`，支持 `read_ica_from_data_info()` 与 `save_ica_fif()`。
- 已完成：`backend/app/pipeline/dispatcher.py` 接入 `eeg/ica/compute` 与 `eeg/ica/apply`；Apply ICA 在缺少 `excluded_components/decision` 时返回 `waiting_user_input`，不会阻塞 worker 等待用户。
- 已完成：`backend/app/pipeline/executor.py` 支持 `waiting_user_input` run 状态，遇到等待节点后暂停下游；新增从等待节点 `start_topo_index` 继续执行的路径；恢复前会把 `node_run.output_json` 中的 ICA decision 合入 params，使 decision 参与 `params_hash/node_hash`。
- 已完成：`backend/app/routers/pipelines.py` 新增 ICA interaction API：`GET /projects/{project_id}/pipeline-runs/{run_id}/nodes/{node_run_id}/interaction`、`POST .../decision`、`POST .../resume`；decision 写入 `node_run.output_json`，`decision_version` 冲突返回 `DECISION_CONFLICT`。
- 已完成：`backend/app/schemas/pipeline.py` 新增 interaction/decision/resume response schema；`database/init.sql`、`backend/app/models/project.py`、`backend/app/services/schema_compat.py` 扩展 `pipeline_runs.status` 到 `VARCHAR(32)`，允许 `queued/running/waiting_user_input/completed/failed/canceled/cancelled`。
- 已完成：`frontend/elys-web/src/types/index.ts` 与 `src/api/pipelines.ts` 增加 ICA interaction/decision/resume 类型和 API 封装；`PipelinePage.vue` 对 `waiting_user_input` 节点显示 ICA 成分选择面板，可提交 excluded components 并 resume。
- 保持边界：未实现 ICA 自动识别、未实现独立 interaction 表、未实现 worker 内长时间等待、未接 SSE/WebSocket、未做 artifact preview/download、未改成 DAG 并行。

实际检查：

- `python -m py_compile` 通过：`engine/io.py`、`engine/ica/*.py`、`pipeline/dispatcher.py`、`pipeline/executor.py`、`pipeline/background.py`、`routers/pipelines.py`、`schemas/pipeline.py`、`services/schema_compat.py`、`models/project.py`。
- synthetic tempfile smoke 通过：构造 Raw -> Compute ICA 生成 artifact -> Apply ICA 无 decision 进入 `waiting_user_input` -> 写入 decision 后 Apply ICA 成功输出 cleaned Raw。
- decision hash smoke 通过：`node_run.output_json` 中的 ICA decision 会改变 Apply ICA 的 `params_hash`。
- `npm run build` 通过；仅保留 Vite CJS、litegraph eval、chunk size 等既有构建警告。
- 未执行真实 API/DB/Celery E2E：当前本机无 PostgreSQL/Redis/后端服务和登录态；当前 Python 环境缺少 FastAPI/Jose，路由运行时导入检查未执行，但路由文件已通过 py_compile。

## Step 14：Artifact preview 与观察页联动

目标：让工作流输出能被用户查看和后续模块消费。

修改范围：

- `backend/app/routers/pipeline_artifacts.py` 或 pipelines router
- `backend/app/pipeline/artifacts.py`
- 前端 PipelinePage artifact 入口
- 观察页入口相关文件

实现要点：

- Preview API 不返回大数组。
- ERP preview 返回 event、通道、时间窗、抽样曲线摘要。
- Raw preview 返回采样率、通道、时长、事件摘要。
- Epochs preview 返回 n_epochs、event counts。
- Pipeline 节点可点击打开 preview。

测试：

- 生成 evoked artifact 后 preview 可返回。
- 文件缺失返回 404。
- 前端可打开 preview。

Codex 提示词：

```text
请实现 pipeline_artifacts 的 preview API 和前端入口。

目标：
1. GET /api/v1/projects/{project_id}/pipeline-artifacts/{artifact_id}/preview。
2. 根据 artifact.data_type 返回轻量 preview：
   - raw: sfreq、n_channels、duration、event summary。
   - epochs: n_epochs、event counts、tmin/tmax。
   - evoked: event_names、time range、channel summary、少量抽样曲线。
3. 文件缺失或 checksum 不匹配时返回明确错误。
4. PipelinePage 中 artifact 入口可打开 preview，不直接下载大文件。
5. 为后续观察页保留 route/query 参数，例如 artifact_id/run_id。

要求：
- 不在 preview API 中返回完整 EEG 矩阵。
- 权限必须校验 project_id。
- preview_json 可缓存到 pipeline_artifacts.preview_json。

测试：
- 对 evoked artifact 调 preview。
- 删除文件后 preview 返回错误。
- npm run build。
```

完成标准：

- 工作流运行结果可以被用户打开查看。

2026-05-18 落地记录：

- 已完成：新增 `backend/app/pipeline/previews.py`，实现 artifact path 解析、文件存在检查、sha256 checksum 校验，以及 raw/epochs/evoked 三类轻量 preview 生成；preview 不返回完整 EEG 矩阵，Evoked 仅返回事件名、时间范围、通道摘要和少量抽样曲线。
- 已完成：`GET /api/v1/projects/{project_id}/pipeline-artifacts/{artifact_id}/preview` 已接入 `backend/app/routers/pipelines.py`，复用项目读权限并校验 artifact 属于该 project；文件缺失返回 `PIPELINE_ARTIFACT_FILE_MISSING`，checksum 不匹配返回 `PIPELINE_ARTIFACT_CHECKSUM_MISMATCH`。
- 已完成：`backend/app/schemas/pipeline.py` 新增 `PipelineArtifactPreviewResponse`，返回 `preview_json`、`observe_route` 和 `observe_query`；router 会把生成的 preview 回写到 `pipeline_artifacts.preview_json`。
- 已完成：`frontend/elys-web/src/types/index.ts` 和 `src/api/pipelines.ts` 增加 `PipelineArtifactPreview` 类型与 `previewArtifact()` API。
- 已完成：`PipelinePage.vue` 在选中节点右侧面板展示 artifact 列表，点击后打开轻量 preview 面板；面板显示指标、事件摘要、抽样曲线概览，并提供带 `artifact_id/run_id/node_run_id` query 的观察页入口，不直接下载大文件。
- 保持边界：未实现 artifact download，未改观察页实际渲染逻辑，未引入大矩阵返回，未实现 PSD/TFR 等后续 data_type preview。

实际检查：

- `python -m py_compile` 通过：`backend/app/pipeline/previews.py`、`backend/app/schemas/pipeline.py`、`backend/app/schemas/__init__.py`、`backend/app/routers/pipelines.py`。
- synthetic tempfile preview smoke 通过：构造 synthetic Raw -> Epochs -> Evoked FIF artifact，调用 `build_artifact_preview()` 验证 `/observe/erp` 路由、event_names、channel_summary 和抽样曲线数量。
- checksum 异常 smoke 通过：篡改 Evoked artifact 文件后返回 `PIPELINE_ARTIFACT_CHECKSUM_MISMATCH`。
- 文件缺失 smoke 通过：删除 Evoked artifact 文件后返回 `PIPELINE_ARTIFACT_FILE_MISSING`。
- `npm run build` 通过；仅保留 Vite CJS、litegraph eval、chunk size 等既有构建警告。
- 未执行真实 API/DB 端到端：当前本机无 PostgreSQL/后端服务和登录态；路由文件已通过 py_compile，preview 核心逻辑已用 synthetic FIF 直接验证。

## Step 15：同步正式 wiki 与回归

目标：把已落地事实回写正式文档，避免讨论稿和代码脱节。

修改范围：

- `wiki/docs/M3-00-工作流模块总览.md`
- `wiki/docs/M3-40-工作流执行.md`
- `wiki/docs/M3-50-异步任务与进度.md`
- `wiki/docs/M3-60-缓存与结果复用.md`
- `wiki/docs/4-08-工作流编辑器.md`
- `wiki/docs/2-30-数据库设计总览.md`
- `wiki/docs/2-50-API设计总览.md`
- `2_meeting260516/09-工作流讨论稿与正式wiki对齐清单.md`

实现要点：

- 已实现写“已实现”并给代码位置。
- 未实现继续写“规划”。
- 删除或修正过时说法。
- 补一份回归测试清单。

测试：

- Markdown 链接检查。
- `rg` 检查旧状态是否残留。
- 后端和前端完整回归。

Codex 提示词：

```text
请根据当前代码已经实现的工作流功能，回写正式 wiki 文档，并做一次回归检查。

要求：
1. 只把真实已经实现的能力写成“已实现”。
2. 未实现的能力仍写为“规划/待接”，不要把讨论稿方案写成事实。
3. 更新以下页面中与工作流状态相关的内容：
   - wiki/docs/M3-00-工作流模块总览.md
   - wiki/docs/M3-40-工作流执行.md
   - wiki/docs/M3-50-异步任务与进度.md
   - wiki/docs/M3-60-缓存与结果复用.md
   - wiki/docs/4-08-工作流编辑器.md
   - wiki/docs/2-30-数据库设计总览.md
   - wiki/docs/2-50-API设计总览.md
4. 更新 2_meeting260516/09-工作流讨论稿与正式wiki对齐清单.md 中的同步状态。

测试：
- rg 检查是否仍有过时状态描述。
- 后端相关测试。
- 前端 npm run build。

最后输出：哪些页面已同步、哪些功能仍未实现、哪些测试已跑。
```

完成标准：

- 正式 wiki 与代码事实一致。
- 后续交接不再依赖过时讨论稿。

## 附：第一轮最推荐连续执行的三个提示词

如果只能先做三件事，建议按顺序执行：

1. Step 1：新增 `pipeline_node_runs` 和 `pipeline_artifacts`。（2026-05-17 已完成数据结构层）
2. Step 2：拆分 `validator.py`。（2026-05-17 已完成）
3. Step 3：定义 `ArtifactStore` 和 `NodeOutput` 契约。（2026-05-17 已完成基础设施）
4. Step 4：新增 run detail、node run、artifact 查询 API。（2026-05-17 已完成查询通道和前端封装）
5. Step 5：实现只跑 LoadData 的 `PipelineExecutor` 骨架。（2026-05-17 已完成）
6. Step 6：建立 MNE IO 与 synthetic 测试工具。（2026-05-17 已完成）
7. Step 7：实现 FIR、Resample、Re-reference 节点。（2026-05-17 已完成）
8. Step 8：实现 Epoch、ERP Average、Save Result。（2026-05-18 已完成）
9. Step 9：前端接入节点级运行状态。（2026-05-18 已完成）
10. Step 10：把 `/run` 改成后台运行过渡版。（2026-05-18 已完成）
11. Step 11：接入 Celery + Redis。（2026-05-18 已完成第一版投递入口；本机 Redis 不可用，真实消费未验证）
12. Step 12：实现缓存与增量执行。（2026-05-18 已完成第一版 node_hash/artifact 复用；连续 pipeline E2E 待 DB 环境验证）
13. Step 13：实现 ICA 人工交互节点。（2026-05-18 已完成第一版 Compute/Apply、waiting_user_input、decision/resume API 和前端成分选择面板；真实 API/DB/Celery E2E 待环境验证）
14. Step 14：Artifact preview 与观察页联动。（2026-05-18 已完成第一版 preview API、raw/epochs/evoked 轻量摘要、checksum/缺失文件错误、PipelinePage artifact 入口和观察页 query；真实 API/DB E2E 待环境验证）

这些基础完成后，当前工作流已从“run 级预运行”推进到“节点级可追踪执行 + 前端可见节点状态 + Celery 投递入口 + 第一版 artifact 缓存 + ICA 人工等待/决策/恢复 + artifact 轻量预览入口”的阶段，并具备文件驱动 MNE IO、预处理节点、ICA 节点、分析节点、artifact 输出、`analysis_results` 登记和 raw/epochs/evoked preview 能力。下一步如果继续原路线，可进入 Step 15：同步正式 wiki 与回归；也可以先完善 worker 部署、恢复、取消和重试。
