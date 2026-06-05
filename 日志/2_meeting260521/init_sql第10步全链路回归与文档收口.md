# init.sql 第 10 步全链路回归与文档收口

日期：2026-05-21

## 1. 回归结论

本轮完成了代码级、模型级、文档级和可用测试环境内的回归验证。受本机环境限制，未能执行真实 PostgreSQL 初始化、真实 FastAPI HTTP 请求、真实 Celery worker 和真实 EEG 上传转换端到端链路。

当前可确认：

- 数据库对象、ORM、schema 和文档已对齐到 Dataset / Study / Pipeline / Run 主干。
- `dataset_files`、`pipeline_run_inputs`、`pipeline_artifacts.retention_status`、`async_tasks`、`task_events`、`study_locks`、`audit_events` 已进入 schema 和 ORM。
- Pipeline Run 创建链路在代码上已包含运行锁、Run、输入快照、AsyncTask、TaskEvent、Celery 派发和兼容 result_json。
- 新文档可成功构建。

## 2. 已执行验证

| 验证项 | 结果 | 说明 |
|---|---|---|
| 后端编译 | 通过 | `python -m compileall app alembic` |
| 后端测试 | 通过 | `python -m pytest -q`，15 passed，17 个 datetime.utcnow deprecation warning |
| SQLAlchemy mapper | 通过 | `DatasetAsset`、`StudyDatasetMount`、`Recording`、`RecordingVersion`、`DatasetFile`、`PipelineRunInput`、`AsyncTask`、`TaskEvent`、`PipelineArtifact` 映射成功 |
| Pipeline schema 构造 | 通过 | `PipelineArtifactResponse`、`PipelineRunInputResponse`、`AsyncTaskResponse`、`TaskEventResponse` 可构造 |
| 路由数量静态统计 | 通过 | 当前 44 个 HTTP API：health 1、auth 4、datasets.py 11、pipelines.py 17、projects.py 11 |
| 数据库 SQL 分区检查 | 通过 | `init.sql` 4 个 include，`init_core.sql` 3 个 include；baseline 不含 role/user seed |
| MkDocs 构建 | 通过 | `mkdocs build` 成功，Material for MkDocs 输出上游 MkDocs 2.0 提醒，不影响构建 |

## 3. 核心链路核对

| 链路 | 当前核对结果 |
|---|---|
| 登录 | 认证路由和现有 QA 路由测试桩通过；未做真实 HTTP 登录 |
| 创建 Study/Project | 路由和 ORM 编译通过；未连接 PostgreSQL 做真实创建 |
| 上传 EEG | 现有 QA 测试覆盖部分 dataset router 导入相关依赖；未做真实 multipart 上传和 MNE 转换 |
| 生成 canonical FIF | 代码路径保留；未做真实 EEG 文件转换 |
| `dataset_files` 写入 | 导入代码已双写 raw/canonical/sidecar，ORM 和 schema 校验通过 |
| 创建 Pipeline | 路由和 schema 编译通过；未做真实数据库创建 |
| Run 创建 | 代码核对通过：创建 `pipeline_runs`、`async_tasks`、`task_events`，并调用 `PipelineExecutor.prepare_run()` |
| `pipeline_run_inputs` 写入 | `prepare_run()` 已写 selector 和解析数据快照，并优先匹配 `dataset_files` |
| `async_tasks` 关联 | Run 创建时写 `async_tasks.resource_kind='pipeline_run'`、`resource_id=run.id` |
| Artifact 写入 | `ArtifactStore` 新 Artifact 写 `storage_uri`、`sha256`、`retention_status='current'` |
| retention 查询 | Artifact schema/response 已暴露 `retention_status`；真实 API 查询未执行 |

## 4. 文档更新

已同步更新：

- `wiki/docs_v2/2-50-API设计总览.md`
- `wiki/docs_v2/2-60-任务队列与异步架构.md`
- `wiki/docs_v2/3-00-数据库设计总览.md`
- `wiki/docs_v2/3-20-Dataset与采集记录表.md`
- `wiki/docs_v2/3-40-Run与Artifact追溯表.md`
- `wiki/docs_v2/3-50-协作权限状态与迁移.md`
- `wiki/docs_v2/4-00-文件管理总览.md`
- `wiki/docs_v2/4-20-Dataset文件与导入转换.md`
- `wiki/docs_v2/4-30-Study输出与Artifact.md`
- `wiki/docs_v2/4-40-数据选择器与文件索引.md`
- `wiki/docs_v2/7-00-后端架构总览.md`
- `wiki/docs_v2/7-10-后端工程结构与启动入口.md`
- `wiki/docs_v2/7-40-工作流执行与后台任务.md`

## 5. 遗留风险

- 本机没有 `psql`，未执行 `database/init.sql` 的真实 PostgreSQL 初始化。
- 本机没有 `fastapi`，未启动后端服务做真实 HTTP 回归。
- 本机没有 `alembic` CLI 包，未执行 `alembic upgrade head`。
- 没有 Redis/Celery worker，未验证真实后台派发与 worker 状态流转。
- Dataset 导入仍是同步 HTTP 流程，真实大文件上传转换仍需部署环境压测。
- Task 查询、取消、重试 API 尚未暴露。
- Artifact pin/unpin/cleanup 服务尚未实现。

## 6. 下一步建议

在安装完整后端依赖并启动 PostgreSQL、Redis、Celery 后，补一次部署环境端到端回归：

1. `psql -d elys -v ON_ERROR_STOP=1 -f database/init.sql`
2. 启动 FastAPI、Redis、Celery worker。
3. 登录 `admin` 或 `user1`。
4. 创建 Study/Project。
5. 上传一个小型 EDF/BDF/BrainVision 测试文件。
6. 检查 `dataset_files` 是否有 raw、canonical、sidecar。
7. 创建含 LoadData 的 Pipeline 并运行。
8. 检查 `pipeline_run_inputs`、`async_tasks`、`task_events`、`pipeline_artifacts.retention_status`。
9. 打开 Run 详情和 Artifact 预览。
