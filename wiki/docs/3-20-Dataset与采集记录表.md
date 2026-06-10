# 3-20 Dataset 与采集记录表

> 本页维护 Dataset 资产、Recording（采集记录）、Recording Version（采集记录版本）、Dataset File 和数据选择器索引。它是导入、重传、LoadData 和数据选择器的数据库依据。

<div class="elys-meta" markdown>

定位
: 数据资产、采集记录、上传版本、文件索引

事实源
: `backend/app/models/study.py`

代码位置
: `backend/app/models/study.py` · `backend/app/routers/datasets.py`

更新
: 2026-06-05 00:00:00 +08:00

</div>

## 一句话现状

「A+B 重构」已落地：`recordings` 与 `recording_versions` 现在就是真实主表（由原 `datasets` / `dataset_uploads` 改名而来），不存在只读兼容视图，也没有「写入仍走旧表」的过渡层。本页所有字段表均对齐 `models/study.py` 的 ORM 定义。

## 1. `dataset_assets`（标准 Dataset 资产）

标准 Dataset 表示一个可被 Study 引用的数据资产，不等于某个具体文件，也不等于某个被试。`dataset_assets` 就是用户创建和维护的 Dataset 资产身份。系统可以为它自动创建或选择一个配套 Study，但这个 Study 只是导入、QC、Pipeline/Execution 工作空间；Study 通过 `study_dataset_mounts` 使用 Dataset，不拥有 Dataset。

| 字段 | 说明 |
|---|---|
| `id` | UUID 主键 |
| `name` / `code` | 数据集名称和短代码（`code` 全局唯一） |
| `description` | 数据说明 |
| `owner_id` | 数据集负责人 |
| `status` | `working`（在建草稿）默认值，配套 `active` · `archived` · `deleted` · `quarantined`（隔离待核） |
| `visibility` | `private`（默认）· `shared` · `public`。可见范围，也是数据集 UI 的状态徽章轴（6-05 B 方案）；发布默认私有，由负责人显式开放，**只升不降、无降级接口**，旧 `workspace` 档已去掉 |
| `metadata`（ORM 属性 `metadata_json`）| 设备、采样范式、伦理说明、采集说明等扩展信息 |
| `primary_study_id` | 主属 Study，发布/生命周期口径下的归属锚点（见 3-25），可空 |
| `concept_doi` | 概念级 DOI（指向资产本身而非某个版本），可空 |
| `current_version_id` | 指向 `dataset_versions` 的当前有效发布版本，可空 |
| `created_by` / `created_at` / `updated_at` | 创建人、创建和更新时间 |

发布、撤回等生命周期通过 `dataset_versions.state` 的 `unpublished / published / withdraw_requested / withdrawn` 状态机管理，未发布数据不会被发布改写，详见 [3-25 数据集生命周期与发布机制](3-25-数据集生命周期与发布机制.md)。

唯一的 Dataset 创建入口是 `POST /api/v1/dataset-assets/bootstrap`：一次性创建 Dataset Asset、working Dataset Version、配套 Study 和 active mount（裸建端点 `POST /dataset-assets` 已删除）。

## 2. `recordings`（采集记录，真实主表）

`recordings` 表表示 Dataset 内的一条采集记录，通常对应 BIDS 语义下的一个 `subject/session/task/run`。「BIDS」（Brain Imaging Data Structure，脑成像数据的标准目录命名约定）下，一条记录由被试、会话、任务、run 四个标签定位。

这是真实主表，由原 `Dataset` / `datasets` 在「A 重构（2026-06-04）」中改名而来；不存在 `recordings_view` 之类的只读兼容视图。

| 字段 | 说明 |
|---|---|
| `id` | UUID 主键 |
| `study_id` | 导入发生的 origin/paired Study，不代表 Dataset 属于该 Study |
| `dataset_asset_id` | 所属 Dataset 资产，可空 |
| `subject_id` | 关联 `subjects` 被试 |
| `session` | `ses-01`，可空 |
| `task` | `task-rest` 或任务名，非空 |
| `run` | `run-01`，可空 |
| `source_format` | 原始文件格式 |
| `source_path` | 原始上传路径 |
| `fif_path` | canonical FIF 路径，可空 |
| `current_version_id` | 指向 `recording_versions` 的当前有效版本，可空 |
| `file_size` / `checksum` | 主文件大小与校验值 |
| `n_channels` / `sfreq` / `duration_seconds` / `n_events` | 基础数据摘要（通道数、采样率、时长、事件数） |
| `qa_status` | 当前 QA 状态，默认 `pending`；不作为运行硬门槛 |
| `qa_report` | QA 报告 JSON |
| `imported_by` / `imported_at` | 导入人和导入时间 |

一条采集记录的 BIDS 身份由 `subject_id`（外键指向 `subjects`，被试的 BIDS 标签存在 `subjects.bids_subject_id`）加上 `session` / `task` / `run` 共同定位。`task` 非空，`session` 和 `run` 可空。`recordings` 表有数据库级唯一索引 `uq_recordings_bids_entities`，按 `(study_id, subject_id, COALESCE(session,''), task, COALESCE(run,''))` 兜底去重；导入流程在此之上再做语义去重。

## 3. `recording_versions`（采集记录版本，真实主表）

`recording_versions` 表表示同一条采集记录的某次上传、重传或转换版本。这是真实主表，由原 `DatasetUpload` / `dataset_uploads` 在「A 重构（2026-06-04）」中改名而来；`recording_id`、`version_seq` 等都是原生字段，没有从旧表派生的迁移注解，也没有 `recording_versions_view`。

| 字段 | 说明 |
|---|---|
| `id` | UUID 主键 |
| `recording_id` | 所属采集记录，非空 |
| `version_seq` | 递增版本号，非空 |
| `source_format` | `edf` · `cnt` · `vhdr` · `set` 等 |
| `source_dir` / `source_main_file` / `source_files` | 原始上传归档目录、主文件与文件清单 |
| `fif_dir` / `fif_path` / `sidecar_paths` | canonical FIF 目录、路径与 sidecar；逐文件标准索引见 `dataset_files` |
| `file_size` / `checksum` | 版本主文件大小与校验值 |
| `status` | `current` 默认值，CHECK 取值 `current` · `replaced` · `rejected` · `failed`（无 `quarantined`） |
| `qa_status` | 版本级 QC 状态，默认 `converted`；不作为运行硬门槛 |
| `note` | 备注 |
| `uploaded_by` / `uploaded_at` | 上传人和上传时间 |

增量上传不会产生新的 Dataset 副本，只会新增 Recording 或 Recording Version，并更新 `recordings.current_version_id`。

## 4. `dataset_files`

`dataset_files` 是所有 Dataset 文件的统一索引。

| 字段 | 说明 |
|---|---|
| `id` | UUID 主键 |
| `study_id` | 记录 origin/paired Study，不代表 Dataset File 的所有权 |
| `recording_id` | 所属采集记录，非空 |
| `recording_version_id` | 所属采集记录版本，非空 |
| `dataset_version_id` | 关联发布版本（3-25），可空 |
| `file_role` | 标准角色 `original_upload` · `raw_bids_data` · `raw_bids_eeg_json` · `raw_bids_channels` · `raw_bids_events` · `canonical_fif`；兼容角色 `raw_source` · `sidecar`（见 DDL `COMMENT ON COLUMN dataset_files.file_role`） |
| `storage_uri` | 存储地址，如 `elys://datasets/...`，未来可映射 MinIO/S3 |
| `relative_path` | Dataset 内相对路径，非空 |
| `logical_path` | Dataset 内部逻辑路径，如 `raw_bids/...` 或 `derivatives/elys-canonical-fif/...` |
| `source_file_id` | 派生关系的源文件（如 canonical FIF 指向其 raw_source），自引用，可空 |
| `file_size` / `sha256` / `mime_type` | 文件大小、校验值、文件类型 |
| `metadata`（ORM 属性 `metadata_json`）| 文件角色细节、sidecar key、上传序号等 |
| `created_by` / `created_at` | 创建信息 |

> 注：API 响应模型 `DatasetFileResponse` 里仍有名为 `dataset_id` / `dataset_upload_id` 的字段，但其取值来自 `recording_id` / `recording_version_id`，这是响应层的历史命名兼容，不是数据库列。见 [2-50 API 设计总览](2-50-API设计总览.md)。

Dataset 可以同时包含原始上传证据、Raw BIDS 标准入口和系统生成的 canonical FIF。Raw BIDS 是原始数据权威入口；canonical FIF 是从 Raw BIDS 生成的 MNE-ready 工作副本（MNE 是常用的 Python 脑电分析库），不替代 Raw BIDS，也不是滤波、ICA 或去坏段后的处理结果。

## 5. 选择器索引表

数据选择器不能依赖用户理解目录结构，也不能每次临时扫描 FIF。建议维护轻量索引表：

| 表 | 用途 |
|---|---|
| `recording_event_summaries` | 每个 recording version 中各 marker/event 的数量、首末时间、标签别名和可选分组 |
| `recording_channel_summaries` | 通道类型、通道数量、坏通道候选、缺失通道、定位状态摘要 |

详细事件仍保存在 `events.tsv` 或其它 sidecar 文件中；数据库只保存筛选和批量选择所需的摘要。这两张表为规划项，事实源以 `models/study.py` 落地为准。

## 6. 与当前代码的关系

「A+B 重构」后命名已统一落地，下表只描述现状：

| 表 | 当前角色 | 备注 |
|---|---|---|
| `dataset_assets` | 标准 Dataset 资产 | 已接入 `primary_study_id` / `concept_doi` / `current_version_id` 等 3-25 生命周期字段 |
| `dataset_versions` | Dataset 发布版本 | `unpublished / published / withdraw_requested / withdrawn` 状态机（字段 `state`），见 3-25 |
| `recordings` | 采集记录真实主表 | 由原 `datasets` 改名；无兼容视图 |
| `recording_versions` | 采集记录版本真实主表 | 由原 `dataset_uploads` 改名；`recording_id` / `version_seq` 均为原生字段 |
| `dataset_files` | 文件统一索引 | 外键为 `recording_id` + `recording_version_id`（不再是 `dataset_id` / `dataset_upload_id`） |

判断 Dataset 所属关系时，应优先看 `dataset_asset_id` 和 `study_dataset_mounts`。`recordings.study_id`、`subjects.study_id`、`dataset_files.study_id` 只作为导入上下文字段；跨 Study 使用 Dataset 时，不能再用这些字段当权限或可见性的唯一依据。

当前回归确认的查询口径：

- `GET /api/v1/studies/{study_id}/recordings` 不带过滤条件时默认使用当前 Study active mounts 的 `dataset_asset_id`，并保留旧 `study_id` fallback（旧的 `GET /studies/{study_id}/datasets` 列表端点已不存在）。
- `GET /api/v1/studies/{study_id}/datasets` 前缀下现在只剩 mounts 端点（`GET/POST /mounts`、`PATCH/DELETE /mounts/{mount_id}`）。
- LoadData resolve 查询 DatasetFile 时不强制 `dataset_files.study_id == 当前 Study`，而是按已校验可访问的 Dataset/Recording 和 `dataset_file_id / storage_uri / logical_path` 冻结输入。

## 7. 相关页面

- [3-25 数据集生命周期与发布机制](3-25-数据集生命周期与发布机制.md)
- [4-20 Dataset 文件与导入转换](4-20-Dataset文件与导入转换.md)
- [4-40 数据选择器与文件索引](4-40-数据选择器与文件索引.md)
- [5-00 研究管理总览](5-00-研究管理总览.md)
