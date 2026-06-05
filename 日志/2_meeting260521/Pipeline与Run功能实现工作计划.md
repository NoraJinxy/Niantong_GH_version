# Pipeline 与 Run 功能实现工作计划

文档生成时间：2026-05-21 22:08:58 +08:00

本文基于以下两份文档继续拆解 Pipeline / Run 功能实现路线：

1. `日志/2_meeting260521/Pipeline与Run功能定义与实现规范.md`
2. `日志/2_meeting260521/当前程序未实现与未收口功能清单.md`

目标是把当前已有的工作流骨架推进成符合新定义的稳定 MVP：

```text
Pipeline 管处理方案。
Run 管执行事实。
Pipeline 可编辑，Run 可追溯。
动态选择在 Pipeline，实际输入冻结在 Run。
试跑和正式分析通过 run_mode / save_policy 区分。
协作冲突通过 version / lock / task 状态机控制。
```

## 1. 总体实施原则

| 原则 | 说明 |
| --- | --- |
| 兼容优先 | 不破坏现有 `/projects`、`/run`、旧 Pipeline Definition 和旧 Run |
| 小步验证 | 每一步都跑局部测试和可用全量测试 |
| 事实冻结 | Run 创建后不再依赖 Pipeline 当前定义或 Dataset 当前状态 |
| 状态统一 | Run 成功统一叫 `completed`，Task 成功可叫 `succeeded` |
| 不做大迁移 | 短期不物理改名 `projects`、`datasets`、`pipeline_definitions` |
| 文档同步 | 每一步完成后必须更新本计划文档和相关 docs_v2 页面 |

## 2. 阶段划分

### 阶段 A：语义和 API 收口

目标：先解决最容易造成前后端对接混乱的地方。

包含步骤：

1. 建立 Pipeline/Run 改造基线。
2. 统一 Run 路由和状态命名。
3. 接入 `run_mode` / `save_policy`。
4. 增加 Pipeline 状态运行规则。
5. 增加 NodeSpec executor 校验。

### 阶段 B：输入边界和协作安全

目标：把“Pipeline 不保存具体数据，Run 保存实际输入”的边界打硬，并减少多人协作覆盖。

包含步骤：

6. 收敛 LoadData explicit 选择到 Run override。
7. 强制 `expected_version`。
8. 增加 Pipeline edit lock。

### 阶段 C：运行控制和任务治理

目标：让 Run / Task 从“能派发”变成“能管理”。

包含步骤：

9. 增加 Run cancel。
10. 增加 Run retry。
11. 增加 Task cancel/retry。
12. 增加任务事件 SSE。

### 阶段 D：结果体验和追溯视图

目标：让用户能理解一次 Run 的输入、过程、输出和依赖。

包含步骤：

13. 增加 Run lineage 聚合视图。
14. 增加 Artifact pin/unpin/hide 语义 API。
15. 前端接入 Pipeline/Run 新规范。

### 阶段 E：回归和文档收口

目标：完成端到端验证和 docs_v2 更新。

包含步骤：

16. 全链路回归与文档收口。

## 3. 工作计划总表

| 步骤 | 状态 | 主题 | 主要产出 | 优先级 |
| --- | --- | --- | --- | --- |
| 第 1 步 | 已完成 | 建立 Pipeline/Run 改造基线 | 当前 API、模型、测试、文档差异清单 | P0 |
| 第 2 步 | 已完成 | 统一 Run 路由和状态命名 | `/runs` alias、文档状态统一 | P0 |
| 第 3 步 | 已完成 | 接入 `run_mode/save_policy` | schema、API、DB 写入、response、测试 | P0 |
| 第 4 步 | 已完成 | Pipeline 状态运行规则 | active/draft/archived 运行限制 | P0 |
| 第 5 步 | 已完成 | NodeSpec executor 校验 | 运行前发现无 executor 节点 | P0 |
| 第 6 步 | 已完成 | LoadData explicit 边界收口 | Run override 方案和兼容实现 | P0 |
| 第 7 步 | 已完成 | 强制 `expected_version` | Pipeline 保存乐观锁硬约束 | P1 |
| 第 8 步 | 已完成 | Pipeline edit lock | 编辑锁获取、续期、释放和冲突提示 | P1 |
| 第 9 步 | 已完成 | Run cancel | 取消 Run、释放锁、生成 manifest | P1 |
| 第 10 步 | 已完成 | Run retry | 从失败 Run 创建新 Run | P1 |
| 第 11 步 | 已完成 | Task cancel/retry | 后台任务取消、重试 API 和状态机 | P1 |
| 第 12 步 | 已完成 | 任务事件 SSE | Task 级 SSE 与增量 events 查询 | P1 |
| 第 13 步 | 已完成 | Run lineage 聚合视图 | Run 输入、输出、上下游依赖图 API | P1 |
| 第 14 步 | 已完成 | Artifact 语义操作 | pin/unpin/hide 与 blocker 返回 | P1 |
| 第 15 步 | 已完成 | 前端接入 | Run 对话框、Run detail、任务进度 | P1 |
| 第 16 步 | 已完成 | 全链路回归与文档收口 | pytest、compileall、mkdocs build、回归报告 | P0 |

## 4. 分步骤实施方案

### 第 1 步：建立 Pipeline/Run 改造基线

状态：已完成

文档更新时间：2026-05-21 22:30:55 +08:00

工作目标：

在正式改代码前，确认当前 Pipeline/Run 的 API、数据库字段、执行器、文档和测试覆盖，形成改造基线。

具体需要做：

1. 读取并整理：
   - `elys_version1/backend/app/routers/pipelines.py`
   - `elys_version1/backend/app/schemas/pipeline.py`
   - `elys_version1/backend/app/models/project.py`
   - `elys_version1/backend/app/pipeline/validator.py`
   - `elys_version1/backend/app/pipeline/dispatcher.py`
   - `elys_version1/backend/app/pipeline/executor.py`
   - `elys_version1/backend/app/tasks/pipeline_tasks.py`
   - `elys_version1/backend/app/services/study_locks.py`
   - `elys_version1/backend/app/services/task_events.py`
   - `elys_version1/backend/tests`
   - `wiki/docs_v2/5-20-Pipeline工作流管理.md`
   - `wiki/docs_v2/5-30-Run执行项管理.md`
   - `wiki/docs_v2/7-40-工作流执行与后台任务.md`
   - `wiki/docs_v2/2-50-API设计总览.md`
2. 列出当前实际路由和文档目标路由差异。
3. 列出当前 Run 状态枚举、Task 状态枚举和文档状态差异。
4. 列出已有测试覆盖和缺口。
5. 不做业务代码改动。

建议验证：

```bash
cd elys_version1/backend
python -m compileall app tests scripts
python -m pytest tests -q
```

实际发现：

1. 当前实际 API 仍以 `/api/v1/projects/{project_id}` 为主，Study 语义尚未体现在路由命名中。Pipeline CRUD 已有 `GET/POST /projects/{project_id}/pipelines`、`GET/PUT/DELETE /projects/{project_id}/pipelines/{pipeline_id}` 和 `POST /projects/{project_id}/pipelines/{pipeline_id}/validate`。
2. Run 创建当前只有旧兼容入口 `POST /projects/{project_id}/pipelines/{pipeline_id}/run`，尚未提供文档目标中的复数标准入口 `/runs`。Run 查询已包含 `GET /pipelines/{pipeline_id}/runs`、`GET /pipeline-runs/{run_id}`、`GET /pipeline-runs/{run_id}/manifest`、`GET /pipeline-runs/{run_id}/nodes`、`GET /pipeline-runs/{run_id}/artifacts`。
3. Artifact 和交互相关 API 已较完整：Artifact 列表、预览、下载、retention patch、cleanup task，以及 ICA 交互的 interaction、decision、resume 都在 `routers/pipelines.py` 中；但还没有 Run cancel、Run retry、Run lineage、Task cancel/retry 和 SSE。
4. Task API 当前支持 `GET /projects/{project_id}/tasks`、`GET /projects/{project_id}/tasks/{task_id}`、`GET /projects/{project_id}/tasks/{task_id}/events`。`task_events` 已是追加式事件表，但当前只是列表查询，不是事件流。
5. Run 状态代码侧主要使用 `queued`、`running`、`waiting_user_input`、`completed`、`failed`、`canceled/cancelled`。执行器成功完成写 `completed`，人工交互节点会让 Run 停在 `waiting_user_input`。文档里 `5-30-Run执行项管理.md` 仍有 `succeeded/retrying` 作为 Run 状态的表述，后续第 2 步需要统一。
6. Task 状态 schema 允许 `queued`、`running`、`succeeded`、`failed`、`canceled`、`cancelled`、`retrying`。`task_status_for_pipeline_run()` 会把 `completed` 和 `waiting_user_input` 映射为 Task `succeeded`，表示这次 Celery 任务已结束，但 Run 可能仍等待用户决策。
7. 数据库/ORM 已具备核心追溯表：`pipeline_definitions`、`pipeline_runs`、`pipeline_node_runs`、`pipeline_artifacts`、`pipeline_run_inputs`、`pipeline_run_dependencies`、`async_tasks`、`task_events`。其中 `pipeline_runs` 已有 `manifest_json`、`run_mode`、`save_policy` 字段，但 `PipelineRunCreate` 和 `PipelineRunResponse` 尚未暴露 `run_mode/save_policy`。
8. `pipeline_run_inputs` 已能记录 Dataset Asset、旧 Dataset、Upload、Dataset File、`file_role`、`storage_uri`、`logical_path`、上游 Run/Artifact、selector、resolved metadata 和 sha256，适合作为历史 Run 的输入事实源。
9. 执行器当前注册的真实节点包括：`eeg/data/load`、`eeg/filter/fir`、`eeg/preproc/resample`、`eeg/preproc/rereference`、`eeg/ica/compute`、`eeg/ica/apply`、`eeg/epoch/segment`、`eeg/analysis/erp`、`eeg/output/save_result`。
10. NodeSpec 目录中还存在 `eeg/filter/butterworth`，但 `NodeDispatcher` 没有对应 handler。当前 validator 主要校验 NodeSpec、参数、连接和环路，不校验是否有真实 executor，因此会出现“能创建/校验、运行时才失败”的风险。
11. Study 运行锁已接入 Run 创建：Run 创建前会获取 `study_locks` 的 `lock_type=run`，派发失败或任务结束会释放。Pipeline 编辑锁尚未实现。
12. 测试覆盖集中在文件管理、ArtifactStore、LoadData 输入快照、Run dependency、Run manifest、StorageService、file tasks 和项目目录结构；缺少针对 Pipeline/Run 路由 alias、状态统一、`run_mode/save_policy` API 暴露、Pipeline 状态运行规则、无 executor 节点校验、cancel/retry/SSE/edit lock 的专门测试。
13. docs_v2 已经写入很多目标设计，但与代码现状存在混用：`5-20` 写 Run 创建为 `/pipelines/{pipeline_id}/runs`，代码实际为 `/run`；`5-30` 把 Run 成功状态写为 `succeeded`，代码实际为 `completed`；`2-50` 同时记录了 Study 标准目标 API 和当前 Project 兼容 API，后续需要更明确区分“现状”和“目标”。

实际改动：

本步没有改业务代码、数据库 schema 或测试，仅更新本文档的第 1 步基线记录。

验证结果：

1. `cd elys_version1/backend; python -m compileall app tests scripts` 通过。
2. `cd elys_version1/backend; python -m pytest tests -q` 通过，结果为 `53 passed, 30 warnings in 1.16s`。
3. warnings 主要是 Pydantic V2 class-based config 弃用提示和 `datetime.utcnow()` 弃用提示，本步未处理。

遗留风险：

1. API 路由命名仍有 `/run` 与文档目标 `/runs` 的差异，容易造成前后端对接混乱。
2. Run 状态和 Task 状态尚未在所有文档中统一，尤其是 `succeeded` 应只作为 Task 成功状态，不应作为 Run 成功状态。
3. `run_mode/save_policy` 已在 ORM 中存在，但 API 创建和响应未打通，前端无法可靠表达试跑、正式分析和输出保留策略。
4. `eeg/filter/butterworth` 有 NodeSpec 但无 executor，当前 validator 不能提前拦截。
5. Run cancel/retry、Task cancel/retry、SSE、Run lineage、Pipeline edit lock 仍未实现，需要按后续步骤逐步补齐。

下一步建议：

按计划进入第 2 步，优先新增 `POST /projects/{project_id}/pipelines/{pipeline_id}/runs` 兼容入口，并把 docs_v2 中 Run 成功状态统一为 `completed`、Task 成功状态统一为 `succeeded`。完成第 2 步后再接第 3 步 `run_mode/save_policy`，这样前后端先有稳定命名，再扩展语义字段。

Codex 提示词：

```text
第1步：建立 Pipeline/Run 改造基线。请读取 elys_version1/backend/app/routers/pipelines.py、schemas/pipeline.py、models/project.py、pipeline/validator.py、pipeline/dispatcher.py、pipeline/executor.py、tasks/pipeline_tasks.py、services/study_locks.py、services/task_events.py、backend/tests 以及 docs_v2 中 Pipeline/Run/API/任务队列相关页面，整理当前实际 API、Run/Task 状态枚举、数据库字段、执行器支持情况、测试覆盖和文档差异。不要做业务代码改动。完成后运行可用验证，并更新 日志/2_meeting260521/Pipeline与Run功能实现工作计划.md 中第 1 步的状态、实际发现、验证结果、遗留风险和下一步建议。
```

### 第 2 步：统一 Run 路由和状态命名

状态：已完成

文档更新时间：2026-05-21 22:37:23 +08:00

工作目标：

解决 `/run` 与 `/runs`、`completed` 与 `succeeded` 混用问题。

具体需要改：

1. 在 `routers/pipelines.py` 中保留现有：
   - `POST /api/v1/projects/{project_id}/pipelines/{pipeline_id}/run`
2. 新增兼容 alias：
   - `POST /api/v1/projects/{project_id}/pipelines/{pipeline_id}/runs`
3. 两个入口调用同一内部函数，避免复制逻辑。
4. 文档中当前实现统一写清：
   - 当前兼容：`/run`
   - 标准新接口：`/runs`
5. Run 状态文档统一：
   - 成功 Run 使用 `completed`
   - Task 成功使用 `succeeded`
6. 如 schema 中存在容易混淆的注释，也同步修正。

建议测试：

1. 新增或更新 router 层测试，验证两个路由都能创建 Run 或至少调用同一逻辑。
2. 文档关键词检查：
   - Run 文档不再把 Run 成功状态写成 `succeeded`。

实际改动：

1. `elys_version1/backend/app/routers/pipelines.py`
   - 抽出 `_create_pipeline_run(...)` 作为 Run 创建共享实现。
   - 新增标准入口 `POST /api/v1/projects/{project_id}/pipelines/{pipeline_id}/runs`。
   - 保留兼容旧入口 `POST /api/v1/projects/{project_id}/pipelines/{pipeline_id}/run`，两个入口调用同一内部函数。
2. `elys_version1/backend/tests/test_pipeline_run_routes.py`
   - 新增轻量 AST 测试，确认 `/runs` 和 `/run` 两个路由都存在，并都调用 `_create_pipeline_run(...)`。
3. `wiki/docs_v2/5-30-Run执行项管理.md`
   - Run 生命周期成功状态由 `succeeded` 改为 `completed`。
   - 明确 `succeeded` 只作为 Task 成功状态，`retrying` 暂不作为当前 Run 状态。
   - Run 创建 API 写成标准 `/runs` 与兼容 `/run` 双入口。
4. `wiki/docs_v2/5-20-Pipeline工作流管理.md`
   - Pipeline 运行 API 明确标准 `/runs` 和兼容 `/run`。
5. `wiki/docs_v2/7-40-工作流执行与后台任务.md`
   - Run 创建链路说明改为双入口共用同一创建逻辑。
6. `wiki/docs_v2/2-50-API设计总览.md`
   - Study 目标 API 使用 `/runs`。
   - 当前 Project 兼容 API 同时列出标准 `/runs` 和旧 `/run`。

验证结果：

1. `cd elys_version1/backend; python -m pytest tests/test_pipeline_run_routes.py -q` 通过，结果为 `1 passed in 0.02s`。
2. `cd elys_version1/backend; python -m compileall app tests scripts` 通过。
3. `cd elys_version1/backend; python -m pytest tests -q` 通过，结果为 `54 passed, 30 warnings in 1.14s`。
4. warnings 仍主要来自 Pydantic V2 class-based config 和 `datetime.utcnow()` 弃用提示，本步未处理。

遗留风险：

1. 新 `/runs` 已接入，但前端是否已切换到标准入口尚未核对，后续前端接入步骤需要统一。
2. Run cancel/retry 尚未实现，所以文档只收口了命名；重试仍是后续能力，不是当前 Run 状态。
3. 当前代码仍同时兼容 `canceled/cancelled`，取消状态命名可在 Run cancel 步骤中再做最终收口。

下一步建议：

继续进入第 3 步，打通 `run_mode/save_policy` 的 API 创建、响应和任务追踪字段。第 2 步已经把创建入口命名稳定下来，适合在这个基础上扩展试跑、正式分析和输出保留策略。

Codex 提示词：

```text
第2步：统一 Run 路由和状态命名。请在 routers/pipelines.py 中为创建 Run 新增 POST /api/v1/projects/{project_id}/pipelines/{pipeline_id}/runs 兼容入口，保留旧 POST /run，并抽出共享内部函数避免重复逻辑。同时把 docs_v2 中 Run 成功状态统一为 completed，Task 成功状态保留 succeeded，明确 /run 是兼容旧接口、/runs 是标准接口。完成后运行相关测试和可用验证，并更新 日志/2_meeting260521/Pipeline与Run功能实现工作计划.md 中第 2 步的状态、实际改动、验证结果、遗留风险和下一步建议。
```

### 第 3 步：接入 `run_mode` 与 `save_policy`

状态：已完成

文档更新时间：2026-05-21 22:41:29 +08:00

工作目标：

让用户和前端能明确区分试跑、正式分析、重放，以及输出保存策略。

具体需要改：

1. 更新 `PipelineRunCreate`：
   - `trigger: Literal["manual"] = "manual"`
   - `run_mode: Literal["trial", "analysis", "replay", "system"] = "analysis"`
   - `save_policy: Literal["temporary", "current", "pinned", "discard"] = "current"`
2. 更新 `PipelineRunResponse`：
   - 返回 `run_mode`
   - 返回 `save_policy`
3. 更新 `pipeline_run_to_response(...)`。
4. 创建 Run 时把 payload 写入 `PipelineRun.run_mode` 和 `PipelineRun.save_policy`。
5. `result_json` 和 `async_tasks.payload_json` 中写入 `run_mode/save_policy`，方便任务侧和前端追踪。
6. 初步定义 save policy 对 Artifact 默认状态的影响：
   - `temporary` -> 默认输出 `temporary`
   - `current` -> 默认输出 `current`
   - `pinned` -> 默认输出 `pinned`
   - `discard` -> 尽量只保留摘要和必要日志
7. 本步可以先只打通 Run 字段，ArtifactStore 的默认策略可在后续继续强化。

建议测试：

1. 创建 Run 时传入 `trial/temporary`，Run response 和数据库字段正确。
2. 不传字段时默认 `analysis/current`。
3. 非法值返回 422。

实际改动：

1. `elys_version1/backend/app/schemas/pipeline.py`
   - 新增 `PipelineRunMode = Literal["trial", "analysis", "replay", "system"]`。
   - 新增 `PipelineRunSavePolicy = Literal["temporary", "current", "pinned", "discard"]`。
   - `PipelineRunCreate` 增加 `run_mode` 和 `save_policy`，默认 `analysis/current`。
   - `PipelineRunResponse` 增加 `run_mode` 和 `save_policy` 返回字段。
2. `elys_version1/backend/app/routers/pipelines.py`
   - `pipeline_run_to_response(...)` 返回 `run_mode/save_policy`，旧数据缺失时兜底为 `analysis/current`。
   - `_create_pipeline_run(...)` 从请求 payload 读取 `run_mode/save_policy`。
   - 创建 `PipelineRun` 时写入 `pipeline_runs.run_mode` 和 `pipeline_runs.save_policy`。
   - `result_json` 写入 `run_mode/save_policy`，方便前端和历史追踪。
   - `async_tasks.payload_json` 写入 `run_mode/save_policy`，方便任务侧追踪。
   - 运行锁 metadata 和审计 metadata 同步记录 `run_mode/save_policy`。
3. `elys_version1/backend/tests/test_pipeline_run_routes.py`
   - 增加 schema 默认值、合法值和非法值校验测试。
   - 增加 response 字段存在性测试。
   - 增加路由源码检查，确认创建链路写入和追踪 `run_mode/save_policy`。
4. `wiki/docs_v2/5-30-Run执行项管理.md`
   - 增加“运行模式和保存策略”说明。
   - 明确本步只保证字段可创建、可返回、可追踪，ArtifactStore 自动保留策略后续再做。
5. `wiki/docs_v2/2-50-API设计总览.md`
   - 增加 Run 创建请求体示例和字段取值说明。
6. `wiki/docs_v2/3-40-Run与Artifact追溯表.md`
   - 将旧 `preview/formal` 和 `cached` 保存策略描述更新为当前 `trial/analysis/replay/system` 与 `temporary/current/pinned/discard`。

验证结果：

1. `cd elys_version1/backend; python -m pytest tests/test_pipeline_run_routes.py -q` 通过，结果为 `3 passed in 0.25s`。
2. `cd elys_version1/backend; python -m compileall app tests scripts` 通过。
3. `cd elys_version1/backend; python -m pytest tests -q` 通过，结果为 `56 passed, 30 warnings in 1.11s`。
4. warnings 仍主要来自 Pydantic V2 class-based config 和 `datetime.utcnow()` 弃用提示，本步未处理。

遗留风险：

1. ArtifactStore 仍未根据 `save_policy` 自动设置新 Artifact 的 `retention_status`，这是本步刻意后置的范围。
2. `run_mode=trial/analysis/replay/system` 目前只做 API 和追踪字段，不影响 Pipeline 状态运行规则；第 4 步会继续接入 draft/active/archived 的运行限制。
3. 前端 Run 创建对话框尚未接入 `run_mode/save_policy`，后续前端接入步骤需要同步。

下一步建议：

继续进入第 4 步，在 Run 创建逻辑中根据 `pipeline.status` 和 `run_mode` 做运行规则校验：`active` 允许 `analysis/trial`，`draft` 只允许 `trial`，`archived` 禁止新 Run。第 3 步已经让 `run_mode` 可被 API 接收和追踪，下一步可以把它用于实际控制。

Codex 提示词：

```text
第3步：接入 run_mode 与 save_policy。请更新 PipelineRunCreate、PipelineRunResponse、pipeline_run_to_response 和 Run 创建逻辑，让 API 支持 run_mode=trial/analysis/replay/system 与 save_policy=temporary/current/pinned/discard，并把字段写入 pipeline_runs、result_json 和 async_tasks.payload_json。默认值为 analysis/current。先不要大改 ArtifactStore，只保证字段可创建、可返回、可追踪。完成后补充测试并运行可用验证，更新 日志/2_meeting260521/Pipeline与Run功能实现工作计划.md 中第 3 步的状态、实际改动、验证结果、遗留风险和下一步建议。
```

### 第 4 步：增加 Pipeline 状态运行规则

状态：已完成

文档更新时间：2026-05-21 22:45:53 +08:00

工作目标：

防止草稿或归档 Pipeline 被误用于正式分析。

具体需要改：

1. 在 Run 创建共享内部函数中增加状态校验。
2. 建议规则：
   - `active`：允许 `analysis` 和 `trial`
   - `draft`：只允许 `trial`
   - `archived`：禁止创建新 Run
   - `deleted`：继续 404
3. 错误返回结构化 detail：
   - `code`
   - `message`
   - `pipeline_status`
   - `run_mode`
4. 文档同步更新。

建议测试：

1. active + analysis 成功。
2. draft + analysis 返回 409。
3. draft + trial 成功。
4. archived + trial/analysis 返回 409。

实际改动：

1. `elys_version1/backend/app/services/pipeline_run_rules.py`
   - 新增 Pipeline Run 创建规则服务。
   - 定义 `active` 允许 `analysis/trial`，`draft` 只允许 `trial`。
   - `archived` 和未知状态返回结构化错误 detail。
2. `elys_version1/backend/app/routers/pipelines.py`
   - Run 创建逻辑在 validation、运行锁和任务创建之前执行状态规则校验。
   - 不满足规则时返回 409，错误体包含 `code`、`message`、`pipeline_status`、`run_mode`。
   - `deleted` Pipeline 仍由 `get_pipeline_or_404(...)` 过滤并返回 404。
3. `elys_version1/backend/tests/test_pipeline_run_routes.py`
   - 补充 active + analysis、active + trial、draft + trial 放行测试。
   - 补充 draft + analysis、archived + trial、active + replay 拦截测试。
   - 补充源码顺序测试，确认状态规则在 validation 和运行锁之前执行。
4. `wiki/docs_v2/5-20-Pipeline工作流管理.md`
   - 明确 Pipeline 状态与 Run 创建规则。
   - 从后续任务中移除“明确 draft 运行策略”。
5. `wiki/docs_v2/5-30-Run执行项管理.md`
   - 在 Run 模式说明后补充 Pipeline 状态校验规则。
6. `wiki/docs_v2/2-50-API设计总览.md`
   - 在 Run 创建请求说明中补充 active/draft/archived/deleted 的当前规则。

验证结果：

1. `cd elys_version1/backend; python -m pytest tests/test_pipeline_run_routes.py -q` 通过，结果为 `6 passed in 0.24s`。
2. `cd elys_version1/backend; python -m compileall app tests scripts` 通过。
3. `cd elys_version1/backend; python -m pytest tests -q` 通过，结果为 `59 passed, 30 warnings in 1.10s`。
4. warnings 仍主要来自 Pydantic V2 class-based config 和 `datetime.utcnow()` 弃用提示，本步未处理。

遗留风险：

1. `replay/system` 虽然是 API 合法值，但当前运行规则尚未放行，后续如需要系统任务或重放任务，需要增加专门入口或规则。
2. 错误 message 当前是英文短句，后续前端可基于 `code/pipeline_status/run_mode` 做本地化提示。
3. 前端尚未根据 Pipeline 状态禁用 Run 按钮，后续前端接入步骤需要同步，否则仍会由后端返回 409。

下一步建议：

继续进入第 5 步，增加 NodeSpec executor 校验。当前 Pipeline 状态规则已经能挡住“不该运行”的 Pipeline，下一步应挡住“看起来能运行但没有真实执行器”的节点，尤其是 `eeg/filter/butterworth`。

Codex 提示词：

```text
第4步：增加 Pipeline 状态运行规则。请在 Pipeline Run 创建逻辑中根据 pipeline.status 和 run_mode 做硬校验：active 可正式 analysis/trial，draft 只允许 trial，archived 禁止新 Run，deleted 继续不可见。错误使用结构化 code/message/pipeline_status/run_mode。补充测试覆盖 active、draft、archived 的运行规则，并更新 docs_v2 和 日志/2_meeting260521/Pipeline与Run功能实现工作计划.md 中第 4 步的状态、实际改动、验证结果、遗留风险和下一步建议。
```

### 第 5 步：增加 NodeSpec executor 校验

状态：已完成

文档更新时间：2026-05-21 22:50:43 +08:00

工作目标：

避免 NodeSpec 存在但运行时没有执行器，导致用户到 Run 阶段才失败。

具体需要改：

1. 在 `NodeDispatcher` 暴露 executor 支持查询方法，例如：
   - `supports(node_type: str) -> bool`
   - `supported_node_types() -> set[str]`
2. 在 `validate_definition(...)` 中校验：
   - NodeSpec 存在。
   - 对应 executor 存在。
3. 当前已知问题：
   - `eeg/filter/butterworth` 有 NodeSpec，但 dispatcher 未注册 handler。
4. 处理方式二选一：
   - 临时隐藏或禁用 butterworth NodeSpec。
   - 或实现 butterworth executor。
5. 建议 MVP 先选择“校验报错或隐藏”，避免误导用户。

建议测试：

1. 包含无 executor 节点的 Pipeline validate 返回 error。
2. 已支持节点不报错。

实际改动：

1. `elys_version1/backend/app/pipeline/dispatcher.py`
   - `NodeDispatcher` 新增 `supported_node_types() -> set[str]`。
   - `NodeDispatcher` 新增 `supports(node_type: str) -> bool`。
2. `elys_version1/backend/app/pipeline/validator.py`
   - `validate_definition(...)` 创建 `NodeDispatcher` 并检查每个已存在的 NodeSpec 是否有真实 handler。
   - 对无 executor 的节点返回 `PIPELINE_NODE_EXECUTOR_NOT_IMPLEMENTED`。
   - 当前 `eeg/filter/butterworth` 会在 validate 阶段明确报错，不再等到运行时由 dispatcher 抛异常。
3. `elys_version1/backend/tests/test_pipeline_validator_executor.py`
   - 新增 dispatcher 支持列表测试。
   - 新增 `eeg/filter/butterworth` 无 executor 的 validate 错误测试。
   - 新增 `eeg/filter/fir` 有 executor 的放行测试。
4. `wiki/docs_v2/5-20-Pipeline工作流管理.md`
   - 校验规则增加“NodeSpec 必须有真实后端 executor”。
   - 明确 Butterworth 当前返回 `PIPELINE_NODE_EXECUTOR_NOT_IMPLEMENTED`。
5. `wiki/docs_v2/7-40-工作流执行与后台任务.md`
   - 更新 Validator 职责和 Run 创建链路，说明会调用 `NodeDispatcher.supports()` 做 executor 支持检查。
   - 将“部分 NodeSpec 暂无 executor”记录为 validate 阶段明确错误。

验证结果：

1. `cd elys_version1/backend; python -m pytest tests/test_pipeline_validator_executor.py -q` 通过，结果为 `3 passed, 1 warning in 0.64s`。
2. `cd elys_version1/backend; python -m compileall app tests scripts` 通过。
3. `cd elys_version1/backend; python -m pytest tests -q` 通过，结果为 `62 passed, 30 warnings in 1.16s`。
4. warnings 仍主要来自 Pydantic V2 class-based config 和 `datetime.utcnow()` 弃用提示，本步未处理。

遗留风险：

1. Butterworth 节点仍会出现在 NodeSpec 列表中，本步选择 validate 报错，尚未在 registry/UI 层标记 disabled。
2. validator 现在会实例化 `NodeDispatcher`，因此 executor 支持校验依赖 dispatcher 注册表；后续如果节点很多，可以考虑抽成轻量 executor registry。
3. 如果未来希望 `replay/system` 绕过部分 executor 检查，需要在专门入口中设计规则；当前所有 Run 创建都执行同一校验。

下一步建议：

继续进入第 6 步，收敛 LoadData explicit 选择到 Run override。当前前五步已经把 Run 创建入口、状态命名、运行模式、Pipeline 状态规则和 executor 可运行性收口，下一步应继续打硬“Pipeline 保存选择规则，Run 保存实际输入”的边界。

Codex 提示词：

```text
第5步：增加 NodeSpec executor 校验。请在 NodeDispatcher 中提供 supported_node_types/supports 方法，并在 validate_definition 中检查每个 NodeSpec 是否有真实 executor。对当前 eeg/filter/butterworth 这种有 NodeSpec 但无 dispatcher handler 的节点，先让 validate 返回明确 error，或从 registry/UI 标记为 disabled，避免运行时才失败。完成后补测试，运行可用验证，并更新 日志/2_meeting260521/Pipeline与Run功能实现工作计划.md 中第 5 步的状态、实际改动、验证结果、遗留风险和下一步建议。
```

### 第 6 步：收敛 LoadData explicit 选择到 Run override

状态：已完成

文档更新时间：2026-05-21 22:57:19 +08:00

工作目标：

落实“Pipeline 不保存具体数据，Run 保存实际输入”的边界。

具体需要改：

1. 保留现有 `selection_mode=explicit + dataset_ids` 兼容旧 Pipeline。
2. 新增 Run 创建时的输入覆盖字段，例如：

```json
{
  "selection_override": {
    "node-001": {
      "selection_mode": "explicit",
      "dataset_ids": ["..."]
    }
  }
}
```

3. `PipelineRunCreate` 增加可选 `selection_override`。
4. `PipelineExecutor.prepare_run(...)` 在解析 LoadData 时：
   - 优先使用 Run override。
   - 没有 override 时使用 Pipeline node params。
5. override 只写入 `pipeline_run_inputs.selector_json` 和 Run manifest，不写回 Pipeline definition。
6. 文档说明：
   - Pipeline 标准模式保存 filter selector。
   - 用户临时手选具体数据属于 Run override。

建议测试：

1. Pipeline filter + Run override explicit 时，Run 输入按 override 冻结。
2. Pipeline definition 不被修改。
3. 旧 explicit Pipeline 仍能兼容运行。

实际改动：

1. `elys_version1/backend/app/schemas/pipeline.py`
   - 新增 `LoadDataSelectionOverride`。
   - `PipelineRunCreate` 新增 `selection_override: dict[str, LoadDataSelectionOverride]`。
   - 支持按 LoadData `node_id` 覆盖 `selection_mode`、`dataset_ids`、`dataset_filter`。
2. `elys_version1/backend/app/pipeline/selection_override.py`
   - 新增 Run 级 LoadData override 兼容层。
   - 提供 `normalize_selection_override(...)`、`selection_override_from_run(...)`、`apply_selection_override_to_params(...)`、`apply_load_data_selection_overrides(...)`。
   - 所有处理都复制数据，不修改 Pipeline definition 原对象。
3. `elys_version1/backend/app/routers/pipelines.py`
   - Run 创建时读取并规范化 `selection_override`。
   - validation 阶段使用应用 override 后的临时 definition，避免 Pipeline 原 selector 与 Run override 不一致。
   - `result_json` 和 `async_tasks.payload_json` 写入 `selection_override`，用于任务侧和追溯。
4. `elys_version1/backend/app/pipeline/executor.py`
   - `prepare_run()` 解析 LoadData 时优先使用 Run override。
   - override 写入 `pipeline_run_inputs.selector_json.selection_override`。
   - `selector_json` 同时记录 `base_params`、最终 `params` 和 `override_applied`。
   - 对应 `PipelineNodeRun.params_json` 更新为本次 Run 实际使用的 LoadData 参数，但不改 `pipeline.definition_json`。
5. `elys_version1/backend/tests/test_pipeline_run_routes.py`
   - 补充 `selection_override` schema 默认、合法值和非法值测试。
   - 确认 Run 创建链路会追踪 `selection_override`。
6. `elys_version1/backend/tests/test_load_data_run_input_snapshots.py`
   - 新增 Pipeline filter + Run explicit override 测试。
   - 验证 override 优先、`pipeline_run_inputs.selector_json` 写入 override、Pipeline definition 不被修改。
7. `elys_version1/backend/tests/test_run_manifest.py`
   - 补充 manifest inputs 中保留 `selector_json.selection_override` 的断言。
8. `wiki/docs_v2/5-20-Pipeline工作流管理.md`
   - 明确临时手选数据走 Run `selection_override`，不写回 Pipeline。
9. `wiki/docs_v2/5-30-Run执行项管理.md`
   - 新增 Run 级数据选择覆盖说明和请求示例。
10. `wiki/docs_v2/2-50-API设计总览.md`
   - 更新 Run 创建请求体，加入 `selection_override` 字段说明。

验证结果：

1. `cd elys_version1/backend; python -m pytest tests/test_pipeline_run_routes.py tests/test_load_data_run_input_snapshots.py tests/test_run_manifest.py -q` 通过，结果为 `12 passed, 13 warnings in 0.84s`。
2. `cd elys_version1/backend; python -m pytest tests/test_pipeline_validator_executor.py -q` 通过，结果为 `3 passed, 1 warning in 0.64s`。
3. `cd elys_version1/backend; python -m compileall app tests scripts` 通过。
4. `cd elys_version1/backend; python -m pytest tests -q` 通过，结果为 `63 passed, 34 warnings in 1.15s`。
5. warnings 仍主要来自 Pydantic V2 class-based config 和 `datetime.utcnow()` 弃用提示，本步未处理。

遗留风险：

1. `selection_override` 当前只支持 LoadData 的 `selection_mode`、`dataset_ids`、`dataset_filter`，不支持覆盖其它节点参数。
2. Run override 已写入 `result_json`、`async_tasks.payload_json` 和 `pipeline_run_inputs.selector_json`，但 Run response 尚未单独顶层返回 override；调用方可从 `result_json` 或 Run inputs 查询。
3. 前端尚未提供专门的 Run 创建数据选择器入口，后续第 15 步需要接入。

下一步建议：

继续进入第 7 步，强制 `expected_version`。当前 Run 输入边界已经更清楚：Pipeline 可以保存动态 selector，Run 可以临时覆盖并冻结实际输入；下一步应防止多人编辑 Pipeline 时静默覆盖定义。

Codex 提示词：

```text
第6步：收敛 LoadData explicit 选择到 Run override。请在 PipelineRunCreate 中新增 selection_override，可按 node_id 覆盖 LoadData 的 selection_mode/dataset_ids/dataset_filter。PipelineExecutor.prepare_run 解析输入时优先使用 Run override，但不得写回 pipeline.definition_json；override 内容必须进入 pipeline_run_inputs.selector_json 和 Run manifest。保留旧 selection_mode=explicit 的兼容运行。完成后补测试并更新 docs_v2，以及 日志/2_meeting260521/Pipeline与Run功能实现工作计划.md 中第 6 步的状态、实际改动、验证结果、遗留风险和下一步建议。
```

### 第 7 步：强制 `expected_version`

状态：已完成

文档更新时间：2026-05-21 23:05:58

工作目标：

防止多人编辑 Pipeline 时静默覆盖。

具体需要改：

1. 将 `PipelineUpdate.expected_version` 改为必填。
2. Pydantic schema 缺失时返回 422。
3. 保存时版本不一致返回 409。
4. 前端保存必须带当前 `version`。
5. 文档更新“后端已强制 expected_version”。

建议测试：

1. 缺少 expected_version 返回 422。
2. expected_version 不一致返回 409。
3. expected_version 正确时保存成功且 version +1。

实际改动：

1. `elys_version1/backend/app/schemas/pipeline.py` 中 `PipelineUpdate.expected_version` 从可选字段改为必填 `int`，并要求 `ge=1`。
2. `elys_version1/backend/app/routers/pipelines.py` 中保存 Pipeline 的版本冲突判断改为无条件比较 `payload.expected_version != pipeline.version`，不再允许缺省跳过乐观锁。
3. `elys_version1/frontend/elys-web/src/types/index.ts` 中 `PipelineUpdateRequest.expected_version` 改为必填；已核对 `PipelinePage.vue` 保存现有 Pipeline 时传入 `currentPipeline.value.version`。
4. `elys_version1/backend/tests/test_pipeline_run_routes.py` 补充 schema 必填测试和路由冲突判断静态测试。
5. 更新 `wiki/docs_v2/5-00-研究管理总览.md`、`wiki/docs_v2/5-20-Pipeline工作流管理.md` 和 `wiki/docs_v2/2-50-API设计总览.md`，明确缺失版本返回 422、版本冲突返回 409。

验证结果：

1. `cd elys_version1/backend; python -m pytest tests/test_pipeline_run_routes.py -q` 通过，结果为 `8 passed in 0.25s`。
2. `cd elys_version1/backend; python -m compileall app tests scripts` 通过。
3. `cd elys_version1/backend; python -m pytest tests -q` 通过，结果为 `65 passed, 34 warnings in 1.34s`。
4. `cd elys_version1/frontend/elys-web; npm run typecheck` 通过。
5. `cd elys_version1/frontend/elys-web; npm run build` 通过。
6. `cd wiki; mkdocs build` 通过。
7. warnings 仍为既有 Pydantic V2 class-based config、`datetime.utcnow()` 弃用提示、Vite CJS API 弃用提示、`litegraph.js` eval 提示和大 chunk 提示，本步未处理。

遗留风险：

1. 当前测试主要覆盖 Pydantic schema 和路由源码约束，尚未补完整 TestClient 级 HTTP 422/409/成功保存集成测试。
2. 版本冲突时前端目前只显示通用错误信息，尚未提供差异对比、重新载入或合并入口。
3. 乐观锁只能防止提交时覆盖，不能提示“正在编辑”；后续仍需要 Pipeline edit lock。

下一步建议：

进入第 8 步，增加 Pipeline edit lock。乐观锁已经能拦住过期保存，编辑锁可以进一步降低多人长时间编辑同一 Pipeline 时的误操作概率。

Codex 提示词：

```text
第7步：强制 expected_version。请把 PipelineUpdate.expected_version 从可选改为必填，确保保存 Pipeline 时必须携带当前 version。版本不一致返回 409，缺失返回 422。同步检查前端 API 调用或测试 stub，确保保存时传入 expected_version。完成后补测试，运行可用验证，并更新 docs_v2 和 日志/2_meeting260521/Pipeline与Run功能实现工作计划.md 中第 7 步的状态、实际改动、验证结果、遗留风险和下一步建议。
```

### 第 8 步：增加 Pipeline edit lock

状态：已完成

文档更新时间：2026-05-21 23:13:48

工作目标：

在乐观锁之外，增加协作编辑锁，减少长时间编辑互相覆盖。

具体需要改：

1. 复用 `study_locks`。
2. 新增 lock_type：
   - `edit`
3. 建议 API：
   - `POST /projects/{project_id}/pipelines/{pipeline_id}/edit-lock`
   - `POST /projects/{project_id}/pipelines/{pipeline_id}/edit-lock/refresh`
   - `DELETE /projects/{project_id}/pipelines/{pipeline_id}/edit-lock`
4. 锁字段应包含：
   - locked_by
   - locked_at
   - expires_at
   - resource_kind=pipeline
   - resource_id=pipeline_id
5. Pipeline update 时可以：
   - 如果存在别人持有的 active edit lock，则返回 409 或 423。
   - 当前用户持有锁或锁过期则允许保存。
6. 前端后续打开编辑器时获取锁，关闭或离开时释放锁。

建议测试：

1. 用户 A 获取编辑锁成功。
2. 用户 B 获取同一 Pipeline 编辑锁返回冲突。
3. 锁过期后用户 B 可获取。
4. 非锁持有人保存返回冲突。

实际改动：

1. `elys_version1/backend/app/services/study_locks.py` 新增 `refresh_study_lock()`，用于续期已有锁并记录 `refresh_reason`、`refreshed_by`、`refreshed_at`。
2. `elys_version1/backend/app/schemas/pipeline.py` 新增 `PipelineEditLockResponse`，并在 `elys_version1/backend/app/schemas/__init__.py` 导出；响应返回 `lock_id`、`locked_by`、`locked_at`、`expires_at`、`metadata_json` 等编辑锁信息。
3. `elys_version1/backend/app/routers/pipelines.py` 新增 Pipeline edit lock 兼容 API：
   - `POST /api/v1/projects/{project_id}/pipelines/{pipeline_id}/edit-lock`
   - `POST /api/v1/projects/{project_id}/pipelines/{pipeline_id}/edit-lock/refresh`
   - `DELETE /api/v1/projects/{project_id}/pipelines/{pipeline_id}/edit-lock`
4. edit lock 复用 `study_locks`，字段语义为 `resource_kind=pipeline`、`resource_id=pipeline_id`、`lock_type=edit`，TTL 当前为 30 分钟。
5. 获取锁时，同一用户重复获取会续期；其他用户持有 active edit lock 时返回 409，错误体包含 `code=PIPELINE_EDIT_LOCKED`、`lock_id`、`locked_by`、`locked_at`、`expires_at`。
6. `Pipeline update` 保存前会调用 `ensure_pipeline_edit_lock_available()`：无 active edit lock 或当前用户持有 edit lock 时允许保存；其他用户持有 active edit lock 时返回 409。
7. 获取、续期、释放 edit lock 均写入 `audit_events`：`pipeline.edit_lock.acquired`、`pipeline.edit_lock.refreshed`、`pipeline.edit_lock.released`。
8. 更新 docs_v2：`5-20 Pipeline 工作流管理`、`2-50 API 设计总览`、`5-00 研究管理总览`、`5-10 Study 研究项管理`、`7-40 工作流执行与后台任务`、`2-60 任务队列与异步架构`。

验证结果：

1. `cd elys_version1/backend; python -m pytest tests/test_pipeline_run_routes.py -q` 通过，结果为 `11 passed, 2 warnings in 0.56s`。
2. `cd elys_version1/backend; python -m compileall app tests scripts` 通过。
3. `cd elys_version1/backend; python -m pytest tests -q` 通过，结果为 `68 passed, 35 warnings in 1.21s`。
4. `cd wiki; mkdocs build` 通过。
5. warnings 仍为既有 Pydantic V2 class-based config、`datetime.utcnow()` 弃用提示和 Material for MkDocs 上游提示，本步未处理。

遗留风险：

1. 当前测试覆盖路由路径、写权限调用、保存前 edit lock 检查、响应 schema 和续期服务；尚未补完整 TestClient/真实数据库级“用户 A 获取、用户 B 冲突、过期后可获取”的端到端测试。
2. 前端尚未在打开 Pipeline 编辑器时自动获取 edit lock、定时续期、离开释放；后续第 15 步需要接入。
3. 当前没有管理员强制释放他人 edit lock 的 API；MVP 依赖 `expires_at` 自动失效。
4. Pipeline update 仍兼容“无 edit lock 也可保存”，这是为了不破坏旧前端；前端接入完成后可再考虑是否强制必须持锁保存。

下一步建议：

进入第 9 步，增加 Run cancel。编辑锁和运行锁现在都复用了 `study_locks`，下一步取消 Run 时应重点保证 queued/running/waiting_user_input 状态正确收口、释放 `lock_type=run` 的锁，并生成或刷新 run manifest。

Codex 提示词：

```text
第8步：增加 Pipeline edit lock。请复用 study_locks，为 Pipeline 编辑增加 lock_type=edit 的获取、续期、释放 API，并在 Pipeline update 时检查是否存在其他用户持有的 active edit lock。锁必须有 expires_at，过期锁应自动释放或忽略。完成后补权限和冲突测试，更新 docs_v2，并更新 日志/2_meeting260521/Pipeline与Run功能实现工作计划.md 中第 8 步的状态、实际改动、验证结果、遗留风险和下一步建议。
```

### 第 9 步：增加 Run cancel

状态：已完成

文档更新时间：2026-05-21 23:24:00

工作目标：

允许用户取消 queued/running/waiting_user_input 的 Run，并正确释放锁和留下追溯证据。

具体需要改：

1. 新增 API：
   - `POST /projects/{project_id}/pipeline-runs/{run_id}/cancel`
2. 状态规则：
   - queued -> cancelled
   - running -> cancel_requested 或直接 cancelled，取决于 Celery 支持
   - waiting_user_input -> cancelled
   - completed/failed/cancelled 不可取消，返回 409
3. 接入 Celery：
   - 对 queued/running task 调用 revoke。
   - Worker 后续应能识别取消请求。
4. 释放 study run lock。
5. 写 `task_events`。
6. 写 `audit_events`。
7. 生成或刷新 Run manifest。

建议测试：

1. queued Run cancel 后状态为 cancelled。
2. completed Run cancel 返回 409。
3. cancel 后锁被释放。
4. manifest 包含 cancelled 状态。

实际改动：

1. `elys_version1/backend/app/routers/pipelines.py` 新增 `POST /api/v1/projects/{project_id}/pipeline-runs/{run_id}/cancel`，返回 `PipelineRunResponse`。
2. 新增 Run 取消规则：只允许取消 `queued`、`running`、`waiting_user_input`；`completed`、`failed`、`cancelled/canceled` 等状态返回 409，错误体包含 `code=PIPELINE_RUN_NOT_CANCELABLE` 和当前状态。
3. 取消时统一写 `pipeline_runs.status=cancelled`，设置 `finished_at`，在 `result_json` 记录 `cancelled_by`、`cancelled_at`、`previous_status` 和 `celery_revoke`，并把 active node runs 标记为 `cancelled`。
4. 取消时查找关联 `async_tasks`，对 `queued/running/retrying` task 写 `task_events(event_type=run_cancelled,status=cancelled,progress=100)`；对已结束 task 写 `run_cancelled` 事件但保留 task 原状态。
5. 取消时通过 `best_effort_revoke_pipeline_task()` 调用 `run_pipeline_task.app.control.revoke(..., terminate=False)`，失败不阻断 Run 取消。
6. 取消时释放 `study_locks` 中 `lock_type=run` 的锁，优先使用 `async_tasks.payload_json.lock_id`，否则按 Pipeline 资源兜底释放。
7. 取消时写 `audit_events(action=pipeline.run.cancelled)`，并调用 `generate_run_manifest()` 生成或刷新 Run Manifest。
8. `elys_version1/backend/app/pipeline/background.py` 增加启动前取消防护：worker 若拿到已 `cancelled/canceled` 的 Run，直接返回，不再执行节点。
9. `elys_version1/backend/tests/test_pipeline_run_routes.py` 补充 Run cancel 路由、权限、状态规则、revoke、锁释放、task event、audit 和 manifest 的源码级测试。
10. 更新 docs_v2：`5-30 Run 执行项管理`、`2-50 API 设计总览`、`2-60 任务队列与异步架构`、`7-40 工作流执行与后台任务`、`5-00 研究管理总览`、`5-10 Study 研究项管理`。

验证结果：

1. `cd elys_version1/backend; python -m pytest tests/test_pipeline_run_routes.py -q` 通过，结果为 `14 passed, 2 warnings in 0.64s`。
2. `cd elys_version1/backend; python -m compileall app tests scripts` 通过。
3. `cd elys_version1/backend; python -m pytest tests -q` 通过，结果为 `71 passed, 35 warnings in 1.26s`。
4. `cd wiki; mkdocs build` 通过。
5. warnings 仍为既有 Pydantic V2 class-based config、`datetime.utcnow()` 弃用提示和 Material for MkDocs 上游提示，本步未处理。

遗留风险：

1. Celery revoke 当前为 best-effort，使用 `terminate=False`，不会强杀正在执行的 worker 进程。
2. Worker 已能在任务启动前跳过已取消 Run，但运行中长耗时节点还没有完整协作式取消检查；如果节点已经开始执行，可能需要等节点结束后才停止，后续应在 executor/dispatcher/engine 安全点检查取消状态。
3. 当前测试主要是源码级和 schema/service 级覆盖，尚未补真实 FastAPI TestClient + 数据库 + Celery broker 的端到端取消回归。
4. Task cancel/retry API 仍未实现，当前只提供 Run cancel 入口。

下一步建议：

进入第 10 步，增加 Run retry。Run cancel 已经能把旧 Run 收口到 `cancelled`，下一步应从 `failed/cancelled` Run 创建新的 Run，不覆盖旧 Run，并明确是复用旧输入快照还是重新解析当前输入。

Codex 提示词：

```text
第9步：增加 Run cancel。请新增 POST /api/v1/projects/{project_id}/pipeline-runs/{run_id}/cancel，支持取消 queued/running/waiting_user_input Run。取消时更新 pipeline_runs.status=cancelled，写 task_events 和 audit_events，释放 study_locks 运行锁，并生成或刷新 run_manifest。Celery revoke 可先做 best-effort；若 worker 取消检查尚未完整实现，请在遗留风险中说明。完成后补测试并更新 docs_v2，以及 日志/2_meeting260521/Pipeline与Run功能实现工作计划.md 中第 9 步的状态、实际改动、验证结果、遗留风险和下一步建议。
```

### 第 10 步：增加 Run retry

状态：已完成

文档更新时间：2026-05-21 23:31:29

工作目标：

失败后允许规范重试，但不覆盖旧 Run。

具体需要改：

1. 新增 API：
   - `POST /projects/{project_id}/pipeline-runs/{run_id}/retry`
2. 只能 retry：
   - failed
   - cancelled，可选
3. retry 行为：
   - 创建一个新 Run。
   - 默认复用旧 Run 的 `definition_snapshot`。
   - 默认复用旧 Run 的 `pipeline_run_inputs`，或提供重新解析选项。
4. 建议字段：

```json
{
  "input_policy": "reuse_snapshot | re_resolve",
  "save_policy": "temporary | current | pinned",
  "reason": "..."
}
```

5. 新 Run 记录与旧 Run 的关系：
   - result_json.retry_of_run_id
   - 或新增 dependency_kind=retry_of
6. 不要修改旧 Run 的状态或输出。

建议测试：

1. failed Run retry 创建新 Run。
2. completed Run retry 返回 409 或要求明确 duplicate/replay。
3. 新旧 Run 可追溯。

实际改动：

1. `elys_version1/backend/app/schemas/pipeline.py` 新增 `PipelineRunRetryRequest`，字段为 `input_policy`，允许 `reuse_snapshot` 和 `re_resolve`，默认 `reuse_snapshot`；并在 `schemas/__init__.py` 导出。
2. `elys_version1/backend/app/routers/pipelines.py` 新增 `POST /api/v1/projects/{project_id}/pipeline-runs/{run_id}/retry`，返回新的 `PipelineRunResponse`。
3. retry 只允许从 `failed`、`cancelled`、`canceled` 状态创建；其他状态返回 409，错误体包含 `code=PIPELINE_RUN_NOT_RETRYABLE`。
4. 新 Run 使用旧 Run 的 `definition_snapshot`、`pipeline_version`、`run_mode` 和 `save_policy`，`trigger=retry`，并重新分配 `run_seq`、`run_id`、`async_task_id` 和 Celery task。
5. 默认 `input_policy=reuse_snapshot` 会复制旧 Run 的 `pipeline_run_inputs` 到新 Run，并在 `resolved_metadata_json.retry` 中记录 `retry_of_run_id`、源 input id 和输入策略；复制后会把新 input snapshot 关联到新 node runs。
6. `input_policy=re_resolve` 已预留并可用：不复制旧输入，而是基于旧 `definition_snapshot` 重新解析输入。
7. 若默认 `reuse_snapshot` 遇到有 LoadData 节点但旧 Run 没有输入快照，则返回 409，提示使用 `input_policy=re_resolve`。
8. 新 Run 写入 `pipeline_run_dependencies(dependency_kind=retry_of)` 指向旧 Run，同时在 `result_json.retry_of_run_id` 和 `async_tasks.payload_json.retry_of_run_id` 记录追溯关系。
9. retry 会重新创建 `async_tasks`，写 `task_events(created/dispatched)`，写 `audit_events(action=pipeline.run.retry_queued)`，并通过 `run_pipeline_task.apply_async()` 派发。
10. `elys_version1/backend/tests/test_pipeline_run_routes.py` 补充 retry 路由、权限、状态规则、新 Run/Task/lineage、输入快照复用和 `re_resolve` 预留测试。
11. 更新 docs_v2：`5-30 Run 执行项管理`、`2-50 API 设计总览`、`2-60 任务队列与异步架构`、`7-40 工作流执行与后台任务`、`5-00 研究管理总览`、`5-10 Study 研究项管理`。

验证结果：

1. `cd elys_version1/backend; python -m pytest tests/test_pipeline_run_routes.py -q` 通过，结果为 `17 passed, 2 warnings in 0.72s`。
2. `cd elys_version1/backend; python -m compileall app tests scripts` 通过。
3. `cd elys_version1/backend; python -m pytest tests -q` 通过，结果为 `74 passed, 35 warnings in 1.46s`。
4. `cd wiki; mkdocs build` 通过。
5. warnings 仍为既有 Pydantic V2 class-based config、`datetime.utcnow()` 弃用提示和 Material for MkDocs 上游提示，本步未处理。

遗留风险：

1. 当前测试主要为源码级覆盖，尚未补真实数据库级端到端验证：failed/cancelled Run retry 后新 Run 输入快照与旧 Run 完全一致、旧 Run 不变、Celery 派发成功。
2. `input_policy=reuse_snapshot` 已复制旧输入快照，但如果旧 Run 的输入快照本身缺失或质量不完整，只能提示改用 `re_resolve`；后续应在 UI 明确展示两种策略差异。
3. `input_policy=re_resolve` 会用旧 `definition_snapshot` 重新解析当前可用输入，可能得到与旧 Run 不同的数据集合；这是设计预留能力，需要前端明确提示。
4. retry 当前从头执行整个 Pipeline，不支持“从失败节点继续”或节点级 checkpoint 恢复。

下一步建议：

进入第 11 步，增加 Task cancel/retry。Run 层的 cancel/retry 已经能管理业务执行项；下一步应让普通 `async_tasks` 也能被取消或重试，并明确 pipeline_run task 应引导到 Run cancel/retry，而不是直接重跑旧 Run。

Codex 提示词：

```text
第10步：增加 Run retry。请新增 POST /api/v1/projects/{project_id}/pipeline-runs/{run_id}/retry，从 failed 或 cancelled Run 创建一个新的 Run，不覆盖旧 Run。新 Run 默认复用旧 Run 的 definition_snapshot 和输入快照，可预留 input_policy=reuse_snapshot/re_resolve。记录 retry_of_run_id 或等价追溯信息，重新创建 async_task 并派发。完成后补测试、更新 docs_v2，并更新 日志/2_meeting260521/Pipeline与Run功能实现工作计划.md 中第 10 步的状态、实际改动、验证结果、遗留风险和下一步建议。
```

### 第 11 步：增加 Task cancel/retry

状态：已完成

文档更新时间：2026-05-21 23:48:16 +08:00

工作目标：

让后台任务成为可管理对象，而不只是只读状态。

具体需要改：

1. 新增 API：
   - `POST /projects/{project_id}/tasks/{task_id}/cancel`
   - `POST /projects/{project_id}/tasks/{task_id}/retry`
2. cancel 规则：
   - queued/running 可取消。
   - succeeded/failed/cancelled 不可重复取消。
3. retry 规则：
   - failed/cancelled 可 retry。
   - 对 pipeline_run task，优先走 Run retry，而不是直接重跑同一 Run。
4. 写 `task_events`。
5. 任务状态机和 Run 状态机需要保持一致。

建议测试：

1. failed task retry 产生新 task 或提示使用 Run retry。
2. running task cancel 写 event。
3. 不允许 retry succeeded task。

实际改动：

1. `elys_version1/backend/app/routers/pipelines.py` 新增 `POST /api/v1/projects/{project_id}/tasks/{task_id}/cancel`，返回 `AsyncTaskResponse`。
2. Task cancel 支持 `queued`、`running`、`retrying`。普通 Task 会写 `task_events(event_type=cancelled,status=cancelled,progress=100)`，在 `result_json` 记录取消人、取消时间、原状态和 Celery revoke 结果，并写 `audit_events(action=async_task.cancelled)`。
3. Task cancel 对 `pipeline_run` Task 不只改 Task：会查找对应 `PipelineRun`，复用 Run cancel 的核心逻辑，更新 Run 为 `cancelled`、写 `run_cancelled` 事件、释放运行锁、刷新 Run Manifest，并写 `audit_events(action=pipeline.run.cancelled, source=task_cancel)`。
4. 新增 `best_effort_revoke_async_task()`，对普通 Task 调用 `celery_app.control.revoke(..., terminate=False)`；`pipeline_run` Task 继续复用 `best_effort_revoke_pipeline_task()`。
5. `elys_version1/backend/app/routers/pipelines.py` 新增 `POST /api/v1/projects/{project_id}/tasks/{task_id}/retry`。普通文件任务只允许从 `failed/cancelled/canceled` 创建新 Task，支持的类型为 `artifact_cleanup`、`dataset_import`、`raw_bids_build`、`canonical_fif_rebuild`。
6. Task retry 不覆盖旧 Task，会复制旧 `payload_json` 并追加 `retry_of_task_id`、`retry_source_status`、`retry_requested_by`、`retry_requested_at`，再通过统一 `create_and_dispatch_file_task()` 创建并派发新 Task。
7. `pipeline_run` Task retry 不直接重跑旧 Run，返回 409 和 `code=TASK_RETRY_USE_RUN_RETRY`，并给出 `/api/v1/projects/{project_id}/pipeline-runs/{run_id}/retry` 引导。
8. `elys_version1/backend/app/tasks/file_tasks.py` 增加启动前取消防护：worker 如果拿到已 `cancelled/canceled` 的文件 Task，直接返回，不再执行文件任务逻辑。
9. `elys_version1/backend/tests/test_pipeline_run_routes.py` 补充 Task cancel/retry 路由、权限、状态常量、revoke、pipeline_run 同步取消、retry 引导、文件任务重试和 worker 预取消防护的源码级测试。
10. 更新 docs_v2：`2-60 任务队列与异步架构`、`2-50 API 设计总览`、`5-30 Run 执行项管理`、`7-40 工作流执行与后台任务`、`2-00 系统架构总览`、`3-00 数据库设计总览`、`5-00 研究管理总览`、`5-10 Study 研究项管理`、`7-00 后端架构总览` 和 `0-50 变更记录`。

验证结果：

1. `cd elys_version1/backend; python -m pytest tests/test_pipeline_run_routes.py -q` 通过，结果为 `21 passed, 2 warnings in 0.78s`。
2. `cd elys_version1/backend; python -m compileall app/tasks/file_tasks.py app/routers/pipelines.py` 通过。
3. `cd elys_version1/backend; python -m compileall app tests scripts` 通过。
4. `cd elys_version1/backend; python -m pytest tests -q` 通过，结果为 `78 passed, 35 warnings in 1.48s`。
5. `cd wiki; mkdocs build` 通过，文档构建耗时 `1.81 seconds`。
6. warnings 仍为既有 Pydantic V2 class-based config、`datetime.utcnow()` 弃用提示和 Material for MkDocs 上游提示，本步未处理。

遗留风险：

1. Celery revoke 仍为 best-effort，使用 `terminate=False`，不会强杀已经进入执行中的 worker。
2. 文件任务已能在启动前跳过已取消 Task，但运行中长耗时文件任务还没有协作式取消检查。
3. `pipeline_run` Task cancel 会同步取消 Run，但真实 Celery broker/worker 的端到端撤销效果尚未在 staging 环境验证。
4. Task retry 当前只支持普通文件任务；Pipeline Run 的失败重跑必须走 Run retry，不支持直接重试旧 Task。

下一步建议：

进入第 12 步，增加任务事件 SSE。当前已有 Task 查询、事件列表、cancel/retry；下一步应基于 `task_events` 提供事件流或轮询友好的 `since` 参数，让前端不用高频全量轮询任务状态。

Codex 提示词：

```text
第11步：增加 Task cancel/retry。请为 async_tasks 增加 POST /api/v1/projects/{project_id}/tasks/{task_id}/cancel 和 /retry。cancel 需写 task_events 并 best-effort revoke Celery；retry 对普通文件任务可创建新 task，对 pipeline_run task 应引导或复用 Run retry，避免直接改旧 Run。完成后补测试、更新任务队列 docs_v2，并更新 日志/2_meeting260521/Pipeline与Run功能实现工作计划.md 中第 11 步的状态、实际改动、验证结果、遗留风险和下一步建议。
```

### 第 12 步：增加任务事件 SSE

状态：已完成

文档更新时间：2026-05-21 23:58:22 +08:00

工作目标：

减少前端轮询，让长任务有实时进度。

具体需要改：

1. 新增只读事件流 API：
   - `GET /projects/{project_id}/tasks/{task_id}/events/stream`
   - 可选 Study 级：`GET /projects/{project_id}/tasks/events/stream`
2. SSE 输出：
   - task.created
   - task.started
   - task.progress
   - task.succeeded
   - task.failed
   - task.cancelled
3. 保留现有 events list API。
4. 注意鉴权和断线重连。
5. 如当前环境不适合 SSE，可先实现轮询友好的 `since` 参数。

建议测试：

1. events list 仍可用。
2. SSE endpoint 鉴权可用。
3. 新事件可被流式读取，或至少有单元测试覆盖生成器。

实际改动：

1. `elys_version1/backend/app/routers/pipelines.py` 新增 `GET /api/v1/projects/{project_id}/tasks/{task_id}/events/stream`，返回 `StreamingResponse(media_type="text/event-stream")`。
2. SSE route 先通过 `get_project_for_read()` 和 `get_async_task_or_404()` 做鉴权与任务可见性检查，不绕过现有权限模型。
3. 新增 `task_event_stream_generator()`，流内使用独立 `SessionLocal()` 轮询 `task_events`，避免复用请求级 session 持有长连接。
4. SSE 事件格式固定为：
   - `ready`：连接建立；
   - `task_event`：新 `task_events` 记录；
   - `heartbeat`：空闲心跳；
   - `stream_closed`：达到最长连接时间或任务不可见。
5. SSE `id` 使用 `task_events.id`；客户端可用 `Last-Event-ID` 或 `?since=<event_id|ISO时间>` 断线续读。
6. 现有 `GET /api/v1/projects/{project_id}/tasks/{task_id}/events` 保持兼容，并新增可选 `since` 参数用于增量轮询。
7. 新增 `normalize_task_event_since()`、`query_task_events()`、`task_event_stream_payload()` 和 `format_sse_event()` 等 helper，统一事件查询和 SSE 序列化。
8. `elys_version1/backend/tests/test_pipeline_run_routes.py` 补充 Task events stream 路由、`Last-Event-ID`、SSE header、生成器轮询、heartbeat、stream close 和 events list `since` 的源码级测试。
9. 更新 docs_v2：`2-60 任务队列与异步架构`、`2-50 API 设计总览`、`5-30 Run 执行项管理`、`7-40 工作流执行与后台任务`、`2-00 系统架构总览`、`3-00 数据库设计总览`、`5-00 研究管理总览`、`7-00 后端架构总览` 和 `0-50 变更记录`。

验证结果：

1. `cd elys_version1/backend; python -m pytest tests/test_pipeline_run_routes.py -q` 通过，结果为 `24 passed, 2 warnings in 1.02s`。
2. `cd elys_version1/backend; python -m compileall app/routers/pipelines.py` 通过。
3. `cd elys_version1/backend; python -m compileall app tests scripts` 通过。
4. `cd elys_version1/backend; python -m pytest tests -q` 通过，结果为 `81 passed, 35 warnings in 1.63s`。
5. `cd wiki; mkdocs build` 通过，文档构建耗时 `1.84 seconds`。
6. warnings 仍为既有 Pydantic V2 class-based config、`datetime.utcnow()` 弃用提示和 Material for MkDocs 上游提示，本步未处理。

遗留风险：

1. 当前完成的是 Task 级 SSE；Study 级或 Run 详情页一次订阅多个 Task 的聚合流仍未实现。
2. 测试以源码级和编译验证为主，尚未在真实浏览器 EventSource、Nginx 反代、真实 PostgreSQL/Celery worker 环境做长连接回归。
3. SSE generator 使用轮询数据库方式实现，适合 MVP；高并发任务面板后续可评估 Redis pub/sub 或 LISTEN/NOTIFY。
4. 默认连接有 `max_seconds` 上限，到期会发送 `stream_closed`；前端需要按 SSE 断线重连逻辑重新连接。

下一步建议：

进入第 13 步，增加 Run lineage 聚合视图。任务状态现在能查、能取消、能重试、能流式读取；下一步应让用户在 Run 详情里看清输入、输出、上游依赖、下游依赖和哪些 Artifact 会阻止清理。

Codex 提示词：

```text
第12步：增加任务事件 SSE。请在现有 task_events 查询基础上新增任务事件流接口，例如 GET /api/v1/projects/{project_id}/tasks/{task_id}/events/stream。若当前测试环境不适合完整 SSE，可先实现事件生成器和 since 参数，保留 events list API 兼容。注意鉴权、断线重连和事件格式。完成后补测试、更新 docs_v2，并更新 日志/2_meeting260521/Pipeline与Run功能实现工作计划.md 中第 12 步的状态、实际改动、验证结果、遗留风险和下一步建议。
```

### 第 13 步：增加 Run lineage 聚合视图

状态：已完成

文档更新时间：2026-05-22 00:07:30 +08:00

工作目标：

让用户一眼看懂某次 Run 用了哪些数据、产生哪些输出、依赖谁、被谁依赖。

具体需要改：

1. 新增 API：
   - `GET /projects/{project_id}/pipeline-runs/{run_id}/lineage`
2. 返回结构建议：

```json
{
  "run": {},
  "inputs": [],
  "artifacts": [],
  "upstream_runs": [],
  "downstream_runs": [],
  "blocked_cleanup_artifacts": []
}
```

3. 聚合来源：
   - `pipeline_run_inputs`
   - `pipeline_artifacts`
   - `pipeline_run_dependencies`
   - 下游依赖反查
4. 可选返回 mermaid 或 graph nodes/edges 给前端。

建议测试：

1. 有上游 Artifact 依赖时 lineage 返回 upstream。
2. 被其他 Run 依赖时 lineage 返回 downstream。
3. 无依赖时返回空数组。

实际改动：

1. `elys_version1/backend/app/schemas/pipeline.py` 新增 `PipelineRunLineageGraphNode`、`PipelineRunLineageGraphEdge` 和 `PipelineRunLineageResponse`。
2. `elys_version1/backend/app/schemas/__init__.py` 导出新增 lineage schema。
3. `elys_version1/backend/app/routers/pipelines.py` 新增 `GET /api/v1/projects/{project_id}/pipeline-runs/{run_id}/lineage`，返回 `PipelineRunLineageResponse`。
4. 新增 `build_pipeline_run_lineage_response()` 聚合：
   - `pipeline_run_inputs`；
   - 当前 Run 的全部 `pipeline_artifacts`，包括 `deleted` 状态；
   - `pipeline_run_dependencies.run_id = 当前 Run` 的上游依赖；
   - `pipeline_run_dependencies.depends_on_run_id = 当前 Run` 的下游反向依赖；
   - `pipeline_run_dependencies.upstream_artifact_id in 当前 Run 输出 Artifact` 的下游反向依赖。
5. 返回结构包含 `run`、`inputs`、`artifacts`、`upstream_runs`、`downstream_runs`、`upstream_dependencies`、`downstream_dependencies`、`graph_nodes` 和 `graph_edges`。
6. 图节点使用稳定 id：`run:{run_id}`、`input:{pipeline_run_input_id}`、`artifact:{pipeline_artifact_id}`，图边覆盖 input_to_run、produces、upstream_run_input、upstream_artifact_input、uses_artifact、artifact_used_by 等关系。
7. 保持 `GET /api/v1/projects/{project_id}/pipeline-runs/{run_id}` Run detail 响应不变，没有把 lineage 字段塞进既有详情响应。
8. `elys_version1/backend/tests/test_pipeline_run_routes.py` 补充 lineage route、read 权限、独立 response schema、Run detail 不变、聚合来源和 graph nodes/edges 的源码级测试。
9. 更新 docs_v2：`5-30 Run 执行项管理`、`2-50 API 设计总览`、`7-40 工作流执行与后台任务`、`5-00 研究管理总览`、`3-40 Run 与 Artifact 追溯表` 和 `0-50 变更记录`。

验证结果：

1. `cd elys_version1/backend; python -m pytest tests/test_pipeline_run_routes.py -q` 通过，结果为 `27 passed, 2 warnings in 0.93s`。
2. `cd elys_version1/backend; python -m compileall app/routers/pipelines.py app/schemas/pipeline.py app/schemas/__init__.py` 通过。
3. `cd elys_version1/backend; python -m compileall app tests scripts` 通过。
4. `cd elys_version1/backend; python -m pytest tests -q` 通过，结果为 `84 passed, 35 warnings in 1.66s`。
5. `cd wiki; mkdocs build` 通过，文档构建耗时 `1.70 seconds`。
6. warnings 仍为既有 Pydantic V2 class-based config、`datetime.utcnow()` 弃用提示和 Material for MkDocs 上游提示，本步未处理。

遗留风险：

1. 当前测试主要是源码级约束，尚未用真实数据库构造“Run A 输出 Artifact -> Run B 使用 -> lineage 反查 downstream”的端到端数据验证。
2. lineage graph 当前是后端聚合结构，前端图视图、过滤、折叠、节点点击跳转还未接入。
3. 当前 downstream 只覆盖 `pipeline_run_dependencies` 中记录的依赖；如果未来有报告、analysis_results 或外部导出引用 Artifact，还需要继续扩展反向依赖来源。
4. 当前 lineage 返回当前 Run 的全部 Artifact，包括 `deleted`，便于追溯；前端展示时需要根据 `retention_status` 做视觉区分。

下一步建议：

进入第 14 步，增加 Artifact pin/unpin/hide 语义 API。lineage 已能告诉用户哪些输出被下游依赖，下一步应把 Artifact 操作从直接改 `retention_status` 收口成固定、取消固定、隐藏等产品动作，并在有依赖时返回清晰 blocker。

Codex 提示词：

```text
第13步：增加 Run lineage 聚合视图。请新增 GET /api/v1/projects/{project_id}/pipeline-runs/{run_id}/lineage，聚合 pipeline_run_inputs、pipeline_artifacts、pipeline_run_dependencies 和下游反向依赖，返回 inputs/artifacts/upstream_runs/downstream_runs/graph nodes edges。不要改变既有 Run detail 响应。完成后补测试、更新 docs_v2，并更新 日志/2_meeting260521/Pipeline与Run功能实现工作计划.md 中第 13 步的状态、实际改动、验证结果、遗留风险和下一步建议。
```

### 第 14 步：增加 Artifact pin/unpin/hide 语义 API

状态：已完成

文档更新时间：2026-05-22 00:16:57 +08:00

工作目标：

把用户操作从“改 retention_status”变成更容易理解的产品动作。

具体需要改：

1. 保留现有 retention patch。
2. 新增语义 API：
   - `POST /projects/{project_id}/pipeline-artifacts/{artifact_id}/pin`
   - `POST /projects/{project_id}/pipeline-artifacts/{artifact_id}/unpin`
   - `POST /projects/{project_id}/pipeline-artifacts/{artifact_id}/hide`
3. 映射：
   - pin -> `pinned`
   - unpin -> `current` 或 `cached`，需要按原状态或参数决定
   - hide -> 可新增 `hidden` 字段，或短期映射为 `deleted` 但不物理删除
4. 如果 hide/delete 遇到依赖，返回 blocker detail。
5. 写 audit event。

实际改动：

1. 后端新增 `PipelineArtifactActionRequest`，用于 pin/unpin/hide 语义接口的可选 `reason` 入参。
2. `routers/pipelines.py` 保留原有 `PATCH /projects/{project_id}/pipeline-artifacts/{artifact_id}/retention`，并抽出 `apply_pipeline_artifact_retention_action()` 统一处理状态映射、依赖检查、删除标记和审计写入。
3. 新增语义接口：
   - `POST /projects/{project_id}/pipeline-artifacts/{artifact_id}/pin` -> `retention_status='pinned'`
   - `POST /projects/{project_id}/pipeline-artifacts/{artifact_id}/unpin` -> `retention_status='current'`
   - `POST /projects/{project_id}/pipeline-artifacts/{artifact_id}/hide` -> `retention_status='deleted'`
4. `hide` 和兼容 `retention_status='deleted'` 都复用 `assert_artifact_can_be_deleted()`；如果 Artifact 已被下游 Run 输入或 `pipeline_run_dependencies` 引用，返回 409 和依赖详情。
5. 成功的 pin/unpin/hide/retention patch 都写 `audit_events`；被 blocker 拒绝的 hide/delete 或对 hidden artifact 执行 pin/unpin，也会写 `.blocked` 审计事件后返回 409。
6. 语义接口不会把 hidden/deleted Artifact 通过 pin/unpin 恢复；若确实需要恢复，仍保留旧 retention patch 作为显式兼容入口。
7. docs_v2 已同步更新 API 总览、Run 执行项管理、Run 与 Artifact 追溯表、Study 输出与 Artifact、后端架构总览、工作流执行与后台任务和变更记录。

验证结果：

1. `cd elys_version1/backend; python -m compileall app/routers/pipelines.py app/schemas/pipeline.py app/schemas/__init__.py tests/test_pipeline_run_routes.py` 通过。
2. `cd elys_version1/backend; python -m pytest tests/test_pipeline_run_routes.py -q` 通过，结果为 `30 passed, 2 warnings in 1.15s`。
3. `cd elys_version1/backend; python -m compileall app tests scripts` 通过。
4. `cd elys_version1/backend; python -m pytest tests -q` 通过，结果为 `87 passed, 35 warnings in 1.74s`。
5. `cd wiki; mkdocs build` 通过，文档构建耗时 `1.61 seconds`。
6. warnings 仍为既有 Pydantic V2 class-based config、`datetime.utcnow()` 弃用提示和 Material for MkDocs 上游提示，本步未处理。

遗留风险：

1. 当前测试以源码级约束和轻量 schema 验证为主，尚未用真实数据库 HTTP client 构造“被依赖 Artifact hide 返回 409”的端到端用例。
2. hide 当前映射为 `deleted`，属于逻辑隐藏，不物理移动文件到 trash；后续物理清理仍需要独立策略。
3. unpin 当前统一回到 `current`，没有恢复到原来的 `cached/temporary`；如果后续产品需要“取消固定后恢复原状态”，需要在 metadata 或单独字段中保存 pinned 前状态。
4. pin/unpin/hide 后暂未自动刷新已有 Run manifest；manifest 若要展示最新 Artifact 保留状态，需要在前端实时查 Artifact 或后续补 manifest refresh。

下一步建议：

进入第 15 步：前端接入 Pipeline/Run 新规范。后端已有 Run 创建、Run detail、lineage、Task events、Artifact 语义操作，下一步应把这些能力变成界面上的 run_mode/save_policy 选择、编辑锁提示、Run detail 分栏、lineage 图入口和 Artifact 固定/取消固定/隐藏按钮。

Codex 提示词：

```text
第14步：增加 Artifact pin/unpin/hide 语义 API。请保留现有 retention patch，同时新增 pin、unpin、hide 语义接口，内部映射 retention_status 或预留 hidden 语义。hide/delete 前必须复用依赖检查，存在 blocker 时返回 409 和依赖详情。所有操作写 audit_events。完成后补测试、更新 docs_v2，并更新 日志/2_meeting260521/Pipeline与Run功能实现工作计划.md 中第 14 步的状态、实际改动、验证结果、遗留风险和下一步建议。
```

### 第 15 步：前端接入 Pipeline/Run 新规范

状态：已完成

文档更新时间：2026-05-22 00:52:20 +08:00

工作目标：

让用户在界面上能使用新规范，而不是只停留在后端 API。

具体需要改：

1. Pipeline 编辑器：
   - 保存时携带 `expected_version`。
   - 显示编辑锁状态。
   - 无 executor 的节点隐藏或禁用。
2. Run 创建对话框：
   - `run_mode` 选择。
   - `save_policy` 选择。
   - `trial` / `analysis` 文案区分。
   - Pipeline 状态不允许运行时置灰。
3. Run detail：
   - summary
   - inputs
   - node runs
   - tasks/events
   - artifacts
   - manifest
   - lineage
4. Task 进度：
   - 先轮询，后 SSE。
5. Artifact 操作：
   - 固定结果。
   - 取消固定。
   - 隐藏输出。
   - 清理缓存。
6. 前端文案统一：
   - Project 展示为 Study / 研究项。
   - Run 成功展示 completed / 已完成。

建议验证：

1. 本地前端构建通过。
2. 用浏览器或 Playwright 走一遍创建 Pipeline、Run、查看 detail。
3. 移动端/小屏文字不重叠。

实际改动：

1. `elys_version1/frontend/elys-web/src/types/index.ts`
   - 新增 `PipelineRunMode`、`PipelineRunSavePolicy`、`PipelineRunCreateRequest`。
   - 扩展 `PipelineRun`、`PipelineRunDetail`、`PipelineArtifact`，补齐 `run_mode`、`save_policy`、`manifest_json`、`inputs`、`dependencies`、`tasks`、`retention_status`、`storage_uri`、`sha256` 等前端类型。
   - 新增 `PipelineRunInput`、`AsyncTask`、`TaskEvent`、`PipelineRunLineage` 和 `ArtifactCleanupTaskRequest`。
2. `elys_version1/frontend/elys-web/src/api/pipelines.ts`
   - Run 创建默认改为标准入口 `POST /projects/{project_id}/pipelines/{pipeline_id}/runs`，旧 `/run` 仅由后端兼容。
   - 新增 `getRunManifest()`、`getRunLineage()`、`pinArtifact()`、`unpinArtifact()`、`hideArtifact()`、`cleanupArtifacts()`。
   - Artifact 语义接口返回类型改为 `PipelineArtifact`。
3. `elys_version1/frontend/elys-web/src/views/PipelinePage.vue`
   - Pipeline 保存现有定义时携带 `expected_version=currentPipeline.version`。
   - 标题区显示 Pipeline 状态；运行按钮根据 `pipeline.status` 与 `run_mode` 禁用不允许的组合。
   - 新增 Run 创建对话框，提供 `run_mode=trial/analysis/replay/system` 和 `save_policy=temporary/current/pinned/discard` 选择，默认 `analysis/current`。
   - Run detail 增加 `摘要 / 输入 / 节点 / 任务 / 产物 / Manifest / Lineage` 七个入口。
   - Manifest 和 Lineage 改为分栏懒加载，避免每次 Run 刷新都拉完整追溯图。
   - Artifact 操作按钮改为 `固定结果`、`取消固定`、`隐藏输出`、`清理缓存`。
4. `elys_version1/frontend/elys-web/src/views/ProjectDetailPage.vue`
   - Project/Study 快捷入口文案从“配置分析流程”调整为“工作流与执行项 / Pipeline / Run”，更贴合当前对象边界。
5. `docs_v2`
   - 更新 `2-50 API 设计总览`、`5-20 Pipeline 工作流管理`、`5-30 Run 执行项管理`、`6-00 前端页面总览`、`7-40 工作流执行与后台任务` 和 `0-50 变更记录`。

验证结果：

1. `cd elys_version1/frontend/elys-web; npm run typecheck` 通过。
2. `cd elys_version1/frontend/elys-web; npm run build` 通过，构建耗时约 `2.28s`；Vite 仍提示 `litegraph.js` 使用 `eval` 和 `PipelinePage` chunk 较大，这是既有构建警告。
3. `cd elys_version1/backend; python -m pytest tests/test_pipeline_run_routes.py -q` 通过，结果为 `30 passed, 2 warnings in 1.20s`。
4. 本地启动前端 `http://127.0.0.1:3000/pipeline`，配合 mock API 完成浏览器可用性验证：
   - Pipeline 页面显示 `ERP preprocessing v7`、`已启用`、Run detail 七个分栏。
   - Run 创建对话框显示运行模式和保存策略，默认 `analysis/current`，创建按钮可用。
   - Artifact 分栏显示清理缓存和三个语义按钮。
5. 截图记录：
   - `日志/2_meeting260521/pipeline_step15_page.png`
   - `日志/2_meeting260521/pipeline_step15_run_dialog.png`
   - `日志/2_meeting260521/pipeline_step15_artifacts.png`
   - `日志/2_meeting260521/pipeline_step15_artifacts_controls.png`
6. `cd wiki; mkdocs build` 通过，文档构建耗时约 `1.92s`；MkDocs Material 输出关于未来 MkDocs 2.0 的上游提示，不影响本次构建。

遗留风险：

1. 前端尚未接入 Pipeline edit lock 的获取、心跳续期、离开释放和冲突提示；后端能力已存在，后续需要补 UI 状态。
2. Run detail 的任务事件目前是详情摘要和轮询刷新，尚未接入浏览器端 SSE 实时流。
3. Lineage 前端当前是入口和摘要，不是完整图形化依赖图；清理阻断详情也还需要更好的交互。
4. Artifact cleanup 当前只提供入口；清理任务进度、清理完成后的 toast 和列表自动刷新还需要补齐。
5. 本次浏览器验证使用本地 mock API，能覆盖页面契约和按钮行为，但不等同于真实 Celery/MNE 端到端验证。

下一步建议：

进入第 16 步，做 Pipeline/Run 全链路回归与文档收口。重点补真实后端环境下的登录、创建 Study、上传/选择数据、创建 Pipeline、保存 expected_version、创建 trial/analysis Run、写入 inputs、写入 Artifact、生成 manifest、lineage、cancel/retry、Task events、Artifact blocker 和 cleanup 验证。

Codex 提示词：

```text
第15步：前端接入 Pipeline/Run 新规范。请检查前端 PipelinePage、ProjectDetail/Study 页面和相关 api 封装，把 Pipeline 保存改为携带 expected_version；Run 创建对话框增加 run_mode/save_policy；根据 Pipeline 状态禁用不允许的运行；Run detail 增加 inputs、node runs、tasks/events、artifacts、manifest、lineage 入口；Artifact 操作改为固定结果、取消固定、隐藏输出、清理缓存等语义按钮。完成后运行前端可用验证和必要截图检查，并更新 docs_v2 与 日志/2_meeting260521/Pipeline与Run功能实现工作计划.md 中第 15 步的状态、实际改动、验证结果、遗留风险和下一步建议。
```

### 第 16 步：全链路回归与文档收口

状态：已完成（自动化回归完成，真实部署端到端待 staging 补验）
文档更新时间：2026-05-22 01:02:52 +08:00

工作目标：

验证 Pipeline/Run 新规范从后端到前端、从数据选择到输出清理都能闭环。

核心回归链路：

1. 登录。
2. 创建 Study。
3. 创建或挂载 working Dataset Asset。
4. 上传或准备可用 EEG canonical FIF。
5. 创建 Pipeline。
6. 保存 Pipeline，携带 expected_version。
7. 创建 trial Run，save_policy=temporary。
8. 创建 analysis Run，save_policy=current。
9. Run 创建时冻结 `pipeline_run_inputs`。
10. Celery 执行 Run。
11. 写 node runs。
12. 写 artifacts。
13. 生成 run_manifest。
14. 创建下游 Run 使用上游 Artifact。
15. 写 pipeline_run_dependencies。
16. 被依赖 Artifact 清理返回 blocker。
17. 未依赖 temporary/cached Artifact 可清理。
18. Run cancel 可释放锁。
19. Run retry 创建新 Run，不覆盖旧 Run。
20. Task events 可查询或 SSE 可读。

建议命令：

```bash
cd elys_version1/backend
python -m compileall app tests scripts
python -m pytest tests -q

cd ../../wiki
python -m mkdocs build --clean
```

如前端已接入：

```bash
cd elys_version1/frontend
npm run build
```

需要更新的文档：

1. `wiki/docs_v2/2-50-API设计总览.md`
2. `wiki/docs_v2/2-60-任务队列与异步架构.md`
3. `wiki/docs_v2/3-30-Study与Pipeline表.md`
4. `wiki/docs_v2/3-40-Run与Artifact追溯表.md`
5. `wiki/docs_v2/5-20-Pipeline工作流管理.md`
6. `wiki/docs_v2/5-30-Run执行项管理.md`
7. `wiki/docs_v2/7-40-工作流执行与后台任务.md`
8. `日志/2_meeting260521/Pipeline与Run功能定义与实现规范.md`
9. `日志/2_meeting260521/当前程序未实现与未收口功能清单.md`
10. 本工作计划文档。
11. `日志/2_meeting260521/Pipeline与Run第16步全链路回归报告.md`

实际改动：
1. 新增 `日志/2_meeting260521/Pipeline与Run第16步全链路回归报告.md`，把第 16 步拆成可追踪的回归矩阵，逐项说明“已自动化覆盖 / 代码级覆盖 / staging 待补验”。
2. 更新 `Pipeline与Run功能定义与实现规范.md`，补充当前实现收口状态，避免旧版“不一致清单”继续误导后续开发。
3. 更新 `当前程序未实现与未收口功能清单.md`，将第 2 步到第 15 步已完成的 Pipeline/Run 能力标记为已收口，并保留真实端到端、worker 协作取消、前端 SSE、不可变 pipeline_versions 等后续项。
4. 更新 docs_v2 中 API、任务队列、数据库、Pipeline、Run、后端执行和变更记录相关页面，明确当前 Project API 兼容承载 Study 语义，标准 Run 创建入口为 `/runs`，旧 `/run` 只作为兼容入口。

验证结果：
1. `cd elys_version1/backend; python -m compileall app tests scripts` 通过。
2. `cd elys_version1/backend; python -m pytest tests -q` 通过，结果为 `87 passed, 35 warnings in 1.97s`。
3. `cd wiki; python -m mkdocs build --clean` 通过，最终文档构建耗时约 `1.70 seconds`。
4. `cd elys_version1/frontend/elys-web; npm run typecheck` 通过。
5. `cd elys_version1/frontend/elys-web; npm run build` 通过，Vite build 耗时约 `2.25s`。
6. warnings 仍主要来自 Pydantic V2 class-based config、`datetime.utcnow()` 弃用提示、MkDocs Material 上游提示、Vite CJS API 弃用、`litegraph.js` 使用 `eval` 和 `PipelinePage` chunk 较大，不影响本轮验收。

遗留风险：
1. 当前回归以单元测试、源码结构测试、schema 测试和 mock UI 验证为主，没有在真实部署环境中完整跑登录、真实上传、真实 MNE 转换、真实 Celery worker 和浏览器端 SSE。
2. Run cancel 的 API、状态、事件、审计和锁释放已收口，但长任务节点仍需要 worker 协作式取消检查，才能做到真正停止正在运行的 EEG 处理。
3. Project/Study 仍处于语义统一、物理兼容阶段，短期不建议直接大规模改表名和路由名前缀。
4. 前端已接入 Run 新规范，但 edit lock 心跳续期、SSE 实时流、Lineage 图形化和 cleanup blocker 详情展示仍是体验增强项。

最终结论：
Pipeline/Run 的 MVP 主链路已经完成本轮收口，可以作为 Dataset / Study / Pipeline / Run 四对象体系中的协作分析主线。下一步应优先在 staging 环境补一轮真实端到端回归，并把真实 EEG 上传、canonical FIF 转换、Celery worker 执行和前端实时事件作为部署验收项目。

Codex 提示词：

```text
第16步：Pipeline/Run 全链路回归与文档收口。请对 Pipeline/Run 新规范做完整回归：登录、创建 Study、挂载或创建 working Dataset Asset、准备 EEG canonical FIF、创建 Pipeline、保存 expected_version、创建 trial Run 和 analysis Run、写 pipeline_run_inputs、执行 Run、写 node_runs/artifacts、生成 run_manifest、写 pipeline_run_dependencies、验证被依赖 Artifact 不能清理、验证 temporary/cached 可清理、验证 Run cancel 释放锁、验证 Run retry 创建新 Run、验证 Task events/SSE。同步更新 docs_v2 中 API、任务队列、数据库、Pipeline、Run、后端执行相关页面，以及 日志/2_meeting260521/Pipeline与Run功能定义与实现规范.md、当前程序未实现与未收口功能清单.md 和本工作计划文档。最后运行 compileall、pytest、mkdocs build，如前端已改则运行前端 build，并更新 日志/2_meeting260521/Pipeline与Run功能实现工作计划.md 中第 16 步的状态、实际改动、验证结果、遗留风险和最终结论。
```

## 5. 不建议本轮立即实施的内容

| 内容 | 原因 | 建议 |
| --- | --- | --- |
| 物理改名 `projects` -> `studies` | 牵涉表、API、路径和前端大量改动 | 先做 alias 和文案统一 |
| 物理改名 `datasets` -> `recordings` | 导入流程仍依赖旧表名 | 继续用兼容视图，后续迁移 |
| 拆 `pipeline_definitions` 为 `pipelines + pipeline_versions` | 对当前 CRUD 和 Run snapshot 影响大 | 等 expected_version、Run policy 稳定后再拆 |
| 真正物理删除 Artifact 文件 | 依赖、审计和回收站策略未完整 | 继续逻辑删除，后续加 trash |
| Dataset 发布共享治理 | MVP 当前是 working/private | 内部流程稳定后再做 |

## 6. 每一步文档更新要求

每一步完成后，都必须回写本文档对应步骤，至少包含：

1. `状态`：待开始 / 进行中 / 已完成 / 部分完成 / 阻塞。
2. `文档更新时间`：精确到秒。
3. `实际改动`：列出修改的文件、表、API、测试。
4. `验证结果`：列出运行过的命令和结果。
5. `遗留风险`：说明没有完成或需要后续确认的内容。
6. `下一步建议`：说明下一步应接哪个步骤，是否需要调整计划。

如果执行中发现计划不合理，可以直接修改后续步骤，但必须保留修改原因和时间。

## 7. 当前结论

Pipeline/Run 的核心改造不需要先做大迁移，应该先做语义和运行控制收口：

```text
/runs alias
  -> run_mode/save_policy
  -> Pipeline 状态运行规则
  -> executor 校验
  -> Run override 输入边界
  -> expected_version
  -> edit lock
  -> cancel/retry/SSE
  -> lineage 和 Artifact 语义操作
  -> 前端接入
  -> 全链路回归
```

做到第 1 至第 5 步后，Pipeline/Run 的基本语义会明显更稳。做到第 8 至第 12 步后，多人协作和长任务控制会进入可用状态。做到第 16 步后，工作流系统可以作为 MVP 的正式协作分析主线。
