# StudyOutputs 子领域 · 拆 router 蓝图

> 把 `routers/pipelines.py` 的 StudyOutputs 子领域抽到独立 `routers/study_outputs.py` 的施工图。
> 由分析 agent 产出（2026-06-12），供拆分时照单移动、避免漏 import。**行号会随改动漂移，以函数名/依赖为准。**
>
> **✅ 2026-06-12 已按本蓝图执行完毕、云端验证零回归**：`study_outputs.py` 含 7 个 CRUD 端点 + 3 个专属 helper；`cleanup`/`gc` 与 execution-outputs 按蓝图留在 `pipelines.py`。本文留作施工记录。

## 已就绪
- `routers/_pipeline_shared.py` 已建，含 `get_study_for_read/write/run`、`study_output_to_response`、`_to_str_list`、（建议再加 `FILE_TASK_TYPES` 常量）。

## 移到 study_outputs.py 的 endpoint（纯 StudyOutputs）
- `list_study_outputs` GET `/studies/{id}/outputs`
- `get_study_output` GET `/studies/{id}/outputs/{dataset_id}`
- `update_study_output` PATCH `/studies/{id}/outputs/{dataset_id}`（内含 `db.commit()`）
- `batch_update_study_outputs` POST `/studies/{id}/outputs/batch-update`（`db.commit()` + `assert_artifact_can_be_deleted`）
- `get_study_output_preview` GET `.../preview`（`db.commit()` 更新 preview_json）
- `get_study_output_timeseries` GET `.../timeseries`
- `download_study_output` GET `.../download`（`db.commit()` 更新 updated_at；`FileResponse`）

## ⚠️ 暂留 pipelines.py（依赖共享函数，先别移，避免循环 import）
- `create_study_output_cleanup_task` / `create_study_output_gc_task`：调用 `create_and_dispatch_file_task`（多区域共享，留 pipelines.py）。先留，等共享层把 `create_and_dispatch_file_task` 也提取后再移。
- `list_pipeline_execution_study_outputs`：execution 视角，留 pipelines.py。

## 随之移走的专属 helper
- `get_study_output_or_404`
- `record_study_output_action_audit`
- `apply_study_output_retention_action`（⚠️ 内有 3 处 `commit-then-raise`：依赖被挡 commit+409、GC 清盘恢复 commit+409；原样保留）

## study_outputs.py 的 import 清单
```python
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import StudyOutput, Study, User
from app.schemas.study_output import (
    StudyOutputBatchUpdate, StudyOutputListResponse, StudyOutputPreviewResponse,
    StudyOutputResponse, StudyOutputUpdate,
)
from app.pipeline.previews import (
    StudyOutputPreviewError, MAX_EVOKED_CHANNELS,
    build_study_output_preview, resolve_study_output_path, validate_study_output_file,
)
from app.pipeline.timeseries import build_timeseries
from app.pipeline.save_settings import retention_expiry_after_user_action
from app.services.execution_dependencies import ArtifactDependencyError, assert_artifact_can_be_deleted
from app.services.audit_events import record_audit_event
from app.routers.auth import get_current_user
from app.routers._pipeline_shared import get_study_for_read, get_study_for_write, study_output_to_response
```

## 遗漏风险点（按危险度）
1. `MAX_EVOKED_CHANNELS` / `StudyOutputPreviewError`（app.pipeline.previews）— preview 端点必需，易漏。
2. `apply_study_output_retention_action` 的 3 处 commit-then-raise — 改错破坏原子性。
3. `ArtifactDependencyError` 异常类 — batch_update 依赖检查必需。
4. `FILE_TASK_TYPES` 常量 — 若移 cleanup/gc 才需要；本蓝图先不移它们，故暂不涉及。

## 施工顺序建议
1. （可选）先把 `create_and_dispatch_file_task` + `FILE_TASK_TYPES` 提到 `_pipeline_shared.py`，解锁 cleanup/gc 一起移。
2. 建 `study_outputs.py`，按上面清单移 7 个 CRUD 端点 + 3 个专属 helper + import。
3. pipelines.py 删这些定义。
4. `__init__.py` / `main.py` 注册 `study_outputs_router`。
5. compileall（查语法）→ **部署后 curl 每个 `/studies/{id}/outputs*` 端点 + elys_debug 验运行**（本地查不出 import resolve / 运行错）。
