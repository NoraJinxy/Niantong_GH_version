# 3-30 Study 与 Pipeline 表

> 本页维护 Study、成员、Dataset 挂载、Pipeline 和 Pipeline Version。它是研究项协作和工作流定义的数据库依据。

<div class="elys-meta" markdown>

定位
: 研究项、成员、数据挂载、工作流定义

更新
: 2026-06-05 00:56:39 +08:00

</div>

## 1. `studies`

`studies` 是产品层的"研究项"。

| 字段 | 说明 |
|---|---|
| `id` | 12 位 Study ID（`YYYYMM + 6 位序号`） |
| `name` / `code` | 名称和短代码 |
| `description` | 说明 |
| `owner_id` | 负责人 |
| `status` | `active` · `archived` · `trashed` |
| `data_root` | 研究项数据根目录（即以 `id` 命名的存储目录） |
| `storage_quota_bytes` | 空间配额（默认 1 TiB） |
| `created_at` / `updated_at` / `archived_at` | 时间戳 |
| `deleted_at` / `deleted_by` / `delete_reason` | 软删除信息 |

> 运行锁策略、默认数据选择器、派生数据保留策略等**不在 `studies` 表里**，而在独立的 `study_settings` 表（`default_dataset_filter` / `run_policy` / `derived_dataset_retention_policy` / `storage_policy` 四个 JSONB，主键即 `study_id`）。`studies` 没有 `settings_json` 列。

## 2. `study_members`

Study 成员表记录研究项内权限。

| 字段 | 说明 |
|---|---|
| `study_id` | 所属 Study |
| `user_id` | 成员用户 |
| `role` | `owner` · `editor` · `viewer` |
| `can_read` / `can_write` / `can_run` / `can_export` | 可选细粒度权限 |
| `added_by` / `added_at` | 添加信息 |

平台级 RBAC 决定用户能不能创建或管理资源；Study 成员权限决定用户能不能操作某个研究项。

## 3. `study_dataset_mounts`

Study 不复制 Dataset 文件，而是挂载 Dataset 或 Dataset 的一个选择范围。Dataset-first 导入时自动创建或选择的配套 Study，也只是在 `study_dataset_mounts` 中消费 Dataset，不获得 Dataset 所有权。

| 字段 | 说明 |
|---|---|
| `id` | UUID 主键 |
| `study_id` / 当前 `study_id` | 所属 Study |
| `dataset_id` / 当前 `dataset_asset_id` | 被引用 Dataset Asset |
| `mount_name` | 在 Study 内显示的名称 |
| `selection_json` | 默认选择规则，例如 task、group、subject 范围 |
| `is_active` | 是否启用 |
| `mounted_by` / `mounted_at` | 挂载信息 |

选择规则是动态的；Execution 启动时必须把它解析成固定的 `pipeline_execution_inputs`。

当前实现中，Recording 列表、Dataset 列表和 Pipeline LoadData 已经按 active mount 解析外部 Dataset Asset：显式 `mount_id`、`mount_name` 或 `dataset_asset_id` 会先校验挂载关系；未显式指定时默认取当前 Study active mounts，并保留旧 `study_id` fallback。

关系约束：

- `study_id(study_id) + dataset_id(dataset_asset_id) + mount_name` 在 active 范围内应尽量唯一，避免同一 Study 内出现难以区分的同名挂载。
- `selection_json` 只表达默认范围，不等于 Execution 输入事实。
- Dataset 权限、Study 成员权限和挂载状态都要参与 LoadData 解析。
- 禁用挂载只影响后续选择和运行，不能删除历史 `pipeline_execution_inputs`。

## 4. `pipeline_definitions`

`pipeline_definitions` 是工作流定义，把"工作流身份"和"版本化定义"合并在一张表里。

| 字段 | 说明 |
|---|---|
| `id` | SERIAL 主键 |
| `study_id` | 所属 Study |
| `name` / `description` | 工作流名称与说明 |
| `status` | `draft` · `active` · `archived` · `deleted` |
| `version` | 定义版本号；保存新版本时新增一行 |
| `is_template` | 是否为可复用模板 |
| `definition_json` | 节点、连线、默认参数、输入输出槽、选择规则 |
| `node_count` | 节点数量（冗余计数） |
| `created_by` / `created_at` / `updated_at` | 创建和更新信息 |

"当前认可结果"（指这条 Pipeline 被采纳为正式结论的那一次 Execution，区分于最新一次）目前不由 `pipeline_definitions` 上的指针列承载：设计中的 `current_execution_id` 经核实在后端代码与 SQL schema 中均查无，`PipelineDefinition` 模型（`backend/app/models/study.py`）和建表脚本（`database/schema/04_pipelines.sql`）都未定义此列，它只存在于本设计页与规划端点 `POST .../set-current-execution`（见 [2-50 API 设计总览](2-50-API设计总览.md)，标注"规划"）。该语义现由 `current` 保留档（retention tier，按"保留多久、能否清理"给产物分档的一档）承载——Execution 以 `save_policy='current'`（`backend/app/schemas/pipeline.py`）落库、产物落在 `derived_datasets.retention_status='current'`（即"被 Save 节点引用"的正式结果，见 [4-30 Study输出与Artifact](4-30-Study输出与Artifact.md)），再经 `derived_datasets.produced_by_execution_id` 反查到对应的 Execution。专用指针列 `current_execution_id` 仍是设计项、尚未落地。

## 5. 当前代码映射

| 当前表 | 说明 |
|---|---|
| `studies` | 研究项主表 |
| `study_members` | 研究项内成员与权限 |
| `study_dataset_mounts` | Study 与 Dataset Asset 的 active mount 关系，被 Recording/Dataset 列表、LoadData 和上传目标校验消费 |
| `pipeline_definitions` | Pipeline 定义（含版本号、模板标记）|

## 6. 相关页面

- [2-50 API 设计总览](2-50-API设计总览.md)
- [3-40 Execution 与 Artifact 追溯表](3-40-Execution与Artifact追溯表.md)
- [5-00 研究管理总览](5-00-研究管理总览.md)
