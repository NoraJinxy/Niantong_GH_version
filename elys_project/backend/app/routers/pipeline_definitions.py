"""
Purpose: Pipeline definition CRUD + edit-lock routes, split out of routers/pipelines.py.
Related: app/routers/_pipeline_shared.py, app/routers/pipelines.py, app/services/study_locks.py, docs_v2/2-50.

Covers list/create/get/update/delete of PipelineDefinition plus the edit-lock acquire/refresh/release.
Execution endpoints (.../executions, validate, run) stay in pipelines.py.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PipelineDefinition, Study, StudyLock, User
from app.routers.auth import get_current_user
from app.routers._pipeline_shared import (
    count_nodes,
    get_pipeline_or_404,
    get_study_for_read,
    get_study_for_write,
    pipeline_to_response,
)
from app.schemas.pipeline import (
    PipelineCreate,
    PipelineEditLockResponse,
    PipelineListResponse,
    PipelineResponse,
    PipelineUpdate,
)
from app.services.audit_events import record_audit_event
from app.services.study_locks import (
    StudyLockConflictError,
    acquire_study_lock,
    find_active_study_lock,
    refresh_study_lock,
    release_study_lock,
)

router = APIRouter(prefix="/api/v1", tags=["工作流"])

PIPELINE_EDIT_LOCK_TTL_SECONDS = 30 * 60


# ===================== helpers =====================

def pipeline_edit_lock_to_response(lock: StudyLock, pipeline_id: int) -> PipelineEditLockResponse:
    return PipelineEditLockResponse(
        id=str(lock.id),
        study_id=lock.study_id,
        pipeline_id=pipeline_id,
        resource_kind=lock.resource_kind,
        resource_id=lock.resource_id,
        lock_type=lock.lock_type,
        locked_by=str(lock.locked_by) if lock.locked_by else None,
        locked_at=lock.locked_at,
        expires_at=lock.expires_at,
        released_at=lock.released_at,
        metadata_json=lock.metadata_json or {},
    )


def pipeline_edit_lock_conflict_detail(
    study: Study,
    pipeline: PipelineDefinition,
    lock: StudyLock | None,
) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "code": "PIPELINE_EDIT_LOCKED",
        "message": "该工作流正在被其他用户编辑，请等待锁释放或过期后再保存。",
        "study_id": study.id,
        "pipeline_id": pipeline.id,
    }
    if lock is not None:
        detail.update(
            {
                "lock_id": str(lock.id),
                "lock_type": lock.lock_type,
                "locked_by": str(lock.locked_by) if lock.locked_by else None,
                "locked_at": lock.locked_at.isoformat() if lock.locked_at else None,
                "expires_at": lock.expires_at.isoformat() if lock.expires_at else None,
            }
        )
    return detail


def is_lock_owned_by(lock: StudyLock, user: User) -> bool:
    return lock.locked_by is not None and str(lock.locked_by) == str(user.id)


def find_active_pipeline_edit_lock(
    db: Session,
    *,
    study: Study,
    pipeline: PipelineDefinition,
) -> StudyLock | None:
    return find_active_study_lock(
        db,
        study_id=study.id,
        resource_kind="pipeline",
        resource_id=pipeline.id,
        lock_type="edit",
    )


def ensure_pipeline_edit_lock_available(
    db: Session,
    *,
    study: Study,
    pipeline: PipelineDefinition,
    current_user: User,
) -> StudyLock | None:
    lock = find_active_pipeline_edit_lock(db, study=study, pipeline=pipeline)
    if lock is not None and not is_lock_owned_by(lock, current_user):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=pipeline_edit_lock_conflict_detail(study, pipeline, lock),
        )
    return lock


def acquire_or_refresh_pipeline_edit_lock(
    db: Session,
    *,
    study: Study,
    pipeline: PipelineDefinition,
    current_user: User,
    reason: str,
) -> tuple[StudyLock, bool]:
    existing = find_active_pipeline_edit_lock(db, study=study, pipeline=pipeline)
    if existing is not None:
        if not is_lock_owned_by(existing, current_user):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=pipeline_edit_lock_conflict_detail(study, pipeline, existing),
            )
        refreshed = refresh_study_lock(
            db,
            existing,
            ttl_seconds=PIPELINE_EDIT_LOCK_TTL_SECONDS,
            refreshed_by=current_user.id,
            reason=reason,
        )
        return refreshed, False

    try:
        lock = acquire_study_lock(
            db,
            study_id=study.id,
            resource_kind="pipeline",
            resource_id=pipeline.id,
            lock_type="edit",
            locked_by=current_user.id,
            ttl_seconds=PIPELINE_EDIT_LOCK_TTL_SECONDS,
            metadata={
                "pipeline_id": pipeline.id,
                "pipeline_version": pipeline.version,
                "reason": reason,
            },
        )
    except StudyLockConflictError as exc:
        if exc.lock is not None and is_lock_owned_by(exc.lock, current_user):
            refreshed = refresh_study_lock(
                db,
                exc.lock,
                ttl_seconds=PIPELINE_EDIT_LOCK_TTL_SECONDS,
                refreshed_by=current_user.id,
                reason=reason,
            )
            return refreshed, False
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=pipeline_edit_lock_conflict_detail(study, pipeline, exc.lock),
        ) from exc
    return lock, True


# ===================== endpoints =====================

@router.get("/studies/{study_id}/pipelines", response_model=PipelineListResponse)
def list_pipelines(
    study_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    pipelines = (
        db.query(PipelineDefinition)
        .filter(PipelineDefinition.study_id == study.id, PipelineDefinition.status != "deleted")
        .order_by(PipelineDefinition.updated_at.desc(), PipelineDefinition.id.desc())
        .all()
    )
    return PipelineListResponse(pipelines=[pipeline_to_response(item) for item in pipelines])


@router.post("/studies/{study_id}/pipelines", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
def create_pipeline(
    study_id: str,
    payload: PipelineCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_write(study_id, db, current_user)
    definition = payload.definition_json.model_dump(mode="json")
    definition["name"] = payload.name
    definition["description"] = payload.description
    pipeline = PipelineDefinition(
        study_id=study.id,
        name=payload.name,
        description=payload.description,
        definition_json=definition,
        node_count=count_nodes(definition),
        version=1,
        is_template=payload.is_template,
        status="active",
        created_by=current_user.id,
    )
    db.add(pipeline)
    try:
        db.flush()
        record_audit_event(
            db,
            study_id=study.id,
            action="pipeline.created",
            actor_id=current_user.id,
            resource_kind="pipeline",
            resource_id=pipeline.id,
            resource_label=pipeline.name,
            metadata={
                "version": pipeline.version,
                "status": pipeline.status,
                "node_count": pipeline.node_count,
                "is_template": pipeline.is_template,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="同名工作流已存在") from exc
    db.refresh(pipeline)
    return pipeline_to_response(pipeline)


@router.get("/studies/{study_id}/pipelines/{pipeline_id}", response_model=PipelineResponse)
def get_pipeline(
    study_id: str,
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_read(study_id, db, current_user)
    return pipeline_to_response(get_pipeline_or_404(db, study.id, pipeline_id))


@router.post("/studies/{study_id}/pipelines/{pipeline_id}/edit-lock", response_model=PipelineEditLockResponse)
def acquire_pipeline_edit_lock(
    study_id: str,
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_write(study_id, db, current_user)
    pipeline = get_pipeline_or_404(db, study.id, pipeline_id)
    lock, created = acquire_or_refresh_pipeline_edit_lock(
        db,
        study=study,
        pipeline=pipeline,
        current_user=current_user,
        reason="pipeline_edit_acquire",
    )
    record_audit_event(
        db,
        study_id=study.id,
        action="pipeline.edit_lock.acquired" if created else "pipeline.edit_lock.refreshed",
        actor_id=current_user.id,
        resource_kind="pipeline",
        resource_id=pipeline.id,
        resource_label=pipeline.name,
        metadata={
            "lock_id": str(lock.id),
            "lock_type": lock.lock_type,
            "pipeline_version": pipeline.version,
            "expires_at": lock.expires_at.isoformat(),
        },
    )
    db.commit()
    db.refresh(lock)
    return pipeline_edit_lock_to_response(lock, pipeline.id)


@router.post(
    "/studies/{study_id}/pipelines/{pipeline_id}/edit-lock/refresh",
    response_model=PipelineEditLockResponse,
)
def refresh_pipeline_edit_lock(
    study_id: str,
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_write(study_id, db, current_user)
    pipeline = get_pipeline_or_404(db, study.id, pipeline_id)
    lock = ensure_pipeline_edit_lock_available(db, study=study, pipeline=pipeline, current_user=current_user)
    if lock is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "PIPELINE_EDIT_LOCK_NOT_FOUND",
                "message": "没有可续期的工作流编辑锁，请先获取编辑锁。",
                "study_id": study.id,
                "pipeline_id": pipeline.id,
            },
        )
    lock = refresh_study_lock(
        db,
        lock,
        ttl_seconds=PIPELINE_EDIT_LOCK_TTL_SECONDS,
        refreshed_by=current_user.id,
        reason="pipeline_edit_refresh",
    )
    record_audit_event(
        db,
        study_id=study.id,
        action="pipeline.edit_lock.refreshed",
        actor_id=current_user.id,
        resource_kind="pipeline",
        resource_id=pipeline.id,
        resource_label=pipeline.name,
        metadata={
            "lock_id": str(lock.id),
            "lock_type": lock.lock_type,
            "pipeline_version": pipeline.version,
            "expires_at": lock.expires_at.isoformat(),
        },
    )
    db.commit()
    db.refresh(lock)
    return pipeline_edit_lock_to_response(lock, pipeline.id)


@router.delete("/studies/{study_id}/pipelines/{pipeline_id}/edit-lock", status_code=status.HTTP_204_NO_CONTENT)
def release_pipeline_edit_lock(
    study_id: str,
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_write(study_id, db, current_user)
    pipeline = get_pipeline_or_404(db, study.id, pipeline_id)
    lock = find_active_pipeline_edit_lock(db, study=study, pipeline=pipeline)
    if lock is not None and not is_lock_owned_by(lock, current_user):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=pipeline_edit_lock_conflict_detail(study, pipeline, lock),
        )
    if lock is not None:
        release_study_lock(db, lock, released_by=current_user.id, reason="pipeline_edit_release")
        record_audit_event(
            db,
            study_id=study.id,
            action="pipeline.edit_lock.released",
            actor_id=current_user.id,
            resource_kind="pipeline",
            resource_id=pipeline.id,
            resource_label=pipeline.name,
            metadata={
                "lock_id": str(lock.id),
                "lock_type": lock.lock_type,
                "pipeline_version": pipeline.version,
            },
        )
    db.commit()
    return None


@router.put("/studies/{study_id}/pipelines/{pipeline_id}", response_model=PipelineResponse)
def update_pipeline(
    study_id: str,
    pipeline_id: int,
    payload: PipelineUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_write(study_id, db, current_user)
    pipeline = get_pipeline_or_404(db, study.id, pipeline_id)
    edit_lock = ensure_pipeline_edit_lock_available(db, study=study, pipeline=pipeline, current_user=current_user)
    if payload.expected_version != pipeline.version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="工作流版本已变化，请刷新后再保存")

    fields_set = payload.model_fields_set
    previous_version = pipeline.version
    previous_status = pipeline.status
    # 仅在确有实质改动时才升版本 —— 否则"运行前的空保存 / 没改任何参数的重复保存"也会让 version+1,
    # 与用户「版本号=定义改了几次」的预期不符。version 同时兼任乐观锁计数,但无变更时不升也不影响并发检测。
    changed = False

    if "name" in fields_set and payload.name is not None and payload.name != pipeline.name:
        pipeline.name = payload.name
        changed = True
    if "description" in fields_set and payload.description != pipeline.description:
        pipeline.description = payload.description
        changed = True
    if "definition_json" in fields_set and payload.definition_json is not None:
        definition = payload.definition_json.model_dump(mode="json")
        definition["name"] = pipeline.name
        definition["description"] = pipeline.description
        if definition != pipeline.definition_json:
            pipeline.definition_json = definition
            pipeline.node_count = count_nodes(definition)
            changed = True
    if "is_template" in fields_set and payload.is_template is not None and payload.is_template != pipeline.is_template:
        pipeline.is_template = payload.is_template
        changed = True
    if "status" in fields_set and payload.status is not None and payload.status != pipeline.status:
        pipeline.status = payload.status
        changed = True

    if not changed:
        # 无实质改动:不升版本、不写审计;但仍 commit 以持久化前面可能获取的编辑锁,幂等返回当前状态
        # (运行前的空保存 / 没改参数的重复保存不再让 version 漂)。
        db.commit()
        return pipeline_to_response(pipeline)

    pipeline.version += 1
    pipeline.updated_at = datetime.utcnow()
    try:
        record_audit_event(
            db,
            study_id=study.id,
            action="pipeline.updated",
            actor_id=current_user.id,
            resource_kind="pipeline",
            resource_id=pipeline.id,
            resource_label=pipeline.name,
            metadata={
                "fields": sorted(fields_set),
                "previous_version": previous_version,
                "new_version": pipeline.version,
                "previous_status": previous_status,
                "new_status": pipeline.status,
                "expected_version": payload.expected_version,
                "edit_lock_id": str(edit_lock.id) if edit_lock is not None else None,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="同名工作流已存在") from exc
    db.refresh(pipeline)
    return pipeline_to_response(pipeline)


@router.delete("/studies/{study_id}/pipelines/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pipeline(
    study_id: str,
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_for_write(study_id, db, current_user)
    pipeline = get_pipeline_or_404(db, study.id, pipeline_id)
    pipeline.status = "deleted"
    pipeline.version += 1
    pipeline.updated_at = datetime.utcnow()
    record_audit_event(
        db,
        study_id=study.id,
        action="pipeline.deleted",
        actor_id=current_user.id,
        resource_kind="pipeline",
        resource_id=pipeline.id,
        resource_label=pipeline.name,
        metadata={"version": pipeline.version},
    )
    db.commit()
    return None
