# EEG 原始数据归档与 FIF 导入开发实现方案

> 更新日期：2026-05-15  
> 依据：`elys_version1` 当前 FastAPI + PostgreSQL + Vue 实现、`wiki/601/602/603/407` 设计说明，以及新的 `source_uploads` 原始归档 + `fifdata` 处理起点方案。

## 1. 当前代码基线

`elys_version1` 已有能力：

| 能力 | 位置 | 现状 |
|------|------|------|
| 项目创建 | `backend/app/routers/projects.py` | 创建 `source_uploads/fifdata/derivatives/preprocessing/pipeline` |
| EEG 上传 | `backend/app/routers/datasets.py` | multipart 上传、BrainVision 分组、MNE 转 FIF |
| 前端上传 | `frontend/elys-web/src/views/Dashboard.vue` | 项目卡片内选择文件夹并上传 |
| 数据表 | `database/init.sql` | 已有 `projects/subjects/datasets/dataset_uploads/dataset_derivatives` 等 |

需要调整：

| 当前实现 | 新目标 |
|------|------|
| `source_uploads/` 近似作为 BIDS raw | `source_uploads/` 只做原始上传归档 |
| `fifdata/` 视作工作副本 | `fifdata/` 是全系统处理起点 |
| 上传时写 canonical raw | 上传时归档 source，并生成 FIF |
| BIDS Validator 面向 `source_uploads/` | Validator 面向按需生成的 `bids_exports/` |
| 无上传版本 | v1 已增加 `dataset_uploads`，后续再补 curation 和 FIF version |

## 2. 后端模块划分

建议新增：

```text
backend/app/services/eeg_import/
  __init__.py
  policy.py              # 产品边界：拒收 set/fif/derivatives 等
  detector.py            # 文件识别、BrainVision 三件套、高级 source 分组
  raw_archive.py         # 保存到 source_uploads/sub-*/task-*/run-*/upload-###/
  manifest.py            # manifest/checksum/user mapping
  readers.py             # BrainVision/EDF/BDF/CNT/MFF/GDF reader
  matrix_reader.py       # MAT/HDF5/CSV/TSV/TXT 矩阵模板
  trigger.py             # annotations/status/trigger/event 预览和映射
  fif_writer.py          # 写 fifdata/ FIF 和 sidecar
  curation.py            # 通道、montage、trigger 导入校正
  validation.py          # import validation + FIF validation
  bids_export.py         # 按需生成官方 BIDS export
  jobs.py                # import job 状态机
```

路由：

```text
backend/app/routers/import_jobs.py
backend/app/routers/datasets.py
backend/app/routers/bids_exports.py
```

## 3. 依赖

```text
mne>=1.6,<2.0
numpy>=1.24
scipy>=1.11
h5py>=3.10
pandas>=2.0
openpyxl>=3.1
pybv>=0.7
edfio>=0.4
```

说明：

- `mne` 用于读原始格式并写 FIF。
- `scipy/h5py` 读取 MAT/HDF5。
- `pandas/openpyxl` 处理行为表。
- `pybv/edfio` 用于后续 BIDS export 时导出 BrainVision/EDF。
- BIDS Validator 只在 export 阶段作为独立命令运行。

## 4. 目录创建

项目创建时只需初始化工程目录，不再把 `source_uploads/` 写成 BIDS 骨架。

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

    write_project_marker(root, project)
```

`fifdata/` 的 `dataset_description.json` 可以在首次成功导入时创建：

```json
{
  "Name": "Project Name",
  "DatasetKind": "ELYS-FIF",
  "Description": "Processing-ready FIF dataset generated from immutable raw uploads.",
  "BIDSLikeEntities": true
}
```

不要在这里写 `BIDSVersion` 并声称它是官方 BIDS raw。

## 5. 格式分类

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

分类返回：

| 分类 | 行为 |
|------|------|
| `standard-source` | 归档原始文件，直接读取生成 FIF |
| `advanced-source` | 归档原始文件，进入 reader/schema/trigger 确认 |
| `behavior-source` | 归档原始文件，映射为 events/beh/phenotype |
| `rejected` | 返回明确提示 |

## 6. 原始归档

`raw_archive.py`：

```python
def archive_import_files(project_root: Path, entities: BidsEntities, upload_seq: int, files: list[UploadFileInfo]) -> RawArchive:
    archive_root = project_root / "source_uploads" / entities.subject
    if entities.session:
        archive_root = archive_root / entities.session
    archive_root = archive_root / entities.task / (entities.run or "run-none") / f"upload-{upload_seq:03d}"
    files_root = archive_root / "files"
    files_root.mkdir(parents=True, exist_ok=True)

    archived = []
    for file in files:
        target = safe_join(files_root, file.relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        move_or_copy_upload(file.temp_path, target)
        archived.append({
            "relativePath": file.relative_path,
            "storedPath": str(target),
            "sha256": sha256_file(target),
            "size": target.stat().st_size,
        })

    write_json(archive_root / "manifest.json", {"files": archived, "uploadSeq": upload_seq})
    return RawArchive(root=archive_root, files=archived)
```

注意：

- 防止 `../` 路径穿越。
- 不覆盖同一 `upload-###` 内已存在文件。
- 已成功导入的原始上传版本不允许手工修改。

## 7. 数据库增量设计

v1 已实现的最小版本表是 `dataset_uploads`，用于在不改变 `subject/session/task/run` 语义的情况下保存重传历史。

```sql
CREATE TABLE dataset_uploads (
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

`datasets.current_upload_id` 指向当前上传版本。重传时旧版本标记为 `replaced`，新版本标记为 `current`。

后续完整异步导入可以继续新增：

```sql
CREATE TABLE import_jobs (
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

CREATE TABLE import_files (
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

CREATE TABLE fif_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id      UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    version         INTEGER NOT NULL,
    fif_path        TEXT NOT NULL,
    metadata_json   JSONB NOT NULL DEFAULT '{}',
    is_active       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE curation_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id      UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    fif_version_id  UUID REFERENCES fif_versions(id) ON DELETE SET NULL,
    event_type      VARCHAR(64) NOT NULL,
    payload_json    JSONB NOT NULL,
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
```

`datasets` 建议保存：

```text
project_id
subject_id
session
task
run
source_format
current_upload_id
source_file_paths
active_fif_path
current_upload_seq
n_channels
sfreq
duration_seconds
n_events
import_status
curation_status
```

## 8. FIF 写入

`fif_writer.py`：

```python
def write_processing_fif(raw: mne.io.BaseRaw, target_base: Path, metadata: ImportMetadata) -> WrittenFIF:
    fif_path = target_base.with_name(target_base.name + "_raw.fif")
    raw.save(fif_path, overwrite=False)

    write_eeg_json(target_base.with_name(target_base.name + "_eeg.json"), metadata.eeg)
    write_channels_tsv(target_base.with_name(target_base.name + "_channels.tsv"), metadata.channels)
    write_events_tsv(target_base.with_name(target_base.name + "_events.tsv"), metadata.events)
    write_json(target_base.with_name(target_base.name + "_import.json"), metadata.import_report)
    return WrittenFIF(path=fif_path)
```

命名：

```text
fifdata/sub-001/ses-01/eeg/sub-001_ses-01_task-rest_run-01_raw.fif
```

同一 active recording 不能重复占用同一实体路径；冲突时先返回 `DATASET_EXISTS`，用户确认后新增 `dataset_uploads` 上传版本并替换当前 FIF。

## 9. 高级格式读取

```python
def load_advanced_raw(path: Path, source_format: str, options: AdvancedImportOptions) -> mne.io.BaseRaw:
    if source_format == "cnt-neuroscan":
        return mne.io.read_raw_cnt(path, preload=False)
    if source_format == "cnt-ant":
        return mne.io.read_raw_ant(path, preload=False)
    if source_format == "egi-mff":
        return mne.io.read_raw_egi(path, preload=False)
    if source_format == "gdf":
        return mne.io.read_raw_gdf(path, preload=False)
    raise ImportPolicyError("不支持的高级导入 reader")
```

矩阵类：

```python
def raw_from_matrix(matrix: np.ndarray, meta: MatrixImportMetadata) -> mne.io.RawArray:
    if matrix.shape[1] != len(meta.channel_names):
        raise ImportPolicyError("矩阵列数必须等于通道名数量")
    info = mne.create_info(
        ch_names=meta.channel_names,
        sfreq=meta.sampling_frequency,
        ch_types=meta.channel_types,
    )
    return mne.io.RawArray(matrix.T, info)
```

## 10. trigger 和 events

`trigger.py` 需要同时服务 EDF/BDF 和高级格式。

```python
def preview_events(raw: mne.io.BaseRaw, options: TriggerOptions) -> EventPreview:
    # raw.annotations
    # Status/Trigger/STI channel
    # bit mask / edge / shift
    # external events TSV
    ...
```

用户确认后写入：

```text
fifdata/sub-001/ses-01/eeg/sub-001_ses-01_task-rest_run-01_events.tsv
```

同时可写入 FIF annotations，方便后续 MNE 处理。

## 11. 导入校正

`curation.py`：

```python
def apply_curation(raw: mne.io.BaseRaw, curation: CurationPatch) -> mne.io.BaseRaw:
    # rename channels
    # set channel types
    # set montage
    # set bads
    # set annotations/events
    ...
```

每次校正写 `curation_events`：

```json
{
  "eventType": "trigger_mapping_updated",
  "payload": {
    "source": "Status",
    "mask": "0x00FF",
    "mapping": {"11": "target", "12": "standard"}
  }
}
```

## 12. 验证

导入阶段验证：

```python
def validate_import(dataset: Dataset) -> ImportValidationResult:
    # source archived
    # raw can be read or matrix can be parsed
    # FIF exists and can be re-opened
    # channels/events sidecars match FIF
    # entities are unique or version policy is selected
```

BIDS export 阶段：

```python
def run_bids_validator(export_root: Path) -> ValidationResult:
    cmd = ["bids-validator", str(export_root), "--json"]
    ...
```

## 13. API 设计

```http
POST   /api/v1/projects/{project_id}/import-jobs
POST   /api/v1/import-jobs/{job_id}/files
GET    /api/v1/import-jobs/{job_id}/manifest
PATCH  /api/v1/import-jobs/{job_id}/mapping
POST   /api/v1/import-jobs/{job_id}/archive-raw
POST   /api/v1/import-jobs/{job_id}/generate-fif
PATCH  /api/v1/import-jobs/{job_id}/curation
POST   /api/v1/import-jobs/{job_id}/validate
POST   /api/v1/import-jobs/{job_id}/commit

POST   /api/v1/projects/{project_id}/bids-exports
POST   /api/v1/bids-exports/{export_id}/validate
```

## 14. 前端导入向导

```text
DataImportView
  FileSelectStep
  RawArchiveStep
  GroupingPreviewStep
  MappingStep
  EEGMetadataStep
  ChannelMontageStep
  TriggerEventStep
  FIFPreviewStep
  ValidationStep
  CommitStep
```

界面重点：

- 原始文件树和 checksum。
- 标准格式/高级格式分组。
- subject/session/task/run 批量映射。
- trigger 预览和事件码计数。
- 通道表和 montage。
- FIF 生成结果预览。
- 冲突处理：实验设计中的新 run、同数据位重传版本、跳过重复。

## 15. 开发阶段

| 阶段 | 目标 |
|------|------|
| Phase 1 | 建立 `source_uploads/.../upload-###/` 原始归档 |
| Phase 2 | BrainVision/EDF/BDF 生成 `fifdata/` |
| Phase 3 | import validation + 增量上传冲突处理 |
| Phase 4 | 通道、montage、trigger 导入校正和审计 |
| Phase 5 | CNT/MFF/GDF 高级导入 |
| Phase 6 | MAT/HDF5/CSV 矩阵模板 |
| Phase 7 | BIDS export 和 validator |

第一周建议完成 Phase 1-3，先把“原始归档 + FIF 处理起点 + 增量冲突”跑通。

## 16. 测试清单

| 用例 | 期望 |
|------|------|
| 上传 BrainVision 三件套 | source_uploads 原样归档，fifdata 生成 FIF |
| BrainVision 缺 `.vmrk` | 原始可归档，但 group 不能生成 FIF |
| 上传 EDF/BDF | 能生成 FIF 并预览 events |
| 上传 `.set/.fdt/.fif` | 明确拒收 |
| 上传 CNT | 要求选择 CNT 来源 |
| 上传 MFF | 校验目录完整性 |
| 上传 MAT 多变量 | advanced policy failed |
| 重复 checksum | 提示重复上传 |
| 重复 sub/ses/task/run | 返回 `DATASET_EXISTS`，确认后新增上传版本并替换当前 FIF |
| 修改 trigger 映射 | 写 curation log，更新 events/FIF annotations |
| 后续处理读取 | 只读 `fifdata/` active version |
| BIDS export | 生成 `bids_exports/` 并运行 validator |


