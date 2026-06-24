"""
Purpose: Node-spec catalog route (global, read-only) split out of the pipelines god-router.
Related: app/pipeline/registry.py, app/schemas/pipeline.py, app/routers/pipelines.py, docs_v2/2-50.

This is the first cut of breaking up routers/pipelines.py (3400+ lines). list_node_specs is the
only fully standalone endpoint (no db / study / shared helpers), so it moves out cleanly first and
establishes the multi-router-file pattern that larger sub-areas (tasks / executions / study-outputs)
will follow later.
"""

from fastapi import APIRouter, Depends, Query

from app.models import User
from app.pipeline import get_node_registry
from app.routers.auth import get_current_user
from app.schemas.pipeline import NodeSpecListResponse, NodeSpecResponse

router = APIRouter(prefix="/api/v1", tags=["工作流"])


@router.get("/pipeline/nodes", response_model=NodeSpecListResponse)
def list_node_specs(
    phase: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    registry = get_node_registry()
    specs = [NodeSpecResponse(**spec) for spec in registry.list_specs(phase=phase)]
    return NodeSpecListResponse(nodes=specs)
