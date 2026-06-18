"""
Purpose: Load application settings from environment variables for API, database, storage, CORS, and Celery.
Related: deploy/profiles/*.env, app/main.py, app/database.py, app/tasks/celery_app.py.
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "念析 (ELYS)"
    VERSION: str = "1.0.0"
    DEBUG: bool = False

    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "elys"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    CELERY_WORKFLOW_QUEUE: str = "workflow.default"
    PIPELINE_EXECUTION_MODE: str = "auto"
    CELERY_WORKER_PING_TIMEOUT_SECONDS: float = 0.5
    # auto 模式下「探测 worker 是否在线」结果的缓存有效期（秒）：TTL 内的连续运行复用
    # 上次探测、跳过 ping，省掉每次运行的固定开销。设 0 关闭缓存、恢复每次都 ping。
    CELERY_WORKER_PING_CACHE_TTL_SECONDS: float = 5.0

    STUDIES_DIR: str = "/mnt/elys_data/studies"
    ELYS_STORAGE_ROOT: str = "/mnt/elys_data/storage"
    DATASETS_STORAGE_ROOT: str = "/mnt/elys_data/storage/datasets"
    STUDIES_STORAGE_ROOT: str = "/mnt/elys_data/storage/studies"
    TRASH_STORAGE_ROOT: str = "/mnt/elys_data/storage/trash"
    CORS_ORIGINS: str = (
        "http://elysbrain.site,"
        "https://elysbrain.site,"
        "http://www.elysbrain.site,"
        "https://www.elysbrain.site,"
        "http://data.elysbrain.site,"
        "https://data.elysbrain.site,"
        "http://8.135.40.150,"
        "https://8.135.40.150,"
        "http://8.135.52.84,"
        "https://8.135.52.84,"
        "http://8.135.57.42,"
        "https://8.135.57.42,"
        "http://localhost:3000,"
        "http://localhost:5173"
    )

    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
