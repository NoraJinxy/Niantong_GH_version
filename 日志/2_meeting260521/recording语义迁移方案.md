# Recording 语义迁移方案

> 目标：把当前旧 `datasets` / `dataset_uploads` 的产品语义逐步迁移为 `Recording` / `Recording Version`，同时保留旧上传、旧 API 和旧代码路径，避免一次性破坏现有功能。

## 1. 命名边界

| 新概念 | 中文名 | 当前落地 | 说明 |
|---|---|---|---|
| Dataset Asset | 数据集资产 | `dataset_assets` | 平台级可共享、可挂载的数据资产，不等同单条被试记录。 |
| Study Dataset Mount | 研究项数据集挂载 | `study_dataset_mounts` | Study/Project 对 Dataset Asset 的引用关系，不复制文件。 |
| Recording | 采集记录 | `recordings_view` -> `datasets` | 单条 subject/session/task/run 采集记录。第 8 步先用视图兼容。 |
| Recording Version | 采集版本 | `recording_versions_view` -> `dataset_uploads` | 某条 Recording 的第几次上传/重传版本。 |
| Dataset File | 数据文件索引 | `dataset_files` | raw source、canonical FIF、sidecar 等文件事实索引。 |

## 2. 第 8 步采用的兼容策略

- 不删除、不重命名 `datasets` 和 `dataset_uploads`。
- 旧上传流程继续写 `datasets` / `dataset_uploads` / `dataset_files`。
- 新增只读视图：
  - `recordings_view`：把 `datasets` 投影为 Recording。
  - `recording_versions_view`：把 `dataset_uploads` 投影为 Recording Version。
- 新增 ORM 只读模型：
  - `Recording` -> `recordings_view`
  - `RecordingVersion` -> `recording_versions_view`
- 新增新命名 API：
  - `GET /api/v1/projects/{project_id}/recordings`
  - `GET /api/v1/projects/{project_id}/recordings/{recording_id}/versions`
- 旧 API 保留：
  - `GET /api/v1/projects/{project_id}/datasets`
  - `POST /api/v1/projects/{project_id}/datasets/import`

## 3. 后续迁移路线

1. 先让前端和新后端模块优先使用 Recording 命名读取采集记录。
2. 让 LoadData 数据选择器支持从 Study Dataset Mount 出发，解析到 Recording / Recording Version / Dataset File。
3. 在后续迁移中为 `datasets` 增加 `dataset_asset_id` 或建立独立关联表，让 Dataset Asset 与 Recording 明确关联。
4. 等旧 API 和旧前端完成迁移后，再考虑把物理表改名为 `recordings` / `recording_versions`，或保留旧表名但只暴露新命名。

## 4. 当前遗留边界

- `recordings_view` 和 `recording_versions_view` 是兼容视图，不作为写入入口。
- Dataset Asset 与旧 `datasets` 暂未自动关联。
- Study Mount 的 `selection_json` 尚未接入 LoadData 查询。
- 当前版本的“新命名可用”主要指只读查询可用，上传仍走旧入口。
