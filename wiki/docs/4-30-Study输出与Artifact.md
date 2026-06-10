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
| `derived/{sha256[:2]}/{sha256}/` | StudyOutput 内容寻址输出：clean raw、epochs、ERP、表格、图片、报告、缓存 |
| `previews/` | 前端快速预览用的小文件或缩略图 |
| `temp/` | 运行中的临时文件 |
| `exports/` | 用户导出的报告、数据包、复现包 |

## 2. Execution 输出发布流程

Execution 运行时先写临时目录，成功后再原子发布为 Artifact。

```mermaid
flowchart LR
  Temp[temp/] --> Hash[计算 sha256/content_hash]
  Hash --> Publish[移动到 outputs/{sha256[:2]}/{sha256}]
  Publish --> Derived[(study_outputs)]
  Derived --> Manifest[更新 execution_manifest.json]
  Derived --> Status[keep / cache_eligible / TTL]
```

规则：

- 临时文件不直接登记为正式输出。
- 正式输出必须有 `study_outputs` 记录。
- 输出必须记录 `produced_by_execution_id`、`produced_by_job_id`、`file_role`、`data_type`、`storage_uri`、`sha256`。
- 如果内容哈希已存在，可以复用已有文件，只新增新的引用记录。
- 用户要长期保存某条输出，置 `keep=true`（永不自动清理）。

## 3. 输出保留状态

输出（`study_outputs`，详见 [3-45](3-45-StudyOutput.md)）的保留模型是三个正交维度（P3 三层解耦，替代旧 `retention_status` 五值状态机）：

| 维度 | 字段 | 含义 |
|---|---|---|
| 用户保存 | `keep` | true＝正式结果、永不自动清理；false＝交回系统按 TTL 管理 |
| 系统缓存 | `cache_eligible` | P4 评分快照（计算贵、产物小才值得缓存），决定 keep=false 行的 TTL 档位 |
| 回收站 | `deleted_at` / `purged_at` | 软删可恢复；GC 物理删盘后置 `purged_at`（终态，DB 行保留可追溯） |

TTL（`retention_expires_at`，仅 keep=false 行有值）口径：

- 产出时：缓存档 `now+7d`；临时档 `now`（登记即过期）。
- 用户动作后（取消保存 / 回收站恢复）：缓存档 `now+7d`；非缓存行给 7 天宽限（`USER_ACTION_GRACE_DAYS`）——保证用户刚点的「不保存 / 恢复」不会被下一轮每日 cleanup 立即软删。

统一 PATCH 入口 `PATCH /outputs/{id}` 改 `keep` / `deleted`；批量改走 `POST /outputs/batch-update`。删除（deleted=true）先做下游依赖检查，被下游 Execution 引用则 409 并附依赖详情；恢复（deleted=false）对 GC 已清盘（`purged_at` 非空）的行 409 `OUTPUT_PURGED`（磁盘文件已删、恢复只会得到无文件的幽灵行）。

清理任务 `study_output_cleanup` 跳过未到期 + 被下游依赖的项；命中只置 `deleted_at`（软删进回收站），物理清盘由 GC（`study_output_gc`）在删除满 30 天后执行。

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
      "study_output_id": "uuid",
      "storage_uri": "elys://studies/202605000001/outputs/ab/abcdef...",
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
| 旧 `pipeline_runs/{execution_id}/nodes/{node_id}` | `studies/{study_id}/executions` + `derived/{sha256[:2]}/{sha256}` | 旧输出兼容读取；新结果写入 Study content-addressed `derived/` 目录 |
| 旧 `storage_path` 字段 | `study_outputs.storage_uri` | 统一为 `storage_uri`，使用 `elys://studies/...` |
| `checksum` | `sha256` | 新写入双写；旧字段继续兼容 |
| `retention_status` | 输出保留状态 | 新 Artifact 默认 `current`，缓存复用可写 `cached`，清理任务处理 `temporary/cached` |
| `deleted_at` / `deleted_by` / `last_accessed_at` | 清理和访问追踪 | 预览/下载更新访问时间，逻辑清理写删除信息 |

## 7. 当前状态要点

- StudyOutput 列表和预览读取数据库中的 `study_outputs`。
- StudyOutput 统一使用 `storage_uri`（`elys://studies/...` 协议）。
- 内容校验统一为 `sha256`。
- `deleted` StudyOutput 默认不在列表展示，预览返回 409。
- 清理策略当前只改变 `retention_status` / `deleted_at`，不能让 Execution 记录消失，也不会物理删除文件。
- pin/unpin/hide 与兼容 retention patch 都写入 `audit_events`；hide/delete 复用同一依赖 blocker。
- Execution 完成、失败、等待用户输入或取消时生成 `execution_manifest.json`（调试期无 backfill 工具，旧 Execution 不回填）。
- 下游依赖会阻止 Artifact 标记为 `deleted`，清理任务必须复用同一依赖检查。

## 8. 相关页面

- [3-40 Execution 与 Artifact 追溯表](3-40-Execution与Artifact追溯表.md)
- [5-00 研究管理总览](5-00-研究管理总览.md)
- [4-50 清理策略与迁移](4-50-清理策略与迁移.md)
