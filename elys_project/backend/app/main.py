"""
Purpose: Create the FastAPI application, register routers, configure CORS, and expose health checks.
Related: app/config.py, app/routers/*, docs_v2/2-50 and docs_v2/7-10.
"""

import json
import uuid

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
