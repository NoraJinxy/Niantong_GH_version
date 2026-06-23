"""
Purpose: Load application settings from environment variables for API, database, storage, CORS, and Celery.
Related: deploy/profiles/*.env, app/main.py, app/database.py, app/tasks/celery_app.py.
"""

import logging
from functools import lru_cache
from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

INSECURE_DEFAULT_SECRET_KEY = "change-me-in-production"


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

    # ===== 存储后端（OSS 迁移 A 阶段）=====
    # STORAGE_BACKEND=local 时一切照旧（读写本地 FS）；=oss 时经 StorageService 走对象存储。
    # 凭证只从环境变量注入（部署时写进后端服务 env / 用 RAM 角色），绝不写进仓库。
    STORAGE_BACKEND: str = "local"                         # local | oss
    OSS_ENDPOINT: str = ""                                 # 计算服上用内网域名 oss-cn-shenzhen-internal.aliyuncs.com
    OSS_BUCKET: str = ""                                   # 例：elys-oss-test1
    OSS_ACCESS_KEY_ID: str = ""                            # 走 env / RAM 角色，勿入库
    OSS_ACCESS_KEY_SECRET: str = ""                        # 走 env / RAM 角色，勿入库
    OSS_PREFIX: str = ""                                   # 可选：桶内统一前缀（多环境共用一桶时隔离）
    # 放 storage 根下：deploy.sh 已把 /mnt/elys_data/storage chown www-data + chmod 2775，worker 可在其下建子目录；
    # /mnt/elys_data/scratch 那种新顶级目录 www-data 无权创建(父 /mnt/elys_data 属 root)→ Permission denied。
    # 顺带随 RESET_STORAGE 一起被清(find rm storage 根下)，scratch 每轮干净。
    OSS_SCRATCH_ROOT: str = "/mnt/elys_data/storage/oss_scratch"   # oss 后端把对象下载到这里供 MNE 读

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

    SECRET_KEY: str = INSECURE_DEFAULT_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

    @model_validator(mode="after")
    def _guard_secret_key(self):
        if self.SECRET_KEY == INSECURE_DEFAULT_SECRET_KEY:
            message = (
                "INSECURE DEFAULT SECRET_KEY: SECRET_KEY 仍是占位默认值 "
                f"'{INSECURE_DEFAULT_SECRET_KEY}'，JWT 将用公开已知密钥签名、任意 token 可被伪造。"
                "请通过环境变量注入真实 SECRET_KEY。"
            )
            if self.DEBUG:
                logger.warning(message)
            else:
                raise RuntimeError(message)
        return self


@lru_cache()
def get_settings() -> Settings:
    return Settings()
