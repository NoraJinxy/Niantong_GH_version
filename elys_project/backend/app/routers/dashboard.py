"""
Purpose: Expose compact Dashboard summary endpoints.
Related: app/services/dashboard_summary.py, app/schemas/dashboard.py, frontend Dashboard.vue.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.routers.auth import get_current_user
from app.schemas.dashboard import DashboardSummaryResponse
from app.services.dashboard_summary import build_dashboard_summary


router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return build_dashboard_summary(db, current_user=current_user)
