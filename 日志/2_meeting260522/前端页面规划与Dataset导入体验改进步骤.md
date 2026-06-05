# 前端页面规划与 Dataset 导入体验改进步骤

文档生成时间：2026-05-22 18:48:28 +08:00

## 1. 本次问题

`/datasets` 已经按 Dataset-first 创建 Dataset、配套 Study 和 mount，但上传导入组件只在创建成功后才渲染。用户进入页面时只看到“创建 Dataset”表单，原来已经完成的 BrainVision / EDF / BDF 导入能力被折叠到了后续状态里，容易误解为“导入数据功能没了”。

本次先做规划，再按规划改进。原则是：不推翻已完成的 Dataset-first 后端主链路；前端要把“准备 Dataset 目标”和“上传原始 EEG 数据”作为同一条连续流程展示出来。

## 2. 当前前端页面有哪些

| 路由 | 组件 | 当前状态 | 说明 |
|---|---|---|---|
| `/` | `Index.vue` | 展示页 | 未登录入口 |
| `/login` | `Login.vue` | 已接后端 | 登录与 token 恢复 |
| `/dashboard` | `Dashboard.vue` | 已接后端 | 四对象总览：Dataset / Study / Pipeline / Run |
| `/studies`、`/projects` | `ProjectsPage.vue` | 已接后端 | Study 研究项列表、创建、回收站治理 |
| `/studies/:id`、`/projects/:id` | `ProjectDetailPage.vue` | 已接后端 | Study 主页，展示 mounts、Recordings、Pipelines、Runs、Artifacts 摘要 |
| `/import`、`/datasets` | `ImportPage.vue` | 部分不一致 | Dataset-first 创建已接入，但上传导入初始态不可见 |
| `/pipeline` | `PipelinePage.vue` | 核心接入 | Pipeline 编辑、LoadData、Run 创建、Run detail、Artifact、Manifest、Lineage |
| `/ica` | `IcaPage.vue` | 预览 | 静态预处理审核页 |
| `/observe` | `StaticWorkbenchPage.vue` | 预览 | 观察入口 |
| `/observe/erp` | `ErpPage.vue` | 预览 | ERP 观察 |
| `/observe/psd` | `PsdPage.vue` | 预览 | PSD 观察 |
| `/observe/tfr` | `TfrPage.vue` | 预览 | TFR 观察 |
| `/observe/connectivity` | `ConnectivityPage.vue` | 预览 | 脑网络观察 |
| `/observe/microstate` | `MicrostatePage.vue` | 预览 | 微状态观察 |
| `/observe/source` | `SourcePage.vue` | 预览 | 溯源观察 |
| `/statistics` | `StatisticsPage.vue` | 预览 | 统计分析配置与结果示意 |
| `/figures` | `FiguresPage.vue` | 预览 | 论文出图 |
| `/ml` | `MlPage.vue` | 预览 | 机器学习 |
| `/admin` | `StaticWorkbenchPage.vue` | 预览 | 管理面板 |

## 3. 根据项目需求和使用逻辑应该有哪些

| 功能域 | 应有页面/入口 | 使用逻辑 |
|---|---|---|
| 工作台总览 | `/dashboard` | 汇总 Dataset、Study、Pipeline、Run 的近期状态和下一步入口 |
| Dataset 资产与导入 | `/datasets` 或 `/import` | 用户先创建或选择 Dataset，系统自动生成配套 Study，然后立刻上传 EEG 原始数据 |
| Study 研究项 | `/studies`、`/studies/:id` | Study 是协作空间，引用 Dataset，管理成员、设置、Pipeline、Run、Artifact |
| Pipeline / Run | `/pipeline` | Pipeline 定义处理流程；Run 冻结一次执行的输入、定义、任务和输出 |
| 预处理与观察 | `/ica`、`/observe/*` | 未来应从 Run Artifact 或 Dataset 文件进入，当前可保留预览标识 |
| 输出分析 | `/statistics`、`/figures`、`/ml` | 未来接 Run Artifact / 结果表，当前不要伪装成真实后端能力 |
| 管理 | `/admin` | 后续接资源、队列、用户、审计，当前保持预览 |

## 4. 不一致的地方

| 不一致 | 当前表现 | 影响 |
|---|---|---|
| Dataset 导入页主流程断开 | 只有创建或挂载目标后才出现 `BidsUploadPanel` | 用户会以为原来的上传导入功能被删掉 |
| 页面没有明确步骤 | 创建目标、挂载状态、上传区域是条件渲染 | 用户不知道创建 Dataset 后下一步是什么 |
| `/datasets` 初始态缺少导入入口 | 未创建目标时显示“请先准备 Dataset 导入目标”空态 | 已完成的 BrainVision / EDF / BDF 分组能力不可见 |
| 自动生成配套 Study 的口径不够直观 | Study 不再让用户选择，但页面没有展示“准备目标后即可上传”的主线 | Dataset-first 和导入功能被拆成两个心理任务 |
| 预览页面与真实页面状态差异需要持续维护 | 观察、统计、作图、ML 多数为静态预览 | 后续应保持“预览”标识，避免误导 |

## 5. 改进方向

1. `/datasets` 改成明确的两阶段页面：步骤 1 准备 Dataset 目标，步骤 2 上传 EEG 原始数据。
2. `BidsUploadPanel` 在页面初始态就显示，允许用户先选择文件；没有 Dataset target 时只禁用最终“导入”按钮。
3. 创建 Dataset bootstrap 成功后自动滚动到上传区域，并显示 Dataset Asset ID、Study ID、mount_name。
4. 保留 BrainVision 三件套、EDF、BDF、重复 Recording 新版本导入、进度条和导入结果摘要。
5. 后续把 Dashboard、Study、Pipeline 的状态文档继续和 `docs_v2/6-00`、当天日志保持同步。

## 6. 分步 Codex 提示词

### 第1步：前端页面和产品口径复核

```text
第1步：请复核当前前端页面、路由、导航和 docs_v2 前端页面口径。重点确认 Dashboard、Study 列表、Study 主页、Dataset 导入、Pipeline/Run、预览页面分别承担什么职责；列出当前页面、项目需求下应该有的页面、不一致点和优先改进点。不要先改业务代码，先把规划写入日志\2_meeting260522中的 md 文档，并标注文档生成时间精确到秒。完成后同步更新日志\2_meeting260522中的文档
```

### 第2步：恢复 Dataset 导入页的上传主功能可见性

```text
第2步：请改进 frontend/elys-web/src/views/ImportPage.vue，让 /datasets 页面明确展示“步骤 1：准备 Dataset 目标”和“步骤 2：上传 EEG 原始数据”。BidsUploadPanel 不应只在 bootstrap 成功后才出现；初始态也应展示上传区域，允许用户先选择 BrainVision/EDF/BDF 文件，但在缺少 Dataset Asset ID、Study ID、mount_name 时禁止最终提交。Dataset bootstrap 成功后把 next_upload 上下文传给 BidsUploadPanel，并自动滚动到上传区域。保留 /datasets?study_id= 或 ?project_id= 快捷入口兼容。完成后运行 npm run typecheck、npm run build，并用浏览器检查 /datasets。完成后同步更新日志\2_meeting260522中的文档
```

### 第3步：优化上传组件的缺目标状态

```text
第3步：请改进 BidsUploadPanel.vue 的缺目标状态。组件在没有 Dataset target 时仍可分组选择文件，但应清楚显示“先准备 Dataset 目标后再提交导入”，选择数据/选择文件夹按钮可用，最终导入按钮禁用；一旦父组件传入 studyId、datasetAssetId、mountName，应自动进入可上传状态，不丢失已选择的文件组。保留重复 Recording 新版本确认、进度条、错误处理和 original upload / Raw BIDS / canonical FIF / dataset_files 摘要。完成后运行 npm run typecheck、npm run build，并用浏览器检查 /datasets 初始态和目标准备后的状态。完成后同步更新日志\2_meeting260522中的文档
```

### 第4步：前端页面一致性回归与后续任务整理

```text
第4步：请做前端页面一致性回归。检查 /dashboard、/studies、/studies/:id、/datasets、/pipeline 的可见文案是否符合 Dataset / Study / Pipeline / Run 四对象逻辑；检查预览页面是否仍有预览标识；如只发现文档或轻量文案问题，做最小修正。运行 npm run typecheck、npm run build；如同步 docs_v2，则运行 mkdocs build --clean。最后在日志中记录已改进、未改进、下一步建议。完成后同步更新日志\2_meeting260522中的文档
```

## 7. 本轮执行记录

### 第1步执行记录

- 状态：已完成。
- 执行时间：2026-05-22 18:48:28 +08:00。
- 已读取：`frontend/elys-web/src/router/index.ts`、`frontend/elys-web/src/data/workbenchPages.ts`、`ImportPage.vue`、`BidsUploadPanel.vue`、`ProjectsPage.vue`、`ProjectDetailPage.vue`、`PipelinePage.vue`、`wiki/docs_v2/6-00-前端页面总览.md` 和既有当天日志。
- 初步结论：真实页面主线已经基本收敛到四对象，当前最急的体验问题是 `/datasets` 初始态没有直接展示上传导入组件。

补充复核：

- 执行时间：2026-05-22 22:02:32 +08:00。
- 已按“第1步”单独生成详细复核文档：`日志/2_meeting260522/前端页面路由导航与docs_v2口径复核-Step1.md`。
- 补充结论：Dashboard、Study 列表、Study 主页、Dataset 导入、Pipeline/Run 和预览页面职责基本清楚；当前优先不一致点是 `docs_v2/6-00` 的 `/import` 状态仍偏旧、未显式列 `/datasets` alias，以及未来缺 Dataset Asset 管理、Run 队列和 Artifact 结果库独立入口。

### 第2步执行记录

- 状态：已完成。
- 执行时间：2026-05-22 18:51:39 +08:00。
- 实际改动：
  - 更新 `elys_version1/frontend/elys-web/src/views/ImportPage.vue`。
  - 把目标准备卡片标题改成“步骤 1：准备 Dataset 目标”。
  - 移除 `BidsUploadPanel` 的 `v-if="uploadContext"` 条件渲染，改为页面初始态就显示上传组件。
  - 未准备 Dataset target 时，给上传组件传空 `studyId`、`datasetAssetId`、`mountName`；准备完成后传入 `next_upload` 上下文。
  - Dataset bootstrap 或挂载成功后，自动滚动到上传区域。
- 保留兼容：
  - `/datasets?study_id=...` 和 `?project_id=...` 快捷入口仍按已有 Study 兼容。
  - 已有 Dataset Asset 挂载逻辑仍保留。

### 第3步执行记录

- 状态：已完成。
- 执行时间：2026-05-22 18:51:39 +08:00。
- 实际改动：
  - 更新 `elys_version1/frontend/elys-web/src/components/BidsUploadPanel.vue`。
  - 标题改为“步骤 2：导入到 Dataset working 版本”。
  - 没有 Dataset target 时，上传区显示“可先选择数据，准备 Dataset 目标后提交”。
  - 文件选择和文件夹选择按钮保持可用，最终“导入 N 组数据”按钮继续由 `hasUploadTarget` 控制。
  - Dataset target 就绪后，如果此前因为缺目标产生错误提示，会自动清理该提示，不丢失已选择的文件组。
- 保留能力：
  - BrainVision 三件套分组、EDF/BDF 单文件导入、重复 Recording 新版本确认、进度条和导入结果摘要均未删除。

### 第4步执行记录

- 状态：已完成。
- 执行时间：2026-05-22 18:51:39 +08:00。
- 文档同步：
  - 更新 `wiki/docs_v2/6-00-前端页面总览.md`，说明 `/datasets` 现在是两阶段体验，上传组件初始态可见。
  - 更新 `wiki/docs_v2/0-50-变更记录.md`，新增 Dataset 导入页上传体验修正记录。
- 验证结果：
  - `cd elys_version1/frontend/elys-web; npm run typecheck`：通过。
  - `cd elys_version1/frontend/elys-web; npm run build`：通过；仍有既有 Vite CJS、LiteGraph eval 和 chunk size warning。
  - 浏览器检查 `http://127.0.0.1:63241/datasets`：页面包含“步骤 1：准备 Dataset 目标”“步骤 2：导入到 Dataset working 版本”“选择数据”“选择文件夹”；不再包含“使用已有 Study / 自动创建配套 Study”的 Study 模式选择。
  - `cd wiki; mkdocs build --clean`：通过；仍有 Material for MkDocs 关于 MkDocs 2.0 的既有提示。

## 8. 本轮结论

本轮已经把 `/datasets` 从“只看到创建 Dataset”修正为“准备目标 + 上传导入”的连续流程。用户进入页面后能直接看到原来已经完成的上传导入能力；可以先选文件，等 Dataset Asset、配套 Study 和 `mount_name` 准备好后再提交。

后续建议：

1. 做一次真实登录态下的 Dataset bootstrap + 小文件上传联调，确认后端返回的 `next_upload` 能在浏览器里完整驱动导入。
2. 继续推进 staged upload + 后台任务进度，把当前同步 multipart 上传升级为更适合大文件的异步导入。
3. 在 Study 主页增加“从此 Study 继续导入到已有 Dataset / 新 Dataset”的更明确入口，减少用户在 Study 和 Dataset 页面之间来回判断。
