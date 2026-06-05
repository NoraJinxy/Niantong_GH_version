# BIDS 管理：原始归档与 FIF 存储架构

> 更新日期：2026-05-15\
> 关联主文档：[BIDS管理.md](BIDS管理.md)

## 1. 存储原则

念析项目目录是工程工作区，不是一个纯 BIDS dataset。新的存储原则是：

```text
source_uploads/      = 不可变原始上传归档
fifdata/  = 系统统一处理起点，FIF 格式
bids_exports/ = 按需生成的官方 BIDS 导出
```

这样做的好处是：

- 原始文件不被重命名、不被覆盖，便于追溯。
- 所有分析统一从 MNE FIF 读取，减少多格式处理复杂度。
- 通道名、montage、trigger、events 的导入校正可以集中管理。
- 增量上传按 `upload-###` 隔离，不会和已有原始文件混在一起。

代价是：

- `source_uploads/` 不再能直接运行 BIDS Validator。
- `fifdata/` 不是官方 EEG-BIDS raw dataset，因为官方 EEG-BIDS raw 不接受 `.fif` 作为主数据文件。
- 如需对外交付 BIDS，需要额外生成 `bids_exports/`。

## 2. 根目录布局

```text
/mnt/elys_data/projects/{project_id}/
  .elys_project.json
  source_uploads/
  fifdata/
  derivatives/
  pipeline/
  validation/
  upload_staging/
  bids_exports/
```

| 目录                   | 写入来源        | 是否可删除重建 | 说明                                                         |
| -------------------- | ----------- | :-----: | ---------------------------------------------------------- |
| `.elys_project.json` | 系统          |    否    | 项目标记文件                                                     |
| `source_uploads/`           | 导入提交        |    否    | 原始上传归档，保留用户文件                                              |
| `fifdata/`       | 系统导入流程      |  部分可重建  | FIF 处理起点，后续所有操作以此为输入                                       |
| `derivatives/`       | 系统 pipeline |    是    | 预处理和分析结果                                                   |
| `pipeline/`          | 用户/系统       |    否    | 工作流定义                                                      |
| `validation/`        | 系统          |    是    | import validation、FIF validation、BIDS export validation 报告 |
| `upload_staging/`           | 上传临时区       |    是    | 分片/断点续传/未提交 job                                            |
| `bids_exports/`      | 系统按需生成      |    是    | 官方 BIDS 导出和 validator 目标                                   |

## 3. source_uploads：原始上传归档

v1 当前实现中，`source_uploads/` 按 BIDS 数据位和上传序号存放。这样同一 `subject/session/task/run` 的重传可以自然形成 `upload-001`、`upload-002` 历史，而不会覆盖原始文件。

```text
source_uploads/
  sub-001/
    ses-01/
      task-rest/
        run-01/
          upload-001/
            manifest.json
            files/
              S01/rest/sub001.vhdr
              S01/rest/sub001.vmrk
              S01/rest/sub001.eeg
          upload-002/
            manifest.json
            files/
              S01_repeat/rest/sub001.vhdr
              S01_repeat/rest/sub001.vmrk
              S01_repeat/rest/sub001.eeg
```

规则：

| 规则           | 说明                                    |
| ------------ | ------------------------------------- |
| 不改名          | 保留用户原始相对路径和文件名                        |
| 不覆盖          | 每次有效导入递增 `upload-###`              |
| 不手工改         | 任何修正都发生在 `fifdata/` 或数据库 metadata |
| 必须有 manifest | 记录文件、大小、checksum、原始相对路径、分组结果          |
| 可重复上传但需确认    | 同一数据位已存在时，用户确认后新增上传版本并替换当前 FIF |

不再设置 `sourcedata/`。`source_uploads/` 已经承担 source archive 的职责。

## 4. fifdata：统一处理起点

`fifdata/` 保存系统生成的 FIF 和与 FIF 对齐的元数据。它采用 BIDS entities 组织，但不声明自己是官方 BIDS raw dataset。

```text
fifdata/
  dataset_description.json
  participants.tsv
  participants.json
  sub-001/
    ses-01/
      eeg/
        sub-001_ses-01_task-rest_run-01_raw.fif
        sub-001_ses-01_task-rest_run-01_eeg.json
        sub-001_ses-01_task-rest_run-01_channels.tsv
        sub-001_ses-01_task-rest_run-01_events.tsv
        sub-001_ses-01_task-rest_run-01_import.json
  .elys/
    recordings/
      5f9d6e77-xxxx.json
    curation-log.jsonl
```

### 4.1 fifdata 中允许的导入校正

这些操作属于“导入校正”，可以发生在 `fifdata/`：

| 操作                | 是否允许 | 说明                                  |
| ----------------- | :--: | ----------------------------------- |
| 通道重命名             |   是  | 例如 `FP1` 改为 `Fp1`                   |
| 通道类型修正            |   是  | 例如 `MISC` 改为 `EOG`                  |
| 单位缩放确认            |   是  | 必须记录原始单位和缩放                         |
| montage/定位配置      |   是  | 记录来源模板或上传坐标                         |
| trigger/event 增删改 |   是  | 必须保留事件来源和审计日志                       |
| 坏通道标记             |   是  | 可作为导入质控元数据                          |
| 滤波、重参考、ICA、去伪迹    |   否  | 属于 preprocessing，应写入 `derivatives/` |

### 4.2 版本策略

`fifdata/` 不是原始历史仓库。当前 v1 采用“当前工作 FIF”策略：同一数据位重传时，`source_uploads` 保留多个上传版本，`fifdata` 在新 FIF 转换成功后替换当前工作文件。

| 层 | 版本含义 |
| --- | --- |
| `source_uploads` | `upload-001/002/003` 是原始上传历史 |
| `dataset_uploads` | 记录 `upload_seq`、source files、checksum、current/replaced 状态 |
| `fifdata` | 当前可分析 FIF，不保存所有历史工作文件 |

后续如需要回滚某个历史 FIF，可从对应 `source_uploads/upload-###` 重新生成，或再增加独立 FIF 历史版本表。

示例 metadata：

```json
{
  "datasetId": "5f9d6e77-xxxx",
  "currentUploadSeq": 2,
  "sourceFiles": [
    "source_uploads/sub-001/ses-01/task-rest/run-01/upload-002/files/S01/rest/sub001.vhdr",
    "source_uploads/sub-001/ses-01/task-rest/run-01/upload-002/files/S01/rest/sub001.vmrk",
    "source_uploads/sub-001/ses-01/task-rest/run-01/upload-002/files/S01/rest/sub001.eeg"
  ],
  "fifPath": "fifdata/sub-001/ses-01/eeg/sub-001_ses-01_task-rest_run-01_raw.fif",
  "entities": {
    "subject": "sub-001",
    "session": "ses-01",
    "task": "task-rest",
    "run": "run-01"
  },
  "activeUploadSeq": 2,
  "curationStatus": "curated"
}
```

## 5. derivatives

`derivatives/` 只存系统 pipeline 结果，不接受用户上传。

```text
derivatives/
  preprocessing/
    pipeline_00001/
      pipeline_meta.json
      sub-001/
        ses-01/
          eeg/
            sub-001_ses-01_task-rest_run-01_desc-filtered_raw.fif
            sub-001_ses-01_task-rest_run-01_desc-ica_raw.fif
```

边界：

| 层              | 内容            |
| -------------- | ------------- |
| `source_uploads/`     | 原始上传文件        |
| `fifdata/` | 导入标准化后的初始处理数据 |
| `derivatives/` | 预处理和分析结果      |

## 6. bids_exports

当用户需要官方 BIDS 数据集时，系统生成：

```text
bids_exports/
  export-20260515-0001/
    dataset_description.json
    README
    participants.tsv
    sub-001/
      ses-01/
        eeg/
          sub-001_ses-01_task-rest_run-01_eeg.vhdr
          sub-001_ses-01_task-rest_run-01_eeg.vmrk
          sub-001_ses-01_task-rest_run-01_eeg.eeg
          sub-001_ses-01_task-rest_run-01_eeg.json
          sub-001_ses-01_task-rest_run-01_channels.tsv
          sub-001_ses-01_task-rest_run-01_events.tsv
```

说明：

- 如果原始就是 BrainVision/EDF/BDF，可优先复制/重命名原始文件并补 sidecar。
- 如果原始是 CNT/MFF/GDF/MAT/HDF5/CSV，可从 `fifdata/` 导出 BrainVision 或 EDF，再生成 BIDS。
- BIDS Validator 只对 `bids_exports/export-<id>/` 运行。

## 7. 数据库对应关系

现有表可复用，但建议强化 import 和 FIF 版本。

| 表                      | 作用                  |
| ---------------------- | ------------------- |
| `projects`             | 项目和根目录              |
| `subjects`             | 被试索引                |
| `datasets`             | active recording 索引 |
| `pipeline_definitions` | 工作流定义               |
| `dataset_derivatives`  | 系统生成结果              |
| `analysis_results`     | 分析结果                |

建议新增或明确：

| 表                    | 作用                          |
| -------------------- | --------------------------- |
| `import_jobs`        | 一次上传/导入流程                   |
| `import_files`       | 原始文件、checksum、相对路径          |
| `recording_imports`  | source group 到 dataset 的映射  |
| `dataset_uploads`    | v1 已实现，记录每个数据集的原始上传版本和当前版本 |
| `fif_versions`       | 后续可选，保存 FIF 文件历史、active 状态、生成参数 |
| `curation_events`    | 通道、montage、trigger 等导入校正日志  |
| `validation_reports` | import/FIF/BIDS export 验证报告 |

## 8. 增量上传解决方案

增量上传的核心不是文件夹扫描，而是数据库唯一性和 job 隔离。

### 8.1 保存策略

每次上传都保存到新目录：

```text
source_uploads/sub-*/[ses-*]/task-*/run-*/upload-###/files/
```

所以即使用户再次上传同一个 `sub001.edf` 或同一组 BrainVision 三件套，也不会覆盖旧原始文件。

### 8.2 记录唯一性

业务唯一键建议为：

```text
project_id + subject + session + task + run + acquisition(optional)
```

数据库同时保存 `dataset_id`。真正处理时推荐使用 `dataset_id`，UI 展示时使用 BIDS entities。

### 8.3 冲突策略

| 冲突                   | 默认行为             | 可选行为              |
| -------------------- | ---------------- | ----------------- |
| checksum 完全相同        | 提示重复上传           | 跳过、复用、仍导入为副本      |
| 同一 BIDS entities 已存在 | 阻止提交             | 自动建议下一个 run       |
| 用户确认是同数据位重传          | 新建 `dataset_uploads` 版本 | 新 FIF 成功后替换当前 `fifdata` |
| 原始文件名相同但内容不同         | 允许保存             | 必须重新映射            |
| 批量上传部分冲突             | 非冲突先提交           | 冲突项进入待处理          |

### 8.4 fifdata 路径冲突

`fifdata/` 中同一个 active recording 不允许两个文件占用同一实体路径。处理方式：

1. 如果是实验设计中的新重复，应使用新的 `run`，例如 `run-02`。
2. 如果是同一数据位重采或修订，保留同一实体，新增 `upload-###`。
3. 如果 checksum 完全相同，阻止重复生成新的 FIF。

## 9. Validator 目标

| 验证                | 目标                                                |
| ----------------- | ------------------------------------------------- |
| Import validation | `source_uploads/.../upload-###/` 和用户 mapping           |
| FIF validation    | `fifdata/` 中新生成的 FIF、channels、events、metadata |
| BIDS Validator    | `bids_exports/export-<id>/`                       |

示例：

```bash
bids-validator /mnt/elys_data/projects/202605000001/bids_exports/export-20260515-0001 --json
```

## 10. 与当前 v1 存储的差异

| 项              | 当前 v1         | 新方案                        |
| -------------- | ------------- | -------------------------- |
| `rawdata/`     | 近似 BIDS raw   | 改为 `source_uploads/` 原始上传归档 |
| `rawdata_fif/` | 内部工作副本        | 改为 `fifdata/` 全系统处理起点      |
| `sourcedata/`  | source 归档     | 取消，由 `source_uploads/` 承担 |
| validator      | 面向 `rawdata/` | 面向 `bids_exports/`         |
| 增量上传           | 容易和 BIDS 路径耦合 | `dataset_uploads` 上传版本 + 数据库唯一性     |


