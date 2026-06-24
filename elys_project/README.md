# ELYS v1

念析 v1 当前实现包含：

- Vue 3 前端：登录、项目、Dashboard、数据导入与若干静态工作台页面。
- FastAPI 后端：认证、项目管理、数据集导入、项目垃圾箱。
- PostgreSQL 初始化：用户/RBAC、项目、BIDS/FIF 元数据、数据上传版本。
- 一键部署：`deploy/deploy_remote.ps1` 从 Windows 主机部署到入口服务器和计算服务器。

## 数据导入

当前 EEG 数据导入遵循：

```text
原始文件 -> source_uploads/.../upload-### -> fifdata 当前工作 FIF -> PostgreSQL 索引
```

详细说明见：

- [BIDS_DATA_IMPORT_AND_VERSIONING.md](docs/BIDS_DATA_IMPORT_AND_VERSIONING.md)

## 部署

在本地 Windows PowerShell 中进入：

```powershell
cd .\elys_project\deploy
.\deploy_remote.ps1
```

部署脚本会清理并初始化计算服务器数据目录、数据库、后端服务和入口服务器前端。

## 计算服务器状态排查

计算服务器默认包含 `elys-backend`、`nginx`、`postgresql`、`redis-server` 和 `/mnt/elys_data/projects`。

常用检查：

```powershell
$KEY="$env:USERPROFILE\.ssh\elys_deploy_ed25519"
$HOST="root@REPLACE_WITH_COMPUTE_PUBLIC_IP"

ssh -i $KEY $HOST "systemctl status elys-backend nginx postgresql redis-server --no-pager"
ssh -i $KEY $HOST "curl -i http://127.0.0.1:8000/api/v1/health && curl -i http://127.0.0.1/api/v1/health"
ssh -i $KEY $HOST "journalctl -u elys-backend -n 120 --no-pager"
```

如果日志中出现 `health 200`、`login 200`、`datasets/import 201`，说明计算服务器主体正常。`401 Unauthorized` 通常是未登录或 token 过期；`SAWarning` 和 Matplotlib cache warning 属于需要修复的技术债，不等于服务宕机。

## 工作流 Celery Worker

工作流 `/run` 会创建 execution/job 后投递 Celery 任务到 `workflow.default` 队列。启动 worker 前需要 Redis 可用。

本地 Windows 调试：

```powershell
$env:PYTHONPATH=(Join-Path $PWD 'backend')
python -m celery -A app.tasks.celery_app:celery_app worker -Q workflow.default --pool=solo --loglevel=INFO
```

Linux/服务器：

```bash
export PYTHONPATH=backend
celery -A app.tasks.celery_app:celery_app worker -Q workflow.default --loglevel=INFO
```
