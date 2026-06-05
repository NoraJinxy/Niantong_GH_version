# 工作流讨论稿与正式 wiki 对齐清单

> 文档性质：工作流专题讨论稿，可随方案讨论随时修改。
> 正式维护口径以 `wiki/docs` 为准；`wiki1` 是旧版文档，只作历史参考，不再作为新版事实源。
> 本目录用于把工作流方案讨论清楚，形成可落地的开发步骤后，再同步到 `wiki/docs` 的对应正式页面。

> 日期：2026-05-17  
> 目的：明确 `2_meeting260516` 中哪些内容只是讨论，哪些内容应该在定稿后同步到 `wiki/docs`。

## 1. 当前工作方式

`wiki/docs` 是正式维护文档，面向团队开发、后续交接和大模型检索。`2_meeting260516` 是工作流专题讨论稿，允许反复修改、推翻、合并和重写。

工作流相关决策建议按下面节奏推进：

1. 在本目录把问题讲透：用户行为、前端交互、后端执行、数据结构、API、开发步骤。
2. 确认方案是否合理、能否落地、是否符合当前代码。
3. 将被采纳的内容同步到 `wiki/docs` 对应正式页面。
4. 按正式 wiki 和代码任务开发。
5. 代码实现后，再回头修正 `wiki/docs` 的状态。

## 2. 权威顺序

| 顺序 | 来源 | 说明 |
| --- | --- | --- |
| 1 | 当前代码 `elys_version1` | 判断“是否已经实现”的最终依据。 |
| 2 | 正式文档 `wiki/docs` | 判断当前项目正式口径。 |
| 3 | 工作流讨论稿 `2_meeting260516` | 判断工作流下一步怎么做。 |
| 4 | 旧版程序 `Niantong-eeg-analysis-app-https-1.0.0` | 提供技术参考和可复用思想。 |
| 5 | 旧版文档 `wiki1` | 只保留历史参考价值。 |

如果 `2_meeting260516` 与 `wiki/docs` 不一致，默认认为本目录是未定稿讨论，不能直接覆盖正式文档。

## 3. 正式 wiki 对应页面

| 讨论主题 | 正式 wiki 页面 | 同步条件 |
| --- | --- | --- |
| 工作流模块总状态 | `wiki/docs/M3-00-工作流模块总览.md` | 当前状态变化时同步。 |
| 节点库和 NodeSpec | `wiki/docs/M3-10-节点库设计.md` | 新增、删除、改字段后同步。 |
| 工作流 definition JSON | `wiki/docs/M3-20-工作流定义.md` | definition schema 或版本规则变化后同步。 |
| 校验规则 | `wiki/docs/M3-30-工作流校验.md` | 新增 issue code 或校验逻辑后同步。 |
| 执行机制 | `wiki/docs/M3-40-工作流执行.md` | `PipelineExecutor` 或普通节点执行器实现后同步。 |
| 异步和进度 | `wiki/docs/M3-50-异步任务与进度.md` | 后台任务、轮询、SSE、取消机制定稿后同步。 |
| 缓存和复用 | `wiki/docs/M3-60-缓存与结果复用.md` | traceCode、node_hash、缓存策略定稿或实现后同步。 |
| Pipeline 前端页面 | `wiki/docs/4-08-工作流编辑器.md` | 页面行为、按钮语义、状态面板变化后同步。 |
| API | `wiki/docs/2-50-API设计总览.md` | API 已实现或接口契约冻结后同步。 |
| 数据库 | `wiki/docs/2-30-数据库设计总览.md` | 表结构或字段落地后同步。 |
| 文件目录 | `wiki/docs/2-40-文件系统与数据目录.md` | artifact / derivatives / cache 路径定稿后同步。 |
| Artifact preview / 观察入口 | `wiki/docs/M9-00-交互观察模块总览.md`、`2-50-API设计总览.md`、`4-08-工作流编辑器.md` | preview API 或观察页入口实现后同步；观察页真实渲染另行同步。 |
| 预处理执行器 | `wiki/docs/M4-00-预处理模块总览.md`、`M4-10`、`M4-20`、`M4-40`、`M4-50` | FIR、Resample、Re-reference、ICA Compute/Apply 第一版、Epoch 已实现后可同步；Butterworth 等后续实现后继续补。 |
| ERP/PSD/TFR | `wiki/docs/M5-00` 到 `M5-50` | ERP Average 与 Save Result 已实现后可同步；PSD/TFR 后续实现后继续补。 |

## 4. 会议稿到正式文档的映射

| 会议稿 | 主要内容 | 对应正式页面 |
| --- | --- | --- |
| `00-工作流专题文档索引.md` | 讨论稿总入口和阅读顺序 | 不直接同步；只用于本目录导航。 |
| `01-工作流功能需求分析.md` | 用户故事、角色、功能边界 | `M3-00`、`M3-20`、`M3-40`、`4-08`。 |
| `02-工作流编辑器交互与用户行为定义.md` | 页面布局、按钮、节点状态、前端行为 | `4-08`，部分同步到 `M3-30`、`M3-50`。 |
| `03-工作流节点规范与数据结构.md` | NodeSpec、data_infos、表结构建议 | `M3-10`、`M3-20`、`2-30`。 |
| `04-工作流执行缓存与增量运行设计.md` | Executor、缓存、增量、人工节点 | `M3-40`、`M3-50`、`M3-60`。 |
| `05-工作流程序架构与实施方案.md` | 前后端模块拆分和实施路线 | `2-20`、`2-80`、`M3-40`。 |
| `06-FIF数据导入校正规则.md` | fifdata 边界、导入校正、版本策略 | `M1-40`、`M1-50`、`M2-10`、`2-40`。 |
| `07-工作流方案审阅与细化.md` | 风险、状态机、错误码、开放问题 | 同步到对应模块页或风险清单。 |
| `08-工作流当前进度与开发路线.md` | 当前进度、API 缺口、开发步骤 | 定稿后拆分同步到 M3、2-50、4-08、2-30。 |
| `10-Redis后台任务与工作流调度架构.md` | Redis/Celery、后台任务、状态恢复、重试和取消 | 定稿后同步到 `2-60`、`M3-50`，工作流专属细节同步到 `M3-40`。 |
| `11-工作流图示页面规划.md` | 工作流架构、执行、调度、缓存、追溯和人工节点图示规划 | 不直接同步；可作为正式 wiki 图示素材清单。 |
| `12-image2工作流图示提示词.md` | 图示生成提示词 | 不直接同步；只作为图示资产生产记录。 |
| `13-工作流Codex分步开发提示词.md` | Codex 分步开发提示词、每步目标、实现范围和测试要求 | 不直接同步为正式能力；可拆成 issue、开发任务或实现后回写状态。 |

## 5. 当前正式事实

以下内容已经是 `wiki/docs` 和当前代码共同支持的事实：

- Pipeline 页面已接 LiteGraph。
- NodeSpec 注册和节点库读取已实现。
- 工作流 CRUD 已实现。
- 基础校验已实现，并已拆分到 `backend/app/pipeline/validator.py`。
- LoadData 可以解析真实 fifdata。
- `/run` 会写入 `pipeline_runs`，预创建每个图节点的 `pipeline_node_runs`，以 `queued` 返回，并向 Celery `workflow.default` 队列投递 `run_pipeline_task`；worker 内重新获取 DB session 调用 `PipelineExecutor`。
- `/run` 当前真正执行 LoadData、FIR、Resample、Re-reference、Epoch、ERP、Save Result；其它节点会以 `PIPELINE_NODE_EXECUTOR_NOT_IMPLEMENTED` 写入失败 node_run。
- Butterworth、PSD/TFR 等普通节点执行器未实现；ICA Compute/Apply 第一版已实现。
- `pipeline_node_runs` 和 `pipeline_artifacts` 的数据结构已在当前代码中落地。
- `ArtifactStore` 与 `NodeOutput` 基础契约已在当前代码中落地，可支持 JSON metadata、普通文件/目录 artifact 的 sha256、原子发布和 `PipelineArtifact` 登记；FIR/Resample/Re-reference/Epoch/ERP 已调用 ArtifactStore 写 pipeline artifact。
- Run detail、node_run 列表、artifact 列表查询 API 已在当前代码中落地，前端 API 和类型已封装；`PipelinePage.vue` 已接入轮询展示，画布节点、底部运行面板和选中节点摘要以后端 `node_run.status` 为准。
- MNE IO 基础已在当前代码中落地，可从 data_info 读取 Raw FIF，保存 Raw/Epochs/Evoked FIF，并用 synthetic Raw 做测试。
- 预处理节点 FIR、Resample、Re-reference 已在当前代码中落地，输入来自上游 data_infos，输出派生 Raw FIF artifact 和派生 data_infos。
- Epoch、ERP Average、Save Result 已在当前代码中落地，输出 Epochs/Evoked artifact，并登记带 `artifact_id/run_id/node_run_id` 追溯的 `analysis_results`。
- Redis/Celery 投递入口已在当前代码中落地，但真实消费依赖 Redis 服务和 worker 进程；第一版节点级缓存已落地，可按 `node_hash` 复用已校验 artifact；ICA 人工交互节点第一版已落地；artifact preview 第一版已落地，支持 raw/epochs/evoked 轻量摘要、文件存在/checksum 校验和 PipelinePage artifact 入口；PSD/TFR 仍是规划或讨论。
- 2026-05-17 到 2026-05-18 的 Step 0-14 代码审计和落地结果已同步到 `08-工作流当前进度与开发路线.md` 和 `13-工作流Codex分步开发提示词.md`；其中记录了实际检查结果和未能执行的检查原因。

## 6. 当前讨论稿里的未定稿内容

以下内容可以作为开发方向，但还不能写成正式已实现能力：

- 让 `PipelineExecutor` 在 PSD/TFR 等后续节点中继续调用 `ArtifactStore` 写入 `pipeline_artifacts`；ICA Compute/Apply 第一版已完成 artifact 写入。
- 继续增强 `PipelineCache`：第一版 hash/artifact 复用已实现，但缓存统计、手动失效、run-from、partial policy 尚未实现。
- 完善 Redis/Celery 运行保障：worker 部署、恢复、取消、重试和监控；当前只完成第一版单队列投递入口。
- 新增 artifact download、cancel、run-from API；run detail、node_run 列表、artifact 列表、ICA interaction/decision/resume、artifact preview 已完成。
- 增强 traceCode/node_hash 的可解释性、缓存统计和人工失效能力；基础 hash 与 artifact 恢复已完成。
- ICA 人工交互节点的独立 interaction 表、通知、锁定和 resume 队列化。
- 观察、统计、作图页面与工作流 artifact 的深度联动；当前仅保留观察页 route/query 入口。
- `13-工作流Codex分步开发提示词.md` 中的步骤是执行建议，不代表对应功能已经实现。

## 7. 同步规则

当本目录讨论出确定方案时，按以下规则同步：

- 如果是“当前代码已经实现”，同步到 `wiki/docs` 时写成已实现，并给出代码位置。
- 如果是“开发方案已决定但未实现”，同步到 `wiki/docs` 时写成规划或待实现。
- 如果仍在讨论，保留在 `2_meeting260516`，不要写入正式 wiki。
- 如果方案推翻，直接改本目录讨论稿；正式 wiki 不受影响。
- 如果代码实现改变了事实，以代码为准，反向修正正式 wiki 和讨论稿。

## 8. 对 wiki1 的使用限制

`wiki1` 已经是旧版文档。它可以用来查旧需求、旧说法、旧命名，但不能用来判断新版已经实现什么。

引用 wiki1 时必须写清楚：这是旧版参考，不是新版承诺。凡是 wiki1 中提到但当前代码和 `wiki/docs` 没有支持的功能，一律按规划、参考或待讨论处理。

## 9. 2026-05-18 Step 13 对齐记录

已可作为“代码事实”同步到正式 wiki 的内容：

- ICA Compute/Apply 第一版已实现：`eeg/ica/compute` 生成 ICA artifact 和组件预览 metadata；`eeg/ica/apply` 可等待用户 decision 并在 resume 后输出 cleaned Raw artifact。
- `waiting_user_input` 已成为 run/node_run 状态机的一部分；`pipeline_runs.status` schema 兼容层已扩展。
- 已新增 interaction/decision/resume API，decision 版本冲突返回 `DECISION_CONFLICT`。
- 前端 PipelinePage 已在选中 waiting 的 Apply ICA 节点时显示成分选择面板。

仍只能写成“规划/待完善”的内容：

- 独立 interaction 表、多人锁定详情、通知、SSE/WebSocket。
- resume 完全 Celery 化。
- ICA 图像级 preview、artifact download、观察页真实渲染。
- ICA 自动成分识别和复杂人工审核策略。

## 10. 2026-05-18 Step 14 对齐记录

已可作为“代码事实”同步到正式 wiki 的内容：

- `GET /api/v1/projects/{project_id}/pipeline-artifacts/{artifact_id}/preview` 已实现，复用 project read 权限并确保 artifact 属于该 project。
- raw/epochs/evoked artifact preview 第一版已实现；只返回 sfreq、通道、时长、事件、时间范围和少量抽样曲线等轻量摘要，不返回完整 EEG 矩阵。
- 文件缺失返回 `PIPELINE_ARTIFACT_FILE_MISSING`，checksum 不匹配返回 `PIPELINE_ARTIFACT_CHECKSUM_MISMATCH`。
- `PipelineArtifactPreviewResponse` 返回 `observe_route/observe_query`，并把 preview 缓存到 `pipeline_artifacts.preview_json`。
- `PipelinePage.vue` 已提供选中节点 artifact 列表和 preview 面板，可跳转观察页入口并带 `artifact_id/run_id/node_run_id` query。

仍只能写成“规划/待完善”的内容：

- artifact download。
- 观察页按 `artifact_id/run_id` 真实加载和渲染 EEG artifact。
- PSD/TFR/ICA 图像等更多 data_type 的专门 preview。
- 真实 PostgreSQL/API E2E 和权限联调验证。
