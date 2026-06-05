# 上传后模拟质控流程 Codex 分步开发提示词

> 文档性质：开发执行手册。  
> 正式业务边界以 `wiki/docs/M2-15-上传后模拟质控流程.md` 为准。本文把“模拟质控流程”拆成可以逐步交给 Codex 执行的小任务。  
> 目标：在不实现真实 RMS/PSD/坏段等科研级算法的前提下，先做出可演示、可追溯、不会误导用户的上传后质量检查闭环。

## 使用方式

每次只复制一个步骤的提示词给 Codex。执行前先确认当前工作区没有未完成冲突；执行后让 Codex 把实际改动、验证结果和未完成项同步回本目录。

每条提示词必须满足两个格式要求：

- 开头为 `step x：xxxxxx`。
- 结尾为 `相关执行内容和结果在2_meeting260516中md中同步更新。`

## 总体边界

模拟质控的核心不是“判定 EEG 信号质量好坏”，而是“确认这份数据整理清楚、文件可访问、元数据可用、用户已经看过”。因此实现时要守住以下边界：

| 事项 | 规则 |
|---|---|
| `converted` | 导入成功、FIF 读回成功，由现有导入流程写入 |
| `checked` | 只能由人工确认通过，或未来真实 QC 通过后写入 |
| `qa_report.mode` | 模拟质控必须写 `mock` |
| `qa_report.summary.score` | 真实信号指标未实现前建议为 `null`，不要伪造精确分 |
| 信号质量 | 当前只写 `not_computed` 占位，不展示真实 RMS/PSD/坏段结论 |
| LoadData | 默认可选 `converted` 和 `checked`，强制排除 `failed/rejected/deleted` |
| 数据来源 | 只检查当前 `datasets.current_upload_id` 指向的版本 |
| 文件读取 | 可以轻量读 FIF header；不要在模拟质控里做耗时 preload 或改变数据 |

## 推荐开发顺序

| 阶段 | 步骤 | 目标 |
|---|---|---|
| 基线 | Step 0 | 确认现状，不改功能 |
| 后端契约 | Step 1 - 3 | 定义 schema、报告生成器、只读 API |
| 后端写入 | Step 4 - 6 | 生成 mock report、人工 review、审计记录 |
| 前端接入 | Step 7 - 11 | API/types、数据列表入口、详情面板、操作按钮、LoadData 展示 |
| 验证收口 | Step 12 - 15 | 后端测试、前端测试、端到端手动验证、wiki 同步 |

第一轮最小闭环建议只做 Step 0 - Step 9：可以从数据列表打开一份数据，生成模拟质控报告，并通过/暂缓/拒绝。

## Step 0：基线审计

目标：确认当前代码里 `datasets.qa_status`、`datasets.qa_report`、数据集 API、项目详情页、LoadData 面板的真实状态，不做任何功能改动。

需要检查：

- 后端模型：`backend/app/models/project.py` 中 `Dataset`、`DatasetUpload` 字段。
- Pydantic schema：`backend/app/schemas/dataset.py`。
- 后端路由：`backend/app/routers/datasets.py`。
- 前端 API：`frontend/elys-web/src/api/datasets.ts`。
- 前端类型：`frontend/elys-web/src/types/index.ts`。
- 数据展示页面：`ProjectDetailPage.vue`、`Dashboard.vue`、`PipelinePage.vue`。
- 正式文档：`wiki/docs/M2-15-上传后模拟质控流程.md`。

完成标准：

- 写清楚当前已经能读写哪些字段。
- 写清楚需要新增哪些 API。
- 写清楚前端第一版应放在哪个页面。
- 不修改业务代码。

Codex 提示词：

```text
step 0：上传后模拟质控基线审计

请基于当前代码状态审计上传后模拟质控功能的实现基础，不要改业务功能。

重点检查：
1. backend/app/models/project.py 中 Dataset 和 DatasetUpload 是否已有 qa_status、qa_report、current_upload_id、fif_path、sidecar_paths 等字段。
2. backend/app/schemas/dataset.py 当前 DatasetResponse 是否返回 qa_status、qa_report、current_upload 信息。
3. backend/app/routers/datasets.py 当前 list/import 路由如何写入 qa_status。
4. frontend/elys-web/src/api/datasets.ts 和 frontend/elys-web/src/types/index.ts 是否已有足够类型承接 qa_report。
5. ProjectDetailPage.vue、Dashboard.vue、PipelinePage.vue 当前如何展示 dataset 状态。
6. 对照 wiki/docs/M2-15-上传后模拟质控流程.md，总结待实现 API、前端入口、测试缺口。

请输出一份审计结论，写明：
- 当前已具备的字段和接口。
- 最小实现需要新增的文件/函数/API。
- 第一轮最推荐的落地范围。
- 暂时不要实现真实 RMS/PSD/坏段算法。

相关执行内容和结果在2_meeting260516中md中同步更新。
```

## Step 1：定义后端 schema 和状态常量

目标：先把模拟质控的输入/输出契约固定下来，避免后续 API 和前端各写各的 JSON。

建议改动：

- 新增或扩展 `backend/app/schemas/dataset.py`。
- 定义 `DatasetQaReportResponse`、`DatasetQaMockRunResponse`、`DatasetQaReviewRequest`、`DatasetQaReviewResponse`。
- 定义 review conclusion：`accept / reject / hold`。
- 定义 stage/item 的通用结构：`key/title/status/severity/message/items`。
- 不新增数据库表，第一版只复用 `datasets.qa_report`。

完成标准：

- schema 可被导入。
- 字段能表达 `mode='mock'`、`summary`、`stages`、`human_review`。
- 真实 QC 预留 `mode='real'`，但不实现。

Codex 提示词：

```text
step 1：定义上传后模拟质控后端 schema 和状态常量

请为上传后模拟质控定义后端 Pydantic schema 和状态常量，先不实现业务逻辑。

要求：
1. 优先在 backend/app/schemas/dataset.py 中扩展；如果文件过大，也可以新增 backend/app/schemas/dataset_qa.py，但需要在 __init__ 或引用处保持清晰。
2. 定义模拟质控报告响应结构，至少包含 version、mode、generated_at、summary、stages、human_review。
3. summary 至少包含 mock_qc_status、level、score、blocking_issues、warnings。
4. stage 至少包含 key、title、status、severity、message、items。
5. review 请求支持 conclusion=accept/reject/hold 和 notes。
6. mode 当前允许 mock/real，但本轮业务只能写 mock。
7. score 在 mock 模式下允许为 null。
8. 不新增数据库表，不改变现有 DatasetResponse 的兼容性。

请补充最小导入测试或 import smoke，确保新增 schema 可导入。

相关执行内容和结果在2_meeting260516中md中同步更新。
```

## Step 2：实现模拟质控报告生成服务

目标：把检查逻辑从 router 中拆出来，形成可测试的纯后端服务。

建议新增：

- `backend/app/services/dataset_qa.py` 或 `backend/app/qa/mock_dataset_qa.py`。
- 函数：`build_mock_qa_report(project, dataset) -> dict`。
- 辅助函数：
  - 检查当前上传版本。
  - 检查 `source_path/fif_path/current_upload.sidecar_paths`。
  - 解析项目相对路径到绝对路径。
  - 检查 metadata 字段是否为空或异常。
  - 尝试轻量打开 FIF header。
  - 生成 signal placeholder。

检查阶段建议：

| key | 标题 | 目标 |
|---|---|---|
| `preflight` | 前置状态 | dataset/current upload 是否存在 |
| `identity` | 数据身份 | subject/session/task/run 是否清楚 |
| `file_integrity` | 文件完整性 | source/fif/sidecar 是否存在 |
| `metadata_consistency` | 元数据一致性 | n_channels/sfreq/duration/n_events |
| `fif_header` | FIF 头部快速读取 | FIF 能否打开，头部和 DB 是否一致 |
| `channels_sidecar` | 通道清单 | channels sidecar 是否存在、行数是否合理 |
| `events_sidecar` | 事件清单 | events sidecar 是否存在、事件是否越界 |
| `signal_placeholder` | 信号质量占位 | 明确真实信号指标未计算 |

完成标准：

- 对正常 dataset 返回 `mode='mock'` 报告。
- 文件缺失会生成 blocking issue。
- 不修改数据库。
- 不做真实信号算法。

Codex 提示词：

```text
step 2：实现上传后模拟质控报告生成服务

请实现一个后端服务，用于根据 Project + Dataset 生成 qa_report.mode='mock' 的模拟质控报告，但不要写数据库。

要求：
1. 新增 backend/app/services/dataset_qa.py，或放在项目已有服务目录中，保持命名清楚。
2. 暴露 build_mock_qa_report(project, dataset) -> dict。
3. 报告包含这些 stages：preflight、identity、file_integrity、metadata_consistency、fif_header、channels_sidecar、events_sidecar、signal_placeholder。
4. file_integrity 检查 source_path、fif_path、current_upload.sidecar_paths 中 import/channels/events 指向的文件是否存在。
5. metadata_consistency 检查 n_channels、sfreq、duration_seconds、n_events、checksum 是否存在且基本合理。
6. fif_header 只做轻量读取，不 preload，不改变 FIF 文件；如果当前环境缺少 mne，要优雅降级为 warning 或 not_computed。
7. signal_placeholder 必须写 status=not_computed，并说明真实 RMS/PSD/坏段指标尚未实现。
8. 有致命问题时写入 summary.blocking_issues；普通问题写 warnings。
9. mock 模式下 summary.score 保持 null。
10. 本步骤不新增 API，不写数据库。

请补充最小单元测试或脚本验证：正常 dataset、缺少 fif_path、FIF 文件缺失三种情况的报告结构。

相关执行内容和结果在2_meeting260516中md中同步更新。
```

## Step 3：新增读取 QA 报告 API

目标：前端可以读取一份 dataset 当前的 `qa_report`；如果还没有报告，也能拿到清晰的空状态。

建议 API：

- `GET /api/v1/projects/{project_id}/datasets/{dataset_id}/qa`

返回：

- dataset_id
- qa_status
- qa_report
- has_report
- current_upload_id
- updated_at 或 imported_at

完成标准：

- 权限使用项目可读 + `data:read`。
- dataset 必须属于当前项目。
- 没有 `qa_report` 时返回空报告状态，不报 500。

Codex 提示词：

```text
step 3：新增读取数据集 QA 报告 API

请为上传后模拟质控新增只读 API：GET /api/v1/projects/{project_id}/datasets/{dataset_id}/qa。

要求：
1. 在 backend/app/routers/datasets.py 中实现，或拆到清晰的子路由后挂载。
2. 使用现有项目读权限和 data:read 权限模式。
3. 校验 dataset_id 属于 project_id。
4. 返回 dataset_id、project_id、qa_status、qa_report、has_report、current_upload_id、imported_at 等必要信息。
5. 如果 datasets.qa_report 为空，返回 has_report=false 和一个清晰的空状态，不要报错。
6. 不触发 mock-run，不修改数据库。
7. 更新 backend/app/schemas/dataset.py 中对应 response schema。

请补充 API 层测试或最小调用脚本，覆盖有报告和无报告两种情况。

相关执行内容和结果在2_meeting260516中md中同步更新。
```

## Step 4：新增生成模拟质控报告 API

目标：后端能真正把 Step 2 的报告写入 `datasets.qa_report`，但不自动改成 `checked`。

建议 API：

- `POST /api/v1/projects/{project_id}/datasets/{dataset_id}/qa/mock-run`

行为：

- 读取 dataset。
- 调用 `build_mock_qa_report()`。
- 写入 `datasets.qa_report`。
- 如果发现 fatal 文件错误，可选择写 `qa_status='failed'`；若只是 warnings，保持 `converted`。
- 不自动写 `checked`。

完成标准：

- 生成后 GET API 能读到报告。
- 报告 `mode='mock'`。
- `score=null`。
- `checked` 只能由 review API 写入。

Codex 提示词：

```text
step 4：新增生成上传后模拟质控报告 API

请新增 POST /api/v1/projects/{project_id}/datasets/{dataset_id}/qa/mock-run，用于生成并保存 qa_report.mode='mock' 的模拟质控报告。

要求：
1. 使用 Step 2 的 build_mock_qa_report(project, dataset)。
2. 校验当前用户有 data:write 和项目写权限。
3. dataset 必须属于当前 project。
4. 将生成的报告写入 datasets.qa_report。
5. 不要自动把 qa_status 改成 checked。
6. 如果报告存在 blocking_issues，允许将 qa_status 写为 failed；如果只是 warnings，保持原状态，通常是 converted。
7. 返回最新 qa_status 和 qa_report。
8. 报告必须包含 mode='mock'，summary.score 必须为 null，signal_placeholder 必须是 not_computed。

请补充测试：mock-run 后数据库有 qa_report；正常 warning 不会自动 checked；blocking issue 不允许 checked。

相关执行内容和结果在2_meeting260516中md中同步更新。
```

## Step 5：新增人工确认 Review API

目标：让 `checked/rejected/hold` 的状态变化有明确入口，而不是由 mock-run 自动决定。

建议 API：

- `POST /api/v1/projects/{project_id}/datasets/{dataset_id}/qa/review`

入参：

- `conclusion`: `accept / reject / hold`
- `notes`: string

行为：

| conclusion | qa_status | 说明 |
|---|---|---|
| `accept` | `checked` | 只有没有 blocking issues 时允许 |
| `reject` | `rejected` | 用户明确拒绝进入分析 |
| `hold` | 保持 `converted` 或当前非阻断状态 | 暂缓，不阻断 LoadData 默认规则 |

完成标准：

- 人工确认写入 `qa_report.human_review`。
- `accept` 遇到 blocking issue 返回 409 或 422。
- 不覆盖已有 stages。

Codex 提示词：

```text
step 5：新增上传后模拟质控人工确认 Review API

请新增 POST /api/v1/projects/{project_id}/datasets/{dataset_id}/qa/review，用于提交人工确认结论并更新 qa_status。

要求：
1. 入参 conclusion 支持 accept、reject、hold；notes 可选。
2. 使用 data:write 和项目写权限。
3. dataset 必须属于当前 project。
4. 如果 conclusion=accept，只有 qa_report 存在且 summary.blocking_issues 为空时，才允许写 qa_status='checked'。
5. 如果 conclusion=reject，写 qa_status='rejected'。
6. 如果 conclusion=hold，不写 checked，优先保持 converted；如果当前是 failed/rejected，不要静默恢复。
7. 将 human_review 写入 datasets.qa_report.human_review，包含 conclusion、notes、reviewed_by、reviewed_at。
8. 不删除 qa_report.stages，不伪造真实信号指标。

请补充测试：accept 成功、accept 被 blocking issue 拒绝、reject 写 rejected、hold 不写 checked。

相关执行内容和结果在2_meeting260516中md中同步更新。
```

## Step 6：补充审计记录和状态历史

目标：数据状态变化有审计线索，便于后续追溯谁确认了数据。

第一版可选方案：

- 复用 `project_audit_events` 写入 `dataset.qa.mock_run`、`dataset.qa.review`。
- 不新增 `dataset_qa_runs` 表，避免第一版范围变大。
- 在 `qa_report.history` 中追加简短记录。

完成标准：

- mock-run 和 review 都能看到审计事件。
- 审计 metadata 不保存大对象，只保存 dataset_id、old/new status、conclusion。

Codex 提示词：

```text
step 6：为上传后模拟质控补充审计记录和状态历史

请为 mock-run 和 review 两个动作补充轻量审计，不新增数据库表。

要求：
1. 优先复用 project_audit_events，写入 action：dataset.qa.mock_run 和 dataset.qa.review。
2. metadata 至少包含 dataset_id、current_upload_id、old_qa_status、new_qa_status、conclusion、has_blocking_issues。
3. 如果项目已有审计 helper，沿用现有 helper；如果没有，保持实现简洁。
4. 在 qa_report.history 中追加一条简短历史记录，包含 action、actor_id、at、status。
5. 不把完整 qa_report 大对象塞进 audit metadata。
6. 不新增真实信号 QC 计算。

请补充测试或最小脚本验证：mock-run 与 review 后能生成审计记录或 history。

相关执行内容和结果在2_meeting260516中md中同步更新。
```

## Step 7：前端补齐 Dataset QA 类型和 API

目标：前端可以调用 QA API，并有明确 TypeScript 类型。

建议改动：

- `frontend/elys-web/src/types/index.ts`
- `frontend/elys-web/src/api/datasets.ts`

新增 API：

- `getQa(projectId, datasetId)`
- `runMockQa(projectId, datasetId)`
- `reviewQa(projectId, datasetId, payload)`

完成标准：

- 类型覆盖 response/report/stage/item/review。
- API 封装路径与后端一致。
- 前端 build 通过。

Codex 提示词：

```text
step 7：前端补齐上传后模拟质控类型和 API 封装

请在前端补齐 Dataset QA 相关类型和 API 封装。

要求：
1. 在 frontend/elys-web/src/types/index.ts 中定义 DatasetQaReport、DatasetQaStage、DatasetQaStageItem、DatasetQaSummary、DatasetQaHumanReview、DatasetQaResponse、DatasetQaReviewRequest 等类型。
2. qa_report.mode 支持 mock/real，但当前 UI 按 mock 处理。
3. 在 frontend/elys-web/src/api/datasets.ts 中新增 getQa、runMockQa、reviewQa。
4. API 路径必须与后端保持一致：
   - GET /projects/{projectId}/datasets/{datasetId}/qa
   - POST /projects/{projectId}/datasets/{datasetId}/qa/mock-run
   - POST /projects/{projectId}/datasets/{datasetId}/qa/review
5. 保持现有 list/upload API 兼容。

请运行前端 TypeScript/build 检查；如果当前项目已有 lint/build 命令，优先使用现有命令。

相关执行内容和结果在2_meeting260516中md中同步更新。
```

## Step 8：项目数据列表增加 QA 状态入口

目标：用户上传数据后，在项目数据列表里能看到状态，并能进入模拟质控操作。

建议页面：

- 第一优先：`ProjectDetailPage.vue`。
- 可选同步：`Dashboard.vue` 最近导入列表。

UI 建议：

- 数据行显示 `qa_status` 徽章。
- 显示 `converted/checked/failed/rejected` 的颜色区分。
- 增加“质控”按钮或图标。
- 点击后打开右侧面板或弹窗。

完成标准：

- 不创建完整新路由也可以完成第一版。
- 不展示真实信号分数。
- 没有 qa_report 时显示“尚未运行模拟质控”。

Codex 提示词：

```text
step 8：项目数据列表增加上传后模拟质控入口

请在前端项目数据列表中增加 QA 状态展示和模拟质控入口，优先修改 ProjectDetailPage.vue。

要求：
1. 每个 dataset 行显示 qa_status 徽章：converted、checked、failed、rejected、pending、unknown。
2. 增加“质控”入口按钮，点击后打开详情面板或弹窗。
3. 进入时调用 datasetApi.getQa(projectId, datasetId)。
4. 如果没有 qa_report，显示“尚未运行模拟质控”，并提供“运行模拟质控”按钮。
5. 如果 qa_report.mode='mock'，明确显示“模拟质控，真实信号指标未计算”。
6. 不展示真实 RMS/PSD/坏段结论。
7. 保持页面响应式和现有设计风格。

请运行前端 build 或至少 TypeScript 检查，确保页面无类型错误。

相关执行内容和结果在2_meeting260516中md中同步更新。
```

## Step 9：实现 QA 详情面板和阶段清单

目标：让用户能看懂每一项检查做了什么、哪些通过、哪些只是警告、哪些阻断。

展示内容：

- 总览：状态、模式、生成时间、blocking issues、warnings。
- stages 列表。
- 每个 stage 展示 key/title/status/severity/message/items。
- `signal_placeholder` 必须明显显示未计算。

完成标准：

- 正常报告可读。
- 有 blocking issues 时醒目。
- 没有报告时空状态清楚。

Codex 提示词：

```text
step 9：实现上传后模拟质控详情面板和阶段清单

请实现 QA 详情面板，用于展示 qa_report 的 summary、stages 和 human_review。

要求：
1. 可以在 ProjectDetailPage.vue 内部实现，也可以抽成 DatasetQaPanel.vue 组件。
2. 展示 summary：mock_qc_status、level、blocking_issues、warnings、generated_at。
3. 展示 stages：preflight、identity、file_integrity、metadata_consistency、fif_header、channels_sidecar、events_sidecar、signal_placeholder。
4. 每个 stage 展示 status、severity、message 和 items。
5. signal_placeholder 必须显示“真实 RMS/PSD/坏段指标尚未实现”。
6. blocking issue 用明显错误状态展示；warning 用警告状态展示。
7. qa_report.mode='mock' 时，始终显示“模拟质控”标识。

请补充最小组件测试或手动验证说明，确保无报告、有 warning、有 blocking issue 三种状态显示合理。

相关执行内容和结果在2_meeting260516中md中同步更新。
```

## Step 10：实现前端运行模拟质控按钮

目标：用户能手动触发 mock-run，并看到报告刷新。

行为：

- 点击“运行模拟质控”。
- 按钮进入 loading。
- 调用 `datasetApi.runMockQa()`。
- 成功后刷新面板和数据列表。
- 失败时显示后端错误。

完成标准：

- 不能重复点击造成多次并发。
- 成功后能看到 `mode='mock'` 报告。
- 不自动显示为真实信号质量通过。

Codex 提示词：

```text
step 10：实现上传后模拟质控运行按钮

请在 QA 详情面板中实现“运行模拟质控”按钮。

要求：
1. 点击按钮调用 datasetApi.runMockQa(projectId, datasetId)。
2. 请求期间按钮 loading/disabled，避免重复提交。
3. 成功后刷新当前 QA 报告，并同步刷新项目数据列表中的 qa_status。
4. 后端返回 blocking issue 时，前端展示为阻断，但不要崩溃。
5. 报告 mode='mock' 时必须显示模拟标识。
6. 不自动把数据展示为 checked，除非后端 qa_status 已经因其他原因返回 checked。

请运行前端 build 或最小手动验证：无报告 -> 点击运行 -> 报告出现。

相关执行内容和结果在2_meeting260516中md中同步更新。
```

## Step 11：实现人工确认按钮

目标：用户能通过、暂缓或拒绝一份数据，并让 `qa_status` 反映人工结论。

操作：

- 通过：`conclusion=accept`，成功后 `qa_status=checked`。
- 暂缓：`conclusion=hold`，保持 `converted` 或当前非阻断状态。
- 拒绝：`conclusion=reject`，成功后 `qa_status=rejected`。

完成标准：

- 有 blocking issues 时通过按钮应禁用或后端拒绝。
- notes 可填写。
- 操作后刷新数据列表和面板。

Codex 提示词：

```text
step 11：实现上传后模拟质控人工确认按钮

请在 QA 详情面板中实现人工确认操作：通过、暂缓、拒绝。

要求：
1. 支持填写 notes。
2. 通过按钮调用 reviewQa，payload 为 conclusion='accept'，成功后 qa_status 应为 checked。
3. 暂缓按钮 payload 为 conclusion='hold'，不应写 checked。
4. 拒绝按钮 payload 为 conclusion='reject'，成功后 qa_status 应为 rejected。
5. 如果 summary.blocking_issues 非空，前端应禁用“通过”按钮或显示不可通过原因；后端仍应做最终校验。
6. 操作成功后刷新 QA 报告和项目数据列表。
7. human_review 区域展示 reviewed_by、reviewed_at、conclusion、notes。

请运行前端 build，并手动说明 accept/hold/reject 三种交互如何验证。

相关执行内容和结果在2_meeting260516中md中同步更新。
```

## Step 12：LoadData 面板显示 QA 摘要

目标：工作流选择数据时，用户能看到哪些数据只是 `converted`，哪些已经 `checked`。

建议改动：

- `PipelinePage.vue` 的 LoadData 数据表。
- 增加列或徽章：
  - qa_status
  - mock_qc_status
  - warning/blocking 数量
- 可选增加筛选：只看 checked。

完成标准：

- 不改变默认选择规则：`converted` 和 `checked` 仍可选。
- `failed/rejected/deleted` 仍强制排除。
- UI 不声称 mock 是真实信号 QC。

Codex 提示词：

```text
step 12：在 LoadData 面板显示上传后模拟质控摘要

请在 PipelinePage.vue 的 LoadData 数据选择表格中显示 dataset 的 QA 状态摘要。

要求：
1. 数据行展示 qa_status 徽章，checked 应比 converted 更醒目但不要改变默认选择逻辑。
2. 如果 dataset.qa_report.mode='mock'，显示“模拟质控”标识。
3. 显示 blocking issue 数量和 warning 数量；没有报告时显示“未检查”。
4. failed、rejected、deleted 仍应被现有 isDatasetEligibleForLoad 或后端解析强制排除。
5. 可选增加“只看 checked”筛选，但默认仍允许 converted + checked。
6. 不展示真实 RMS/PSD/坏段结果。

请运行前端 build，并说明用 converted、checked、rejected 三类数据如何手动验证 LoadData 展示。

相关执行内容和结果在2_meeting260516中md中同步更新。
```

## Step 13：后端测试补齐

目标：让后端逻辑可回归，避免状态误写。

测试范围：

- `build_mock_qa_report()`。
- `GET qa`。
- `POST mock-run`。
- `POST review`。
- 权限和项目隔离。

关键用例：

| 用例 | 期望 |
|---|---|
| 无 qa_report | GET 返回 has_report=false |
| 正常 converted dataset | mock-run 写 mode=mock，保持 converted |
| FIF 缺失 | mock-run 有 blocking issue，不能 accept |
| accept | 写 checked |
| reject | 写 rejected |
| hold | 不写 checked |
| 跨项目 dataset_id | 404 或权限错误 |

Codex 提示词：

```text
step 13：补齐上传后模拟质控后端测试

请为上传后模拟质控补齐后端测试，覆盖服务函数和 API 行为。

要求：
1. 测试 build_mock_qa_report：正常 dataset、缺少 fif_path、FIF 文件缺失、缺少 metadata。
2. 测试 GET /qa：无报告返回 has_report=false，有报告返回完整结构。
3. 测试 POST /qa/mock-run：写入 qa_report.mode='mock'，不自动写 checked。
4. 测试 POST /qa/review：accept 写 checked，reject 写 rejected，hold 不写 checked。
5. 测试 accept 遇到 blocking_issues 时失败。
6. 测试 dataset 不属于 project 时不可访问。
7. 如果当前测试环境没有真实 PostgreSQL，可使用项目已有测试模式或最小 fake/mock，但要说明限制。

请运行相关后端测试，并把命令和结果记录下来。

相关执行内容和结果在2_meeting260516中md中同步更新。
```

## Step 14：前端测试和交互验证

目标：前端类型、构建和关键交互不破。

检查：

- TypeScript build。
- 项目详情页打开。
- 数据行 QA 状态。
- QA 面板空状态。
- mock-run loading/success/error。
- accept/hold/reject 操作。
- LoadData 表格 QA 摘要。

Codex 提示词：

```text
step 14：补齐上传后模拟质控前端测试和交互验证

请为上传后模拟质控补齐前端构建检查和关键交互验证。

要求：
1. 运行前端 build/typecheck，修复类型错误。
2. 验证 ProjectDetailPage.vue 数据列表显示 qa_status 徽章。
3. 验证 QA 面板无报告、有 mock 报告、有 blocking issue 三种状态。
4. 验证运行模拟质控按钮的 loading、成功、错误提示。
5. 验证人工确认 accept/hold/reject 后页面刷新和状态变化。
6. 验证 PipelinePage.vue 的 LoadData 表格显示 QA 摘要。
7. 如果能启动本地前端，请用浏览器截图或文字说明验证结果；如果不能启动，请说明原因。

相关执行内容和结果在2_meeting260516中md中同步更新。
```

## Step 15：最小端到端手动验证

目标：用真实操作或最小脚本走完一条链路。

推荐链路：

1. 登录。
2. 创建或选择项目。
3. 上传一组 BrainVision/EDF/BDF 数据。
4. 确认数据进入 `converted`。
5. 打开项目数据列表，运行模拟质控。
6. 查看报告。
7. 点击通过，确认 `qa_status=checked`。
8. 进入 Pipeline，LoadData 能看到该数据且标记 checked。
9. 点击拒绝另一份数据，确认 LoadData 默认排除。

完成标准：

- 写出手动验证记录。
- 若 Redis/worker/真实数据不可用，说明替代验证方式。

Codex 提示词：

```text
step 15：执行上传后模拟质控最小端到端验证

请执行或设计一条最小端到端验证，确认上传后模拟质控可以串起来。

验证目标：
1. 上传或准备一个已有 converted dataset。
2. 在项目数据列表打开 QA 面板。
3. 运行模拟质控，生成 qa_report.mode='mock'。
4. 查看 stages 和 signal_placeholder。
5. 点击 accept，确认 qa_status='checked'。
6. 进入 Pipeline LoadData，确认该数据可见且显示 checked/模拟质控摘要。
7. 对另一份数据点击 reject，确认 qa_status='rejected' 后 LoadData 默认排除。

如果当前环境无法启动完整前后端或没有真实 EEG 文件，请用最小脚本/API mock 验证，并明确说明未完成的手动项。

相关执行内容和结果在2_meeting260516中md中同步更新。
```

## Step 16：同步 wiki 和本目录结果

目标：代码实现后，把实际完成状态回写正式 wiki 和讨论文档。

需要同步：

- `wiki/docs/M2-15-上传后模拟质控流程.md`
- `wiki/docs/M2-00-数据质控模块总览.md`
- `wiki/docs/M2-50-质控报告.md`
- `wiki/docs/M1-30-数据导入.md`
- `wiki/docs/2-50-API设计总览.md`
- `wiki/docs/4-07-数据质控页.md`
- 本文档执行结果区

完成标准：

- 已实现写成已实现。
- 仍未实现的真实信号 QC 继续标为规划。
- 不把模拟质控写成真实算法能力。

Codex 提示词：

```text
step 16：同步上传后模拟质控实现结果到 wiki 和会议文档

请根据当前代码实际实现情况，同步更新上传后模拟质控相关文档。

需要更新：
1. wiki/docs/M2-15-上传后模拟质控流程.md：把已实现 API、页面、验收状态写清楚。
2. wiki/docs/M2-00-数据质控模块总览.md：更新 M2-15 状态。
3. wiki/docs/M2-50-质控报告.md：更新 qa_report.mode='mock' 的实现状态。
4. wiki/docs/M1-30-数据导入.md：说明导入后可进入模拟质控。
5. wiki/docs/2-50-API设计总览.md：补充 GET /qa、POST /qa/mock-run、POST /qa/review。
6. wiki/docs/4-07-数据质控页.md：同步前端页面状态。
7. 2_meeting260516/15-上传后模拟质控流程Codex分步开发提示词.md：在执行记录中写明完成情况、测试命令、未完成项。

注意：
- 真实 RMS/PSD/坏段/坏通道算法如果仍未实现，必须继续写为规划。
- 模拟质控必须明确标注 mode='mock'。
- 不要把导入成功直接写成质量通过。

请运行 mkdocs build --strict 或当前项目文档构建命令，并记录结果。

相关执行内容和结果在2_meeting260516中md中同步更新。
```

## 执行记录模板

后续每次执行一个 step 后，在本文末尾按以下格式追加记录：

```md
## 执行记录：Step x

- 执行日期：
- 执行范围：
- 修改文件：
- 后端验证：
- 前端验证：
- 文档同步：
- 未完成项：
- 下一步建议：
```

## 执行记录：Step 0

- 执行日期：2026-05-18
- 执行范围：只读审计当前代码和正式 wiki，不改业务功能。
- 修改文件：仅更新本文档的 Step 0 审计记录。
- 审计依据：
  - `elys_version1/backend/app/models/project.py`
  - `elys_version1/backend/app/schemas/dataset.py`
  - `elys_version1/backend/app/routers/datasets.py`
  - `elys_version1/database/init.sql`
  - `elys_version1/frontend/elys-web/src/api/datasets.ts`
  - `elys_version1/frontend/elys-web/src/types/index.ts`
  - `elys_version1/frontend/elys-web/src/views/ProjectDetailPage.vue`
  - `elys_version1/frontend/elys-web/src/views/Dashboard.vue`
  - `elys_version1/frontend/elys-web/src/views/PipelinePage.vue`
  - `wiki/docs/M2-15-上传后模拟质控流程.md`

### 1. 当前已具备的字段和接口

#### 1.1 后端模型和数据库

`Dataset` 已经具备模拟质控所需的核心字段：

| 字段 | 当前状态 | 说明 |
|---|---|---|
| `datasets.qa_status` | 已有 | `String(16)`，默认 `pending`。 |
| `datasets.qa_report` | 已有 | `JSONB`，可直接承载 M2-15 的 mock report。 |
| `datasets.current_upload_id` | 已有 | 指向当前 `DatasetUpload`。 |
| `datasets.fif_path` | 已有 | 当前工作 FIF 路径。 |
| `datasets.source_path` | 已有 | `source_uploads/` 主原始文件路径。 |
| `datasets.n_channels/sfreq/duration_seconds/n_events/checksum` | 已有 | 可用于 metadata consistency 检查。 |

`DatasetUpload` 已经具备版本和 sidecar 信息：

| 字段 | 当前状态 | 说明 |
|---|---|---|
| `dataset_uploads.upload_seq` | 已有 | 上传版本序号。 |
| `dataset_uploads.status` | 已有 | `current/replaced/rejected/failed`。 |
| `dataset_uploads.fif_dir` | 已有 | 当前 FIF 目录。 |
| `dataset_uploads.fif_path` | 已有 | 当前 FIF 文件。 |
| `dataset_uploads.sidecar_paths` | 已有 | JSONB，包含 `eeg/channels/events/import`。 |
| `dataset_uploads.qa_status` | 已有 | 默认 `converted`。 |

`database/init.sql` 中也已经有对应字段，因此第一版模拟质控不需要新增数据库表。需要注意：`datasets.qa_status` 当前没有枚举约束，后续 API 层要自己限制 `pending/converted/checked/failed/rejected/deleted/unknown`。

#### 1.2 后端 schema

`DatasetResponse` 当前已经返回：

- `qa_status`
- `qa_report`
- `current_upload_id`
- `current_upload_seq`
- `current_fif_dir`
- `current_sidecar_paths`
- `fif_path`
- `source_path`
- `n_channels`
- `sfreq`
- `duration_seconds`
- `n_events`
- `checksum`

当前不足：

- `qa_report` 类型只是 `Optional[dict[str, Any]]`，没有结构化的 `DatasetQaReportResponse`。
- 没有 `DatasetQaReviewRequest`。
- 没有 `DatasetQaResponse`。
- 没有 `stage/item/summary/human_review` 等 M2-15 专用 schema。

#### 1.3 后端 list/import 路由

`GET /api/v1/projects/{project_id}/datasets` 已经：

- 校验 `data:read` 和项目可读权限。
- `joinedload(Dataset.subject)` 和 `joinedload(Dataset.current_upload)`。
- 返回 `DatasetListResponse`，其中包含 `qa_status/qa_report/current_upload/current_sidecar_paths`。

`POST /api/v1/projects/{project_id}/datasets/import` 当前已经：

- 支持 BrainVision / EDF / BDF 导入。
- 生成 `source_uploads/` 归档和 `fifdata/` 工作 FIF。
- 写 `channels.tsv`、`events.tsv`、`eeg.json`、`import.json`。
- FIF 写入后会用 MNE 读回校验。
- 新建 dataset 时写 `qa_status='converted'`。
- 重传替换 dataset 时也写 `qa_status='converted'`。
- 写入 `qa_report`，但当前结构只有：
  - `import`
  - `fif_conversion`
  - 替换时额外有 `replacement`

当前不足：

- 没有 `GET /datasets/{dataset_id}/qa`。
- 没有 `POST /datasets/{dataset_id}/qa/mock-run`。
- 没有 `POST /datasets/{dataset_id}/qa/review`。
- 没有专门的 `build_mock_qa_report()` 服务函数。
- `qa_report` 当前不是 M2-15 目标结构，没有 `mode='mock'`、`summary`、`stages`、`human_review`。
- 导入成功只写 `converted`，不会写 `checked`，这与 M2-15 边界一致。

#### 1.4 前端类型和 API

`frontend/elys-web/src/types/index.ts` 中 `Dataset` 已经有：

- `qa_status: string | null`
- `qa_report: Record<string, unknown> | null`
- `current_upload_id`
- `current_upload_seq`
- `current_fif_dir`
- `current_sidecar_paths`

当前不足：

- 没有结构化 `DatasetQaReport` / `DatasetQaStage` / `DatasetQaSummary` / `DatasetQaHumanReview` 类型。
- 没有 `DatasetQaResponse`。
- 没有 `DatasetQaReviewRequest`。

`frontend/elys-web/src/api/datasets.ts` 当前只有：

- `list(projectId)`
- `upload(projectId, payload, options)`

当前不足：

- 没有 `getQa(projectId, datasetId)`。
- 没有 `runMockQa(projectId, datasetId)`。
- 没有 `reviewQa(projectId, datasetId, payload)`。

#### 1.5 前端页面展示

`ProjectDetailPage.vue` 当前：

- 读取项目详情和 dataset list。
- 数据表展示被试、任务、格式、FIF、大小、导入时间。
- FIF 状态仅按 `dataset.fif_path` 显示“已生成/待转换”。
- 没有展示 `qa_status`。
- 没有 QA 面板、mock-run 按钮、review 操作。

`Dashboard.vue` 当前：

- 统计总 dataset 数和 `fif_path` 存在数量。
- 最近活动显示“FIF 已生成 / FIF 待转换”。
- 选中项目的数据表展示被试、任务、session、run、格式、FIF、通道、事件、大小、导入时间。
- 没有展示 `qa_status` 或 `qa_report`。

`PipelinePage.vue` 当前：

- LoadData 面板已有质量状态多选：`converted/checked/pending/unknown`。
- 默认 `DEFAULT_LOAD_DATA_QA_STATUS = ['converted', 'checked']`。
- LoadData 表格有一列直接展示 `dataset.qa_status || '-'`。
- `isDatasetEligibleForLoad()` 会排除 `failed/deleted/rejected`。
- `datasetMatchesLoadFilter()` 会按 `qa_status` 过滤。

当前不足：

- LoadData 不展示 `qa_report.mode`。
- 不展示 mock QC warning/blocking issue 数量。
- 不展示“模拟质控，真实信号指标未计算”。
- 不支持“只看 checked”等额外 UI。

### 2. 最小实现需要新增的文件 / 函数 / API

#### 2.1 后端 schema

建议新增或扩展：

- `backend/app/schemas/dataset.py`

需要的结构：

- `DatasetQaStageItem`
- `DatasetQaStage`
- `DatasetQaSummary`
- `DatasetQaHumanReview`
- `DatasetQaReport`
- `DatasetQaResponse`
- `DatasetQaReviewRequest`
- `DatasetQaReviewResponse`

#### 2.2 后端服务

建议新增：

- `backend/app/services/dataset_qa.py`

核心函数：

- `build_mock_qa_report(project, dataset) -> dict`
- `resolve_project_path(project, path_value) -> Path | None`
- `build_stage(...)`
- `append_qa_history(...)`

模拟检查阶段：

- `preflight`
- `identity`
- `file_integrity`
- `metadata_consistency`
- `fif_header`
- `channels_sidecar`
- `events_sidecar`
- `signal_placeholder`

第一版不做真实 RMS/PSD/坏段算法。

#### 2.3 后端 API

建议新增 3 个 API：

| API | 目标 |
|---|---|
| `GET /api/v1/projects/{project_id}/datasets/{dataset_id}/qa` | 读取当前 `qa_report` 和 `qa_status` |
| `POST /api/v1/projects/{project_id}/datasets/{dataset_id}/qa/mock-run` | 生成并保存 `qa_report.mode='mock'` |
| `POST /api/v1/projects/{project_id}/datasets/{dataset_id}/qa/review` | 人工确认 `accept/reject/hold` 并更新 `qa_status` |

权限建议：

- GET：`data:read` + 项目可读。
- mock-run/review：`data:write` + 项目可写。

#### 2.4 前端类型和 API

建议改动：

- `frontend/elys-web/src/types/index.ts`
- `frontend/elys-web/src/api/datasets.ts`

新增：

- QA report 结构化类型。
- `datasetApi.getQa()`
- `datasetApi.runMockQa()`
- `datasetApi.reviewQa()`

#### 2.5 前端入口

第一版优先落在：

- `ProjectDetailPage.vue`

原因：

- 它已经是单项目数据列表。
- 代码比 Dashboard 简单。
- 用户语义最直接：进入项目后查看数据集并运行质控。

后续再同步：

- `Dashboard.vue`：只显示摘要，不做完整操作。
- `PipelinePage.vue`：LoadData 只消费 `qa_status/qa_report` 摘要，不负责运行质控。

### 3. 第一轮最推荐落地范围

建议第一轮只做最小闭环，不做独立质控页：

1. 后端 schema：定义 QA report / review 契约。
2. 后端服务：实现 `build_mock_qa_report()`，输出 `mode='mock'`。
3. 后端 API：实现 GET QA、mock-run、review。
4. 前端 API/types：补齐 `getQa/runMockQa/reviewQa`。
5. `ProjectDetailPage.vue`：数据表展示 `qa_status`，加一个“质控”按钮和右侧/弹窗面板。
6. QA 面板：展示 stages、warnings、blocking issues、signal placeholder。
7. 人工确认：accept 写 `checked`，reject 写 `rejected`，hold 保持 `converted`。
8. `PipelinePage.vue`：只增加 mock QA 摘要展示，不改变默认选择逻辑。

暂不做：

- 独立 `4-07 数据质控页` 完整页面。
- 项目级批量质控。
- 真实 RMS / PSD / 坏段 / 坏通道算法。
- 复杂 QC 分数。
- 新增 `dataset_qa_runs` 表。
- Celery 异步队列。

### 4. 测试缺口

#### 4.1 后端测试

需要补：

- `build_mock_qa_report()` 正常 dataset。
- 缺 `fif_path`。
- `fif_path` 记录存在但文件缺失。
- 缺 metadata 字段。
- `GET /qa` 无报告 / 有报告。
- `POST /qa/mock-run` 写入 `mode='mock'`，不自动写 `checked`。
- `POST /qa/review`：
  - `accept` 成功写 `checked`。
  - 有 blocking issue 时 `accept` 失败。
  - `reject` 写 `rejected`。
  - `hold` 不写 `checked`。
- dataset 跨项目访问必须失败。

#### 4.2 前端测试

需要补：

- `Dataset` QA 类型编译。
- `datasetApi` 新 API 路径正确。
- ProjectDetailPage 数据表 qa_status 徽章。
- QA 面板空状态。
- QA 面板展示 `mode='mock'` 和 signal placeholder。
- mock-run loading/success/error。
- accept/hold/reject 状态刷新。
- PipelinePage LoadData 显示 QA 摘要。

#### 4.3 手动验证

需要准备至少一份 `converted` dataset：

1. 打开项目详情。
2. 点击“质控”。
3. 运行模拟质控。
4. 看到 `qa_report.mode='mock'`。
5. 点击通过，状态变 `checked`。
6. 进入 Pipeline LoadData，确认该数据仍可选并显示 `checked`。
7. 点击拒绝另一份数据，状态变 `rejected`，LoadData 默认排除。

### 5. 本次验证

- 后端验证：只做静态审计，使用 `rg` 和文件片段核对字段、schema、路由和写入逻辑；未运行后端单元测试。
- 前端验证：只做静态审计，核对 `types/index.ts`、`api/datasets.ts`、`ProjectDetailPage.vue`、`Dashboard.vue`、`PipelinePage.vue`；未运行前端 build。
- 文档同步：已将 Step 0 审计结论写入本文档。
- 未完成项：没有实现任何业务功能；Step 1 起再进入 schema 和代码改造。
- 下一步建议：执行 Step 1，先定义后端 QA schema 和状态常量；不要先写 UI，也不要先做真实信号算法。

## 执行记录：Step 1

- 执行日期：2026-05-18
- 执行范围：定义上传后模拟质控后端 Pydantic schema 和状态常量；不实现业务逻辑、不新增数据库表、不改变现有 `DatasetResponse` 兼容性。
- 修改文件：
  - `elys_version1/backend/app/schemas/dataset.py`
  - `elys_version1/backend/app/schemas/__init__.py`
  - `2_meeting260516/15-上传后模拟质控流程Codex分步开发提示词.md`

### 1. 本次新增的后端常量

在 `backend/app/schemas/dataset.py` 中新增：

| 常量 | 值 | 用途 |
|---|---|---|
| `DATASET_QA_REPORT_VERSION` | `v1` | 当前 QA report schema 版本 |
| `DATASET_QA_MODE_MOCK` | `mock` | 模拟质控模式 |
| `DATASET_QA_MODE_REAL` | `real` | 未来真实质控模式预留 |
| `DATASET_QA_REVIEW_ACCEPT` | `accept` | 人工确认通过 |
| `DATASET_QA_REVIEW_REJECT` | `reject` | 人工拒绝 |
| `DATASET_QA_REVIEW_HOLD` | `hold` | 人工暂缓 |

同时定义了 Literal 类型：

- `DatasetQaMode = Literal["mock", "real"]`
- `DatasetQaReviewConclusion = Literal["accept", "reject", "hold"]`
- `DatasetQaStageStatus = Literal["pass", "warning", "fail", "not_computed", "skipped", "pending"]`
- `DatasetQaSeverity = Literal["info", "warning", "error"]`

### 2. 本次新增的 Pydantic schema

在 `backend/app/schemas/dataset.py` 中新增：

| Schema | 作用 |
|---|---|
| `DatasetQaStageItem` | 单个检查项，例如 FIF 文件存在、RMS 未计算 |
| `DatasetQaStage` | 一个检查阶段，例如 file_integrity、signal_placeholder |
| `DatasetQaSummary` | 报告摘要，包含 `mock_qc_status/level/score/blocking_issues/warnings` |
| `DatasetQaHumanReview` | 人工确认结果，包含 `conclusion/notes/reviewed_by/reviewed_at` |
| `DatasetQaReport` | 完整 QA report，包含 `version/mode/generated_at/summary/stages/human_review/history` |
| `DatasetQaResponse` | GET QA 报告接口响应预留 |
| `DatasetQaMockRunResponse` | mock-run 接口响应预留 |
| `DatasetQaReviewRequest` | review 请求，支持 `accept/reject/hold` 和 `notes` |
| `DatasetQaReviewResponse` | review 响应预留 |

关键约束：

- `mode` 允许 `mock/real`，默认 `mock`。
- `score` 是 `Optional[float]`，mock 模式下允许为 `null`。
- `stages` 默认空数组。
- `human_review` 默认空对象。
- `DatasetResponse.qa_report` 保持 `Optional[dict[str, Any]]`，没有改成强类型，避免破坏现有导入级 `qa_report` 结构。

### 3. 导出情况

`backend/app/schemas/__init__.py` 已导出新增 schema 和常量，后续 router/service 可以从 `app.schemas` 或 `app.schemas.dataset` 引用。

### 4. 后端验证

已执行 import smoke：

| 验证项 | 结果 |
|---|---|
| 直接从 `app.schemas.dataset` 导入 `DatasetQaReport/DatasetQaReviewRequest/DatasetQaStage/DatasetQaStageItem` | 通过 |
| 实例化 `DatasetQaReport(mode="mock")`，确认 `summary.score is None` | 通过 |
| 实例化 `DatasetQaStage(status="not_computed")` | 通过 |
| 从 `app.schemas` 导入 `DatasetQaReport/DatasetQaReviewRequest/DATASET_QA_REPORT_VERSION` | 通过 |
| `DatasetQaReviewRequest(conclusion="approve")` 触发 Pydantic `ValidationError` | 通过 |

说明：验证只覆盖 schema import 和基础字段约束；本步骤不涉及数据库连接、API 路由或业务写入。

### 5. 前端验证

本步骤没有前端代码改动，未运行前端 build。

### 6. 文档同步

已将 Step 1 执行结果写入本文档。

### 7. 未完成项

- 尚未实现 `build_mock_qa_report()`。
- 尚未新增 `GET /qa`、`POST /qa/mock-run`、`POST /qa/review`。
- 尚未写入 `qa_report.mode='mock'` 的业务逻辑。
- 尚未实现前端 QA API/types。
- 尚未实现真实 RMS/PSD/坏段算法，且本阶段明确不做。

### 8. 下一步建议

执行 Step 2：新增后端模拟质控报告生成服务 `build_mock_qa_report(project, dataset) -> dict`。下一步仍然先不接 API，先把报告结构和检查阶段做成可测试的纯服务。

## 执行记录：Step 2

- 执行日期：2026-05-18
- 执行范围：新增纯后端服务，根据 Project + Dataset 构造 `qa_report.mode='mock'` 的模拟质控报告；不接 API、不写数据库、不新增表。
- 修改文件：
  - `elys_version1/backend/app/services/dataset_qa.py`
  - `2_meeting260516/15-上传后模拟质控流程Codex分步开发提示词.md`

### 1. 本次新增服务

新增文件：

```text
elys_version1/backend/app/services/dataset_qa.py
```

暴露函数：

```python
build_mock_qa_report(project, dataset) -> dict[str, Any]
```

函数特点：

- 只读取 `project` 和 `dataset` 字段，不修改数据库对象。
- 不写 `datasets.qa_report`。
- 不修改 `qa_status`。
- 不改变任何 FIF/source/sidecar 文件。
- 返回值经过 Step 1 的 `DatasetQaReport` Pydantic schema 规整后 `model_dump(mode="json")`。

### 2. 报告结构

当前生成的报告包含：

| 字段 | 当前行为 |
|---|---|
| `version` | `v1` |
| `mode` | 固定 `mock` |
| `generated_at` | 当前 UTC 时间 |
| `summary.mock_qc_status` | `passed / passed_with_warnings / blocked` |
| `summary.level` | `good / warning / bad` |
| `summary.score` | 固定 `null` |
| `summary.blocking_issues` | 致命问题代码数组 |
| `summary.warnings` | 普通警告文本数组 |
| `stages` | 八个模拟质控阶段 |
| `human_review` | 空 review 对象 |
| `history` | 空数组 |

### 3. 已实现 stages

| stage key | 标题 | 当前检查内容 |
|---|---|---|
| `preflight` | 前置状态 | dataset id、current_upload/current_upload_id、当前 `qa_status` |
| `identity` | 数据身份检查 | subject、task、session、run |
| `file_integrity` | 文件完整性检查 | `source_path`、`fif_path`、`current_upload.sidecar_paths.import/channels/events` 指向的文件是否存在 |
| `metadata_consistency` | 元数据一致性检查 | `n_channels`、`sfreq`、`duration_seconds`、`n_events`、`checksum` |
| `fif_header` | FIF 头部快速读取 | 轻量 `mne.io.read_raw_fif(..., preload=False)`；不改变文件 |
| `channels_sidecar` | 通道清单检查 | 读取 `channels.tsv` 行数，与 `n_channels` 做基础对比 |
| `events_sidecar` | 事件清单检查 | 读取 `events.tsv`，检查事件 onset 是否超出数据时长 |
| `signal_placeholder` | 信号质量占位 | 固定 `not_computed`，明确真实 RMS/PSD/坏段指标尚未实现 |

### 4. 致命问题和警告规则

当前会写入 `summary.blocking_issues` 的问题：

- 缺少 dataset id：`dataset_id_missing`
- 缺少当前上传版本：`current_upload_missing`
- `fif_path` 未记录或 FIF 文件不存在：`fif_exists`
- `n_channels/sfreq/duration_seconds` 缺失或不合理：`*_invalid`
- FIF 头部读取失败：`fif_header_unreadable`

当前会写入 `summary.warnings` 的问题：

- `qa_status` 不是 `converted/checked`
- source 文件缺失
- import/channels/events sidecar 缺失
- `n_events` 或 `checksum` 缺失
- MNE 不可用时跳过 FIF header
- FIF header 与数据库记录不一致
- channels 行数与 `n_channels` 不一致
- events onset 超出数据时长

### 5. MNE 降级策略

`fif_header` 阶段动态导入 `mne`：

- 如果当前环境有 MNE：只做 `preload=False` 的轻量 FIF 头部读取。
- 如果当前环境缺少 MNE：`fif_header` 写 `status='not_computed'`，并在 warnings 中提示，不让服务崩溃。
- 如果 MNE 可用但 FIF 文件不可读：写 blocking issue `fif_header_unreadable`。

### 6. 后端验证

已执行以下 smoke：

| 验证项 | 结果 |
|---|---|
| `python -m compileall backend/app/services/dataset_qa.py` | 通过 |
| 正常 fake dataset + 真实临时 FIF + source + import/channels/events sidecar | 通过，`mock_qc_status='passed'`，无 blocking issue |
| 缺少 `fif_path` | 通过，`blocking_issues=['fif_exists']`，`mock_qc_status='blocked'` |
| 记录了 `fif_path` 但文件不存在 | 通过，`blocking_issues=['fif_exists']`，`level='bad'` |

验证说明：

- smoke 使用 `types.SimpleNamespace` 构造 Project/Dataset/CurrentUpload，不依赖数据库连接。
- 正常 dataset 验证中，如果当前 Python 环境有 MNE，则用 `mne.io.RawArray` 生成临时真实 FIF；如果缺少 MNE，服务会按降级逻辑处理。
- 本步骤没有运行完整 pytest，因为项目当前没有现成后端 tests 目录；采用脚本 smoke 覆盖三类要求场景。

### 7. 前端验证

本步骤没有前端代码改动，未运行前端 build。

### 8. 文档同步

已将 Step 2 执行结果写入本文档。

### 9. 未完成项

- 尚未新增 `GET /qa`。
- 尚未新增 `POST /qa/mock-run`。
- 尚未新增 `POST /qa/review`。
- 尚未将 `build_mock_qa_report()` 接入 router。
- 尚未写数据库。
- 尚未实现前端 QA 面板。
- 尚未实现真实 RMS/PSD/坏段算法，且本阶段明确不做。

### 10. 下一步建议

执行 Step 3：新增只读 API `GET /api/v1/projects/{project_id}/datasets/{dataset_id}/qa`，先让前端能读取已有 `qa_report` 或空状态，不触发 mock-run，不写数据库。

---

## Step 3 执行记录：新增读取数据集 QA 报告 API

执行时间：2026-05-18

### 1. 本步目标

新增只读 API：

```http
GET /api/v1/projects/{project_id}/datasets/{dataset_id}/qa
```

本接口只读取当前数据集的 QA 状态和已保存的 `qa_report`，不触发模拟质控运行，不调用 `build_mock_qa_report()`，不写数据库。

### 2. 已实现代码

修改文件：

```text
elys_version1/backend/app/routers/datasets.py
```

本次改动包含：

1. 引入 Step 1 已定义的 `DatasetQaReport`、`DatasetQaResponse`、`DatasetQaSummary`。
2. 新增 `dataset_qa_to_response(dataset)`，负责把 ORM dataset 对象转换为 QA 只读响应。
3. 新增路由函数 `get_dataset_qa_report()`。
4. 路由挂载在现有 datasets router 下，因此完整路径为：

```http
GET /api/v1/projects/{project_id}/datasets/{dataset_id}/qa
```

### 3. 权限与归属校验

当前实现沿用现有数据读取权限模式：

1. 先调用 `require_system_permission(current_user, "data:read", ...)`，要求用户具备数据读取权限。
2. 再调用 `require_project_read(...)`，要求用户对项目具备读取权限。
3. 查询数据集时同时约束：

```python
Dataset.project_id == project.id
Dataset.id == dataset_id
```

因此即使传入其他项目的数据集 ID，也不会跨项目返回。

### 4. 响应行为

返回结构复用 `DatasetQaResponse`：

```python
class DatasetQaResponse(BaseModel):
    dataset_id: str
    project_id: str
    qa_status: Optional[str] = None
    qa_report: Optional[DatasetQaReport] = None
    has_report: bool = False
    current_upload_id: Optional[str] = None
    imported_at: Optional[datetime] = None
```

具体行为：

| 场景 | 返回行为 |
|---|---|
| `datasets.qa_report` 有内容 | `has_report=true`，尝试按 `DatasetQaReport` 返回结构化报告 |
| `datasets.qa_report` 为 `None` 或空对象 | `has_report=false`，`qa_report=null`，不报错 |
| `datasets.qa_report` 存在但不符合当前 v1 schema | 返回 fallback 报告，`summary.mock_qc_status='unparsed'`，提示存量报告结构不匹配 |
| dataset 不属于当前 project | 404，返回“数据集不存在” |

### 5. 本步没有做的事

本步保持只读边界：

- 没有触发 mock-run。
- 没有调用 `build_mock_qa_report()`。
- 没有修改 `datasets.qa_status`。
- 没有修改 `datasets.qa_report`。
- 没有新增数据库表或字段。
- 没有改前端入口。

### 6. 后端验证

已执行以下验证：

| 验证项 | 结果 |
|---|---|
| `python -m compileall elys_version1/backend/app/routers/datasets.py` | 通过 |
| 轻量 API smoke：验证 `/{dataset_id}/qa` 路由已注册 | 通过 |
| 轻量 API smoke：dataset 有 `qa_report` 时返回 `has_report=true`、`qa_report.mode='mock'` | 通过 |
| 轻量 API smoke：dataset 无 `qa_report` 时返回 `has_report=false`、`qa_report=null` | 通过 |

验证说明：

- 当前默认 Python 环境缺少 `fastapi`，因此没有直接启动完整 FastAPI 应用。
- smoke 使用轻量 stub 模拟 `fastapi`、`sqlalchemy`、`Project/Dataset/User` 和 DB query，只验证本次新增路由的注册、权限调用路径和响应转换行为。
- 本步未运行完整 pytest，因为项目当前没有现成后端 tests 目录，且本次目标是只读 API 的最小落地。

### 7. 下一步建议

执行 Step 4：新增 `POST /api/v1/projects/{project_id}/datasets/{dataset_id}/qa/mock-run`，把 Step 2 的 `build_mock_qa_report(project, dataset)` 接入 router，并把生成结果写入 `datasets.qa_report` 与 `datasets.qa_status`。该步骤需要重点处理事务提交、失败回滚、重复运行覆盖策略，以及前端触发入口。

---

## Step 4 执行记录：新增生成上传后模拟质控报告 API

执行时间：2026-05-18

### 1. 本步目标

新增写入型 API：

```http
POST /api/v1/projects/{project_id}/datasets/{dataset_id}/qa/mock-run
```

用于调用 Step 2 的 `build_mock_qa_report(project, dataset)` 生成 `qa_report.mode='mock'` 的模拟质控报告，并保存到 `datasets.qa_report`。

### 2. 已实现代码

修改文件：

```text
elys_version1/backend/app/routers/datasets.py
```

新增内容：

1. 引入 `build_mock_qa_report()`。
2. 引入 `DatasetQaMockRunResponse` 和 `DATASET_QA_MODE_MOCK`。
3. 新增 `validate_mock_qa_report_payload(report)`，校验 mock 报告硬性约定。
4. 新增 `apply_mock_qa_status(dataset, qa_report)`，集中处理 mock-run 后的 `qa_status` 更新规则。
5. 新增路由函数 `run_dataset_mock_qa_report()`。

新增测试文件：

```text
elys_version1/backend/tests/test_dataset_qa_mock_run.py
```

### 3. 权限与归属校验

当前实现使用写权限边界：

1. 调用 `require_system_permission(current_user, "data:write", ...)`，要求用户具备数据写权限。
2. 调用 `require_project_write(...)`，要求用户对项目具备写权限。
3. 查询 dataset 时同时约束：

```python
Dataset.project_id == project.id
Dataset.id == dataset_id
```

因此不会跨项目生成或覆盖其他项目的数据集 QA 报告。

### 4. 写库行为

当前写库边界：

1. 调用 `build_mock_qa_report(project, dataset)`。
2. 用 `DatasetQaReport` 校验报告结构。
3. 将报告保存到：

```python
dataset.qa_report = qa_report.model_dump(mode="json")
```

4. 根据 blocking 情况更新状态：

```python
if qa_report.summary.blocking_issues:
    dataset.qa_status = "failed"
```

5. 提交事务：

```python
db.commit()
db.refresh(dataset)
```

如果 `db.commit()` 失败，会执行 `db.rollback()` 后继续抛出异常。

### 5. qa_status 规则

本步明确不自动写 `checked`。

| 报告结果 | 当前行为 |
|---|---|
| 无 blocking，无 warnings | 保存 `qa_report`，`qa_status` 保持原状态 |
| 无 blocking，有 warnings | 保存 `qa_report`，`qa_status` 保持原状态，通常仍为 `converted` |
| 有 blocking_issues | 保存 `qa_report`，`qa_status` 写为 `failed` |
| 原状态为 `checked` 但新报告有 blocking | 强制写为 `failed`，不允许继续保持 `checked` |

说明：如果后续要支持“blocking 修复后从 `failed` 回到 `converted` 或其他状态”，建议另设明确规则；本步严格按当前提示词，只在存在 blocking 时写 `failed`，其他情况保持原状态。

### 6. mock 报告硬性约定

`validate_mock_qa_report_payload()` 当前校验：

| 约定 | 当前校验 |
|---|---|
| 报告必须可被 `DatasetQaReport` 解析 | 是 |
| `mode` 必须为 `mock` | 是 |
| `summary.score` 必须为 `null` | 是 |
| 必须存在 `signal_placeholder` stage | 是 |
| `signal_placeholder.status` 必须为 `not_computed` | 是 |

如果不满足这些约定，接口返回 500，提示“模拟质控报告未满足 mock 模式约定”或报告结构无效。

### 7. API 返回

返回结构使用 `DatasetQaMockRunResponse`：

```python
class DatasetQaMockRunResponse(BaseModel):
    dataset_id: str
    project_id: str
    qa_status: str
    qa_report: DatasetQaReport
```

返回的是提交后的最新 `qa_status` 和本次生成的 `qa_report`。

### 8. 后端验证

已执行以下验证：

| 验证项 | 结果 |
|---|---|
| `python -m compileall elys_version1/backend/app/routers/datasets.py elys_version1/backend/tests/test_dataset_qa_mock_run.py` | 通过 |
| `python elys_version1/backend/tests/test_dataset_qa_mock_run.py` | 通过 |
| mock-run 后 dataset/fake DB 中有 `qa_report` | 通过 |
| 正常 warning 不会自动把 `qa_status` 改为 `checked` | 通过，保持 `converted` |
| blocking issue 不允许继续保持 `checked` | 通过，写为 `failed` |
| 返回报告 `mode='mock'` | 通过 |
| 返回报告 `summary.score is None` | 通过 |
| `signal_placeholder.status == 'not_computed'` | 通过 |

验证说明：

- 当前默认 Python 环境没有安装完整后端依赖 `fastapi/sqlalchemy`，因此测试文件使用轻量 stub 代替外部框架对象。
- 测试仍然加载真实的 `backend/app/routers/datasets.py`，调用真实的 `run_dataset_mock_qa_report()` 路由函数。
- 测试中通过 monkeypatch `MODULE.build_mock_qa_report` 构造 deterministic 报告，以便稳定覆盖状态规则；生产代码仍然调用 Step 2 的真实 `build_mock_qa_report(project, dataset)`。

### 9. 下一步建议

执行 Step 5：新增人工审核 API `POST /api/v1/projects/{project_id}/datasets/{dataset_id}/qa/review`，写入 `qa_report.human_review` 和 `qa_report.history`。该步骤需要定义 `accept/reject/hold` 对 `qa_status` 的影响边界，尤其要明确：有 blocking 的 mock 报告是否允许人工 accept，以及 accept 后是否才允许从 `converted/failed` 进入 `checked`。

---

## Step 5 执行记录：新增上传后模拟质控人工确认 Review API

执行时间：2026-05-18

### 1. 本步目标

新增人工确认 API：

```http
POST /api/v1/projects/{project_id}/datasets/{dataset_id}/qa/review
```

用于在已有 `qa_report` 的基础上写入人工确认结论，并根据结论更新 `datasets.qa_status`。

### 2. 已实现代码

修改文件：

```text
elys_version1/backend/app/routers/datasets.py
```

新增内容：

1. 引入 `DatasetQaReviewRequest`、`DatasetQaReviewResponse`、`DatasetQaHumanReview`。
2. 新增 `require_existing_qa_report(dataset)`，确保 review 前必须已有可解析的 `qa_report`。
3. 新增 `apply_dataset_qa_review(dataset, qa_report, review, current_user)`，集中处理人工确认和状态变更。
4. 新增路由函数 `review_dataset_qa_report()`。

更新测试文件：

```text
elys_version1/backend/tests/test_dataset_qa_mock_run.py
```

### 3. 入参与响应

入参复用 Step 1 已定义的 schema：

```python
class DatasetQaReviewRequest(BaseModel):
    conclusion: Literal["accept", "reject", "hold"]
    notes: Optional[str] = None
```

返回结构：

```python
class DatasetQaReviewResponse(BaseModel):
    dataset_id: str
    project_id: str
    qa_status: str
    qa_report: DatasetQaReport
```

### 4. 权限与归属校验

当前实现使用写权限边界：

1. 调用 `require_system_permission(current_user, "data:write", ...)`。
2. 调用 `require_project_write(...)`。
3. 查询 dataset 时同时约束：

```python
Dataset.project_id == project.id
Dataset.id == dataset_id
```

因此 review 只能作用于当前项目内的数据集。

### 5. review 前置条件

`review` 之前必须已有 `datasets.qa_report`：

| 场景 | 当前行为 |
|---|---|
| `qa_report` 为空 | 400，提示“请先生成模拟质控报告” |
| `qa_report` 无法被 `DatasetQaReport` 解析 | 400，提示“已有质控报告结构无效” |
| `qa_report` 存在且可解析 | 继续处理人工确认 |

### 6. qa_status 规则

当前实现规则如下：

| conclusion | 当前行为 |
|---|---|
| `accept` 且无 `summary.blocking_issues` | 写 `qa_status='checked'` |
| `accept` 但存在 `summary.blocking_issues` | 409，拒绝确认通过，不提交数据库 |
| `reject` | 写 `qa_status='rejected'` |
| `hold` 且当前不是 `failed/rejected` | 写回中性状态 `converted`，确保不会停留在 `checked` |
| `hold` 且当前是 `failed` | 保持 `failed`，不静默恢复 |
| `hold` 且当前是 `rejected` | 保持 `rejected`，不静默恢复 |

本步仍然不自动伪造真实信号指标，也不删除任何 `qa_report.stages`。

### 7. human_review 写入

每次 review 会写入：

```python
qa_report.human_review = DatasetQaHumanReview(
    conclusion=review.conclusion,
    notes=review.notes,
    reviewed_by=str(current_user.id),
    reviewed_at=datetime.utcnow(),
)
```

然后保存：

```python
dataset.qa_report = qa_report.model_dump(mode="json")
```

保留原有 `summary`、`stages`、`history` 等字段。

### 8. 后端验证

已执行以下验证：

| 验证项 | 结果 |
|---|---|
| `python -m compileall elys_version1/backend/app/routers/datasets.py elys_version1/backend/tests/test_dataset_qa_mock_run.py` | 通过 |
| `python elys_version1/backend/tests/test_dataset_qa_mock_run.py` | 通过 |
| `accept` 成功写入 `checked` 和 `human_review` | 通过 |
| `accept` 遇到 blocking issue 被拒绝 | 通过，返回 409，不提交数据库 |
| `reject` 写入 `rejected` | 通过 |
| `hold` 不写 `checked` | 通过，当前为 `checked` 时回到 `converted` |
| `hold` 不静默恢复 `failed/rejected` | 通过 |
| review 后不删除 `qa_report.stages` | 通过 |

验证说明：

- 当前默认 Python 环境仍未安装完整后端依赖，因此 smoke 继续使用轻量 stub。
- 测试调用真实 `review_dataset_qa_report()` 路由函数。
- 测试中的 `qa_report` 使用 Step 1 schema 构造，确保 `human_review` 写入后仍可被 `DatasetQaReport` 解析。

### 9. 下一步建议

执行下一步：先为 mock-run 和 review 补充轻量审计与 `qa_report.history`，完成后再进入前端 API 类型与请求函数。

---

## Step 6 执行记录：为上传后模拟质控补充审计记录和状态历史

执行时间：2026-05-18

### 1. 本步目标

为以下两个动作补充轻量审计：

```text
dataset.qa.mock_run
dataset.qa.review
```

审计目标：

1. 复用已有 `project_audit_events` 表，不新增数据库表。
2. 在 `qa_report.history` 中追加动作历史。
3. 不把完整 `qa_report` 大对象写入 audit metadata。
4. 不新增真实信号 QC 计算。

### 2. 现有审计基础

当前项目已有模型：

```text
elys_version1/backend/app/models/project.py
```

已有表模型：

```python
class ProjectAuditEvent(Base):
    __tablename__ = "project_audit_events"
```

已有 `projects.py` 中的 `add_project_audit_event()` helper，但该 helper 位于 router 文件内，不是独立 service。为了避免 router 之间互相导入，本步在 `datasets.py` 内新增轻量本地 helper，写同一张 `project_audit_events` 表，并保持字段含义一致。

### 3. 已实现代码

修改文件：

```text
elys_version1/backend/app/routers/datasets.py
```

新增 helper：

| 函数 | 作用 |
|---|---|
| `actor_id_text(user)` | 将 actor id 转成字符串写入 history |
| `project_snapshot(project)` | 优先调用 `project.to_dict()`，测试或轻量对象下退化为 `{id}` |
| `add_qa_report_history(...)` | 向 `qa_report.history` 追加简短历史 |
| `add_dataset_qa_audit_event(...)` | 写入 `ProjectAuditEvent` |
| `record_dataset_qa_action(...)` | 同时写 history 和 audit，并回写 `dataset.qa_report` |

更新测试文件：

```text
elys_version1/backend/tests/test_dataset_qa_mock_run.py
```

### 4. Audit metadata 内容

当前 audit metadata 保持轻量：

```python
{
    "dataset_id": "...",
    "current_upload_id": "...",
    "old_qa_status": "...",
    "new_qa_status": "...",
    "conclusion": "...",
    "has_blocking_issues": true / false,
}
```

说明：

- `mock-run` 的 `conclusion` 为 `null`。
- `review` 的 `conclusion` 为 `accept/reject/hold`。
- metadata 不包含完整 `qa_report`。
- metadata 不包含 `stages`、真实信号指标或大体积文件信息。

### 5. qa_report.history 内容

每次成功动作会追加：

```python
{
    "action": "dataset.qa.mock_run" 或 "dataset.qa.review",
    "actor_id": "...",
    "at": "...Z",
    "status": "最新 qa_status",
}
```

history 位于 `qa_report.history`，随 `dataset.qa_report = qa_report.model_dump(mode="json")` 一起保存。

### 6. mock-run 审计行为

`POST /api/v1/projects/{project_id}/datasets/{dataset_id}/qa/mock-run` 当前流程：

1. 保存旧状态 `old_qa_status`。
2. 生成并校验 mock 报告。
3. 如果有 `blocking_issues`，写 `qa_status='failed'`；否则保持原状态。
4. 调用 `record_dataset_qa_action(..., action="dataset.qa.mock_run")`。
5. 提交数据库事务。

mock-run 会写：

- `project_audit_events.action = "dataset.qa.mock_run"`
- `qa_report.history[-1].action = "dataset.qa.mock_run"`

### 7. review 审计行为

`POST /api/v1/projects/{project_id}/datasets/{dataset_id}/qa/review` 当前流程：

1. 保存旧状态 `old_qa_status`。
2. 校验已有 `qa_report`。
3. 应用 `accept/reject/hold` 状态规则。
4. 写入 `qa_report.human_review`。
5. 调用 `record_dataset_qa_action(..., action="dataset.qa.review", conclusion=review.conclusion)`。
6. 提交数据库事务。

review 会写：

- `project_audit_events.action = "dataset.qa.review"`
- `qa_report.history[-1].action = "dataset.qa.review"`
- `qa_report.human_review.conclusion/notes/reviewed_by/reviewed_at`

如果 `accept` 因 blocking issue 被拒绝，会返回 409，不写 audit，不追加 history，不提交数据库。

### 8. 后端验证

已执行以下验证：

| 验证项 | 结果 |
|---|---|
| `python -m compileall elys_version1/backend/app/routers/datasets.py elys_version1/backend/tests/test_dataset_qa_mock_run.py` | 通过 |
| `python elys_version1/backend/tests/test_dataset_qa_mock_run.py` | 通过 |
| mock-run 后生成 `ProjectAuditEvent` | 通过 |
| mock-run 后追加 `qa_report.history` | 通过 |
| mock-run audit metadata 包含 dataset/upload/status/blocking 信息 | 通过 |
| mock-run audit metadata 不包含完整 `qa_report` | 通过 |
| review accept 后生成 audit 和 history | 通过 |
| review reject/hold 后生成 audit 和 history | 通过 |
| review accept 遇到 blocking issue 被拒绝时不写 audit/history | 通过 |

验证说明：

- 当前默认 Python 环境没有完整安装 `fastapi/sqlalchemy`，测试仍使用轻量 stub。
- 测试调用真实 `run_dataset_mock_qa_report()` 和 `review_dataset_qa_report()` 路由函数。
- fake DB 的 `add()` 会记录被加入的 `ProjectAuditEvent`，用于验证 action 和 metadata。

### 9. 下一步建议

后端 mock QA 的最小闭环已包含：

1. 读取 QA 报告。
2. 生成 mock QA 报告。
3. 人工 review。
4. 状态更新。
5. 轻量审计与 history。

下一步建议进入前端接口层：在 `frontend/elys-web/src/types/index.ts` 和 `frontend/elys-web/src/api/datasets.ts` 补齐 QA 类型与请求函数，然后再做项目详情页或数据集详情区域的 QA 面板入口。

---

## Step 7 执行记录：前端补齐上传后模拟质控类型和 API 封装

执行时间：2026-05-18

### 1. 本步目标

在前端补齐上传后模拟质控的类型定义和 API 请求封装，先不改 UI。

目标文件：

```text
elys_version1/frontend/elys-web/src/types/index.ts
elys_version1/frontend/elys-web/src/api/datasets.ts
```

### 2. 已实现类型

修改文件：

```text
elys_version1/frontend/elys-web/src/types/index.ts
```

新增类型：

| 类型 | 说明 |
|---|---|
| `DatasetQaMode` | `'mock' | 'real'`，当前 UI 先按 mock 使用 |
| `DatasetQaReviewConclusion` | `'accept' | 'reject' | 'hold'` |
| `DatasetQaStageStatus` | `pass/warning/fail/not_computed/skipped/pending` |
| `DatasetQaSeverity` | `info/warning/error` |
| `DatasetQaStageItem` | stage 内的单项检查结果 |
| `DatasetQaStage` | QA 阶段 |
| `DatasetQaSummary` | QA 总结，包含 `blocking_issues/warnings/score` |
| `DatasetQaHumanReview` | 人工确认记录 |
| `DatasetQaHistoryItem` | mock-run/review 历史 |
| `DatasetQaReport` | 完整 QA 报告 |
| `DatasetQaResponse` | GET QA 报告响应 |
| `DatasetQaMockRunResponse` | POST mock-run 响应 |
| `DatasetQaReviewRequest` | review 入参 |
| `DatasetQaReviewResponse` | review 响应 |

### 3. Dataset 兼容处理

原有 `Dataset.qa_report` 是：

```ts
qa_report: Record<string, unknown> | null
```

本步调整为：

```ts
qa_report: DatasetQaReport | Record<string, unknown> | null
```

原因：

- 新的 QA API 返回结构化 `DatasetQaReport`。
- 现有 list/import 可能仍返回旧导入流程中的 legacy `qa_report`。
- 这样可以保持现有 `list/upload` API 兼容，不强迫旧页面立即按新 QA schema 解析。

### 4. 已实现 API 封装

修改文件：

```text
elys_version1/frontend/elys-web/src/api/datasets.ts
```

新增方法：

```ts
datasetApi.getQa(projectId, datasetId)
datasetApi.runMockQa(projectId, datasetId)
datasetApi.reviewQa(projectId, datasetId, payload)
```

对应后端路径：

| 方法 | 路径 |
|---|---|
| `getQa` | `GET /projects/{projectId}/datasets/{datasetId}/qa` |
| `runMockQa` | `POST /projects/{projectId}/datasets/{datasetId}/qa/mock-run` |
| `reviewQa` | `POST /projects/{projectId}/datasets/{datasetId}/qa/review` |

说明：

- 前端 `dataApi` 的 baseURL 默认为 `/api/v1`，因此封装路径不重复写 `/api/v1`。
- 原有 `datasetApi.list()` 和 `datasetApi.upload()` 未改变。

### 5. 前端验证

已执行：

```bash
npm run build
```

结果：通过。

构建输出摘要：

```text
vite v5.4.21 building for production...
149 modules transformed.
✓ built in 2.23s
```

构建警告：

- `litegraph.js` 使用 `eval`，这是项目已有依赖警告。
- `PipelinePage` chunk 大于 500 kB，这是项目已有构建体积警告。
- Vite CJS Node API deprecated warning，这是现有 Vite 使用方式警告。

额外尝试：

```bash
npx vue-tsc --noEmit
```

结果：未执行实际类型检查。当前 `frontend/elys-web` 根目录没有 `tsconfig.json`，`package.json` 也没有 `typecheck` 脚本，因此该命令只打印 TypeScript 帮助并返回 1。此限制已记录，非本次代码改动导致。

### 6. 本步没有做的事

- 未新增 QA 面板 UI。
- 未在 `ProjectDetailPage.vue` 或 `Dashboard.vue` 中接入按钮。
- 未更改上传流程。
- 未更改后端 API。
- 未新增真实信号 QC 计算。

### 7. 下一步建议

执行 Step 8：在项目详情页或数据集详情区域新增 QA 面板入口。建议先做最小 UI 闭环：

1. 在数据集列表中增加“质控”入口。
2. 打开后调用 `datasetApi.getQa()`。
3. 如果无报告，显示空状态和“运行模拟质控”按钮。
4. 点击后调用 `datasetApi.runMockQa()` 并刷新报告。
5. 展示 `summary`、`stages`、`history`。
6. 提供 accept/reject/hold 三个 review 操作，调用 `datasetApi.reviewQa()`。

---

## Step 8 执行记录：项目数据列表增加上传后模拟质控入口

执行时间：2026-05-18

### 1. 本步目标

在前端项目详情页的数据集列表中增加上传后模拟质控入口，优先修改：

```text
elys_version1/frontend/elys-web/src/views/ProjectDetailPage.vue
```

目标：

1. 每行展示 `qa_status` 徽章。
2. 每行增加“质控”按钮。
3. 点击后打开 QA 详情弹窗，并调用 `datasetApi.getQa(projectId, datasetId)`。
4. 没有报告时显示“尚未运行模拟质控”，并允许运行模拟质控。
5. 有 mock 报告时明确显示“模拟质控，真实信号指标未计算”。
6. 不展示真实 RMS/PSD/坏段结论。

### 2. 已实现 UI

修改文件：

```text
elys_version1/frontend/elys-web/src/views/ProjectDetailPage.vue
```

数据集表格新增两列：

| 列 | 行为 |
|---|---|
| `QA` | 展示 `qa_status` 徽章 |
| `操作` | 展示“质控”按钮 |

状态徽章覆盖：

```text
converted
checked
failed
rejected
pending
unknown
```

未知或空状态统一显示为 `unknown`。

### 3. QA 弹窗行为

点击“质控”后：

1. 设置当前 dataset。
2. 清空旧 QA 响应和错误。
3. 调用：

```ts
datasetApi.getQa(projectId, dataset.id)
```

4. 根据响应展示：

| 场景 | UI 行为 |
|---|---|
| 正在加载 | 显示读取中状态 |
| 无 `qa_report` | 显示“尚未运行模拟质控”和“运行模拟质控”按钮 |
| 有 `qa_report.mode='mock'` | 显示“模拟质控，真实信号指标未计算” |
| 有 blocking issues | 展示阻塞问题摘要 |
| 有 warnings | 展示警告摘要 |
| 有 stages | 展示阶段列表 |
| 有 history | 展示历史列表 |

### 4. 运行模拟质控

弹窗内新增：

```ts
runSelectedDatasetMockQa()
```

调用：

```ts
datasetApi.runMockQa(projectId, dataset.id)
```

成功后：

1. 更新弹窗内 `qaResponse`。
2. 同步当前数据集行的 `qa_status`。
3. 同步当前数据集行的 `qa_report`。

当前 Step 8 没有接入 review 按钮，review UI 留到后续步骤。

### 5. 不展示真实信号结论

当前 UI 对 `signal_placeholder` 只显示阶段状态和“真实信号指标未计算”的提示，不展示任何真实 RMS/PSD/坏段结论。

如果 stage 是 `signal_placeholder`：

```vue
<ul v-if="stage.key !== 'signal_placeholder' && stage.items.length">
```

因此不会渲染该 stage 内部的 RMS/PSD/坏段占位 item 为真实结果。

### 6. 响应式处理

本步新增 scoped CSS：

1. QA 弹窗宽度 `min(760px, 100%)`。
2. 小屏幕下弹窗撑满可用宽度。
3. QA summary 从 4 列降为 2 列，再降为 1 列。
4. stage header 和 footer 在小屏幕下纵向排列。
5. 数据集表格继续使用现有 `.table-wrap` 横向滚动。

整体沿用现有 `card/table/badge/button/modal` 设计风格。

### 7. 前端验证

已执行：

```bash
npm run build
```

结果：通过。

构建输出摘要：

```text
vite v5.4.21 building for production...
150 modules transformed.
✓ built in 2.24s
```

构建警告：

- `litegraph.js` 使用 `eval`，这是项目已有依赖警告。
- `PipelinePage` chunk 大于 500 kB，这是项目已有构建体积警告。
- Vite CJS Node API deprecated warning，这是现有 Vite 使用方式警告。

### 8. 本步没有做的事

- 未实现 accept/reject/hold review UI。
- 未在 Dashboard.vue 中重复接入 QA 入口。
- 未展示真实 RMS/PSD/坏段结论。
- 未新增真实信号 QC 计算。
- 未更改后端 API。

### 9. 下一步建议

执行 Step 9：在 QA 弹窗中增加人工确认操作。建议接入 `datasetApi.reviewQa()`，提供 accept/reject/hold 三个按钮和 notes 输入框，并在成功后刷新 `qa_status`、`human_review`、`history`。

---

## Step 9 执行记录：实现上传后模拟质控详情面板和阶段清单

执行时间：2026-05-18

### 1. 本步目标

在 Step 8 已有 QA 弹窗基础上，补齐 `qa_report` 详情展示：

1. 展示完整 summary。
2. 按固定顺序展示 stages。
3. 每个 stage 展示 `status/severity/message/items`。
4. 展示 `human_review`。
5. `mock` 报告始终显示“模拟质控”标识。
6. `signal_placeholder` 必须明确显示“真实 RMS/PSD/坏段指标尚未实现”。

### 2. 已实现代码

修改文件：

```text
elys_version1/frontend/elys-web/src/views/ProjectDetailPage.vue
```

本步继续在 `ProjectDetailPage.vue` 内部实现，没有额外拆组件。

原因：

- 当前 QA 入口只在项目详情页使用。
- 先保持改动集中，便于后续 Step 10 接入 review 操作。
- 如果 Dashboard 或其他页面也需要复用，再抽 `DatasetQaPanel.vue` 会更自然。

### 3. Summary 展示

当前 summary 展示字段：

| 字段 | UI 展示 |
|---|---|
| `mock_qc_status` | 展示原始状态，如 `passed/passed_with_warnings/blocked` |
| `level` | 展示 `good/warning/bad/unknown` |
| `generated_at` | 格式化为中文本地时间 |
| `blocking_issues` | 展示数量，并在下方错误区列出明细 |
| `warnings` | 展示数量，并在下方警告区列出明细 |
| `score` | mock 模式下显示“未计算” |

blocking issue 使用 `qa-note--danger`，warning 使用 `qa-note--warning`，视觉上明显区分错误和警告。

### 4. Stages 展示

新增固定顺序：

```ts
const QA_STAGE_ORDER = [
  'preflight',
  'identity',
  'file_integrity',
  'metadata_consistency',
  'fif_header',
  'channels_sidecar',
  'events_sidecar',
  'signal_placeholder',
]
```

当前 stage 展示内容：

| 字段 | UI 展示 |
|---|---|
| `title` | 阶段标题 |
| `key` | 阶段 key，使用 mono 文本 |
| `status` | 状态徽章 |
| `severity` | 严重程度徽章 |
| `message` | 阶段说明 |
| `items` | 全量 item 列表 |

每个 item 展示：

| 字段 | UI 展示 |
|---|---|
| `label` | 检查项标题 |
| `key` | 无 message 时作为辅助信息 |
| `message` | 检查项说明 |
| `value` | 如果存在，格式化显示 |
| `status` | item 状态徽章 |
| `severity` | item 严重程度徽章 |

### 5. signal_placeholder 行为

新增常量：

```ts
const SIGNAL_PLACEHOLDER_MESSAGE = '真实 RMS/PSD/坏段指标尚未实现。'
```

当 stage key 为 `signal_placeholder` 时：

1. 始终显示该提示。
2. stage 状态显示为 `not_computed`。
3. item 也只按 `not_computed/info` 占位显示。
4. 不展示真实 RMS/PSD/坏段结论。

### 6. human_review 展示

新增“人工确认”区域：

| 场景 | UI |
|---|---|
| `human_review.conclusion` 存在 | 展示 conclusion、notes、reviewed_by、reviewed_at |
| 尚未 review | 显示“尚未人工确认” |

本步只展示 human_review，不提供 accept/reject/hold 操作按钮。

### 7. 样式与响应式

新增/增强样式：

| 样式 | 用途 |
|---|---|
| `qa-severity` | severity 徽章 |
| `qa-stage--error` | error/fail 阶段高亮 |
| `qa-stage--warning` | warning 阶段高亮 |
| `qa-stage--muted` | not_computed 阶段弱化 |
| `qa-issue-list` | blocking/warning 明细列表 |
| `qa-review` | 人工确认信息网格 |

响应式：

- summary 和 review 在宽屏多列展示。
- 小屏下自动降到 1 列。
- stage header 在小屏下纵向排列。

### 8. 前端验证

已执行：

```bash
npm run build
```

结果：通过。

构建输出摘要：

```text
vite v5.4.21 building for production...
150 modules transformed.
✓ built in 2.16s
```

构建警告仍为项目既有警告：

- `litegraph.js` 使用 `eval`。
- `PipelinePage` chunk 大于 500 kB。
- Vite CJS Node API deprecated warning。

### 9. 手动验证说明

本地前端地址：

```text
http://127.0.0.1:5173
```

浏览器验证结果：

- 本地前端可以打开。
- 未登录状态访问 `/projects/{projectId}` 会被路由守卫重定向到 `/login`，这是现有鉴权行为。
- 因当前浏览器没有登录态，未能在浏览器内直接点开真实项目数据列表。

登录后建议按三种状态验证：

| 状态 | 操作 | 期望 |
|---|---|---|
| 无报告 | 打开某 dataset 的“质控” | 显示“尚未运行模拟质控”和“运行模拟质控”按钮 |
| 有 warning | 运行模拟质控，或选择仅有 warning 的数据 | summary 显示 warning 数量，warning 明细用警告色展示，stage 使用 warning 徽章 |
| 有 blocking issue | 选择缺少 FIF 或 metadata 不合理的数据 | summary 显示 blocking issue 数量，blocking 明细用错误色展示，stage 使用 error/fail 徽章 |

必须确认：

1. `mode='mock'` 时顶部始终有“模拟质控”标识。
2. `signal_placeholder` 显示“真实 RMS/PSD/坏段指标尚未实现”。
3. 不出现真实 RMS/PSD/坏段质量结论。
4. human_review 未提交时显示“尚未人工确认”；提交后能展示 conclusion/notes/reviewed_by/reviewed_at。

### 10. 本步没有做的事

- 未新增真实信号 QC 计算。
- 未新增组件测试框架。
- 未接入 review 提交按钮。
- 未抽出 `DatasetQaPanel.vue`。

### 11. 下一步建议

执行 Step 10：在 QA 详情面板中接入人工确认操作。新增 notes 输入框和 accept/reject/hold 三个按钮，调用 `datasetApi.reviewQa()`，并在成功后刷新 `qa_status`、`qa_report.human_review` 和 `qa_report.history`。

---

## Step 10 执行记录：实现上传后模拟质控运行按钮

执行时间：2026-05-18

### 1. 本步目标

在 QA 详情面板中完善“运行模拟质控”按钮行为：

1. 点击调用 `datasetApi.runMockQa(projectId, datasetId)`。
2. 请求期间按钮 loading/disabled，避免重复提交。
3. 成功后刷新当前 QA 报告。
4. 同步刷新项目数据列表中的 `qa_status`。
5. blocking issue 作为阻断状态展示，不让页面崩溃。
6. `mode='mock'` 时继续显示模拟标识。
7. 不在前端自动把数据改成 `checked`。

### 2. 已实现代码

修改文件：

```text
elys_version1/frontend/elys-web/src/views/ProjectDetailPage.vue
```

本步在 Step 8/9 的基础上增强已有按钮：

| 位置 | 行为 |
|---|---|
| 无报告空状态 | “运行模拟质控”按钮 |
| 已有报告底部 | “重新运行模拟质控”按钮 |

按钮 disabled 条件：

```vue
:disabled="qaActionLoading || qaLoading"
```

函数入口也加了防重复 guard：

```ts
if (!selectedQaDataset.value || qaActionLoading.value) return
```

### 3. 调用流程

当前 `runSelectedDatasetMockQa()` 流程：

1. 保存当前 `datasetId`。
2. 设置 `qaActionLoading=true`。
3. 清空旧错误。
4. 调用：

```ts
datasetApi.runMockQa(projectId.value, datasetId)
```

5. 先用 POST 返回值更新面板：

```ts
qaResponse.value = {
  dataset_id: res.data.dataset_id,
  project_id: res.data.project_id,
  qa_status: res.data.qa_status,
  qa_report: res.data.qa_report,
  has_report: true,
  current_upload_id: selectedQaDataset.value.current_upload_id || null,
  imported_at: selectedQaDataset.value.imported_at,
}
```

6. 同步数据集列表状态：

```ts
syncDatasetQa(datasetId, res.data.qa_status, res.data.qa_report)
```

7. 再静默读取一次最新持久化报告：

```ts
await loadSelectedDatasetQa({ silent: true })
```

### 4. 状态同步规则

前端不自行推导 `checked/failed/converted`。

当前页面只使用后端返回的：

```ts
res.data.qa_status
```

因此：

| 后端返回 | 前端行为 |
|---|---|
| `converted` | 列表和弹窗显示 converted |
| `failed` | 列表和弹窗显示 failed，并展示 blocking issue |
| `checked` | 只有后端返回 checked 时才显示 checked |
| `rejected` | 显示 rejected |

前端不会因为点击“运行模拟质控”而自动写 `checked`。

### 5. Blocking issue 展示

当后端报告包含：

```ts
qa_report.summary.blocking_issues.length > 0
```

前端显示：

- summary 中阻塞问题数量。
- `qa-note--danger` 错误区域。
- 阶段中的 `fail/error` 徽章和错误底色。

页面不会因为 blocking issue 崩溃，也不会把它当作 JS 异常处理。

### 6. Mock 标识

只要：

```ts
qaReport.mode === 'mock'
```

面板继续显示：

```text
模拟质控
模拟质控，真实信号指标未计算
```

### 7. 前端验证

已执行：

```bash
npm run build
```

结果：通过。

构建输出摘要：

```text
vite v5.4.21 building for production...
150 modules transformed.
✓ built in 2.20s
```

构建警告仍为项目既有警告：

- `litegraph.js` 使用 `eval`。
- `PipelinePage` chunk 大于 500 kB。
- Vite CJS Node API deprecated warning。

### 8. 最小手动验证说明

本地前端地址：

```text
http://127.0.0.1:5173
```

当前浏览器未登录时访问项目详情页会被重定向到 `/login`，这是现有鉴权行为。登录后建议验证：

| 场景 | 操作 | 期望 |
|---|---|---|
| 无报告 | 打开 dataset “质控”弹窗 | 显示“尚未运行模拟质控” |
| 点击运行 | 点击“运行模拟质控” | 按钮显示“运行中...”，且不可重复点击 |
| 运行成功 | 等待请求完成 | 报告出现，顶部显示“模拟质控”，列表 `qa_status` 同步更新 |
| 有 blocking issue | 使用缺失 FIF 或元数据不合理 dataset 运行 | 页面显示阻塞问题和 failed/error 样式，不崩溃 |
| 后端未返回 checked | 运行 mock-run | 前端不自动显示 checked |

### 9. 本步没有做的事

- 未新增真实 RMS/PSD/坏段计算。
- 未实现 accept/reject/hold review 操作。
- 未绕过登录态做浏览器端强行接口模拟。

### 10. 下一步建议

执行 Step 11：在 QA 详情面板中接入人工确认操作。新增 notes 输入框和 accept/reject/hold 三个按钮，调用 `datasetApi.reviewQa()`，成功后刷新 `qa_status`、`qa_report.human_review` 和 `qa_report.history`。

---

## Step 11 执行记录：实现上传后模拟质控人工确认按钮

### 1. 本步目标

在项目详情页的 QA 详情面板中补齐人工确认操作，让用户可以在模拟质控报告生成后提交：

- `accept`：通过。
- `hold`：暂缓。
- `reject`：拒绝。

前端只负责提交人工结论、展示后端返回的状态和刷新界面，不绕过后端校验，也不伪造真实 RMS/PSD/坏段指标。

### 2. 修改文件

本步主要修改：

```text
elys_version1/frontend/elys-web/src/views/ProjectDetailPage.vue
```

继续复用 Step 7 已补齐的类型和 API：

```text
elys_version1/frontend/elys-web/src/types/index.ts
elys_version1/frontend/elys-web/src/api/datasets.ts
```

其中 `datasets.ts` 已提供：

```ts
datasetApi.reviewQa(projectId, datasetId, payload)
```

payload 类型为：

```ts
{
  conclusion: 'accept' | 'reject' | 'hold'
  notes?: string | null
}
```

### 3. 前端交互实现

在 QA 详情面板的“人工确认”区域新增：

- notes 文本框，用于填写本次人工确认说明。
- “通过”按钮，提交 `conclusion='accept'`。
- “暂缓”按钮，提交 `conclusion='hold'`。
- “拒绝”按钮，提交 `conclusion='reject'`。

提交期间使用 `qaReviewLoading` 区分当前正在提交的动作：

```ts
const qaReviewLoading = ref<DatasetQaReviewConclusion | ''>('')
const qaReviewNotes = ref('')
```

并用统一的 busy 状态避免重复操作：

```ts
const qaBusy = computed(() => qaLoading.value || qaActionLoading.value || !!qaReviewLoading.value)
```

### 4. 通过按钮的阻断规则

前端增加 `acceptDisabledReason`：

```ts
const acceptDisabledReason = computed(() => {
  if (!qaReport.value) return '请先运行模拟质控后再确认通过。'
  if (qaReport.value.summary.blocking_issues.length) return '存在阻塞问题，不能确认通过。'
  return ''
})
```

当 `summary.blocking_issues` 非空时：

- “通过”按钮禁用。
- 面板显示不可通过原因。
- 后端仍然保留最终校验，前端只是提前给用户明确反馈。

### 5. Review 提交流程

新增 `submitQaReview(conclusion)`：

1. 检查是否存在当前 dataset。
2. 检查是否已有请求进行中。
3. 如果是 `accept` 且存在阻断原因，直接返回。
4. 读取 notes，并将空字符串转为 `null`。
5. 调用：

```ts
datasetApi.reviewQa(projectId.value, datasetId, {
  conclusion,
  notes: notes || null,
})
```

6. 用后端返回值更新当前 QA 面板。
7. 调用 `syncDatasetQa()` 同步项目数据列表中的 `qa_status` 和 `qa_report`。
8. 再静默调用 `loadSelectedDatasetQa({ silent: true })` 拉取持久化后的最新报告。

### 6. 状态同步规则

前端不自行推断最终状态，只使用后端返回的 `qa_status`：

| 操作 | payload | 期望后端状态 | 前端行为 |
|---|---|---|---|
| 通过 | `conclusion='accept'` | `checked` | QA 面板和数据列表显示 `checked` |
| 暂缓 | `conclusion='hold'` | 不应写 `checked` | QA 面板和数据列表显示后端返回状态，通常保持 `converted` |
| 拒绝 | `conclusion='reject'` | `rejected` | QA 面板和数据列表显示 `rejected` |
| 有 blocking issue 时通过 | `conclusion='accept'` | 后端拒绝 | 前端按钮已禁用，后端仍做最终保护 |

### 7. human_review 展示

面板继续展示 `qa_report.human_review`：

- `conclusion`
- `notes`
- `reviewed_by`
- `reviewed_at`

如果已经提交过人工确认，面板会显示最近一次确认结论、备注、审核人和审核时间。

### 8. 前端验证

已执行：

```bash
npm run build
```

结果：通过。

构建输出摘要：

```text
vite v5.4.21 building for production...
150 modules transformed.
✓ built in 2.25s
```

构建警告仍为项目既有警告：

- `litegraph.js` 使用 `eval`。
- `PipelinePage` chunk 大于 500 kB。
- Vite CJS Node API deprecated warning。

### 9. accept/hold/reject 手动验证说明

本地前端地址：

```text
http://127.0.0.1:5173
```

当前未登录访问项目详情页会被重定向到 `/login`。登录后建议按下表验证：

| 场景 | 操作 | 期望 |
|---|---|---|
| accept 成功 | 打开无 blocking issue 的 QA 报告，填写 notes，点击“通过” | 请求 payload 为 `conclusion='accept'`，成功后列表和面板 `qa_status` 显示 `checked`，human_review 显示通过结论和 notes |
| accept 被禁用 | 打开含 blocking issue 的 QA 报告 | “通过”按钮禁用，并显示“存在阻塞问题，不能确认通过。” |
| hold 暂缓 | 打开 QA 报告，填写 notes，点击“暂缓” | 请求 payload 为 `conclusion='hold'`，成功后不显示 `checked`，human_review 显示暂缓结论和 notes |
| reject 拒绝 | 打开 QA 报告，填写 notes，点击“拒绝” | 请求 payload 为 `conclusion='reject'`，成功后列表和面板 `qa_status` 显示 `rejected`，human_review 显示拒绝结论和 notes |
| 重复提交保护 | 任意 review 请求未完成时连续点击按钮 | 按钮 disabled/loading，不重复提交 |

### 10. 本步没有做的事

- 未新增真实 RMS/PSD/坏段计算。
- 未绕过后端的 accept 校验。
- 未新增单独的 QA 组件文件，当前仍集中在 `ProjectDetailPage.vue` 中实现，便于第一轮快速闭环。

### 11. 下一步建议

执行 Step 12：补充端到端联调和状态回归检查。重点验证 `mock-run -> hold -> accept/reject` 的状态流转、`qa_report.history` 是否追加、项目数据列表是否稳定同步，以及后端 blocking issue 对 accept 的最终保护是否可靠。

---

## Step 12 执行记录：在 LoadData 面板显示上传后模拟质控摘要

### 1. 本步目标

在 `PipelinePage.vue` 的 LoadData 数据选择表格中，让每一行 dataset 都能看到上传后模拟质控的摘要信息：

- `qa_status` 徽章。
- `qa_report.mode='mock'` 时显示“模拟质控”标识。
- 显示 blocking issue 数量和 warning 数量。
- 没有报告时显示“未检查”。
- 不展示真实 RMS/PSD/坏段结果。

本步只增强展示，不改变 LoadData 的默认选择逻辑。

### 2. 修改文件

```text
elys_version1/frontend/elys-web/src/views/PipelinePage.vue
```

### 3. 表格展示调整

将 LoadData 数据选择表格最后一列从原来的纯文本“状态”调整为“质控”列。

每个 dataset 行现在展示：

```text
qa_status 徽章
模拟质控标识
阻断 N · 警告 N
```

没有 `qa_report` 或报告结构不可识别时显示：

```text
未检查
```

示例展示逻辑：

| dataset 状态 | 展示 |
|---|---|
| `converted` 且无报告 | `converted` 徽章 + `未检查` |
| `converted` 且 mock 报告 | `converted` 徽章 + `模拟质控` + `阻断 N · 警告 N` |
| `checked` 且 mock 报告 | 更醒目的 `checked` 徽章 + `模拟质控` + `阻断 0 · 警告 N` |
| `rejected` | 默认不会进入 LoadData 可选表格 |

### 4. QA 报告读取规则

新增轻量前端辅助函数：

- `datasetQaReport(dataset)`
- `isDatasetMockQa(dataset)`
- `datasetQaBlockingIssueCount(dataset)`
- `datasetQaWarningCount(dataset)`
- `datasetQaSummaryText(dataset)`
- `datasetQaStatusLabel(status)`
- `datasetQaStatusClass(status)`

`datasetQaReport()` 只做结构识别：

- `mode` 必须是 `mock` 或 `real`。
- `summary` 必须存在。
- `summary.blocking_issues` 和 `summary.warnings` 必须是数组。

当前 UI 只展示 mock 摘要，不展示真实信号指标。

### 5. 选择逻辑保持不变

LoadData 原有默认状态筛选仍为：

```ts
const DEFAULT_LOAD_DATA_QA_STATUS = ['converted', 'checked']
```

因此默认仍允许：

- `converted`
- `checked`

`checked` 在视觉上更醒目，但不会改变默认命中、固定选择或运行解析逻辑。

### 6. 强制排除规则保持不变

现有 `isDatasetEligibleForLoad()` 继续排除：

```ts
['failed', 'deleted', 'rejected']
```

因此：

- `failed` 不进入 LoadData 可选列表。
- `rejected` 不进入 LoadData 可选列表。
- `deleted` 不进入 LoadData 可选列表。

后端 `resolveLoadData` 仍是最终解析保护；前端展示不会绕过后端校验。

### 7. checked-only 筛选说明

本步没有额外新增“只看 checked”快捷复选框。

当前 LoadData 已有“质量状态”多选框，用户可以只选 `checked`，达到“只看 checked”的效果。默认仍保持 `converted + checked`。

### 8. 前端验证

已执行：

```bash
npm run build
```

结果：通过。

构建输出摘要：

```text
vite v5.4.21 building for production...
150 modules transformed.
✓ built in 2.24s
```

构建警告仍为项目既有警告：

- `litegraph.js` 使用 `eval`。
- `PipelinePage` chunk 大于 500 kB。
- Vite CJS Node API deprecated warning。

### 9. converted、checked、rejected 手动验证说明

本地前端地址：

```text
http://127.0.0.1:5173
```

登录后进入 Pipeline 页面，选择项目并选中 `LoadData` 节点，验证：

| 数据类型 | 准备方式 | 期望展示 |
|---|---|---|
| converted | 使用已上传并转换、但尚未人工通过的数据 | LoadData 表格中可见该行，显示 `converted` 徽章；若无报告显示 `未检查`；若有 mock 报告显示“模拟质控”和阻断/警告数量 |
| checked | 对无 blocking issue 的 mock QA 报告点击“通过” | LoadData 表格中可见该行，显示更醒目的 `checked` 徽章，不影响默认选择逻辑 |
| rejected | 对某个 QA 报告点击“拒绝” | 该 dataset 不应出现在 LoadData 可选表格中；即使前端状态筛选包含其他值，也会被 `isDatasetEligibleForLoad()` 排除 |

补充验证：

| 场景 | 期望 |
|---|---|
| mock 报告存在 | 行内显示“模拟质控” |
| 报告有 blocking issue | 行内显示 `阻断 N`，文字使用危险色 |
| 报告无 blocking issue 但有 warnings | 行内显示 `阻断 0 · 警告 N` |
| 质量状态多选只保留 checked | 表格只显示 checked 且仍符合可加载条件的数据 |

### 10. 本步没有做的事

- 未新增真实 RMS/PSD/坏段结果展示。
- 未改变 LoadData 默认筛选逻辑。
- 未改变后端解析规则。
- 未新增单独 QA 摘要组件，当前展示集中在 `PipelinePage.vue` 内完成。

### 11. 下一步建议

执行 Step 13：补充 LoadData 与 QA 状态的端到端联调。重点验证项目详情页 review 后回到 Pipeline 页面，`converted/checked/rejected` 在 LoadData 表格、筛选条件和后端 `resolveLoadData` 中保持一致。

---

## Step 13 执行记录：补齐上传后模拟质控后端测试

### 1. 本步目标

为上传后模拟质控补齐后端测试，覆盖：

- `build_mock_qa_report()` 服务函数。
- GET `/qa` 读取行为。
- POST `/qa/mock-run` 生成并保存行为。
- POST `/qa/review` 人工确认状态流转。
- blocking issue 下 accept 失败。
- dataset 不属于 project 时不可访问。

### 2. 修改文件

```text
elys_version1/backend/tests/test_dataset_qa_mock_run.py
```

### 3. 测试环境说明

当前后端测试没有配置真实 PostgreSQL，也没有完整 FastAPI app 测试客户端夹具。

本步沿用项目现有测试方式：

- 使用最小 `fastapi/sqlalchemy/app.models` stub。
- 直接加载 `app/routers/datasets.py`。
- 直接调用路由函数验证 GET/POST API 行为。
- 使用 `FakeDB/FakeQuery` 模拟 `Project` 和 `Dataset` 查询。
- 使用真实 `app/services/dataset_qa.py` 服务函数，单独加载为 `dataset_qa_service_under_test`。

限制：

- 没有覆盖真实数据库事务、SQLAlchemy 查询执行和 PostgreSQL JSONB 行为。
- 没有覆盖 ASGI 层请求序列化、鉴权中间件和真实依赖注入。
- 但覆盖了当前 QA 业务函数、路由函数、权限码调用、状态写入、audit/history 追加和跨项目访问保护。

### 4. 服务函数测试

新增 `build_mock_qa_report()` 测试：

| 测试 | 覆盖点 |
|---|---|
| `test_build_mock_qa_report_normal_dataset` | 正常 dataset，mock 报告 `mode='mock'`，`score=null`，无 blocking issue，`signal_placeholder=not_computed` |
| `test_build_mock_qa_report_missing_fif_path` | 缺少 `fif_path`，写入 `fif_exists` blocking issue，`file_integrity/fif_header` 失败 |
| `test_build_mock_qa_report_missing_fif_file` | `fif_path` 有值但文件不存在，写入 `fif_exists` blocking issue |
| `test_build_mock_qa_report_missing_metadata` | 缺少 `n_channels/sfreq/duration_seconds/n_events/checksum`，关键元数据写入 blocking/warning |

正常 dataset 测试中使用 fake `mne` reader，确保轻量 FIF header 读取逻辑可稳定测试，不依赖本机是否安装 MNE 或真实 FIF 文件。

### 5. GET /qa 测试

新增：

| 测试 | 覆盖点 |
|---|---|
| `test_get_qa_without_report_returns_empty_state` | 无 `qa_report` 时返回 `has_report=false`、`qa_report=None`，不报错 |
| `test_get_qa_with_report_returns_complete_structure` | 有报告时返回 `mode='mock'`、summary、stages 等完整结构 |

同时验证 GET 使用 `data:read` 权限。

### 6. POST /qa/mock-run 测试

保留并加强现有 mock-run 测试：

| 测试 | 覆盖点 |
|---|---|
| `test_mock_run_persists_report_and_returns_latest_status` | 写入 `qa_report.mode='mock'`，`score=None`，追加 audit/history |
| `test_warning_report_does_not_auto_check` | 有 warnings 时不自动写 `checked` |
| `test_blocking_report_cannot_stay_checked` | 有 blocking issue 时写 `failed`，不允许保持 `checked` |

### 7. POST /qa/review 测试

保留并加强现有 review 测试：

| 测试 | 覆盖点 |
|---|---|
| `test_review_accept_success_writes_checked_and_human_review` | accept 成功写 `checked`，写入 `human_review`、audit/history |
| `test_review_accept_rejected_by_blocking_issue` | 有 blocking issue 时 accept 返回 409，不写状态、不写 audit |
| `test_review_reject_writes_rejected` | reject 写 `rejected` |
| `test_review_hold_does_not_write_checked` | hold 不写 checked，当前可恢复状态回到 `converted` |
| `test_review_hold_preserves_failed_or_rejected_status` | hold 不静默恢复 `failed/rejected` |

### 8. 跨项目不可访问测试

新增：

```text
test_dataset_from_other_project_is_not_accessible_for_qa_routes
```

覆盖：

- GET `/qa`
- POST `/qa/mock-run`
- POST `/qa/review`

当 `dataset.project_id != requested_project.id` 时，三个入口都返回 404，且不会 commit。

为支持这一点，`FakeQuery.filter().first()` 已从“忽略 filter”改为会检查 `id/project_id` 过滤条件。

### 9. 已执行测试命令

脚本模式：

```bash
python tests\test_dataset_qa_mock_run.py
```

结果：

```text
dataset qa service/api tests passed
```

pytest 模式：

```bash
python -m pytest tests\test_dataset_qa_mock_run.py -q
```

结果：

```text
...............                                                          [100%]
15 passed, 17 warnings in 0.24s
```

warnings 为 Python 对 `datetime.utcnow()` 的弃用提示，来自：

- `app/services/dataset_qa.py`
- `app/routers/datasets.py`

本步没有改动该时间实现，后续可单独替换为 timezone-aware UTC 时间。

### 10. 本步没有做的事

- 未接入真实 PostgreSQL。
- 未新增 TestClient/ASGI 级别测试。
- 未覆盖真实上传文件到数据库再 QA 的完整链路。
- 未实现真实 RMS/PSD/坏段算法。

### 11. 下一步建议

执行 Step 14：补齐前后端联调回归清单。建议用一组真实项目数据跑通 `upload -> mock-run -> review -> Pipeline LoadData 展示 -> resolveLoadData`，并把需要真实 PostgreSQL/TestClient 的测试债务单独列入后续任务。

---

## Step 14 执行记录：补齐上传后模拟质控前端测试和交互验证

### 1. 本步目标

补齐上传后模拟质控前端侧的构建检查、类型检查和关键交互验证，重点覆盖：

- ProjectDetail 数据列表 `qa_status` 徽章。
- QA 面板无报告、有 mock 报告、有 blocking issue 三种状态。
- 运行模拟质控按钮成功和错误提示。
- 人工确认 `accept/hold/reject` 后状态刷新。
- Pipeline LoadData 表格 QA 摘要展示。

### 2. 修改文件

为让前端 typecheck 真正可执行，本步新增/修改：

```text
elys_version1/frontend/elys-web/package.json
elys_version1/frontend/elys-web/tsconfig.json
elys_version1/frontend/elys-web/src/components/BidsUploadPanel.vue
elys_version1/frontend/elys-web/src/views/Dashboard.vue
elys_version1/frontend/elys-web/src/views/PipelinePage.vue
elys_version1/frontend/elys-web/src/views/StatisticsPage.vue
```

### 3. Typecheck 工具链补齐

此前前端只有：

```json
"dev": "vite",
"build": "vite build",
"preview": "vite preview"
```

直接执行：

```bash
npx vue-tsc --noEmit
```

只会打印 TypeScript 帮助并退出，因为前端目录没有 `tsconfig.json`。

本步新增：

```json
"typecheck": "vue-tsc --noEmit"
```

并新增最小 `tsconfig.json`：

- `moduleResolution=Bundler`
- `baseUrl=.` 
- `paths["@/*"]=["src/*"]`
- `types=["vite/client"]`
- include `src/**/*.ts`、`src/**/*.d.ts`、`src/**/*.vue`

### 4. Typecheck 修复内容

新增 typecheck 后暴露出若干既有类型问题，已一并修复：

| 文件 | 修复 |
|---|---|
| `BidsUploadPanel.vue` | 用正则替代 `replaceAll`，并调整拖拽目录 entry 过滤类型 |
| `Dashboard.vue` | 将 `!validation.ok` 改为 `validation.ok === false`，让联合类型正确收窄 |
| `StatisticsPage.vue` | `resultTabs` 增加 `as const`，保证 tab key 不被扩大为普通 string |
| `PipelinePage.vue` | `startNewPipeline` 点击处理改为显式调用，避免 MouseEvent 被当作参数 |
| `PipelinePage.vue` | 为 litegraph runtime 扩展字段增加 loose 类型封装 |
| `PipelinePage.vue` | 用 `liteGraphNodes()` 统一访问 litegraph 内部 `_nodes`，避免直接触碰 private 类型 |
| `PipelinePage.vue` | `LoadData` 参数规范化时将 `nextParams` 标为 `Record<string, unknown>`，允许删除旧字段 |

这些修复不改变 QA 业务行为，只让类型检查能够通过。

### 5. 已执行检查命令

类型检查：

```bash
npm run typecheck
```

结果：

```text
> elys-web@1.0.0 typecheck
> vue-tsc --noEmit
```

退出码：0。

生产构建：

```bash
npm run build
```

结果：

```text
vite v5.4.21 building for production...
150 modules transformed.
✓ built in 2.29s
```

构建警告仍为项目既有警告：

- Vite CJS Node API deprecated warning。
- `litegraph.js` 使用 `eval`。
- `PipelinePage` chunk 大于 500 kB。

### 6. 浏览器验证环境

本地已有前端实例：

```text
http://127.0.0.1:5173
```

真实后端 `http://127.0.0.1:8000` 当前没有可用服务，直接登录会失败。

为验证前端交互本身，本步临时启动了一个只用于本轮验证的 fake API，模拟：

- `/api/v1/auth/login`
- `/api/v1/projects`
- `/api/v1/projects/{project_id}`
- `/api/v1/projects/{project_id}/datasets`
- `/api/v1/projects/{project_id}/datasets/{dataset_id}/qa`
- `/api/v1/projects/{project_id}/datasets/{dataset_id}/qa/mock-run`
- `/api/v1/projects/{project_id}/datasets/{dataset_id}/qa/review`
- `/api/v1/pipeline/nodes`
- `/api/v1/projects/{project_id}/pipelines`
- `/api/v1/projects/{project_id}/pipeline/load-data/resolve`

验证完成后 fake API 已停止。

限制：

- 本轮是前端交互验证，不是真实 PostgreSQL/真实后端联调。
- loading 状态因 fake API 响应很快，只确认了按钮 disabled/loading 代码路径和请求前按钮可用；真实慢请求下仍需再做一次视觉确认。

### 7. ProjectDetail 数据列表验证

登录后进入：

```text
http://127.0.0.1:5173/projects/202605000001
```

验证结果：

| 数据 | 状态 | 前端展示 |
|---|---|---|
| `sub-001` | `converted` | 数据列表显示 `converted` QA 徽章 |
| `sub-003` | `failed` | 数据列表显示 `failed` QA 徽章 |
| `sub-005` | `checked` | 数据列表显示 `checked` QA 徽章 |
| `sub-007` | `rejected` | 数据列表显示 `rejected` QA 徽章 |

确认数据列表中每行都有“质控”入口。

### 8. QA 面板三种状态验证

| 状态 | 操作 | 验证结果 |
|---|---|---|
| 无报告 | 打开 `sub-001` QA 面板 | 显示“尚未运行模拟质控”和“运行模拟质控”按钮 |
| 有 mock 报告 | 打开 `sub-002` QA 面板 | 显示“模拟质控”、summary、stages、`真实 RMS/PSD/坏段指标尚未实现` |
| 有 blocking issue | 打开 `sub-003` QA 面板 | 显示 `failed`、阻塞问题 `fif_exists`，并显示“存在阻塞问题，不能确认通过。” |

blocking issue 状态下，“通过”按钮验证为 disabled。

### 9. 运行模拟质控按钮验证

成功场景：

- 打开 `sub-001` 无报告面板。
- 点击“运行模拟质控”。
- 成功后面板从“尚未运行模拟质控”切换为 mock 报告。
- 显示：
  - `mode=mock`
  - `score=未计算`
  - `signal_placeholder=未计算`
  - “真实 RMS/PSD/坏段指标尚未实现”

错误场景：

- 打开 `sub-008` 无报告面板。
- 点击“运行模拟质控”。
- fake API 返回 500。
- 前端显示：

```text
模拟质控运行失败：fake API error
```

页面没有崩溃，仍保留“尚未运行模拟质控”和“运行模拟质控”按钮。

### 10. 人工确认交互验证

| 操作 | 数据 | 备注 | 结果 |
|---|---|---|---|
| accept | `sub-004` | `accept ok` | 面板和列表状态刷新为 `checked`，human_review 显示 `accept`、备注、确认人、确认时间 |
| hold | `sub-005` | `hold note` | 面板和列表状态刷新为 `converted`，没有写成 `checked` |
| reject | `sub-006` | `reject note` | 面板和列表状态刷新为 `rejected`，human_review 显示 `reject` |

验证后的数据列表片段显示：

```text
sub-004 ... checked
sub-005 ... converted
sub-006 ... rejected
```

### 11. Pipeline LoadData QA 摘要验证

进入：

```text
http://127.0.0.1:5173/pipeline?projectId=202605000001
```

fake pipeline 默认包含一个 `LoadData` 节点，并自动选中。

验证结果：

| 数据 | LoadData 展示 |
|---|---|
| `sub-001` | `converted`、`模拟质控`、`阻断 0 · 警告 1` |
| `sub-002` | `converted`、`模拟质控`、`阻断 0 · 警告 1` |
| `sub-004` | `checked`、`模拟质控`、`阻断 0 · 警告 1` |
| `sub-005` | `converted`、`模拟质控`、`阻断 0 · 警告 0` |
| `sub-008` | `converted`、`未检查` |

同时确认：

- `failed` 的 `sub-003` 没有出现在 LoadData 可选表格。
- `rejected` 的 `sub-006/sub-007` 没有出现在 LoadData 可选表格。
- LoadData 解析摘要显示“后端可运行 5 个数据集，其中 FIF 可用 5 个”。

### 12. 本步没有做的事

- 未接入真实后端服务和真实 PostgreSQL。
- 未新增 Vitest/Cypress/Playwright 自动化测试套件。
- 未验证慢网络下 loading 的视觉持续状态。
- 未实现真实 RMS/PSD/坏段结果展示。

### 13. 下一步建议

执行 Step 15：做真实后端环境下的联调回归。建议启动真实 FastAPI + PostgreSQL，使用真实上传数据跑通 `upload -> mock-run -> accept/hold/reject -> Pipeline LoadData resolve`，确认 fake API 中验证过的交互在真实数据库状态下完全一致。

---

## Step 15 执行记录：上传后模拟质控最小端到端验证

### 1. 本步目标

确认上传后模拟质控链路可以从项目数据列表串到 Pipeline `LoadData`：

```text
converted dataset -> QA 面板 -> mock-run -> qa_report.mode='mock' -> accept/reject -> qa_status 更新 -> LoadData 展示与过滤
```

### 2. 环境检查结论

本轮没有使用真实后端和真实 EEG 文件完成完整联调，原因如下：

- 前端开发服务可用：`http://127.0.0.1:5173`。
- 真实后端 `http://127.0.0.1:8000` 当前不可连接，`GET /api/v1/projects` 失败。
- 当前 Python 环境中 `fastapi` 未安装，因此不能直接启动真实 FastAPI 服务。
- 本轮未连接真实 PostgreSQL，也未执行真实上传流程。

因此，本步采用“真实前端 + 最小 fake API”的方式验证前端端到端交互和接口契约。fake API 仅用于本步验证，验证结束后已经停止。

### 3. fake API 覆盖接口

本轮临时模拟了以下接口：

```text
GET  /api/v1/projects
GET  /api/v1/projects/{project_id}
GET  /api/v1/projects/{project_id}/datasets
GET  /api/v1/projects/{project_id}/datasets/{dataset_id}/qa
POST /api/v1/projects/{project_id}/datasets/{dataset_id}/qa/mock-run
POST /api/v1/projects/{project_id}/datasets/{dataset_id}/qa/review
GET  /api/v1/pipeline/nodes
GET  /api/v1/projects/{project_id}/pipelines
POST /api/v1/projects/{project_id}/pipeline/load-data/resolve
GET  /api/v1/projects/{project_id}/pipelines/{pipeline_id}/runs
```

验证项目：

```text
project_id = 202605000015
project_name = Step15 模拟质控端到端项目
```

准备的数据：

| 数据 | 初始状态 | 用途 |
|---|---|---|
| `sub-101` / `ds-e2e-accept` | `converted`，无 `qa_report` | 验证 mock-run 后 accept |
| `sub-102` / `ds-e2e-reject` | `converted`，已有 mock 报告 | 验证 reject 后 LoadData 排除 |
| `sub-103` / `ds-e2e-control` | `converted`，已有 mock 报告 | 验证普通 converted 数据仍可见 |

### 4. 项目数据列表与 QA 面板验证

进入：

```text
http://127.0.0.1:5173/projects/202605000015
```

验证结果：

- 项目数据列表成功显示 `sub-101`、`sub-102`、`sub-103`。
- 每行均显示 `qa_status` 徽章和“质控”入口。
- `sub-101` 初始显示 `converted`。
- 点击 `sub-101` 的“质控”后，QA 面板显示“尚未运行模拟质控”和“运行模拟质控”按钮。

### 5. mock-run 验证

对 `sub-101` 点击“运行模拟质控”。

验证结果：

- 请求命中 `POST /projects/202605000015/datasets/ds-e2e-accept/qa/mock-run`。
- 面板刷新为 mock 报告。
- `qa_report.mode = mock`。
- `summary.score = null`，前端显示“未计算”。
- `signal_placeholder.status = not_computed`。
- 面板明确显示“模拟质控，真实信号指标未计算”。
- stages 展示完整，包含：
  - `preflight`
  - `identity`
  - `file_integrity`
  - `metadata_consistency`
  - `fif_header`
  - `channels_sidecar`
  - `events_sidecar`
  - `signal_placeholder`

### 6. accept 验证

对 `sub-101` 在 QA 面板点击“通过”。

验证结果：

- 请求命中 `POST /projects/202605000015/datasets/ds-e2e-accept/qa/review`。
- fake API 写入 `human_review.conclusion = accept`。
- `qa_status` 从 `converted` 更新为 `checked`。
- QA 面板显示：
  - `checked`
  - `人工确认`
  - `结论 accept`
  - `确认人 user-admin`
  - history 中包含 `dataset.qa.review`

最终状态：

```text
ds-e2e-accept: qa_status=checked, qa_report.mode=mock, signal_placeholder=not_computed, review=accept
```

### 7. reject 验证

对 `sub-102` 打开 QA 面板并点击“拒绝”。

验证结果：

- 请求命中 `POST /projects/202605000015/datasets/ds-e2e-reject/qa/review`。
- fake API 写入 `human_review.conclusion = reject`。
- `qa_status` 从 `converted` 更新为 `rejected`。
- QA 面板显示：
  - `rejected`
  - `结论 reject`
  - history 中包含 `dataset.qa.review`

最终状态：

```text
ds-e2e-reject: qa_status=rejected, qa_report.mode=mock, signal_placeholder=not_computed, review=reject
```

### 8. Pipeline LoadData 验证

进入：

```text
http://127.0.0.1:5173/pipeline?projectId=202605000015
```

验证结果：

| 数据 | LoadData 结果 |
|---|---|
| `sub-101` / `ds-e2e-accept` | 可见，显示 `checked`、`模拟质控`、`阻断 0 · 警告 1` |
| `sub-102` / `ds-e2e-reject` | 不可见，`rejected` 被默认排除 |
| `sub-103` / `ds-e2e-control` | 可见，显示 `converted`、`模拟质控`、`阻断 0 · 警告 1` |

LoadData 解析摘要显示：

```text
后端可运行 2 个数据集，其中 FIF 可用 2 个
```

这说明 `checked` 数据没有改变默认可选逻辑，`converted` 数据仍然可选，`rejected` 数据按预期被排除。

### 9. 最终状态汇总

```text
ds-e2e-accept:
  qa_status = checked
  qa_report.mode = mock
  blocking_issues = 0
  warnings = 1
  human_review.conclusion = accept
  signal_placeholder.status = not_computed

ds-e2e-reject:
  qa_status = rejected
  qa_report.mode = mock
  blocking_issues = 0
  warnings = 1
  human_review.conclusion = reject
  signal_placeholder.status = not_computed

ds-e2e-control:
  qa_status = converted
  qa_report.mode = mock
  blocking_issues = 0
  warnings = 1
  human_review.conclusion = null
  signal_placeholder.status = not_computed
```

### 10. 本步已确认

- 项目数据列表可以打开上传后 QA 面板。
- 无报告数据可以运行 mock-run 并生成 `qa_report.mode='mock'`。
- QA 面板可以展示 summary、stages、human_review 和 history。
- `signal_placeholder` 按要求显示真实 RMS/PSD/坏段指标尚未实现。
- accept 后 `qa_status` 可以更新为 `checked`。
- reject 后 `qa_status` 可以更新为 `rejected`。
- Pipeline `LoadData` 可以显示 `checked/converted` 数据的模拟质控摘要。
- Pipeline `LoadData` 默认排除 `rejected` 数据。

### 11. 本步未完成的真实环境项

- 未执行真实文件上传。
- 未使用真实 EEG/FIF 文件。
- 未启动真实 FastAPI 服务。
- 未连接真实 PostgreSQL。
- 未验证真实数据库中的 `qa_report`、`qa_status`、审计记录、history 是否持久化。
- 本轮 accept/reject 没有再次验证备注输入；备注输入已经在 Step 14 的前端交互验证中覆盖，本轮因为浏览器输入通道偶发不可用，accept/reject 使用无备注提交完成主链路验证。

### 12. 下一步建议

下一轮应执行真实后端环境联调：

```text
真实 FastAPI + PostgreSQL -> 真实上传或导入 converted dataset -> mock-run -> accept/hold/reject -> 数据库检查 -> Pipeline LoadData resolve
```

建议把下一轮拆成两个小步骤：

1. 先补齐本机后端依赖和启动脚本，确保 `http://127.0.0.1:8000/api/v1/projects` 可用。
2. 再用一份真实上传数据重复本步流程，重点检查数据库持久化、权限校验、审计记录和真实 LoadData resolve 结果。

---

## Step 16 执行记录：同步上传后模拟质控实现结果到 wiki 和会议文档

### 1. 本步目标

根据当前代码实际实现情况，把上传后模拟质控从“流程规划”同步为“mock 最小闭环已实现”，同时继续明确真实 RMS/PSD/坏段/坏通道算法仍未实现，不把导入成功或 mock 通过写成真实质量通过。

### 2. 已同步的 wiki 文档

| 文档 | 更新内容 |
|---|---|
| `wiki/docs/M2-15-上传后模拟质控流程.md` | 状态改为 mock 最小闭环已实现；补充已实现 API、前端操作、后端 stages、验收状态和未完成真实算法 |
| `wiki/docs/M2-00-数据质控模块总览.md` | M2-15 状态改为已实现；M2-50 改为 mock 报告已接入；补充 QA 审计、history、LoadData 过滤关系 |
| `wiki/docs/M2-50-质控报告.md` | 明确 `qa_report.mode='mock'` 已启用；补充当前 v1 schema、已实现 API、前端展示、待实现 `mode='real'` |
| `wiki/docs/M1-30-数据导入.md` | 说明导入成功后进入 `converted`，可打开 QA 弹窗运行模拟质控，但不会直接写成 `checked` |
| `wiki/docs/2-50-API设计总览.md` | 新增 GET `/qa`、POST `/qa/mock-run`、POST `/qa/review`；数据集接口数量从 2 更新为 5，总数从 22 更新为 25 |
| `wiki/docs/4-07-数据质控页.md` | 独立质控页仍规划；当前项目详情页 QA 弹窗和 Pipeline LoadData QA 摘要已实现 |

### 3. 当前实现状态摘要

后端已实现：

- `backend/app/schemas/dataset.py`：`DatasetQaReport`、`DatasetQaSummary`、`DatasetQaStage`、`DatasetQaStageItem`、`DatasetQaHumanReview`、`DatasetQaResponse`、`DatasetQaReviewRequest`。
- `backend/app/services/dataset_qa.py`：`build_mock_qa_report(project, dataset)`，生成 `qa_report.mode='mock'`。
- `backend/app/routers/datasets.py`：
  - `GET /api/v1/projects/{project_id}/datasets/{dataset_id}/qa`
  - `POST /api/v1/projects/{project_id}/datasets/{dataset_id}/qa/mock-run`
  - `POST /api/v1/projects/{project_id}/datasets/{dataset_id}/qa/review`
- mock-run / review 写入轻量审计：`project_audit_events.action='dataset.qa.mock_run'` 和 `dataset.qa.review`。
- `qa_report.history` 追加简短历史记录。
- `accept` 只有无 blocking issue 才能写 `checked`；`reject` 写 `rejected`；`hold` 不写 `checked`。

前端已实现：

- `frontend/elys-web/src/types/index.ts`：Dataset QA 类型。
- `frontend/elys-web/src/api/datasets.ts`：`getQa`、`runMockQa`、`reviewQa`。
- `ProjectDetailPage.vue`：数据列表 QA 状态徽章、“质控”入口、QA 面板、mock-run、accept/hold/reject、human_review/history 展示。
- `PipelinePage.vue`：LoadData 表格显示 `qa_status`、`模拟质控`、阻断/警告数量；默认允许 `converted + checked`，排除 `failed/rejected/deleted`。

### 4. 必须继续保持的边界

- `qa_report.mode='mock'` 必须显式标注。
- mock 模式 `summary.score=null`。
- `signal_placeholder.status='not_computed'`。
- 真实 RMS/PSD/坏段/坏通道算法仍未实现，继续写为规划。
- 导入成功只代表 `qa_status='converted'`，不能写成质量通过。
- 只有人工 accept 且无 blocking issue，才写 `qa_status='checked'`。

### 5. 测试命令与结果

文档严格构建：

```bash
cd wiki
mkdocs build --strict
```

结果：

```text
INFO    -  Cleaning site directory
INFO    -  Building documentation to directory: D:\proposal\20260106 念通软件开发\claude\wiki\site
INFO    -  Documentation built in 2.46 seconds
```

说明：构建通过。控制台出现 Material for MkDocs 关于 MkDocs 2.0 的上游提示，不是本次文档错误。

后端 QA 最小测试：

```bash
cd elys_version1/backend
python tests/test_dataset_qa_mock_run.py
```

结果：

```text
dataset qa service/api tests passed
```

前端类型检查：

```bash
cd elys_version1/frontend/elys-web
npm run typecheck
```

结果：

```text
> elys-web@1.0.0 typecheck
> vue-tsc --noEmit
```

退出码为 0。

### 6. 本步未完成项

- 未新增真实 RMS/PSD/坏段/坏通道算法。
- 未实现 `qa_report.mode='real'`。
- 未实现项目级独立 `/qc` 或 `/projects/:id/qc` 质控页。
- 未实现项目级 HTML/PDF 质控报告导出。
- 未执行真实 FastAPI + PostgreSQL + 真实 EEG 上传的完整联调；Step 15 已用真实前端 + fake API 跑通最小链路，真实环境联调仍建议单独执行。

### 7. 下一步建议

下一步优先做真实环境联调和部署检查：

1. 补齐本机后端依赖，启动真实 FastAPI。
2. 连接真实 PostgreSQL。
3. 用一份真实 EDF/BDF/BrainVision 数据上传生成 `converted` dataset。
4. 跑真实 API：GET `/qa`、POST `/qa/mock-run`、POST `/qa/review`。
5. 检查数据库中 `datasets.qa_report`、`datasets.qa_status`、`project_audit_events` 与 `qa_report.history`。
6. 进入 Pipeline LoadData 确认 `checked/converted` 可见、`rejected/failed/deleted` 排除。
