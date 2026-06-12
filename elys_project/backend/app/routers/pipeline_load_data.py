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


@router.post("/studies/{study_id}/pipeline/load-data/resolve", response_model=LoadDataResolveResponse)
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
