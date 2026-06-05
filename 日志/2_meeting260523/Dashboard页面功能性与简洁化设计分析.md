# Dashboard 页面功能性与简洁化设计分析

文档生成时间：2026-05-23 00:36:04 +08:00

## 1. 设计目标

Dashboard 是数据处理网站的“工作台入口”，不是营销首页，也不是开发调试面板。它的核心价值是让用户在 5 到 10 秒内判断：

1. 当前平台里有哪些关键对象。
2. 我最近在做哪个 Study。
3. 现在有没有 Run 正在跑、排队、失败或等待我确认。
4. 下一步应该进入 Dataset、Study、Pipeline 还是 Run。

因此页面应该简洁、精致、克制，信息密度要服务效率。用户不应该在 Dashboard 上阅读对象定义、实现策略、服务器路径或完整明细；这些内容应进入对应业务页、详情页、抽屉或技术信息区。

## 2. Dashboard 的核心职责

Dashboard 建议承担五个职责：

1. 全局态势摘要：用很少的数字说明 Dataset、Study、Pipeline、Run 的当前状态。
2. 工作恢复：让用户快速回到最近 Study。
3. 运行监控：突出活动中的 Run，尤其是 running、queued、waiting_user_input、failed。
4. 异常提醒：展示需要用户处理的失败、等待确认、接口降级、权限问题。
5. 入口分流：把用户带到正确页面，而不是在 Dashboard 内完成复杂操作。

Dashboard 不应承担以下职责：

1. 完整 Dataset 导入流程。
2. Pipeline 编辑器。
3. Run 全量详情、manifest、node runs、artifact 列表。
4. 文件浏览器或文件索引。
5. 后端摘要策略说明。
6. 数据库字段、服务器路径、UUID 调试信息展示。

## 3. 用户最需要看见的信息

默认暴露的信息应该围绕“决策”而不是围绕“系统结构”。

### 3.1 顶部区域

建议展示：

- 问候语和用户名称。
- 当前日期。
- 刷新按钮。
- 主要动作：导入 Dataset、新建 Study。

不建议展示：

- `Dataset / Study / Pipeline / Run` 作为提示词。
- “这里显示四个核心对象的有限摘要和下一步入口”这类开发说明。
- 大段产品介绍。
- 复杂的首屏 hero。

对于数据处理工具，顶部应该像操作台，不应该像宣传页。

### 3.2 四对象摘要卡

四个核心对象仍然应该保留，但呈现方式要精致、紧凑、可点击。

建议字段：

| 对象 | 主数字 | 辅助信息 | 点击去向 |
| --- | --- | --- | --- |
| Dataset | 数据集数量 | working / active / error 数量 | `/datasets` |
| Study | Study 数量 | active / archived 数量 | `/studies` |
| Pipeline | Pipeline 数量 | 可运行 / 草稿数量 | `/pipeline` |
| Run | 最近 Run 或活动 Run 数量 | running / queued / waiting / failed / completed | `/pipeline` 或未来 `/runs` |

呈现建议：

- 卡片使用清晰的对象颜色和细左边线，不使用大面积装饰。
- 数字使用等宽数字或稳定宽度，避免刷新时跳动。
- 每张卡最多一行辅助信息。
- 卡片本身作为入口，避免再额外重复一组“快捷入口”。

不建议字段：

- Dataset Asset ID。
- Study ID / Project ID。
- Pipeline JSON 或 node 详细列表。
- Run manifest、result_json、error_json。
- 服务器目录、`bids_root`、`source_path`、`fif_path`。

### 3.3 最近 Study

最近 Study 是 Dashboard 的主要工作恢复入口。用户通常不是从“全部对象”开始工作，而是从最近研究项继续。

建议展示：

- Study 名称。
- Study code。
- 状态：活跃、归档、回收站。
- 简短描述。
- Pipeline 数量。
- Run 数量。
- 活动中 Run 数量。
- 最近更新时间。

可以后续补充：

- 最近操作者。
- 数据挂载数量。
- Dataset 完成度。
- 最近失败 Run 数。

不建议默认展示：

- owner_id。
- storage quota。
- bids_root。
- 成员完整列表。
- 全部 Dataset / Pipeline / Run 明细。

交互建议：

- 点击整行进入 Study 详情。
- 行内只保留状态和少量指标，不放太多按钮。
- 如果需要更多操作，用悬浮或右侧菜单提供，但默认不要铺满。

### 3.4 活动中的 Run

活动中的 Run 是 Dashboard 对效率最有帮助的区域。数据处理网站的用户最关心“任务现在跑到哪里了、有没有卡住、是否需要我确认”。

建议展示：

- Pipeline 名称。
- Run 编号。
- 状态：运行中、排队中、等待确认、失败。
- run_mode / save_policy。
- dataset_count。
- node_count。
- 开始时间或更新时间。
- 进度条或阶段提示。

优先级：

1. waiting_user_input：需要用户确认，应最高优先。
2. failed：需要处理，应高优先。
3. running：需要监控。
4. queued：需要知道等待。
5. completed：只在最近活动里展示，不需要挤占活动 Run 卡。

交互建议：

- 默认展开活动中的 Run。
- 提供“展开 / 收起”，让页面在数据多时保持简洁。
- 点击 Run 进入 Pipeline / Run 详情。
- 等待确认的 Run 可提供明确 CTA，例如“进入确认”。
- 取消、重试这类高影响操作不建议直接放在 Dashboard 主界面，除非进入二次确认或详情页。

不建议默认展示：

- node_run 全列表。
- artifact 全列表。
- manifest JSON。
- worker 日志。
- traceback。
- 详细参数。

这些信息应进入 Run detail。

### 3.5 最近活动

最近活动适合做轻量审计摘要，帮助用户知道最近发生了什么。

建议展示：

- 事件对象：Dataset / Study / Pipeline / Run。
- 对象名称。
- 简短动作：已更新、已导入、已启动、已完成、失败、等待确认。
- 时间。
- 对象类型颜色。

不建议展示：

- 审计事件 ID。
- 完整 payload。
- API 响应原文。
- 太多历史记录。

默认显示 6 到 8 条即可。更多内容进入审计日志或 Study 详情。

## 4. 不需要暴露的信息清单

以下信息不应在 Dashboard 默认展示：

1. “Dataset / Study / Pipeline / Run”提示词或产品解释句。
2. “当前摘要策略”这类开发自述。
3. `bids_root`、`source_path`、`fif_path`、`canonical_fif_path`。
4. 服务器绝对路径和存储目录。
5. Dataset UUID、Study UUID、mount_id、pipeline_id、task_id 等底层 ID。
6. manifest、result_json、error_json、definition_json。
7. node_run、artifact、dataset_file 的全量明细。
8. 所有 Study 的所有 Pipeline / Run。
9. 完整上传表单和批量文件队列。
10. 运维指标如 CPU、内存、磁盘，除非当前用户是管理员且页面有专门运维区域。

这些信息不是“不存在”，而是不应该放在 Dashboard 默认视图。它们应该进入：

- Dataset 文件索引。
- Study 详情。
- Pipeline 编辑器。
- Run 详情。
- Artifact 详情。
- 管理员运维页。
- 技术信息折叠面板。

## 5. 推荐信息层级

Dashboard 的信息层级建议如下：

```text
顶部：问候 + 日期 + 主要动作

第一层：四对象摘要
Dataset / Study / Pipeline / Run 的极简状态

第二层：工作恢复 + 运行监控
左：最近 Study
右：活动中的 Run

第三层：最近活动
跨对象变化摘要

隐藏层：技术信息
不在 Dashboard 展示，进入对应页面查看
```

这个结构能兼顾效率和优雅：首屏有全局态势，第二屏能继续工作，底部有变化感，但不会像调试页一样铺满细节。

## 6. 交互原则

### 6.1 点击路径要短

用户常见路径应该是：

1. Dashboard -> 最近 Study -> Study 详情。
2. Dashboard -> 活动 Run -> Run 详情。
3. Dashboard -> 导入 Dataset -> Dataset 导入页。
4. Dashboard -> 新建 Study -> Study 管理页。
5. Dashboard -> Pipeline 摘要卡 -> Pipeline 页面。

不建议让用户在 Dashboard 上完成复杂编辑。Dashboard 负责“发现和跳转”，不是负责“完成所有操作”。

### 6.2 默认紧凑，按需展开

适合展开/收起的内容：

- 活动中的 Run 列表。
- 最近活动更多记录。
- 异常详情。
- 技术信息。

不适合默认展开的内容：

- 文件索引。
- Run 节点详情。
- Artifact 列表。
- manifest。
- 后端拉取策略。

### 6.3 异常优先

如果存在失败或等待确认，应把它们放在正常活动之前。

建议优先级：

```text
等待用户确认 > 失败 > 运行中 > 排队中 > 最近完成 > 普通更新
```

颜色语义建议：

- Dataset：蓝色。
- Study：青绿色。
- Pipeline：黄色 / 琥珀色。
- Run：信息蓝。
- 成功：绿色。
- 警告：琥珀色。
- 失败：红色。

颜色应该用于状态识别，不应变成大面积装饰。

### 6.4 刷新与实时性

Dashboard 需要刷新，但不一定需要每个区域都实时轮询。

建议：

- 手动刷新保留。
- 活动 Run 可 15 到 30 秒刷新一次，或接入 SSE 后只订阅 active Run。
- 最近 Study 和四对象摘要可以低频刷新。
- 最近活动可以低频刷新或页面进入时加载。

避免：

- 页面打开后对所有 Study 做全量 N+1 拉取。
- 因轮询导致大量接口请求。
- 频繁刷新导致卡片数字和布局跳动。

## 7. 性能与 API 建议

当前 Dashboard 仍偏前端聚合：先读 Study 列表，再对有限 Study 拉 Pipeline / Run。短期可接受，但长期建议补专门摘要 API。

建议新增：

```text
GET /api/v1/dashboard/summary
```

返回建议：

```json
{
  "counts": {
    "dataset_assets": 0,
    "studies": 0,
    "pipelines": 0,
    "runs": 0
  },
  "states": {
    "dataset_working": 0,
    "study_active": 0,
    "pipeline_active": 0,
    "run_running": 0,
    "run_queued": 0,
    "run_waiting_user_input": 0,
    "run_failed": 0
  },
  "recent_studies": [],
  "active_runs": [],
  "recent_activity": []
}
```

好处：

1. Dashboard 只发一次主请求。
2. 后端可以统一做权限过滤。
3. 可以避免前端全量扫描。
4. 可以统一定义摘要口径。
5. 后续可以直接接入审计事件和任务队列。

## 8. 当前 Dashboard 状态评估

当前页面已经朝正确方向收敛：

1. 已使用统一 `WorkbenchShell`。
2. 已去掉顶部对象提示词和开发说明。
3. 已去掉“快捷入口”重复卡。
4. 已去掉 Dataset / Pipeline / Run 对象解释卡。
5. 已去掉“当前摘要策略”开发自述。
6. 已将四对象改为可点击摘要卡。
7. 已新增最近 Study 和活动中的 Run。
8. 活动中的 Run 已支持展开 / 收起。

仍建议继续优化：

1. 顶部按钮中“导入 Dataset”和“新建 Study”可以根据数据状态动态主次切换。
2. 活动 Run 应优先显示 waiting_user_input 和 failed。
3. 最近 Study 的指标应尽量来自后端 summary，避免前端有限聚合导致数量不完整。
4. 最近活动应由审计事件 API 或 dashboard summary API 提供，而不是前端拼接。
5. Run 卡点击后应能定位到具体 Run，而不是只进入 Pipeline 总页。
6. 如果未来有 `/runs` 独立页，Run 摘要卡和活动 Run 应跳转到 `/runs` 或 `/runs/:id`。

## 9. 推荐落地步骤

### 第 1 步：稳定当前简洁版 Dashboard

目标：

- 保持当前三层结构：四对象摘要、最近 Study / 活动 Run、最近活动。
- 不再恢复快捷入口、对象解释卡和摘要策略卡。
- 修正空态、移动端、长文本截断。

验收：

- 首屏没有开发说明。
- 首屏没有服务器路径。
- 首屏可以判断是否有活动 Run。
- 移动端卡片纵向排列且文字不溢出。

### 第 2 步：强化 Run 监控效率

目标：

- active Run 按 waiting_user_input、failed、running、queued 排序。
- Run 行支持状态图标、更新时间、阶段说明。
- waiting_user_input 提供“进入确认”入口。

验收：

- 用户能立刻看到是否需要自己处理。
- 失败和等待确认不会被普通运行项淹没。

### 第 3 步：补 Dashboard Summary API

目标：

- 用单一 summary API 替换前端多接口聚合。
- 统一统计口径、权限过滤、最近活动口径。

验收：

- Dashboard 首屏主数据只依赖一个摘要接口。
- 加载失败时有清晰降级提示。
- 不对所有 Study 做全量 N+1 请求。

### 第 4 步：接入审计活动和 Run 详情跳转

目标：

- 最近活动来自 audit_events 或 activity summary。
- Run 行点击能定位到具体 Run detail。
- Pipeline / Run 页面支持通过 query 或 route 自动选中某个 Run。

验收：

- Dashboard 活动记录是真实事件，不是前端拼接。
- 用户从 Dashboard 到具体 Run 不需要二次寻找。

## 10. 结论

Dashboard 的设计方向应是“轻量态势 + 快速恢复 + 运行监控”。它要精致，不是靠更多卡片和装饰，而是靠信息取舍准确、层级清楚、默认视图克制。

应该暴露给用户的是：数量、状态、最近工作、活动任务、异常和下一步入口。

不应该暴露给用户的是：对象定义、开发策略、服务器路径、UUID、JSON、文件明细和全量运行事实。

只要坚持“默认只展示能帮助用户决策的信息，其他内容按需进入详情”，Dashboard 就会更像一个高效、优雅的数据处理工作台，而不是一个工程调试页面。
