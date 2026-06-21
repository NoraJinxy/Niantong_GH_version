"""
Purpose: StudyOutputs (研究项结果数据) sub-router, split out of routers/pipelines.py.
Related: app/routers/_pipeline_shared.py, app/routers/pipelines.py, app/models/study_output.py, docs_v2/2-50.

Covers StudyOutput CRUD + retention + preview/timeseries/download. The cleanup/gc task endpoints stay
in pipelines.py for now because they depend on the shared create_and_dispatch_file_task; the
execution-scoped outputs list (list_pipeline_execution_study_outputs) also stays there.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

try:
    from fastapi.responses import FileResponse
except Exception:  # pragma: no cover - lightweight test stubs do not provide fastapi.responses
    class FileResponse:  # type: ignore[no-redef]
        def __init__(self, path, **kwargs):
            self.path = path
            self.kwargs = kwargs

from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Study, StudyOutput, User
from app.schemas.study_output import (
    StudyOutputBatchUpdate,
    StudyOutputListResponse,
    StudyOutputPreviewResponse,
    StudyOutputResponse,
    StudyOutputUpdate,
)
from app.pipeline.previews import (
    MAX_EVOKED_CHANNELS,
    StudyOutputPreviewError,
    build_study_output_preview,
    resolve_study_output_path,
    validate_study_output_file,
)
from app.pipeline.timeseries import build_auto_artifacts, build_timeseries
from app.pipeline.psd_view import build_psd_lines
from app.pipeline.stat_view import build_stat_view
from app.pipeline.tfr_view import build_tfr_cube, build_tfr_heatmap, build_tfr_topomap
from app.pipeline.ica_inspect import build_ica_components, build_ica_component_detail, build_ica_labels, build_ica_preview
from app.pipeline.save_settings import retention_expiry_after_user_action
from app.services.audit_events import record_audit_event
from app.services.execution_dependencies import ArtifactDependencyError, assert_artifact_can_be_deleted
from app.routers.auth import get_current_user
from app.routers._pipeline_shared import (
    get_study_for_read,
    get_study_for_write,
    pipeline_attribution_by_execution,
    study_output_to_response,
)


router = APIRouter(prefix="/api/v1", tags=["工作流"])


# ===================== 专属 helper =====================

def get_study_output_or_404(db: Session, study_id: str, dataset_id: UUID) -> StudyOutput:
    dataset = (
        db.query(StudyOutput)
        .filter(StudyOutput.study_id == study_id, StudyOutput.id == dataset_id)
        .first()
    )
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Derived dataset not found")
    return dataset


def record_study_output_action_audit(
    db: Session,
    *,
    study: Study,
    dataset: StudyOutput,
    current_user: User,
    action: str,
    reason: str | None,
    operation: str,
    previous: dict[str, Any],
    blocked: bool = False,
    dependencies: list[dict[str, Any]] | None = None,
) -> None:
    record_audit_event(
        db,
        study_id=study.id,
        action=action,
        actor_id=current_user.id,
        resource_kind="study_output",
        resource_id=dataset.id,
        resource_label=dataset.display_name or dataset.storage_uri,
        metadata={
            "operation": operation,
            "previous": previous,
            "keep": bool(dataset.keep),
            "deleted": dataset.deleted_at is not None,
            "reason": reason,
            "execution_id": str(dataset.produced_by_execution_id) if dataset.produced_by_execution_id else None,
            "blocked": blocked,
            "dependencies": dependencies or [],
        },
    )


def apply_study_output_retention_action(
    db: Session,
    *,
    study: Study,
    dataset: StudyOutput,
    current_user: User,
    keep: bool | None = None,
    deleted: bool | None = None,
    action: str,
    reason: str | None = None,
    operation: str = "retention_update",
) -> StudyOutput:
    """统一改 keep（保留意图）/ deleted（回收站软删），两者正交、按传入项分别应用。

    - deleted=True：删到回收站（先做下游依赖检查，被引用则 409 整体不改）
    - deleted=False：从回收站恢复（GC 已清盘的行磁盘文件已没了，恢复一律 409）
    - keep=True：用户保留（清掉缓存 TTL、永不自动清）
    - keep=False：交回系统管理（按缓存档 / 宽限期补 TTL，到期由每日 cleanup 回收）

    凡是动作后行处于 keep=false 活跃态的，都重算 retention_expires_at——否则
    NULL / 已过期的 TTL 会让下一轮每日 cleanup（tasks/file_tasks.py 的
    run_study_output_cleanup 把两者都视为立即可回收）马上再次软删，用户的
    「恢复 / 不保留」操作形同无效。
    """
    previous = {"keep": bool(dataset.keep), "deleted": dataset.deleted_at is not None}
    restoring = deleted is False

    # 1) 软删 / 恢复
    if deleted is not None:
        if deleted:
            try:
                assert_artifact_can_be_deleted(db, artifact=dataset)
            except ArtifactDependencyError as exc:
                record_study_output_action_audit(
                    db,
                    study=study,
                    dataset=dataset,
                    current_user=current_user,
                    action=f"{action}.blocked",
                    reason=reason,
                    operation=operation,
                    previous=previous,
                    blocked=True,
                    dependencies=exc.blockers,
                )
                db.commit()
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.to_detail()) from exc
            dataset.deleted_at = datetime.utcnow()
        else:
            if dataset.purged_at is not None:
                # GC 已物理删盘：恢复只会得到"活跃但磁盘无文件"的幽灵行（预览/下载必挂），
                # 且占用 (study_id, sha256) 唯一索引、挡住同内容输出再登记。
                record_study_output_action_audit(
                    db,
                    study=study,
                    dataset=dataset,
                    current_user=current_user,
                    action=f"{action}.blocked",
                    reason=reason,
                    operation=operation,
                    previous=previous,
                    blocked=True,
                )
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "OUTPUT_PURGED",
                        "message": "该输出已物理清盘（磁盘文件已删除），无法恢复。",
                        "study_output_id": str(dataset.id),
                        "purged_at": dataset.purged_at.isoformat(),
                    },
                )
            dataset.deleted_at = None

    # 2) 保留意图 + TTL 重算
    if keep is not None:
        dataset.keep = keep
        dataset.retention_expires_at = retention_expiry_after_user_action(
            keep=keep, cache_eligible=bool(dataset.cache_eligible)
        )
    elif restoring and not dataset.keep:
        dataset.retention_expires_at = retention_expiry_after_user_action(
            keep=False, cache_eligible=bool(dataset.cache_eligible)
        )

    dataset.updated_at = datetime.utcnow()
    record_study_output_action_audit(
        db,
        study=study,
        dataset=dataset,
        current_user=current_user,
        action=action,
        reason=reason,
        operation=operation,
        previous=previous,
    )
    return dataset


# ===================== endpoints =====================

@router.get(
    "/studies/{study_id}/outputs",
    response_model=StudyOutputListResponse,
)
def list_study_outputs(
    study_id: str,
    execution_ids: list[str] | None = Query(default=None),
    node_types: list[str] | None = Query(default=None),
    data_types: list[str] | None = Query(default=None),
    bids_subject_ids: list[str] | None = Query(default=None),
    sessions: list[str] | None = Query(default=None),
    tasks: list[str] | None = Query(default=None),
    conditions: list[str] | None = Query(default=None),
    tags: list[str] | None = Query(default=None),
    keep: bool | None = Query(default=None),
    include_deleted: bool = Query(default=False),
    visible_only: bool = Query(
        default=False,
        description="只返回「有意义」的结果：keep / cache_eligible / 已删除（结果页用，避免拉回一堆隐藏的纯临时中间产物）。",
    ),
    include_cross_study: bool = Query(
        default=False,
        description="Phase 3 (docs_v2/3-25): 列出其他 Study 已发布且共享的结果 (lifecycle_state='published' AND visibility='shared')",
    ),
    limit: int = Query(default=200, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """跨执行（Execution）列出研究项的结果，支持多维筛选。用于 /results 页面。

    Phase 3 (docs_v2/3-25):
        include_cross_study=True 时,在本 Study 的结果之外,附加列出其他 Study
        中 lifecycle_state='published' AND visibility='shared' 的结果,用于
        新建 Pipeline 时选择跨 Study 的上游结果。
    """
    from sqlalchemy import and_ as _and, or_ as _or

    study = get_study_for_read(study_id, db, current_user)
    if include_cross_study:
        scope_filter = _or(
            StudyOutput.study_id == study.id,
            _and(
                StudyOutput.study_id != study.id,
                StudyOutput.lifecycle_state == "published",
                StudyOutput.visibility == "shared",
            ),
        )
        query = db.query(StudyOutput).filter(scope_filter)
    else:
        query = db.query(StudyOutput).filter(StudyOutput.study_id == study.id)
    if not include_deleted:
        query = query.filter(StudyOutput.deleted_at.is_(None))
    if execution_ids:
        query = query.filter(StudyOutput.produced_by_execution_id.in_(execution_ids))
    if node_types:
        query = query.filter(StudyOutput.produced_by_node_type.in_(node_types))
    if data_types:
        query = query.filter(StudyOutput.data_type.in_(data_types))
    if bids_subject_ids:
        query = query.filter(StudyOutput.bids_subject_id.in_(bids_subject_ids))
    if sessions:
        query = query.filter(StudyOutput.session.in_(sessions))
    if tasks:
        query = query.filter(StudyOutput.task.in_(tasks))
    if conditions:
        query = query.filter(StudyOutput.condition.in_(conditions))
    if keep is not None:
        query = query.filter(StudyOutput.keep.is_(keep))
    if visible_only:
        # 结果页只展示 keep / cache / 已删除；纯临时中间产物（keep=False 且 cache=False）
        # 占绝大多数却从不显示，服务端先滤掉，避免序列化 + 传输上百行废料拖慢加载。
        query = query.filter(
            _or(
                StudyOutput.keep.is_(True),
                StudyOutput.cache_eligible.is_(True),
                StudyOutput.deleted_at.isnot(None),
            )
        )
    if tags:
        # JSONB contains: 任一 tag 匹配即可
        from sqlalchemy import or_ as _or
        tag_filters = [StudyOutput.tags.contains([tag]) for tag in tags]
        query = query.filter(_or(*tag_filters))

    total = query.count()
    datasets = (
        query.order_by(StudyOutput.created_at.desc(), StudyOutput.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    # 批量解析来源工作流（哪个工作流·哪一版·第几次运行），结果页据此展示与筛选；一次 IN 查询避免 N+1。
    pipeline_info = pipeline_attribution_by_execution(
        db, (item.produced_by_execution_id for item in datasets)
    )
    return StudyOutputListResponse(
        study_outputs=[
            study_output_to_response(
                item,
                pipeline_info=pipeline_info.get(item.produced_by_execution_id),
            )
            for item in datasets
        ],
        total=total,
    )


@router.get(
    "/studies/{study_id}/outputs/{dataset_id}",
    response_model=StudyOutputResponse,
)
def get_study_output(
    study_id: str,
    dataset_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    dataset = get_study_output_or_404(db, study.id, dataset_id)
    return study_output_to_response(dataset)


@router.patch(
    "/studies/{study_id}/outputs/{dataset_id}",
    response_model=StudyOutputResponse,
)
def update_study_output(
    study_id: str,
    dataset_id: UUID,
    payload: StudyOutputUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """统一的 PATCH 入口：可改 display_name / description / tags / keep / deleted。"""
    study = get_study_for_write(study_id, db, current_user)
    dataset = get_study_output_or_404(db, study.id, dataset_id)

    if payload.display_name is not None:
        dataset.display_name = payload.display_name.strip() or None
    if payload.description is not None:
        dataset.description = payload.description.strip() or None
    if payload.tags is not None:
        seen: set[str] = set()
        cleaned: list[str] = []
        for tag in payload.tags:
            text = str(tag).strip()
            if text and text not in seen:
                seen.add(text)
                cleaned.append(text)
        dataset.tags = cleaned
    if payload.keep is not None or payload.deleted is not None:
        apply_study_output_retention_action(
            db,
            study=study,
            dataset=dataset,
            current_user=current_user,
            keep=payload.keep,
            deleted=payload.deleted,
            action="study_output.retention",
            reason=payload.reason,
        )
    dataset.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(dataset)
    return study_output_to_response(dataset)


@router.post(
    "/studies/{study_id}/outputs/batch-update",
    response_model=StudyOutputListResponse,
)
def batch_update_study_outputs(
    study_id: str,
    payload: StudyOutputBatchUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """对多个 study_outputs 应用同一组改动。用于 /results 页批量打标签 / 改保留策略。"""
    study = get_study_for_write(study_id, db, current_user)
    datasets = (
        db.query(StudyOutput)
        .filter(StudyOutput.study_id == study.id, StudyOutput.id.in_(payload.ids))
        .all()
    )
    found_ids = {str(d.id) for d in datasets}
    missing = [pid for pid in payload.ids if pid not in found_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "DERIVED_DATASET_BATCH_NOT_FOUND",
                "message": "部分结果不存在",
                "missing_ids": missing,
            },
        )
    upd = payload.update
    # 事务原子性：apply_study_output_retention_action 命中依赖 blocker 时会先 db.commit()
    # 再抛 409。批量循环里若第 N 条撞 blocker，会把前 N-1 条的改动一并提交后抛错，造成
    # "部分成功 + 无回滚"。因此当目标是 deleted 时，先全量预检所有 blocker，任一被挡就
    # 在改动任何数据之前一次性 409，循环内便不会再触发 commit-then-raise。
    if upd.deleted is True:
        blocked: list[dict[str, Any]] = []
        for ds in datasets:
            try:
                assert_artifact_can_be_deleted(db, artifact=ds)
            except ArtifactDependencyError as exc:
                blocked.append(
                    {"study_output_id": str(ds.id), "dependencies": exc.blockers}
                )
        if blocked:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "DERIVED_DATASET_BATCH_BLOCKED",
                    "message": "部分输出被下游引用，无法删除；批量操作已整体取消。",
                    "blocked": blocked,
                },
            )
    # 同理：恢复（deleted=False）撞到 GC 已清盘的行时，单条路径是 commit-then-raise，
    # 批量循环中途触发会部分成功；先全量预检 purged_at，任一命中整体 409。
    if upd.deleted is False:
        purged_ids = [str(ds.id) for ds in datasets if ds.purged_at is not None]
        if purged_ids:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "OUTPUT_BATCH_PURGED",
                    "message": "部分输出已物理清盘（磁盘文件已删除），无法恢复；批量操作已整体取消。",
                    "purged_ids": purged_ids,
                },
            )
    for ds in datasets:
        if upd.display_name is not None:
            ds.display_name = upd.display_name.strip() or None
        if upd.description is not None:
            ds.description = upd.description.strip() or None
        if upd.tags is not None:
            seen: set[str] = set()
            cleaned: list[str] = []
            for tag in upd.tags:
                text = str(tag).strip()
                if text and text not in seen:
                    seen.add(text)
                    cleaned.append(text)
            ds.tags = cleaned
        if upd.keep is not None or upd.deleted is not None:
            apply_study_output_retention_action(
                db,
                study=study,
                dataset=ds,
                current_user=current_user,
                keep=upd.keep,
                deleted=upd.deleted,
                action="study_output.batch.retention",
                reason=upd.reason,
            )
        ds.updated_at = datetime.utcnow()
    db.commit()
    for ds in datasets:
        db.refresh(ds)
    return StudyOutputListResponse(
        study_outputs=[study_output_to_response(ds) for ds in datasets],
        total=len(datasets),
    )


@router.get(
    "/studies/{study_id}/outputs/{dataset_id}/preview",
    response_model=StudyOutputPreviewResponse,
)
def get_study_output_preview(
    study_id: str,
    dataset_id: UUID,
    max_channels: int = Query(default=MAX_EVOKED_CHANNELS, ge=1, le=256),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    dataset = get_study_output_or_404(db, study.id, dataset_id)
    if dataset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DERIVED_DATASET_DELETED", "message": "输出已删除，预览不可用。"},
        )
    try:
        preview = build_study_output_preview(study, dataset, sample_channels=max_channels)
    except StudyOutputPreviewError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "study_output_id": str(dataset_id)},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "DERIVED_DATASET_PREVIEW_ENGINE_UNAVAILABLE", "message": str(exc)},
        ) from exc

    dataset.preview_json = preview["preview_json"]
    dataset.updated_at = datetime.utcnow()
    db.commit()
    # build_study_output_preview 仍以 artifact_id 为字段名输出；映射到 study_output_id
    return StudyOutputPreviewResponse(
        study_output_id=preview.get("artifact_id") or str(dataset.id),
        study_id=preview.get("study_id") or study.id,
        produced_by_execution_id=preview.get("execution_id"),
        produced_by_job_id=preview.get("job_id"),
        data_type=preview.get("data_type") or dataset.data_type,
        storage_uri=preview.get("storage_uri"),
        sha256=preview.get("sha256"),
        keep=bool(preview.get("keep")),
        preview_json=preview.get("preview_json") or {},
        observe_route=preview.get("observe_route") or "/observe",
        observe_query=preview.get("observe_query") or {},
        generated_at=preview.get("generated_at") or datetime.utcnow(),
    )


@router.get("/studies/{study_id}/outputs/{dataset_id}/timeseries")
def get_study_output_timeseries(
    study_id: str,
    dataset_id: UUID,
    tmin: float | None = Query(default=None),
    tmax: float | None = Query(default=None),
    index: int | None = Query(default=None, ge=0),
    max_points: int = Query(default=2000, ge=50, le=8000),
    max_channels: int = Query(default=64, ge=1, le=256),
    format: str = Query(default="json"),
    l_freq: float | None = Query(default=None, description="高通 Hz（view-only 瞬时滤波，不存储）"),
    h_freq: float | None = Query(default=None, description="低通 Hz（view-only）"),
    notch: float | None = Query(default=None, description="陷波 Hz（view-only）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    dataset = get_study_output_or_404(db, study.id, dataset_id)
    if dataset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DERIVED_DATASET_DELETED", "message": "输出已删除，时域数据不可用。"},
        )
    try:
        payload = build_timeseries(
            study,
            dataset,
            tmin=tmin,
            tmax=tmax,
            index=index,
            max_points=max_points,
            max_channels=max_channels,
            l_freq=l_freq,
            h_freq=h_freq,
            notch=notch,
        )
        if str(format).lower() == "binary":
            from fastapi import Response
            from app.pipeline.timeseries import encode_timeseries_binary

            return Response(content=encode_timeseries_binary(payload), media_type="application/octet-stream")
        return payload
    except StudyOutputPreviewError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "study_output_id": str(dataset_id)},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "DERIVED_DATASET_TIMESERIES_ENGINE_UNAVAILABLE", "message": str(exc)},
        ) from exc


@router.post("/studies/{study_id}/outputs/{dataset_id}/auto-artifacts")
def auto_detect_study_output_artifacts(
    study_id: str,
    dataset_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """对一个连续数据产物自动检测坏道 / 坏段，返回**建议**（不改数据）。伪迹审核页「自动检测异常」调用。"""
    study = get_study_for_read(study_id, db, current_user)
    dataset = get_study_output_or_404(db, study.id, dataset_id)
    if dataset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DERIVED_DATASET_DELETED", "message": "输出已删除，无法自动检测。"},
        )
    try:
        return build_auto_artifacts(study, dataset)
    except StudyOutputPreviewError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "study_output_id": str(dataset_id)},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "DERIVED_DATASET_AUTO_ARTIFACTS_ENGINE_UNAVAILABLE", "message": str(exc)},
        ) from exc


@router.get("/studies/{study_id}/outputs/{dataset_id}/ica-components")
def get_study_output_ica_components(
    study_id: str,
    dataset_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ICA 成分网格（快路径）：总览 + 每成分地形图（电极权重落 2D 坐标）+ 主导通道。

    只载 ICA 矩阵、不碰源 raw、不跑 ICLabel，让首屏秒出；方差% / ICLabel 标签 / 自动建议走 /labels 异步补。
    """
    study = get_study_for_read(study_id, db, current_user)
    dataset = get_study_output_or_404(db, study.id, dataset_id)
    if dataset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DERIVED_DATASET_DELETED", "message": "输出已删除，ICA 成分不可用。"},
        )
    try:
        return build_ica_components(study, dataset)
    except StudyOutputPreviewError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "study_output_id": str(dataset_id)},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "ICA_ENGINE_UNAVAILABLE", "message": str(exc)},
        ) from exc


@router.get("/studies/{study_id}/outputs/{dataset_id}/ica-components/labels")
def get_study_output_ica_labels(
    study_id: str,
    dataset_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ICA 成分标签（慢路径，异步补）：载入源 raw → 每成分解释方差% + ICLabel 自动分类 + 建议剔除。

    与网格端点分离——前端先拿网格秒出，再拉这个把方差 / 标签 / 默认勾选补上。必须注册在 /{index} 之前。
    """
    study = get_study_for_read(study_id, db, current_user)
    dataset = get_study_output_or_404(db, study.id, dataset_id)
    if dataset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DERIVED_DATASET_DELETED", "message": "输出已删除，ICA 成分不可用。"},
        )
    try:
        return build_ica_labels(study, dataset)
    except StudyOutputPreviewError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "study_output_id": str(dataset_id)},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "ICA_ENGINE_UNAVAILABLE", "message": str(exc)},
        ) from exc


@router.get("/studies/{study_id}/outputs/{dataset_id}/ica-components/preview")
def get_study_output_ica_preview(
    study_id: str,
    dataset_id: UUID,
    excluded: str | None = Query(default=None, description="逗号分隔的成分序号；要剔除的组合"),
    channel: str | None = Query(default=None, description="对比通道名；缺省取首通道"),
    max_seconds: float = Query(default=10.0, gt=0, le=60),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ICA 实时预览：给定要剔除的成分组合，返回某通道去除前后对比波形 + 方差降幅。

    成分审核页中心视图实时刷新用——比单成分详情端点轻（不算时序 / 频谱）。
    必须注册在 /{index} 之前，否则 "preview" 会被当作整数 index 匹配。
    """
    study = get_study_for_read(study_id, db, current_user)
    dataset = get_study_output_or_404(db, study.id, dataset_id)
    if dataset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DERIVED_DATASET_DELETED", "message": "输出已删除，ICA 预览不可用。"},
        )
    excluded_list = [int(tok) for tok in re.split(r"[,;\s]+", excluded or "") if tok.strip().lstrip("-").isdigit()]
    try:
        return build_ica_preview(study, dataset, excluded=excluded_list, channel=channel, max_seconds=max_seconds)
    except StudyOutputPreviewError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "study_output_id": str(dataset_id)},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "ICA_ENGINE_UNAVAILABLE", "message": str(exc)},
        ) from exc


@router.get("/studies/{study_id}/outputs/{dataset_id}/ica-components/{index}")
def get_study_output_ica_component_detail(
    study_id: str,
    dataset_id: UUID,
    index: int,
    excluded: str | None = Query(default=None, description="逗号分隔的成分序号；给出则附去除前后对比"),
    max_seconds: float = Query(default=10.0, gt=0, le=60),
    fmax: float = Query(default=50.0, gt=0, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """单成分详情：时域波形 + Welch 频谱（+ excluded 给出时的去除前后对比）。"""
    study = get_study_for_read(study_id, db, current_user)
    dataset = get_study_output_or_404(db, study.id, dataset_id)
    if dataset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DERIVED_DATASET_DELETED", "message": "输出已删除，ICA 成分不可用。"},
        )
    excluded_list = [int(tok) for tok in re.split(r"[,;\s]+", excluded or "") if tok.strip().lstrip("-").isdigit()]
    try:
        return build_ica_component_detail(
            study, dataset, index, excluded=excluded_list, max_seconds=max_seconds, fmax=fmax
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ICA_COMPONENT_INDEX_INVALID", "message": str(exc)},
        ) from exc
    except StudyOutputPreviewError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "study_output_id": str(dataset_id)},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "ICA_ENGINE_UNAVAILABLE", "message": str(exc)},
        ) from exc


@router.get("/studies/{study_id}/outputs/{dataset_id}/tfr")
def get_study_output_tfr(
    study_id: str,
    dataset_id: UUID,
    channel: str | None = Query(default=None),
    max_freqs: int = Query(default=60, ge=4, le=200),
    max_times: int = Query(default=120, ge=8, le=400),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """单通道时频热图(freq × time 功率矩阵)。供时频观察页按通道切换拉取。"""
    study = get_study_for_read(study_id, db, current_user)
    dataset = get_study_output_or_404(db, study.id, dataset_id)
    if dataset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DERIVED_DATASET_DELETED", "message": "输出已删除，时频数据不可用。"},
        )
    if str(dataset.data_type or "").lower() != "tfr":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "DERIVED_DATASET_NOT_TFR", "message": "该结果不是时频(TFR)类型。"},
        )
    try:
        return build_tfr_heatmap(study, dataset, channel=channel, max_freqs=max_freqs, max_times=max_times)
    except StudyOutputPreviewError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "study_output_id": str(dataset_id)},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "DERIVED_DATASET_TFR_ENGINE_UNAVAILABLE", "message": str(exc)},
        ) from exc


@router.get("/studies/{study_id}/outputs/{dataset_id}/tfr/topo")
def get_study_output_tfr_topo(
    study_id: str,
    dataset_id: UUID,
    tmin: float | None = Query(default=None),
    tmax: float | None = Query(default=None),
    fmin: float | None = Query(default=None),
    fmax: float | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """时频地形图:全通道在 (时窗 × 频窗) 内的平均功率 + 2D 电极坐标。供时频观察页画频段空间分布。"""
    study = get_study_for_read(study_id, db, current_user)
    dataset = get_study_output_or_404(db, study.id, dataset_id)
    if dataset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DERIVED_DATASET_DELETED", "message": "输出已删除，时频数据不可用。"},
        )
    if str(dataset.data_type or "").lower() != "tfr":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "DERIVED_DATASET_NOT_TFR", "message": "该结果不是时频(TFR)类型。"},
        )
    try:
        return build_tfr_topomap(study, dataset, tmin=tmin, tmax=tmax, fmin=fmin, fmax=fmax)
    except StudyOutputPreviewError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "study_output_id": str(dataset_id)},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "DERIVED_DATASET_TFR_ENGINE_UNAVAILABLE", "message": str(exc)},
        ) from exc


@router.get("/studies/{study_id}/outputs/{dataset_id}/tfr/cube")
def get_study_output_tfr_cube(
    study_id: str,
    dataset_id: UUID,
    max_freqs: int = Query(default=60, ge=4, le=200),
    max_times: int = Query(default=120, ge=8, le=400),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """时频立方体：全通道降采样 freq×time 面 + 2D 坐标，一次取回前端本地算地形图（跟随游标零往返）。"""
    study = get_study_for_read(study_id, db, current_user)
    dataset = get_study_output_or_404(db, study.id, dataset_id)
    if dataset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DERIVED_DATASET_DELETED", "message": "输出已删除，时频数据不可用。"},
        )
    if str(dataset.data_type or "").lower() != "tfr":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "DERIVED_DATASET_NOT_TFR", "message": "该结果不是时频(TFR)类型。"},
        )
    try:
        return build_tfr_cube(study, dataset, max_freqs=max_freqs, max_times=max_times)
    except StudyOutputPreviewError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "study_output_id": str(dataset_id)},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "DERIVED_DATASET_TFR_ENGINE_UNAVAILABLE", "message": str(exc)},
        ) from exc


@router.get("/studies/{study_id}/outputs/{dataset_id}/psd")
def get_study_output_psd(
    study_id: str,
    dataset_id: UUID,
    channel: str | None = Query(default=None),
    max_freqs: int = Query(default=300, ge=8, le=2000),
    max_channels: int = Query(default=64, ge=1, le=256),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """多通道功率谱(频率 → 各通道功率 dB 折线 + 逐通道频带统计)。供功率谱观察页做叠加/分面/频段地形图。"""
    study = get_study_for_read(study_id, db, current_user)
    dataset = get_study_output_or_404(db, study.id, dataset_id)
    if dataset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DERIVED_DATASET_DELETED", "message": "输出已删除，功率谱不可用。"},
        )
    if str(dataset.data_type or "").lower() not in ("psd", "psd_grandavg"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "DERIVED_DATASET_NOT_PSD", "message": "该结果不是功率谱(PSD)类型。"},
        )
    try:
        return build_psd_lines(study, dataset, channel=channel, max_freqs=max_freqs, max_channels=max_channels)
    except StudyOutputPreviewError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "study_output_id": str(dataset_id)},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "DERIVED_DATASET_PSD_ENGINE_UNAVAILABLE", "message": str(exc)},
        ) from exc


@router.get("/studies/{study_id}/outputs/{dataset_id}/stat")
def get_study_output_stat(
    study_id: str,
    dataset_id: UUID,
    channel: str | None = Query(default=None),
    max_points: int = Query(default=600, ge=8, le=4000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """统计比较图(stat_map):选定通道的 t 图 + 显著掩码 + A/B 均值 + cluster 显著窗口。供统计观察页绘制。"""
    study = get_study_for_read(study_id, db, current_user)
    dataset = get_study_output_or_404(db, study.id, dataset_id)
    if dataset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DERIVED_DATASET_DELETED", "message": "输出已删除，统计图不可用。"},
        )
    if str(dataset.data_type or "").lower() != "stat_map":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "DERIVED_DATASET_NOT_STAT", "message": "该结果不是统计比较(stat_map)类型。"},
        )
    try:
        return build_stat_view(study, dataset, channel=channel, max_points=max_points)
    except StudyOutputPreviewError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "study_output_id": str(dataset_id)},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "DERIVED_DATASET_STAT_ENGINE_UNAVAILABLE", "message": str(exc)},
        ) from exc


@router.get("/studies/{study_id}/outputs/{dataset_id}/download")
def download_study_output(
    study_id: str,
    dataset_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    dataset = get_study_output_or_404(db, study.id, dataset_id)
    if dataset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DERIVED_DATASET_DELETED", "message": "输出已删除，下载不可用。"},
        )
    try:
        path = resolve_study_output_path(study, dataset)
        validate_study_output_file(path, dataset)
    except StudyOutputPreviewError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "study_output_id": str(dataset_id)},
        ) from exc
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DERIVED_DATASET_DOWNLOAD_DIRECTORY_UNSUPPORTED", "message": "Directory download is not supported."},
        )
    dataset.updated_at = datetime.utcnow()
    db.commit()
    filename = dataset.display_name or Path(str(dataset.logical_path or dataset.storage_uri or "")).name or f"derived-{dataset.id}"
    filename = re.sub(r"[\\/:*?\"<>|]", "_", str(filename))
    return FileResponse(path, media_type="application/octet-stream", filename=filename)
