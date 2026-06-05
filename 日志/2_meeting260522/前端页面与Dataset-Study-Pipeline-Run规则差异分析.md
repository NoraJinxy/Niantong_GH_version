# 前端页面与 Dataset / Study / Pipeline / Run 规则差异分析

文档生成时间：2026-05-22 09:27:30 +08:00

## 1. 本次分析范围

本次只做前端现状分析，不修改业务页面代码。

读取范围：

1. `elys_version1/frontend/elys-web/src/router/index.ts`
2. `elys_version1/frontend/elys-web/src/data/workbenchPages.ts`
3. `elys_version1/frontend/elys-web/src/views/Dashboard.vue`
4. `elys_version1/frontend/elys-web/src/views/ProjectsPage.vue`
5. `elys_version1/frontend/elys-web/src/views/ProjectDetailPage.vue`
6. `elys_version1/frontend/elys-web/src/views/ImportPage.vue`
7. `elys_version1/frontend/elys-web/src/views/PipelinePage.vue`
8. `elys_version1/frontend/elys-web/src/views/Index.vue`
9. `elys_version1/frontend/elys-web/src/components/WorkbenchShell.vue`
10. `elys_version1/frontend/elys-web/src/components/BidsUploadPanel.vue`
11. `elys_version1/frontend/elys-web/src/api/projects.ts`
12. `elys_version1/frontend/elys-web/src/api/datasets.ts`
13. `elys_version1/frontend/elys-web/src/api/pipelines.ts`
14. `elys_version1/frontend/elys-web/src/types/index.ts`
15. `wiki/docs_v2/2-00-系统架构总览.md`
16. `wiki/docs_v2/5-00-研究管理总览.md`
17. `wiki/docs_v2/5-10-Study研究项管理.md`
18. `wiki/docs_v2/6-00-前端页面总览.md`

## 2. 前端应遵守的新规则

前端需要和当前产品对象统一：

| 对象 | 前端产品语义 | 前端不应做的事 |
| --- | --- | --- |
| Dataset / 数据集 | 平台级数据资产，包含原始上传、Raw BIDS 逻辑视图、canonical FIF、Recording / Version / File 索引 | 不把旧 `datasets` 表的单条 recording 直接等同为完整 Dataset 资产 |
| Study / 研究项 | 协作空间，引用 Dataset，管理成员、设置、Pipeline、Run、Artifact 和审计 | 不继续在用户可见层把 Study 叫成 Project，不把 Study 当作原始文件目录 |
| Pipeline / 工作流 | 可编辑的处理方案，保存节点、连线、参数和数据选择规则 | 不把具体 `dataset_id`、文件路径、某次上传版本当作标准定义保存 |
| Run / 执行项 | 一次运行事实，冻结输入快照、定义快照、任务、节点、Artifact、manifest 和 lineage | 不依赖“当前数据”重算历史事实，不覆盖旧 Run |

前端还应遵守几条界面原则：

1. 用户不直接理解服务器目录，尽量不展示 `bids_root`、`source_path`、`fif_path` 这类路径字段。
2. 当前代码可以继续调用 `/projects` API，但用户可见文案应逐步统一为 Study / 研究项。
3. 旧 `Dataset` 类型在前端语义上更像 Recording / 采集记录；未来需要引入 Dataset Asset、Dataset File、Dataset Version 的类型。
4. 静态预览页面继续保留“预览/未接入”标识，第一轮不要强行接入未实现后端能力。

## 3. 总体差距判断

总体差距：**中到大**。

原因是后端和 Pipeline/Run 文档已经基本进入 Dataset / Study / Pipeline / Run 体系，但前端大部分真实工作台页面仍然是较早的 Project 工作台设计：

```text
Dashboard / Projects / ProjectDetail / Import
  仍主要围绕 Project、项目数据目录、旧 datasets 表、fif_path 展示

PipelinePage
  已接近新规范，但 LoadData 选择和页面命名仍有旧语义

Observe / Statistics / Figures / ML / Admin
  多数仍是静态预览，不建议第一轮改业务逻辑
```

结论：前端不适合只做“把项目改成研究项”的文案替换。真正需要的是把真实工作台页面重新分成四类入口：

1. Dataset 资产与导入入口
2. Study 协作与研究主页
3. Pipeline 工作流编辑入口
4. Run 执行与结果追溯入口

## 4. 页面现状与差异

### 4.1 Dashboard.vue

当前状态：

1. Dashboard 没有复用 `WorkbenchShell`，而是复制了一套 topbar 和 sidebar。
2. 页面主对象是 Project：最近项目、我的项目、项目数、项目配额、Project ID、项目数据根目录。
3. 页面内嵌 `BidsUploadPanel`，选中一个 Project 后直接上传数据。
4. 页面会 `projectApi.list()` 后对所有项目逐个 `datasetApi.list(project.id)`，用于统计数据集和最近导入。
5. 数据表展示的是旧 `Dataset` / recording 字段：`bids_subject_id`、`task`、`session`、`run`、`source_format`、`fif_path`、`n_channels`、`n_events`。
6. 没有展示 Pipeline、Run、Task、Artifact、Manifest、Lineage、锁、最近协作行为。

与新规则的差异：**大**。

主要问题：

| 问题 | 影响 |
| --- | --- |
| Dashboard 仍是 Project 工作台 | 用户会继续把 Study 理解为项目目录，而不是研究协作空间 |
| 直接展示 `bids_root` 和项目本地目录 | 违背“用户不直接操作服务器目录”的产品边界 |
| 把旧 `datasets` 记录称为数据集 | 会混淆 Dataset Asset、Recording、Dataset File |
| Dashboard 同时承担项目列表、创建、上传、数据表 | 信息架构过重，后续接入 Pipeline/Run 后会更乱 |
| 不展示 Run/Task/Artifact 状态 | 用户无法从首页知道哪些分析正在跑、失败、等待确认或产物需要处理 |
| 对所有项目逐个拉取 datasets | 数据量大时前端 N+1 请求会很重 |

建议方向：

1. Dashboard 改为“四对象总览”，不再是 Project 详情页。
2. 首页 KPI 改成：Dataset 资产 / Study 研究项 / Pipeline 工作流 / Run 执行项。
3. 主要区块建议：
   - 我的 Study：最近进入、锁状态、成员角色。
   - 数据资产：working Dataset、最近上传、canonical FIF 生成状态。
   - 运行队列：queued / running / waiting_user_input / failed Run。
   - 最近结果：current / pinned Artifact、需要确认或清理的输出。
4. 上传入口保留为快捷按钮即可，具体上传流程放到 Dataset/Import 页面。
5. 不在 Dashboard 展示 `bids_root`、`fif_path` 等服务器路径。
6. 未来最好增加 dashboard summary API，避免逐项目拉全量 datasets。

第一轮是否要改：**应该改，但先做结构和文案，不强行接入未实现 API**。

### 4.2 ProjectsPage.vue

当前状态：

1. 页面标题是“项目管理”。
2. API 使用 `projectApi.list()`、`listTrash()`、`create()`、`trash()`、`restore()`、`purge()`。
3. 卡片展示 Project ID、Data Root、数据集数量、配额、删除原因。
4. 数据集数量通过逐个 `datasetApi.list(project.id)` 统计。
5. 支持垃圾箱、恢复、永久删除。

与新规则的差异：**中到大**。

主要问题：

| 问题 | 影响 |
| --- | --- |
| 可见文案仍是项目 | 与 Study / 研究项产品定义不一致 |
| Data Root 直接展示路径 | 暴露服务器目录概念 |
| 数据集数量来自旧 datasets list | 不能表达 mounted Dataset Asset、Recording、Dataset File 的差异 |
| 永久删除文案强调清空项目文件夹 | 和“Study 不拥有 Dataset 文件”的新边界冲突 |
| 没有显示成员权限、锁、Pipeline/Run 概览 | 不像协作空间管理页 |

建议方向：

1. 页面产品名改为“研究项管理”，代码和 API 可继续用 Project 兼容。
2. Project ID 显示为“Study ID / 兼容 Project ID”。
3. 卡片从 Data Root 改为：
   - 角色 / 权限
   - 挂载 Dataset 数
   - Pipeline 数
   - 最近 Run 状态
   - 存储用量摘要
4. 删除/永久删除文案改为研究项治理语言：删除 Study 不等于删除 Dataset 原始资产；若仍有 Run/Artifact 依赖，应被阻断。
5. 数据统计最好改为 overview/summary API；短期可继续兼容旧统计，但文案不要写死“数据集 = datasets 表条数”。

第一轮是否要改：**应该改，优先改命名、字段展示和删除语义**。

### 4.3 ProjectDetailPage.vue

当前状态：

1. 页面标题是项目详情，副标题显示 `Project ID`。
2. KPI 是数据集、FIF、配额、状态。
3. 主表是当前项目的 `datasets` 上传记录。
4. 支持 mock QA / 人工确认。
5. 快捷操作包括上传数据、工作流与执行项、观察分析结果、论文出图。
6. “存储分布”仍写 `source_uploads`、`fifdata`、`derivatives`。
7. “最近活动”是静态文案：项目创建、上传写入 datasets 表、FIF 转换后更新 fif_path。

与新规则的差异：**大**。

主要问题：

| 问题 | 影响 |
| --- | --- |
| 页面还是 Project Detail，不是 Study Home | Study 的协作、挂载、Pipeline、Run、Artifact 没有形成主页 |
| 数据表混淆 Dataset 与 Recording | 用户会把每条被试/session/run 当作一个完整数据集 |
| 存储分布仍是旧目录 | 与 Dataset 标准目录、Study artifacts 分离方案冲突 |
| QA 是 mock 质控 | 可以保留，但必须清楚标为上传后初筛，不应作为 Pipeline 硬门槛 |
| 没有成员、锁、Run 队列、最近 Artifact、Activity | 协作平台的研究项视角不足 |

建议方向：

1. 页面改为“Study 研究项主页”。
2. 建议拆成 tabs 或分区：
   - 总览：角色、挂载数据、Pipeline、Run、最近活动。
   - 数据：Study mounts、Recording 列表、canonical FIF 状态、QA 摘要。
   - 工作流：Pipeline 列表、状态、版本、编辑锁。
   - 执行项：Run 列表、状态、mode、save_policy、等待人工确认。
   - 输出：Artifact current/pinned/cached、清理阻断。
   - 成员与审计：成员权限、最近行为。
3. 旧 `datasets` 表列表短期保留，但命名为“采集记录 / Recording”，不要继续叫完整 Dataset。
4. 移除或弱化 `source_uploads/fifdata` 文案，改成 `Dataset 原始资产 / canonical FIF / Study Artifact`。

第一轮是否要改：**应该改，是 Dashboard 之后最重要的页面**。

### 4.4 ImportPage.vue 与 BidsUploadPanel.vue

当前状态：

1. ImportPage 标题是“数据导入”，但目标是“项目”，文案写“系统按 Project ID 定位数据目录”。
2. `BidsUploadPanel` 支持拖拽/选择文件夹，能识别 BrainVision 三件套、EDF、BDF。
3. 上传时传 `subject/task/session/run/files` 到 `/projects/{project_id}/datasets/import`。
4. 支持同一数据位重传：弹窗写“作为新版本重新上传”，提示新增上传版本并切换当前指针。
5. 仍然以 `projectId` 为唯一上下文，没有 Dataset Asset 选择或创建。

与新规则的差异：**中**。

优点：

1. BIDS 实体识别和 BrainVision 成组逻辑是有价值的。
2. 重传版本语义已经接近 Recording Version / upload version。
3. 上传 UI 没有要求用户理解目录结构，方向比旧 Dashboard 内联上传更好。

主要问题：

| 问题 | 影响 |
| --- | --- |
| 目标仍是 Project | 用户不知道数据是进入 Dataset Asset，还是 Study 私有工作数据 |
| 不支持选择或创建 Dataset Asset | 多来源、多批次数据资产会难以组织 |
| 只暴露 subject/session/task/run | 缺少 Dataset 名称、来源、批次、伦理/可见性等资产级元信息 |
| 上传仍像同步导入 | 与 async_tasks / import task 体系还没完全对齐 |
| 文案说自动整理为 FIF 工作数据 | 需要改成 Raw BIDS 逻辑视图 + canonical FIF 更准确 |

建议方向：

1. ImportPage 继续作为真实页面保留，但文案改成“导入到研究项的 working Dataset”。
2. 增加目标选择：
   - 选择 Study。
   - 选择 Dataset Asset：新建 working Dataset / 追加到已有 Dataset。
3. 上传结果展示从“FIF 已生成”扩展为：
   - 原始上传已登记。
   - Raw BIDS 逻辑视图已登记。
   - canonical FIF 已生成或排队中。
   - dataset_files 已写入。
4. 支持导入任务进度时，再接入 async task 和 task_events。

第一轮是否要改：**应该改文案和目标概念；Dataset Asset 选择可等 API 稳定后做**。

### 4.5 PipelinePage.vue

当前状态：

1. 近期已接入很多 Pipeline/Run 新规范。
2. 已有 `expected_version` 保存、`run_mode/save_policy`、Run detail 分栏、Manifest、Lineage、Artifact pin/unpin/hide、cleanup。
3. 当前仍使用 `selectedProjectId` 和“项目与工作流”文案。
4. LoadData 面板读取当前项目 datasets，并显示“命中数据集”。
5. LoadData 面板支持“固定当前命中”和 explicit `dataset_ids`，这些值会写入 Pipeline definition。
6. Run 创建对话框目前没有提供 selection override 的独立数据选择入口。
7. 前端还没有接入 Pipeline edit lock 的获取、续期、释放和冲突展示。
8. Task events 主要是轮询/详情摘要，没有浏览器端 SSE。

与新规则的差异：**中**。

最关键的问题：

| 问题 | 影响 |
| --- | --- |
| Pipeline 仍可把 explicit `dataset_ids` 写入 definition | 与“Pipeline 不保存具体数据，Run 冻结实际输入”冲突 |
| LoadData 显示“数据集”但实际是旧 recording 列表 | 会混淆 Dataset Asset / Recording / Dataset File |
| 选择数据在 Pipeline 编辑器内完成 | 用户会把临时看数据、试跑、正式分析混在同一个 Pipeline 定义里 |
| 编辑锁 UI 未接 | 多人协作时用户不知道谁正在编辑 |
| SSE 未接 | 长任务体验仍依赖轮询 |

建议方向：

1. 将页面文案改为“Study 与工作流”。
2. LoadData 标准模式只保存 filter / mount selector。
3. “固定当前命中”不要写回 Pipeline definition，应移动到 Run 创建对话框，作为 `selection_override`。
4. LoadData 面板把旧 datasets 表展示为“采集记录”，并逐步显示 `dataset_file_id/file_role/storage_uri/logical_path` 摘要。
5. 增加 edit lock 状态条：谁持有、何时过期、是否只能查看。
6. Run detail 后续接 Task SSE；短期保留轮询。

第一轮是否要改：**只改关键语义，不要大改 LiteGraph**。其中 `explicit dataset_ids` 从 Pipeline definition 移到 Run override 是 P0/P1。

### 4.6 Index.vue

当前状态：

1. 首页仍写“项目工作台”“创建项目”“source_uploads”“fifdata”。
2. 页面导航里 `/pipeline` 仍标成“静态预览”，但当前 PipelinePage 已经核心接入。
3. 文案是旧 v1 流程：项目创建 -> 原始归档 -> fifdata -> 数据库索引。

与新规则的差异：**中**。

建议方向：

1. 首页不是核心工作台，第一轮可后置。
2. 后续统一改为 Dataset / Study / Pipeline / Run 的产品叙事。
3. 修正 Pipeline 已接入状态，不再写静态预览。
4. 去掉 `source_uploads/fifdata` 作为产品主叙事，改为 Raw BIDS / canonical FIF / Run Artifact。

第一轮是否要改：**可以晚一点，但要避免公开演示时继续误导**。

### 4.7 WorkbenchShell 与 workbenchPages.ts

当前状态：

1. `WorkbenchShell` 是大部分工作台页面的共享壳。
2. Dashboard 没有使用它，导致导航和布局重复。
3. `workbenchPages.ts` 的主导航仍是：仪表盘、项目管理、分析、观察、统计、作图、机器学习。
4. 侧栏仍有“项目列表”“数据导入”“工作流编辑器”等旧组织。
5. 预览页面标识机制是存在的。

与新规则的差异：**中**。

建议方向：

1. Dashboard 改用 `WorkbenchShell`。
2. 导航按四对象改：
   - 总览
   - 数据集
   - 研究项
   - 工作流
   - 执行项 / 运行队列
   - 观察 / 统计 / 出图 / ML 继续标预览
3. 如果短期没有独立 Dataset / Run 页面，可以先把入口指向现有 Import、ProjectDetail、Pipeline 的相应区域，但文案必须统一。
4. 未实现页面继续保留 preview badge，不要假装上线。

第一轮是否要改：**应该改共享导航文案和 Dashboard 壳，避免每页重复旧概念**。

### 4.8 类型与 API 层

当前状态：

1. `types/index.ts` 仍以 `Project`、`Dataset` 为主要类型。
2. `Project` 实际承载 Study。
3. `Dataset` 实际更像旧 `datasets` 表中的 Recording / 当前上传记录。
4. `Pipeline`、`PipelineRun`、`PipelineRunInput`、`PipelineArtifact` 类型已经比较接近新规范。
5. `api/projects.ts`、`api/datasets.ts` 仍使用 `/projects` 路径；这是当前后端兼容现实。

与新规则的差异：**中到大**。

建议方向：

1. 短期不要破坏 API wrapper，可新增类型 alias：
   - `export type Study = Project`
   - `export type Recording = Dataset`
2. UI 层逐步用 `Study` / `Recording` 命名，API 层继续用 `projectId` 兼容。
3. 新增前端类型预留：
   - `DatasetAsset`
   - `DatasetVersion`
   - `DatasetFile`
   - `StudyDatasetMount`
   - `StudyOverview`
   - `RunOverview`
4. 不再让新 UI 依赖 `source_path/fif_path/bids_root` 做事实源；这些字段只作为兼容展示或后台调试信息。

第一轮是否要改：**应该先加 alias 和新类型，降低后续页面改造成本**。

### 4.9 静态预览页面

涉及页面：

1. `IcaPage.vue`
2. `StatisticsPage.vue`
3. `FiguresPage.vue`
4. `MlPage.vue`
5. `StaticWorkbenchPage.vue`
6. `ErpPage.vue`
7. `PsdPage.vue`
8. `TfrPage.vue`
9. `ConnectivityPage.vue`
10. `MicrostatePage.vue`
11. `SourcePage.vue`

当前状态：

这些页面主要是静态预览或演示 UI。它们没有真实接入 Dataset / Study / Pipeline / Run 后端链路。

建议：**第一轮不要改业务逻辑**。

可以接受的轻量改动：

1. 保持 preview badge。
2. 如果全局导航改名导致入口文案不一致，可以轻量同步页面标题或说明。
3. 不要给这些页面接假数据选择器、假 Run 或假 Artifact 操作。

## 5. 推荐改造优先级

### P0：必须优先统一的内容

1. Dashboard 从 Project 工作台改为 Dataset / Study / Pipeline / Run 总览。
2. ProjectsPage 和 ProjectDetailPage 的用户可见文案从 Project 收敛为 Study / 研究项。
3. 不再在用户可见主界面展示 `bids_root`、`source_uploads`、`fifdata`、`fif_path` 作为产品事实。
4. PipelinePage 中 explicit 数据选择不要作为标准 Pipeline 定义保存，应迁移到 Run override。
5. 旧 `Dataset` 表记录在 UI 中改称“采集记录 / Recording”，完整数据资产才叫 Dataset。

### P1：MVP 产品体验需要尽快补齐

1. Study Detail 增加 Pipeline/Run/Artifact/Activity 概览。
2. ImportPage 增加“导入到 working Dataset Asset”的概念。
3. WorkbenchShell 和导航按四对象统一。
4. PipelinePage 增加 edit lock 状态展示。
5. Run detail 增加更清楚的 Task 事件与 waiting_user_input 提示。

### P2：等待后端或真实数据稳定后再做

1. 独立 Dataset Asset 管理页面。
2. 独立 Run 队列 / Run 历史页面。
3. Task SSE 浏览器端实时流。
4. Study activity 时间线。
5. Dataset mount 可视化管理。
6. Observe / Statistics / Figures / ML 真实接入 Run Artifact。

## 6. 推荐分步方案

### 第 1 步：前端术语兼容层

目标：不破坏接口，先降低概念混乱。

建议改动：

1. `types/index.ts` 增加 `Study = Project`、`Recording = Dataset` 等 alias。
2. `workbenchPages.ts` 把可见导航从“项目管理”改成“研究项”，把“分析”明确为“工作流”或“工作流与执行项”。
3. `WorkbenchShell` 保持 preview 标识。
4. `Index.vue` 可后置，但至少不要继续把 Pipeline 写成静态预览。

### 第 2 步：Dashboard 重构为四对象总览

目标：Dashboard 不再是 Project Detail + Upload 的混合页面。

建议改动：

1. 改用 `WorkbenchShell`。
2. 顶部 KPI：Dataset / Study / Pipeline / Run。
3. 最近区块：
   - 最近 Study
   - 最近导入/转换
   - 最近 Pipeline
   - 最近 Run / Task
4. 上传只保留入口按钮，跳转 Import。
5. 不展示服务器路径。
6. 短期可用现有 API 组装，长期补 dashboard summary API。

### 第 3 步：Study 列表和详情页收口

目标：Project 页面变成 Study 管理体验。

建议改动：

1. `ProjectsPage.vue` 改文案为研究项管理。
2. `ProjectDetailPage.vue` 改为 Study Home。
3. Dataset 表改称 Recording 列表，补“Dataset Asset / Mount”占位说明。
4. 增加 Pipeline / Run / Artifact 概览区。
5. 删除/恢复/永久删除文案按 Study 治理和依赖保护重写。

### 第 4 步：Import / Dataset 导入语义升级

目标：用户知道上传数据进入 Dataset 资产，而不是直接丢进项目目录。

建议改动：

1. ImportPage 选择 Study 后，再选择或创建 working Dataset。
2. BidsUploadPanel 上传结果显示 original upload、raw_bids、canonical_fif、dataset_files。
3. 重传文案从“作为新版本重新上传”进一步明确为 Recording Version。
4. 后续接入 async import task。

### 第 5 步：PipelinePage 数据选择边界修正

目标：Pipeline 保存规则，Run 保存事实。

建议改动：

1. LoadData 标准保存 filter / mount selector。
2. explicit 具体数据选择进入 Run 创建对话框的 `selection_override`。
3. Run 对话框显示命中输入数量和是否使用 override。
4. Run detail 中更突出 `pipeline_run_inputs`、manifest、lineage。
5. 接入 edit lock UI 和 Task SSE。

### 第 6 步：静态页面冻结策略

目标：不把未实现页面卷入第一轮重构。

建议：

1. 观察、统计、作图、机器学习、管理后台继续标记 preview。
2. 只做全局导航和标题级轻量同步。
3. 等 Run Artifact、Analysis Result、Figure Artifact 模型稳定后再接真实数据。

## 7. 需要后端配合的地方

前端可以先做很多兼容改造，但如果要体验完整，后端最好补这些 summary API：

| API 能力 | 用途 |
| --- | --- |
| Dashboard summary | 避免 Dashboard 对每个 Study 拉 datasets / pipelines / runs |
| Study overview | 一次返回 Study、Dataset mounts、Pipeline count、Run status、Artifact count |
| Dataset Asset list | 让 Import 和 Study Detail 能展示真正 Dataset 资产 |
| Study activity | Dashboard / Study Detail 展示最近谁改了什么 |
| Active locks | 显示谁正在编辑 Pipeline 或运行 Run |
| Task event stream | 支撑 Run 和导入任务实时进度 |

没有这些 API 时，前端可以先做“结构和文案收口”，但数据只能从现有 `/projects`、`/datasets`、`/pipelines`、`/runs` 拼出来，性能和准确性有限。

## 8. 当前结论

前端确实需要改，而且不是只改 `/dashboard`。最需要先改的是：

```text
Dashboard
  -> 从 Project 工作台改成四对象总览

ProjectsPage / ProjectDetailPage
  -> 从 Project 管理改成 Study 管理与 Study Home

ImportPage / BidsUploadPanel
  -> 从按 Project 上传改成导入到 working Dataset

PipelinePage
  -> 保留当前成果，但修正 explicit 数据选择写入 Pipeline definition 的问题
```

不建议第一轮改的页面：

```text
IcaPage / Observe / ERP / PSD / TFR / Connectivity / Microstate / Source
Statistics / Figures / ML / Admin
```

这些页面现在多数是静态预览，贸然改成 Dataset / Study / Pipeline / Run 的真实交互会制造新的假接口和假状态。更稳妥的路线是：先把真实工作台主线改顺，再让这些页面以后从 Run Artifact / Analysis Result 中读取真实结果。

## 14. 第 6 步 Study 详情页改造补充

复核时间：2026-05-22 11:50:53 +08:00

本次已将 `ProjectDetailPage.vue` 从旧 Project Detail + Dataset/QA 页面改为 Study 研究项主页。

补充结论：
1. Study 详情页现在按 Overview、Data、Pipelines、Runs、Artifacts、Activity 六个区块组织，不再把旧项目目录作为页面信息架构。
2. 页面用户可见文案已收口到 Study / 研究项，旧 `/projects/:id` 只作为兼容路由和 `Study ID` 标识存在。
3. Data 区块将 Dataset Mount 和 Recording 分开表达；旧 datasets list 只作为 Recording 兼容降级，不再被描述为完整 Dataset Asset。
4. 页面不再展示 `source_uploads`、`fifdata`、`derivatives`、`Project ID`、`Data Root`、`bids_root`、`source_path`、`fif_path` 等旧目录或路径字段。
5. Pipeline、Run、Artifact 当前使用现有 API 做有限摘要，不伪造后端尚未提供的完整 Study overview、activity 或文件浏览能力。
6. Activity 当前明确为已有对象时间聚合，正式审计事件仍待 `audit_events` 或 Study activity API 接入。
7. 旧 QA mock/review 操作已从 Study 主页移除；质量审核后续应回到 Dataset/Recording 详情或独立 QC 页面，而不是混在 Study 首页。
8. 移动端 Data 表格已限制在容器内横向滚动，不再造成页面级横向溢出。

验证结果：
- `npm run typecheck`：通过。
- `npm run build`：通过。
- headless Chrome 检查 `/projects/:id` 桌面视口：六个区块可见，旧路径字段未出现在页面文本中，无横向溢出。
- headless Chrome 检查 `/projects/:id` 移动视口：六个区块可见，旧路径字段未出现在页面文本中，无页面级横向溢出。

剩余差异：
1. Study 详情页仍靠多个现有接口前端聚合摘要；后端应补 `StudyOverview` summary API。
2. Dataset Mount、Recording、Artifact 的完整浏览、预览、下载还需要后续 Dataset File / Artifact API 页面接入。
3. canonical FIF 状态短期仍从旧兼容字段推断；长期应改为读取 `dataset_files.file_role=canonical_fif`。

## 9. 第 1 步基线复核补充

复核时间：2026-05-22 09:52:44 +08:00

本次按“第 1 步：建立前端 Dataset / Study / Pipeline / Run 改造基线”重新读取了路由、核心页面、类型、API 封装和 docs_v2 相关页面，未修改前端业务代码。

补充结论：

1. 当前真实主线仍是 `/dashboard`、`/projects`、`/projects/:id`、`/import`、`/pipeline`；观察、ICA、统计、作图、机器学习、管理后台仍应按预览页处理。
2. `Dashboard.vue`、`ProjectsPage.vue`、`ProjectDetailPage.vue`、`ImportPage.vue` 仍明显 Project-centric，且多处展示 `bids_root`、`source_uploads`、`fifdata`、`fif_path` 等旧文件口径。
3. `BidsUploadPanel.vue` 的上传分组和重传确认能力可复用，但前端语义仍是“上传到项目”，不是“导入到 working Dataset / Dataset Asset”。
4. `PipelinePage.vue` 已有较多 Run 新能力：`expected_version`、`run_mode`、`save_policy`、Run detail、Manifest、Lineage、Artifact 语义操作等。
5. `PipelinePage.vue` 仍存在最关键的不一致：LoadData explicit 选择会把 `dataset_ids` 写回 Pipeline definition，Run 创建 payload 目前没有携带 `selection_override`。因此“Pipeline 保存规则，Run 保存事实”尚未在前端闭环。
6. `types/index.ts` 已有较新的 Run / Task / Artifact 类型，但缺少 `Study`、`Recording`、`DatasetAsset`、`DatasetFile` 等前端语义别名；`api/*.ts` 仍以 `projectApi` / `datasetApi` 为主。
7. docs_v2 中 Pipeline/Run 标准口径已经较新，其中关于 `selection_override` 的描述比当前前端实现更超前，后续应通过第 8 步修正前端，而不是降低规范。

验证结果：

- `npm run typecheck`：通过。
- `npm run build`：通过。
- 构建警告：Vite CJS API 弃用、`litegraph.js` 使用 `eval`、`PipelinePage` chunk 超过 500 kB。

## 10. 第 2 步语义兼容层补充

复核时间：2026-05-22 09:59:16 +08:00

本次已在前端建立四对象语义兼容层，旧页面未切换调用，因此不改变当前用户界面和业务行为。

补充结论：

1. `types/index.ts` 已新增 `Study`、`Recording`、`DatasetAsset`、`DatasetFile`、`StudyDatasetMount`、`StudyOverview`、`RunManifestSummary` 等类型；旧 `Project`、`Dataset` 仍保留。
2. `ProjectMember.can_run` 已作为可选字段接入，便于后续 Study 页面显示运行权限。
3. 旧 `Dataset` 增加可选 `dataset_asset_id`，用于兼容旧采集记录与新 Dataset Asset 的关系。
4. `api/studies.ts` 新增 `studyApi`，内部仍走 `/projects` 与 `projectApi`，列表响应映射为 `{ studies }`。
5. `api/datasetAssets.ts` 新增 `datasetAssetApi`、`studyDatasetMountApi`、`recordingApi`、`datasetFileApi`，后续页面可以逐步改用这些语义化 API。
6. 当前 Dashboard、ProjectsPage、ProjectDetailPage、ImportPage、PipelinePage 尚未迁移到新 API 包装层；因此功能差异仍存在，但第 3 步之后可以按页面逐个替换。

验证结果：

- `npm run typecheck`：通过。
- `npm run build`：通过。
- 构建警告与第 1 步一致，未新增阻断问题。

## 11. 第 3 步导航命名补充

复核时间：2026-05-22 10:05:56 +08:00

本次已把前端全局导航和首页入口先收口到 Dataset / Study / Pipeline / Run 主线，未新增任何假业务逻辑。

补充结论：

1. `workbenchPages.ts` 顶部导航已改为“工作台 / 数据集 / 研究项 / 工作流 / 执行项”，观察、统计、作图、机器学习仍为 preview。
2. `workbenchPages.ts` 侧栏已把真实主线集中到“四对象主线”，包含工作台总览、Dataset 导入、Study 研究项、Pipeline / Run。
3. Pipeline 入口已从首页和导航中移出“静态预览”语义，符合当前已有工作流编辑、Run 创建、Run detail、Artifact 和 Manifest 的实际状态。
4. 管理面板预览不再展示 `/mnt/elys_data/projects`、`source_uploads`、`fifdata` 等服务器目录口径，改为 Dataset assets / Study artifacts / Run manifests。
5. `router/index.ts` 已增加 `/studies`、`/studies/:id`、`/datasets` alias，同时保留 `/projects`、`/projects/:id`、`/import` 旧路径兼容。
6. `Index.vue` 推荐路径和站点地图已改为 Study、Dataset、Pipeline、Run；`ImportPage.vue` 导航高亮改到数据集。
7. 当前仍未改 `Dashboard.vue`、`ProjectsPage.vue`、`ProjectDetailPage.vue` 页面主体，因此页面内部 Project-centric 问题仍留给第 4、5、6 步。

验证结果：

- `npm run typecheck`：通过。
- `npm run build`：通过。
- 构建警告与前两步一致，未新增阻断问题。

## 12. 第 4 步 Dashboard 改造补充

复核时间：2026-05-22 10:40:36 +08:00

本次已把 `Dashboard.vue` 从旧 Project 工作台重构为 Dataset / Study / Pipeline / Run 四对象总览。

补充结论：

1. Dashboard 已复用 `WorkbenchShell`，不再维护独立 topbar/sidebar。
2. 首屏 KPI 已改为 Dataset 数据集、Study 研究项、Pipeline 工作流、Run 执行项。
3. Dashboard 已移除完整上传流程和 `BidsUploadPanel`，上传只作为跳转到 `/datasets` 的快捷入口。
4. Dashboard 不再把 `bids_root`、`source_path`、`fif_path`、`Project ID`、`Data Root` 作为主要展示信息。
5. 数据读取从“所有 Study 逐个读取完整 datasets”改为有限摘要：Study 列表、Dataset Asset 列表、最近 3 个 Study 的 Pipeline 摘要和少量 Run 摘要。
6. 最近活动当前由前端聚合 Study、Dataset Asset、Pipeline、Run 更新时间生成，还不是正式 audit_events。
7. Dashboard 的用户心智已从“项目目录 + 上传”切换为“四对象总览 + 快捷入口”，但 Study 列表页和 Study 详情页仍需第 5、6 步继续收口。

验证结果：

- `npm run typecheck`：通过。
- `npm run build`：通过。
- 浏览器检查 `/dashboard` 桌面视口：四对象 KPI 可见，无上传 input，无旧路径字段，无横向溢出。
- 浏览器检查 `/dashboard` 390px 移动视口：主要区块可读，无横向溢出。

## 13. 第 5 步 Study 列表页改造补充

复核时间：2026-05-22 11:15:30 +08:00

本次已把 `ProjectsPage.vue` 从旧项目管理页收口为 Study 研究项列表。

补充结论：

1. 页面用户可见标题、标签页、创建弹窗、空态和治理操作已改为 Study / 研究项语义。
2. 页面代码主入口改为 `studyApi` 和 `Study` 类型，仍兼容后端既有 `/projects` 路径。
3. Study 卡片不再展示 `Data Root`、`bids_root`、`Project ID` 等旧目录或路径字段；保留 `Study ID` 作为业务标识。
4. Study 卡片新增成员角色、成员权限、最近活动、Recording、Pipeline、Run、运行中数量等概况。
5. 数据概况当前仍使用旧 datasets list 兼容统计，因此文案改为 Recording / 采集记录，不再把旧 datasets 表条目直接称为完整 Dataset Asset。
6. Pipeline / Run 概况通过现有 Pipeline API 做有限摘要，避免对所有 Study 做深度 N+1。
7. 回收站、恢复、清理操作已改为 Study 治理语义；危险操作说明已强调 Dataset 原始资产不应随 Study 清理物理删除，存在 Run / Artifact 依赖时应由后端阻断。
8. 当前差异重点转移到 `ProjectDetailPage.vue`：列表页已收口，但详情页仍是旧 Project Detail，需要第 6 步继续处理。

验证结果：

- `npm run typecheck`：通过。
- `npm run build`：通过。
- 浏览器检查 `/projects` 桌面视口：Study 卡片、成员权限、Recording/Pipeline/Run 摘要可见，无旧路径字段，无横向溢出。
- 浏览器检查 `/projects` 390px 移动视口：卡片和摘要区可读，无横向溢出。
