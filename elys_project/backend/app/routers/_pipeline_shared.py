"""
Purpose: Shared helpers for the pipelines router area, extracted so the god-router
(routers/pipelines.py) can be split into focused sub-routers.
Related: app/routers/pipelines.py, app/routers/pipeline_definitions.py, app/routers/study_outputs.py, docs_v2/2-50.

Only CROSS-sub-area helpers live here: study-access guards, the pipeline 404-getter and response
converter (used by both Pipelines-CRUD and Executions), and the StudyOutput response converter
(used by both the execution-detail area and the study-outputs area).
"""

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import PipelineDefinition, Study, StudyOutput, User
from app.schemas.pipeline import PipelineResponse
from app.schemas.study_output import StudyOutputResponse
from app.services.study_access import require_study_read, require_study_run, require_study_write


def get_study_for_read(study_id: str, db: Session, user: User) -> Study:
    study = db.query(Study).filter(Study.id == study_id).first()
    return require_study_read(study, db, user)


def get_study_for_write(study_id: str, db: Session, user: User) -> Study:
    study = db.query(Study).filter(Study.id == study_id).first()
    return require_study_write(study, db, user)


def get_study_for_run(study_id: str, db: Session, user: User) -> Study:
    study = db.query(Study).filter(Study.id == study_id).first()
    return require_study_run(study, db, user)


def count_nodes(definition_json: dict[str, Any]) -> int:
    graph = definition_json.get("graph") or {}
    nodes = graph.get("nodes") or []
    return len(nodes) if isinstance(nodes, list) else 0


def get_pipeline_or_404(db: Session, study_id: str, pipeline_id: int) -> PipelineDefinition:
    pipeline = (
        db.query(PipelineDefinition)
        .filter(
            PipelineDefinition.study_id == study_id,
            PipelineDefinition.id == pipeline_id,
            PipelineDefinition.status != "deleted",
        )
        .first()
    )
    if pipeline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")
    return pipeline


def pipeline_to_response(pipeline: PipelineDefinition) -> PipelineResponse:
    return PipelineResponse(
        id=pipeline.id,
        study_id=pipeline.study_id,
        name=pipeline.name,
        description=pipeline.description,
        definition_json=pipeline.definition_json,
        node_count=pipeline.node_count,
        version=pipeline.version,
        is_template=pipeline.is_template,
        status=pipeline.status,
        created_by=str(pipeline.created_by) if pipeline.created_by else None,
        created_at=pipeline.created_at,
        updated_at=pipeline.updated_at,
    )


def _to_str_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def study_output_to_response(dataset: StudyOutput) -> StudyOutputResponse:
    return StudyOutputResponse(
        id=str(dataset.id),
        study_id=dataset.study_id,
        produced_by_execution_id=str(dataset.produced_by_execution_id) if dataset.produced_by_execution_id else None,
        produced_by_job_id=str(dataset.produced_by_job_id) if dataset.produced_by_job_id else None,
        produced_by_node_id=dataset.produced_by_node_id,
        produced_by_node_type=dataset.produced_by_node_type,
        produced_by_params=dataset.produced_by_params or {},
        upstream_dataset_ids=_to_str_list(dataset.upstream_dataset_ids),
        upstream_recording_ids=_to_str_list(dataset.upstream_recording_ids),
        data_type=dataset.data_type,
        subject_id=str(dataset.subject_id) if dataset.subject_id else None,
        bids_subject_id=dataset.bids_subject_id,
        session=dataset.session,
        task=dataset.task,
        run_label=dataset.run_label,
        condition=dataset.condition,
        display_name=dataset.display_name,
        description=dataset.description,
        tags=_to_str_list(dataset.tags),
        storage_uri=dataset.storage_uri or "",
        logical_path=dataset.logical_path,
        file_role=dataset.file_role,
        file_size=dataset.file_size,
        sha256=dataset.sha256,
        mime_type=dataset.mime_type,
        keep=bool(dataset.keep),
        cache_eligible=bool(dataset.cache_eligible),
        retention_expires_at=dataset.retention_expires_at,
        preview_json=dataset.preview_json or {},
        created_at=dataset.created_at,
        created_by=str(dataset.created_by) if dataset.created_by else None,
        updated_at=dataset.updated_at,
        deleted_at=dataset.deleted_at,
    )
