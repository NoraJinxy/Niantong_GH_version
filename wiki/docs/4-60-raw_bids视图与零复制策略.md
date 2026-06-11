# 4-60 raw_bids 视图与零复制策略

> 本页说明 `raw_bids` 如何作为标准 BIDS 入口存在，同时避免把 EEG 大文件物理复制多份。

<div class="elys-meta" markdown>

定位
: Raw BIDS 逻辑视图、硬链接、reflink、对象引用、格式处理策略

更新
: 2026-05-21 17:59:13 +08:00

</div>

!!! warning "已定型（2026-06-11 两层重构）"
    raw_bids **永久定型为纯逻辑索引**，不再是目录概念。「给我 sub-001/task-rest 的原始文件」由 `recordings` 表（BIDS 四元组）+ `dataset_files` 里 `file_role='original_upload'` 行的 `storage_uri` 回答；导入时**不复制、不建硬链接/reflink、不重写格式头、不单独登记 file_role**。

    §2.2 硬链接 / reflink 混合视图、§2.3 `storage_objects` 物理对象表方案**已废弃**（不再规划，`storage_objects` 表不会建）。下文 §2.2–§2.3 / §3 链接重写 / §4 第 3–4 步保留仅作历史设计参考，**不代表路线**。要对外交付标准 BIDS 包走「按需导出」（从 `sourcedata/` + sidecar 临时物化），不常驻磁盘。canonical FIF 现常驻 `BIDSdata/`（见 [4-20](4-20-Dataset文件与导入转换.md)）。

## 1. 核心判断

raw_bids 作为「标准原始数据入口」的语义不变——它决定数据能否被共享、验证、导出和长期解释——但**它不是物理目录，而是逻辑索引**：

- **（已定型）** 数据库中的逻辑 BIDS 映射：`recordings` 四元组 + `original_upload` 行的物理位置。
- **（已废弃）** 文件系统硬链接 / reflink。
- **（已废弃）** 对象存储同一 object 多个逻辑引用。
- **（已废弃）** `storage_objects` + `dataset_files` 多对一映射。

## 2. 三种实现层级

### 2.1 逻辑索引（已定型）

服务器上只保存原始上传：

```text
sourcedata/original_uploads/upload-001/original.edf
```

数据库登记（两层重构后 raw_bids 不再单独登记 file_role，原始文件就一条 `original_upload` 行）：

```text
recordings
  bids_subject_id: sub-001   session: ses-01   task: task-rest   run: run-01   # BIDS 四元组身份
dataset_files
  file_role: original_upload
  logical_path: sourcedata/original_uploads/upload-001/original.edf
  storage_uri: elys://datasets/ds-000001/sourcedata/original_uploads/upload-001/original.edf
  sha256: ...
```

「sub-001/ses-01/task-rest 的原始文件在哪」= 用四元组在 `recordings` 定位采集记录 → 取其 `original_upload` 行的 `storage_uri`。优点是最省空间、无冗余行；要标准 Raw BIDS 文件树时按需临时组装导出。

### 2.2 混合视图（规划，未实现）

目录上真的有 `raw_bids/`，但大文件用硬链接或 reflink，小文件由平台生成。

```text
sourcedata/original_uploads/upload-0001/
  original.edf

raw_bids/sub-001/ses-01/eeg/
  sub-001_ses-01_task-rest_run-01_eeg.edf        # hardlink/reflink
  sub-001_ses-01_task-rest_run-01_eeg.json       # generated
  sub-001_ses-01_task-rest_run-01_channels.tsv   # generated
  sub-001_ses-01_task-rest_run-01_events.tsv     # generated
```

Linux 本地文件系统可以用硬链接：

```bash
ln original.edf sub-001_ses-01_task-rest_run-01_eeg.edf
```

支持 copy-on-write 的文件系统可以用 reflink：

```bash
cp --reflink=auto original.edf sub-001_ses-01_task-rest_run-01_eeg.edf
```

### 2.3 物理对象 + 逻辑文件（规划，未实现）

正式平台建议引入 `storage_objects`（当前 schema 中无此表）：

```text
storage_objects
  id
  storage_uri
  sha256
  size
  mime_type
```

`dataset_files` 只表示逻辑文件：

```text
dataset_files
  id
  dataset_asset_id
  dataset_version_id
  file_role
  logical_path
  storage_object_id
  metadata_json
```

同一个物理对象可以被多个逻辑文件引用：

```text
storage_object: obj-abc
  file:///.../sourcedata/original_uploads/upload-0001/original.edf

dataset_file A:
  role = original_upload
  logical_path = sourcedata/original_uploads/upload-0001/original.edf
  storage_object_id = obj-abc

dataset_file B:
  role = raw_bids_data
  logical_path = raw_bids/sub-001/ses-01/eeg/sub-001_ses-01_task-rest_run-01_eeg.edf
  storage_object_id = obj-abc
```

## 3. 格式处理策略

| 上传格式 | raw_bids 视图策略 | 注意事项 |
|---|---|---|
| 标准 BIDS | 直接登记为 `raw_bids` | 不复制，保留原目录结构或导入为逻辑视图 |
| EDF / BDF | 大文件硬链接/reflink，补 BIDS 文件名和 sidecar | 文件名可改，内容不用改 |
| BrainVision | `.eeg` 大文件可链接；`.vhdr/.vmrk` 重写 | `.vhdr` 中 `DataFile` / `MarkerFile` 必须指向 BIDS 文件名 |
| EEGLAB | `.fdt` 大文件可链接；`.set` 可能重写 | `.set` 内部引用需要检查 |
| CNT / MAT / 厂商私有格式 | 保留在 `sourcedata`，生成可用 Raw BIDS 或 canonical FIF | 不能假装成 Raw BIDS |

## 4. 写入规则

1. 先保存 `original_upload`。
2. 解析 subject/session/task/run 等 BIDS entities。
3. 判断是否可以零复制构建 Raw BIDS。
4. 能链接就链接，不能链接但可转换就生成 Raw BIDS 文件。
5. 生成 `*_eeg.json`、`*_channels.tsv`、`*_events.tsv`。
6. 为每个逻辑文件写 `dataset_files`。
7. 记录 `source_file_id`、`sha256`、转换参数和导入工具版本。

## 5. 删除与重建

如果 `raw_bids` 是视图：

- 可以删除损坏或过期的视图链接。
- 不能删除底层 `original_upload` 物理对象。
- 必须能通过数据库记录重建视图。
- 导出 Raw BIDS 时，以 `dataset_files.logical_path` 作为包内路径，以 `storage_uri` 读取真实内容。

## 6. MVP 建议

MVP 不需要一次性引入 `storage_objects`，可以先做到：

- `dataset_files.file_role` 细分为 `original_upload`、`raw_bids_data`、`raw_bids_*`、`canonical_fif`。
- `dataset_files.relative_path` 暂作逻辑路径。
- `dataset_files.storage_uri` 记录真实读取位置。
- 对 EDF/BDF 优先硬链接或 reflink。
- 对 BrainVision 重写 `.vhdr/.vmrk`，`.eeg` 大文件尽量链接。

后续再把 `relative_path` 明确拆成 `logical_path`，并引入 `storage_objects`。

## 7. 相关页面

- [4-20 Dataset 文件与导入转换](4-20-Dataset文件与导入转换.md)
- [4-70 文件角色、URI 与追溯关系](4-70-文件角色URI与追溯关系.md)
- [3-20 Dataset 与采集记录表](3-20-Dataset与采集记录表.md)
