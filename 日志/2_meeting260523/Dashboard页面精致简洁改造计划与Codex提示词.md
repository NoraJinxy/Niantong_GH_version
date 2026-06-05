# Dashboard 页面精致简洁改造计划与 Codex 提示词

文档生成时间：2026-05-23 00:37:55 +08:00

## 1. 本文目标

本文基于当前 `elys_version1/frontend/elys-web/src/views/Dashboard.vue` 的实现，结合“数据处理功能性网站需要简洁、精致、优雅、高效”的目标，完成四件事：

1. 分析现有 Dashboard 页面的功能性和信息架构。
2. 对比当前实现与目标要求之间的差距。
3. 制定分阶段修改计划，让页面信息明确、交互高效、视觉克制。
4. 为每个修改步骤提供可直接给 Codex 执行的提示词。

Dashboard 的最终方向不是“卡片更多、效果更炫”，而是让用户更快判断当前工作状态，并用最短路径进入下一步。

## 2. 当前 Dashboard 页面分析

当前 Dashboard 已经从旧的 Project 工作台收敛为 Dataset / Study / Pipeline / Run 四对象工作台，整体方向比早期版本更正确。

### 2.1 当前已有优点

1. 页面已经复用 `WorkbenchShell`，顶栏和工作台导航保持统一。
2. 已移除顶部 `Dataset / Study / Pipeline / Run` 提示词。
3. 已移除“这里显示四个核心对象的有限摘要和下一步入口”这类开发说明。
4. 已移除独立“快捷入口”卡，避免与顶栏和右上按钮重复。
5. 已移除 Dataset / Pipeline / Run 的对象解释卡。
6. 已移除“当前摘要策略”这类开发自述。
7. 首屏保留四对象摘要卡，用户能快速看到 Dataset、Study、Pipeline、Run 的数量状态。
8. 主体区域已包含最近 Study 和活动中的 Run。
9. 活动中的 Run 已支持展开 / 收起。
10. 最近活动已经按对象类型聚合显示。

### 2.2 当前主要问题

当前页面虽然已经变得干净，但仍存在一些“功能工作台还不够精致高效”的问题：

1. 四对象摘要卡仍偏“统计展示”，没有突出异常和下一步判断。
2. Run 摘要只显示 `activeRuns.length` 和 completed 数，不区分 waiting_user_input、failed、running、queued 的优先级。
3. 活动 Run 当前只纳入 `queued/running/waiting_user_input/pending`，失败 Run 可能不够突出。
4. 活动 Run 点击只进入 `/pipeline`，不能定位到具体 Run。
5. 最近 Study 的 Pipeline / Run 指标来自有限前端聚合，容易让用户误以为是全量统计。
6. 最近活动由前端拼接，不是真正审计事件或业务事件流。
7. 顶部右侧按钮固定为“导入 Dataset”和“新建 Study”，没有根据用户当前数据状态动态调整主按钮。
8. 空态文案仍比较普通，没有明确引导“先导入数据、再创建 Pipeline、再发起 Run”的最短路径。
9. 视觉上四张摘要卡较大，移动端首屏被摘要卡占满，最近 Study 和活动 Run 下沉。
10. `Pipeline 工作流` 卡片文案“3 个 Study 已抽取”仍带有实现痕迹，不够用户化。
11. 警告区域直接显示接口降级信息，后续需要压缩成不打扰主流程的轻提示。
12. 页面没有统一的“需要处理”聚合，例如等待确认、失败、导入异常应比普通数字更醒目。

## 3. 目标要求对比

| 维度 | 当前状态 | 目标要求 | 差距 |
| --- | --- | --- | --- |
| 页面定位 | 四对象摘要工作台 | 数据处理状态入口和工作恢复入口 | 已基本对齐，但还需突出异常和下一步 |
| 信息密度 | 已去掉冗余解释，但卡片仍占空间 | 信息少但有判断力 | 需要减少实现口径，增加用户决策口径 |
| 视觉气质 | 清爽但略普通 | 简洁、精致、优雅 | 需要更克制的间距、卡片层级、状态表达 |
| 效率 | 可进入 Dataset / Study / Pipeline | 快速恢复最近工作和处理运行异常 | Run 定位、异常排序、动态 CTA 仍不足 |
| 数据准确性 | 前端有限聚合 | 后端 summary 统一口径 | 需要 Dashboard Summary API |
| 交互 | 点击卡片和行进入对应页面 | 点击后定位到具体对象和具体任务 | Run 详情跳转还不够直接 |
| 空态 | 有基础空态 | 明确下一步动作 | 需要按阶段引导 |
| 移动端 | 可响应排列 | 首屏仍高效 | 需要压缩摘要卡和优先展示关键区域 |

## 4. 信息展示原则

### 4.1 应该默认暴露

Dashboard 默认只暴露能帮助用户决策的信息：

1. Dataset 总数，以及 working / active / error 状态。
2. Study 总数，以及活跃和最近更新。
3. Pipeline 总数，以及草稿 / 可运行状态。
4. Run 运行态势，尤其是等待确认、失败、运行中、排队中。
5. 最近 Study 列表。
6. 活动中的 Run 列表。
7. 最近关键活动。
8. 必要的错误或降级提示。
9. 下一步主要动作。

### 4.2 不应该默认暴露

Dashboard 不应默认展示：

1. 对象定义说明。
2. 摘要策略说明。
3. Dataset / Study / Pipeline / Run 的底层 ID。
4. `bids_root`、`source_path`、`fif_path`、服务器存储路径。
5. manifest、result_json、error_json、definition_json。
6. node_run 全列表。
7. artifact 全列表。
8. dataset_files 文件索引。
9. 完整导入流程。
10. Pipeline 编辑器。
11. 运维资源指标，除非进入管理员运维页。

## 5. 推荐目标结构

建议 Dashboard 最终保持三层结构，但进一步压缩和提炼。

```text
顶部操作条
问候 / 日期 / 需要处理数量 / 主要动作

第一层：状态摘要
四对象紧凑摘要 + 异常优先标识

第二层：工作恢复与任务监控
左：最近 Study
右：需要处理 / 活动 Run

第三层：最近活动
6 到 8 条跨对象事件
```

其中“需要处理 / 活动 Run”应是页面的效率核心。如果存在 waiting_user_input 或 failed，它应该比普通 completed 数更醒目。

## 6. 总体修改计划

改造建议分为 12 步推进。前 6 步主要做前端信息和视觉，后 6 步补数据口径、交互定位和长期架构。每一步都应保持页面可运行，并在日志中同步结果。

## 7. 详细步骤与 Codex 提示词

### 第 01 步：建立 Dashboard 当前状态基线

目标：

- 复核当前 `Dashboard.vue` 的数据来源、展示字段、交互入口和样式结构。
- 确认哪些内容已经符合“简洁精致高效”，哪些内容仍偏实现口径或信息噪声。
- 不改业务代码，只形成基线记录。

需要改进的内容：

- 梳理 Dashboard 当前调用的 API：Study list、Dataset Asset list、Pipeline list、Pipeline Runs list。
- 标注当前前端聚合的限制：只抽取有限 Study 和有限 Pipeline。
- 标注当前 UI 区块：顶部、四对象摘要、最近 Study、活动 Run、最近活动。
- 记录当前不应再恢复的内容：快捷入口卡、对象解释卡、摘要策略卡、服务器路径。

验收标准：

- 日志中有清晰的当前状态描述。
- 明确当前 Dashboard 的数据口径不是全量 summary。
- 没有进行代码改动。

Codex 提示词：

```text
第01步：请复核当前 elys_version1/frontend/elys-web/src/views/Dashboard.vue 的页面结构、API 依赖、展示字段、交互入口和样式组织，基于“数据处理功能性网站需要简洁、精致、优雅、高效”的目标，整理当前 Dashboard 的现状基线。不要修改业务代码。重点记录当前已完成的删减项、仍存在的信息噪声、前端有限聚合的数据口径限制、后续不应恢复的旧区块。完成后把结论写入 日志/2_meeting260523/Dashboard页面精致简洁改造计划与Codex提示词.md 的对应步骤。把运行结果在日志文档中同步更新
```

执行记录：

执行时间：2026-05-23 00:43:26 +08:00

本步已复核 `elys_version1/frontend/elys-web/src/views/Dashboard.vue`、`src/api/studies.ts`、`src/api/datasetAssets.ts`、`src/api/pipelines.ts`，未修改任何业务代码。

当前页面结构基线：

1. 顶部区域位于 `Dashboard.vue` 第 3 行附近，使用 `WorkbenchShell`，展示问候语、日期、刷新按钮、导入 Dataset、新建 Study。
2. 四对象摘要位于第 36 行附近，包含 Dataset、Study、Pipeline、Run 四张可点击摘要卡。
3. 最近 Study 区域位于第 86 行附近，展示最近 5 个 Study，并提供 Study 名称、code、描述、Pipeline 数、Run 数、活动中 Run 数和更新时间。
4. 活动中的 Run 区域位于第 138 行附近，支持展开 / 收起，展示 active Run 的 Pipeline 名称、Run 编号、状态、run_mode、save_policy、dataset_count、node_count 和开始时间。
5. 最近活动区域位于第 188 行附近，由前端聚合 Study、Dataset、Pipeline、Run 的最近变化并展示最多 8 条。
6. 数据加载入口为 `loadDashboard()`，位于第 394 行附近；页面 mounted 后自动加载。
7. 样式集中在同一个 SFC 的 scoped style 中，四对象卡、最近 Study、Run 列表、活动时间线都有独立 class 组织。

API 依赖基线：

1. `studyApi.list()` 实际通过 `projectApi.list()` 读取 `/projects`，再映射成 `{ studies }`。
2. `datasetAssetApi.list()` 读取 `/dataset-assets`，只用于 Dashboard 的 Dataset Asset 数量和状态摘要，以及最近活动拼接。
3. `pipelineApi.list(study.id)` 读取 `/projects/{study_id}/pipelines`。
4. `pipelineApi.listRuns(project_id, pipeline_id, 3)` 读取 `/projects/{project_id}/pipelines/{pipeline_id}/runs`。
5. 当前没有专门的 Dashboard summary API，Dashboard 仍由前端组合多个业务 API 得到摘要。

展示字段基线：

1. Dataset 卡：数量、working 数、active 数。
2. Study 卡：数量、active 数、archived 数。
3. Pipeline 卡：数量、已抽取 Study 数、active Pipeline 数。
4. Run 卡：最近读取 Run 数、active Run 数、completed Run 数。
5. Study 行：名称、code、描述、Pipeline 数、Run 数、活动中 Run 数、状态、更新时间。
6. Run 行：Pipeline 名称、Run 编号、状态、run_mode、save_policy、dataset_count、node_count、时间。
7. 最近活动：对象类型、对象名称、状态或摘要、时间。

已完成的删减项：

1. 已移除顶部 `Dataset / Study / Pipeline / Run` 提示词。
2. 已移除“这里显示四个核心对象的有限摘要和下一步入口”开发说明。
3. 已移除“快捷入口”卡。
4. 已移除 Dataset / Pipeline / Run 对象解释卡。
5. 已移除“当前摘要策略”说明卡。
6. 已移除首页默认展示服务器路径、`bids_root`、`source_path`、`fif_path`、Project ID、Data Root 等调试字段。
7. 已移除 Dashboard 内嵌完整上传流程，上传只通过 `/datasets` 入口进入。

仍存在的信息噪声：

1. Pipeline 摘要卡的“几个 Study 已抽取”属于实现口径，不是用户决策口径，后续应改为 active / draft / error 等状态摘要。
2. Run 摘要卡未单独突出 waiting_user_input 和 failed，用户可能不能立即判断是否需要处理。
3. 活动 Run 当前只展示 queued、running、waiting_user_input、pending，未把 failed 纳入需要处理队列。
4. 活动 Run 行点击只进入 `/pipeline`，不能直接定位到具体 Run。
5. 最近活动来自前端拼接，不是真实审计事件，内容会与最近 Study / Run 区域重复。
6. warning 文案仍出现 `Dataset Asset 接口暂不可用`、`部分 Study 的 Pipeline / Run 加载失败`，偏接口口径，后续应改成更用户化的降级提示。
7. 四对象摘要卡高度仍较大，移动端首屏会被四张卡占满，不利于快速看到最近 Study 和活动 Run。

前端有限聚合的数据口径限制：

1. `MAX_SNAPSHOT_STUDIES = 3`，Dashboard 只对前 3 个 Study 拉取 Pipeline 摘要，不代表全量 Study 的 Pipeline 总数。
2. `MAX_RUN_PIPELINES = 4`，Dashboard 只对前 4 个 Pipeline 拉取 Run 摘要，不代表全量 Run。
3. `listRuns(..., 3)` 每个 Pipeline 只取 3 条 Run，recentRuns 最终再截取 8 条。
4. 最近 Study 每行 Pipeline / Run 指标只来自上述有限聚合，不能作为严格全量统计。
5. 最近活动由这些有限集合拼接，可能漏掉未抽取 Study / Pipeline 下的重要事件。
6. 当前数据口径适合 MVP 的低成本摘要，但长期需要 `GET /api/v1/dashboard/summary` 统一返回 counts、states、recent_studies、active_runs、recent_activity。

后续不应恢复的旧区块：

1. 不恢复 Dashboard 内嵌上传表单或 `BidsUploadPanel`。
2. 不恢复“快捷入口”重复卡。
3. 不恢复 Dataset / Study / Pipeline / Run 的对象定义说明。
4. 不恢复“当前摘要策略”开发自述。
5. 不在 Dashboard 默认展示服务器路径、UUID、manifest、node_run、artifact、dataset_files 逐项明细。
6. 不把 Dashboard 做成 Pipeline 编辑器、Run 详情页或文件浏览器。

运行结果：

1. 已执行文本复核和旧文案扫描。
2. `rg` 扫描 `Dashboard.vue` 未发现 `Dataset / Study / Pipeline / Run` 顶部提示词、`这里显示四个核心对象`、`快捷入口`、`当前摘要策略`、`bids_root`、`source_path`、`fif_path`、`Project ID`、`Data Root` 等旧默认展示内容。
3. 本步按要求未修改业务代码，仅更新本文档。
4. 本步未运行 `npm run typecheck` 或 `npm run build`，因为没有前端业务代码改动。

### 第 02 步：重写顶部区域为任务型操作条

目标：

- 顶部不做宣传，不做解释，只承载身份、日期、系统状态和主动作。
- 让用户一眼知道“我是谁、今天是什么状态、现在最该做什么”。

需要改进的内容：

- 保留问候语和日期。
- 增加一个轻量状态提示，例如“3 个 Run 活动中 / 1 个等待确认”。
- 刷新按钮保留为 icon 按钮。
- 右侧主按钮根据状态动态调整：
  - 没有 Dataset：主按钮为“导入 Dataset”。
  - 有 Dataset 但没有 Study：主按钮为“新建 Study”。
  - 有 Study 但没有 Pipeline：主按钮为“创建 Pipeline”。
  - 有 waiting_user_input：主按钮为“处理确认”。
- 次要动作保留 1 到 2 个，避免按钮过多。

验收标准：

- 顶部没有对象提示词和解释句。
- 主按钮有明确优先级。
- 移动端按钮不换行挤压标题。

Codex 提示词：

```text
第02步：请改造 Dashboard 顶部区域，把它从普通标题栏调整为任务型操作条。保留问候语、日期和刷新按钮，新增轻量状态提示；右侧主按钮根据当前数据状态动态决定优先动作：无 Dataset 时导入 Dataset，无 Study 时新建 Study，无 Pipeline 时创建 Pipeline，有 waiting_user_input Run 时处理确认。不要增加大段说明文案，不要做营销式 hero。完成后运行 npm run typecheck、npm run build，并用浏览器检查 /dashboard 桌面和移动端顶部不拥挤。把运行结果在日志文档中同步更新
```

运行结果（2026-05-23 00:52:12 +08:00）：

1. 已将 Dashboard 顶部从普通标题区改为任务型操作条：左侧保留问候语和日期，新增轻量状态胶囊；右侧保留刷新 icon 按钮，并只保留一个动态主按钮。
2. 主按钮优先级已落地：`waiting_user_input Run` 优先显示“处理确认 (n)”；其次按无 Dataset、无 Study、无 Pipeline 分别显示“导入 Dataset”“新建 Study”“创建 Pipeline”；有活动 Run 时显示“查看 Run”；默认进入 Pipeline。
3. 状态提示已按数据状态分层：读取中、等待确认、失败、运行/排队、缺 Dataset、缺 Study、缺 Pipeline、Dataset 摘要不可用、正常状态分别显示短句和不同语气色，不增加大段解释文案。
4. 样式已补齐桌面和移动端响应：移动端顶部改为纵向自然排列，状态胶囊和动作按钮单独成行，避免挤压标题。
5. 同步补充了全局 `refresh` 图标，并给 Dashboard 刷新按钮添加 `aria-label="刷新"`，避免刷新按钮退回默认图标。

修改文件：

- `elys_version1/frontend/elys-web/src/views/Dashboard.vue`
- `elys_version1/frontend/elys-web/src/components/AppIcon.vue`

验证结果：

- `npm run typecheck`：通过。备注：并行执行过程中曾短暂出现 `ImportPage.vue` 的成员识别报错；复核发现对应成员已存在，随后单独重跑 `npm run typecheck` 通过，未修改 `ImportPage.vue`。
- `npm run build`：通过。构建仍输出 Vite CJS API deprecation、`litegraph.js` eval、`PipelinePage` chunk 超过 500 kB 的提示，未阻断本次构建。
- 浏览器 `/dashboard` 桌面端 1280x720：顶部不拥挤，状态为“1 个 Run 等待确认”，主按钮为“处理确认 (1)”，页面宽度无横向溢出。
- 浏览器 `/dashboard` 移动端 390x844：顶部自然换行，`documentElement.scrollWidth = 380`，`bodyScrollWidth = 381`，均小于视口宽度 390；`dashboard-header` 的 `scrollWidth` 与 `clientWidth` 均为 349，无横向溢出。

截图记录：

- `D:\proposal\20260106 念通软件开发\claude\dashboard-step02-desktop.png`
- `D:\proposal\20260106 念通软件开发\claude\dashboard-step02-mobile.png`

剩余风险与后续约束：

- “处理确认 (n)”当前先跳转到 `/pipeline`，精确定位到具体 Run 留给第 11 步处理。
- 当前无 Pipeline 判断仍来自前端有限聚合，只覆盖最近若干 Study 的 Pipeline / Run 摘要；后续 Summary API 接入前，不应把它理解为全局精确统计。
- 顶部已经去掉长说明和营销式 hero，后续步骤不应恢复对象提示词、快捷入口、摘要策略说明、Dataset/Pipeline/Run 说明卡等旧区块。

### 第 03 步：压缩四对象摘要卡的信息密度

目标：

- 四张卡继续保留，但更像状态仪表，不像大卡片展板。
- 每张卡只展示一个主数字和一条有判断力的状态句。

需要改进的内容：

- 缩小卡片高度和内边距。
- 数字使用稳定宽度，刷新不造成布局跳动。
- Dataset 卡展示 working / active / error。
- Study 卡展示 active / archived。
- Pipeline 卡展示 active / draft。
- Run 卡展示 waiting / failed / running / queued，优先展示需要处理数。
- 移除“几个 Study 已抽取”这种实现口径，改为“2 个可运行 · 1 个草稿”这类用户口径。

验收标准：

- 四卡在桌面首屏占用高度明显降低。
- 每张卡没有超过两行文字。
- 文案不暴露前端拉取策略。

Codex 提示词：

```text
第03步：请优化 Dashboard 四对象摘要卡，让它们更紧凑、精致、信息明确。卡片只保留对象名、主数字和一条状态摘要；Dataset 展示 working/active/error，Study 展示 active/archived，Pipeline 展示 active/draft，Run 优先展示 waiting_user_input/failed/running/queued。移除“几个 Study 已抽取”等实现口径文案。调整样式减少卡片高度和首屏占用，保持桌面四列、平板两列、移动端单列。完成后运行 npm run typecheck、npm run build，并用浏览器检查 /dashboard 桌面和移动端。把运行结果在日志文档中同步更新
```

运行结果（2026-05-23 01:06:22 +08:00）：

1. 已将四对象摘要卡压缩为“对象名 + 主数字 + 一条状态摘要”的结构，移除卡片图标、实现口径说明和多余单位文案。
2. Dataset 卡展示：`working / active / error`。其中 `error` 目前按 `error / failed / quarantined / deleted` 归类，避免把异常数据资产埋在其它状态中。
3. Study 卡展示：`active / archived`。
4. Pipeline 卡展示：`active / draft`，已移除“几个 Study 已抽取”“几个可运行”等前端有限聚合或实现口径文案。
5. Run 卡按优先状态展示：`waiting / failed / running / queued`；其中 `queued` 合并 `queued / pending`，保持首页摘要短而明确。
6. 样式已压缩：摘要区外边距从 `mb-5` 降为 `mb-4`，卡片 gap 从 `var(--s-4)` 降为 `var(--s-3)`，单卡最小高度降为 `104px`，内边距降为 `14px 16px 13px`，卡片圆角改为 `var(--r)`。
7. 为避免 Run 状态摘要在桌面四列中换行，摘要行改回正文体，保持 4 个状态在同一行可读。

修改文件：

- `elys_version1/frontend/elys-web/src/views/Dashboard.vue`

验证结果：

- `npm run typecheck`：通过。
- `npm run build`：通过。构建仍输出 Vite CJS API deprecation、`litegraph.js` eval、`PipelinePage` chunk 超过 500 kB 的既有提示，未阻断构建。
- 浏览器 `/dashboard` 桌面端 1280x720：4 张卡保持一行四列；每张卡高度 `104px`；摘要文字分别为 `working 1 · active 1 · error 0`、`active 2 · archived 1`、`active 2 · draft 1`、`waiting 1 · failed 0 · running 1 · queued 1`；无“Study 已抽取”等实现口径文案。
- 浏览器 `/dashboard` 移动端 390x844：4 张卡保持单列；每张卡高度 `104px`；`documentElement.scrollWidth = 380`，`bodyScrollWidth = 381`，均小于视口宽度 390，无横向溢出。
- Browser 插件截图接口本次连续超时；已补充使用临时 headless Chrome 保存同一页面的桌面和移动端截图，作为视觉记录，不修改业务代码。

截图记录：

- `D:\proposal\20260106 念通软件开发\claude\dashboard-step03-desktop.png`
- `D:\proposal\20260106 念通软件开发\claude\dashboard-step03-mobile.png`

剩余风险与后续约束：

- Pipeline 总数与状态仍来自 Dashboard 当前前端有限聚合，只覆盖最近若干 Study；后续接入 Summary API 前，卡片不应宣称全局精确统计。
- `error` 与 `queued` 当前是前端状态归类，后续 Summary API 应由后端统一给出状态桶，避免前后端口径漂移。
- 后续步骤不应恢复卡片图标、技术解释句、`Study 已抽取`、`可运行` 等实现口径摘要。

### 第 04 步：新增“需要处理”优先级逻辑

目标：

- Dashboard 不只展示数量，还要帮助用户发现需要立即处理的事项。
- waiting_user_input 和 failed 的优先级高于普通 running。

需要改进的内容：

- 新增 computed：`attentionRuns`。
- attentionRuns 包含 waiting_user_input 和 failed。
- 顶部状态提示和 Run 卡优先引用 attentionRuns。
- 如果存在 waiting_user_input，显示“需要确认”状态。
- 如果存在 failed，显示“有失败需要处理”状态。
- 不直接在 Dashboard 提供危险操作，如取消、重试、删除。

验收标准：

- 等待确认和失败 Run 不会被普通 Run 淹没。
- 没有需要处理项时，页面保持安静。
- 所有状态色语义清晰。

Codex 提示词：

```text
第04步：请在 Dashboard 中新增“需要处理”优先级逻辑。增加 attentionRuns 计算属性，优先包含 waiting_user_input 和 failed Run；顶部状态提示、Run 摘要卡、活动 Run 区域都优先展示这些需要用户处理的任务。不要在 Dashboard 直接提供取消、重试、删除等高影响操作，只提供进入详情或进入确认的入口。完成后运行 npm run typecheck、npm run build，并用浏览器检查有 waiting_user_input、failed、running、queued 的 mock 数据时排序和提示正确。把运行结果在日志文档中同步更新
```

运行结果（2026-05-23 01:13:34 +08:00）：

1. 已新增 `attentionRuns` 计算属性，状态来源为 `waiting_user_input` 和 `failed`。
2. 已新增统一排序口径：`waiting_user_input > failed > running > queued/pending > 其它`，用于右侧 Run 列表展示。
3. 顶部状态提示优先读取 `attentionRuns`：存在 waiting 时显示“1 个 Run 等待确认”；无 waiting 但有 failed 时显示失败需要查看。
4. 顶部主按钮优先处理需要处理项：waiting 时显示“处理确认 (n)”；仅 failed 时显示“查看失败 (n)”。
5. Run 摘要卡优先展示需要处理数，当前 mock 下显示：`attention 2 · waiting 1 · failed 1`。
6. 右侧“活动中的 Run”区域优先展示需要处理项，并给 waiting 行显示“进入确认”、failed 行显示“查看错误”。这些只是进入入口，没有提供取消、重试、删除等高影响操作。
7. 已补充 attention 视觉状态：需要处理时右侧区域的状态点变为警示色；waiting/failed 行使用轻量强调背景；failed 状态点使用危险色。

修改文件：

- `elys_version1/frontend/elys-web/src/views/Dashboard.vue`

验证结果：

- `npm run typecheck`：通过。
- `npm run build`：通过。构建仍输出 Vite CJS API deprecation、`litegraph.js` eval、`PipelinePage` chunk 超过 500 kB 的既有提示，未阻断构建。
- 当前临时 mock API 已更新为包含 `waiting_user_input / failed / running / queued` 四类 Run，mock API 进程 PID 为 `274528`。
- 浏览器 `/dashboard` 桌面端检查：顶部状态为“1 个 Run 等待确认”；主按钮为“处理确认 (1)”；右侧摘要为“2 个需要处理 · 1 个确认 · 1 个失败”。
- 浏览器排序检查通过：Run 行顺序为 waiting_user_input `Run #16`、failed `Run #15`、running `Run #14`、queued `Run #17`。
- 浏览器危险操作扫描通过：右侧 Run 行文本中没有“取消 / 重试 / 删除”。
- 浏览器移动端 390x844：`documentElement.scrollWidth = 380`，`bodyScrollWidth = 381`，均小于视口宽度 390；排序和提示与桌面一致。

截图记录：

- `D:\proposal\20260106 念通软件开发\claude\dashboard-step04-desktop.png`
- `D:\proposal\20260106 念通软件开发\claude\dashboard-step04-mobile.png`

剩余风险与后续约束：

- “进入确认 / 查看错误”当前仍整体跳转到 `/pipeline`，尚未携带具体 `run_id` 定位；精确定位留给后续 Run 跳转步骤处理。
- 右侧区域已具备处理优先级，但还没有完全重构为“处理队列”；第 05 步需要继续收敛行文案、默认数量和状态展示规则。
- 当前 `attentionRuns` 仍基于前端已读取的有限 Run 集合；后续 Summary API 应由后端统一给出 attention 数和排序列表。

### 第 05 步：重构活动 Run 卡为“处理队列”

目标：

- 右侧区域不只是活动 Run 列表，而是用户的处理队列。
- 默认展示最需要关注的 3 到 5 个 Run。

需要改进的内容：

- 区块标题可调整为“需要处理 / 活动 Run”或“运行队列”。
- 排序规则：waiting_user_input > failed > running > queued > pending。
- 每行展示 Pipeline 名称、Run 编号、状态、阶段、开始时间。
- waiting_user_input 行提供“进入确认”按钮。
- failed 行提供“查看错误”按钮或状态链接。
- running 行展示轻量进度条。
- queued 行展示队列状态，不展示假进度。
- 展开 / 收起保留。

验收标准：

- 用户能在 3 秒内看到是否需要处理。
- 列表不超过 5 条默认展示。
- 文案不出现 manifest、node_run、worker 等底层词。

Codex 提示词：

```text
第05步：请把 Dashboard 右侧“活动中的 Run”重构为更高效的处理队列。排序规则为 waiting_user_input > failed > running > queued > pending；默认展示最需要关注的 3 到 5 条，保留展开/收起。每行展示 Pipeline 名称、Run 编号、状态、阶段或简短说明、开始时间；waiting_user_input 提供“进入确认”，failed 提供“查看错误”，running 显示轻量进度条，queued 不显示假进度。不要展示 manifest、node_run、worker 日志等底层信息。完成后运行 npm run typecheck、npm run build，并用浏览器检查交互和视觉。把运行结果在日志文档中同步更新
```

运行结果（2026-05-23 01:21:05 +08:00）：

1. 已将右侧区块标题从“活动中的 Run”调整为“处理队列”，视觉语义从监控列表转为任务处理入口。
2. 已新增 `RUN_QUEUE_DISPLAY_LIMIT = 5`，默认最多展示 5 条最需要关注的 Run；如果后续队列超过 5 条，会显示剩余数量提示。
3. 队列仍沿用第 04 步优先级排序：`waiting_user_input > failed > running > queued/pending > 其它`。
4. 队列行内容已收敛为：Pipeline 名称、Run 编号、状态、运行阶段、保存策略、开始时间。
5. waiting_user_input 行显示“进入确认”，failed 行显示“查看错误”；这些入口仍为轻量导航提示，不提供取消、重试、删除等高影响操作。
6. running 行保留轻量进度条；queued / pending 行不再显示假进度。
7. 队列文案已移除 Dataset 数、节点数、manifest、node_run、worker 等底层或技术字段。
8. 展开 / 收起交互保留：浏览器验证收起后队列行数为 0，重新展开后恢复 4 条。

修改文件：

- `elys_version1/frontend/elys-web/src/views/Dashboard.vue`

验证结果：

- `npm run typecheck`：通过。
- `npm run build`：通过。构建仍输出 Vite CJS API deprecation、`litegraph.js` eval、`PipelinePage` chunk 超过 500 kB 的既有提示，未阻断构建。
- 浏览器 `/dashboard` 桌面端检查：标题为“处理队列”；摘要为“2 个需要处理 · 1 个确认 · 1 个失败”；排序为 waiting `Run #16`、failed `Run #15`、running `Run #14`、queued `Run #17`。
- 浏览器规则检查：waiting 和 failed 有入口标签；running 有进度条；queued 无进度条。
- 浏览器危险/底层词扫描通过：队列行文本中没有“取消 / 重试 / 删除 / manifest / node_run / worker”。
- 浏览器移动端 390x844：`documentElement.scrollWidth = 380`，`bodyScrollWidth = 381`，无横向溢出；移动端滚动到处理队列后视觉正常。

截图记录：

- `D:\proposal\20260106 念通软件开发\claude\dashboard-step05-desktop.png`
- `D:\proposal\20260106 念通软件开发\claude\dashboard-step05-mobile.png`
- `D:\proposal\20260106 念通软件开发\claude\dashboard-step05-mobile-queue.png`

剩余风险与后续约束：

- “进入确认 / 查看错误”仍未携带具体 `run_id` 定位到 Pipeline 页面内部对象，后续 Run 跳转定位步骤需要补齐。
- 当前队列仍来自前端有限聚合的 `recentRuns`，不是后端全局队列；后续 Summary API 应统一提供处理队列和状态桶。
- 第 06 步需要继续优化左侧最近 Study，把“活动中”指标调整为更贴近处理队列的“需要处理”等工作恢复信息。

### 第 06 步：优化最近 Study 为工作恢复列表

目标：

- 最近 Study 不是普通列表，而是“继续工作”的入口。
- 每行指标要少而有用。

需要改进的内容：

- 最近 Study 行保留名称、code、状态、更新时间。
- 描述过长时一行截断。
- 指标控制在 3 到 4 个以内。
- 指标建议为 Dataset、Pipeline、Run、需要处理。
- 如果当前没有准确 Dataset 数，可先不显示或标注为“挂载数”，避免误导。
- 行点击进入 Study 详情。
- 避免每行多个按钮造成视觉噪音。

验收标准：

- 行高稳定。
- 长 Study 名称和 code 不溢出。
- 用户能快速找回最近工作。

Codex 提示词：

```text
第06步：请优化 Dashboard 的最近 Study 区域，把它做成高效的工作恢复列表。每行保留 Study 名称、code、状态、最近更新时间和最多 3 到 4 个指标；建议指标为 Dataset 或挂载数、Pipeline、Run、需要处理。长名称、长描述、长 code 必须截断且不撑开布局。整行点击进入 Study 详情，避免在行内堆多个按钮。完成后运行 npm run typecheck、npm run build，并用浏览器检查桌面和移动端长文本表现。把运行结果在日志文档中同步更新
```

运行结果（2026-05-23 01:27:35 +08:00）：

完成情况：

1. 已将“最近研究项”调整为工作恢复列表，副标题收敛为“继续最近研究项，快速回到数据、流程和待处理任务。”。
2. 每行保留 Study 名称、code、状态、最近更新时间和 3 个指标：Pipeline、Run、需处理。
3. 将原先“活动中”指标替换为“需处理”，口径来自 `attentionRunCount`，仅统计 `waiting_user_input` 和 `failed` Run，更贴合第 04 / 05 步的处理队列优先级。
4. 保留整行点击进入 Study 详情，没有在行内堆叠多个按钮。
5. 对 Study 名称、code、描述和 meta 文本补强截断样式：容器使用 `min-width: 0`，长文本使用 `overflow: hidden`、`text-overflow: ellipsis`、`white-space: nowrap`，避免撑开布局。
6. code 设置弹性宽度和最大宽度，长 code 在桌面和移动端都会截断，不挤压状态和指标。
7. “需处理”指标使用轻量警示色，仅在数量大于 0 时突出，避免把所有指标做成高噪音状态标签。
8. 当前 Dashboard 仍没有准确的 per-Study Dataset / 挂载数摘要 API，因此本步未展示 Dataset 指标，避免用前端推断造成误导；后续 Summary API 可补齐。

修改文件：

- `elys_version1/frontend/elys-web/src/views/Dashboard.vue`

验证结果：

- `npm run typecheck`：通过。
- `npm run build`：通过。构建仍输出 Vite CJS API deprecation、`litegraph.js` eval、`PipelinePage` chunk 超过 500 kB 的既有提示，未阻断构建。
- 已启动长文本 mock 数据验证，mock 服务 PID 为 `479364`，包含超长 Study 名称、超长 code、超长描述，以及 `waiting_user_input`、`failed`、`running`、`queued` Run。
- 浏览器 `/dashboard` 桌面端检查：首个 Study 行宽约 704px、高约 99px；长名称、长 code、长描述均触发截断；页面 `scrollWidth = 1270`，未超过 1280px 视口。
- 浏览器 `/dashboard` 移动端 390x844 检查：首个 Study 行宽约 315px、高约 135px；长名称、长 code、长描述均触发截断；`documentElement.scrollWidth = 380`，`bodyScrollWidth = 381`，未出现横向溢出。
- 桌面和移动端均确认最近 Study 行内没有多按钮堆叠，列表仍可作为整行点击入口使用。

截图记录：

- `D:\proposal\20260106 念通软件开发\claude\dashboard-step06-desktop.png`
- `D:\proposal\20260106 念通软件开发\claude\dashboard-step06-mobile-study.png`

剩余风险与后续约束：

- 最近 Study 的 Dataset / 挂载数还缺少后端摘要口径，本步刻意不展示，后续应由 Dashboard Summary API 提供。
- Study 行当前进入项目详情页，但如果未来需要定位到具体 Dataset / Pipeline / Run，应通过明确 query 或详情页内部导航完成，不应在 Dashboard 行内增加大量按钮。
- 长文本截断已处理，但第 10 步视觉统一时仍需整体复核行高、间距和状态色是否与最终工作台规格一致。

### 第 07 步：重写空态为阶段化引导

目标：

- 空态不只是“暂无数据”，而是告诉用户下一步该做什么。
- 根据 Dataset、Study、Pipeline、Run 的阶段给出不同引导。

需要改进的内容：

- 无 Dataset：提示“先导入 Dataset”，主按钮进入 `/datasets`。
- 有 Dataset 无 Study：提示“创建 Study 组织分析空间”。
- 有 Study 无 Pipeline：提示“创建 Pipeline 定义处理流程”。
- 有 Pipeline 无 Run：提示“发起 trial Run 验证流程”。
- 无活动 Run：保持安静，不要大面积占位。

验收标准：

- 空态文案短，不超过两行。
- 每个空态只有一个主动作。
- 不使用开发词和技术字段。

Codex 提示词：

```text
第07步：请重写 Dashboard 空态，让空态按 Dataset、Study、Pipeline、Run 的阶段给出明确下一步。无 Dataset 时引导导入 Dataset；有 Dataset 无 Study 时引导创建 Study；有 Study 无 Pipeline 时引导创建 Pipeline；有 Pipeline 无 Run 时引导发起 trial Run；无活动 Run 时保持轻量安静。每个空态只保留一个主动作，文案不超过两行，不出现技术字段。完成后运行 npm run typecheck、npm run build，并用 mock 数据检查不同空态。把运行结果在日志文档中同步更新
```

运行结果（2026-05-23 01:39:37 +08:00）：

完成情况：

1. 已新增 `DashboardEmptyState` 空态模型，将标题、短说明、图标和可选主动作集中管理。
2. 最近 Study 区域负责 Dataset / Study 前置阶段：
   - 无 Dataset：显示“导入 Dataset”，说明“先把数据放进工作台。”，唯一主动作“导入 Dataset”。
   - 有 Dataset 无 Study：显示“创建 Study”，说明“用 Study 组织数据和流程。”，唯一主动作“创建 Study”。
3. 处理队列区域负责 Pipeline / Run 阶段：
   - 有 Study 无 Pipeline：显示“创建 Pipeline”，说明“为 Study 配置处理流程。”，唯一主动作“创建 Pipeline”。
   - 有 Pipeline 无 Run：显示“发起 trial Run”，说明“先试跑一次，确认流程可用。”，唯一主动作“发起 trial Run”。
   - 无活动 Run：显示“暂无活动 Run”，说明“没有等待处理或正在运行的任务。”，不显示动作按钮，保持安静。
4. 最近活动空态改为轻量安静提示：“暂无最近活动 / 导入、创建或运行后会显示在这里。”，不添加按钮。
5. 最近 Study 在空列表时隐藏“查看全部”二级入口，避免空态内外出现多个动作。
6. 顶部状态和主按钮同步补齐 Pipeline 有但 Run 为空的阶段：状态提示“还没有 Run，可先发起试跑”，主按钮“发起 trial Run”。
7. 空态文案没有出现 API、payload、manifest、node_run、worker、UUID、server 等技术字段。

修改文件：

- `elys_version1/frontend/elys-web/src/views/Dashboard.vue`

验证结果：

- `npm run typecheck`：通过。
- `npm run build`：通过。构建仍输出 Vite CJS API deprecation、`litegraph.js` eval、`PipelinePage` chunk 超过 500 kB 的既有提示，未阻断构建。
- 已启动第 07 步可切换场景 mock API，服务 PID 为 `631328`；临时 mock 脚本已删除，进程仍在运行。
- 浏览器 `/dashboard` 桌面端逐项检查 mock 场景，页面宽度 1280px 时 `documentElement.scrollWidth = 1270`，未出现横向溢出。
- `no_dataset`：顶部主按钮为“导入 Dataset”；最近 Study 空态为“导入 Dataset”，按钮数 1；处理队列和最近活动均为无动作轻提示。
- `dataset_no_study`：顶部主按钮为“新建 Study”；最近 Study 空态为“创建 Study”，按钮数 1；处理队列无动作轻提示。
- `study_no_pipeline`：最近 Study 已显示 1 行；处理队列空态为“创建 Pipeline”，按钮数 1；顶部主按钮为“创建 Pipeline”。
- `pipeline_no_run`：最近 Study 已显示 1 行；处理队列空态为“发起 trial Run”，按钮数 1；顶部主按钮为“发起 trial Run”。
- `no_active_run`：最近 Study 已显示 1 行；处理队列空态为“暂无活动 Run”，按钮数 0；顶部主按钮回到“进入 Pipeline”。

剩余风险与后续约束：

- “发起 trial Run”目前仍进入 `/pipeline`，尚未携带具体 Pipeline 或自动打开试跑面板；后续第 11 步的定位跳转可继续细化。
- Pipeline / Run 阶段判断仍来自前端有限聚合，只覆盖最近 Study 的摘要；后续 Summary API 应统一返回 Dashboard 阶段和空态推荐动作。
- 第 10 步视觉统一时需要继续压实空态高度、按钮间距和安静态颜色，确保桌面首屏更稳定。

### 第 08 步：收敛最近活动为审计式时间线

目标：

- 最近活动只展示关键变化，避免重复展示普通列表信息。
- 颜色按对象类型稳定区分。

需要改进的内容：

- 默认最多 6 到 8 条。
- 优先展示失败、等待确认、导入完成、Pipeline 更新、Study 更新。
- 每条只保留对象类型、对象名称、动作、时间。
- 文案使用业务语言，如“导入完成”“等待确认”“运行失败”“流程已更新”。
- 不展示 API payload、事件 ID、技术 JSON。
- 后续可替换为 audit_events API。

验收标准：

- 最近活动区没有冗长描述。
- 不与最近 Study 和活动 Run 重复过多。
- 点击能进入相关对象页。

Codex 提示词：

```text
第08步：请优化 Dashboard 最近活动区域，把它收敛为审计式时间线。默认最多展示 6 到 8 条，优先展示失败、等待确认、导入完成、Pipeline 更新、Study 更新等关键事件。每条只保留对象类型、对象名称、动作和时间，使用业务语言，不展示 API payload、事件 ID 或技术 JSON。当前仍可用前端聚合数据，但结构要便于后续替换为 audit_events API。完成后运行 npm run typecheck、npm run build，并用浏览器检查最近活动不拥挤。把运行结果在日志文档中同步更新
```

运行结果（2026-05-23 01:47:35 +08:00）：

完成情况：

1. 已将最近活动从“对象摘要 + 描述”改为审计式时间线字段：对象类型、对象名称、动作、时间。
2. 新增 `ACTIVITY_LIMIT = 8`，默认最多展示 8 条活动。
3. `ActivityItem` 已调整为更接近后续 `audit_events` 的结构：`objectType`、`objectName`、`actionLabel`、`time`、`to`、`tone`、`priority`。
4. 活动排序改为先按业务优先级、再按时间排序：失败 Run > 等待确认 Run > Dataset 导入完成 > Pipeline 更新 > Study 更新 > Run 完成 / 运行中等。
5. Dataset 活动文案收敛为“导入完成 / 导入中 / 导入异常 / 数据已更新”。
6. Pipeline 活动文案收敛为“Pipeline 已创建 / Pipeline 已更新”，不再展示版本号或节点数。
7. Run 活动文案收敛为“运行失败 / 等待确认 / 运行完成 / 运行中 / 已排队 / 等待调度”等业务语言，不再展示运行模式或保存策略。
8. 最近活动视觉改为紧凑行：对象类型胶囊、对象名、动作、时间同一行展示；移动端改为两列换行，避免拥挤。

修改文件：

- `elys_version1/frontend/elys-web/src/views/Dashboard.vue`

验证结果：

- `npm run typecheck`：通过。
- `npm run build`：通过。构建仍输出 Vite CJS API deprecation、`litegraph.js` eval、`PipelinePage` chunk 超过 500 kB 的既有提示，未阻断构建。
- 已启动第 08 步活动 mock API，服务 PID 为 `56688`；临时 mock 脚本已删除，进程仍在运行。
- 浏览器 `/dashboard?case=step08` 桌面端检查：最近活动共 8 条，符合默认上限。
- 浏览器检查到的前 5 条动作顺序为：`运行失败`、`等待确认`、`导入完成`、`Pipeline 已更新`、`Pipeline 已更新`，优先级符合预期。
- 浏览器扫描最近活动文本，未发现 `API`、`payload`、`JSON`、`manifest`、`node_run`、`worker`、`UUID`、版本号、节点数、`analysis`、`trial`、`temporary`、`current` 等技术或底层字段。
- 桌面端页面宽度 1280px 时 `documentElement.scrollWidth = 1270`，最近活动面板高度约 500px，未出现横向溢出或明显拥挤。

剩余风险与后续约束：

- 当前最近活动仍由前端从 Study、Dataset、Pipeline、Run 聚合生成，不是真实审计事件；第 13 步应接入后端 `audit_events` 或 Dashboard Summary 返回的审计活动。
- 现阶段点击 Run / Pipeline 活动仍进入 `/pipeline`，尚未定位到具体对象；后续第 11 步需补齐 query 定位。
- 当前优先级会让较早的失败 / 等待确认排在较新的普通更新前，这是有意设计；若后续产品更强调时间顺序，应由后端返回 `priority` 和 `created_at` 后统一裁剪。

### 第 09 步：优化告警和降级提示

目标：

- 接口失败或摘要降级时提示用户，但不要破坏主界面。
- 区分阻塞错误和非阻塞警告。

需要改进的内容：

- Study 列表失败属于阻塞错误，应显示明显错误。
- Dataset Asset 摘要失败、部分 Pipeline 摘要失败属于非阻塞警告，应压缩展示。
- 非阻塞警告可以放在顶部细条或卡片内小提示。
- 警告文案使用用户语言，如“部分摘要暂不可用，刷新后重试”。
- 提供刷新动作。

验收标准：

- 一个非核心接口失败不会让 Dashboard 显得全页报错。
- 错误文案不出现接口名或堆栈。
- 刷新后能重新加载。

Codex 提示词：

```text
第09步：请优化 Dashboard 的错误和降级提示。Study 列表加载失败作为阻塞错误显示；Dataset Asset 摘要失败、部分 Pipeline/Run 摘要失败作为非阻塞警告压缩展示，不要破坏主界面。警告文案使用用户语言，例如“部分摘要暂不可用，刷新后重试”，不要暴露接口名、堆栈或实现细节。保留刷新动作。完成后运行 npm run typecheck、npm run build，并通过 mock 失败场景检查提示层级。把运行结果在日志文档中同步更新
```

运行结果（2026-05-23 01:55:13 +08:00）：

完成情况：

1. 已将 Study 列表失败固定为阻塞错误文案：“研究项列表加载失败，请刷新后重试”，不再透传后端 `detail`。
2. Study 列表失败时会清空 Dashboard 摘要数据并停止继续加载；主内容区不再渲染四对象卡片、最近 Study、处理队列和最近活动，避免误导成“暂无数据”。
3. 阻塞错误状态下顶部主按钮变为“重新加载”，错误提示条内也保留“刷新”按钮。
4. Dataset 摘要失败、Pipeline 摘要失败、Run 摘要失败统一进入 `addSummaryWarning()`，只展示一条压缩警告：“部分摘要暂不可用，刷新后重试”。
5. 非阻塞警告不会中断主界面，四对象摘要、最近 Study、处理队列和最近活动继续基于可用数据渲染。
6. 非阻塞警告提示条内保留“刷新”按钮，顶部刷新按钮也继续可用。
7. Dashboard 状态提示中的摘要失败文案也收敛为“部分摘要暂不可用，核心入口仍可使用”，不再暴露具体接口名。

修改文件：

- `elys_version1/frontend/elys-web/src/views/Dashboard.vue`

验证结果：

- `npm run typecheck`：通过。
- `npm run build`：通过。构建仍输出 Vite CJS API deprecation、`litegraph.js` eval、`PipelinePage` chunk 超过 500 kB 的既有提示，未阻断构建。
- 已启动第 09 步失败场景 mock API，服务 PID 为 `478756`；临时 mock 脚本已删除，进程仍在运行。
- 浏览器 `study_fail` 场景：红色阻塞错误数量 1，警告数量 0；错误文案为“研究项列表加载失败，请刷新后重试”；四对象卡片数量 0，Dashboard 主面板数量 0；顶部主按钮为“重新加载”；刷新入口数量 2。
- 浏览器 `dataset_fail` 场景：阻塞错误数量 0，警告数量 1；警告文案为“部分摘要暂不可用，刷新后重试”；四对象卡片数量 4，Dashboard 主面板数量 3，主界面继续可用。
- 浏览器 `pipeline_fail` 场景：阻塞错误数量 0，警告数量 1；主界面继续可用，Study 行仍展示 2 条，Run 队列保留可用摘要。
- 浏览器 `run_fail` 场景：阻塞错误数量 0，警告数量 1；主界面继续可用，Run 摘要缺失不会造成全页错误。
- 浏览器 `summary_fail` 场景：Dataset / Pipeline / Run 同时失败时仍只展示 1 条压缩警告。
- 浏览器 `ok` 场景：阻塞错误数量 0，警告数量 0，四对象卡片数量 4，主面板数量 3，刷新入口保留 1 个顶部按钮。
- 所有失败场景文本扫描均未发现 `API`、`stack`、`trace`、`traceback`、`SQL`、`worker`、`node_run`、`manifest`、`internal`、`host`、`接口` 等技术词或后端细节。

剩余风险与后续约束：

- 目前非阻塞警告统一压缩为一条，用户不能区分是 Dataset 摘要还是 Pipeline / Run 摘要失败；这是本步刻意降低噪音的取舍，后续可在详情页或日志中心提供更细信息。
- Study 列表失败时隐藏主内容区，避免误导；第 10 步视觉统一时需要复核阻塞错误状态下的空白高度和按钮位置。
- 后续 Summary API 接入后，应由后端统一返回降级状态和用户级提示，前端只负责展示。

复核记录（2026-05-23 01:57:47 +08:00）：

- 未做新的业务代码修改；复核当前 `Dashboard.vue` 中第 09 步实现仍然存在。
- `npm run typecheck`：通过。
- `npm run build`：通过。构建仍输出 Vite CJS API deprecation、`litegraph.js` eval、`PipelinePage` chunk 超过 500 kB 的既有提示，未阻断构建。
- 复验 mock 场景：`study_fail` 仍为 1 个阻塞错误、0 个警告、0 个主面板，顶部主按钮为“重新加载”。
- 复验 mock 场景：`dataset_fail`、`pipeline_fail`、`run_fail`、`summary_fail` 均为 0 个阻塞错误、1 个压缩警告，主界面继续渲染。
- 复验 mock 场景：`ok` 为 0 个阻塞错误、0 个警告。
- 复验所有场景均未发现 `API`、`stack`、`trace`、`traceback`、`SQL`、`worker`、`node_run`、`manifest`、`internal`、`host`、`接口` 等技术词或后端细节。

### 第 10 步：统一视觉规格与精致度

目标：

- 页面更像专业数据处理工具，而不是卡片堆叠页面。
- 通过克制间距、边框、字体层级提升精致感。

需要改进的内容：

- 统一 Dashboard 内卡片圆角，不超过现有设计系统半径。
- 减少大面积浅色装饰。
- 控制标题字号，避免小面板标题过大。
- 使用稳定间距，减少首屏垂直浪费。
- 图标只用于识别，不做装饰堆叠。
- 状态色只用于状态，不做大面积渐变。
- 移动端优先保证信息可读和不重叠。

验收标准：

- 桌面首屏能看到四对象摘要、最近 Study 开头和活动 Run 开头。
- 移动端不会出现文字溢出、按钮拥挤、卡片过高。
- 页面不呈现单一蓝色或过重渐变。

Codex 提示词：

```text
第10步：请统一 Dashboard 的视觉规格，目标是简洁、精致、优雅的数据处理工作台。调整卡片圆角、边框、阴影、间距、标题字号和状态色使用，减少大面积浅色装饰和不必要渐变；图标只用于识别，不做装饰堆叠；状态色只用于状态。确保桌面首屏能看到四对象摘要、最近 Study 开头和活动 Run 开头，移动端不出现文字溢出、按钮拥挤或卡片过高。完成后运行 npm run typecheck、npm run build，并用浏览器截图检查桌面和移动端。把运行结果在日志文档中同步更新
```

### 第 11 步：补具体 Run 定位跳转

目标：

- 用户从 Dashboard 点击 Run 后，不需要到 Pipeline 页面再寻找。
- 为未来 Run detail 独立页预留路径。

需要改进的内容：

- 活动 Run 行点击携带 `run_id`、`project_id`、`pipeline_id` query。
- Pipeline 页面读取 query 后自动定位对应 Pipeline 和 Run。
- 如果 Pipeline 页面暂不支持自动定位，先补最小兼容逻辑。
- 等待确认按钮也应定位到对应 Run。
- 后续如果新增 `/runs/:id`，Dashboard 只需改跳转目标。

验收标准：

- 点击 Dashboard 某个 Run 后，Pipeline 页面能选中或展示该 Run。
- 刷新后 query 不导致页面报错。
- 找不到 Run 时给出轻量提示。

Codex 提示词：

```text
第11步：请为 Dashboard 活动 Run 增加具体定位跳转。Run 行和“进入确认/查看错误”等入口跳转到 Pipeline 页面时携带 project_id、pipeline_id、run_id query；改造 PipelinePage 读取这些 query 后自动选择对应 Pipeline 和 Run，若找不到则给出轻量提示且不报错。不要新建假接口。完成后运行 npm run typecheck、npm run build，并用浏览器从 Dashboard 点击不同 Run 验证能定位。把运行结果在日志文档中同步更新
```

运行结果（2026-05-23 10:26:16 +08:00）：

完成情况：

1. Dashboard 处理队列中的 Run 行已从固定 `/pipeline` 改为携带 query 的定位跳转：`project_id`、`pipeline_id`、`run_id`。
2. waiting_user_input 行内“进入确认”和 failed 行内“查看错误”仍作为整行 Run 链接的一部分，不新增危险操作按钮。
3. 最近活动中的 Run 事件也改为携带同样的 Run query，点击审计式时间线中的 Run 可进入对应执行项。
4. 最近活动中的 Pipeline 事件携带 `project_id`、`pipeline_id`，便于进入对应工作流。
5. PipelinePage 新增 query 读取逻辑，兼容 `project_id / pipeline_id / run_id`，同时保留旧的 `projectId / studyId` 读取方式。
6. PipelinePage 加载时会优先选择 query 指定的 Study、Pipeline 和 Run；同一路由组件内 query 改变时也会重新定位。
7. PipelinePage 新增指定 Run 加载逻辑：直接读取目标 Run、node runs 和 artifacts，并显示“已定位 Run #xx”。
8. 若指定 Pipeline 或 Run 找不到，页面只给出轻量状态提示，并回退到最近可用工作流或当前工作流最新 Run，不抛错。
9. 本步没有新增前端业务接口，也没有新建假 API；验证 mock 仅复用已有接口路径。

修改文件：

- `elys_version1/frontend/elys-web/src/views/Dashboard.vue`
- `elys_version1/frontend/elys-web/src/views/PipelinePage.vue`

验证结果：

- `npm run typecheck`：通过。
- `npm run build`：通过。构建仍输出 Vite CJS API deprecation、`litegraph.js` eval、`PipelinePage` chunk 超过 500 kB 的既有提示，未阻断构建。
- 已启动第 11 步本地 mock API，服务 PID 为 `100936`；临时 mock 脚本已删除，进程仍在运行。
- 浏览器 `/dashboard` 检查：处理队列中 3 条 Run 链接均带 query，例如 `/pipeline?project_id=study-1&pipeline_id=11&run_id=run-waiting`。
- 从 Dashboard 点击 waiting_user_input Run 行后进入 `/pipeline?project_id=study-1&pipeline_id=11&run_id=run-waiting`；PipelinePage 选中 `Resting EEG Study` 和 `Preprocess Pipeline v3`，状态栏显示“已定位 Run #19”，Run 面板显示 `Run #19 / 等待确认`。
- 从 Dashboard 点击 failed Run 的“查看错误”入口后进入 `/pipeline?project_id=study-1&pipeline_id=11&run_id=run-failed`；PipelinePage 选中同一 Study / Pipeline，状态栏显示“已定位 Run #18”，Run 面板显示 `Run #18 / 失败`，并保留错误摘要。
- 浏览器直接访问缺失 Run：`/pipeline?project_id=study-1&pipeline_id=11&run_id=missing-run`；页面未报错，状态栏显示“未找到指定 Run，已显示当前工作流最新 Run”，并回退展示 `Run #19`。

剩余风险与后续约束：

- 当前 Dashboard 仍跳转到 PipelinePage，而不是独立 Run 详情页；如果未来新增 `/runs/:id`，只需要调整 Dashboard 的 `pipelineRunRoute()` 目标。
- PipelinePage 可以定位到 Run，但“进入确认”尚未自动选中需要人工确认的具体节点；如果后续确认流程要求一步到位，需要在 query 中继续携带 node_run_id 或由 Run detail 自动选中 waiting 节点。
- Query 定位复用了当前 PipelinePage 的状态栏作为轻提示，后续可在第 10 / 14 步视觉回归中统一轻提示位置和样式。

### 第 12 步：新增 Dashboard Summary API 设计与前端切换

目标：

- 从前端有限聚合升级为后端统一摘要。
- 提升准确性、性能和权限一致性。

需要改进的内容：

- 后端新增 `GET /api/v1/dashboard/summary`。
- 返回 counts、states、recent_studies、active_runs、recent_activity。
- 后端统一做权限过滤。
- 前端新增 `dashboardApi`。
- Dashboard 优先使用 summary API。
- summary API 不可用时保留当前有限聚合降级。

验收标准：

- 正常情况下 Dashboard 首屏主数据来自一个 summary API。
- summary API 失败时页面仍可降级显示。
- 不对所有 Study 做全量 N+1 拉取。

Codex 提示词：

```text
第12步：请设计并实现 Dashboard Summary API。后端新增 GET /api/v1/dashboard/summary，返回 counts、states、recent_studies、active_runs、recent_activity，并在后端统一做权限过滤和摘要口径控制。前端新增 dashboardApi，Dashboard 优先使用 summary API；当 summary API 不可用时保留当前有限聚合降级逻辑。不要把服务器路径、UUID、manifest JSON 等技术字段返回给 Dashboard 默认视图。完成后运行后端相关测试、npm run typecheck、npm run build，并用浏览器检查 /dashboard。把运行结果在日志文档中同步更新
```

执行记录（2026-05-23）：

- 已新增后端 `GET /api/v1/dashboard/summary`，路由文件为 `elys_version1/backend/app/routers/dashboard.py`，并在 `app/main.py` 中注册。
- 已新增 `elys_version1/backend/app/schemas/dashboard.py`，响应固定收敛为 `counts`、`states`、`recent_studies`、`active_runs`、`recent_activity`。
- 已新增 `elys_version1/backend/app/services/dashboard_summary.py`，在后端统一做可见 Study、可见 Dataset Asset、Pipeline、Run、审计活动的摘要口径控制。
- 权限口径：Study / Pipeline / Run 只基于当前用户可见 Study 聚合；Dataset Asset 只在用户具备 `data:read` 或 admin 权限时纳入，并继续复用可见资产过滤。
- Dashboard 默认摘要没有返回服务器路径、manifest JSON、result JSON、error JSON、definition snapshot、source path、fif path 等底层字段；Run 仅保留定位所需的 `project_id`、`pipeline_id`、`id` 和业务展示字段。
- `active_runs` 在后端按 `waiting_user_input > failed > running > queued > pending` 排序，返回首页处理队列所需的 Pipeline 名称、Run 编号、状态、阶段说明和时间。
- `recent_activity` 已优先读取审计事件，并用业务语言映射动作；审计不足时用受控摘要补齐，不返回 audit event ID、payload 或技术 JSON。
- 前端已新增 `elys_version1/frontend/elys-web/src/api/dashboard.ts`，Dashboard 优先调用 `dashboardApi.summary()`。
- 当前 `Dashboard.vue` 保留旧的有限聚合逻辑作为降级：summary API 不可用时仍按 Study 列表、Dataset Asset、有限 Pipeline / Run 快照加载，并显示“部分摘要暂不可用，刷新后重试”。
- 已更新前端类型 `elys_version1/frontend/elys-web/src/types/index.ts`，新增 Dashboard Summary 专用类型，避免复用完整 Run 响应导致技术字段进入默认视图。

验证结果：

- 后端相关测试：`python -m pytest tests/test_dashboard_summary.py` 通过，4 passed；仅有既有 Pydantic deprecated warning 和 `.pytest_cache` 写入权限 warning。
- 前端类型检查：`npm run typecheck` 通过。
- 前端构建：`npm run build` 通过；保留既有 Vite CJS deprecated、litegraph eval、PipelinePage chunk size warning。
- 浏览器检查 `/dashboard`：使用 summary mock 验证到四对象统计 `Dataset 3 / Study 4 / Pipeline 5 / Run 9`，顶部显示 `1 个 Run 等待确认`，处理队列按等待确认、失败、运行中、排队顺序展示。
- 浏览器交互检查：处理队列“收起 / 展开”可用，收起后 `.run-list .run-row` 为 0，展开后为 4。
- 桌面视觉检查：1280px 视口下首屏紧凑，四对象卡、最近 Study、处理队列和最近活动正常展示，无服务器路径、manifest、UUID 文本进入页面。
- 移动端检查说明：尝试使用 headless Chrome 390px 截图时本机 Chrome GPU/headless 截图能力异常未产出图片；本轮已完成桌面浏览器和交互验证，移动端完整截图回归建议放入第 14 步继续执行。

### 第 13 步：接入真实审计活动

目标：

- 最近活动从前端拼接变成真实事件。
- 支持后续审计、协作和追溯。

需要改进的内容：

- 后端 summary 或 activity API 返回最近事件。
- 事件包含 object_kind、object_name、action_label、created_at、target_url。
- 前端最近活动只渲染事件，不再拼接 Study / Dataset / Pipeline / Run。
- 事件文案由后端或统一 mapper 生成。
- 保留对象类型颜色。

验收标准：

- 最近活动中的事件与后端审计一致。
- 没有重复、过长、技术化描述。
- 点击活动能进入相关对象。

Codex 提示词：

```text
第13步：请把 Dashboard 最近活动接入真实审计活动。后端通过 dashboard summary 或 activity API 返回 object_kind、object_name、action_label、created_at、target_url 等字段；前端最近活动只渲染这些事件，不再用 Study/Dataset/Pipeline/Run 前端拼接生成。保留对象类型颜色和最多 6 到 8 条展示，不暴露审计事件 ID、payload 或技术 JSON。完成后运行后端相关测试、npm run typecheck、npm run build，并用浏览器检查最近活动。把运行结果在日志文档中同步更新
```

执行记录（2026-05-23）：

- 已将 Dashboard Summary 的 `recent_activity` 字段调整为真实审计活动视图，单条事件字段为 `object_kind`、`object_name`、`action_label`、`created_at`、`target_url`。
- 后端 `elys_version1/backend/app/services/dashboard_summary.py` 的最近活动现在只读取 `AuditEvent`，按当前用户可见 Study 和可见 Dataset Asset 做过滤，不再用 Study / Dataset / Pipeline / Run 的更新时间做 synthetic 补齐。
- 后端保留业务语言映射，例如 `pipeline.run.failed -> Run 运行失败`、`dataset.uploaded -> Dataset 导入完成`、`pipeline.updated -> Pipeline 已更新`。
- 后端活动响应不返回审计事件 ID、payload、metadata JSON、接口名、堆栈或底层技术字段。
- 前端 `elys_version1/frontend/elys-web/src/views/Dashboard.vue` 的最近活动区域现在只渲染 `dashboardSummary.recent_activity`，不再基于 Study / Dataset / Pipeline / Run 列表前端拼接活动。
- summary API 不可用进入旧有限聚合降级时，最近活动保持安静空态，避免用不完整数据伪造审计时间线。
- 前端类型 `elys_version1/frontend/elys-web/src/types/index.ts` 已同步为 `DashboardRecentActivityItem` 的新字段结构，并继续根据 `object_kind` 保留对象类型颜色。

验证结果：

- 后端相关测试：`python -m pytest tests/test_dashboard_summary.py` 通过，5 passed；仅有既有 Pydantic deprecated warning 和 `.pytest_cache` 写入权限 warning。
- 前端类型检查：`npm run typecheck` 通过。
- 前端构建：`npm run build` 通过；保留既有 Vite CJS deprecated、litegraph eval、PipelinePage chunk size warning。
- 浏览器检查 `/dashboard`：使用 summary mock 返回 5 条审计活动，页面最近活动只展示 `Run 运行失败`、`Run 等待确认`、`Dataset 导入完成`、`Pipeline 已更新`、`Study 已创建`。
- 浏览器检查点击入口：活动链接分别指向 `/pipeline?project_id=study-1&pipeline_id=11&run_id=run-failed`、`/pipeline?project_id=study-1&pipeline_id=11&run_id=run-waiting`、`/datasets`、`/pipeline?project_id=study-1&pipeline_id=11`、`/studies/study-1`。
- 浏览器检查技术字段：页面文本未出现 `event_id`、`payload`、`metadata_json` 或 mock 中的 `raw stack`。
- 本轮浏览器截图尝试因 in-app browser 截图 CDP 超时未产出图片；DOM 与页面文本验证已覆盖最近活动字段、数量、文案和链接。

### 第 14 步：全链路视觉与效率回归

目标：

- 确认 Dashboard 真正达到简洁、精致、信息明确、高效。
- 防止后续局部改动破坏整体体验。

需要改进的内容：

- 检查桌面 1440px、常规 1280px、移动 390px。
- 检查有数据、无数据、接口降级、Run waiting、Run failed、Run running 等场景。
- 检查点击路径：Dataset、Study、Pipeline、Run。
- 检查页面是否没有服务器路径、UUID、开发说明。
- 检查首屏是否能看到核心态势和任务监控。
- 截图保存到日志目录或测试记录。

验收标准：

- `npm run typecheck` 通过。
- `npm run build` 通过。
- 浏览器桌面和移动端无明显重叠、溢出、空白过大。
- 记录剩余风险和下一步建议。

Codex 提示词：

```text
第14步：请对 Dashboard 做全链路视觉与效率回归。运行 npm run typecheck、npm run build；用浏览器检查 /dashboard 在桌面 1440px、常规 1280px、移动 390px 下的表现；分别验证有数据、无数据、接口降级、waiting_user_input Run、failed Run、running Run 场景；检查 Dataset、Study、Pipeline、Run 点击路径；确认页面不展示服务器路径、UUID、开发说明或摘要策略。保存必要截图，记录通过项、发现的问题、剩余风险和下一步建议。把运行结果在日志文档中同步更新
```

## 8. 建议优先级

建议按以下优先级执行：

| 优先级 | 步骤 | 原因 |
| --- | --- | --- |
| P0 | 第 02 到 07 步 | 直接影响用户看到什么、下一步做什么 |
| P0 | 第 10 步 | 直接影响简洁、精致、优雅的观感 |
| P1 | 第 08 到 09 步 | 改善信息噪声和异常体验 |
| P1 | 第 11 步 | 提升从 Dashboard 到 Run 的效率 |
| P2 | 第 12 到 13 步 | 需要后端配合，但能解决长期准确性和性能 |
| P0 | 第 14 步 | 每轮修改后都应做回归 |

如果只做第一轮，建议先做：

1. 第 02 步：顶部任务型操作条。
2. 第 03 步：压缩四对象摘要卡。
3. 第 05 步：活动 Run 改为处理队列。
4. 第 06 步：最近 Study 工作恢复列表。
5. 第 10 步：视觉规格统一。
6. 第 14 步：浏览器回归。

## 9. 最终验收标准

完成改造后，Dashboard 应满足：

1. 首屏没有开发说明、对象定义和服务器路径。
2. 四对象摘要清楚但不抢占过多空间。
3. 用户能立即发现等待确认和失败 Run。
4. 用户能一键回到最近 Study。
5. 用户能从 Run 行定位到具体 Run。
6. 最近活动短、准、可点击。
7. 空态能明确告诉用户下一步。
8. 移动端不拥挤、不溢出、不重叠。
9. 数据加载失败时有降级提示，但主界面不崩。
10. 长期通过 Dashboard Summary API 避免前端 N+1 聚合。

## 10. 结论

当前 Dashboard 已经完成“删掉冗余解释、建立四对象工作台”的第一轮收敛。下一轮重点不应是继续加模块，而是提升信息判断力：

- 把四对象摘要从“数量展示”变成“状态判断”。
- 把活动 Run 从“列表”变成“处理队列”。
- 把最近 Study 从“记录列表”变成“工作恢复入口”。
- 把最近活动从“拼接摘要”变成“真实事件时间线”。

这样页面会更符合数据处理功能性网站的气质：简洁、精致、信息明确，并且真正提高用户效率。
