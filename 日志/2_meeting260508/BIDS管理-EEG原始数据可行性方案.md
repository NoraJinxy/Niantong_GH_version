# EEG 原始数据导入到 FIF 的可行性方案

> 更新日期：2026-05-15  
> 目标：用户可以批量上传 EEG 原始数据、行为数据和项目/范式描述；平台保留原始文件，并生成统一的 FIF 处理起点。  
> 边界：不接入 DICOM、NIfTI、用户上传 derivatives、用户上传预处理结果；不接受 `.set/.fdt` 和用户上传 `.fif`。

## 1. 方案判断

用户提出的改进是可行的，而且更适合一个以在线处理和分析为核心的 EEG Web 平台。

推荐方案：

```text
source_uploads/      保存用户原始上传文件，不改、不覆盖、不强行 BIDS 化
fifdata/  保存系统导入后生成的 FIF，作为后续所有处理的初始数据
derivatives/  保存预处理、分析、图表等 pipeline 结果
bids_exports/ 按需生成官方 BIDS 数据集
```

关键结论：

1. `source_uploads/` 可以不按照官方 BIDS 组织；v1 按数据位和 `upload-###` 保存原始文件历史。
2. `fifdata/` 可以按照 BIDS entities 组织，例如 `sub/ses/task/run`，但它不是官方 EEG-BIDS raw dataset。
3. FIF 是系统处理格式，不是用户上传格式。
4. `sourcedata/` 没有必要单独存在，因为 `source_uploads/` 本身就是 source archive。
5. 增量上传必须通过 checksum、数据库唯一性和冲突处理来解决；v1 使用 `dataset_uploads`，后续可扩展完整 import job。

## 2. 利弊分析

### 2.1 优点

| 优点 | 说明 |
|------|------|
| 原始数据真正不可变 | 用户上传什么就保存什么，便于审计、追责和重新导入 |
| 处理入口统一 | 后续预览、质控、预处理、分析都读 FIF，避免每个模块重复兼容 CNT/MFF/GDF/MAT |
| 适合复杂格式 | CNT/MFF/GDF/MAT/HDF5/CSV 都可以先导入为 FIF，再进入统一流程 |
| 导入校正更自然 | 通道名、montage、trigger、events 可以在 FIF 层被修正并记录 |
| 增量上传更稳 | 原始文件按 `upload-###` 隔离，不会因文件名相同而覆盖 |

### 2.2 代价

| 代价 | 解决方案 |
|------|------|
| `source_uploads/` 不再是 BIDS dataset | 明确文档口径：`source_uploads/` 是原始归档 |
| `fifdata/` 不能跑官方 BIDS Validator | 只称为 ELYS-FIF 工作数据集；BIDS Validator 只用于 `bids_exports/` |
| 需要更强的数据库索引 | v1 用 `datasets/dataset_uploads` 管理当前数据和上传历史；后续再补 `import_jobs/fif_versions/curation_events` |
| 导入校正可能改变语义 | 所有通道、montage、trigger 修改都记录审计日志和版本 |
| 对外交付 BIDS 多一步 | 提供 BIDS export 功能，从原始文件和 FIF 元数据生成官方 BIDS |

## 3. 支持范围

### 3.1 标准原始上传

这些格式可以较少人工干预地导入为 FIF：

| 格式 | 原始保存位置 | FIF 生成 | 关键校验 |
|------|------|------|------|
| BrainVision `.vhdr/.vmrk/.eeg` | `source_uploads/sub-*/[ses-*]/task-*/run-*/upload-###/files/` | 是 | 三件套完整、`.vhdr` 引用、marker |
| EDF / EDF+ `.edf` | `source_uploads/sub-*/[ses-*]/task-*/run-*/upload-###/files/` | 是 | annotations、trigger/status 通道、采样率 |
| BioSemi BDF / BDF+ `.bdf` | `source_uploads/sub-*/[ses-*]/task-*/run-*/upload-###/files/` | 是 | `Status` 通道、bit mask、事件码 |

### 3.2 高级格式导入

这些格式进入 import staging，需要用户确认元数据后生成 FIF：

| 格式 | 风险 | 必须确认 |
|------|------|------|
| Neuroscan CNT `.cnt` | 和 ANT 同扩展名 | Neuroscan/Curry reader、trigger |
| ANT / EEProbe CNT `.cnt` | 和 Neuroscan 同扩展名 | ANT/EEProbe/eego reader、trigger |
| EGI / Net Station `.mff` | 目录包完整性 | 事件来源、EGI montage、通道名 |
| GDF `.gdf` | BCI 事件编码不统一 | event channel、单位、通道类型 |
| MATLAB `.mat` | 自由结构太多 | 一个变量、二维 `time x channel`、采样率、通道 |
| HDF5 `.h5/.hdf5` | 私有 schema | 只接受平台 schema |
| CSV/TSV/TXT | 元数据缺失 | 只接受矩阵模板或作为行为/events 表 |

## 4. 导入校正范围

`fifdata/` 是处理起点，因此允许在导入阶段做必要校正。

| 校正 | 允许 | 存储 |
|------|:--:|------|
| 通道重命名 | 是 | `channels.tsv`、curation log、FIF info |
| 通道类型修正 | 是 | `channels.tsv`、FIF info |
| montage/电极位置配置 | 是 | `*_eeg.json`、FIF montage |
| trigger 事件新增 | 是 | `events.tsv`、FIF annotations、curation log |
| trigger 事件删除/合并/改码 | 是 | `events.tsv`、curation log |
| 坏通道标记 | 是 | `channels.tsv`、FIF info |
| 滤波、ICA、重参考 | 否 | 进入 `derivatives/` |

原则：导入校正只解决“让原始数据可被正确解释”的问题，不做信号处理。

## 5. 推荐结构

```text
projects/202605000001/
  source_uploads/
    2026/
      05/
        15/
          import-20260515-0001/
            files/
              S01/rest/sub001.vhdr
              S01/rest/sub001.vmrk
              S01/rest/sub001.eeg
              S01/rest/log.csv
            upload-manifest.json
            checksums.tsv
            user-mapping.json
            import-report.json
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
  derivatives/
  pipeline/
  validation/
  upload_staging/
  bids_exports/
```

## 6. 增量上传方案

### 6.1 原始文件如何放置

每次有效上传都新建上传版本：

```text
source_uploads/sub-*/[ses-*]/task-*/run-*/upload-###/files/
```

这样用户上传的目录结构可以原样保存，不会因为已有 `source_uploads/` 内容而不知道放哪里。

### 6.2 如何确定新数据属于谁

不能靠文件夹名自动决定，必须通过 manifest 和用户映射：

```text
source group -> subject/session/task/run -> dataset_id -> fifdata path
```

示例：

```json
{
  "groupId": "g001",
  "sourceFiles": [
    "source_uploads/sub-001/ses-01/task-rest/run-01/upload-001/files/S01/rest/sub001.vhdr",
    "source_uploads/sub-001/ses-01/task-rest/run-01/upload-001/files/S01/rest/sub001.vmrk",
    "source_uploads/sub-001/ses-01/task-rest/run-01/upload-001/files/S01/rest/sub001.eeg"
  ],
  "entities": {
    "subject": "sub-001",
    "session": "ses-01",
    "task": "task-rest",
    "run": "run-01"
  }
}
```

### 6.3 冲突处理

| 冲突 | 处理 |
|------|------|
| checksum 已存在 | 提示重复，可跳过或复用 |
| `sub/ses/task/run` 已存在 | 返回 `DATASET_EXISTS`，用户确认后作为同数据位重传 |
| 用户确认重传 | 不覆盖原始文件；新增 `dataset_uploads.upload_seq`，新 FIF 成功后替换当前 `fifdata` |
| 部分文件冲突 | 非冲突记录可提交，冲突记录留在 job 中修复 |
| BrainVision 三件套不完整 | job 可保存，但该 group 不能生成 FIF |

## 7. 验证策略

### 7.1 导入验证

导入提交必须检查：

- 原始文件 checksum。
- 文件分组是否完整。
- reader 是否能读取。
- FIF 是否能生成并重新打开。
- 通道表和数据通道数是否一致。
- events 是否在数据时长范围内。
- `sub/ses/task/run` 是否唯一。
- 用户导入校正是否有审计记录。

### 7.2 BIDS 验证

BIDS Validator 不再验证 `source_uploads/` 或 `fifdata/`。只有导出官方 BIDS 时才运行：

```bash
bids-validator /mnt/elys_data/projects/202605000001/bids_exports/export-20260515-0001 --json
```

## 8. 最小可上线版本

MVP 建议：

1. `source_uploads/.../upload-###/` 原始归档。
2. BrainVision/EDF/BDF 导入生成 FIF。
3. `fifdata/` 按 `sub/ses/task/run` 组织。
4. 支持通道名、通道类型、montage、trigger/events 的导入校正。
5. 增量上传冲突检查。
6. 拒收 `.set/.fdt/.fif`、derivatives、预处理结果。
7. BIDS export 放到后续迭代。

后续增强：

- CNT/MFF/GDF 高级导入。
- MAT/HDF5/CSV 矩阵模板。
- 更完整的 FIF 历史版本管理和回滚。
- 官方 BIDS 导出和 validator。

## 9. 结论

把 `source_uploads/` 作为原始归档、把 `fifdata/` 作为全系统处理起点，是一个更工程化、更适合在线 EEG 分析平台的方案。它牺牲了“项目目录天然就是 BIDS dataset”的简单性，但换来了原始数据不可变、处理格式统一、增量上传可控和高级格式兼容能力。v1 已先落地 `dataset_uploads` 上传版本；后续需要继续补齐异步 import job、FIF 历史版本、导入校正审计、以及按需 BIDS export。


