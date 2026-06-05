# Pipeline/Run 第16步全链路回归报告

文档生成时间：2026-05-22 01:02:52 +08:00

## 1. 回归结论

本轮完成的是 Pipeline/Run 新规范的代码级、单元级、静态路由级和文档级收口。当前后端测试套件已经覆盖 Run 创建入口、`run_mode/save_policy`、Pipeline 状态运行规则、`expected_version`、编辑锁、输入快照、Artifact 写入、Run Manifest、Run 依赖、依赖保护清理、Run cancel/retry、Task cancel/retry、Task events/SSE、Lineage 和 Artifact 语义操作等核心能力。

需要明确的是：本轮没有在真实部署环境中跑完整浏览器登录、真实数据库、真实 EEG 文件上传、真实 MNE 转换和真实 Celery worker 的端到端链路。因此第 16 步结论是：MVP 主链路的程序结构与自动化验证已收口，可以进入 staging 级端到端验收；真实部署链路仍应单独补跑并记录。

## 2. 回归矩阵

| 链路项 | 当前覆盖 | 验证证据 | 结论 |
| --- | --- | --- | --- |
| 登录 | 当前测试未启动真实鉴权 HTTP 链路 | 本轮仅运行后端单元/源码级测试 | 需 staging 补验 |
| 创建 Study | 代码仍以 Project API 兼容承载 Study 语义 | `test_project_storage_directories.py`、目录与模型相关测试 | 自动化部分覆盖，真实 API 流程需补验 |
| 创建或挂载 working Dataset Asset | Dataset Asset、Study mount、Dataset file 已有模型和解析链路 | `test_load_data_run_input_snapshots.py`、`test_dataset_upload_storage_paths.py` | 自动化覆盖核心语义 |
| 准备 EEG canonical FIF | canonical FIF file_role、storage_uri、provenance 已登记 | `test_dataset_upload_storage_paths.py` | 自动化覆盖登记与路径，真实 MNE 转换需 staging 补验 |
| 创建 Pipeline | Pipeline CRUD、校验、状态语义已有后端路由 | `test_pipeline_run_routes.py` | 自动化覆盖路由/源码约束 |
| 保存 expected_version | 前端保存携带版本，后端强制校验 | `test_pipeline_run_routes.py`、前端 typecheck/build | 已覆盖 |
| 创建 trial Run | `run_mode=trial` 与 draft/active 规则已接入 | `test_pipeline_run_routes.py` | 已覆盖 |
| 创建 analysis Run | `run_mode=analysis` 与 active 规则已接入 | `test_pipeline_run_routes.py` | 已覆盖 |
| 写入 pipeline_run_inputs | LoadData 解析后的 DatasetFile、storage_uri、selector 快照写入 Run 输入 | `test_load_data_run_input_snapshots.py` | 已覆盖 |
| 执行 Run | executor、dispatcher、task 派发具备代码路径 | `test_pipeline_validator_executor.py`、`test_pipeline_run_routes.py` | 代码级覆盖，真实 Celery worker 需补验 |
| 写 node_runs/artifacts | NodeRun/ArtifactStore 写入路径与 storage_uri 兼容 | `test_artifact_store_study_storage.py`、`test_run_dependencies.py` | 自动化覆盖核心写入 |
| 生成 run_manifest | 成功、失败、取消等终态可生成 Manifest | `test_run_manifest.py`、`test_pipeline_run_routes.py` | 已覆盖 |
| 写 pipeline_run_dependencies | 上游 Artifact 依赖可写入并避免自依赖 | `test_run_dependencies.py` | 已覆盖 |
| 被依赖 Artifact 不能清理 | 删除/隐藏/清理前检查下游依赖 | `test_run_dependencies.py`、`test_file_tasks.py`、`test_pipeline_run_routes.py` | 已覆盖 |
| temporary/cached 可清理 | 清理任务只处理未被依赖的 temporary/cached | `test_file_tasks.py` | 已覆盖 |
| Run cancel 释放锁 | cancel API 写状态、事件、审计、释放运行锁并刷新 manifest | `test_pipeline_run_routes.py` | API 级覆盖，worker 协作式中断需补验 |
| Run retry 创建新 Run | retry 从 failed/cancelled 创建新 Run，不覆盖旧 Run | `test_pipeline_run_routes.py` | 已覆盖 |
| Task events/SSE | events list 与 task-level SSE 入口存在 | `test_pipeline_run_routes.py` | 后端覆盖，浏览器端实时客户端需补验 |
| 前端 Pipeline/Run 新规范 | Run dialog、Run detail、Artifact 语义按钮、standard `/runs` API 已接入 | 第 15 步截图、`npm run typecheck`、`npm run build` | 已覆盖静态与 mock UI |

## 3. 本轮验证命令

| 命令 | 结果 |
| --- | --- |
| `cd elys_version1/backend; python -m compileall app tests scripts` | 通过 |
| `cd elys_version1/backend; python -m pytest tests -q` | 通过，`87 passed, 35 warnings in 1.97s` |
| `cd wiki; python -m mkdocs build --clean` | 通过，最终文档构建耗时约 `1.70 seconds` |
| `cd elys_version1/frontend/elys-web; npm run typecheck` | 通过 |
| `cd elys_version1/frontend/elys-web; npm run build` | 通过，Vite build 耗时约 `2.25s` |

构建 warning：pytest 仍有 Pydantic V2 class-based config 和 `datetime.utcnow()` 弃用提示；MkDocs Material 输出 MkDocs 2.0 上游提示；前端 build 仍提示 Vite CJS API 弃用、`litegraph.js` 使用 `eval` 和 `PipelinePage` chunk 超过 500 kB。这些均为既有技术债，不影响本轮第 16 步验收。

## 4. 遗留风险

1. 当前自动化测试中有不少是源码结构、schema 和轻量 fake DB 级验证，不等价于真实 HTTP + DB + Celery + MNE 的生产级端到端回归。
2. `Project` 与 `Study` 的物理表名和路由命名仍未完全统一，当前策略是兼容承载，不做大迁移。
3. Run cancel 已有 API 和状态收口，但长时间运行中的具体 EEG 节点仍需要 worker 定期检查取消标记，才能做到真正协作式停止。
4. Task SSE 后端入口已具备，前端当前主要是详情刷新和入口展示，还没有完整浏览器端断线重连、Study 级事件聚合体验。
5. canonical FIF 的路径、file_role 和 provenance 可自动化验证，真实 EEG 格式转换质量仍需用代表性 EDF/BDF/BrainVision 数据在 staging 环境验收。

## 5. 最终结论

Pipeline/Run 的 MVP 主链路已经从“能派发运行”推进到“能表达试跑/正式分析、能冻结输入、能追溯输出、能管理任务、能保护依赖、能查看 lineage”的阶段。下一阶段不建议继续堆新语义，应该优先做真实部署端到端回归、补齐前端实时协作体验，以及把 Project/Study 命名兼容策略固化到 API 文档和迁移路线中。
