"""
Purpose: Configure or run Celery background tasks for asynchronous Pipeline execution.
Related: app/pipeline/background.py, app/routers/pipelines.py, deploy/profiles/*.env, docs_v2/2-60.
"""

from __future__ import annotations

from urllib.parse import quote_plus

from celery import Celery

from app.config import get_settings


def _redis_url() -> str:
    settings = get_settings()
    password = f":{quote_plus(settings.REDIS_PASSWORD)}@" if settings.REDIS_PASSWORD else ""
    return f"redis://{password}{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"


settings = get_settings()
broker_url = settings.CELERY_BROKER_URL or _redis_url()
result_backend = settings.CELERY_RESULT_BACKEND or broker_url

celery_app = Celery(
    "elys",
    broker=broker_url,
    backend=result_backend,
    include=["app.tasks.pipeline_tasks", "app.tasks.file_tasks"],
)

celery_app.conf.update(
    accept_content=["json"],
    enable_utc=True,
    result_serializer="json",
    task_default_queue=settings.CELERY_WORKFLOW_QUEUE,
    task_routes={
        "app.tasks.pipeline_tasks.run_pipeline_task": {"queue": settings.CELERY_WORKFLOW_QUEUE},
        "app.tasks.file_tasks.run_file_task": {"queue": settings.CELERY_WORKFLOW_QUEUE},
    },
    task_serializer="json",
    task_track_started=True,
    task_soft_time_limit=1800,
    task_time_limit=2100,
    timezone="UTC",
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        # 每天一次：全局软删过期缓存(cleanup) + 物理清盘超期回收站(GC)
        # 需部署侧起 celery beat 进程（celery -A app.tasks.celery_app beat）才会触发
        "storage-maintenance-daily": {
            "task": "app.tasks.file_tasks.run_storage_maintenance",
            "schedule": 24 * 60 * 60,
        },
    },
)
