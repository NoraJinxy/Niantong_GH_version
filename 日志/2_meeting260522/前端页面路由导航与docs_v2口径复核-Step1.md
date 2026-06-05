# 前端页面路由导航与 docs_v2 口径复核 Step 1

文档生成时间：2026-05-22 22:02:32 +08:00

## 1. 本次复核范围

本次只做前端页面、路由、导航和 `docs_v2` 口径复核，不修改业务代码。

读取范围：

1. `elys_version1/frontend/elys-web/src/router/index.ts`
2. `elys_version1/frontend/elys-web/src/data/workbenchPages.ts`
3. `elys_version1/frontend/elys-web/src/views/Dashboard.vue`
4. `elys_version1/frontend/elys-web/src/views/ProjectsPage.vue`
5. `elys_version1/frontend/elys-web/src/views/ProjectDetailPage.vue`
6. `elys_version1/frontend/elys-web/src/views/ImportPage.vue`
7. `elys_version1/frontend/elys-web/src/components/BidsUploadPanel.vue`
8. `elys_version1/frontend/elys-web/src/views/PipelinePage.vue`
9. `elys_version1/frontend/elys-web/src/views/StaticWorkbenchPage.vue`
10. `wiki/docs_v2/6-00-前端页面总览.md`

## 2. 当前页面和职责

| 页面类别 | 路由 | 组件 | 当前职责 | 当前状态 |
|---|---|---|---|---|
| 展示入口 | `/` | `Index.vue` | 未登录展示页 | 展示页 |
| 登录 | `/login` | `Login.vue` | 登录、认证态恢复、登录后跳转 | 已接后端 |
| 工作台 | `/dashboard` | `Dashboard.vue` | Dataset / Study / Pipeline / Run 四对象摘要、最近 Study、快捷入口 | 已接后端，口径基本正确 |
| Study 列表 | `/studies`，兼容 `/projects` | `ProjectsPage.vue` | Study 创建、列表、回收站治理、有限摘要 | 已接后端，底层仍用 Project API |
| Study 主页 | `/studies/:id`，兼容 `/projects/:id` | `ProjectDetailPage.vue` | Study 概览、Dataset mounts、Recordings、Pipelines、Runs、Artifacts 摘要 | 已接后端，仍有 legacy Dataset/Recording 兼容 |
| Dataset 导入 | `/import`，alias `/datasets` | `ImportPage.vue` + `BidsUploadPanel.vue` | 准备 Dataset Asset，系统生成配套 Study/mount，上传 BrainVision/EDF/BDF 到 Dataset working version | 已接主链路，真实大文件 staging 仍待验收 |
| Pipeline / Run | `/pipeline` | `PipelinePage.vue` | Pipeline 编辑、LoadData、Run 创建、Run detail、Artifact、Manifest、Lineage | 核心接入，部分执行器和真实任务验收待补 |
| ICA 审核 | `/ica` | `IcaPage.vue` | 预处理审核静态体验 | 预览 |
| 观察入口 | `/observe` | `StaticWorkbenchPage.vue` | 观察模块静态导航 | 预览 |
| ERP / PSD / TFR / Connectivity / Microstate / Source | `/observe/*` | 对应观察页 | 各类结果观察静态页 | 预览 |
| 统计 | `/statistics` | `StatisticsPage.vue` | 统计配置和结果示意 | 预览 |
| 作图 | `/figures` | `FiguresPage.vue` | 论文出图示意 | 预览 |
| 机器学习 | `/ml` | `MlPage.vue` | ML 工作台示意 | 预览 |
| 管理 | `/admin` | `StaticWorkbenchPage.vue` | 存储、计算、用户、审计静态管理入口 | 预览 |

## 3. 导航当前口径

顶部导航：

| key | 文案 | 路由 | 状态 |
|---|---|---|---|
| `dashboard` | 工作台 | `/dashboard` | live |
| `datasets` | 数据集 | `/import` | live |
| `projects` | 研究项 | `/studies` | live |
| `analysis` | 工作流 | `/pipeline` | live |
| `observe` | 观察 | `/observe` | preview |
| `stats` | 统计 | `/statistics` | preview |
| `figure` | 作图 | `/figures` | preview |
| `ai` | 机器学习 | `/ml` | preview |

侧栏导航：

| 分组 | 入口 | 状态 |
|---|---|---|
| 四对象主线 | 工作台总览、Dataset 导入、Study 研究项、Pipeline / Run | live |
| 预处理与分析预览 | ICA、统计、机器学习、管理面板 | preview |
| 观察与出图 | 观察入口、ERP、PSD、TFR、脑网络、微状态、溯源、作图 | preview |

判断：导航已经基本符合四对象主线；`datasets` 顶部入口实际跳 `/import`，router 再用 alias 支持 `/datasets`，这可用，但文档里应把 `/datasets` alias 明写出来。

## 4. docs_v2/6-00 当前口径判断

`docs_v2/6-00-前端页面总览.md` 已经记录：

- `BidsUploadPanel` 是 Dataset-first 上传组件。
- `ImportPage.vue` 已接 `datasetAssetApi.bootstrap()` 自动创建配套 Study 和 mount。
- `/datasets?study_id=...` 或 `?project_id=...` 作为 Study-first 快捷入口保留。
- PipelinePage 已接 `expected_version`、`run_mode`、`save_policy`、LoadData mount 展示、Run detail、Artifact、Manifest、Lineage。
- 观察、统计、作图、机器学习、管理后台多数仍是静态预览。

需要修正或补充的口径：

1. 路由表仍把 `/import` 状态写成“Study-first 兼容接入”，现在应改成“Dataset-first 导入主线，Study-first URL 快捷兼容”。
2. 路由分组和路由总表没有单独显式写 `/datasets` alias，用户和文档更常用 `/datasets`，建议补充。
3. API 客户端表里 `api/projects.ts` 后端能力仍写“项目管理”，建议改成“Study 研究项 / Project 兼容 API”。
4. 工作台导航表仍写“仪表盘、项目管理、分析”，建议统一成“工作台、数据集、研究项、工作流”等当前 nav 文案。
5. 相关页面中出现 `8-00 功能模块总览`，但 `docs_v2` 当前主目录是 0-7 结构时需要确认该页是否实际存在，避免死链。

## 5. 根据项目需求应该有的页面

| 产品对象/功能 | 应有入口 | 当前是否具备 | 说明 |
|---|---|---|---|
| Dashboard 总览 | `/dashboard` | 已具备 | 应继续只做摘要和入口，不承载完整上传或执行编辑 |
| Dataset 资产列表 | `/datasets` | 部分具备 | 当前 `/datasets` 是导入页，缺少独立的 Dataset Asset 列表、版本、状态、可见性、归档治理 |
| Dataset 导入 | `/datasets/import` 或当前 `/datasets` | 已具备主链路 | 当前导入页可继续作为 MVP 入口，后续可从资产列表拆出导入子页 |
| Study 列表 | `/studies` | 已具备 | 已统一 Study 口径，底层 Project API 兼容 |
| Study 主页 | `/studies/:id` | 已具备 | 需要继续补 Dataset mount 详情、Recording versions/files 详情 |
| Pipeline 列表/编辑 | `/pipeline` | 已具备 | 当前单页承担列表、编辑、Run detail，MVP 可接受 |
| Run 列表/队列 | `/runs` 或 Study 内 Run tab | 部分具备 | 目前 Run 主要在 PipelinePage 和 Study 主页摘要中出现，缺少跨 Study Run 队列页 |
| Artifact / 结果库 | `/artifacts` 或 Study 输出 tab | 部分具备 | 目前在 PipelinePage Run detail 和 Study 摘要中出现，缺少统一结果库 |
| 预处理审核 | `/ica` | 预览 | 未来应从 Run Artifact 或 Dataset canonical FIF 进入 |
| 观察/统计/作图/ML | `/observe/*`、`/statistics`、`/figures`、`/ml` | 预览 | 当前应继续保持预览标识 |
| 管理后台 | `/admin` | 预览 | 后续接用户、存储、队列、审计 |

## 6. 不一致点

| 优先级 | 不一致点 | 当前表现 | 影响 | 建议 |
|---|---|---|---|---|
| P0 | `docs_v2/6-00` 中 `/import` 状态仍写 Study-first | 实际页面已是 Dataset-first 主线，只保留 Study-first URL 快捷兼容 | 文档落后，后续协作会误判导入页状态 | 更新为 Dataset-first 主线 |
| P0 | `/datasets` alias 未在 `docs_v2/6-00` 路由表显式列出 | router 有 alias，但文档只列 `/import` | 用户当前访问的是 `/datasets`，文档入口不直观 | 路由表写 `/import`、`/datasets` |
| P1 | Dataset 页面同时承担资产创建和导入，缺少资产列表视角 | 当前可创建/选择 Dataset Asset，但没有资产列表、版本、归档页 | Dataset-first 资产治理不完整 | 后续新增 Dataset Asset 管理区或拆子路由 |
| P1 | Run 缺少跨 Study 队列入口 | Run 主要挂在 PipelinePage 最近 Run 和 Study 摘要 | 多任务运行时不便统一追踪 | 后续补 `/runs` 或 Dashboard 队列摘要 API |
| P1 | Artifact 缺少统一结果库 | Artifact 在 Run detail 和 Study 摘要里出现 | 结果复查、下载、固定、清理不够集中 | 后续补 Study 输出页或 `/artifacts` |
| P1 | `Project` 兼容命名仍散落在代码/API 文档 | router alias 和 API 文件仍是 projects | 代码层可接受，但文档要明确兼容语义 | 文档统一写 Study / Project 兼容 |
| P2 | 预览页面的真实数据入口尚未建立 | 观察、统计、作图、ML 多为静态页面 | 用户可能期待真实结果联动 | 保留预览标识，未来从 Run Artifact 进入 |
| P2 | `docs_v2/6-00` 工作台导航表文案偏旧 | 写“项目管理、分析”等旧口径 | 轻微文档不一致 | 改成当前 nav 文案 |

## 7. 优先改进点

### 7.1 近期必须先做

1. 更新 `docs_v2/6-00`：把 `/import` 状态从“Study-first 兼容接入”改成“Dataset-first 主线，Study-first URL 快捷兼容”。
2. 在 `docs_v2/6-00` 路由表显式列出 `/datasets` alias。
3. 继续验证 `/datasets` 真实登录态下的 bootstrap + 上传导入完整流程。
4. 对导入页补错误边界：Dataset code 冲突、自动 Study code 冲突、mount_name 冲突、权限不足、上传失败。

### 7.2 下一阶段建议

1. 新增或拆分 Dataset Asset 管理视图：资产列表、working/active version、状态、可见性、归档、mount 使用情况。
2. 增加 Run 队列/历史统一入口：跨 Study 查看 queued/running/waiting/failed/completed。
3. 增加 Artifact 结果库入口：按 Study、Run、类型、retention 状态筛选，支持固定、隐藏、下载、清理。
4. Study 主页补齐 Recording versions/files 详情，尤其是 mounted 外部 Dataset 的版本与文件可见性。
5. 预览页面后续从 Run Artifact 或 Dataset File 进入，避免直接伪造数据源。

## 8. 本 Step 结论

当前前端整体已经从旧 Project 工作台明显收敛到 Dataset / Study / Pipeline / Run 四对象主线；Dashboard、Study 列表、Study 主页、Dataset 导入、Pipeline/Run 的页面职责基本清楚。主要问题不再是“页面全错”，而是：

1. `docs_v2/6-00` 有几处状态和路由 alias 落后于当前实现。
2. Dataset Asset、Run、Artifact 还缺独立治理入口，目前依赖导入页、PipelinePage 和 Study 主页摘要承载。
3. 预览页面应继续保持预览语义，等真实 Run Artifact / Dataset File 数据链路稳定后再接入。

本 Step 未修改业务代码。

