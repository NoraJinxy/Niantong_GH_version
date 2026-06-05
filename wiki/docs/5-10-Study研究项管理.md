# 5-10 Study 研究项管理

> 本页说明 Study 的功能边界、管理方式和后端实现方案。当前代码层仍使用 Study 命名，产品语义统一称 Study / 研究项。

<div class="elys-meta" markdown>

状态
: <span class="elys-badge elys-badge--wip">部分接入</span>

前端
: `StudyDetailPage.vue` · `Dashboard.vue`

后端
: `routers/studies.py` · `routers/datasets.py` · `services/study_access.py` · `services/dataset_assets.py`

数据库
: `studies` · `study_members` · `study_settings` · `study_dataset_mounts` · `study_locks` · `audit_events`

更新
: 2026-06-04

</div>

## 1. 功能边界

Study 是围绕一个研究问题的协作空间。它负责：

- 成员和权限。
- Dataset 挂载和默认数据选择范围。
- 工作流定义的组织。
- Execution 的运行策略、并发控制和审计。
- 研究内 DerivedDataset、预览、报告和导出入口。

Study 不负责：

- 拥有 Dataset 原始文件。
- 直接修改 Dataset 的发布版本。
- 把 Pipeline 输出自动当成新 Dataset，除非用户显式发布为 Derived Dataset。

### 1.1 Dataset-first 下的 Study 角色

Dataset-first 导入时，用户创建的是 Dataset。系统可以自动创建一个配套 Study，或让用户选择已有 Study，并把 Dataset 通过 `study_dataset_mounts` 挂进去。这个配套 Study 的职责是承载导入上下文、QC、Pipeline、Execution、DerivedDataset 和审计，不是 Dataset 的所有者。

因此，删除、归档或切换某个 Study 不应直接删除 Dataset 原始文件；要停用某个研究项对数据的使用，应调整挂载关系。只有 Dataset 自身的归档、隔离、删除和权限策略，才决定数据资产本体的生命周期。

## 2. Study 与 Dataset

Study 通过 `study_dataset_mounts` 引用 Dataset。这个关系要按“挂载数据资产”理解，不按“复制数据到研究项”理解：

```text
Study A mounts Dataset X v0001 as working
Study B mounts Dataset X v0001 as external-control
```

### 2.1 责任边界

| 边界 | Dataset | Study |
|---|---|---|
| 核心职责 | 管数据资产本身 | 管研究协作和分析过程 |
| 文件 | 原始上传证据、Raw BIDS、canonical FIF、sidecar、QC、基础 metadata | Execution 输出、DerivedDataset、预览、日志、报告、导出包 |
| 权限 | 数据资产级 owner/member/share，MVP 可先简化 | 研究项成员、编辑、运行、导出和删除权限 |
| 变化 | 可以增量上传、重传和补充 metadata | 引用关系和默认筛选可以调整，但历史 Execution 不变 |

### 2.2 挂载关系

- 一个 Dataset 可以被多个 Study 挂载，用于复用公共数据、对照数据或跨课题共享数据。
- 一个 Study 可以挂载多个 Dataset，例如主试验数据、外部对照数据和示例数据。
- 挂载关系保存 `mount_name`、用途、默认筛选条件、状态和审计信息。
- Study 不复制 Dataset 文件，前端文件选择器和后端 LoadData 都应从数据库索引解析。

### 2.3 Execution 输入冻结

Pipeline 可以保存动态选择规则，例如“使用本 Study 中 task=rest 且 group=control 的当前数据”。Execution 创建时必须把这个规则解析成确定输入，并写入 `pipeline_execution_inputs`：

```text
Study mount + Pipeline selector + Execution override
  -> resolved dataset_files / recording_versions
  -> pipeline_execution_inputs
```

这条规则保证：

- Dataset 增量上传不会自动改变旧 Execution。
- Study 修改挂载或默认筛选不会改写旧 Execution。
- 旧 Execution 可以追溯到当时实际用过的文件、版本、hash 和 selector 快照。
- Dataset 被隔离、禁用或下架后，普通用户不能继续挂载或新运行，但已有 Execution 的追溯记录仍保留。

MVP 阶段 Dataset 版本仍以 working 为主；未来若引入发布版 Dataset，应优先让 Study 挂载不可变发布版本，working 只用于导入、整理和内部迭代。

### 2.4 当前接入状态

Dataset-first bootstrap 会创建或选择配套 Study，并创建 active `study_dataset_mounts`。上传接口通过 `dataset_asset_id` / `mount_name` 找到上传目标；Recording/Dataset 列表和 Pipeline LoadData 读取当前 Study active mounts 解析。历史 Execution 的输入仍以 `pipeline_execution_inputs` 为准，不受后续挂载停用或重命名影响。

## 3. Study Settings

`study_settings` 保存研究项级默认策略：

| 设置 | 作用 | 当前状态 |
|---|---|---|
| `default_dataset_filter` | LoadData 默认筛选范围 | 已被 LoadData 消费 |
| `run_policy` | 是否同一 Study 只允许一个活跃 Execution、是否需要运行锁 | 字段已存在，运行时待完整接入 |
| `derived_dataset_retention_policy` | 新 DerivedDataset 默认保存策略、缓存清理开关（DDL 字段名，非 `artifact_retention_policy`） | 字段已存在，清理服务待接入 |
| `storage_policy` | Study 级配额、冷热存储或导出策略 | 预留 |

Settings 必须成为运行时事实源，不能只是前端可写配置。

## 4. 成员和权限

当前 `study_members` 支持：

| 权限 | 含义 |
|---|---|
| `can_read` | 查看 Study、Dataset mount、Pipeline、Execution |
| `can_write` | 修改 Study 设置、创建/编辑 Pipeline、维护数据挂载 |
| `can_run` | 创建 Pipeline Execution |
| `can_export` | 导出数据包、报告或 Execution manifest |
| `can_delete` | 软删除 Study 或管理成员 |

建议前端把权限影响明确呈现：

- 只有 `can_write` 才能编辑 Pipeline。
- 只有 `can_run` 才能启动 Execution。
- 只有 owner/admin 才能修改成员权限。
- 编辑锁或运行锁占用时，其他人可以查看；其他用户持有编辑锁时不能保存 Pipeline。

## 5. 协作锁

为避免多人同时编辑和运行污染结果，Study 使用 `study_locks` 保存短期协作锁：

```text
study_locks
  study_id
  lock_type = edit / execution
  locked_by
  resource_id
  expires_at
```

规则：

- 同一 Study 内同一 Pipeline 同时只能有一个人持有 active edit lock。
- 同一 Study 是否允许多个活跃 Execution，由 `study_settings.run_policy` 决定。
- 锁必须有 `expires_at`，避免异常后永久占用。
- 锁变化写入 `audit_events`。
- 当前代码已为 Pipeline 提供获取、续期、释放 edit lock API，并在 Pipeline update 时拦截其他用户持有的 active edit lock。

## 6. 审计

Study 级关键行为要留痕：

| 行为 | 审计 action |
|---|---|
| 创建/修改 Study | `study.created` / `study.updated` |
| 修改成员权限 | `study.member.updated` |
| 挂载/停用 Dataset | `dataset_mount.created` / `dataset_mount.disabled` |
| 修改 Study Settings | `study.settings.updated` |
| 启动/取消/重试 Execution | `pipeline.execution.queued` / `pipeline.execution.canceled` / `pipeline.execution.retry_queued` |
| 固定/清理 DerivedDataset | `derived_dataset.retention.pinned` / `derived_dataset.retention.deleted` |
| 永久删除被阻断 | `study.purge_blocked` |

当前代码已经覆盖 settings、mount、pipeline、Pipeline edit lock、Execution cancel/retry、Task cancel/retry、derived_dataset retention、purge blocked 等部分行为；运行中长节点的协作式取消检查仍需补齐。

## 7. 文件边界

Study 目录只存研究输出：

```text
studies/202605000001/
  executions/
  derived/
  previews/
  temp/
  exports/
  pipeline_snapshots/
```

Dataset 原始文件和 canonical FIF 放在 Dataset 目录中，Study 通过数据库引用，不复制。

## 8. API 和数据库实现

| 能力 | 当前 API / 表 |
|---|---|
| 创建 Study | `POST /api/v1/studies` -> `studies` |
| 成员管理 | `/api/v1/studies/{study_id}/members` -> `study_members` |
| Settings | `/api/v1/studies/{study_id}/settings` -> `study_settings` |
| Dataset mount | `/api/v1/studies/{study_id}/datasets/mounts` -> `study_dataset_mounts` |
| Dataset-first bootstrap | `/api/v1/dataset-assets/bootstrap` -> 创建或选择 Dataset Asset、working version、配套 Study 和 mount，并返回 `next_upload` |
| Dataset/Recording 筛选 | `/datasets`、`/recordings` 支持 `dataset_asset_id` / `mount_id` / `mount_name` |
| 软删除/恢复 | `/trash` / `/restore` |
| 永久删除 | `/purge`，已有数据时阻断 |

## 9. 后续实现任务

1. Study 路径已确定为 `/studies`（产品语义即「研究项」，无迁名计划）。
2. 前端接入 Pipeline 编辑锁的获取、续期和释放。
3. `run_policy` 真正控制并发 Execution。
4. `derived_dataset_retention_policy` 接入 DerivedDatasetStore（写 `derived_datasets`）和清理服务。
5. Study activity 页面展示最近谁改了 Pipeline、谁运行、谁固定结果。

## 10. 相关页面

- [5-20 Pipeline 工作流管理](5-20-Pipeline工作流管理.md)
- [5-30 Execution 管理](5-30-Execution管理.md)
- [3-30 Study 与 Pipeline 表](3-30-Study与Pipeline表.md)
- [4-00 文件管理总览](4-00-文件管理总览.md)
