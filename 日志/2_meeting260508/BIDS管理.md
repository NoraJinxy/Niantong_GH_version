# BIDS 管理总方案：原始归档 + FIF 处理起点

> 更新日期：2026-05-15  
> 适用范围：念析项目管理、EEG 原始数据上传、FIF 导入、行为数据、项目/实验范式描述。  
> 明确不支持：DICOM、NIfTI、MRI/fMRI、用户上传 derivatives、用户上传预处理结果、EEGLAB `.set/.fdt`、用户上传 `.fif` 作为原始数据。

本文档是 `2_meeting260508` 中 BIDS 相关文档的总入口。完整方案见：

- [BIDS管理-EEG原始数据可行性方案.md](BIDS管理-EEG原始数据可行性方案.md)
- [BIDS管理-EEG原始数据开发实现方案.md](BIDS管理-EEG原始数据开发实现方案.md)
- [BIDS管理-数据上传流程.md](BIDS管理-数据上传流程.md)
- [BIDS管理-存储架构.md](BIDS管理-存储架构.md)
- [BIDS管理-技术实现步骤.md](BIDS管理-技术实现步骤.md)
- [BIDS管理-兼容格式与导入策略.md](BIDS管理-兼容格式与导入策略.md)

## 1. 新的核心定位

念析不再把 `source_uploads/` 设计为官方 EEG-BIDS raw dataset。新的定位是：

| 目录 | 定位 | 是否可改 | 是否作为系统处理起点 |
|------|------|:--:|:--:|
| `source_uploads/` | 用户原始上传归档，保留原始文件和相对路径 | 否 | 否 |
| `fifdata/` | 系统生成的 FIF 标准化处理起点 | 可通过导入校正流程改 | 是 |
| `derivatives/` | 预处理、分析、统计、图表等系统结果 | 系统写入 | 否 |
| `bids_exports/` | 按需生成的官方 BIDS 导出目录 | 系统生成 | 否 |

这个调整的含义：

1. `source_uploads/` 只保存用户上传的原始材料，不再强行改名、移动成 BIDS 结构，也不再作为 BIDS Validator 的目标。
2. `fifdata/` 是平台所有后续操作的统一入口，后续预览、质控、预处理、分析都从 FIF 读取。
3. 通道名修正、定位配置、trigger 添删改等“导入校正”发生在 `fifdata/`，但必须记录版本和审计日志。
4. 因为 FIF 不是官方 EEG-BIDS raw 主格式，`fifdata/` 只能称为 **BIDS 实体命名的 ELYS-FIF 工作数据集**，不能称为官方 BIDS raw dataset。
5. 如果需要论文、共享或对外交付的 BIDS 数据集，系统从 `source_uploads/` 原始文件和 `fifdata/` 元数据生成 `bids_exports/export-<id>/`，再运行 BIDS Validator。

## 2. 格式策略

仍然保留两层导入策略：原始文件统一保存到 `source_uploads/`，导入结果统一写入 `fifdata/`。

| 类别 | 格式 | 原始文件保存 | 导入目标 | 处理策略 |
|------|------|------|------|------|
| 标准原始上传 | BrainVision `.vhdr/.vmrk/.eeg` | `source_uploads/sub-*/[ses-*]/task-*/run-*/upload-###/files/` | `fifdata/` | 直接读取三件套，生成 FIF、channels、events、metadata |
| 标准原始上传 | EDF / EDF+ `.edf` | `source_uploads/sub-*/[ses-*]/task-*/run-*/upload-###/files/` | `fifdata/` | 读取 header、annotations/trigger 通道，生成 FIF |
| 标准原始上传 | BioSemi BDF / BDF+ `.bdf` | `source_uploads/sub-*/[ses-*]/task-*/run-*/upload-###/files/` | `fifdata/` | 重点检查 `Status`/trigger 通道 |
| 高级格式导入 | CNT / MFF / GDF | `source_uploads/sub-*/[ses-*]/task-*/run-*/upload-###/files/` | `fifdata/` | 先进入 import staging，确认 reader、通道、trigger 后生成 FIF |
| 高级格式导入 | MAT / HDF5 / CSV/TSV/TXT | `source_uploads/sub-*/[ses-*]/task-*/run-*/upload-###/files/` | `fifdata/` | 只接受模板化矩阵和明确元数据，生成 FIF |
| 行为/事件/范式文件 | CSV/TSV/XLSX/JSON/TXT/MD | `source_uploads/sub-*/[ses-*]/task-*/run-*/upload-###/files/` | `fifdata/` 元数据表 | 映射为 events、beh、phenotype、README/task 描述 |
| 拒收 | `.set/.fdt` | 不入库 | 不生成 | 提示转 EDF/BDF/BrainVision 或走后续专用转换 |
| 拒收 | 用户上传 `.fif` | 不入库 | 不生成 | FIF 只能由系统导入流程生成 |
| 拒收 | DICOM/NIfTI/derivatives/预处理结果 | 不入库 | 不生成 | 本阶段不接入 |

## 3. 推荐目录

```text
/mnt/elys_data/projects/202605000001/
  .elys_project.json
  source_uploads/
    sub-001/
      ses-01/
        task-rest/
          run-01/
            upload-001/
              files/               # 原始上传文件，保留用户相对路径
                S01/rest/sub001.vhdr
                S01/rest/sub001.vmrk
                S01/rest/sub001.eeg
              manifest.json
            upload-002/            # 同一数据位重传后的历史版本
  fifdata/
    dataset_description.json       # ELYS-FIF 工作数据集描述，不等于官方 BIDS raw
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
        <dataset_id>.json
      curation-log.jsonl
  derivatives/
  pipeline/
  validation/
  upload_staging/
  bids_exports/
```

不再单独设置 `sourcedata/`。因为 `source_uploads/` 本身就是 source archive，再放一层 `sourcedata/` 会语义重复。

## 4. BIDS 在此方案中的角色

BIDS 仍然有价值，但角色变化为：

| 层面 | 使用方式 |
|------|------|
| 命名和索引 | `fifdata/` 使用 `sub/ses/task/run` 等 BIDS entities |
| 元数据 | 继续维护 `participants.tsv`、`*_channels.tsv`、`*_events.tsv`、`*_eeg.json` |
| 官方验证 | 不验证 `source_uploads/`，也不验证 `fifdata/`；只验证 `bids_exports/export-<id>/` |
| 对外交付 | 按需从原始文件和 FIF 元数据生成官方 EEG-BIDS 导出 |

关键提醒：官方 EEG-BIDS raw 主文件不包含 `.fif`，所以 `fifdata/` 不能作为 `bids-validator` 的目标。它是系统内部的标准处理数据集，而不是官方 BIDS raw dataset。

## 5. 增量上传原则

增量上传不能靠扫描 `source_uploads/` 目录决定文件放哪里，必须靠数据库记录。v1 使用 `dataset_uploads` 管理上传版本；后续异步化后可再引入完整 `import_jobs`。

流程：

```text
新上传 -> 根据 subject/session/task/run 计算数据位 -> 保存到 source_uploads/.../upload-###/files/
       -> 生成 manifest -> 用户映射 sub/ses/task/run
       -> 检查是否与已有 recording 冲突
       -> 生成或更新 fifdata/ 中的 FIF 记录
```

冲突处理策略：

| 场景 | 建议处理 |
|------|------|
| 完全相同 checksum | 提示重复上传，可跳过或关联已有文件 |
| 同一 subject/session/task/run 已存在 | 返回 `DATASET_EXISTS`，前端弹窗确认 |
| 确认为同一 recording 的重传 | 新增 `dataset_uploads.upload_seq`，新 FIF 成功后替换当前 `fifdata` |
| 新 session/task/run | 直接新增 recording |
| 原始文件名相同但内容不同 | 因 `upload-###` 隔离，不会覆盖；UI 提示潜在冲突 |

## 6. Validator 策略

平台需要两类验证：

1. **ELYS import validation**：导入提交前必须通过，检查 reader、采样率、通道表、trigger、events、subject/session/task/run 唯一性、FIF 是否可由 MNE 读取。
2. **BIDS export validation**：只有用户需要导出官方 BIDS 数据集时，生成 `bids_exports/export-<id>/` 后运行 `bids-validator`。

示例：

```bash
bids-validator /mnt/elys_data/projects/202605000001/bids_exports/export-20260515-0001 --json
```

## 7. 与 elys_version1 的差异

| 维度 | 当前 `elys_version1` | 新目标 |
|------|------|------|
| `rawdata/` | 近似 BIDS raw 目录 | 改为 `source_uploads/`，只做原始上传归档 |
| `rawdata_fif/` | 内部工作副本/缓存 | 改为 `fifdata/`，作为全系统处理起点 |
| `.fif` 来源 | 上传后同步生成 | 只能由导入流程生成，用户不能上传 |
| BIDS Validator | 计划验证 `rawdata/` | 只验证按需生成的 `bids_exports/` |
| 高级格式 | 先 source 再 BIDS raw | 先 source 再 FIF，必要时再导出 BIDS |
| `sourcedata/` | 高级源文件归档 | 取消，由 `source_uploads/` 承担 |

## 8. 结论

这个改进方案是可行的，而且更贴合一个 Web EEG 分析平台：原始文件永久保留，系统处理入口统一为 FIF，用户的导入校正集中发生在 `fifdata/`。代价是 `source_uploads/` 不再是官方 BIDS dataset，`fifdata/` 也不能被称为官方 BIDS raw。平台需要额外提供 BIDS export 功能，才能在需要共享、投稿或归档时生成可验证的官方 BIDS 数据集。


