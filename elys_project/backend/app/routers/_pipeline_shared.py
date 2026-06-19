"""
Purpose: Shared helpers for the pipelines router area, extracted so the god-router
(routers/pipelines.py) can be split into focused sub-routers.
Related: app/routers/pipelines.py, app/routers/pipeline_definitions.py, app/routers/study_outputs.py, docs_v2/2-50.

Only CROSS-sub-area helpers live here: study-access guards, the pipeline 404-getter and response
converter (used by both Pipelines-CRUD and Executions), and the StudyOutput response converter
(used by both the execution-detail area and the study-outputs area).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import (
    ExecutionOutput,
    PipelineDefinition,
    PipelineExecution,
    Study,
    StudyOutput,
    User,
)
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


@dataclass(frozen=True)
class PipelineAttribution:
    """某条结果的来源工作流标识，由 produced_by_execution_id 解析而来。

    结果页要回答「这条结果是哪个工作流、哪一版、第几次运行产出的」，但 StudyOutput 行只存
    produced_by_execution_id。这里把 execution → pipeline 的归属信息打包，由列表端点批量查好后
    传给 study_output_to_response，避免逐行查库（N+1）。
    """

    pipeline_id: int | None = None
    pipeline_name: str | None = None
    pipeline_version: int | None = None
    execution_seq: int | None = None


def pipeline_attribution_by_execution(
    db: Session, execution_ids: Iterable[Any]
) -> dict[Any, PipelineAttribution]:
    """批量把 execution_id 映射到来源工作流（pipeline 名/版本/运行序号）。

    一次 IN 查询取回所有相关 execution 的 (pipeline_id, name, version, seq)，键为 execution.id
    （与 StudyOutput.produced_by_execution_id 同为 UUID 对象，可直接 .get 命中）。
    """
    ids = [eid for eid in {*execution_ids} if eid]
    if not ids:
        return {}
    rows = (
        db.query(
            PipelineExecution.id,
            PipelineExecution.pipeline_id,
            PipelineExecution.pipeline_version,
            PipelineExecution.execution_seq,
            PipelineDefinition.name,
        )
        .outerjoin(
            PipelineDefinition, PipelineDefinition.id == PipelineExecution.pipeline_id
        )
        .filter(PipelineExecution.id.in_(ids))
        .all()
    )
    return {
        exec_id: PipelineAttribution(
            pipeline_id=pipeline_id,
            pipeline_name=name,
            pipeline_version=pipeline_version,
            execution_seq=execution_seq,
        )
        for exec_id, pipeline_id, pipeline_version, execution_seq, name in rows
    }


def study_output_to_response(
    dataset: StudyOutput,
    *,
    attribution: tuple[str | None, str | None] | None = None,
    pipeline_info: PipelineAttribution | None = None,
) -> StudyOutputResponse:
    """把 StudyOutput 行序列化成响应。

    attribution 非空时，用 (execution_id, job_id) 覆盖 produced_by_execution_id / produced_by_job_id —
    用于「某次执行视角」的列表（运行面板/执行详情）：一条因 content-addressed 去重 / 缓存命中而被复用
    的输出，其 study_outputs.produced_by_* 指向 canonical 首产者，但在本次执行视角下应归属本次执行的
    job，运行面板才能正确按 job 统计与分组。attribution 为 None 时保持行自身的 canonical 血缘。
    """
    if attribution is not None:
        produced_by_execution_id, produced_by_job_id = attribution
    else:
        produced_by_execution_id = str(dataset.produced_by_execution_id) if dataset.produced_by_execution_id else None
        produced_by_job_id = str(dataset.produced_by_job_id) if dataset.produced_by_job_id else None
    return StudyOutputResponse(
        id=str(dataset.id),
        study_id=dataset.study_id,
        produced_by_execution_id=produced_by_execution_id,
        produced_by_job_id=produced_by_job_id,
        produced_by_node_id=dataset.produced_by_node_id,
        produced_by_node_type=dataset.produced_by_node_type,
        produced_by_params=dataset.produced_by_params or {},
        upstream_dataset_ids=_to_str_list(dataset.upstream_dataset_ids),
        upstream_recording_ids=_to_str_list(dataset.upstream_recording_ids),
        pipeline_id=pipeline_info.pipeline_id if pipeline_info else None,
        pipeline_name=pipeline_info.pipeline_name if pipeline_info else None,
        pipeline_version=pipeline_info.pipeline_version if pipeline_info else None,
        execution_seq=pipeline_info.execution_seq if pipeline_info else None,
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


def execution_scoped_outputs(
    db: Session,
    *,
    study_id: str,
    execution_id: Any,
    include_deleted: bool = False,
) -> list[tuple[StudyOutput, str | None]]:
    """列出「某次执行产出或复用」的 study_outputs（经 execution_outputs 关联表）。

    返回 [(StudyOutput, job_id_str | None)]，每条 output 去重保留一条边（优先 created，
    即首产者那条），job_id 为该边对应的 job —— 供「某次执行视角」按 job 统计/分组。

    与按 produced_by_execution_id 直查的区别：去重命中 / 缓存命中而被复用的输出，其
    produced_by_execution_id 指向首产执行，本表却为本次执行也记了 reused 边，故这里能查到。
    """
    rows = (
        db.query(StudyOutput, ExecutionOutput.job_id, ExecutionOutput.relation)
        .join(ExecutionOutput, ExecutionOutput.study_output_id == StudyOutput.id)
        .filter(
            ExecutionOutput.execution_id == execution_id,
            StudyOutput.study_id == study_id,
        )
    )
    if not include_deleted:
        rows = rows.filter(StudyOutput.deleted_at.is_(None))
    # relation 升序让 'created' 排在 'reused' 前，去重时优先保留首产者那条边的 job 归属
    rows = rows.order_by(ExecutionOutput.relation.asc(), ExecutionOutput.created_at.asc()).all()

    seen: set[Any] = set()
    picked: list[tuple[StudyOutput, str | None]] = []
    for output, job_id, _relation in rows:
        if output.id in seen:
            continue
        seen.add(output.id)
        picked.append((output, str(job_id) if job_id else None))
    # 展示顺序按 output 产出时间，稳定可读
    picked.sort(key=lambda pair: (pair[0].created_at or datetime.min, str(pair[0].id)))
    return picked
