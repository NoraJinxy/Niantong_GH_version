# 4-30 Study 输出与 Artifact

> 本页维护 Study 层文件、Execution manifest、日志、Artifact 发布和输出保留状态。

<div class="elys-meta" markdown>

定位
: Study 输出、Execution manifest、Artifact、预览和日志

更新
: 2026-05-22 00:16:57 +08:00

</div>

## 1. Study 文件边界

Study 层保存“为了这个研究问题跑出来的东西”。Study 不复制 Dataset 原始文件，只通过 `study_dataset_mounts` 引用 Dataset 版本，通过 `pipeline_execution_inputs` 冻结某次 Execution 实际使用的数据。

标准目录：

```text
studies/202605000001/
  .elys_study.json
  executions/
    execution-uuid-001/
      execution_manifest.json
      logs/
        load-data.log
        filter.log
        error.log
  derived/
    ab/
      abcdef123456.../
        payload.fif
        metadata.json
  previews/
    derived-dataset-uuid/
      preview.json
      figure.png
  temp/
  exports/
    report-20260521.zip
```

| 目录 | 内容 |
|---|---|
| `executions/{execution_id}/execution_manifest.json` | 本次执行的输入、参数、软件版本、输出索引摘要 |
| `executions/{execution_id}/logs/` | 节点日志、错误日志、运行尾日志 |
| `derived/{sha256[:2]}/{sha256}/` | DerivedDataset 内容寻址输出：clean raw、epochs、ERP、表格、图片、报告、缓存 |
| `previews/` | 前端快速预览用的小文件或缩略图 |
| `temp/` | 运行中的临时文件 |
| `exports/` | 用户导出的报告、数据包、复现包 |

## 2. Execution 输出发布流程

Execution 运行时先写临时目录，成功后再原子发布为 Artifact。

```mermaid
flowchart LR
  Temp[temp/] --> Hash[计算 sha256/content_hash]
  Hash --> Publish[移动到 derived/{sha256[:2]}/{sha256}]
  Publish --> Derived[(derived_datasets)]
  Derived --> Manifest[更新 execution_manifest.json]
  Derived --> Status[current/pinned/cached]
```

规则：

- 临时文件不直接登记为正式输出。
- 正式输出必须有 `derived_datasets` 记录。
- 输出必须记录 `produced_by_execution_id`、`produced_by_job_id`、`file_role`、`data_type`、`storage_uri`、`sha256`。
- 如果内容哈希已存在，可以复用已有文件，只新增新的引用记录。
- 如果用户把某次结果设为当前结果，更新对应 current 标记。

## 3. 输出保留状态

派生数据集（`derived_datasets`，详见 [3-45](3-45-DerivedDataset.md)）的 `retention_status` 六档：

| 状态 | 含义 | 是否可物理清理 | 默认在哪里产生 |
|---|---|---|---|
| `temporary` | 临时预览 / 试跑输出 | 可以 | Execution 模式 = trial 时 |
| `cached` | 可重算缓存 | 可以，但要保留重建信息 | 中间节点（Filter / ICA / Epoch / ERP）默认 + 7 天过期 |
| `current` | 当前认可的工作流结果 | 不可以 | 被 Save 节点引用 / NodeSpec `save_output=true` |
| `pinned` | 用户固定、报告引用、下游依赖 | 不可以 | 用户在 `/results` 页或 Execution 抽屉手动固定 |
| `deleted` | 已隐藏，记录保留 | 已清理 | 用户隐藏或定时清理触发 |
| `quarantined` | 伦理、合规或安全问题隔离 | 不提供普通访问 | 管理员标记 |

用户界面上不暴露"删除服务器文件"这种操作。应提供：

- 设为正式结果（current）
- 固定结果（pinned）
- 取消固定 → current
- 清理可重算缓存
- 隐藏结果（deleted，软删）
- 管理员隔离

当前后端已提供统一 PATCH 入口 `PATCH /derived-datasets/{id}` 改 `retention_status`；批量改走 `POST /derived-datasets/batch-update`；hide 映射到 `deleted` 状态并写 `deleted_at`，但不物理删除文件；如果该 DerivedDataset 已被下游 Execution 使用，会返回 409 和依赖详情。

清理任务 `derived_dataset_cleanup` 跳过未到期 + 被下游依赖的项；只把命中条改 `retention_status='deleted'`，物理文件保留以便恢复。

## 4. Execution Manifest 文件

每个 Execution 建议生成一个 `execution_manifest.json`，同时在 `pipeline_executions.manifest_json` 中保存摘要。

```json
{
  "execution_id": "uuid",
  "study_id": "202605000001",
  "pipeline_id": 12,
  "pipeline_version": 3,
  "inputs": [
    {
      "dataset_asset_id": "ds-000001",
      "dataset_version": "v0001",
      "recording_id": "uuid",
      "file_role": "canonical_fif",
      "storage_uri": "elys://datasets/ds-000001/versions/v0001/derivatives/elys-canonical-fif/...",
      "sha256": "..."
    }
  ],
  "outputs": [
    {
      "derived_dataset_id": "uuid",
      "storage_uri": "elys://studies/202605000001/derived/ab/abcdef...",
      "sha256": "...",
      "retention_status": "current"
    }
  ],
  "software": {},
  "started_by": "uuid",
  "started_at": "2026-05-21T17:59:13+08:00"
}
```

Manifest 的作用不是代替数据库，而是让一次执行可以被导出、审阅、归档和复现。

## 5. Pipeline 定义快照

Pipeline 本质是数据库定义，不拥有数据文件。文件系统最多保存可导出的快照：

```text
studies/202605000001/
  pipeline_snapshots/
    pipeline-12/
      v0003/
        definition.json
```

Execution 创建时仍以 `pipeline_executions.definition_snapshot` 为事实源。

## 6. 与当前代码兼容

| 当前实现 | 标准设计中的位置 | 调整建议 |
|---|---|---|
| 旧 `pipeline_runs/{execution_id}/nodes/{node_id}` | `studies/{study_id}/executions` + `derived/{sha256[:2]}/{sha256}` | 旧输出兼容读取；新派生数据写入 Study content-addressed `derived/` 目录 |
| 旧 `storage_path` 字段 | `derived_datasets.storage_uri` | 统一为 `storage_uri`，使用 `elys://studies/...` |
| `checksum` | `sha256` | 新写入双写；旧字段继续兼容 |
| `retention_status` | 输出保留状态 | 新 Artifact 默认 `current`，缓存复用可写 `cached`，清理任务处理 `temporary/cached` |
| `deleted_at` / `deleted_by` / `last_accessed_at` | 清理和访问追踪 | 预览/下载更新访问时间，逻辑清理写删除信息 |

## 7. 当前状态要点

- DerivedDataset 列表和预览读取数据库中的 `derived_datasets`。
- DerivedDataset 统一使用 `storage_uri`（`elys://studies/...` 协议）。
- 内容校验统一为 `sha256`。
- `deleted` DerivedDataset 默认不在列表展示，预览返回 409。
- 清理策略当前只改变 `retention_status` / `deleted_at`，不能让 Execution 记录消失，也不会物理删除文件。
- pin/unpin/hide 与兼容 retention patch 都写入 `audit_events`；hide/delete 复用同一依赖 blocker。
- Execution 完成、失败、等待用户输入或取消时生成 `execution_manifest.json`（调试期无 backfill 工具，旧 Execution 不回填）。
- 下游依赖会阻止 Artifact 标记为 `deleted`，清理任务必须复用同一依赖检查。

## 8. 相关页面

- [3-40 Execution 与 Artifact 追溯表](3-40-Execution与Artifact追溯表.md)
- [5-00 研究管理总览](5-00-研究管理总览.md)
- [4-50 清理策略与迁移](4-50-清理策略与迁移.md)
