-- Purpose: 一键初始化 ELYS PostgreSQL 数据库（含 MVP/demo 用户）— 按业务模块顺序加载拆分后的 schema 文件 + seeds。
-- Related: database/schema/*.sql, database/seeds/*.sql, deploy/deploy.sh。
-- Usage: psql -d <db> -v ON_ERROR_STOP=1 -f database/init.sql
-- Notes:
--   1. Schema 已拆为 6 个按业务模块组织的文件，加载顺序对应外键依赖关系，不可调整。
--   2. 升级线上库时请先 DROP DATABASE 再重建（项目当前数据量小、迭代频繁，不维护增量 migration）；
--      如需保留生产数据，请人工分析差异后写一次性升级脚本，不要直接重跑本文件。
--   3. init_core.sql 是不含 demo 用户的生产/准生产版本。

\set ON_ERROR_STOP on

\echo 'ELYS bootstrap [1/8]: 01_auth.sql — extensions + users + roles + permissions'
\ir schema/01_auth.sql

\echo 'ELYS bootstrap [2/8]: 02_studies.sql — studies + members + audit + locks + settings'
\ir schema/02_studies.sql

\echo 'ELYS bootstrap [3/8]: 03_datasets.sql — dataset assets + versions + subjects + datasets + files + views'
\ir schema/03_datasets.sql

\echo 'ELYS bootstrap [4/8]: 04_pipelines.sql — pipeline definitions + executions + jobs'
\ir schema/04_pipelines.sql

\echo 'ELYS bootstrap [5/8]: 05_derived.sql — derived datasets + file derivations + execution inputs + dependencies'
\ir schema/05_derived.sql

\echo 'ELYS bootstrap [6/8]: 06_async.sql — async tasks + task events'
\ir schema/06_async.sql

\echo 'ELYS bootstrap [7/8]: seeds/01_roles_permissions.sql — system roles, permissions, role-permission mapping'
\ir seeds/01_roles_permissions.sql

\echo 'ELYS bootstrap [8/8]: seeds/02_dev_users.sql — MVP/demo users'
\ir seeds/02_dev_users.sql

\echo 'ELYS bootstrap: done'
