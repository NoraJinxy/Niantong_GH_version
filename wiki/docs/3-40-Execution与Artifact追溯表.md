# 3-40 Execution 与 DerivedDataset 追溯表

> 本页维护 Execution、Execution Input、Job、DerivedDataset 和 Execution Dependency。它是执行追溯、缓存复用和输出清理的数据库依据。详见 [3-45 DerivedDataset](3-45-DerivedDataset.md)。

<div class="elys-meta" markdown>

定位
: 执行项、输入快照、节点记录、派生数据、依赖关系

更新
: 2026-06-04 +08:00

</div>

## 1. `pipeline_executions`

`pipeline_executions` 是 Pipeline 的执行记录。

| 字段 | 说明 |
|---|---|
| `id` | UUID 主键 |
| `study_id` | 当前兼容字段，记录 Study 上下文 |
| `pipeline_id` / `pipeline_version` | 对应 Pipeline 定义和版本 |
| `definition_snapshot` | 当时 Pipeline 定义的快照 |
| `manifest_json` | 终态 Execution 摘要，详情见 5-30 |
| `execution_mode` | `trial` · `analysis` · `replay` · `system` |
| `save_policy` | `temporary` · `current` · `pinned` · `discard` |
| `status` | `queued` · `running` · `waiting_user_input` · `completed` · `failed` · `canceled` |
| `dataset_count` / `node_count` | 摘要字段 |
| `error_json` / `result_json` | 错误细节和元信息 |
| `started_at` / `finished_at` / `created_at` | 生命周期时间 |
| `started_by` | 触发人 |

历史 Execution 永远使用 `definition_snapshot` 作为事实源，不读 Pipeline 当前定义。

## 2. `pipeline_execution_inputs`

`pipeline_execution_inputs` 冻结本次执行实际使用的数据。

| 字段 | 说明 |
|---|---|
| `id` | UUID 主键 |
| `execution_id` | 所属 Execution |
| `input_slot` | 工作流输入槽或节点 ID |
| `study_id` / `pipeline_id` / `job_id` | 冗余归属，便于查询和追溯 |
| `node_id` / `node_type` | 哪个节点解析出的输入 |
| `input_kind` | `selector` · `dataset_file` · `dataset` · `derived_dataset` · `upstream_dataset` |
| `dataset_asset_id` / `recording_id` / `recording_version_id` / `dataset_file_id` | 输入来源的资产、采集记录、上传版本与文件索引（旧列名 `dataset_id` / `dataset_upload_id` 已不存在） |
| `file_role` / `storage_uri` / `logical_path` | 输入文件角色、读取 URI 和逻辑路径 |
| `upstream_execution_id` / `upstream_dataset_id` | 上游 Execution 输出来源，`upstream_dataset_id` FK 指向 `derived_datasets` |
| `selector_json` | 当时的选择规则 |
| `resolved_metadata_json` | 当时解析到的被试、session、task、run、QC 等元数据 |
| `sha256` | 输入文件校验值 |

这张表是解决"Dataset 继续上传后，旧结果是否还可追溯"的关键。

## 3. `pipeline_jobs`

节点级执行记录用于进度、缓存、错误定位和性能统计。

| 字段 | 说明 |
|---|---|
| `execution_id` | 所属 Execution |
| `node_id` / `node_type` / `node_title` | 节点身份 |
| `status` | `pending` · `running` · `completed` · `failed` · `skipped` · `cached` |
| `params_json` / `input_json` / `output_json` | 节点参数、输入摘要、输出摘要 |
| `input_hash` / `params_hash` / `node_hash` | 缓存与复用依据 |
| `trace_code` / `error_json` / `log_tail` | 调试与错误追踪 |

## 4. `derived_datasets`

`derived_datasets` 是 Execution 产生的所有派生数据登记。

| 字段组 | 说明 |
|---|---|
| 来源追溯 | `produced_by_execution_id` / `produced_by_job_id` / `produced_by_node_id` / `produced_by_node_type` / `produced_by_params` / `upstream_dataset_ids` / `upstream_recording_ids` |
| 数据语义 | `data_type` 枚举 / `subject_id` / `bids_subject_id` / `session` / `task` / `run_label` / `condition` |
| 用户层面 | `display_name` / `description` / `tags` |
| 物理存储 | `storage_uri` / `logical_path` / `file_role` / `file_size` / `sha256` / `mime_type` |
| 生命周期 | `retention_status` ∈ `current / pinned / cached / temporary / deleted / quarantined` + `retention_expires_at` |
| 预览 | `preview_json` |

完整字段定义、生命周期策略、Save 节点 promote 语义见 [3-45 DerivedDataset](3-45-DerivedDataset.md)。

产品语义操作通过 PATCH 统一入口：

| 操作 | 数据库效果 | 说明 |
|---|---|---|
| pin | `retention_status='pinned'` + 清 expires | 用户固定重要输出 |
| unpin / 设为正式 | `retention_status='current'` | 取消固定，但不恢复已 hidden 输出 |
| hide / 隐藏 | `retention_status='deleted'` + 写 `deleted_at` | 从普通列表隐藏；不物理删除文件 |
| Save 节点 promote | retention 切到 current/pinned + 设 display_name + 合并 tags | 跑 Pipeline 时自动 |

所有操作都会写 `audit_events`，用于回看谁在什么时间改动了派生数据。

## 5. `pipeline_execution_dependencies`

用于记录下游 Execution 对上游 Execution / DerivedDataset 的依赖，辅助清理和重建。

| 字段 | 说明 |
|---|---|
| `execution_id` | 当前下游 Execution |
| `depends_on_execution_id` | 被依赖的上游 Execution |
| `upstream_dataset_id` | 被依赖的上游派生数据集，FK 指向 `derived_datasets` |
| `dependency_kind` | `upstream_execution` · `upstream_derived_dataset` · `retry_of` 等 |
| `metadata_json` | 依赖来源、节点、输入槽等扩展信息 |

如果某个 DerivedDataset 被下游 Execution / 报告 / 固定结果引用，不允许直接 hide 或物理清理。

## 5.1 Execution Lineage 聚合视图

后端接口：

```text
GET /studies/{study_id}/pipeline-executions/{execution_id}/lineage
```

聚合来源：

| 来源 | 用途 |
|---|---|
| `pipeline_execution_inputs` | 当前 Execution 的输入快照，并补充输入来源边 |
| `derived_datasets WHERE produced_by_execution_id = 当前 Execution` | 当前 Execution 产生的输出，包括 deleted 状态 |
| `pipeline_execution_dependencies.execution_id = 当前 Execution` | 上游 Execution / DerivedDataset 依赖 |
| `pipeline_execution_dependencies.depends_on_execution_id = 当前 Execution` | 下游 Execution 反向依赖 |
| `pipeline_execution_dependencies.upstream_dataset_id in 当前 Execution 输出` | 当前输出被哪些下游 Execution 使用 |

返回 `graph_nodes` 和 `graph_edges`，节点类型是 `execution` / `input` / `derived_dataset`，便于前端直接画图。

## 6. 当前代码映射

| 当前表 | 说明 |
|---|---|
| `pipeline_executions` | Pipeline 执行记录，含 `manifest_json`、`execution_mode`、`save_policy` |
| `pipeline_jobs` | 节点级执行记录 |
| `derived_datasets` | 派生数据登记 |
| `pipeline_execution_dependencies` | Execution / DerivedDataset 依赖保护，阻止被下游引用的派生数据 hide / 清理 |
| `dataset_file_derivations` | Dataset 文件级派生关系 |

## 7. 回归关注点

| 链路 | 当前可验证事实 |
|---|---|
| Execution 创建 | `create_pipeline_execution()` 创建 `pipeline_executions(status=queued)` + `async_tasks(status=queued)` |
| 输入冻结 | `PipelineExecutor.prepare_execution()` 写入 `pipeline_execution_inputs`，并优先匹配 `dataset_files` |
| 任务关联 | `async_tasks.resource_kind='pipeline_execution'`、`resource_id=execution.id`；Celery id 同步到 `async_tasks.celery_task_id` |
| 任务事件 | 创建、派发、运行、完成、失败路径写 `task_events` |
| DerivedDataset 写入 | `DerivedDatasetStore` 新产物写 `elys://studies/...`、`sha256`；中间节点默认 `retention_status='cached'` + 7 天 expires，`save_output=true` 节点直接 `current` |
| 缓存复用 | `PipelineCache` 复用产物时写 `retention_status='cached'`，指向同 `storage_uri` |
| Execution manifest | 终态 Execution 生成 `execution_manifest.json` 和 `manifest_json` 摘要，含每条派生数据的完整字段快照 |
| Execution dependency | 上游 DerivedDataset 输入写入 `pipeline_execution_inputs.upstream_dataset_id` 与 `pipeline_execution_dependencies.upstream_dataset_id` |
| Execution lineage | `/pipeline-executions/{execution_id}/lineage` 聚合输入、输出、上下游 Execution 和 graph nodes/edges |
| 派生数据 PATCH | 统一 `PATCH /derived-datasets/{id}` 改 display_name / tags / retention，hide/delete 复用下游依赖 blocker |
| Cleanup blocker | 被依赖派生数据标记 deleted 返回 409；cleanup 任务跳过被依赖项 + 未到期项 |
| Save promote | Save 节点不写新行；调用 `DerivedDatasetStore.save_promotion()` UPDATE 上游派生数据集 retention/display_name/tags |

## 8. 相关页面

- [3-45 DerivedDataset](3-45-DerivedDataset.md)
- [4-30 Study 输出与 DerivedDataset](4-30-Study输出与Artifact.md)
- [4-50 清理策略与迁移](4-50-清理策略与迁移.md)
- [2-60 任务队列与异步架构](2-60-任务队列与异步架构.md)
- [5-30 Execution 管理](5-30-Execution管理.md)
