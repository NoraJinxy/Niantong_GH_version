# image2 工作流九图提示词

> 用途：本文件用于重新生成 9 张工作流 PNG 图。参考 `wiki/docs/assets` 中 `access-routes.png`、`hybrid-overview.png`、`one-click-deploy.png`、`security-boundary.png`、`server-roles.png` 的视觉风格。
>
> 重要约束：本轮按用户要求，所有图内文字、箭头、状态名、表名、字段名、图例和说明都交给 image2 直接生成，不拆分为后期 SVG/Figma/PPT 叠加。

## 0. 全局画风约束

所有提示词都默认使用以下统一风格：

- 输出格式：PNG，横向 16:9，建议 1920x1080。
- 整体风格：白色或极浅蓝背景，干净、明亮、企业级软件架构信息图，类似 `access-routes.png`、`hybrid-overview.png`、`one-click-deploy.png`、`security-boundary.png`、`server-roles.png`。
- 标题风格：顶部居中大标题，深海军蓝，粗体中文，清晰可读。
- 版式风格：大模块、大图标、大箭头、大分区；模块之间留足空白；用颜色和边界表达职责。
- 文字风格：简体中文为主，必要技术名词保留英文；所有文字必须清晰、端正、无乱码、无伪字、无错别字。
- 模块颜色：前端/用户用蓝色；API/后端服务用青绿或绿色；执行器/计算引擎用青色；数据库用紫色；Redis/队列/缓存用橙色或红橙色；文件系统/Artifact 用灰蓝色；人工交互用紫色；失败/错误用红色。
- 箭头风格：粗箭头，箭头方向明确，每条关键箭头带短标签；普通流程用实线，状态回退/恢复用虚线，错误路径用红色箭头。
- 图标风格：使用清晰的服务器、浏览器、数据库圆柱、队列、文件夹、齿轮、锁、用户、闪电、检查、警告等图标；图标和文字绑定在同一个卡片中。
- 底部说明：每张图底部放 1 条醒目的结论栏，使用 1-3 句短句，不放长段落。
- 禁止事项：不要生成装饰性背景、渐变光斑、密密麻麻小字、过多交叉箭头、难以阅读的字段列表、没有标题的抽象框图、与本项目无关的组件。

## 1. workflow-01-overview.png：工作流整体架构总览

### 复制给 image2 的提示词

```text
请生成一张 1920x1080 横向 PNG 技术架构信息图，标题为“工作流整体架构总览”。

参考风格：
学习 access-routes.png、hybrid-overview.png、one-click-deploy.png、security-boundary.png、server-roles.png 的风格：白底、深蓝大标题、软阴影卡片、大图标、大箭头、颜色分区清晰。不要画成普通流程图，要像企业级系统架构讲解图。

画面主旨：
让技术人员一眼看懂：前端只负责编辑与展示；FastAPI 负责保存、校验和创建运行；PostgreSQL 是长期事实源；Redis/Celery 只做后台调度；PipelineExecutor 调用 EEG Engine；ArtifactStore 把 EEG 大文件写入项目文件系统；前端再读取状态和预览结果。

整体布局：
顶部是大标题“工作流整体架构总览”。
标题下方从左到右分成 6 个大模块卡片，使用粗箭头串联：
1. “科研用户 / 浏览器”
   - 图标：用户 + 浏览器窗口。
   - 小标签：Pipeline 编辑、节点参数、运行进度、输出预览。
2. “Vue 前端 / LiteGraph”
   - 图标：前端页面或画布。
   - 显示子模块：NodePalette、PipelineCanvas、PropertyPanel、RunPanel。
3. “FastAPI 工作流 API”
   - 图标：闪电 API。
   - 显示子模块：Pipeline CRUD、Validate、Run API、Event API。
4. “后端工作流核心”
   - 图标：齿轮组。
   - 显示子模块：NodeRegistry、PipelineValidator、PipelineExecutor、NodeDispatcher。
5. “EEG Engine”
   - 图标：脑电波或计算服务器。
   - 显示子模块：LoadData、Preprocess、ICA、Epoch、ERP / PSD / TFR。
6. “结果与观察”
   - 图标：图表 + 放大镜。
   - 显示子模块：输出预览、观察模块、统计分析、科研作图、机器学习。

在中下方画一个横向“基础设施层”，分成 3 个并列卡片：
A. “PostgreSQL 长期事实源”
   - 紫色边框，数据库图标。
   - 写清：pipeline_definitions、pipeline_runs、pipeline_node_runs、pipeline_artifacts。
B. “Redis + Celery 后台调度”
   - 橙色边框，队列图标。
   - 写清：任务队列、临时进度、Worker 心跳、事件通知。
C. “项目文件系统 / ArtifactStore”
   - 灰蓝色边框，文件夹图标。
   - 写清：fifdata、derivatives、cache、preview、logs。

箭头要求：
- Vue 前端 -> FastAPI 工作流 API，箭头标签：“保存 / 校验 / 创建 run”。
- FastAPI 工作流 API -> PostgreSQL，箭头标签：“写入 definition 和 run 快照”。
- FastAPI 工作流 API -> Redis + Celery，箭头标签：“投递后台任务”。
- Redis + Celery -> 后端工作流核心，箭头标签：“Worker 执行”。
- 后端工作流核心 -> EEG Engine，箭头标签：“按 NodeSpec 调用节点函数”。
- 后端工作流核心 -> ArtifactStore，箭头标签：“保存 EEG 输出和 metadata”。
- ArtifactStore -> PostgreSQL，箭头标签：“登记 artifact 索引”。
- PostgreSQL -> Vue 前端，虚线箭头标签：“轮询 / SSE 返回状态”。
- ArtifactStore -> 结果与观察，箭头标签：“预览和分析入口”。

底部结论栏：
在底部放一个浅蓝色横条，文字为：
“核心原则：数据库保存事实，Redis 只管调度，文件系统保存大对象，前端只展示后端返回的真实状态。”

视觉要求：
中文必须清晰可读，所有标签都要准确。模块数量不要再增加。箭头不要交叉。画面要有层次，但不要拥挤。
```

## 2. workflow-02-definition-contract.png：工作流定义与 NodeSpec 契约

### 复制给 image2 的提示词

```text
请生成一张 1920x1080 横向 PNG 技术信息图，标题为“工作流定义与 NodeSpec 契约”。

参考风格：
沿用 access-routes.png、server-roles.png 的大卡片和大图标风格。白底、深蓝大标题、软阴影、清晰分栏。不要做成密集 JSON 截图，要把 NodeSpec 如何约束前端、后端和运行结果讲清楚。

画面主旨：
让技术人员一眼看懂：NodeSpec 是节点契约；前端用它生成节点和参数面板；Validator 用它校验端口和参数；Executor/Dispatcher 用它找到后端函数；运行后通过 data_infos 和 artifact_infos 形成可追溯输出。

整体布局：
顶部大标题“工作流定义与 NodeSpec 契约”。
画面中央放一个最大的核心卡片，标题“NodeSpec 节点契约”，边框青绿色，图标为“文档 + 齿轮”。
核心卡片中分 6 个清晰字段区块，使用大字短标签：
1. type：eeg/filter/fir
2. inputs：eeg_data
3. outputs：eeg_data
4. properties：l_freq、h_freq、save_output
5. backend：module + function
6. cache / ui：hash 策略 + 颜色 + 预览类型

核心卡片左侧放 2 个蓝色前端卡片：
A. “节点库 NodePalette”
   - 显示：分类、搜索、拖拽、Phase 标识。
B. “属性面板 PropertyPanel”
   - 显示：参数表单、输入摘要、输出设置、运行按钮。

核心卡片右侧放 2 个绿色后端卡片：
C. “PipelineValidator”
   - 显示：DAG 无环、端口兼容、参数合法、Phase 启用。
D. “NodeDispatcher”
   - 显示：按 backend.module/backend.function 调用执行器。

核心卡片下方放 2 个紫灰色数据卡片：
E. “PipelineDefinition”
   - 显示：graph.nodes、graph.links、params、ui。
   - 特别标注：“保存可复现定义，不保存运行状态”。
F. “NodeExecutionResult”
   - 显示：data_infos、artifacts、metrics、preview、warnings。
   - 特别标注：“输出必须可追溯到输入、参数和代码版本”。

箭头要求：
- NodeSpec -> NodePalette，箭头标签：“生成节点库”。
- NodeSpec -> PropertyPanel，箭头标签：“生成参数表单”。
- PipelineDefinition -> PipelineValidator，箭头标签：“保存前 / 运行前校验”。
- NodeSpec -> PipelineValidator，箭头标签：“端口、参数、Phase 规则”。
- NodeSpec -> NodeDispatcher，箭头标签：“定位后端执行函数”。
- NodeDispatcher -> NodeExecutionResult，箭头标签：“产生标准输出”。
- NodeExecutionResult -> PipelineDefinition，虚线箭头标签：“不回写运行状态，只保留引用关系”。

底部结论栏：
文字为：
“NodeSpec 是前后端共同契约：前端不写死节点，后端不猜参数，结果必须用 data_infos / artifact_infos 追溯。”

视觉要求：
核心卡片最大，左右上下模块围绕它排布。文字清楚，字号足够大。不要添加无关字段，不要生成乱码。
```

## 3. workflow-03-editor-save-validate.png：编辑器保存与校验流程

### 复制给 image2 的提示词

```text
请生成一张 1920x1080 横向 PNG 信息图，标题为“编辑器保存与校验流程”。

参考风格：
参考 one-click-deploy.png 的编号步骤卡片，参考 access-routes.png 的横向路线。白底、深蓝标题、每一步一个大卡片、卡片顶部有醒目的数字圆标，箭头清楚。

画面主旨：
让技术人员一眼看懂：用户在 LiteGraph 编辑器里拖节点、连线、改参数；保存时写入 pipeline_definitions；校验只做静态检查，不运行 EEG 算法；点击运行时才生成 PipelineRun 快照并进入后台任务。

整体布局：
顶部大标题“编辑器保存与校验流程”。
中间画一条从左到右的 6 步主流程，每步是大卡片，编号 1 到 6：
1. “编辑画布”
   - 图标：拖拽节点的画布。
   - 写清：拖节点、连线、改参数、移动位置。
2. “前端序列化”
   - 图标：浏览器 + JSON。
   - 写清：graph.nodes、graph.links、params、ui。
3. “保存 Definition”
   - 图标：保存按钮。
   - 写清：POST / PUT pipeline_definitions。
4. “静态校验”
   - 图标：盾牌 + 检查。
   - 写清：DAG 无环、端口类型、必填参数、LoadData 可用。
5. “返回校验报告”
   - 图标：报告面板。
   - 写清：errors、warnings、action_hint。
6. “创建运行快照”
   - 图标：快照相机 + 运行按钮。
   - 写清：definition_snapshot、pipeline_runs、pipeline_node_runs。

画面下半部分放 3 个横向说明卡片：
A. “保存 ≠ 运行”
   - 蓝色边框。
   - 文字：保存只更新工作流定义，不执行 EEG 计算。
B. “校验 ≠ 产出结果”
   - 橙色边框。
   - 文字：校验只检查结构和参数，不写 artifact。
C. “运行 = 固定快照”
   - 绿色边框。
   - 文字：点击运行后复制 definition_snapshot，后续编辑不影响本次 run。

箭头要求：
- 1 -> 2，标签：“graphSerialize”。
- 2 -> 3，标签：“保存草稿 / 更新版本”。
- 3 -> 4，标签：“validate_definition”。
- 4 -> 5，标签：“返回字段级错误”。
- 5 -> 1，虚线箭头标签：“用户修正后再次保存”。
- 5 -> 6，绿色箭头标签：“校验通过后点击运行”。
- 6 -> 后台任务入口，右侧加一个小卡片“进入 Redis / Celery 调度”，箭头标签：“投递 run task”。

需要出现的准确文字：
PipelineDefinition、pipeline_definitions、definition_snapshot、pipeline_runs、pipeline_node_runs、DAG 无环、端口类型、必填参数、LoadData 可用、保存 ≠ 运行。

底部结论栏：
文字为：
“编辑阶段保存的是可复现定义；运行阶段冻结的是快照；前端运行状态必须来自后端 run/node_run。”

视觉要求：
流程清楚，编号醒目，中文不乱码。不要把所有字段塞进小字表格。每个卡片最多 3-4 行短标签。
```

## 4. workflow-04-run-lifecycle.png：一次 PipelineRun 生命周期

### 复制给 image2 的提示词

```text
请生成一张 1920x1080 横向 PNG 技术信息图，标题为“一次 PipelineRun 生命周期”。

参考风格：
参考 access-routes.png 的清晰路线图和 security-boundary.png 的分层区域。白底、深蓝标题、状态节点要大、箭头要粗、异常路径用红色。不要生成密集状态机，不要让箭头交叉成网。

画面主旨：
让技术人员一眼看懂：点击运行后，系统创建 run 快照，进入 queued、running、waiting_user、completed、failed、canceled 等状态；前端看到的运行面板来自 pipeline_runs、pipeline_node_runs、pipeline_artifacts 三类记录。

整体布局：
顶部大标题“一次 PipelineRun 生命周期”。
画面上半部分是“运行状态主线”，放 5 个大状态节点：
1. “created / 已创建”
2. “queued / 排队等待”
3. “running / 执行中”
4. “waiting_user / 等待人工确认”
5. “completed / 完成”

状态节点颜色：
- created 灰蓝
- queued 橙色
- running 蓝色
- waiting_user 紫色
- completed 绿色

上半部分还要有两个异常终态：
- “failed / 失败”，红色大节点，放在 running 下方。
- “canceled / 取消”，灰色大节点，放在 queued/running 下方。

状态箭头要求：
- created -> queued，标签：“创建 run 和 node_run”。
- queued -> running，标签：“Worker 取任务”。
- running -> completed，标签：“所有必需节点完成或 cached”。
- running -> waiting_user，紫色箭头标签：“ICA / 人工审核节点暂停”。
- waiting_user -> running，紫色虚线箭头标签：“resume API 继续执行”。
- running -> failed，红色箭头标签：“关键节点失败”。
- queued -> canceled，灰色箭头标签：“用户取消”。
- running -> canceled，灰色箭头标签：“取消标记生效”。

画面下半部分是“后端记录与前端展示”，放 4 个大卡片：
A. “pipeline_runs”
   - 字段：id、project_id、pipeline_id、definition_snapshot、status、progress、error_json。
B. “pipeline_node_runs”
   - 字段：node_id、node_type、status、started_at、finished_at、node_hash、trace_code、error_json。
C. “pipeline_artifacts”
   - 字段：artifact_type、storage_path、checksum、metadata_json、preview_json。
D. “前端运行面板”
   - 内容：运行列表、节点颜色、日志 / 进度、错误提示、输出预览。

下半部分箭头要求：
- pipeline_runs -> pipeline_node_runs，标签：“一次 run 包含多个节点执行记录”。
- pipeline_node_runs -> pipeline_artifacts，标签：“节点完成后登记产物”。
- pipeline_artifacts -> 前端运行面板，标签：“预览 / 下载 / 观察入口”。
- pipeline_runs -> 前端运行面板，虚线箭头标签：“轮询或 SSE 获取状态”。

底部结论栏：
文字为：
“运行不读取正在编辑的图，而读取 definition_snapshot；前端只展示后端记录的 run、node_run 和 artifact。”

视觉要求：
状态节点要大，字段字号要能读清。不要出现过多弯曲箭头。failed 和 canceled 只作为异常出口，不要抢主线。
```

## 5. workflow-05-executor-internals.png：PipelineExecutor 内部执行逻辑

### 复制给 image2 的提示词

```text
请生成一张 1920x1080 横向 PNG 技术信息图，标题为“PipelineExecutor 内部执行逻辑”。

参考风格：
参考 one-click-deploy.png 的编号步骤和 hybrid-overview.png 的服务卡片风格。白底、深蓝大标题、像工厂流水线一样从左到右展示执行器每一步。用大图标和短标签，不要做成代码截图。

画面主旨：
让技术人员一眼看懂：PipelineExecutor 拿到 run 快照后，校验、拓扑排序、解析输入、规范化参数、计算 hash、检查缓存、调用 NodeDispatcher、保存 artifact、更新状态。缓存命中走快速通道，缓存未命中才真实计算。

整体布局：
顶部大标题“PipelineExecutor 内部执行逻辑”。
中间画一条大流水线，8 个编号卡片从左到右排列：
1. “读取 run 快照”
   - 内容：definition_snapshot、run_mode、cache_policy。
2. “校验 graph”
   - 内容：DAG 无环、端口兼容、参数合法。
3. “拓扑排序”
   - 内容：LoadData -> Filter -> Epoch -> ERP。
4. “解析输入”
   - 内容：上游 data_infos、artifact 引用、dataset_filter。
5. “计算标识”
   - 内容：input_hash、params_hash、node_hash、trace_code。
6. “检查缓存”
   - 内容：文件存在、checksum、schema、权限。
7. “执行节点”
   - 内容：NodeDispatcher、engine function、progress event。
8. “保存结果”
   - 内容：ArtifactStore、pipeline_artifacts、node_run status。

在第 6 步“检查缓存”处分成两条明显路径：
- 上方绿色捷径：“缓存命中 cached”
  - 箭头直接指向第 8 步“保存结果 / 登记 artifact”。
  - 标签：“复用输出，不重复计算”。
- 下方蓝色路径：“缓存未命中 run”
  - 箭头指向第 7 步“执行节点”。
  - 标签：“调用 EEG Engine 真实计算”。

画面右侧放一个竖向小面板“关键原则”，包含 4 条：
- save_output 不参与计算 hash。
- UI 位置、缩放、选中状态不参与 hash。
- 人工 decision 必须参与 hash。
- artifact 写入必须先 tmp 后 rename。

画面底部放一个“最小可跑链路”小路线：
LoadData -> FIR Filter -> Resample -> ReReference -> Epoch -> ERP Average -> SaveResult

必须出现的准确文字：
PipelineExecutor、PipelineValidator、NodeDispatcher、ArtifactStore、PipelineCache、node_hash、trace_code、data_infos、pipeline_node_runs、pipeline_artifacts、cached、success、failed。

底部结论栏：
文字为：
“Executor 的核心不是跑算法本身，而是把输入、参数、缓存、执行、产物和状态全部串成可审计闭环。”

视觉要求：
像清楚的流水线，不要像抽象状态图。缓存分叉必须非常醒目。所有技术词清晰可读。
```

## 6. workflow-06-redis-celery-scheduler.png：Redis/Celery 后台调度架构

### 复制给 image2 的提示词

```text
请生成一张 1920x1080 横向 PNG 技术架构图，标题为“Redis/Celery 后台调度架构”。

参考风格：
参考 hybrid-overview.png 和 server-roles.png 的服务器分区风格，也参考 security-boundary.png 的边界表达。白底、深蓝大标题、大服务器图标、大队列图标、大箭头。重点强调“数据库是事实源，Redis 是短期调度”。

画面主旨：
让技术人员一眼看懂：前端点击运行后，FastAPI 立即返回 run_id；PostgreSQL 保存 run/node/artifact 事实；Redis/Celery 只排队、推送临时进度和 worker 心跳；Worker 执行节点并写回数据库和文件系统；前端轮询或 SSE 看进度。

整体布局：
画面分为三层横向区域，左侧用彩色竖条标注层级：
第一层：“用户与 API 层”
第二层：“调度与执行层”
第三层：“事实与存储层”

第一层从左到右：
1. “Vue Pipeline 页面”
   - 图标：浏览器。
   - 内容：点击运行、查看进度、取消 / 重试、打开预览。
2. “FastAPI Run API”
   - 图标：闪电 API。
   - 内容：权限校验、创建 run、返回 run_id。

第二层中间放最大模块：
3. “Redis + Celery”
   - 图标：红色 Redis 队列。
   - 内容：workflow.default、workflow.preprocess、workflow.ica、workflow.analysis、worker heartbeat、event notify。
4. 右侧放 3 个 Worker 卡片：
   - “Preprocess Worker”：Filter、Resample、ReReference。
   - “ICA Worker”：ComputeICA、ApplyICA。
   - “Analysis Worker”：Epoch、ERP、PSD、TFR、Stats。

第三层放 3 个大卡片：
5. “PostgreSQL 事实源”
   - 内容：pipeline_runs、pipeline_node_runs、pipeline_artifacts、error_json。
6. “项目文件系统”
   - 内容：fifdata、derivatives/pipeline_runs、cache/pipeline、logs。
7. “前端状态读取”
   - 内容：GET run、GET nodes、SSE events、artifact preview。

箭头要求：
- Vue Pipeline 页面 -> FastAPI Run API，标签：“POST /run”。
- FastAPI Run API -> PostgreSQL，标签：“创建 run 快照和 node_run”。
- FastAPI Run API -> Redis + Celery，标签：“投递后台任务”。
- Redis + Celery -> Worker，标签：“取任务执行”。
- Worker -> PostgreSQL，标签：“更新状态 / 错误 / 耗时”。
- Worker -> 项目文件系统，标签：“写入 EEG 输出和日志”。
- 项目文件系统 -> PostgreSQL，标签：“登记 artifact 索引”。
- PostgreSQL -> 前端状态读取，标签：“轮询 / 查询状态”。
- Redis + Celery -> 前端状态读取，虚线箭头标签：“临时事件通知，可选 SSE”。

画面右侧放一个醒目警示卡片：
标题：“Redis 不是事实源”
内容：
- 不保存 EEG 大文件
- 不保存长期状态
- 重启后可从 PostgreSQL 恢复

底部结论栏：
文字为：
“Redis 负责排队和通知；PostgreSQL 负责事实；文件系统负责大对象；Worker 负责真正执行 EEG 节点。”

视觉要求：
Redis 模块要醒目但不能看起来像数据库。PostgreSQL 和文件系统是长期存储，必须在底层突出。所有中文和队列名清晰可读。
```

## 7. workflow-07-cache-incremental.png：缓存与增量运行机制

### 复制给 image2 的提示词

```text
请生成一张 1920x1080 横向 PNG 技术信息图，标题为“缓存与增量运行机制”。

参考风格：
参考 access-routes.png 的路线清晰感和 server-roles.png 的大图标分组。白底、深蓝标题、节点图像要像可视化 DAG，而不是数据库 ER 图。用绿色表示缓存命中，用橙色表示 dirty/stale，用蓝色表示需要重新运行。

画面主旨：
让技术人员一眼看懂：每个节点根据输入、参数、NodeSpec 和上游 hash 计算 node_hash；命中缓存则复用 artifact；当某个节点参数或输入变化时，只重算它和下游，不相关分支保持可用。

整体布局：
左侧画一个大的 DAG 示例，标题“小型 EEG 工作流 DAG”：
节点从左到右：
LoadData -> FIR Filter -> Resample -> Epoch -> ERP Average -> SaveResult
同时从 Resample 分出一个下游分支：
Resample -> PSD Welch -> SendToStats

节点颜色：
- LoadData：蓝色。
- FIR Filter：橙色高亮，旁边标注“参数变化 l_freq/h_freq”。
- FIR Filter 下游的 Resample、Epoch、ERP Average、SaveResult：橙色虚线边框，标注“stale / 需要重算”。
- PSD 分支如果依赖 Resample，也标注“stale”。
- 与变化无关的旁路节点用绿色标注“cached / 可复用”。

画面右侧放 3 个大卡片：
A. “node_hash 组成”
   - 内容：project_id、node_type、NodeSpec version、engine version、params_hash、input_hashes。
   - 公式样式文字：node_hash = sha256(canonical_json(payload))
B. “缓存命中条件”
   - 内容：node_hash 一致、artifact 文件存在、checksum 正确、schema 兼容、项目权限允许。
C. “增量运行规则”
   - 内容：当前节点 dirty、下游节点 stale、无关分支 cached、缓存缺文件则 failed / rerun。

画面下方画一个“缓存查找路径”横向小流程：
node_hash -> cache manifest -> artifact 文件路径 -> checksum -> data_infos -> pipeline_node_runs.status = cached

箭头要求：
- FIR Filter 参数变化 -> 下游节点，橙色箭头标签：“影响下游结果”。
- node_hash 组成 -> 缓存命中条件，箭头标签：“判断是否可复用”。
- 缓存命中条件 -> 缓存查找路径，绿色箭头标签：“命中则登记 cached”。
- 缓存命中条件 -> 执行节点，蓝色箭头标签：“未命中则重新计算”。

必须出现的准确文字：
dirty、stale、cached、node_hash、input_hash、params_hash、trace_code、cache manifest、artifact、checksum、schema version、reuse_valid、force_rerun。

底部结论栏：
文字为：
“增量运行的目标不是跳过流程，而是只重算受影响节点；缓存命中也必须写入 node_run，审计上看得见。”

视觉要求：
DAG 要大而清楚，右侧规则卡片不要太小。所有英文状态词必须拼写准确。不要画成一堆表字段。
```

## 8. workflow-08-artifact-lineage.png：Artifact 与结果追溯链路

### 复制给 image2 的提示词

```text
请生成一张 1920x1080 横向 PNG 技术信息图，标题为“Artifact 与结果追溯链路”。

参考风格：
参考 security-boundary.png 的分层边界和 hybrid-overview.png 的存储/服务卡片风格。白底、深蓝标题、用清晰链路表现“从上传数据到分析结果”的追溯。不要做成密集数据库表关系图。

画面主旨：
让技术人员一眼看懂：原始上传、fifdata 工作数据、PipelineRun 快照、NodeRun 执行记录、pipeline_artifacts、dataset_derivatives、analysis_results 之间如何形成可追溯链路；大文件在文件系统，元数据和索引在数据库。

整体布局：
画面从左到右是一条“数据血缘链路”，分 6 个大阶段卡片：
1. “原始上传 source_uploads”
   - 图标：上传文件。
   - 内容：raw EEG、BIDS 文件、原始校验。
2. “工作数据 fifdata”
   - 图标：文件夹 + EEG。
   - 内容：datasets.current_upload_id、current.json、fif_checksum。
3. “运行快照 pipeline_runs”
   - 图标：相机快照。
   - 内容：definition_snapshot、run_mode、triggered_by。
4. “节点执行 pipeline_node_runs”
   - 图标：齿轮节点。
   - 内容：node_id、node_type、node_hash、trace_code、status。
5. “产物索引 pipeline_artifacts”
   - 图标：文件夹 + 数据库索引。
   - 内容：artifact_id、source_dataset_id、storage_path、checksum、metadata_json、preview_json。
6. “结果消费”
   - 图标：图表 + 观察窗口。
   - 内容：观察、统计、科研作图、机器学习、报告。

画面下半部分分成两个清晰边界区：
A. “数据库保存索引和元数据”
   - 紫色边框。
   - 包含：datasets、dataset_uploads、pipeline_runs、pipeline_node_runs、pipeline_artifacts、analysis_results。
B. “文件系统保存大对象”
   - 灰蓝色边框。
   - 包含：source_uploads/、fifdata/、derivatives/pipeline_runs/、cache/pipeline/、logs/。

箭头要求：
- source_uploads -> fifdata，标签：“导入校正 / 生成工作 FIF”。
- fifdata -> pipeline_runs，标签：“LoadData 固定输入集合”。
- pipeline_runs -> pipeline_node_runs，标签：“按快照执行节点”。
- pipeline_node_runs -> pipeline_artifacts，标签：“节点输出登记 artifact”。
- pipeline_artifacts -> 结果消费，标签：“预览 / 统计 / 作图 / ML 输入”。
- pipeline_artifacts -> 文件系统保存大对象，标签：“storage_path 指向真实文件”。
- pipeline_artifacts -> 数据库保存索引和元数据，标签：“metadata_json 和 checksum 可审计”。

画面右上角放一个“追溯问题”小面板，内容：
- 这个图来自哪个 run？
- 这个结果由哪个 node 生成？
- 参数和输入是什么？
- 文件 checksum 是否一致？
- 来源 dataset 是谁？

必须出现的准确文字：
source_uploads、fifdata、datasets.current_upload_id、pipeline_runs、pipeline_node_runs、pipeline_artifacts、dataset_derivatives、analysis_results、artifact_id、source_dataset_id、storage_path、checksum、metadata_json、preview_json。

底部结论栏：
文字为：
“派生数据的主身份是 artifact_id；dataset_id 指来源数据；文件路径只是存储位置，数据库索引才是追溯入口。”

视觉要求：
主链路必须一眼看懂，数据库和文件系统边界必须分开。文字不要拥挤，所有表名和字段名清晰准确。
```

## 9. workflow-09-human-node-and-recovery.png：人工交互节点与失败恢复

### 复制给 image2 的提示词

```text
请生成一张 1920x1080 横向 PNG 技术信息图，标题为“人工交互节点与失败恢复”。

参考风格：
参考 one-click-deploy.png 的分步骤卡片和 security-boundary.png 的警示/边界设计。白底、深蓝标题、人工交互用紫色，失败恢复用红色和橙色。画面要像一张清楚的运维/研发说明图。

画面主旨：
让技术人员一眼看懂：ICA 等人工交互节点不能让 Worker 一直阻塞；系统先计算候选结果，再进入 waiting_user，前端让用户提交 decision，resume API 再继续执行；失败、取消、重试、Worker 中断、文件半写入都要有清晰恢复策略。

整体布局：
画面上半部分是“人工交互主流程”，用 6 个大步骤从左到右：
1. “Compute ICA”
   - 图标：脑电 + 计算齿轮。
   - 内容：后台计算 ICA，生成成分预览 artifact。
2. “生成候选结果”
   - 图标：预览面板。
   - 内容：components、auto_labels、preview_json。
3. “waiting_user”
   - 紫色大状态卡片。
   - 内容：interaction_id、decision_version、locked_by、locked_at。
4. “前端审核界面”
   - 图标：用户 + 勾选列表。
   - 内容：选择 excluded_components，查看波形 / 频谱 / topomap。
5. “提交 decision”
   - 图标：提交按钮。
   - 内容：decision_json、decision_by、decision_version + 1。
6. “resume 后继续下游”
   - 图标：继续运行箭头。
   - 内容：Apply ICA -> Epoch -> ERP / PSD。

箭头要求：
- Compute ICA -> 生成候选结果，标签：“保存预览 artifact”。
- 生成候选结果 -> waiting_user，标签：“节点暂停，不占用 Worker”。
- waiting_user -> 前端审核界面，标签：“GET interaction”。
- 前端审核界面 -> 提交 decision，标签：“用户确认选择”。
- 提交 decision -> resume 后继续下游，标签：“POST resume API”。
- resume 后继续下游 -> 后续节点，标签：“decision 参与 hash”。

画面下半部分是“失败恢复策略”，放 5 个并列卡片：
A. “节点失败 failed”
   - 红色边框。
   - 内容：error_json、action_hint、手动 retry。
B. “Worker 中断 interrupted”
   - 橙色边框。
   - 内容：heartbeat 超时、扫描 running、标记 interrupted。
C. “用户取消 canceled”
   - 灰色边框。
   - 内容：canceling 标记、Worker 主动检查、停止下游。
D. “文件半写入”
   - 红橙边框。
   - 内容：只写 .tmp、不登记 artifact、失败后清理。
E. “多人确认冲突”
   - 紫色边框。
   - 内容：decision_version 校验、DECISION_CONFLICT、重新加载。

右侧放一个醒目的“必须记录”小面板：
- interaction_id
- node_run_id
- interaction_type
- candidate_json
- decision_json
- locked_by / locked_at
- decision_version

必须出现的准确文字：
waiting_user、interaction_id、decision_json、decision_version、resume API、excluded_components、failed、interrupted、canceled、retry、DECISION_CONFLICT、ARTIFACT_WRITE_FAILED。

底部结论栏：
文字为：
“人工节点是可恢复的状态，不是阻塞中的函数调用；用户 decision 必须入库、参与 hash，并可被审计。”

视觉要求：
人工流程和失败恢复要分上下两区，不能混在一起。waiting_user 紫色节点要非常醒目。所有状态名和错误码必须清晰可读。
```

