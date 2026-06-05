# 前端 Dataset / Study / Pipeline / Run 改造实现工作计划

生成时间：2026-05-22 09:38:22 +08:00

修订时间：2026-05-22 09:45:36 +08:00

修订说明：本轮前端改造每一步完成后，统一更新 `日志/2_meeting260522` 中的相关 md 文档；除非后续另有明确说明，不跨日期目录写入。

## 1. 文档目标

本文用于规划 Elys 前端从旧的 Project / Dataset 页面语义，逐步调整为 Dataset / Study / Pipeline / Run 四对象规则的实施路线。

本轮只做规划，不直接修改业务代码。后续每一步执行时，都应在完成后更新本文档对应步骤的状态、实际改动、验证结果、遗留风险和下一步建议。

本计划基于以下现有结论：

- `日志/2_meeting260522/前端页面与Dataset-Study-Pipeline-Run规则差异分析.md`
- `docs_v2` 中系统架构、研究管理、数据库、文件管理、API、任务队列、后端架构相关页面
- `elys_version1/frontend/elys-web/src` 当前页面、路由、类型和 API 封装

## 2. 前端改造总原则

### 2.1 产品语义优先

前端用户看到的是业务对象，不应要求用户理解服务器目录或后端兼容命名。

- Dataset：数据资产入口，包含上传原始文件、Raw BIDS 逻辑视图、canonical FIF、Recording / Version / File 等信息。
- Study：研究项，是协作、权限、运行、结果管理的工作空间。现阶段后端 API 仍可继续使用 `/projects`，但前端展示应逐步改为 Study / 研究项。
- Pipeline：工作流定义，只保存处理逻辑、节点参数和选择规则，不保存某次执行的事实数据。
- Run：执行项，是某次运行事实，保存输入快照、运行参数快照、任务、输出、manifest、lineage 和审计记录。

### 2.2 兼容后端，不一次性推翻

当前后端仍有大量 `/projects`、旧 `Dataset`、旧 `dataset_id` 语义。前端应先通过类型别名、API 兼容层、页面文案和交互收口来适配，不要求后端一次性改完。

### 2.3 不暴露服务器绝对路径

页面不应把 `bids_root`、`source_path`、`fif_path`、`storage_path` 等作为用户主要信息展示。用户应通过 Dataset File、Artifact、Run Manifest、下载和预览 API 访问文件。

### 2.4 Pipeline 与 Run 边界必须清楚

Pipeline 页面可以配置 LoadData 的选择规则，但“这一次到底用了哪些数据”必须进入 Run 的 `selection_override`、`pipeline_run_inputs` 和 `run_manifest`。前端要避免把“固定当前命中数据”直接写回 Pipeline definition 作为标准用法。

### 2.5 静态预览页先冻结

观察、统计、作图、机器学习等大量页面目前更接近静态产品预览。本轮不要把这些页面强行接入真实业务链路，只做必要导航、文案和入口约束，避免制造假联动。

### 2.6 每步都要可验证

每一步至少运行：

- `npm run typecheck`
- `npm run build`

如果本步涉及主要页面布局，还应启动前端并用浏览器检查：

- `/dashboard`
- `/projects`
- `/projects/:id`
- `/import`
- `/pipeline`

## 3. 改造范围

### 3.1 优先改造页面

| 页面或模块 | 当前问题 | 改造方向 |
|---|---|---|
| `Dashboard.vue` | Project-centric，内嵌上传，显示目录路径，缺少四对象总览 | 改为 Dataset / Study / Pipeline / Run 工作台 |
| `ProjectsPage.vue` | 产品语义仍是 Project，显示 Data Root | 改为 Study 列表和管理页 |
| `ProjectDetailPage.vue` | Project 详情混合数据、QA、存储路径和旧目录 | 改为 Study 主页，突出数据挂载、Pipeline、Run、Artifact、成员和活动 |
| `ImportPage.vue` | 以 Project 为目标上传 | 改为导入到 working Dataset / Study 默认数据资产 |
| `BidsUploadPanel.vue` | 上传能力可用，但语义是项目目录上传 | 改为 Dataset 导入组件，显示 original / raw_bids / canonical_fif / dataset_files 语义 |
| `PipelinePage.vue` | 已有 Run 新字段，但 LoadData explicit 仍写入 Pipeline definition | 将具体数据选择收敛到 Run override 和输入快照 |
| `types/index.ts` | `Project` 和 `Dataset` 名称与新语义冲突 | 增加 Study / Recording / DatasetAsset 等前端兼容类型 |
| `api/*.ts` | API 路径兼容旧后端，但命名易误导 | 增加语义化前端封装，不破坏旧调用 |
| `workbenchPages.ts` / `WorkbenchShell.vue` | 导航仍偏旧模块名称 | 改为研究管理、数据资产、工作流与执行项的导航结构 |

### 3.2 暂不深改页面

以下页面暂时保持“预览 / 占位 / 后续接入”策略：

- `IcaPage.vue`
- `SourcePage.vue`
- `ErpPage.vue`
- `PsdPage.vue`
- `TfrPage.vue`
- `ConnectivityPage.vue`
- `MicrostatePage.vue`
- `StatisticsPage.vue`
- `FiguresPage.vue`
- `MlPage.vue`
- `StaticWorkbenchPage.vue`

这些页面只在导航、入口文案、状态标签上做轻量调整，不在本轮实现真实数据读写。

## 4. 分阶段实现路线

### 阶段 A：基线和兼容层

目标：先把命名、类型、API 包装、导航结构收口，降低后续页面改造成本。

### 阶段 B：核心页面重构

目标：把 Dashboard、Study 列表、Study 详情、Import 变成符合四对象规则的真实主线。

### 阶段 C：Pipeline / Run 交互收口

目标：把“工作流定义”和“执行事实”彻底分开，前端支持 run_mode、save_policy、selection_override、Run detail、Task events、Artifact 操作。

### 阶段 D：回归、文档和视觉验证

目标：保证页面可用、构建通过、文档一致，并记录仍依赖后端完善的功能。

## 5. 工作计划表

| 步骤 | 状态 | 优先级 | 主题 | 主要文件 | 验收要点 |
|---|---|---|---|---|---|
| 第 1 步 | 已完成 | P0 | 建立前端改造基线 | `src/router`、`src/views`、`src/api`、`src/types`、`docs_v2` | 已输出页面/API/类型依赖清单，未改业务代码 |
| 第 2 步 | 已完成 | P0 | 新增前端四对象语义兼容层 | `types/index.ts`、`api/*.ts` | Study / Recording / DatasetAsset / Run 类型已可被页面引用 |
| 第 3 步 | 已完成 | P0 | 统一导航和命名 | `workbenchPages.ts`、`WorkbenchShell.vue` | 导航主语已改为数据集、研究项、工作流和执行项 |
| 第 4 步 | 已完成 | P0 | Dashboard 四对象重构 | `Dashboard.vue` | 不再以内嵌上传和目录路径作为主界面 |
| 第 5 步 | 已完成 | P0 | Study 列表页改造 | `ProjectsPage.vue` | 页面语义从 Project 改为 Study，隐藏服务器目录 |
| 第 6 步 | 已完成 | P0 | Study 详情页改造 | `ProjectDetailPage.vue` | Study 主页已按 Overview / Data / Pipelines / Runs / Artifacts / Activity 收口 |
| 第 7 步 | 待开始 | P1 | Import / Dataset 上传语义升级 | `ImportPage.vue`、`BidsUploadPanel.vue` | 上传流程表达为 working Dataset / Recording / dataset_files |
| 第 8 步 | 待开始 | P0 | Pipeline LoadData 与 Run override 收口 | `PipelinePage.vue`、`api/pipelines.ts`、`types/index.ts` | Pipeline 不再把具体命中数据作为标准保存结果 |
| 第 9 步 | 待开始 | P1 | Run 创建与详情体验增强 | `PipelinePage.vue` | Run 创建支持 mode/policy/override，详情显示 inputs/tasks/artifacts/manifest |
| 第 10 步 | 待开始 | P1 | Task 与协作状态前端接入 | `PipelinePage.vue`、新 task API 封装 | cancel/retry/events/locks 入口清楚，不影响旧运行 |
| 第 11 步 | 待开始 | P1 | Artifact 语义操作接入 | `PipelinePage.vue`、artifact API 封装 | pin/unpin/hide/cleanup 使用语义按钮，依赖阻塞可读 |
| 第 12 步 | 待开始 | P2 | 静态预览页冻结和文案清理 | `Index.vue`、预览页、`workbenchPages.ts` | 未实现页面不假装已接入真实数据 |
| 第 13 步 | 待开始 | P0 | 全链路前端回归和文档收口 | `docs_v2`、`日志/2_meeting260522` | typecheck/build 通过，核心页面截图检查完成 |

## 6. 每步实施细节与 Codex 提示词

### 第 1 步：建立前端改造基线

工作目标：

- 重新读取当前前端文件、差异分析文档和相关 docs_v2。
- 整理前端路由、页面、组件、API、类型、状态字段、后端接口依赖。
- 明确哪些页面是真功能，哪些页面是静态预览。
- 不修改业务代码。

建议检查文件：

- `elys_version1/frontend/elys-web/src/router/index.ts`
- `elys_version1/frontend/elys-web/src/data/workbenchPages.ts`
- `elys_version1/frontend/elys-web/src/views/Dashboard.vue`
- `elys_version1/frontend/elys-web/src/views/ProjectsPage.vue`
- `elys_version1/frontend/elys-web/src/views/ProjectDetailPage.vue`
- `elys_version1/frontend/elys-web/src/views/ImportPage.vue`
- `elys_version1/frontend/elys-web/src/components/BidsUploadPanel.vue`
- `elys_version1/frontend/elys-web/src/views/PipelinePage.vue`
- `elys_version1/frontend/elys-web/src/types/index.ts`
- `elys_version1/frontend/elys-web/src/api`
- `wiki/docs_v2/6-00-前端页面总览.md`

验证方式：

- `npm run typecheck`
- `npm run build`

Codex 提示词：

```text
第1步：建立前端 Dataset / Study / Pipeline / Run 改造基线。请读取 elys_version1/frontend/elys-web/src/router/index.ts、data/workbenchPages.ts、views/Dashboard.vue、views/ProjectsPage.vue、views/ProjectDetailPage.vue、views/ImportPage.vue、components/BidsUploadPanel.vue、views/PipelinePage.vue、types/index.ts、src/api，以及 docs_v2 中前端、研究管理、Pipeline/Run、API 相关页面，整理当前路由、页面职责、API 依赖、类型命名、真实功能和静态预览页面边界。不要做业务代码改动。完成后运行 npm run typecheck 和 npm run build，并更新 日志/2_meeting260522/前端Dataset-Study-Pipeline-Run改造实现工作计划.md 中第 1 步的状态、实际发现、验证结果、遗留风险和下一步建议；如发现与本轮前端规范不一致，也同步更新 日志/2_meeting260522 中相关 md 文档。
```

执行记录：

- 执行时间：2026-05-22 09:52:44 +08:00
- 状态：已完成。
- 改动范围：只更新本文档和 `日志/2_meeting260522/前端页面与Dataset-Study-Pipeline-Run规则差异分析.md` 的基线补充记录；未修改前端业务代码。

实际发现：

1. 路由基线清楚但仍是旧命名。`router/index.ts` 当前包含 `/dashboard`、`/projects`、`/projects/:id`、`/import`、`/pipeline` 真实主线，以及 `/ica`、`/observe/*`、`/statistics`、`/figures`、`/ml`、`/admin` 等预览页。`/preprocess` 重定向到 `/ica`。
2. 导航由 `workbenchPages.ts` 管理，已经用 `status: live/preview` 区分真实页和预览页；但 live 导航仍显示“项目管理 / 项目列表 / 分析”，尚未统一到 Dataset / Study / Pipeline / Run。管理面板静态数据里仍写 `/mnt/elys_data/projects`、`source_uploads + fifdata` 等旧文件口径。
3. `Dashboard.vue` 是当前偏离最大页面。它自己实现类似 WorkbenchShell 的布局，调用 `projectApi.list()`、逐项目 `datasetApi.list()`，内嵌 `BidsUploadPanel`，显示 `bids_root` 和 `fif_path`，并保留一套旧上传逻辑；不符合“四对象总览、不暴露服务器路径、上传入口独立”的目标。
4. `ProjectsPage.vue` 已使用 `WorkbenchShell`，但用户语义仍是 Project：标题、按钮、垃圾箱、永久删除、`Project ID`、`Data Root`、`bids_root` 都直接展示；统计数据通过逐项目读取 datasets 得到，性能和语义都需要重构为 Study 列表。
5. `ProjectDetailPage.vue` 当前是 Project Detail + Dataset/QA 页面，调用 `projectApi.get()`、`datasetApi.list()`、QA mock/review API；页面直接说明 `source_uploads`、`fifdata`、`fif_path`，缺少 Study Home 需要的 Data Mount、Pipeline、Run、Artifact、Activity 结构。
6. `ImportPage.vue` 与 `BidsUploadPanel.vue` 的上传能力可复用。`BidsUploadPanel` 已支持 BrainVision 成组、EDF/BDF 上传、重复数据作为新版本确认；但入口仍是“目标项目 / Project ID 定位数据目录”，调用旧 `/projects/{project_id}/datasets/import`，还没有 Dataset Asset / working Dataset 语义。
7. `PipelinePage.vue` 是当前最接近新规范的页面：已接 `expected_version` 保存、`run_mode/save_policy` 创建 Run、Pipeline 状态运行前判断、Run detail、node runs、tasks、artifacts、manifest、lineage、Artifact preview、pin/unpin/hide/cleanup 等能力。
8. `PipelinePage.vue` 的关键不一致仍存在：LoadData 的“固定当前命中 / 勾选数据集”会把 `selection_mode=explicit` 和 `dataset_ids` 写回 `node.params`，保存时进入 Pipeline definition；Run 创建 payload 目前只发送 `run_mode` 和 `save_policy`，没有发送 `selection_override`。这与“Pipeline 保存规则、Run 保存事实”的前端规范不一致。
9. `types/index.ts` 已包含较新的 Run 类型、`PipelineRunInput`、`PipelineRunLineage`、`AsyncTask`、`Artifact` retention 字段和 `PipelineRunCreateRequest.selection_override`；但仍缺少前端语义类型别名，如 `Study`、`Recording`、`DatasetAsset`、`DatasetFile`，页面仍直接使用 `Project` 和旧 `Dataset`。
10. `api/*.ts` 封装集中，没有在 view 中发现裸 axios 调用；`client.ts` 已区分 `api` 与 `dataApi`，上传走 `DATA_API_BASE_URL`。API 命名仍是 `projectApi` / `datasetApi`，尚未提供 `studyApi` 或 Dataset Asset 语义包装。
11. docs_v2 标准口径已经明确 Dataset / Study / Pipeline / Run。需要注意：`5-20 Pipeline 工作流管理` 中“临时手选数据进入 Run selection_override 而不是回写 Pipeline”的描述比当前前端实际实现更超前，当前前端仍需在第 8 步修正。

验证结果：

| 命令 | 结果 | 说明 |
|---|---|---|
| `npm run typecheck` | 通过 | `vue-tsc --noEmit` 无错误 |
| `npm run build` | 通过 | Vite 构建成功，生成 `dist` |

构建警告：

- Vite CJS Node API deprecated。
- `litegraph.js` 使用 `eval`，Vite 提示有安全与压缩风险。
- `PipelinePage` chunk 约 589 kB，超过 500 kB 警告阈值，后续可考虑拆分 Run detail、Artifact panel、LoadData selector 等子模块或 manualChunks。

遗留风险：

1. Dashboard 当前存在重复上传逻辑和内嵌 `BidsUploadPanel`，第 4 步改造时要避免两套上传入口继续并存。
2. Projects / ProjectDetail 页面显示服务器路径和旧目录结构，容易强化用户直接操作文件目录的心智。
3. `PipelinePage.vue` 体量大，功能集中，后续改 `selection_override`、Task、Artifact、锁时回归风险高。
4. 当前没有 Dashboard summary / Study overview API，前端只能用多次 `/projects`、`/datasets`、`/pipelines` 拼概览，性能和准确性有限。
5. 观察、统计、作图、机器学习、管理后台多数是预览页，不能在第一轮改造中假装已经接入真实 Dataset/Run。

下一步建议：

1. 第 2 步先新增前端语义兼容层：`Study`、`Recording`、`DatasetAsset`、`DatasetFile`、`studyApi` 等，内部继续兼容 `/projects`。
2. 第 3 步统一导航命名，把 live 主线调整为研究项、数据导入/数据资产、工作流与执行项，并冻结预览页。
3. 第 4 步重构 Dashboard 前，应先决定是否彻底移除 Dashboard 内嵌上传，只保留跳转到 Import 的入口。
4. 第 8 步必须重点处理 `PipelinePage.vue` 的 LoadData explicit 数据选择，避免继续把“本次命中事实”保存进 Pipeline definition。

### 第 2 步：新增前端四对象语义兼容层

工作目标：

- 在前端类型层建立新语义，不急着改后端 API 路径。
- 保留旧 `Project`、`Dataset` 类型，新增或别名：
  - `Study`
  - `Recording`
  - `DatasetAsset`
  - `DatasetFile`
  - `PipelineRunInput`
  - `RunManifestSummary`
  - `StudyOverview`
- 在 API 层可以新增 `studyApi`、`recordingApi` 或兼容包装，内部仍调用旧 `projectApi`、`datasetApi`。
- 页面后续引用新语义类型，降低大规模重命名风险。

建议改动文件：

- `elys_version1/frontend/elys-web/src/types/index.ts`
- `elys_version1/frontend/elys-web/src/api/projects.ts`
- `elys_version1/frontend/elys-web/src/api/datasets.ts`
- 可新增 `elys_version1/frontend/elys-web/src/api/studies.ts`
- 可新增 `elys_version1/frontend/elys-web/src/api/datasetAssets.ts`

验证方式：

- `npm run typecheck`
- `npm run build`

Codex 提示词：

```text
第2步：新增前端四对象语义兼容层。请在 elys_version1/frontend/elys-web/src/types/index.ts 中保留旧 Project/Dataset 类型兼容，同时新增 Study、Recording、DatasetAsset、DatasetFile、StudyOverview、RunManifestSummary 等前端语义类型；在 src/api 中新增 studyApi 和必要的 dataset asset/recording 兼容封装，内部可继续调用现有 /projects 和 /datasets 接口，不要破坏旧页面调用。完成后运行 npm run typecheck 和 npm run build，并更新 日志/2_meeting260522/前端Dataset-Study-Pipeline-Run改造实现工作计划.md 中第 2 步的状态、实际改动、验证结果、遗留风险和下一步建议；如影响 2_meeting260522 中 Dataset/Study/API 口径，也同步更新相关 md 文档。
```

执行记录：

- 执行时间：2026-05-22 09:59:16 +08:00
- 状态：已完成。
- 改动范围：新增前端语义类型和兼容 API 包装；未修改现有页面调用，旧 `projectApi` / `datasetApi` 仍保持兼容。

实际改动：

1. 在 `elys_version1/frontend/elys-web/src/types/index.ts` 保留旧 `Project` / `Dataset`，并新增 `Study`、`StudyListResponse`、`StudyMember`、`StudyActivityItem` 等 Study 语义类型。
2. 在 `ProjectMember` 增加可选 `can_run`，用于兼容 Study 协作权限，但不破坏旧成员响应。
3. 在旧 `Dataset` 上增加可选 `dataset_asset_id`，方便旧采集记录和新 Dataset Asset 关系并存。
4. 新增 Dataset 资产相关类型：`DatasetAsset`、`DatasetAssetCreateRequest`、`DatasetAssetUpdateRequest`、`DatasetAssetListResponse`、`DatasetAssetTaskRequest`。
5. 新增 Study 挂载相关类型：`StudyDatasetMount`、`StudyDatasetMountCreateRequest`、`StudyDatasetMountUpdateRequest`、`StudyDatasetMountListResponse`。
6. 新增 Recording 相关类型：`Recording`、`RecordingVersion`、`RecordingListResponse`、`RecordingVersionListResponse`，同时保留 `LegacyRecording = Dataset` 作为旧语义过渡。
7. 新增 Dataset File 相关类型：`DatasetFile`、`DatasetFileMetadata`、`DatasetFilePreviewResponse`、`DatasetFileTreeNode`、`DatasetFileTreeResponse`。
8. 新增 `RunManifestSummary` 和 `StudyOverview`，为后续 Dashboard / Study Home / Run detail 逐步迁移提供统一数据结构。
9. 新增 `elys_version1/frontend/elys-web/src/api/studies.ts`，提供 `studyApi`。该包装层内部继续使用 `/projects` 和 `projectApi`，其中列表响应映射为 `{ studies }`，操作响应同时保留 `project` 与新增 `study`。
10. 新增 `elys_version1/frontend/elys-web/src/api/datasetAssets.ts`，提供 `datasetAssetApi`、`studyDatasetMountApi`、`recordingApi`、`datasetFileApi`。其中 Recording 入口使用 `/projects/{study_id}/recordings`，Dataset File 入口使用 `/dataset-files/{file_id}`，并保留 `recordingApi.listLegacyDatasets()` 继续调用旧 `datasetApi.list()`。

验证结果：

| 命令 | 结果 | 说明 |
|---|---|---|
| `npm run typecheck` | 通过 | `vue-tsc --noEmit` 无错误 |
| `npm run build` | 通过 | Vite 构建成功，未新增阻断问题 |

构建警告：

- 与第 1 步一致：Vite CJS Node API deprecated。
- 与第 1 步一致：`litegraph.js` 使用 `eval`。
- 与第 1 步一致：`PipelinePage` chunk 超过 500 kB。

遗留风险：

1. 新增 `studyApi` 只是前端语义包装，真实后端路径仍是 `/projects`；后续若新增 `/studies` alias，需要再调整内部实现。
2. 新增 Dataset Asset / Recording API 包装层已经按当前后端路由写好，但现有页面尚未使用；第 4 到第 7 步迁移页面时需要逐步替换旧 `projectApi` / `datasetApi`。
3. `StudyOverview` 目前是前端聚合类型，不对应单一后端 summary API；在 Dashboard 重构前仍可能需要多次请求拼装。
4. `DatasetFile` 类型以数据库索引字段为核心，后续页面不得回退到直接展示 `source_path` / `fif_path` 作为事实源。

下一步建议：

1. 第 3 步优先把导航和文案切到 Study / Dataset / Pipeline / Run，让用户侧语义先统一。
2. 第 4 步 Dashboard 可以开始引用 `Study` / `StudyOverview` 类型，但在没有 summary API 前先做降级聚合。
3. 第 5 到第 7 步迁移页面时，优先用 `studyApi`、`recordingApi`、`datasetAssetApi` 表达新语义，旧 `projectApi` / `datasetApi` 只保留兼容入口。
4. 第 8 步处理 Pipeline LoadData 时，复用已有 `PipelineRunCreateRequest.selection_override` 类型，避免再新造一次数据选择结构。

### 第 3 步：统一导航和命名

工作目标：

- 将前端导航从旧 Project 语义逐步调整到 Study / Dataset / Pipeline / Run。
- 保留路由兼容，例如 `/projects` 仍可存在，但页面标题和导航显示为“研究项”。
- 明确哪些导航项是预览页，避免用户误以为已经接入真实数据。
- Dashboard 最终应纳入统一 `WorkbenchShell`，可在第 4 步完成。

建议改动文件：

- `elys_version1/frontend/elys-web/src/data/workbenchPages.ts`
- `elys_version1/frontend/elys-web/src/components/WorkbenchShell.vue`
- `elys_version1/frontend/elys-web/src/router/index.ts`
- `elys_version1/frontend/elys-web/src/views/Index.vue`

验证方式：

- `npm run typecheck`
- `npm run build`
- 浏览器检查导航跳转

Codex 提示词：

```text
第3步：统一前端导航和四对象命名。请调整 workbenchPages.ts、WorkbenchShell.vue、router/index.ts 和必要的首页文案，让用户看到的主对象统一为 Dataset 数据集、Study 研究项、Pipeline 工作流、Run 执行项；保留 /projects 等旧路由兼容，但页面标题、导航和说明优先使用 Study/研究项。对观察、统计、作图、机器学习等未真实接入页面保留预览标识，不要新增假业务逻辑。完成后运行 npm run typecheck 和 npm run build，并更新 日志/2_meeting260522/前端Dataset-Study-Pipeline-Run改造实现工作计划.md 中第 3 步的状态、实际改动、验证结果、遗留风险和下一步建议；如影响 2_meeting260522 中前端或研究管理口径，也同步更新相关 md 文档。
```

执行记录：

- 执行时间：2026-05-22 10:05:56 +08:00
- 状态：已完成。
- 改动范围：只调整前端导航、路由 alias、首页和导入页可见命名；未新增业务接口调用，未接入未实现页面的真实数据逻辑。

实际改动：

1. `workbenchPages.ts` 顶部导航改为四对象主线：工作台、数据集、研究项、工作流 / 执行项；观察、统计、作图、机器学习继续保留 `preview`。
2. `workbenchPages.ts` 侧栏改为“四对象主线 / 预处理与分析预览 / 观察与出图”三组。主线包含工作台总览、Dataset 导入、Study 研究项、Pipeline / Run。
3. `workbenchPages.ts` 中 Pipeline 静态说明改为 live 主线说明，不再描述为“静态预览”；工作流说明改为“选择 Study 与数据规则 -> 创建 Run 并追踪结果”。
4. `workbenchPages.ts` 中管理面板预览去掉 `/mnt/elys_data/projects`、`source_uploads + fifdata` 等服务器目录文案，改为 Dataset assets / Study artifacts / Run manifests。
5. `workbenchPages.ts` 中观察预览的筛选口径从“项目”改为 Study / Dataset / Run。
6. `WorkbenchShell.vue` 的预览 tooltip 改为“预览模块，尚未接入真实 Dataset / Run 数据”，避免静态页面被误解为已接业务数据。
7. `router/index.ts` 保留 `/projects`、`/projects/:id`、`/import` 兼容路径，同时新增 `/studies`、`/studies/:id`、`/datasets` alias；路由名调整为 `Studies`、`StudyDetail`、`DatasetImport`。
8. `Index.vue` 首页推荐路径和站点地图改为 Dataset / Study / Pipeline / Run 主线；`/pipeline` 入口不再标记为静态预览。
9. `ImportPage.vue` 顶部 active nav 改到 `datasets`，可见文案从“目标项目”调整为“目标 Study / Dataset 导入”。

验证结果：

| 命令 | 结果 | 说明 |
|---|---|---|
| `npm run typecheck` | 通过 | `vue-tsc --noEmit` 无错误 |
| `npm run build` | 通过 | Vite 构建成功，未新增阻断问题 |

构建警告：

- 与前两步一致：Vite CJS Node API deprecated。
- 与前两步一致：`litegraph.js` 使用 `eval`。
- 与前两步一致：`PipelinePage` chunk 超过 500 kB。

遗留风险：

1. `ProjectsPage.vue` 和 `ProjectDetailPage.vue` 页面内部文案仍是 Project-centric，本步只完成导航和首页口径，第 5、6 步需要继续改页面主体。
2. `Dashboard.vue` 仍是自定义 shell 和旧项目工作台结构，尚未纳入统一 `WorkbenchShell`；第 4 步需要处理。
3. `/studies`、`/datasets` 目前只是前端 alias，后端真实 API 路径仍是 `/projects` 和旧导入接口。
4. 预览页面保留静态内容，虽然 tooltip 已说明尚未接真实 Dataset / Run 数据，但页面内少量示例数值仍是演示数据。

下一步建议：

1. 第 4 步重构 Dashboard 时，直接使用本步形成的四对象导航和 `StudyOverview` 等语义类型。
2. 第 5、6 步继续把 `ProjectsPage.vue`、`ProjectDetailPage.vue` 的页面标题、操作按钮和危险操作文案从 Project 改到 Study。
3. 第 7 步再把 Import/BidsUploadPanel 从“兼容 Study 选择”推进到 working Dataset / Recording / dataset_files 语义。

### 第 4 步：Dashboard 重构为四对象总览

工作目标：

- 将 Dashboard 从“项目列表 + 内嵌上传”改为平台工作台。
- 首屏展示四类对象：
  - Dataset 数据资产状态
  - Study 研究项
  - Pipeline 工作流
  - Run 执行项
- 移除或弱化 `bids_root`、`source_path`、`fif_path` 等服务器路径展示。
- 不再在 Dashboard 内嵌完整上传流程，上传入口跳转到 Import / Dataset 页面。
- 避免一次性拉取所有 Study 的所有 Dataset 造成性能问题，可只展示近期 Study / Run 摘要。

建议改动文件：

- `elys_version1/frontend/elys-web/src/views/Dashboard.vue`
- `elys_version1/frontend/elys-web/src/style.css`
- 必要时补充 API overview 封装

验证方式：

- `npm run typecheck`
- `npm run build`
- 浏览器检查 `/dashboard`
- 移动端宽度下检查卡片和表格是否溢出

Codex 提示词：

```text
第4步：将 Dashboard 重构为 Dataset / Study / Pipeline / Run 四对象总览。请改造 Dashboard.vue，使其使用统一工作台外壳或至少与 WorkbenchShell 视觉一致；首屏展示数据资产、研究项、工作流、执行项的摘要、最近活动和快捷入口。移除 Dashboard 内嵌完整上传流程，上传入口跳转到 Import/Dataset 导入页；不要把 bids_root/source_path/fif_path 等服务器路径作为主要展示信息。注意避免全量 N+1 拉取所有 Study 的所有 Dataset，可优先使用已有 API 做有限摘要或降级展示。完成后运行 npm run typecheck、npm run build，并用浏览器检查 /dashboard 桌面和移动视口；更新 日志/2_meeting260522/前端Dataset-Study-Pipeline-Run改造实现工作计划.md 中第 4 步的状态、实际改动、验证结果、遗留风险和下一步建议；如影响 2_meeting260522 中前端工作台或文件管理口径，也同步更新相关 md 文档。
```

执行记录：

- 执行时间：2026-05-22 10:40:36 +08:00
- 状态：已完成。
- 改动范围：重写 `Dashboard.vue`，把 Dashboard 从旧 Project 工作台改为 Dataset / Study / Pipeline / Run 四对象总览。

实际改动：

1. `Dashboard.vue` 改为复用 `WorkbenchShell`，不再复制 topbar/sidebar。
2. 首屏 KPI 改为 Dataset 数据集、Study 研究项、Pipeline 工作流、Run 执行项。
3. 移除 Dashboard 内嵌 `BidsUploadPanel` 和旧上传表单，只保留跳转到 `/datasets`、`/studies`、`/pipeline` 的快捷入口。
4. Dashboard 不再展示 `bids_root`、`source_path`、`fif_path`、`Project ID`、`Data Root` 等服务器路径或实现字段。
5. 读取策略改为有限摘要：先读取 Study 列表和 Dataset Asset 列表，再只对最近 3 个 Study 拉 Pipeline 摘要，并只对前 4 个 Pipeline 拉少量 Run 摘要，避免全量 Study × Dataset 的 N+1。
6. 增加最近 Study、Dataset Asset、Pipeline、Run 聚合活动列表；当前活动来自已有 API 聚合，后续可替换为审计事件 API。
7. 对 Dataset Asset 摘要接口不可用、部分 Pipeline 摘要失败等情况提供降级提示，不阻塞 Dashboard 主界面。

验证结果：

| 验证项 | 结果 | 说明 |
|---|---|---|
| `npm run typecheck` | 通过 | `vue-tsc --noEmit` 无错误 |
| `npm run build` | 通过 | Vite 构建成功 |
| `/dashboard` 桌面视口 | 通过 | 浏览器检查四对象 KPI 存在，无上传 input，无旧路径字段，无横向溢出 |
| `/dashboard` 移动视口 390px | 通过 | 浏览器检查无横向溢出，四对象 KPI 与主要区块可读 |

构建警告：

- Vite CJS Node API deprecated，仍为既有警告。
- `litegraph.js` 使用 `eval`，仍为既有警告。
- `PipelinePage` chunk 超过 500 kB，仍为既有警告。

遗留风险：

1. Dashboard 仍依赖前端聚合多个旧 API，准确性和性能不如专门的 Dashboard summary API。
2. Dataset Asset API 在部分环境可能未启用，页面已降级展示，但 Dataset 数量可能无法代表真实全部数据资产。
3. 最近活动当前是前端聚合，不等同于正式 audit_events；后续需要 Study activity / audit summary API。
4. `/projects` 列表页和 `/projects/:id` 详情页仍有旧 Project 口径，需要第 5、6 步继续收口。

下一步建议：

1. 第 5 步将 `ProjectsPage.vue` 改为 Study 研究项列表，隐藏服务器目录并改写危险操作文案。
2. 后续补 Dashboard summary / Study overview API 后，再把当前有限聚合替换为单次摘要读取。

### 第 5 步：Study 列表页改造

工作目标：

- 将 `ProjectsPage.vue` 产品语义改为 Study 列表。
- 页面仍可调用 `projectApi`，但用户看到的是研究项。
- 不展示 Data Root、服务器目录等实现细节。
- 展示每个 Study 的成员角色、数据概况、Pipeline/Run 概况、最近活动。
- 删除、归档、恢复、清理等危险操作用 Study 语义重新命名，并明确不会物理删除已被依赖的 Run/Artifact。

建议改动文件：

- `elys_version1/frontend/elys-web/src/views/ProjectsPage.vue`
- `elys_version1/frontend/elys-web/src/api/studies.ts`
- `elys_version1/frontend/elys-web/src/types/index.ts`

验证方式：

- `npm run typecheck`
- `npm run build`
- 浏览器检查 `/projects`

Codex 提示词：

```text
第5步：将 ProjectsPage 收口为 Study 研究项列表。请改造 ProjectsPage.vue，把用户可见文案从 Project/项目目录调整为 Study/研究项；保留旧 projectApi 调用兼容，但通过前端 Study 类型或 studyApi 包装表达。移除 Data Root 等服务器目录展示，改为成员角色、数据概况、Pipeline/Run 概况、最近活动和状态。删除、归档、恢复、清理等操作使用研究项语义，并在危险操作提示中说明不会破坏已被 Run 依赖的数据和输出。完成后运行 npm run typecheck、npm run build，并检查 /projects；更新 日志/2_meeting260522/前端Dataset-Study-Pipeline-Run改造实现工作计划.md 中第 5 步的状态、实际改动、验证结果、遗留风险和下一步建议；如影响 2_meeting260522 中 Study 权限或清理策略口径，也同步更新相关 md 文档。
```

执行记录：

- 执行时间：2026-05-22 11:15:30 +08:00
- 状态：已完成。
- 改动范围：重构 `ProjectsPage.vue`，保留旧 `/projects` 路由兼容，但用户可见层收口为 Study / 研究项。

实际改动：

1. 页面标题、按钮、标签页、空态、创建弹窗和治理弹窗全部改为 Study / 研究项语义。
2. 页面代码改用 `studyApi` 和 `Study` 类型作为主入口，底层仍兼容既有 `/projects` API。
3. 移除卡片中的 `Data Root`、`bids_root`、`Project ID` 等服务器路径和旧项目目录展示；仅保留 `Study ID` 作为业务标识。
4. Study 卡片增加“我的角色”“成员权限”“最近活动”等协作信息；成员权限通过 `studyApi.listMembers()` 做有限摘要。
5. Study 卡片增加 Recording / Pipeline / Run / 运行中四类概况；Recording 暂由旧 datasets list 兼容统计，Pipeline / Run 由现有 pipeline API 做有限摘要。
6. 摘要加载限制为当前列表前 12 个 Study，Run 摘要只读取每个 Study 前 3 个 Pipeline 的少量 Run，避免 Study 列表天然变成全量重查询页。
7. 回收站、恢复和清理操作改为 Study 治理语义；危险操作提示中明确 Dataset 原始资产不应随 Study 清理物理删除，存在下游 Run / Artifact 依赖时后端应阻断。
8. 创建 Study 的配额说明改为运行空间配额，避免用户理解为 Dataset 原始资产所有权。

验证结果：

| 验证项 | 结果 | 说明 |
|---|---|---|
| `npm run typecheck` | 通过 | `vue-tsc --noEmit` 无错误 |
| `npm run build` | 通过 | Vite 构建成功 |
| `/projects` 桌面视口 | 通过 | Study 卡片、成员权限、Recording/Pipeline/Run 摘要可见，无旧路径字段，无横向溢出 |
| `/projects` 移动视口 390px | 通过 | 卡片与摘要区可读，无横向溢出 |

构建警告：

- Vite CJS Node API deprecated，仍为既有警告。
- `litegraph.js` 使用 `eval`，仍为既有警告。
- `PipelinePage` chunk 超过 500 kB，仍为既有警告。

遗留风险：

1. Study 列表页的 Recording 数仍来自旧 `datasets` API，尚不能表达完整 Dataset Asset / Mount / Recording Version 层级。
2. 成员、Pipeline、Run 摘要仍是前端有限聚合，后续应由 Study overview API 一次返回，避免列表页长期维护多接口摘要逻辑。
3. 清理操作前端已改为依赖保护语义，但最终是否阻断仍取决于后端 purge / cleanup 的依赖检查。
4. Study 详情页仍未改造，进入 `/studies/:id` 后仍会看到旧 ProjectDetail 页面语义，需要第 6 步继续收口。

下一步建议：

1. 第 6 步将 `ProjectDetailPage.vue` 改为 Study 主页，按 Overview / Data / Pipelines / Runs / Artifacts / Activity 组织。
2. 后端补 `StudyOverview` 后，前端可把 Study 列表当前的有限聚合替换为单个 summary API。

### 第 6 步：Study 详情页改造

工作目标：

- 将 `ProjectDetailPage.vue` 改为 Study 主页。
- 页面结构建议：
  - Overview：研究项摘要、成员、权限、锁状态
  - Data：挂载 Dataset、Recording、版本、文件状态
  - Pipelines：工作流列表和状态
  - Runs：执行项列表、状态、最近错误
  - Artifacts：输出、预览、固定状态
  - Activity：关键审计事件
- 移除 `source_uploads`、`fifdata`、`derivatives` 这种旧目录结构解释。
- 保留旧 API 数据不足时的空态，不伪造不可用功能。

建议改动文件：

- `elys_version1/frontend/elys-web/src/views/ProjectDetailPage.vue`
- `elys_version1/frontend/elys-web/src/style.css`
- 可能新增 Study 子组件

验证方式：

- `npm run typecheck`
- `npm run build`
- 浏览器检查 `/projects/:id`

Codex 提示词：

```text
第6步：将 ProjectDetailPage 改造为 Study 研究项主页。请重构 ProjectDetailPage.vue 的信息架构，以 Overview、Data、Pipelines、Runs、Artifacts、Activity 为核心组织内容；用户可见文案使用 Study/研究项，旧 project id 只作为兼容标识。移除 source_uploads/fifdata/derivatives 等旧目录解释，不暴露服务器绝对路径；API 暂未提供的数据使用明确空态或“待接入”状态，不伪造结果。完成后运行 npm run typecheck、npm run build，并检查 /projects/:id；更新 日志/2_meeting260522/前端Dataset-Study-Pipeline-Run改造实现工作计划.md 中第 6 步的状态、实际改动、验证结果、遗留风险和下一步建议；如影响 2_meeting260522 中 Study/Dataset/文件管理口径，也同步更新相关 md 文档。
```

执行记录：
- 执行时间：2026-05-22 11:50:53 +08:00
- 状态：已完成。
- 改动范围：重构 `ProjectDetailPage.vue`，将旧 Project Detail + Dataset/QA 页面改为 Study 研究项主页；未新增假业务接口，仍兼容当前 `/projects`、Recording、Pipeline、Run、Artifact API。

实际改动：
1. 页面主结构改为 `WorkbenchShell` 下的 Study 主页，顶部使用 Study / 研究项文案，保留 `Study ID` 作为兼容标识，不再显示 `Project ID`、`Data Root` 或服务器目录。
2. 首屏 KPI 改为 Data、Pipelines、Runs、Artifacts，帮助用户从 Study 视角理解当前研究项的主要对象数量。
3. 新增 Overview 区块，展示 Study 状态、兼容标识、成员与权限、运行空间配额；成员权限不可用时显示空态或待接入，不伪造协作状态。
4. 新增 Data 区块，拆成 Dataset Mounts 与 Recordings。优先读取 `studyDatasetMountApi` 与 `recordingApi`；Recording API 不可用时才降级到旧 datasets list，并将其表达为采集记录，而不是完整 Dataset Asset。
5. 新增 Pipelines / Runs / Artifacts 区块，使用现有 Pipeline API 做有限摘要：最多读取少量 Pipeline、Run 和 Run Artifact，避免详情页做无边界 N+1。
6. 新增 Activity 区块，当前只用已有对象更新时间聚合为可读活动；明确说明正式审计事件待接入，避免把前端聚合当成真实 audit_events。
7. 移除旧页面中的 QA mock/review 操作、`source_uploads`、`fifdata`、`derivatives`、`fif_path` 等目录解释和路径展示；canonical FIF 只作为状态展示，不暴露服务器绝对路径。
8. 修复移动端 Data 表格导致页面级横向溢出的问题，让表格横向滚动限制在容器内部。

验证结果：
| 验证项 | 结果 | 说明 |
|---|---|---|
| `npm run typecheck` | 通过 | `vue-tsc --noEmit` 无错误 |
| `npm run build` | 通过 | Vite 构建成功 |
| `/projects/:id` 桌面视口 | 通过 | headless Chrome 检查 Overview、Data、Pipelines、Runs、Artifacts、Activity 六区块可见；无 `source_uploads`、`fifdata`、`derivatives`、`Project ID`、`Data Root`、`bids_root`、`source_path`、`fif_path` 等旧字段；无横向溢出 |
| `/projects/:id` 移动视口 | 通过 | 390px 级移动视口检查六区块可见；旧字段未出现在页面文本中；修复后无页面级横向溢出 |

构建警告：
- 与前几步一致：Vite CJS Node API deprecated。
- 与前几步一致：`litegraph.js` 使用 `eval`。
- 与前几步一致：`PipelinePage` chunk 超过 500 kB，后续仍建议拆分。

遗留风险：
1. Study 主页当前仍需要前端聚合多个接口；更理想的是后端提供 `StudyOverview` summary API，一次返回成员、Dataset Mount、Recording、Pipeline、Run、Artifact 和 Activity 摘要。
2. Activity 目前不是真实审计流，只是已有对象时间聚合；后续应接入 `audit_events` 或 Study activity API。
3. Dataset Mount、Recording、Artifact 的详情、预览、下载入口尚未在本页完整展开，后续应由 Dataset File / Artifact API 承担。
4. 旧 `datasets.fif_path` 只在前端内部用于判断 canonical FIF 状态，不能作为新 UI 的事实源；后续应改为 `dataset_files.file_role=canonical_fif`。
5. 旧 QA mock/review 操作已从 Study 主页移除；如果仍需要质量审核，应在 Dataset/Recording 详情或专门 QC 页面中重新设计。

下一步建议：
1. 第 7 步继续改造 `ImportPage.vue` 与 `BidsUploadPanel.vue`，把上传入口从“上传到项目目录”改为“导入到 working Dataset / Recording”。
2. 后端补 `StudyOverview`、Study activity、Dataset Mount detail API 后，可减少 Study 主页的前端聚合和降级提示。
3. 后续 Dataset 文件浏览、Artifact 预览/下载、Run lineage 可从本页入口跳转到专门详情页，不建议把所有明细都塞进 Study 主页。

### 第 7 步：Import / Dataset 上传语义升级

工作目标：

- 将上传入口表达为“导入到 working Dataset / Study 数据资产”，而不是“上传到项目目录”。
- `BidsUploadPanel` 继续保留 BrainVision / EDF / BDF 分组能力。
- 上传结果中尽量显示：
  - original upload
  - Raw BIDS logical view
  - canonical FIF
  - dataset_files 索引
  - 转换状态
- 如果后端还没有完整 Dataset Asset 入口，前端可以显示“当前研究项的 working Dataset”，但不要构造不存在的正式发布语义。

建议改动文件：

- `elys_version1/frontend/elys-web/src/views/ImportPage.vue`
- `elys_version1/frontend/elys-web/src/components/BidsUploadPanel.vue`
- `elys_version1/frontend/elys-web/src/api/datasets.ts`
- `elys_version1/frontend/elys-web/src/types/index.ts`

验证方式：

- `npm run typecheck`
- `npm run build`
- 浏览器检查 `/import`
- 有条件时走一次小文件上传

Codex 提示词：

```text
第7步：升级 Import 和 BidsUploadPanel 的 Dataset 语义。请改造 ImportPage.vue 和 BidsUploadPanel.vue，让上传流程表达为导入到 working Dataset 或 Study 的默认数据资产；保留 BrainVision/EDF/BDF 分组和现有上传接口兼容。上传结果和状态中优先展示 original upload、Raw BIDS 逻辑视图、canonical FIF、dataset_files 索引和转换状态，不再强调项目目录路径。如果后端暂未提供独立 Dataset Asset API，请用兼容空态说明“当前研究项 working Dataset”，不要虚构发布/共享能力。完成后运行 npm run typecheck、npm run build，并检查 /import；更新 日志/2_meeting260522/前端Dataset-Study-Pipeline-Run改造实现工作计划.md 中第 7 步的状态、实际改动、验证结果、遗留风险和下一步建议；如影响 2_meeting260522 中 Dataset 文件管理或导入任务口径，也同步更新相关 md 文档。
```

### 第 8 步：Pipeline LoadData 与 Run override 收口

工作目标：

- 修正当前 `PipelinePage.vue` 中 “固定当前命中” 把 `dataset_ids` 写回 Pipeline definition 的问题。
- 标准交互应为：
  - Pipeline 保存 LoadData 的选择规则。
  - Run 创建时允许填写 `selection_override`。
  - 具体命中的 dataset_file_id / recording / version 进入 Run 输入快照。
- 兼容旧 Pipeline definition 中已有 `selection_mode=explicit`、`dataset_ids` 的情况。
- 前端 Run 创建弹窗应展示本次数据选择覆盖项，并说明不会修改 Pipeline definition。

建议改动文件：

- `elys_version1/frontend/elys-web/src/views/PipelinePage.vue`
- `elys_version1/frontend/elys-web/src/api/pipelines.ts`
- `elys_version1/frontend/elys-web/src/types/index.ts`

验证方式：

- `npm run typecheck`
- `npm run build`
- 手动检查 Pipeline 保存 payload 不再标准写入具体 `dataset_ids`
- 手动检查 Run 创建 payload 包含 `selection_override`

Codex 提示词：

```text
第8步：收敛 Pipeline LoadData 数据选择到 Run override。请改造 PipelinePage.vue、api/pipelines.ts 和类型定义，把“固定当前命中数据”从写回 Pipeline definition 的标准行为，改为 Run 创建时的 selection_override；Pipeline definition 只保存选择规则和节点参数，具体 dataset_ids/dataset_file_id/selector 命中进入 Run 创建 payload，并在 UI 中说明本次覆盖不会修改工作流定义。保留旧 selection_mode=explicit 和 dataset_ids 的兼容显示与运行，不要破坏旧工作流。完成后运行 npm run typecheck、npm run build，并手动核对 Pipeline 保存 payload 与 Run 创建 payload；更新 日志/2_meeting260522/前端Dataset-Study-Pipeline-Run改造实现工作计划.md 中第 8 步的状态、实际改动、验证结果、遗留风险和下一步建议；如影响 2_meeting260522 中 Pipeline/Run 功能规范，也同步更新相关 md 文档。
```

### 第 9 步：Run 创建与详情体验增强

工作目标：

- Run 创建弹窗清楚支持：
  - `run_mode=trial/analysis/replay/system`
  - `save_policy=temporary/current/pinned/discard`
  - `selection_override`
- Run 详情区域展示：
  - inputs
  - node runs
  - tasks/events
  - artifacts
  - manifest
  - lineage 入口
- Run 成功状态统一显示为 `completed`，Task 成功状态显示为 `succeeded`。

建议改动文件：

- `elys_version1/frontend/elys-web/src/views/PipelinePage.vue`
- `elys_version1/frontend/elys-web/src/api/pipelines.ts`
- `elys_version1/frontend/elys-web/src/types/index.ts`

验证方式：

- `npm run typecheck`
- `npm run build`
- 手动创建 trial Run 和 analysis Run

Codex 提示词：

```text
第9步：增强 Run 创建和 Run 详情体验。请在 PipelinePage.vue 中完善 Run 创建弹窗，明确支持 run_mode=trial/analysis/replay/system、save_policy=temporary/current/pinned/discard 和 selection_override；Run 详情中按 inputs、node runs、tasks/events、artifacts、manifest、lineage 组织信息。Run 成功状态统一显示 completed，Task 成功状态显示 succeeded。不要改变旧 /run 兼容入口。完成后运行 npm run typecheck、npm run build，并手动验证 trial Run 和 analysis Run 创建流程；更新 日志/2_meeting260522/前端Dataset-Study-Pipeline-Run改造实现工作计划.md 中第 9 步的状态、实际改动、验证结果、遗留风险和下一步建议；如影响 2_meeting260522 中 Pipeline/Run/API 文档，也同步更新相关 md 文档。
```

### 第 10 步：Task 与协作状态前端接入

工作目标：

- 接入或预留：
  - Run cancel
  - Run retry
  - Task cancel
  - Task retry
  - Task events list / SSE
  - Pipeline edit lock
  - Study run lock
- 锁状态和任务状态要让用户知道“谁正在编辑/运行、什么时候过期、能不能抢占或等待”。
- 如果后端 SSE 尚未稳定，可先使用事件列表轮询。

建议改动文件：

- `elys_version1/frontend/elys-web/src/views/PipelinePage.vue`
- `elys_version1/frontend/elys-web/src/api/pipelines.ts`
- 可新增 `elys_version1/frontend/elys-web/src/api/tasks.ts`
- 可新增 `elys_version1/frontend/elys-web/src/api/locks.ts`

验证方式：

- `npm run typecheck`
- `npm run build`
- 手动检查 cancel / retry 按钮状态和错误提示

Codex 提示词：

```text
第10步：接入 Task 与协作状态前端能力。请在 Pipeline/Run 相关页面和 API 封装中接入或预留 Run cancel、Run retry、Task cancel、Task retry、Task events list/SSE、Pipeline edit lock、Study run lock。锁状态要显示持有人、过期时间和当前用户可执行操作；若 SSE 尚未稳定，先使用事件列表或轮询兼容。所有按钮必须根据 Run/Task/Pipeline 状态禁用或提示原因。完成后运行 npm run typecheck、npm run build，并手动检查 cancel/retry/lock 的可见状态；更新 日志/2_meeting260522/前端Dataset-Study-Pipeline-Run改造实现工作计划.md 中第 10 步的状态、实际改动、验证结果、遗留风险和下一步建议；如影响 2_meeting260522 中任务队列或协作锁口径，也同步更新相关 md 文档。
```

### 第 11 步：Artifact 语义操作接入

工作目标：

- 将 Artifact 操作从底层 retention 字段展示，升级为用户能理解的语义：
  - 固定结果 pin
  - 取消固定 unpin
  - 隐藏输出 hide
  - 清理缓存 cleanup
- 遇到下游依赖阻塞时，展示依赖 Run / Artifact 信息，而不是只报失败。
- Artifact 下载、预览、metadata 尽量通过 artifact_id，不展示绝对路径。

建议改动文件：

- `elys_version1/frontend/elys-web/src/views/PipelinePage.vue`
- `elys_version1/frontend/elys-web/src/api/pipelines.ts`
- 可新增 `elys_version1/frontend/elys-web/src/api/artifacts.ts`
- `elys_version1/frontend/elys-web/src/types/index.ts`

验证方式：

- `npm run typecheck`
- `npm run build`
- 手动检查 Artifact 操作按钮与错误提示

Codex 提示词：

```text
第11步：接入 Artifact 固定、取消固定、隐藏和清理语义操作。请在 Pipeline/Run 详情中把 Artifact retention 操作包装为用户可理解的固定结果、取消固定、隐藏输出、清理缓存等按钮；内部可继续调用现有 retention 或 artifact API。下载、预览和 metadata 入口通过 artifact_id 访问，不暴露服务器绝对路径。遇到依赖阻塞 409 时，展示依赖 Run/Artifact 明细和可操作建议。完成后运行 npm run typecheck、npm run build，并手动检查 Artifact 操作状态和错误提示；更新 日志/2_meeting260522/前端Dataset-Study-Pipeline-Run改造实现工作计划.md 中第 11 步的状态、实际改动、验证结果、遗留风险和下一步建议；如影响 2_meeting260522 中 Artifact 保留策略或文件管理口径，也同步更新相关 md 文档。
```

### 第 12 步：静态预览页冻结和文案清理

工作目标：

- 首页和静态模块不要继续讲旧 Project / `source_uploads` / `fifdata`。
- 对未实现真实业务接入的页面显示“预览 / 待接入真实数据”。
- 避免用户从预览页误以为可以直接操作真实 Dataset / Run。
- 不在本步做 Observe / Statistics / Figures / ML 的真实后端接入。

建议改动文件：

- `elys_version1/frontend/elys-web/src/views/Index.vue`
- `elys_version1/frontend/elys-web/src/views/StaticWorkbenchPage.vue`
- 观察、统计、作图、机器学习等预览页面
- `elys_version1/frontend/elys-web/src/data/workbenchPages.ts`

验证方式：

- `npm run typecheck`
- `npm run build`
- 浏览器检查主要预览页文案

Codex 提示词：

```text
第12步：冻结静态预览页并清理旧文案。请检查 Index.vue、StaticWorkbenchPage.vue、观察/统计/作图/机器学习等预览页面和 workbenchPages.ts，移除旧 Project/source_uploads/fifdata 等容易误导的文案；对尚未接入真实 Dataset/Study/Pipeline/Run 链路的页面保留预览或待接入标识，不新增假业务逻辑。完成后运行 npm run typecheck、npm run build，并浏览检查主要预览页面；更新 日志/2_meeting260522/前端Dataset-Study-Pipeline-Run改造实现工作计划.md 中第 12 步的状态、实际改动、验证结果、遗留风险和下一步建议；如影响 2_meeting260522 中功能模块或前端页面说明，也同步更新相关 md 文档。
```

### 第 13 步：全链路前端回归和文档收口

工作目标：

- 验证核心链路：
  - 登录
  - Dashboard 四对象总览
  - 创建 Study
  - 进入 Study 主页
  - Import 上传 EEG
  - 查看 Dataset / Recording / File 状态
  - 创建 / 保存 Pipeline
  - 创建 trial Run
  - 创建 analysis Run
  - 查看 Run inputs / tasks / artifacts / manifest / lineage
  - cancel / retry / artifact 操作状态
- 更新 docs_v2 前端页面总览、研究管理、API、任务队列、Pipeline/Run 相关页面。
- 更新 `日志/2_meeting260522` 中差异分析和本计划最终结论。

验证方式：

- `npm run typecheck`
- `npm run build`
- 必要时启动 `npm run dev` 并浏览器截图检查
- 如果涉及 docs_v2，运行 `mkdocs build`

Codex 提示词：

```text
第13步：前端 Dataset / Study / Pipeline / Run 全链路回归与文档收口。请对改造后的前端核心链路做回归验证：登录、Dashboard 四对象总览、创建 Study、Study 主页、Import 上传 EEG、Dataset/Recording/File 状态、创建和保存 Pipeline、创建 trial Run、创建 analysis Run、查看 Run inputs/tasks/artifacts/manifest/lineage、Run cancel/retry、Artifact 固定/隐藏/清理状态。运行 npm run typecheck、npm run build；如涉及 docs_v2 则运行 mkdocs build；必要时启动前端并用浏览器截图检查 /dashboard、/projects、/projects/:id、/import、/pipeline。完成后更新 docs_v2 中前端页面总览、研究管理、API、任务队列、Pipeline/Run 相关页面，并更新 日志/2_meeting260522/前端页面与Dataset-Study-Pipeline-Run规则差异分析.md 和 日志/2_meeting260522/前端Dataset-Study-Pipeline-Run改造实现工作计划.md 的最终结论；如本轮前端实现改变了 2_meeting260522 中的数据库、文件管理、Pipeline/Run 或后端 API 口径，也同步更新相关 md 文档。
```

## 7. 关键风险和处理建议

### 7.1 后端对象命名仍是 Project / Dataset

风险：

- 前端先显示 Study / Dataset Asset，但 API 仍是 `/projects`、旧 `datasets`，容易造成类型混乱。

建议：

- 先做前端兼容类型和 API 包装，不急于重命名后端路径。
- 页面代码尽量引用 `Study`、`Recording`、`DatasetAsset`，底层 API 文件内部再做旧字段映射。

### 7.2 Dashboard 当前耦合太重

风险：

- `Dashboard.vue` 自己实现 shell、项目列表、上传、配额、数据表，改造范围较大。

建议：

- 先把 Dashboard 拆成概览和快捷入口，不在首轮保留完整上传表单。
- 上传逻辑迁移到 Import / BidsUploadPanel 主线。

### 7.3 PipelinePage 功能多，单步改动风险高

风险：

- Pipeline 编辑、Run 创建、Run 详情、Artifact、Task 都在同一页，容易出现回归。

建议：

- 先改 LoadData / Run override 这个边界问题。
- 再逐步增强 Run detail、Task、Artifact 操作。
- 必要时把 Run detail 拆出子组件。

### 7.4 静态页面过多

风险：

- 一次性接入 Observe / Statistics / Figures / ML 会扩大范围，且后端数据接口未必稳定。

建议：

- 本轮只统一导航和预览标签。
- 等 Dataset File、Artifact、Run Manifest 查询稳定后，再分模块接入真实数据。

### 7.5 API 缺失会限制前端体验

风险：

- 如果缺少 Dataset Asset overview、Study summary、Run lineage、Task SSE、Artifact semantic API，前端只能用降级展示。

建议：

- 前端先做空态和兼容展示。
- 在文档中明确“前端已预留，等待后端 API”。

## 8. 最小可用改造边界

如果时间有限，MVP 前端至少完成以下内容：

1. 类型和 API 兼容层新增 Study / Recording / DatasetAsset 语义。
2. 导航和页面文案统一，不再让用户看到 Project 是主产品概念。
3. Dashboard 改为四对象总览，不再内嵌完整上传。
4. Study 列表和详情页隐藏服务器目录，展示研究项主线。
5. Import 页面表达为 Dataset 导入，不再表达为项目目录操作。
6. Pipeline 的具体数据固定动作改到 Run override。
7. Run 创建和详情能看到 run_mode、save_policy、inputs、tasks、artifacts。
8. 静态预览页面保留预览标识，不做假功能。

完成上述内容后，前端就能基本符合 Dataset / Study / Pipeline / Run 的产品规则。

## 9. 当前结论

前端改造不是简单改几个标题，而是一次信息架构收口。当前代码已经有可复用基础：路由清楚、`WorkbenchShell` 已存在、`BidsUploadPanel` 上传分组能力可保留、`PipelinePage` 已经部分接入新 Run 字段。

主要差距集中在三处：

- Dashboard 和 Study 页面仍以旧 Project / 目录管理为中心。
- Pipeline 的数据选择事实仍可能写回工作流定义。
- Dataset Asset / Recording / Run Manifest / Artifact 语义在前端还没有形成稳定入口。

推荐按本文 13 步推进，先完成 P0 的语义层、导航、Dashboard、Study、Pipeline/Run 边界，再做 Task、Artifact 和预览页收口。
