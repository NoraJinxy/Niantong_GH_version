"""
Purpose: Admin ops console endpoints — platform-wide runtime/load/health and audit query (read-only, Phase 1).
Related: app/services/admin_ops.py, app/routers/auth.py, frontend AdminConsolePage.vue.

权限：全部端点经 require_admin（has_role("admin")）守卫。第一期纯只读监测，无任何干预动作。
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.routers.auth import get_current_user
from app.services import admin_ops

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.has_role("admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_user


@router.get("/overview")
def get_overview(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """总览：实体计数数字墙 + 执行状态分布 + 健康灯（API/DB/Redis/worker/磁盘）+ 告警摘要。"""
    return admin_ops.build_admin_overview(db, get_settings())


@router.get("/runtime")
def get_runtime(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """运行与负荷：全平台执行队列实时列表 + worker active/reserved + 卡死执行与锁 + 系统资源 + 最近失败。"""
    return admin_ops.build_admin_runtime(db, get_settings())


@router.get("/audit-events")
def get_audit_events(
    action: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    resource_kind: str | None = Query(default=None),
    study_id: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """审计事件查询：按 action / actor / resource_kind / study / 时间窗过滤，翻页。"""
    return admin_ops.query_audit_events(
        db,
        action=action,
        actor_id=actor_id,
        resource_kind=resource_kind,
        study_id=study_id,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )


@router.get("/audit-events/facets")
def get_audit_facets(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """审计筛选下拉用：去重后的 action 与 resource_kind 列表。"""
    return admin_ops.audit_facets(db)
