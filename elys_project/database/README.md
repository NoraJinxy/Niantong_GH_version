# ELYS 数据库初始化结构

## 目录组成

```
database/
├── schema/
│   ├── 01_auth.sql       # 用户、角色、权限
│   ├── 02_studies.sql    # 研究项、成员、审计、锁、设置
│   ├── 03_datasets.sql   # 数据集资产、版本、subjects、数据集、上传、文件、视图
│   ├── 04_pipelines.sql  # Pipeline 定义、运行、节点运行
│   ├── 05_outputs.sql    # 结果、文件派生、Run 输入与依赖
│   └── 06_async.sql      # 异步任务、任务事件
├── seeds/
│   ├── 01_roles_permissions.sql  # 系统角色、权限、映射
│   └── 02_dev_users.sql          # MVP/demo 用户（仅 init.sql 使用）
├── init.sql       # 一键入口：schema + roles/permissions + demo 用户
└── init_core.sql  # 一键入口：schema + roles/permissions（不含 demo 用户）
```

`schema/*.sql` 是当前 schema 的**单一事实来源**。文件编号代表加载顺序，受外键依赖约束，**不可调整**。

## 新库初始化

MVP / 本地 / 开发环境：

```bash
psql -d elys -v ON_ERROR_STOP=1 -f database/init.sql
```

生产 / 准生产环境（不含 demo 用户）：

```bash
psql -d elys -v ON_ERROR_STOP=1 -f database/init_core.sql
```

部署脚本 `deploy/deploy.sh` 已自动调用 `init.sql`，无需手动执行。

## 升级线上库

**当前策略：DROP DATABASE + 重建。**

```bash
sudo -u postgres psql -c "DROP DATABASE IF EXISTS elys;"
sudo -u postgres psql -c "CREATE DATABASE elys OWNER elys_user;"
sudo -u postgres psql -d elys -v ON_ERROR_STOP=1 -f database/init.sql
```

理由：项目当前数据量小、schema 迭代频繁、不维护增量 migration 工具。详见 `日志/2_meeting260524/数据库前后一致性审计.md`。

**如果未来真有不可丢失的生产数据**：人工分析新旧 schema 差异，写一次性升级 SQL，不要直接重跑 `init.sql`（`CREATE TABLE IF NOT EXISTS` 不会修改已存在的表，会造成漂移）。

## 修改 schema 的工作流

1. 找到字段所属的业务模块，编辑 `schema/0N_*.sql` 对应文件
2. 同步修改 `backend/app/models/` 下的 ORM 类
3. 在远程库重建：DROP DATABASE → init.sql
4. 跑 backend 验证 ORM 与新 schema 一致

**不要**再新建 `migrations/` 文件夹或往 `backend/alembic/versions/` 加文件 —— 当前流程不维护增量迁移。

## 历史背景

- 2026-05-24 之前：`schema/00_current_schema.sql`（单文件 713 行）+ `migrations/20260521_0001 … 20260524_0006`（6 个增量 SQL）+ `backend/alembic/versions/` 的 6 个 Python 版本（从未在生产跑过）
- 2026-05-24：审计发现 `init.sql` 未引入 0005/0006，远程库长期残留僵尸表和拼写双轨约束。重构为 6 个按业务模块拆分的 schema 文件，删除 `migrations/`，停用 Alembic
- 详见 `日志/2_meeting260524/数据库前后一致性审计.md`

## Alembic 状态

`backend/alembic/` 已停用，详见 `backend/alembic/DEPRECATED.md`。
