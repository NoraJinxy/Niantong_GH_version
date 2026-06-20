"""
Purpose: 沿链路解析「某节点输入端可用 condition」的路由（Epoch / ERP / TFR / PSD 选择器用）。
Related: app/pipeline/condition_resolver.py, app/routers/pipeline_load_data.py.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.pipeline.condition_resolver import resolve_node_conditions
from app.routers.auth import get_current_user
from app.routers._pipeline_shared import get_study_for_read
from app.schemas.pipeline import ConditionResolveRequest, ConditionResolveResponse

router = APIRouter(prefix="/api/v1", tags=["工作流"])


@router.post(
    "/studies/{study_id}/pipeline/resolve-conditions",
    response_model=ConditionResolveResponse,
)
def resolve_conditions(
    study_id: str,
    payload: ConditionResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    return resolve_node_conditions(
        db=db,
        study=study,
        graph=payload.graph,
        node_id=payload.node_id,
    )
