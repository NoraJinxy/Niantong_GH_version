-- Purpose: 一键初始化 ELYS PostgreSQL 数据库（不含 demo 用户）— 按业务模块顺序加载拆分后的 schema 文件 + seeds。
-- Related: database/schema/*.sql, database/seeds/*.sql, deploy/deploy.sh。
-- Usage: psql -d <db> -v ON_ERROR_STOP=1 -f database/init.sql
-- Notes:
--   1. Schema 已拆为 6 个按业务模块组织的文件，加载顺序对应外键依赖关系，不可调整。
--   2. 升级线上库时请先 DROP DATABASE 再重建（项目当前数据量小、迭代频繁，不维护增量 migration）；
--      如需保留生产数据，请人工分析差异后写一次性升级脚本，不要直接重跑本文件。
--   3. demo/dev 用户请在本地未追踪 seed 中维护，不进入公开仓库。

\set ON_ERROR_STOP on

\echo 'ELYS bootstrap [1/7]: 01_auth.sql — extensions + users + roles + permissions'
\ir schema/01_auth.sql

\echo 'ELYS bootstrap [2/7]: 02_studies.sql — studies + members + audit + locks + settings'
\ir schema/02_studies.sql

\echo 'ELYS bootstrap [3/7]: 03_datasets.sql — dataset assets + versions + subjects + datasets + files + views'
\ir schema/03_datasets.sql

\echo 'ELYS bootstrap [4/7]: 04_pipelines.sql — pipeline definitions + executions + jobs'
\ir schema/04_pipelines.sql

\echo 'ELYS bootstrap [5/7]: 05_outputs.sql — derived datasets + file derivations + execution inputs + dependencies'
\ir schema/05_outputs.sql

\echo 'ELYS bootstrap [6/7]: 06_async.sql — async tasks + task events'
\ir schema/06_async.sql

\echo 'ELYS bootstrap [7/7]: seeds/01_roles_permissions.sql — system roles, permissions, role-permission mapping'
\ir seeds/01_roles_permissions.sql

\echo 'ELYS bootstrap: done'
