"""
Purpose: LoadData selection resolver route, split out of routers/pipelines.py.
Related: app/pipeline/load_data.py, app/routers/_pipeline_shared.py, docs_v2/2-50.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.pipeline.load_data import resolve_load_data_selection
from app.routers.auth import get_current_user
from app.routers._pipeline_shared import get_study_for_read
from app.schemas.pipeline import LoadDataResolveRequest, LoadDataResolveResponse

router = APIRouter(prefix="/api/v1", tags=["工作流"])


# fif_abs_path 是服务器绝对路径，引擎要靠它（保留在模型里供 dispatcher 喂引擎），但前端只需
# fif_exists 布尔 + storage_uri/logical_path 逻辑标识，故从本端点响应里排除、不泄漏服务器路径。
@router.post(
    "/studies/{study_id}/pipeline/load-data/resolve",
    response_model=LoadDataResolveResponse,
    response_model_exclude={"data_infos": {"__all__": {"fif_abs_path"}}},
)
def resolve_load_data(
    study_id: str,
    payload: LoadDataResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    return resolve_load_data_selection(
        db=db,
        study=study,
        params=payload.model_dump(mode="json"),
        node_id=payload.node_id,
    )
