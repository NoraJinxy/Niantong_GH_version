"""
Purpose: Create the FastAPI application, register routers, configure CORS, and expose health checks.
Related: app/config.py, app/routers/*, docs_v2/2-50 and docs_v2/7-10.
"""

import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 调试期：每次重部署（= 重启服务）全量重置业务数据。
    # 保留：users / roles / permissions / user_roles / role_permissions（账号不丢）。
    # 清除：所有研究项、数据集、Pipeline 历史、产物 DB 行 + 磁盘文件。
    try:
        _full_reset_on_startup()
    except Exception as exc:  # noqa: BLE001
        logger.warning("startup full reset failed (non-fatal): %s", exc)
    yield


def _full_reset_on_startup() -> None:
    """重部署自动全量重置：清除所有业务表（保留认证表）+ 删除所有存储文件。"""
    import shutil  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415
    from sqlalchemy import text  # noqa: PLC0415
    from app.database import SessionLocal  # noqa: PLC0415

    # 从叶表到根表列出，CASCADE 会自动处理任何遗漏的依赖。
    _TABLES = ", ".join([
        "execution_outputs",
        "pipeline_execution_dependencies",
        "pipeline_execution_inputs",
        "pipeline_jobs",
        "pipeline_executions",
        "pipeline_definitions",
        "study_outputs",
        "recording_versions",
        "recordings",
        "dataset_file_derivations",
        "dataset_version_files",
        "dataset_version_references",
        "dataset_files",
        "dataset_withdrawal_requests",
        "dataset_publicization_requests",
        "dataset_versions",
        "dataset_members",
        "dataset_assets",
        "study_dataset_mounts",
        "study_members",
        "study_locks",
        "study_settings",
        "subjects",
        "task_events",
        "async_tasks",
        "audit_events",
        "studies",
    ])

    db = SessionLocal()
    try:
        db.execute(text(f"TRUNCATE TABLE {_TABLES} CASCADE"))
        db.commit()
        logger.info("startup full reset: all business tables truncated")
    finally:
        db.close()

    # 清文件：删除整个存储根目录下所有内容，重建空子目录。
    storage_root = Path(settings.ELYS_STORAGE_ROOT)
    if storage_root.exists():
        for child in storage_root.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    for sub in ("datasets", "studies", "trash"):
        (storage_root / sub).mkdir(parents=True, exist_ok=True)
    logger.info("startup full reset: storage cleared at %s", storage_root)

from app.routers import (
    auth_router,
    dashboard_router,
    dataset_assets_router,
    dataset_files_router,
    dataset_versions_router,
    dataset_withdrawals_router,
    dataset_publicize_router,
    dataset_publicizations_router,
    datasets_router,
    pipelines_router,
    pipeline_node_specs_router,
    pipeline_load_data_router,
    pipeline_definitions_router,
    study_outputs_router,
    studies_router,
    recording_router,
)
from app.config import get_settings

settings = get_settings()
cors_origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]


class UUIDEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return super().default(obj)


class CustomJSONResponse(JSONResponse):
    def render(self, content):
        return json.dumps(content, ensure_ascii=False, cls=UUIDEncoder).encode("utf-8")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="念析 (ELYS) EEG 分析平台",
    default_response_class=CustomJSONResponse,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(studies_router)
app.include_router(dataset_assets_router)
app.include_router(dataset_files_router)
app.include_router(recording_router)
app.include_router(datasets_router)
app.include_router(dataset_versions_router)
app.include_router(dataset_withdrawals_router)
app.include_router(dataset_publicize_router)
app.include_router(dataset_publicizations_router)
app.include_router(pipelines_router)
app.include_router(pipeline_node_specs_router)
app.include_router(pipeline_load_data_router)
app.include_router(pipeline_definitions_router)
app.include_router(study_outputs_router)


# --- ELYS DEBUG: 临时全局 exception handler,专门捕获 RecursionError,打印未截断的栈 ---
import sys as _sys
import traceback as _tb


# 字段名 → 中文显示名（仅展示给用户的关键字段，未列出的字段保留英文 loc）
_FIELD_LABELS_CN = {
    "code": "短码",
    "name": "名称",
    "description": "描述",
    "storage_quota_gb": "存储配额(GB)",
    "role": "角色",
    "reason": "原因",
    "confirm_study_id": "确认 Study ID",
    "user_id": "用户 ID",
}


def _humanize_validation_error(exc: RequestValidationError) -> str:
    """把 pydantic 校验错误数组拼成单行中文提示，比默认的 JSON 列表友好。"""
    parts: list[str] = []
    for err in exc.errors():
        loc = [str(item) for item in err.get("loc", []) if item not in ("body", "query", "path")]
        field = loc[-1] if loc else ""
        field_cn = _FIELD_LABELS_CN.get(field, field)
        msg = err.get("msg", "") or ""
        # pydantic v2 的中文校验器消息已经带"Value error, "前缀，去掉它
        msg = msg.removeprefix("Value error, ").strip()
        parts.append(f"{field_cn}：{msg}" if field_cn else msg)
    return "；".join(parts) or "请求参数校验失败"


@app.exception_handler(RequestValidationError)
async def _elys_validation_handler(request, exc: RequestValidationError):
    return CustomJSONResponse(
        status_code=422,
        content={
            "detail": _humanize_validation_error(exc),
            "errors": exc.errors(),
        },
    )


@app.exception_handler(RecursionError)
async def _elys_recursion_handler(request, exc):
    _sys.stderr.write(
        f"[ELYS-RECURSION] path={request.url.path} method={request.method}\n"
    )
    # exc.__traceback__ 在 RecursionError 下仍可能截断,但优先输出
    _sys.stderr.write("".join(_tb.format_exception(type(exc), exc, exc.__traceback__, limit=200)))
    _sys.stderr.flush()
    return CustomJSONResponse(
        status_code=500,
        content={"detail": "Internal server error: recursion (see backend logs)"},
    )


@app.exception_handler(Exception)
async def _elys_generic_handler(request, exc):
    _sys.stderr.write(
        f"[ELYS-UNHANDLED] path={request.url.path} method={request.method} type={type(exc).__name__}\n"
    )
    _sys.stderr.write("".join(_tb.format_exception(type(exc), exc, exc.__traceback__, limit=200)))
    _sys.stderr.flush()
    return CustomJSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {type(exc).__name__}"},
    )


@app.get("/api/v1/health")
def health_check():
    return {
        "status": "healthy",
        "service": "elys-api",
        "version": settings.VERSION,
        "cors_origins": cors_origins,
    }
