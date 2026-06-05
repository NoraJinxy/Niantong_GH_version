# Dataset 页面简洁化改造计划与 Codex 提示词

文档生成时间：2026-05-23 00:33:52 +08:00

## 1. 现有 Dataset 页面分析

当前 Dataset 页面主要由两个前端文件承担：

- `frontend/elys-web/src/views/ImportPage.vue`
- `frontend/elys-web/src/components/BidsUploadPanel.vue`

页面现在已经实现 Dataset-first 的基本业务能力：用户可以新建 Dataset，系统自动准备配套 Study 与 mount，然后在下方上传 EEG 文件，上传进入 Dataset working 版本。这个方向是正确的，但当前信息呈现更像“调试型详情页”，还不是一个简洁、高效、精致的数据处理工作台。

### 1.1 当前页面结构

当前 `ImportPage.vue` 大致包含：

1. 顶部标题与新建数据集按钮。
2. 数据集统计卡片：数据集总数、工作中、可用、当前文件索引。
3. 数据集目录：搜索、状态筛选、数据集列表。
4. 数据集详情：名称、描述、状态、可见性、数据集 ID、code、创建时间、更新时间。
5. working 文件索引：文件总数、original、Raw BIDS、canonical FIF、体量，以及若干逐文件路径。
6. 导入目标：mount_name、准备导入目标按钮。
7. 当前导入目标：数据集、配套 Study、挂载信息。
8. `BidsUploadPanel`：选择文件、BIDS 默认值、导入组列表、批量进度、错误与成功提示。

当前 `BidsUploadPanel.vue` 大致包含：

1. 导入标题与 Dataset-first 说明。
2. Dataset Asset ID、mount_name、Study ID 三个技术字段。
3. original upload、Raw BIDS、canonical FIF、dataset_files 四阶段说明。
4. 文件/文件夹选择与拖拽区域。
5. BIDS 默认值设置。
6. 每组文件的大块卡片：文件名、状态说明、阶段结果、进度条、subject/task/session/run 输入框。
7. 批量导入进度与导入按钮。

### 1.2 当前主要问题

#### 问题 1：默认暴露过多技术字段

当前页面默认展示 Dataset UUID、Dataset Asset ID、Study ID、mount_id、mount_name 等字段。这些字段对开发、排错、日志追踪有价值，但对普通数据处理用户没有直接价值。

用户真正需要默认看到的是：

- 数据集名称
- code
- 数据规模
- 导入状态
- 最近更新时间
- 是否可以继续导入或进入工作流

#### 问题 2：working 文件索引不应默认铺开

当前页面会把文件索引中的逻辑路径逐行展示。文件数达到几百时，页面会被长路径占满，用户很难快速判断数据集整体状态。

默认视图应该展示摘要，不应该展示单个文件名和完整路径。逐文件列表应进入独立标签页、抽屉或“查看文件索引”详情区。

#### 问题 3：批量导入时队列不够紧凑

当前每组导入文件都以较大的卡片形式展示，并且成功项也占用大量空间。60 组文件时，用户需要滚动很久，整体进度和失败项反而不突出。

批量导入更适合用紧凑队列：

- 一行代表一组 Recording。
- 默认只展示 subject、task、格式、文件数、状态、进度。
- 失败项自动展开。
- 成功项默认收起。
- 详细文件组成和阶段结果按需展开。

#### 问题 4：信息层级不够像数据处理工作台

当前页面把“数据集详情、文件索引、导入目标、导入文件队列”都放在一个长页面中，层级接近，用户不容易判断下一步要做什么。

更适合的结构是：

1. 数据集目录
2. 数据集概览
3. 导入数据
4. Records / 文件索引
5. 技术信息

#### 问题 5：术语偏工程化

`Dataset Asset ID`、`mount_name`、`dataset_files`、`canonical FIF`、`original upload` 等术语不应成为默认说明。页面默认文案应更多使用用户语言：

- 原始上传
- BIDS 逻辑视图
- 标准 FIF
- 文件索引
- 处理工作空间

技术术语可以保留在技术详情中。

## 2. 与目标要求对比

你的目标是：这是一个数据处理的功能性网站，需要简洁、精致、优雅，也需要效率。

| 目标要求 | 当前表现 | 差距 | 改造方向 |
| --- | --- | --- | --- |
| 简洁 | 默认展示 UUID、mount、Study ID、文件路径 | 主视图信息过载 | 技术字段默认隐藏，放入折叠详情 |
| 精致 | 文件索引和导入组大面积铺开 | 视觉密度不受控 | 采用摘要卡片、紧凑队列、清晰状态 |
| 优雅 | 多处工程术语直接外露 | 产品语言不统一 | 默认使用任务语言，技术词进入高级区 |
| 效率 | 文件多时滚动很长 | 批处理操作不高效 | 队列化、筛选失败、批量编辑、批量重试 |
| 数据处理导向 | 页面像对象调试详情 | 工作流主线不突出 | 以“数据集状态 -> 导入 -> 处理”为主线 |
| 可追溯 | 底层信息直接暴露 | 追溯信息影响主体验 | 追溯信息保留，但按需展开 |

## 3. 改造原则

1. 默认展示用户决策信息，不默认展示数据库字段。
2. 摘要优先，明细按需展开。
3. 成功信息轻量化，失败信息突出化。
4. 批量导入用队列，不用大块说明卡片。
5. 技术追溯信息不删除，但从主界面移入“技术信息”。
6. 尽量先做前端信息架构优化，不急于引入后端破坏性改动。
7. 每一步完成后都运行 `npm run typecheck` 和 `npm run build`；涉及文档时运行必要的文档构建。
8. 每一步都在本日志文档中记录实际改动、验证结果和遗留问题。

## 4. 修改计划

### 第 01 步：复核现状与建立页面改造基线

#### 需要改进的内容

- 阅读 `ImportPage.vue`、`BidsUploadPanel.vue`、`datasetAssets.ts`、`datasets.ts`、`types/index.ts`。
- 确认当前 Dataset 页的状态来源、上传上下文、文件索引接口、导入结果事件。
- 记录当前页面默认暴露的所有字段。
- 明确哪些字段属于主视图，哪些字段属于技术信息。
- 不修改业务代码，只更新本日志中的基线记录。

#### 涉及文件

- `frontend/elys-web/src/views/ImportPage.vue`
- `frontend/elys-web/src/components/BidsUploadPanel.vue`
- `frontend/elys-web/src/api/datasetAssets.ts`
- `frontend/elys-web/src/api/datasets.ts`
- `frontend/elys-web/src/types/index.ts`
- `日志/2_meeting260522/Dataset页面简洁化改造计划与Codex提示词.md`

#### 验证方式

- 不需要构建。
- 输出当前页面结构、字段清单、技术字段清单、风险点。

#### Codex 提示词

```text
第01步：请复核当前 Dataset 页面改造基线。读取 frontend/elys-web/src/views/ImportPage.vue、frontend/elys-web/src/components/BidsUploadPanel.vue、frontend/elys-web/src/api/datasetAssets.ts、frontend/elys-web/src/api/datasets.ts、frontend/elys-web/src/types/index.ts，整理当前页面结构、数据来源、默认暴露字段、技术追溯字段、批量导入队列状态和可能影响 Dataset-first 上传的关键逻辑。不要修改业务代码，只更新日志/2_meeting260522/Dataset页面简洁化改造计划与Codex提示词.md 中第01步执行记录、发现、风险和下一步建议。把运行结果在日志文档中同步更新
```

#### 第 01 步执行记录

执行时间：2026-05-23 00:33:52 +08:00

本步骤已按要求复核以下文件：

- `frontend/elys-web/src/views/ImportPage.vue`
- `frontend/elys-web/src/components/BidsUploadPanel.vue`
- `frontend/elys-web/src/api/datasetAssets.ts`
- `frontend/elys-web/src/api/datasets.ts`
- `frontend/elys-web/src/types/index.ts`

本步骤只更新日志文档，未修改业务代码，未运行前端构建。

#### 当前页面结构复核

`ImportPage.vue` 当前仍是一个“数据集管理 + 导入目标准备 + 文件索引 + 上传入口”混合页面：

1. 顶部标题区：展示“数据集管理”、Dataset-first 说明和“新建数据集”按钮。
2. 数据概览区：展示数据集总数、工作中、可用、当前文件索引数量。
3. Study 快捷入口提示：当 URL 带 `study_id` 或 `project_id` 时，提示上传目标会挂载到当前 Study。
4. 数据集目录：支持搜索名称、code 或 ID，支持按状态筛选。
5. 新建数据集表单：包含名称、code、描述、挂载名称。
6. 数据集详情：展示当前数据集名称、描述、状态、可见性、数据集 ID、code、创建时间、更新时间。
7. working 文件索引：展示文件总数、original、Raw BIDS、canonical FIF、体量，并默认列出最近 8 条文件逻辑路径。
8. 导入目标面板：通过 mount name 将当前 Dataset 设为导入目标。
9. 当前导入目标面板：展示 Dataset、配套 Study、挂载信息。
10. `BidsUploadPanel`：负责选择文件、分组、默认 BIDS 实体、上传进度、重复 Recording 确认和导入结果展示。

`BidsUploadPanel.vue` 当前结构是一个展开式导入组件：

1. 顶部说明：展示 Dataset 名称、配套 Study、mount_name，并说明 original upload、Raw BIDS、canonical FIF、dataset_files。
2. 目标上下文：默认展示 Dataset Asset ID、mount_name、Study ID。
3. 阶段条：展示 original upload、Raw BIDS、canonical FIF、dataset_files 四个阶段。
4. Dropzone：支持选择文件、选择文件夹、拖拽文件。
5. BIDS 默认值：task、session、run，默认折叠在 details 中。
6. 导入组列表：每组一个大块卡片，包含勾选框、格式、标题、文件名、状态信息、结果摘要、单组进度条和 subject/task/session/run 输入框。
7. 批量进度：底部展示总进度、全局错误/成功信息和导入按钮。
8. 重复 Recording 弹窗：遇到 `DATASET_EXISTS` 时确认是否作为新 original upload 版本导入。

#### 数据来源复核

当前页面数据来源如下：

| 数据 | 来源 | 当前用途 |
| --- | --- | --- |
| Study 列表 | `studyApi.list()` | Study 快捷入口、复用或创建配套 Study |
| Dataset Asset 列表 | `datasetAssetApi.list()` -> `GET /dataset-assets` | 左侧数据集目录、统计、选择当前数据集 |
| Dataset working 文件索引 | `datasetAssetApi.listFiles(assetId, { version_label: 'working' })` -> `GET /dataset-assets/{assetId}/files` | 文件角色统计、最近文件路径列表 |
| Dataset bootstrap | `datasetAssetApi.bootstrap()` -> `POST /dataset-assets/bootstrap` | 新建 Dataset Asset、working version、配套 Study、mount、next_upload |
| Study mounts | `studyDatasetMountApi.list/create/update()` | 复用或创建 Dataset 到 Study 的挂载 |
| 上传原始数据 | `datasetApi.upload(projectId, payload)` -> `POST /projects/{projectId}/datasets/import` | 导入 EDF/BDF/BrainVision 到 Dataset working 版本 |
| 上传结果 | `DatasetUploadResponse` | 生成导入结果摘要，触发父组件刷新 Dataset 列表和文件索引 |

#### 默认暴露字段复核

当前默认主界面会暴露以下字段：

- 数据集总数、工作中数量、可用数量、当前文件索引数量。
- 数据集名称、code、状态、可见性、创建时间、更新时间。
- 数据集 ID，即 Dataset UUID。
- 当前文件索引的逻辑路径或相对路径。
- 文件角色：original、Raw BIDS、canonical FIF。
- 当前导入目标中的 Dataset Asset ID。
- 当前导入目标中的 Study ID。
- 当前导入目标中的 mount_name 和 mount_id。
- 上传组件中的 Dataset Asset ID、mount_name、Study ID。
- 上传阶段中的 original upload、Raw BIDS、canonical FIF、dataset_files。

其中，名称、code、状态、可见性、更新时间、文件数量、体量属于用户决策信息；Dataset UUID、Dataset Asset ID、Study ID、mount_id、mount_name、dataset_version_id、storage_uri、sha256、upload endpoint 属于技术追溯信息，不适合默认占据主视觉。

#### 技术追溯字段复核

当前类型和接口中可用于追溯的字段包括：

- `DatasetAsset.id`
- `DatasetVersion.id`
- `DatasetVersion.dataset_asset_id`
- `DatasetVersion.storage_uri`
- `DatasetBootstrapNextUpload.study_id`
- `DatasetBootstrapNextUpload.project_id`
- `DatasetBootstrapNextUpload.dataset_asset_id`
- `DatasetBootstrapNextUpload.dataset_version_id`
- `DatasetBootstrapNextUpload.mount_id`
- `DatasetBootstrapNextUpload.mount_name`
- `DatasetBootstrapNextUpload.upload_endpoint`
- `StudyDatasetMount.id`
- `StudyDatasetMount.project_id`
- `StudyDatasetMount.dataset_asset_id`
- `StudyDatasetMount.mount_name`
- `DatasetFile.id`
- `DatasetFile.dataset_id`
- `DatasetFile.dataset_upload_id`
- `DatasetFile.storage_uri`
- `DatasetFile.relative_path`
- `DatasetFile.logical_path`
- `DatasetFile.sha256`
- `Dataset.source_path`
- `Dataset.fif_path`
- `Recording.source_path`
- `Recording.fif_path`

建议后续将这些字段集中放入“技术信息”或“文件详情”区域，默认折叠，并严格避免在普通视图展示服务器绝对路径。

#### 批量导入队列状态复核

`BidsUploadPanel.vue` 当前的导入队列状态模型如下：

- 支持格式：BrainVision 三件套、EDF、BDF；其他格式进入 invalid group。
- 分组策略：
  - EDF/BDF：单文件一组。
  - BrainVision：按目录 + 文件 stem 聚合 `.vhdr/.eeg/.vmrk`，缺失任一关联文件时标记为不可导入。
- 实体识别：从路径或文件名中识别 `sub-`、`ses-`、`task-`、`run-`，否则使用默认值。
- 组状态：`ready`、`uploading`、`processing`、`replace-pending`、`done`、`error`。
- 批量进度：使用 `batchProgressTotal`、`batchProgressCompleted`、`batchProgressActiveGroupId` 计算总进度。
- 上传顺序：`uploadSelectedGroups()` 按 selected ready groups 顺序串行上传。
- 重复处理：后端返回 `DATASET_EXISTS` 时进入 `replace-pending` 并弹出确认框，确认后以 `replaceExisting=true` 再次上传。
- 导入结果：`buildImportOutcome()` 从响应中聚合 original、raw_bids、dataset_files、canonical_fif 状态。

当前队列逻辑是完整的，但视觉呈现偏展开式：每个 group 都默认占用较大区域，成功项也继续占据页面高度。后续应保留该状态模型和上传流程，只调整展示密度、筛选和展开交互。

#### Dataset-first 上传关键逻辑复核

后续改造时必须保持以下逻辑不被破坏：

1. `bootstrapDataset()` 通过 `datasetAssetApi.bootstrap()` 一次性创建 Dataset Asset、working version、配套 Study、mount，并写入 `bootstrapResponse`。
2. URL 带 `study_id` 或 `project_id` 时，`buildPairedStudyPayload()` 走 `paired_study.mode='existing'`，否则默认走 `mode='create'`。
3. 选择已有 Dataset 时，`mountExistingDatasetAsset()` 会先 `ensureTargetStudy()`，再 `ensureStudyDatasetMount()`。
4. `ensureTargetStudy()` 在普通入口会优先复用同 code 的配套 Study；若 mount name 冲突，则创建新的配套 Study。
5. `uploadContext` 是上传组件的关键输入，必须包含 `studyId/projectId/datasetAssetId/mountName`；如果来自 bootstrap，还带 `datasetVersionId/mountId/uploadEndpoint`。
6. `BidsUploadPanel` 的 `hasUploadTarget` 要求 `studyId + datasetAssetId + mountName` 同时存在。
7. `datasetApi.upload()` 必须继续把 `dataset_asset_id` 和 `mount_name` 写入 `FormData`，否则后端无法按 Dataset-first 口径定位导入目标。
8. 上传成功后，`BidsUploadPanel` 通过 `emit('uploaded')` 通知父组件，父组件 `handleUploaded()` 会刷新 Study 列表、Dataset 列表和文件索引。
9. 重复 Recording 的新版本导入依赖后端 `DATASET_EXISTS` 错误结构和 `replace_existing=true`，不能在视觉改造中移除。

#### 发现

1. 当前业务链路基本完整，Dataset-first 的数据创建、挂载、上传、刷新都有对应前端逻辑。
2. 当前页面默认暴露的技术字段过多，尤其是 Dataset UUID、Dataset Asset ID、Study ID、mount_id 和 mount_name。
3. 文件索引虽然只截取了最近 8 条，但仍在主详情区默认展示逻辑路径，文件多时会强化“文件浏览器/调试页”的观感。
4. 导入组件已经有批量总进度，但每组仍是大块卡片，不适合几十组或上百组导入。
5. Records 视角尚未在 Dataset 页显式呈现；用户目前更多看到文件路径，而不是 Recording。
6. `recordingApi.list()` 已经存在，后续增加 Records 标签页可以优先复用，但需要确认当前 Study mount 与 Dataset Asset 查询参数是否完整满足页面需求。

#### 风险

1. 如果隐藏技术字段时误删 `uploadContext` 或 `datasetApi.upload()` payload 中的 `datasetAssetId/mountName`，会直接破坏 Dataset-first 上传。
2. 如果将 `mount_name` 从创建/挂载表单中完全移除，需要保证仍有默认值 `primary` 并处理同 Study 内 mount name 冲突。
3. 如果把文件索引改为分页或按角色筛选，需要确认后端 `listFiles` 是否支持分页；当前前端类型只声明了 `version_label` 和 `file_role`。
4. 如果增加 Records 视图，需要小心 Study-first 兼容路径和 mounted Dataset 可见性，避免外部挂载 Dataset 的 Recording 再次不可见。
5. 如果大幅重构导入组 DOM，需要保留 BrainVision 完整性校验、重复 Recording 确认、批量进度和 `emit('uploaded')` 刷新机制。

#### 下一步建议

1. 第 02 步先做信息架构调整，把页面拆为“目录 + 工作台 + 页内标签”，但先不改上传逻辑。
2. 第 03 步优先隐藏默认技术 ID，并建立“技术信息”折叠区，确保可追溯但不干扰主体验。
3. 第 04 和第 05 步把 Dataset 概览与文件索引摘要化，先降低主界面复杂度。
4. 第 07 步之后再处理 BidsUploadPanel 的紧凑队列，避免一次性重构过多影响上传链路。
5. 每一步都应运行 `npm run typecheck` 和 `npm run build`；涉及浏览器行为时检查 `/datasets` 普通入口和带 `study_id` 的快捷入口。

### 第 02 步：重构 Dataset 页信息架构为“目录 + 工作台 + 标签页”

#### 需要改进的内容

- 保留左侧数据集目录，但压缩宽度和信息密度。
- 右侧从长详情页改为工作台结构。
- 增加页内标签或分区状态：概览、导入、Records、文件索引、技术信息。
- 默认进入“概览”。
- “导入”只在用户点击导入或新建数据集后重点呈现。
- 不改变 Dataset-first 上传接口。

#### 涉及文件

- `frontend/elys-web/src/views/ImportPage.vue`
- 可能涉及 `frontend/elys-web/src/style.css` 或本组件 scoped style

#### 验证方式

- `npm run typecheck`
- `npm run build`
- 浏览器检查 `/datasets`

#### Codex 提示词

```text
第02步：请把 Dataset 页面重构为“数据集目录 + 数据集工作台 + 页内标签”的信息架构。保留现有 Dataset-first 数据流和上传上下文，不改后端接口；右侧默认显示概览，并提供“概览、导入、Records、文件索引、技术信息”入口。文件索引和技术字段先迁移到对应入口，不要默认铺在主概览。完成后运行 npm run typecheck、npm run build，并用浏览器检查 /datasets 页面可正常打开、可选择数据集、可进入导入区。把运行结果在日志文档中同步更新
```

#### 第 02 步执行记录

执行时间：2026-05-23 00:46:09 +08:00

本步骤已修改：

- `frontend/elys-web/src/views/ImportPage.vue`

本步骤未修改后端接口，未修改 `datasetAssetApi`、`datasetApi.upload()` 和 `DatasetUploadContext` 的调用契约。

#### 实际改动

1. 将右侧数据集区域从长详情页重构为“数据集工作台”。
2. 新增页内标签：
   - `概览`
   - `导入`
   - `Records`
   - `文件索引`
   - `技术信息`
3. 选中数据集后默认进入 `概览`，展示数据集名称、描述、状态、可见性、code、更新时间、文件数、体量、原始上传、BIDS 逻辑视图、标准 FIF 和文件索引摘要。
4. 将原先默认铺在主详情区的 working 文件索引明细迁移到 `文件索引` 标签页。
5. 将 Dataset Asset ID、Study ID、mount_id、working version ID、upload endpoint 等追溯字段迁移到 `技术信息` 标签页。
6. 将原先页面底部独立的 `BidsUploadPanel` 移入 `导入` 标签页。
7. 在 `导入` 标签页保留现有导入目标准备逻辑和上传组件，继续使用原有 `uploadContext`。
8. 新建 Dataset 或将已有 Dataset 设为导入目标后，会自动切到 `导入` 标签页并滚动到上传区域。
9. 选择不同数据集时，工作台会回到 `概览` 标签页，避免沿用上一个数据集的技术信息或导入视图。
10. 新增 `Records` 标签页占位说明，后续第 11 步再接入 Recording 视角。

#### 保持不变的关键逻辑

1. `datasetAssetApi.bootstrap()` 调用未变。
2. `studyDatasetMountApi.list/create/update()` 调用未变。
3. `uploadContext` 仍保留 `studyId/projectId/datasetAssetId/datasetVersionId/mountId/mountName/uploadEndpoint/uploadMethod`。
4. `BidsUploadPanel` 仍通过 props 接收 `studyId`、`datasetAssetId`、`mountName` 和 `uploadContext`。
5. `datasetApi.upload()` 仍会在 `FormData` 中提交 `dataset_asset_id` 和 `mount_name`。
6. 上传成功后仍通过 `@uploaded="handleUploaded"` 刷新 Study、Dataset 和文件索引。

#### 验证结果

已运行：

```text
npm run typecheck
```

结果：通过。

已运行：

```text
npm run build
```

结果：通过。构建输出仍包含既有 Vite CJS API deprecation、`litegraph.js` eval、chunk size 警告；未发现本步骤引入的编译错误。

浏览器检查：

- 打开 `http://127.0.0.1:63241/datasets` 成功。
- 页面可读取数据集列表，当前显示 2 个数据集。
- 选中数据集后默认激活 `概览` 标签。
- 页面存在 5 个工作台标签：`概览`、`导入`、`Records`、`文件索引`、`技术信息`。
- 点击 `导入` 后可看到导入目标面板和 `BidsUploadPanel`。
- 点击 `文件索引` 后可看到 working 文件索引面板。
- 点击 `技术信息` 后可看到 Dataset Asset ID 等追溯字段。
- 点击另一个数据集后，工作台自动回到 `概览`，选择数据集交互正常。

#### 兼容说明

本步骤主要调整 `ImportPage.vue` 的信息架构和布局，没有改上传组件内部逻辑。导入区中 `BidsUploadPanel.vue` 仍暂时显示 Dataset Asset ID、Study ID、mount_name，这是第 03 步要处理的内容；本步骤只确保这些信息不再出现在默认 `概览` 主视图中。

#### 遗留问题

1. `BidsUploadPanel.vue` 顶部仍有 Dataset Asset ID、Study ID、mount_name 技术上下文，下一步应隐藏到技术信息或折叠区。
2. `Records` 标签页目前只是占位，尚未接入 `recordingApi.list()`。
3. 文件索引标签页仍只展示最近 8 条路径，尚未实现搜索、筛选、分页或显示更多。
4. 概览区仍基于文件索引计算规模，后续如果需要 subjects/recordings 级聚合，需要后端或 Recording API 支持。

### 第 03 步：隐藏默认技术 ID，新增技术信息折叠区

#### 需要改进的内容

- 主视图不再默认显示 Dataset UUID。
- 当前导入目标不再默认显示 Dataset Asset ID、Study ID、mount_id。
- `BidsUploadPanel` 不再默认显示 Dataset Asset ID、mount_name、Study ID 三个大字段。
- 新增“技术信息”区域，折叠展示：
  - Dataset Asset ID
  - Study ID
  - mount_name
  - mount_id
  - dataset_version_id
  - upload endpoint
- 技术字段旁边可提供复制按钮，但不要抢占视觉。

#### 涉及文件

- `frontend/elys-web/src/views/ImportPage.vue`
- `frontend/elys-web/src/components/BidsUploadPanel.vue`
- `frontend/elys-web/src/components/AppIcon.vue` 如需要新增 copy 图标

#### 验证方式

- `npm run typecheck`
- `npm run build`
- 浏览器检查主视图不再出现 UUID 和技术 ID。
- 检查技术信息区仍能查看追溯字段。

#### Codex 提示词

```text
第03步：请隐藏 Dataset 页面默认暴露的技术 ID。ImportPage.vue 主概览和当前导入目标中不要默认展示 Dataset UUID、Dataset Asset ID、Study ID、mount_id；BidsUploadPanel.vue 不要默认展示 Dataset Asset ID、Study ID、mount_name 三个技术字段。请新增或整理“技术信息”折叠区，用于按需查看并复制 Dataset Asset ID、Study ID、mount_name、mount_id、dataset_version_id 和 upload endpoint。保持上传 payload 和 DatasetUploadContext 不变。完成后运行 npm run typecheck、npm run build，并浏览器确认默认页面不再暴露这些 ID。把运行结果在日志文档中同步更新
```

#### 第 03 步执行记录

执行时间：2026-05-23 00:53:13 +08:00

本步骤已修改：

- `frontend/elys-web/src/views/ImportPage.vue`
- `frontend/elys-web/src/components/BidsUploadPanel.vue`
- `frontend/elys-web/src/components/AppIcon.vue`

#### 实际改动

1. `ImportPage.vue` 主概览继续保持无 Dataset UUID、Dataset Asset ID、Study ID、mount_id。
2. `ImportPage.vue` 的导入目标摘要改为只展示数据集名称、处理工作空间名称和导入状态，不再默认展示 mount_name。
3. 新建 Dataset 表单和导入目标准备区中的“挂载名称”移入“高级设置”，默认折叠，默认值仍为 `primary`。
4. `技术信息` 标签页新增“技术追溯信息”折叠区，默认折叠。
5. 技术折叠区按需展示并支持复制：
   - Dataset Asset ID
   - Study ID
   - mount_name
   - mount_id
   - dataset_version_id
   - upload endpoint
6. 新增 `copy` 图标用于技术字段复制按钮。
7. `BidsUploadPanel.vue` 顶部说明从技术链路说明调整为用户语言：Dataset、处理工作空间、导入到 working 版本。
8. `BidsUploadPanel.vue` 默认目标上下文不再展示 Dataset Asset ID、Study ID、mount_name，改为展示数据集、处理工作空间、目标状态。
9. `BidsUploadPanel.vue` 中“缺少 Dataset Asset ID 或 mount_name”的默认错误文案改为“缺少 Dataset 导入目标”，避免把技术字段暴露给普通用户。

#### 保持不变的关键逻辑

1. `DatasetUploadContext` 字段未删减。
2. `uploadContext` 仍保留 `studyId/projectId/datasetAssetId/datasetVersionId/mountId/mountName/uploadEndpoint/uploadMethod`。
3. `BidsUploadPanel` 内部仍通过 `hasUploadTarget` 校验 `studyId + datasetAssetId + mountName`。
4. `datasetApi.upload()` 仍会提交 `dataset_asset_id` 和 `mount_name`。
5. 新建 Dataset 和挂载已有 Dataset 的后端接口调用未变。

#### 验证结果

已运行：

```text
npm run typecheck
```

结果：通过。

已运行：

```text
npm run build
```

结果：通过。构建仍有既有 Vite CJS API deprecation、`litegraph.js` eval、chunk size 警告；未发现本步骤引入的编译错误。

浏览器检查 `http://127.0.0.1:63241/datasets`：

- 默认 `概览` 标签中未出现 `Dataset Asset ID`、`Study ID`、`mount_id`、`mount_name`、`upload endpoint`、`dataset_version_id`。
- 点击 `导入` 标签后，`BidsUploadPanel` 可见，但默认正文未出现上述技术字段。
- `导入` 标签中的高级设置默认折叠。
- 点击 `技术信息` 标签后，默认只显示“技术追溯信息”折叠摘要。
- 展开技术折叠区后可看到 Dataset Asset ID；在已有导入目标的上下文中会继续展示 Study ID、mount_name、mount_id、dataset_version_id 和 upload endpoint。
- 技术字段旁存在复制按钮。

#### 遗留问题

1. `技术信息` 中的 Study ID、mount_name、mount_id、dataset_version_id、upload endpoint 只有在已准备导入目标后才会出现；未准备目标时只显示 Dataset Asset ID。
2. `BidsUploadPanel` 内部阶段名仍包含 original upload、Raw BIDS、canonical FIF、dataset_files，后续第 10 步会统一改为更偏用户语言的阶段文案。
3. 文件索引和 Records 视图尚未继续增强，分别留到第 05 步和第 11 步处理。

### 第 04 步：将 Dataset 概览改为用户决策型摘要

#### 需要改进的内容

- 概览区重点显示：
  - 数据集名称
  - code
  - 状态
  - 可见性
  - 最近更新时间
  - 文件总数
  - 原始文件数
  - BIDS 逻辑视图数量
  - 标准 FIF 数量
  - 体量
- 如果后端没有 subjects / recordings 聚合字段，先不要硬做假数据。
- 将“当前文件索引”改为“文件数”或“文件索引摘要”。
- 页面文案减少技术解释，强调“可导入 / 可处理 / 需处理”。

#### 涉及文件

- `frontend/elys-web/src/views/ImportPage.vue`

#### 验证方式

- `npm run typecheck`
- `npm run build`
- 浏览器检查选择不同数据集时摘要能更新。

#### Codex 提示词

```text
第04步：请把 Dataset 概览改造成用户决策型摘要。主概览只展示数据集名称、code、状态、可见性、最近更新时间、文件总数、原始文件数、BIDS 逻辑视图数量、标准 FIF 数量和体量；不要默认展示 UUID、mount、Study 等技术字段。如果当前 API 没有 subjects_count 或 recordings_count，不要伪造数据，先保留文件级摘要。请优化中文文案，让页面表达“该数据集是否已导入、是否可继续导入、是否可进入后续处理”。完成后运行 npm run typecheck、npm run build，并浏览器检查 /datasets。把运行结果在日志文档中同步更新
```

#### 第 04 步执行记录

执行时间：2026-05-23 00:58:32 +08:00

本步骤已修改：

- `frontend/elys-web/src/views/ImportPage.vue`

#### 实际改动

1. 页面顶部说明从“管理数据集资产 + 配套 Study”调整为“选择数据集、查看导入状态和文件摘要、继续导入或进入后续处理”，弱化 Study 技术概念。
2. 顶部统计卡片中的“当前文件索引”改为“当前文件数”。
3. `概览` 标签页改为用户决策型摘要，不再以详情字段堆叠为主。
4. 新增 `datasetDecisionSummary` 计算逻辑，根据文件索引读取状态和文件角色摘要判断：
   - 正在读取文件摘要
   - 文件摘要待确认
   - 尚未导入
   - 已导入，等待标准文件
   - 已导入，可进入后续处理
5. 概览中新增“当前判断 / 后续处理”摘要条，用于表达是否已导入、是否可继续导入、是否建议进入 QC 或 Pipeline。
6. 概览身份摘要只展示：
   - 数据集名称
   - code
   - 状态
   - 可见性
   - 最近更新时间
7. 概览文件摘要只展示：
   - 文件总数
   - 原始文件数
   - BIDS 逻辑视图数量
   - 标准 FIF 数量
   - 体量
8. 未引入 subjects_count 或 recordings_count 假数据；当前仍基于现有 `datasetAssetApi.listFiles()` 的文件级摘要。
9. 概览默认仍不展示 UUID、Dataset Asset ID、Study ID、mount_name、mount_id、dataset_version_id、upload endpoint 等技术字段。

#### 验证结果

已运行：

```text
npm run typecheck
```

结果：通过。

已运行：

```text
npm run build
```

结果：通过。构建仍有既有 Vite CJS API deprecation、`litegraph.js` eval、chunk size 警告；未发现本步骤引入的编译错误。

浏览器检查 `http://127.0.0.1:63241/datasets`：

- 默认进入 `概览` 标签页。
- 概览中可见 `数据集名称`、`code`、`状态`、`可见性`、`最近更新时间`、`文件总数`、`原始文件数`、`BIDS 逻辑视图数量`、`标准 FIF 数量`、`体量`。
- 概览中可见 `当前判断` 和 `后续处理`，用于表达是否可继续导入或进入后续处理。
- 默认概览中未出现 `Dataset Asset ID`、`Study ID`、`mount_id`、`mount_name`、`upload endpoint`、`dataset_version_id`。
- 当前环境下文件索引读取失败时，概览显示“文件摘要待确认 / 暂缓处理”，没有把错误当成已导入状态。

#### 兼容说明

本步骤只调整概览层的展示和计算文案，不改变 Dataset-first 创建、挂载、上传、文件索引读取接口，不改变 `DatasetUploadContext` 和上传 payload。

#### 遗留问题

1. 当前概览仍只能基于文件级摘要判断，无法展示 subjects/recordings 聚合；后续可在 Records 视图或后端聚合接口补齐。
2. 文件索引读取失败时只能给出“待确认”判断，后续需要在文件索引页提供更清晰的刷新、错误原因和恢复动作。
3. “进入 QC 或 Pipeline”目前是文案层判断，尚未增加直接跳转动作。

### 第 05 步：文件索引默认摘要化，明细进入独立区域

#### 需要改进的内容

- 概览页不再逐行展示 `recentSelectedAssetFiles`。
- 新增“文件索引”页内标签或抽屉。
- 文件索引明细支持：
  - 角色筛选
  - 关键词搜索
  - 默认限制显示数量
  - “显示更多”或分页
- 每行默认展示短路径或文件名，完整逻辑路径进入展开详情。
- 不展示服务器绝对路径。

#### 涉及文件

- `frontend/elys-web/src/views/ImportPage.vue`
- `frontend/elys-web/src/api/datasetAssets.ts` 如需要增加查询参数

#### 验证方式

- `npm run typecheck`
- `npm run build`
- 浏览器检查 720 条文件时主概览不被路径列表占满。

#### Codex 提示词

```text
第05步：请把 Dataset working 文件索引从主概览中移出。主概览只保留文件角色摘要和“查看文件索引”入口；新增或完善“文件索引”页内区域，支持按文件角色筛选、关键词搜索、限制默认展示数量，并提供显示更多或分页体验。每行默认展示短文件名或短逻辑路径，完整 logical_path 放到展开详情，不展示服务器绝对路径。保持 datasetAssetApi.listFiles() 调用兼容。完成后运行 npm run typecheck、npm run build，并浏览器检查文件很多时页面仍简洁。把运行结果在日志文档中同步更新
```

#### 第 05 步执行记录

文档更新时间：2026-05-23 01:08:52 +08:00。

本步骤已完成。实际改动集中在 `frontend/elys-web/src/views/ImportPage.vue`：

- 主概览继续只保留文件角色摘要，并新增“查看文件索引”入口，避免默认铺开逐文件路径。
- `文件索引` 页内区域新增关键词搜索、文件角色筛选、当前结果计数和默认展示数量限制。
- 默认最多展示 30 条文件记录，超过后通过“显示更多”逐批展开，每次增加 30 条。
- 文件行默认只展示短逻辑路径或短文件名、文件角色和体量；完整 `logical_path`、`relative_path`、`sha256`、写入时间等信息放入展开详情。
- 展示层不输出 `storage_uri`，也不展示服务器绝对路径；`datasetAssetApi.listFiles(assetId, { version_label: 'working' })` 调用保持兼容，没有新增后端接口要求。

验证结果：

- `npm run typecheck`：通过。
- `npm run build`：通过。仍有既有 Vite CJS API deprecated、`litegraph.js` eval、Pipeline chunk 大小警告，本步骤未新增这些警告。
- 浏览器检查 `/datasets`：概览页有“查看文件索引”入口，默认 `.dataset-file-row` 数量为 0，未在概览铺开文件明细；文件索引页可打开并显示摘要、刷新和错误/空状态。

浏览器验证限制：

- 当前本地/浏览器环境中，两个数据集的 working 文件索引接口均返回“文件索引读取失败”，因此没有真实 720 条文件列表可供页面现场渲染验证。
- 代码层已通过 `visibleAssetFiles = filteredAssetFiles.slice(0, fileDisplayLimit)` 将默认展示限制为 30 条，并通过 `hiddenAssetFileCount` 控制“显示更多”；真实文件索引恢复后，文件多时不会默认铺满主界面。

下一步建议：

- 第 06 步继续压缩“当前导入目标”和 Dataset-first 说明，将普通视图里的 Study/mount 技术语义继续收敛到技术信息区。
- 若后续仍出现文件索引读取失败，需要单独排查 `GET /dataset-assets/{assetId}/files?version_label=working` 的后端响应、鉴权和 working version 关联状态。

### 第 06 步：简化当前导入目标与 Dataset-first 说明

#### 需要改进的内容

- 当前导入目标只展示：
  - 数据集名称
  - 处理工作空间名称
  - ready 状态
  - 继续导入按钮
- 不默认展示 Study ID、mount_id、Dataset Asset ID。
- 将“配套 Study”文案调整为“处理工作空间”，避免用户误以为 Dataset 属于 Study。
- Dataset-first 说明收敛为一句短文案。

#### 涉及文件

- `frontend/elys-web/src/views/ImportPage.vue`
- `frontend/elys-web/src/components/BidsUploadPanel.vue`

#### 验证方式

- `npm run typecheck`
- `npm run build`
- 浏览器检查新建 Dataset 后导入目标可见，但技术字段不显眼。

#### Codex 提示词

```text
第06步：请简化 Dataset 页面当前导入目标和 Dataset-first 说明。当前导入目标默认只展示数据集名称、处理工作空间名称、ready 状态和继续导入动作，不展示 Study ID、mount_id、Dataset Asset ID。将页面文案中的“配套 Study”在普通视图中改为“处理工作空间”，技术信息区可以保留 Study 字段。BidsUploadPanel 顶部说明收敛为一句用户语言，避免长段技术链条。完成后运行 npm run typecheck、npm run build，并浏览器检查新建或选择数据集后的导入目标展示。把运行结果在日志文档中同步更新
```

#### 第 06 步执行记录

文档更新时间：2026-05-23 01:17:02 +08:00。

本步骤已完成。实际改动：

- `frontend/elys-web/src/views/ImportPage.vue`
  - 普通视图中的“配套 Study”口径改为“处理工作空间”。
  - 导入页顶部目标说明收敛为“导入目标已准备好 / 尚未准备导入目标”。
  - ready 状态下按钮改为“继续导入”，滚动到上传组件；未 ready 时仍为“准备导入目标”。
  - 当前导入目标摘要只展示数据集、处理工作空间、导入状态，不展示 Study ID、Dataset Asset ID、mount_id、mount_name。
  - 自动创建的工作空间名称从“xxx Study”调整为“xxx 处理工作空间”；既有名称如果以 `Study` 结尾，普通视图显示为“处理工作空间”。
  - 高级设置中的挂载说明改为“默认 primary；通常不需要调整。”
- `frontend/elys-web/src/components/BidsUploadPanel.vue`
  - 顶部说明收敛为一句用户语言：“上传会写入某数据集的 working 版本”或“请先准备导入目标”。
  - 移除默认显示的 `Dataset-first 导入` 说明块。
  - 目标上下文仅保留数据集、处理工作空间、目标状态。
  - 缺少目标时的错误文案从“缺少 Dataset 导入目标 / Dataset-first 上传”改为“缺少导入目标 / 无法提交上传”。

验证结果：

- `npm run typecheck`：通过。说明：曾在与 `npm run build` 并行执行时出现一次 `Dashboard.vue` 的瞬时 `runQueueDetail` 诊断，复核文件中函数存在，单独复跑 `npm run typecheck` 已通过。
- `npm run build`：通过。仍有既有 Vite CJS API deprecated、`litegraph.js` eval、Pipeline chunk 大小警告，本步骤未新增这些警告。
- 浏览器检查 `/datasets` 的“导入”页：
  - 可看到数据集、处理工作空间、目标状态和“准备导入目标 / 继续导入”动作。
  - 普通导入页未出现 `Dataset Asset ID`、`Study ID`、`mount_id`、`mount_name`、`Dataset-first`、`配套 Study`。
  - 当前浏览器环境点击“准备导入目标”返回 `mock route not found`，因此未能在浏览器中完成真实 ready 目标创建；ready 状态展示已通过组件逻辑和代码检查覆盖。

兼容说明：

- 本步骤未改变 `DatasetUploadContext`、上传 payload、`datasetAssetApi.bootstrap()` 或 `datasetApi.upload()` 的调用契约。
- Study / mount 技术字段仍保留在“技术信息”页，便于排障和大模型追溯。

下一步建议：

- 第 07 步继续压缩 `BidsUploadPanel.vue` 的导入组卡片，把批量导入队列从大块卡片改成紧凑行。

### 第 07 步：将导入组卡片改造成紧凑队列

#### 需要改进的内容

- `BidsUploadPanel` 中每组文件从大块卡片改为紧凑行。
- 一行展示：
  - 勾选框
  - 格式标签
  - subject
  - task
  - session/run 简写
  - 文件数
  - 状态
  - 进度
  - 展开按钮
- 默认收起文件列表和阶段详情。
- 失败项自动展开，成功项保持收起。

#### 涉及文件

- `frontend/elys-web/src/components/BidsUploadPanel.vue`

#### 验证方式

- `npm run typecheck`
- `npm run build`
- 浏览器选择多文件后检查队列密度。

#### Codex 提示词

```text
第07步：请把 BidsUploadPanel.vue 的导入组展示从大块卡片改为紧凑队列。一行代表一组 Recording，默认展示勾选框、格式、subject、task、session/run、文件数、状态、进度和展开按钮；文件组成、阶段结果、错误详情和原始路径只在展开行中显示。成功项默认收起，失败项自动展开。保留 BrainVision/EDF/BDF 分组逻辑、重复 Recording 新版本确认、进度条和现有上传 API。完成后运行 npm run typecheck、npm run build，并浏览器检查批量选择几十组文件时页面高度明显收敛。把运行结果在日志文档中同步更新
```

#### 第 07 步执行记录

文档更新时间：2026-05-23 01:27:48 +08:00。

本步骤已完成。实际改动：

- `frontend/elys-web/src/components/BidsUploadPanel.vue`
  - 将每个导入组从大块卡片改为紧凑行。
  - 默认行展示：勾选框、格式标签、subject、task、session/run、文件数、状态、进度条和展开按钮。
  - 新增 `UploadGroup.expanded` 状态。
  - EDF/BDF/BrainVision 合法组默认收起；不可导入组默认展开。
  - 上传成功后自动收起；上传失败、缺少导入目标、重复 Recording 待确认时自动展开。
  - subject/task/session/run 的编辑入口移入展开详情。
  - 文件组成、每个文件的相对路径、状态详情、错误提示、处理阶段和导入结果摘要移入展开详情。
  - 默认行不再显示 EDF/BDF 文件名，避免批量选择后被文件名刷屏。
- `frontend/elys-web/src/style.css`
  - 重写 `.bids-group` 相关样式为一行式队列。
  - 新增 `.bids-group__row`、`.bids-group__details`、`.bids-group__detail-grid`、`.bids-group__file-summary`、`.bids-group__status-detail` 等样式。
  - 响应式下队列行、实体编辑和展开详情改为单列，避免窄屏挤压。

保留能力：

- BrainVision `.vhdr / .eeg / .vmrk` 三件套分组逻辑未改。
- EDF/BDF 单文件分组逻辑未改。
- 重复 Recording 新版本确认弹窗未改。
- `datasetApi.upload()` 参数、进度回调、`replaceExisting`、`datasetAssetId`、`mountName` 上传契约未改。
- 批量导入总进度、单组上传进度和原有错误处理继续保留。

验证结果：

- `npm run typecheck`：通过。说明：并行执行时曾出现一次 `Dashboard.vue` 的瞬时旁路诊断，单独复跑后通过。
- `npm run build`：通过。仍有既有 Vite CJS API deprecated、`litegraph.js` eval、Pipeline chunk 大小警告，本步骤未新增这些警告。
- 浏览器检查 `/datasets` 的“导入”页：页面可正常打开，上传组件、拖拽区、空状态和导入按钮正常显示。

浏览器验证限制：

- 当前 Codex in-app browser 运行时无法构造 `File` / `DataTransfer`，也无法改写隐藏 file input 的 `files` 属性，因此没有办法在浏览器中真实模拟“几十组文件选择”。
- 已尝试通过合成文件和 DOM 注入方式验证，但该浏览器 evaluate 环境限制 DOM 写入能力，无法完成批量队列现场渲染。
- 因此“几十组文件时页面高度明显收敛”的验证主要来自代码结构、CSS 网格和编译检查；真实文件选择建议在本地浏览器手动选择包含几十个 EDF/BDF 的文件夹后复核。

下一步建议：

- 第 08 步继续优化批量导入总进度和失败处理，在紧凑队列基础上增加“全部 / 待导入 / 失败 / 已完成”筛选和批量动作。

### 第 08 步：优化批量导入总进度和失败处理

#### 需要改进的内容

- 总进度固定在导入队列顶部或底部。
- 明确显示：
  - 总组数
  - 可导入
  - 已完成
  - 失败
  - 当前处理第几组
- 增加快捷筛选：
  - 全部
  - 只看待导入
  - 只看失败
  - 只看已完成
- 增加批量动作：
  - 全选可导入
  - 取消选择
  - 重试失败
  - 清空已完成

#### 涉及文件

- `frontend/elys-web/src/components/BidsUploadPanel.vue`

#### 验证方式

- `npm run typecheck`
- `npm run build`
- 浏览器模拟多组上传前后的状态筛选。

#### Codex 提示词

```text
第08步：请优化 BidsUploadPanel.vue 的批量导入总进度和失败处理。总进度应在导入队列顶部或底部稳定可见，显示总组数、可导入、已完成、失败和当前处理第几组；增加队列筛选“全部、待导入、失败、已完成”；增加批量动作“全选可导入、取消选择、重试失败、清空已完成”。不要改变 datasetApi.upload() 的调用契约，不破坏重复 Recording 新版本导入确认。完成后运行 npm run typecheck、npm run build，并浏览器检查批量导入交互。把运行结果在日志文档中同步更新
```

#### 第 08 步执行记录

文档更新时间：2026-05-23 01:33:40 +08:00。

本步骤已完成。实际改动：

- `frontend/elys-web/src/components/BidsUploadPanel.vue`
  - 新增队列顶部 `bids-queue-panel`，在有导入组时稳定显示总进度。
  - 总进度展示总组数、可导入、已完成、失败、当前处理第几组。
  - 新增队列筛选：`全部`、`待导入`、`失败`、`已完成`，并显示每类数量。
  - 新增批量动作：`全选可导入`、`取消选择`、`重试失败`、`清空已完成`。
  - 将“可导入”收紧为合法且 `status === ready` 的组，失败组需要点“重试失败”后回到待导入队列，避免失败后被误提交。
  - `重试失败` 只处理合法但上传失败的组，会重置状态为 ready、选中并折叠；不可导入的 invalid 组仍保留在失败筛选中等待用户处理文件选择。
  - `清空已完成` 只移除 `done` 组，不影响失败、待导入和重复确认组。
  - 底部上传按钮继续使用原来的 `uploadSelectedGroups()`，只是文案改为新的总进度百分比。
- `frontend/elys-web/src/style.css`
  - 新增队列面板、统计格、筛选按钮、批量动作和紧凑空态样式。
  - 窄屏下队列统计、筛选和动作自动改为单列/纵向排列，避免按钮挤压。

保留能力：

- 未改变 `datasetApi.upload()` 调用契约。
- 未改变 `replaceExisting`、重复 Recording 新版本确认弹窗和确认后的上传流程。
- 未改变 BrainVision/EDF/BDF 分组逻辑。
- 原有单组进度、批量进度、失败提示、成功后刷新 `uploaded` 事件继续保留。

验证结果：

- `npm run typecheck`：通过。说明：并行执行时曾出现一次 `Dashboard.vue` 的瞬时旁路诊断，单独复跑后通过。
- `npm run build`：通过。仍有既有 Vite CJS API deprecated、`litegraph.js` eval、Pipeline chunk 大小警告，本步骤未新增这些警告。
- 浏览器检查 `/datasets` 的“导入”页：页面可正常打开，上传组件、拖拽区、空状态和导入按钮正常显示；空队列时队列工具条不会误显示。

浏览器验证限制：

- 当前 Codex in-app browser 仍无法构造真实 `File` / `DataTransfer` 或向隐藏 file input 注入 `FileList`，因此无法自动模拟几十组文件选择后的筛选与批量动作。
- 真实批量交互建议在本地浏览器手动选择几十个 EDF/BDF 文件后验证：筛选数量、全选可导入、取消选择、重试失败、清空已完成和总进度显示。

下一步建议：

- 第 09 步继续优化 subject、task、session、run 的编辑效率，在当前队列筛选基础上增加批量应用默认值和更紧凑的行内编辑体验。

### 第 09 步：优化 subject/task/session/run 编辑效率

#### 需要改进的内容

- 默认队列行不应被四个输入框撑大。
- 支持行内点击编辑或紧凑输入。
- 增加批量默认值应用：
  - 默认 task
  - 默认 session
  - 默认 run
- 对从文件名识别出的 subject/task 保持自动填充。
- 对无效项突出标识，并显示最短错误原因。

#### 涉及文件

- `frontend/elys-web/src/components/BidsUploadPanel.vue`

#### 验证方式

- `npm run typecheck`
- `npm run build`
- 浏览器检查 EDF/BDF/BrainVision 文件选择后的字段编辑。

#### Codex 提示词

```text
第09步：请优化 BidsUploadPanel.vue 中 subject、task、session、run 的编辑效率。队列默认不要被四个大输入框撑高；支持紧凑行内编辑或点击后编辑；保留从文件名自动识别 subject/task 的逻辑；默认 task/session/run 可批量应用到待导入组；无效项要在行内突出并显示最短错误原因。不要破坏 BrainVision 三件套校验和 EDF/BDF 单文件导入。完成后运行 npm run typecheck、npm run build，并浏览器检查多组文件的编辑效率。把运行结果在日志文档中同步更新
```

#### 第 09 步执行记录

文档更新时间：2026-05-23 01:44:00 +08:00

实际改动：

- `frontend/elys-web/src/components/BidsUploadPanel.vue`
  - 将队列行中的 subject、task、session、run 改为紧凑行内编辑控件，不再在展开区放置四个大输入框。
  - 保留从文件名自动识别 subject/task/session/run 的 `inferEntities()` 逻辑，BrainVision 三件套、EDF/BDF 单文件分组逻辑未改动。
  - 在 BIDS 默认值区域新增“应用到待导入组”，可把默认 task/session/run 批量应用到有效且尚未导入的组；task 默认值为空时不覆盖已有 task，session/run 可批量清空。
  - `readyGroups` 增加 subject/task 必填判断，用户清空 subject 或 task 后该组不再计入可导入；行内显示“缺少 subject / 缺少 task”等最短原因。
  - 无效格式、BrainVision 缺少关联文件、重复 Recording 待确认等状态在队列行内显示短原因，详细说明仍保留在展开详情。
- `frontend/elys-web/src/style.css`
  - 调整导入队列行栅格，让一行同时容纳勾选、格式、四个 BIDS 实体、文件数、状态、进度和展开按钮。
  - 新增紧凑输入、无效态边框、短错误原因颜色、默认值批量操作按钮组样式。

验证结果：

- `npm run typecheck`：通过。
- `npm run build`：通过。
- in-app browser 检查 `/datasets`：页面可打开；切换到“导入”页签正常；展开 “BIDS 实体默认值” 后可见默认 task/session/run 和“应用到待导入组”按钮。

浏览器检查限制：

- 当前 Codex in-app browser 无法构造真实本地 `File` / `DataTransfer`，也无法把 `FileList` 注入隐藏 file input，因此不能自动模拟几十组 EDF/BDF/BrainVision 文件选择后的真实队列行。
- 多组文件行内编辑效率、BrainVision 三件套真实选择、EDF/BDF 单文件真实导入建议在本地浏览器手动复核。

未完成项：

- 未改变 `datasetApi.upload()` 调用契约，未新增后端接口。
- 未做真实上传回归；需要配合本地文件选择和后端可用环境继续验证。

下一步建议：

- 第 10 步统一导入阶段和结果摘要文案，把普通用户视图进一步从 original upload / Raw BIDS / canonical FIF / dataset_files 收敛为“原始上传、BIDS 逻辑视图、标准 FIF、文件索引”。

### 第 10 步：统一导入阶段文案和结果摘要

#### 需要改进的内容

- 普通视图使用：
  - 原始上传
  - BIDS 逻辑视图
  - 标准 FIF
  - 文件索引
- 技术视图可保留：
  - original upload
  - Raw BIDS
  - canonical FIF
  - dataset_files
- 每组导入成功后只显示简洁结果：
  - 已导入
  - 已生成标准 FIF
  - 文件索引已更新
- 详细 API 返回信息进入展开区。

#### 涉及文件

- `frontend/elys-web/src/components/BidsUploadPanel.vue`
- `frontend/elys-web/src/views/ImportPage.vue`

#### 验证方式

- `npm run typecheck`
- `npm run build`
- 浏览器检查导入完成后的文案。

#### Codex 提示词

```text
第10步：请统一 Dataset 导入阶段文案和结果摘要。普通视图使用“原始上传、BIDS 逻辑视图、标准 FIF、文件索引”等用户语言；技术展开区可以保留 original upload、Raw BIDS、canonical FIF、dataset_files。每组导入成功后默认只显示“已导入、已生成标准 FIF、文件索引已更新”等简洁摘要，详细 API 返回计数和技术字段放入展开详情。完成后运行 npm run typecheck、npm run build，并浏览器检查导入完成状态。把运行结果在日志文档中同步更新
```

#### 第 10 步执行记录

文档更新时间：2026-05-23 01:50:37 +08:00

实际改动：

- `frontend/elys-web/src/components/BidsUploadPanel.vue`
  - 普通导入视图的阶段条改为“原始上传 / BIDS 逻辑视图 / 标准 FIF / 文件索引”。
  - 上传状态文案从 `original upload`、`Raw BIDS`、`canonical FIF`、`dataset_files` 收敛为“原始数据、BIDS 逻辑视图、标准 FIF、文件索引”。
  - 每组导入成功后的行内状态从 `100%` 改为用户摘要：`已导入 · 已生成标准 FIF · 文件索引已更新`；如果接口未返回标准 FIF 或文件索引计数，则显示“状态待确认 / 待查询”。
  - 展开详情继续保留技术名和 API 计数：`original upload`、`Raw BIDS`、`canonical FIF`、`dataset_files`、`API response`。
  - 重复 Recording 弹窗和全局成功/错误提示同步改为“原始上传版本、BIDS 逻辑视图、标准 FIF、文件索引”等用户语言。

验证结果：

- `npm run typecheck`：通过。
- `npm run build`：通过。仍有既有 Vite CJS API deprecated、`litegraph.js` eval、Pipeline chunk 体积警告，本步骤未新增这些警告。
- in-app browser 检查 `/datasets` 的“导入”页：页面可打开，普通视图可见“导入到数据集工作版本”和“原始上传 / BIDS 逻辑视图 / 标准 FIF / 文件索引”，未在普通阶段条中暴露 `original upload`、`Raw BIDS`、`canonical FIF`、`dataset_files`。

浏览器检查限制：

- 当前 Codex in-app browser 仍无法构造真实本地 `File` / `DataTransfer` 或向隐藏 file input 注入 `FileList`，因此无法自动触发真实上传完成状态。
- 导入完成后的真实行内摘要、展开详情 API 计数和重复 Recording 新版本弹窗，仍建议用本地浏览器手动选择 EDF/BDF/BrainVision 文件后复核。

下一步建议：

- 第 11 步增加 Records 视图，让 Dataset 页面从“文件路径视角”进一步转为“Recording 视角”。

### 第 11 步：增加 Records 视图，弱化文件名视角

#### 需要改进的内容

- Dataset 页应让用户更多看到 Recording，而不是文件名。
- 增加 Records 标签页或区域。
- 如果已有 `recordingApi.list()` 可用，按当前 Dataset Asset 查询 Recording。
- 展示：
  - subject
  - task
  - session
  - run
  - source format
  - 当前版本
  - QC 状态
  - 最近更新时间
- 文件列表作为 Recording 的详情。

#### 涉及文件

- `frontend/elys-web/src/views/ImportPage.vue`
- `frontend/elys-web/src/api/datasetAssets.ts`
- `frontend/elys-web/src/types/index.ts`

#### 验证方式

- `npm run typecheck`
- `npm run build`
- 浏览器检查 Dataset 选中后能查看 Recording 视角。

#### Codex 提示词

```text
第11步：请在 Dataset 页面增加 Records 视图，让用户以 Recording 而不是逐文件路径管理数据。优先复用 recordingApi.list()，按当前 Dataset Asset 或当前 Study mount 上下文查询 Recording；展示 subject、task、session、run、source format、当前版本、QC 状态和最近更新时间。文件列表只作为 Recording 的展开详情，不要在概览中铺开。若现有 API 无法完整支持，请先实现可兼容的空态和错误态，并记录需要后端补充的字段。完成后运行 npm run typecheck、npm run build，并浏览器检查 Records 入口。把运行结果在日志文档中同步更新
```

#### 第 11 步执行记录

文档更新时间：2026-05-23 01:58:35 +08:00

实际改动：

- `frontend/elys-web/src/views/ImportPage.vue`
  - 将原占位 Records 页签改为可用的 Recording 视图。
  - Records 视图优先按当前 `Dataset Asset` + 当前导入目标/Study mount 上下文调用 `recordingApi.list()`。
  - 若当前数据集还没有处理工作空间上下文，显示“请先准备导入目标”的兼容空态，不误导用户。
  - Recording 默认行展示：subject、task、session、run、source format、当前版本、QC 状态、最近更新。
  - 文件列表只在单条 Recording 展开后通过 `recordingApi.listFiles()` 按需读取；默认概览不铺开文件路径。
  - 增加 Records 统计栏：Recording 总数、标准 FIF 数、QC 通过数、查询上下文。
  - 增加 Records 错误态和单条 Recording 文件列表错误态，便于后端能力不完整时兼容显示。
- `frontend/elys-web/src/api/datasetAssets.ts`
  - `RecordingListParams` 增加 `mount_id`、`mount_name`，用于兼容 Study mount 查询模型。

验证结果：

- `npm run typecheck`：通过。
- `npm run build`：通过。仍有既有 Vite CJS API deprecated、`litegraph.js` eval、Pipeline chunk 体积警告，本步骤未新增这些警告。
- in-app browser 检查 `/datasets`：`Records` 页签存在且可进入；可见 “Records” 面板、Recording 统计栏、刷新按钮和兼容空态/错误态。

后端字段与接口风险：

- 当前前端可展示 `Recording` 类型中已有字段：`bids_subject_id`、`subject_id`、`session`、`task`、`run`、`source_format`、`current_version_id/current_version_seq`、`fif_path`、`qa_status`、`imported_at`。
- 如果后端希望 Records 视图更完整，建议后续补充或确认：`updated_at`、`recording.files_count`、`recording.current_version_status`、`recording.mount_id/mount_name`、`recording.dataset_file_count`、`recording.qc_summary`。
- `recordingApi.listFiles(studyId, recordingId)` 如果无法按 mounted Dataset 返回文件，展开详情会显示接口错误或空态；后续需要后端继续保证外部挂载 Dataset Recording 的文件可见性。

下一步建议：

- 第 12 步做视觉精修和响应式整理，重点检查 Records 行、文件索引行、导入队列在窄屏下是否换行自然且不重叠。

### 第 12 步：视觉精修与响应式整理

#### 需要改进的内容

- 保持功能型网站的冷静、清晰、精致。
- 减少大面积说明块。
- 卡片圆角控制在 8px 左右。
- 统一按钮、标签、状态色。
- 移动端和窄屏下：
  - 数据集目录可折叠或置顶筛选
  - 队列行可换行但不重叠
  - 长文本截断并可展开
- 避免一屏内多个同权重视觉块争抢注意力。

#### 涉及文件

- `frontend/elys-web/src/views/ImportPage.vue`
- `frontend/elys-web/src/components/BidsUploadPanel.vue`
- 可能涉及 `frontend/elys-web/src/style.css`

#### 验证方式

- `npm run typecheck`
- `npm run build`
- 浏览器检查桌面宽屏、普通桌面、窄屏。

#### Codex 提示词

```text
第12步：请对 Dataset 页面做视觉精修和响应式整理。整体风格保持功能型数据处理网站的简洁、精致、克制；减少大面积说明块，统一按钮、标签、状态色和间距，卡片圆角控制在 8px 左右；确保桌面宽屏、普通桌面和窄屏下文本不重叠、队列不撑破、长路径默认截断并可展开。不要引入装饰性渐变或无关视觉元素。完成后运行 npm run typecheck、npm run build，并用浏览器检查 /datasets 的桌面和窄屏效果。把运行结果在日志文档中同步更新
```

#### 执行记录

文档生成时间：2026-05-23 02:10:30 +08:00

本步已完成。实际改动如下：

- `frontend/elys-web/src/views/ImportPage.vue`
  - Dataset 工作台、概览卡片、导入目标、文件索引和 Records 相关区域的圆角统一收敛到约 8px。
  - 去掉 Dataset 导入目标块的装饰性渐变背景，改为克制的浅底色与状态边框。
  - 缩小主概览卡片、导入目标、文件索引面板和 Records 面板的内边距，降低大面积说明块的视觉重量。
  - `dataset-overview`、`dataset-summary-grid`、`dataset-file-stats`、`dataset-record-stats` 改为 `auto-fit + minmax`，避免普通桌面和窄屏下固定列数挤压。
  - Records 行在 1280px 以下增加换行规则，文件索引工具条在中等宽度下从 3 列回落到 2 列，760px 以下统一单列。
- `frontend/elys-web/src/style.css`
  - BIDS 上传面板圆角统一到约 8px，整体 padding 收紧。
  - 上传 dropzone 去掉装饰性渐变背景，改为浅底色；高度和 padding 收敛。
  - 批量队列摘要改为自适应列宽。
  - 批量导入队列在 1320px 以下将进度条稳定换到下一行，在 980px 以下进一步压成安全的多行结构，避免 subject/task/session/run 和状态列把队列撑破。

验证结果：

- `npm run typecheck`：通过。
- `npm run build`：通过。仍存在项目原有的 Vite CJS API deprecated、`litegraph.js` eval、Pipeline chunk 超 500kB 提示，本步未引入新的构建错误。
- 浏览器检查 `/datasets`：
  - 1280x800 导入页：无横向溢出，工作台、导入目标、上传面板、dropzone 圆角均为 8px，导入目标和 dropzone `background-image: none`。
  - 390x800 导入页：无横向溢出，工作台单列，dropzone 单列，文本未检测到撑破页面。
  - Records 和文件索引入口在 1280x800 与 390x800 下均无横向溢出；当前环境中文件索引 API 返回“文件索引读取失败”，因此未能用真实文件行做浏览器级长路径样本验证，已通过 CSS 规则保留默认截断和展开详情。
  - 内置浏览器截图命令本次超时，因此浏览器验收使用 viewport、DOM 和 computed style 指标完成。

遗留风险：

- 批量队列真实几十组文件的视觉高度、成功/失败/重试状态仍需要在真实文件选择后做一次人工验收；当前内置浏览器无法注入本地 `FileList` 完成真实选择。
- 文件索引 API 当前失败时无法直接验证真实 720 条路径列表的视觉表现；后续 API 正常后建议补一次文件索引真实长列表回归。

### 第 13 步：端到端回归 Dataset 创建与导入主流程

#### 需要改进的内容

- 回归新建 Dataset。
- 回归自动准备处理工作空间。
- 回归选择文件、选择文件夹、拖拽文件。
- 回归 EDF/BDF/BrainVision 分组。
- 回归批量导入进度。
- 回归重复 Recording 新版本确认。
- 回归导入完成后刷新概览、Records、文件索引摘要。
- 检查默认页面不暴露技术 ID。

#### 涉及文件

- `frontend/elys-web/src/views/ImportPage.vue`
- `frontend/elys-web/src/components/BidsUploadPanel.vue`
- 相关 API 类型和测试文件，如后续新增

#### 验证方式

- `npm run typecheck`
- `npm run build`
- 浏览器检查 `/datasets`
- 如后端测试受影响，运行相关 pytest

#### Codex 提示词

```text
第13步：请对 Dataset 页面简洁化改造做端到端回归。重点验证新建 Dataset、自动准备处理工作空间、选择文件、选择文件夹、拖拽文件、EDF/BDF/BrainVision 分组、批量导入进度、重复 Recording 新版本确认、导入完成后刷新概览/Records/文件索引摘要，以及默认页面不暴露技术 ID。运行 npm run typecheck、npm run build；如发现后端契约或测试受影响，运行对应 pytest 并说明。把验证结果、问题清单、遗留风险和下一步建议写入本日志。把运行结果在日志文档中同步更新
```

#### 执行记录

文档生成时间：2026-05-23 10:23:52 +08:00

本步执行的是回归验证，未修改业务代码。当前浏览器页面为 `http://127.0.0.1:63241/datasets`，其 `/api/v1/dataset-assets` 和 `/api/v1/projects` 返回 mock 数据；`/api/v1/dataset-assets/bootstrap` 在当前运行服务中返回 404。

验证结果：

- `npm run typecheck`：通过。
- `npm run build`：通过。仍有项目既有警告：Vite CJS Node API deprecated、`litegraph.js` eval、`PipelinePage` chunk 超 500kB。
- 后端相关 pytest：
  - 首次运行因 Windows 默认 pytest 临时目录 `C:\Users\Administrator\AppData\Local\Temp\pytest-of-Administrator` 无权限而在 setup 阶段失败，未形成业务结论。
  - 改用项目内临时目录后通过：`python -m pytest --basetemp .codex-pytest-tmp -p no:cacheprovider tests/test_dataset_bootstrap_service.py tests/test_dataset_upload_storage_paths.py tests/test_recording_mount_visibility.py tests/test_load_data_run_input_snapshots.py`
  - 结果：24 passed，32 warnings。warnings 主要为 Pydantic class-based config deprecated 和 `datetime.utcnow()` deprecated。
- 浏览器默认页：
  - `/datasets` 可打开，显示数据集目录、数据集工作台、概览、导入、Records、文件索引、技术信息入口。
  - 默认概览页未暴露 Dataset UUID、Study ID、mount_id、dataset_version_id、upload endpoint 等技术字段。
  - “技术信息”页签可按需查看技术追溯字段，符合“默认隐藏、按需展开”的口径。
- 新建 Dataset：
  - 表单可打开，可填写数据集名称、code、描述、mount name。
  - 点击“创建并准备导入”后当前 mock API 返回 `Not found`，未创建成功，未进入导入目标 ready 状态。
- 自动准备处理工作空间：
  - 对已有 `Resting EEG Dataset` 点击“准备导入目标”后同样返回 `Not found`。
  - 真实后端代码和 pytest 显示 bootstrap service/route、Study 创建、mount、working Dataset Version、next_upload 契约存在并通过测试；当前失败点是浏览器所连 mock API 未覆盖该契约。
- 导入页：
  - “导入”页可打开，存在 `BidsUploadPanel`。
  - 文件选择入口存在两个 file input：普通多文件选择 `multiple=true`，文件夹选择 `multiple=true` 且 `webkitdirectory=true`。
  - 上传区文案覆盖 BrainVision `.vhdr/.eeg/.vmrk` 组合以及 EDF/BDF 单文件导入。
  - 在导入目标未准备好时，上传面板提示“请先准备导入目标；文件可以先选择，目标就绪后再提交”，未暴露技术 ID。
- Records / 文件索引：
  - Records 页签可打开；未准备导入目标时显示“查询上下文未准备”，不会误铺文件路径。
  - 文件索引页签可打开；当前 mock API 下显示“文件索引读取失败，请确认该数据集是否已完成导入或稍后重试。”

问题清单：

1. 当前浏览器回归环境使用 mock API，未实现 `POST /api/v1/dataset-assets/bootstrap`，导致新建 Dataset 和自动准备处理工作空间端到端失败。
2. 当前 mock API 不能完整支撑 Study mount、Dataset files、Recording 查询的真实回归，因此“导入完成后刷新概览 / Records / 文件索引摘要”只能验证页面入口和空态，不能验证成功态。
3. 当前内置浏览器自动化无法注入本地 `FileList` 或完成系统文件选择对话框，因此“选择文件、选择文件夹、拖拽文件、EDF/BDF/BrainVision 分组、批量导入进度、重复 Recording 新版本确认”未能做真实文件级端到端验收。
4. 文件索引 API 在当前环境返回失败，无法用真实长路径和多文件列表验证导入完成后的摘要刷新。

遗留风险：

- 如果线上或本地真实 FastAPI 服务未替换当前 mock API，用户会在 Dataset 页面遇到与本次一致的 `Not found`，表现为无法创建 Dataset-first 导入目标。
- 前端交互结构和后端单元测试都显示契约存在，但还缺一次“真实后端 + 真实文件 fixture + 真实上传”的端到端验收。
- 重复 Recording 新版本确认、批量进度和导入后刷新属于高价值路径，必须用真实 EDF/BDF/BrainVision fixture 补测。

下一步建议：

- 启动真实 FastAPI 后端替代当前 mock API，或补齐 mock API 的 `dataset-assets/bootstrap`、`projects POST`、`study_dataset_mounts`、`dataset files`、`recordings` 和上传响应。
- 用固定测试数据准备 1 组 EDF、1 组 BDF、1 组完整 BrainVision、1 组缺失 BrainVision 关联文件，做真实文件导入回归。
- 为浏览器 E2E 增加可自动设置文件的 Playwright 测试夹具，覆盖新建 Dataset、自动 ready、批量导入、重复 Recording 确认和导入后摘要刷新。
- 后续可单独清理 `datetime.utcnow()` deprecated warning，但它不阻塞本次 Dataset-first 契约验证。

## 5. 推荐执行顺序

推荐先执行第 01 到第 06 步，快速解决“页面不简洁”和“技术字段外露”的主要问题；再执行第 07 到第 10 步，解决批量导入效率；最后执行第 11 到第 13 步，补齐 Records 视角、视觉精修和回归。

更稳妥的分批方式：

- 第一批：第 01、02、03、04、05、06 步
- 第二批：第 07、08、09、10 步
- 第三批：第 11、12、13 步

第一批完成后，页面主观复杂度会明显下降；第二批完成后，文件多时的操作效率会明显提高；第三批完成后，Dataset 页面会更接近正式数据处理工作台。

## 6. 验收标准

完成改造后，Dataset 页面应满足以下标准：

1. 用户默认看不到 Dataset UUID、Study ID、mount_id。
2. 720 条文件索引不会默认铺满主界面。
3. 用户能在概览中快速判断数据集是否已导入、是否可继续导入。
4. 批量导入几十组文件时，导入队列仍然紧凑、可筛选、可定位失败项。
5. 技术追溯信息仍可在“技术信息”中找到。
6. 成功状态轻量，失败状态突出。
7. 页面默认语言面向数据处理用户，而不是面向数据库开发者。
8. `npm run typecheck` 和 `npm run build` 通过。
