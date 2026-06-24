# ELYS v1 BIDS 数据导入与重传版本说明

> 更新日期: 2026-05-15
> 适用目录: `elys_project`

本文档描述当前代码已经实现的 EEG 原始数据导入、`source_uploads` 归档、`fifdata` 工作数据和同数据位重传策略。

## 1. 项目根目录

部署后项目数据根目录默认是：

```text
/mnt/elys_data/projects/{project_id}/
```

`project_id` 是 12 位数字，前 6 位为年月 `YYYYMM`，后 6 位为当月序号，例如：

```text
202605000001
```

项目创建后会初始化：

```text
.elys_project.json
source_uploads/
fifdata/
upload_staging/
validation/
derivatives/preprocessing/
pipeline/
bids_exports/
```

## 2. 当前支持格式

| 格式 | 前端选择 | 后端行为 |
|---|---|---|
| BrainVision | 同名 `.vhdr/.eeg/.vmrk` 三件套 | 读取 `.vhdr`，生成 FIF |
| EDF / EDF+ | 单个 `.edf` | 读取原始文件，生成 FIF |
| BDF / BDF+ | 单个 `.bdf` | 读取原始文件，生成 FIF |

暂不接受：

- `.fif`：只能由系统生成。
- `.set/.fdt`：请先转换为 EDF/BDF/BrainVision。
- CNT/MFF/GDF/MAT/HDF5/CSV/TSV：后续进入高级导入流程。
- DICOM/NIfTI/MRI、derivatives、用户预处理结果。

## 3. source_uploads 与 fifdata

`source_uploads` 保存原始上传历史，`fifdata` 保存当前可分析工作数据。

```text
source_uploads/
  sub-093/
    task-rest/
      run-none/
        upload-001/
          manifest.json
          files/
            sub093.vhdr
            sub093.eeg
            sub093.vmrk

fifdata/
  sub-093/
    eeg/
      sub-093_task-rest_raw.fif
      sub-093_task-rest_eeg.json
      sub-093_task-rest_channels.tsv
      sub-093_task-rest_events.tsv
      sub-093_task-rest_import.json
```

有 session/run 时：

```text
source_uploads/sub-093/ses-01/task-rest/run-02/upload-001/
fifdata/sub-093/ses-01/eeg/sub-093_ses-01_task-rest_run-02_raw.fif
```

## 4. 同数据位重传

同一 `subject/session/task/run` 已存在时，后端第一次返回：

```json
{
  "detail": {
    "code": "DATASET_EXISTS",
    "message": "该数据位已经存在，可以作为新上传版本替换当前 FIF 工作数据。",
    "current_upload_seq": 1
  }
}
```

前端弹窗确认后，重新提交：

```text
replace_existing=true
```

后端执行：

1. 写入新的 `source_uploads/.../upload-###`。
2. 在临时路径生成新 FIF 和 sidecar。
3. MNE 重新读取验证新 FIF。
4. 成功后替换 `fifdata` 当前工作文件。
5. 写入 `dataset_uploads`，更新 `datasets.current_upload_id`。

如果转换失败，数据库回滚，旧 FIF 继续保留。

## 5. 数据库表

当前列表和后续分析以 `datasets` 为准：

```text
datasets.source_path
datasets.fif_path
datasets.current_upload_id
datasets.checksum
datasets.qa_status
```

上传历史在 `dataset_uploads`：

```text
dataset_uploads.dataset_id
dataset_uploads.upload_seq
dataset_uploads.source_dir
dataset_uploads.source_main_file
dataset_uploads.source_files
dataset_uploads.status
dataset_uploads.checksum
dataset_uploads.uploaded_at
```

## 6. 前端行为

- 单个数据：EDF/BDF 选 1 个文件；BrainVision 需要一次框选同名 3 个文件。
- 批量文件夹：选择或拖拽文件夹，前端自动扫描多组 EDF/BDF 和 BrainVision。
- 上传进度到 95% 后进入服务器归档、FIF 转换和数据库写入阶段。
- 同数据位已存在时弹窗确认，不要求用户临时改 `run`。

## 7. 运维 SQL

查看当前数据集：

```sql
SELECT
  d.id,
  s.bids_subject_id,
  d.session,
  d.task,
  d.run,
  d.source_path,
  d.fif_path,
  du.upload_seq AS current_upload_seq,
  d.imported_at
FROM datasets d
JOIN subjects s ON s.id = d.subject_id
LEFT JOIN dataset_uploads du ON du.id = d.current_upload_id
WHERE d.project_id = '202605000001'
ORDER BY d.imported_at DESC;
```

查看某个数据集历史上传：

```sql
SELECT
  upload_seq,
  status,
  source_dir,
  source_main_file,
  checksum,
  uploaded_at
FROM dataset_uploads
WHERE dataset_id = '<dataset_id>'
ORDER BY upload_seq;
```

## 8. BIDS 边界

`source_uploads` 和 `fifdata` 都不是官方 EEG-BIDS raw dataset，不能直接作为 BIDS Validator 目标。后续需要共享、投稿或归档时，由系统生成：

```text
bids_exports/export-<export_id>/
```

再运行 BIDS Validator。
