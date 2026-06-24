-- Purpose: 一键初始化 ELYS PostgreSQL 数据库（不含 demo 用户）— 适合生产/准生产环境。
-- Related: database/init.sql（含 demo 用户的 MVP 版本），database/schema/*.sql, database/seeds/01_roles_permissions.sql。
-- Usage: psql -d <db> -v ON_ERROR_STOP=1 -f database/init_core.sql
-- Notes: 保留为生产/准生产入口；demo 用户请在本地私有 seed 中创建。

\set ON_ERROR_STOP on

\echo 'ELYS core bootstrap [1/7]: 01_auth.sql'
\ir schema/01_auth.sql

\echo 'ELYS core bootstrap [2/7]: 02_studies.sql'
\ir schema/02_studies.sql

\echo 'ELYS core bootstrap [3/7]: 03_datasets.sql'
\ir schema/03_datasets.sql

\echo 'ELYS core bootstrap [4/7]: 04_pipelines.sql'
\ir schema/04_pipelines.sql

\echo 'ELYS core bootstrap [5/7]: 05_outputs.sql'
\ir schema/05_outputs.sql

\echo 'ELYS core bootstrap [6/7]: 06_async.sql'
\ir schema/06_async.sql

\echo 'ELYS core bootstrap [7/7]: seeds/01_roles_permissions.sql'
\ir seeds/01_roles_permissions.sql

\echo 'ELYS core bootstrap: done'
