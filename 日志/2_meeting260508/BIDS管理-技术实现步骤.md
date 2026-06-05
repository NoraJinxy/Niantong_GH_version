# BIDS 管理：原始归档与 FIF 导入技术实现步骤

> 更新日期：2026-05-15  
> 配套文档：[BIDS管理.md](BIDS管理.md)、[BIDS管理-数据上传流程.md](BIDS管理-数据上传流程.md)、[BIDS管理-存储架构.md](BIDS管理-存储架构.md)  
> 工程基线：`elys_version1`

## 0. 实现目标

1. `source_uploads/` 只保存原始上传文件，v1 按数据位和 `upload-###` 归档，不强行 BIDS 化。
2. `fifdata/` 保存系统生成的 FIF，作为后续所有处理的初始数据。
3. CNT/MFF/GDF/MAT/HDF5/CSV 作为高级 source 进入 import staging，最终输出 FIF。
4. 拒收 `.set/.fdt/.fif`、DICOM、NIfTI、derivatives、预处理结果。
5. 通道名、montage、trigger/events 的导入校正发生在 `fifdata/`，并记录审计日志。
6. BIDS Validator 只用于 `bids_exports/`，不用于 `source_uploads/` 或 `fifdata/`。

> v1 当前已落地的同步导入实现使用 `dataset_uploads` 管理上传版本：`source_uploads/sub-*/[ses-*]/task-*/run-*/upload-###/` 保存原始历史，`fifdata/` 保存当前工作 FIF。独立 `import_jobs`、分片续传、异步任务和完整 `fif_versions` 表仍属于后续阶段。

## 阶段 1：目录和格式边界

### Step 1.1 修改项目目录创建

文件：

```text
elys_version1/backend/app/routers/projects.py
```

目标目录：

```python
def create_project_directories(project: Project) -> None:
    root = Path(project.bids_root)
    for relative in (
        "source_uploads",
        "fifdata",
        "derivatives/preprocessing",
        "pipeline",
        "validation",
        "uploads",
        "bids_exports",
    ):
        (root / relative).mkdir(parents=True, exist_ok=True)
```

不再在 `source_uploads/` 下写 `dataset_description.json`、`participants.tsv` 等 BIDS 文件。

### Step 1.2 修改上传格式分类

文件：

```text
elys_version1/backend/app/routers/datasets.py
```

```python
STANDARD_SOURCE_EXTENSIONS = {
    ".edf",
    ".bdf",
    ".vhdr",
    ".eeg",
    ".vmrk",
}

ADVANCED_SOURCE_EXTENSIONS = {
    ".cnt",
    ".mff",
    ".gdf",
    ".mat",
    ".h5",
    ".hdf5",
    ".csv",
    ".tsv",
    ".txt",
}

REJECTED_EXTENSIONS = {
    ".set": "暂不接受 EEGLAB .set，请转换为 EDF/BDF/BrainVision 后上传。",
    ".fdt": "暂不接受 EEGLAB .fdt，请转换为 EDF/BDF/BrainVision 后上传。",
    ".fif": "FIF 只能由系统导入流程生成，不接受用户直接上传。",
}
```

验收：

```text
BrainVision/EDF/BDF：进入 standard-source
CNT/MFF/GDF/MAT/HDF5/CSV：进入 advanced-source 或 behavior-source
SET/FDT/FIF：422
```

## 阶段 2：上传版本和原始归档

v1 同步导入先使用 `dataset_uploads` 管理上传版本。完整 `import_jobs/import_files` 适合后续异步任务、分片续传和失败恢复。

### Step 2.1 后续异步导入表

```sql
CREATE TABLE IF NOT EXISTS import_jobs (
    id              VARCHAR(64) PRIMARY KEY,
    project_id      CHAR(12) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    created_by      UUID REFERENCES users(id),
    status          VARCHAR(32) NOT NULL DEFAULT 'draft',
    manifest_json   JSONB NOT NULL DEFAULT '{}',
    mapping_json    JSONB NOT NULL DEFAULT '{}',
    archive_path    TEXT,
    error           TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    committed_at    TIMESTAMP
);

CREATE TABLE IF NOT EXISTS import_files (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id          VARCHAR(64) NOT NULL REFERENCES import_jobs(id) ON DELETE CASCADE,
    relative_path   TEXT NOT NULL,
    stored_path     TEXT NOT NULL,
    extension       VARCHAR(16) NOT NULL,
    file_size       BIGINT,
    checksum        VARCHAR(64),
    detected_kind   VARCHAR(64),
    group_key       TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### Step 2.2 保存原始文件

新增：

```text
elys_version1/backend/app/services/eeg_import/raw_archive.py
```

保存路径：

```text
source_uploads/sub-<label>/[ses-<label>/]task-<label>/<run-<label>|run-none>/upload-###/files/<user-relative-path>
```

必须写：

```text
upload-manifest.json
checksums.tsv
user-mapping.json
import-report.json
```

### Step 2.3 安全要求

- 禁止路径穿越。
- 同一 `upload-###` 或同一 job 内同路径文件不能静默覆盖。
- 已 committed 的 raw archive 只读。
- checksum 相同要提示重复上传。

## 阶段 3：生成 fifdata

### Step 3.1 新增 FIF writer

新增：

```text
elys_version1/backend/app/services/eeg_import/fif_writer.py
```

输出：

```text
fifdata/sub-001/ses-01/eeg/
  sub-001_ses-01_task-rest_run-01_raw.fif
  sub-001_ses-01_task-rest_run-01_eeg.json
  sub-001_ses-01_task-rest_run-01_channels.tsv
  sub-001_ses-01_task-rest_run-01_events.tsv
  sub-001_ses-01_task-rest_run-01_import.json
```

### Step 3.2 标准格式 reader

保留：

```python
brainvision -> mne.io.read_raw_brainvision
.edf -> mne.io.read_raw_edf
.bdf -> mne.io.read_raw_bdf
```

生成 FIF 后必须重新读取验证：

```python
raw.save(fif_path, overwrite=False)
mne.io.read_raw_fif(fif_path, preload=False)
```

### Step 3.3 fifdata metadata

首次导入时创建：

```text
fifdata/dataset_description.json
fifdata/participants.tsv
fifdata/participants.json
fifdata/.elys/recordings/
fifdata/.elys/curation-log.jsonl
```

`dataset_description.json` 不写 `BIDSVersion`，改写：

```json
{
  "DatasetKind": "ELYS-FIF",
  "BIDSLikeEntities": true
}
```

## 阶段 4：增量上传和冲突处理

### Step 4.1 唯一键

业务唯一键：

```text
project_id + subject + session + task + run + acquisition(optional)
```

如果冲突：

| 场景 | 处理 |
|------|------|
| 新数据应独立存在 | 使用实验设计中真实的新 `run/session/task` |
| 新数据是同一数据位重传 | v1 新建 `dataset_uploads` 版本，新 FIF 成功后替换当前 `fifdata` |
| checksum 已存在 | 提示重复，可跳过 |

### Step 4.2 v1 已实现的上传版本表

当前代码已实现 `dataset_uploads`，用于记录同一 `datasets` 当前数据位下的历次原始上传：

```sql
CREATE TABLE IF NOT EXISTS dataset_uploads (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id       UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    upload_seq       INTEGER NOT NULL,
    source_dir       VARCHAR(512) NOT NULL,
    source_main_file VARCHAR(512) NOT NULL,
    source_files     JSONB NOT NULL DEFAULT '[]',
    source_format    VARCHAR(16) NOT NULL,
    file_size        BIGINT,
    checksum         VARCHAR(64),
    status           VARCHAR(16) NOT NULL DEFAULT 'current',
    qa_status        VARCHAR(16) NOT NULL DEFAULT 'converted',
    note             TEXT,
    uploaded_by      UUID REFERENCES users(id),
    uploaded_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
```

`datasets.current_upload_id` 指向当前上传版本。同一 `subject/session/task/run` 重新上传时，前端先收到 `DATASET_EXISTS`，用户确认后带 `replace_existing=true`，后端新增 `upload_seq` 并在 FIF 转换成功后替换当前 `fifdata`。

### Step 4.3 后续可选 FIF 版本表

```sql
CREATE TABLE IF NOT EXISTS fif_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id      UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    version         INTEGER NOT NULL,
    fif_path        TEXT NOT NULL,
    metadata_json   JSONB NOT NULL DEFAULT '{}',
    is_active       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### Step 4.4 datasets 字段

建议补充：

```text
current_upload_id
source_file_paths
active_fif_path
current_upload_seq
import_status
curation_status
```

短期可先用现有 `source_path/fif_path/qa_report` 承载，但文档和 UI 口径要改为：

```text
source_path = source_uploads/.../upload-###/files/...
fif_path = fifdata 中 active FIF
```

## 阶段 5：导入校正

新增：

```text
elys_version1/backend/app/services/eeg_import/curation.py
```

允许操作：

- rename channels
- set channel types
- set montage
- mark bad channels
- edit annotations/events
- update trigger mapping

不允许操作：

- filter
- ICA
- rereference
- epoch
- feature extraction

这些进入 preprocessing/derivatives。

### Step 5.1 审计表

```sql
CREATE TABLE IF NOT EXISTS curation_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id      UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    fif_version_id  UUID REFERENCES fif_versions(id) ON DELETE SET NULL,
    event_type      VARCHAR(64) NOT NULL,
    payload_json    JSONB NOT NULL,
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
```

## 阶段 6：高级格式导入

### Step 6.1 readers

```python
ADVANCED_READERS = {
    "cnt-neuroscan": "mne.io.read_raw_cnt",
    "cnt-ant": "mne.io.read_raw_ant",
    "egi-mff": "mne.io.read_raw_egi",
    "gdf": "mne.io.read_raw_gdf",
}
```

CNT 必须让用户选择来源，不能只靠 `.cnt` 自动判断。

### Step 6.2 矩阵类 source

MAT/HDF5/CSV 只接受：

```text
shape = [n_times, n_channels]
sampling_frequency required
channel_names required
channel_types required
units required
events optional
```

矩阵转 Raw：

```python
raw = mne.io.RawArray(matrix.T, info)
```

## 阶段 7：trigger/events

新增：

```text
elys_version1/backend/app/services/eeg_import/trigger.py
```

必须支持：

- EDF/BDF annotations。
- Status/Trigger/STI 通道。
- bit mask。
- rising/falling edge。
- 外部 events TSV。
- 事件码映射和计数预览。

写入：

```text
fifdata/sub-*/ses-*/eeg/*_events.tsv
FIF annotations
curation_events
```

## 阶段 8：验证

导入验证：

```python
def validate_import(dataset: Dataset) -> ValidationResult:
    # raw archive exists
    # checksum exists
    # FIF exists and can be read
    # channels/events match FIF
    # entity uniqueness or version policy
```

BIDS export 验证：

```python
def run_bids_validator(export_root: Path) -> dict:
    proc = subprocess.run(
        ["bids-validator", str(export_root), "--json"],
        capture_output=True,
        text=True,
        timeout=300,
    )
```

## 阶段 9：BIDS export

新增：

```text
elys_version1/backend/app/services/eeg_import/bids_export.py
```

输出：

```text
bids_exports/export-<export_id>/
  dataset_description.json
  README
  participants.tsv
  sub-001/ses-01/eeg/...
```

规则：

- 原始是 BrainVision/EDF/BDF 时，优先从 `source_uploads/` 复制原始数据并改 BIDS 命名。
- 原始是 CNT/MFF/GDF/MAT/HDF5/CSV 时，可从 `fifdata/` 导出 BrainVision/EDF。
- 由 `fifdata` 中的 channels/events/eeg metadata 生成 sidecar。

## 阶段 10：前端

新增路由：

```text
/projects/:id/import
```

组件：

```text
DataImportView.vue
  FileSelectStep.vue
  RawArchiveStep.vue
  GroupingStep.vue
  MappingStep.vue
  EEGMetadataStep.vue
  ChannelMontageStep.vue
  TriggerEventStep.vue
  FIFPreviewStep.vue
  ValidationStep.vue
  CommitStep.vue
```

## 阶段 11：测试

| 测试 | 期望 |
|------|------|
| 上传 BrainVision 三件套 | source_uploads 原样归档，fifdata 生成 FIF |
| 上传 EDF/BDF | source_uploads 原样归档，fifdata 生成 FIF |
| 上传 `.fif` | 422，提示用户不能上传 FIF |
| 上传 `.set/.fdt` | 422，提示转换 |
| CNT 未选来源 | 不能生成 FIF |
| MAT 多变量 | policy failed |
| 重复 checksum | 提示重复 |
| 重复 sub/ses/task/run | 返回 `DATASET_EXISTS`，确认后新增 `dataset_uploads` 版本并替换当前 FIF |
| trigger 修改 | 写 events.tsv、FIF annotations、curation log |
| 后续处理 | 只从 active FIF 读取 |
| BIDS export | 生成导出目录并 validator 通过或给出错误 |

## 阶段 12：发布顺序

| 顺序 | 内容 | 风险 |
|------|------|------|
| 1 | 原始归档 `source_uploads/` | 低 |
| 2 | BrainVision/EDF/BDF 到 FIF | 中 |
| 3 | 增量上传和冲突处理 | 中 |
| 4 | 通道/trigger 导入校正 | 中高 |
| 5 | 高级格式 CNT/MFF/GDF | 高 |
| 6 | MAT/HDF5/CSV 模板 | 高 |
| 7 | BIDS export | 中 |


