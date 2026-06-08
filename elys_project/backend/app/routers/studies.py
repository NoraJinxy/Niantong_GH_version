"""
Purpose: Define FastAPI routes for the studies API area and translate HTTP requests into services/database calls.
Related: app/schemas/*, app/models/*, app/services/*, app/routers/auth.py, docs_v2/2-50.
"""

import shutil
from datetime import datetime
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import DerivedDataset, PipelineExecution, PipelineExecutionDependency, Recording, Study, StudyMember, StudySettings, User
from app.routers.auth import get_current_user
from app.schemas.study import (
    StudyActionResponse,
    StudyCreate,
    StudyListResponse,
    StudyMemberListResponse,
    StudyMemberResponse,
    StudyMemberUpdate,
    StudyMemberUpsert,
    StudyPurgeRequest,
    StudyResponse,
    StudyTrashRequest,
    StudySettingsResponse,
    StudySettingsUpdate,
)
from app.schemas.study_summary import StudySummaryResponse
from app.services.study_access import require_study_read, require_study_write
from app.services.study_summary import build_study_summary
from app.services.audit_events import record_audit_event
from app.services.execution_dependencies import study_downstream_dependency_blockers
from app.services import studies as study_service
from app.services.studies import (
    StudyCreateCodeConflictError,
    StudyCreateIntegrityError,
    StudyStorageSetupError,
    add_study_audit_event,
    default_study_settings_payload,
    ensure_study_create_permission,
)

router = APIRouter(prefix="/api/v1/studies", tags=["研究项"])
settings = get_settings()

STUDY_MEMBER_ROLE_FLAGS = {
    "editor": {
        "can_read": True,
        "can_write": True,
        "can_delete": False,
        "can_export": True,
        "can_run": True,
    },
    "viewer": {
        "can_read": True,
        "can_write": False,
        "can_delete": False,
        "can_export": False,
        "can_run": False,
    },
}


LEGACY_PROJECT_DIRECTORIES = study_service.LEGACY_PROJECT_DIRECTORIES
STUDY_STORAGE_DIRECTORIES = study_service.STUDY_STORAGE_DIRECTORIES


def ensure_study_permission(user: User) -> None:
    ensure_study_create_permission(user)


def study_storage_root(study: Study) -> Path:
    return study_service.study_storage_root(study, settings_obj=settings)


def study_storage_uri(study: Study) -> str:
    return study_service.study_storage_uri(study)


def study_storage_policy(study: Study) -> dict:
    return study_service.study_storage_policy(study, settings_obj=settings)


def create_legacy_study_directories(study: Study) -> None:
    study_service.create_legacy_study_directories(study, settings_obj=settings)


def create_study_storage_directories(study: Study) -> None:
    study_service.create_study_storage_directories(study, settings_obj=settings)


def create_bids_directories(study: Study) -> None:
    study_service.create_bids_directories(study, settings_obj=settings)


def to_study_response(study: Study) -> StudyResponse:
    return StudyResponse(**study.to_dict())


def get_study_or_404(db: Session, study_id: str) -> Study:
    study = db.query(Study).filter(Study.id == study_id).first()
    if study is None or study.status == "deleted":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究项不存在")
    return study


def get_study_membership(db: Session, study: Study, user: User) -> StudyMember | None:
    return (
        db.query(StudyMember)
        .filter(StudyMember.study_id == study.id, StudyMember.user_id == user.id)
        .first()
    )


def study_settings_to_response(study_id: str, settings_obj: StudySettings | None) -> StudySettingsResponse:
    defaults = default_study_settings_payload()
    if settings_obj is None:
        return StudySettingsResponse(study_id=study_id, updated_by=None, updated_at=None, **defaults)
    return StudySettingsResponse(
        study_id=settings_obj.study_id,
        default_dataset_filter=settings_obj.default_dataset_filter or defaults["default_dataset_filter"],
        run_policy=settings_obj.run_policy or defaults["run_policy"],
        derived_dataset_retention_policy=settings_obj.derived_dataset_retention_policy or defaults["derived_dataset_retention_policy"],
        storage_policy=settings_obj.storage_policy or defaults["storage_policy"],
        updated_by=str(settings_obj.updated_by) if settings_obj.updated_by else None,
        updated_at=settings_obj.updated_at,
    )


def apply_study_visibility(query, db: Session, current_user: User):
    if current_user.has_role("admin"):
        return query

    return (
        query.outerjoin(StudyMember, StudyMember.study_id == Study.id)
        .filter(
            or_(
                Study.owner_id == current_user.id,
                StudyMember.user_id == current_user.id,
            )
        )
        .distinct()
    )


def ensure_study_visible(study: Study, db: Session, user: User) -> None:
    if user.has_role("admin") or study.owner_id == user.id:
        return
    if get_study_membership(db, study, user):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该研究项")


def ensure_study_delete_permission(study: Study, db: Session, user: User) -> None:
    if user.has_role("admin") or study.owner_id == user.id:
        return
    membership = get_study_membership(db, study, user)
    if membership and (membership.can_delete or membership.role == "owner"):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除该研究项")


def ensure_member_management_permission(study: Study, db: Session, user: User) -> None:
    if study.status == "trashed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="研究项已在垃圾箱中，请先恢复研究项")
    if study.status == "deleted":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究项不存在")
    if user.has_role("admin") or study.owner_id == user.id:
        return

    membership = get_study_membership(db, study, user)
    if membership and (membership.can_delete or membership.role == "owner"):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权管理该研究项成员")


def ensure_study_purge_permission(user: User) -> None:
    if user.has_role("admin"):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有管理员可以永久删除研究项")


def remove_directory_inside_root(target_root: Path, allowed_root: Path, expected_name: str, label: str) -> None:
    resolved_target_root = target_root.expanduser().resolve(strict=False)
    resolved_allowed_root = allowed_root.expanduser().resolve(strict=False)

    is_inside_allowed_root = (
        resolved_target_root != resolved_allowed_root
        and resolved_allowed_root in resolved_target_root.parents
    )
    if not is_inside_allowed_root or resolved_target_root.name != expected_name:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{label}目录安全检查失败，拒绝删除: {resolved_target_root}",
        )

    if resolved_target_root.exists():
        shutil.rmtree(resolved_target_root)


def remove_study_directory(study: Study) -> None:
    remove_directory_inside_root(
        Path(study.data_root),
        Path(settings.STUDIES_DIR),
        study.id,
        "研究项兼容",
    )
    remove_directory_inside_root(
        study_storage_root(study),
        Path(settings.STUDIES_STORAGE_ROOT),
        study.id,
        "Study",
    )


def member_role_flags(role: str) -> dict[str, bool]:
    flags = STUDY_MEMBER_ROLE_FLAGS.get(role)
    if flags is None:
        raise HTTPException(status_code=422, detail="研究项成员角色只能是 editor 或 viewer")
    return dict(flags)


def to_member_response(member: StudyMember) -> StudyMemberResponse:
    return StudyMemberResponse(
        id=str(member.id),
        study_id=member.study_id,
        user_id=str(member.user_id),
        username=member.user.username if member.user else "",
        full_name=member.user.full_name if member.user else None,
        role=member.role,
        can_read=member.can_read,
        can_write=member.can_write,
        can_delete=member.can_delete,
        can_export=member.can_export,
        can_run=member.can_run,
        added_at=member.added_at,
    )


def get_study_member_or_404(db: Session, study_id: str, member_id: UUID) -> StudyMember:
    member = (
        db.query(StudyMember)
        .filter(StudyMember.study_id == study_id, StudyMember.id == member_id)
        .first()
    )
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究项成员不存在")
    return member


@router.get("", response_model=StudyListResponse)
def list_studies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Study).filter(Study.status.in_(["active", "archived"]))
    query = apply_study_visibility(query, db, current_user)

    studies = query.order_by(Study.created_at.desc()).all()
    return StudyListResponse(studies=[to_study_response(item) for item in studies])


@router.get("/trash", response_model=StudyListResponse)
def list_trashed_studies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Study).filter(Study.status == "trashed")
    query = apply_study_visibility(query, db, current_user)
    studies = query.order_by(Study.deleted_at.desc().nullslast(), Study.updated_at.desc()).all()
    return StudyListResponse(studies=[to_study_response(item) for item in studies])


@router.get("/{study_id}", response_model=StudyResponse)
def get_study(
    study_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = db.query(Study).filter(Study.id == study_id).first()
    return to_study_response(require_study_read(study, db, current_user))


@router.get("/{study_id}/summary", response_model=StudySummaryResponse)
def get_study_summary(
    study_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """研究项概览聚合：一次返回该 study 的 数据/工作流/运行/结果 全貌，

    替代前端原先并发拼约 12 个请求（N+1）。权限复用与 GET /{study_id} 同款的
    require_study_read（只有该 study 成员 / owner / 管理员可访问）。
    """
    study = require_study_read(
        db.query(Study).filter(Study.id == study_id).first(),
        db,
        current_user,
    )
    return build_study_summary(db, study=study, current_user=current_user)


@router.get("/{study_id}/settings", response_model=StudySettingsResponse)
def get_study_settings(
    study_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = require_study_read(get_study_or_404(db, study_id), db, current_user)
    settings_obj = db.query(StudySettings).filter(StudySettings.study_id == study.id).first()
    return study_settings_to_response(study.id, settings_obj)


@router.put("/{study_id}/settings", response_model=StudySettingsResponse)
def update_study_settings(
    study_id: str,
    payload: StudySettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = require_study_write(get_study_or_404(db, study_id), db, current_user)
    settings_obj = db.query(StudySettings).filter(StudySettings.study_id == study.id).first()
    if settings_obj is None:
        settings_obj = StudySettings(study_id=study.id)
        db.add(settings_obj)
    fields_set = payload.model_fields_set
    if "default_dataset_filter" in fields_set and payload.default_dataset_filter is not None:
        settings_obj.default_dataset_filter = payload.default_dataset_filter
    if "run_policy" in fields_set and payload.run_policy is not None:
        settings_obj.run_policy = payload.run_policy
    if "derived_dataset_retention_policy" in fields_set and payload.derived_dataset_retention_policy is not None:
        settings_obj.derived_dataset_retention_policy = payload.derived_dataset_retention_policy
    if "storage_policy" in fields_set and payload.storage_policy is not None:
        settings_obj.storage_policy = payload.storage_policy
    settings_obj.updated_by = current_user.id
    settings_obj.updated_at = datetime.utcnow()
    record_audit_event(
        db,
        study_id=study.id,
        action="study.settings.updated",
        actor_id=current_user.id,
        event_scope="study",
        resource_kind="study_settings",
        resource_id=study.id,
        resource_label=study.name,
        metadata={"fields": sorted(fields_set)},
    )
    db.commit()
    db.refresh(settings_obj)
    return study_settings_to_response(study.id, settings_obj)


@router.get("/{study_id}/members", response_model=StudyMemberListResponse)
def list_study_members(
    study_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = db.query(Study).filter(Study.id == study_id).first()
    study = require_study_read(study, db, current_user)
    members = (
        db.query(StudyMember)
        .filter(StudyMember.study_id == study.id)
        .order_by(StudyMember.added_at.asc())
        .all()
    )
    return StudyMemberListResponse(members=[to_member_response(member) for member in members])


@router.post("/{study_id}/members", response_model=StudyMemberResponse, status_code=status.HTTP_201_CREATED)
def add_study_member(
    study_id: str,
    payload: StudyMemberUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_or_404(db, study_id)
    ensure_member_management_permission(study, db, current_user)

    target_user = db.query(User).filter(User.id == payload.user_id).first()
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if not target_user.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户已禁用，不能加入研究项")
    if not (target_user.has_role("pi") or target_user.has_role("admin")):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="研究项成员必须是系统 PI 或管理员")
    if target_user.id == study.owner_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="研究项 owner 已自动拥有全部权限")

    membership = (
        db.query(StudyMember)
        .filter(StudyMember.study_id == study.id, StudyMember.user_id == target_user.id)
        .first()
    )
    if membership is None:
        membership = StudyMember(
            study_id=study.id,
            user_id=target_user.id,
            added_by=current_user.id,
        )
        db.add(membership)

    flags = member_role_flags(payload.role)
    membership.role = payload.role
    membership.can_read = flags["can_read"]
    membership.can_write = flags["can_write"]
    membership.can_delete = flags["can_delete"]
    membership.can_export = flags["can_export"]
    membership.can_run = payload.can_run if payload.can_run is not None else flags["can_run"]
    db.flush()
    record_audit_event(
        db,
        study_id=study.id,
        action="study.member.upsert",
        actor_id=current_user.id,
        resource_kind="study_member",
        resource_id=membership.id,
        resource_label=target_user.username,
        metadata={
            "target_user_id": str(target_user.id),
            "role": membership.role,
            "can_run": membership.can_run,
        },
    )

    db.commit()
    db.refresh(membership)
    return to_member_response(membership)


@router.put("/{study_id}/members/{member_id}", response_model=StudyMemberResponse)
def update_study_member(
    study_id: str,
    member_id: UUID,
    payload: StudyMemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_or_404(db, study_id)
    ensure_member_management_permission(study, db, current_user)
    member = get_study_member_or_404(db, study.id, member_id)
    if member.user_id == study.owner_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="不能修改研究项 owner 的成员权限")

    old_values = {
        "role": member.role,
        "can_read": member.can_read,
        "can_write": member.can_write,
        "can_delete": member.can_delete,
        "can_export": member.can_export,
        "can_run": member.can_run,
    }
    flags = member_role_flags(payload.role)
    member.role = payload.role
    member.can_read = flags["can_read"]
    member.can_write = flags["can_write"]
    member.can_delete = flags["can_delete"]
    member.can_export = flags["can_export"]
    member.can_run = payload.can_run if payload.can_run is not None else flags["can_run"]
    record_audit_event(
        db,
        study_id=study.id,
        action="study.member.updated",
        actor_id=current_user.id,
        resource_kind="study_member",
        resource_id=member.id,
        resource_label=member.user.username if member.user else None,
        metadata={
            "target_user_id": str(member.user_id),
            "old": old_values,
            "new": {
                "role": member.role,
                "can_read": member.can_read,
                "can_write": member.can_write,
                "can_delete": member.can_delete,
                "can_export": member.can_export,
                "can_run": member.can_run,
            },
        },
    )

    db.commit()
    db.refresh(member)
    return to_member_response(member)


@router.delete("/{study_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_study_member(
    study_id: str,
    member_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_or_404(db, study_id)
    ensure_member_management_permission(study, db, current_user)
    member = get_study_member_or_404(db, study.id, member_id)
    if member.user_id == study.owner_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="不能移除研究项 owner")

    record_audit_event(
        db,
        study_id=study.id,
        action="study.member.removed",
        actor_id=current_user.id,
        resource_kind="study_member",
        resource_id=member.id,
        resource_label=member.user.username if member.user else None,
        metadata={
            "target_user_id": str(member.user_id),
            "role": member.role,
            "can_run": member.can_run,
        },
    )
    db.delete(member)
    db.commit()
    return None


@router.post("", response_model=StudyResponse, status_code=status.HTTP_201_CREATED)
def create_study(
    payload: StudyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_study_permission(current_user)

    try:
        result = study_service.create_study(
            db,
            code=payload.code,
            name=payload.name,
            description=payload.description,
            owner=current_user,
            actor=current_user,
            storage_quota_gb=payload.storage_quota_gb,
            settings_obj=settings,
            commit=True,
        )
    except StudyCreateCodeConflictError:
        raise HTTPException(status_code=409, detail="研究项短码已存在")
    except StudyCreateIntegrityError:
        raise HTTPException(status_code=400, detail="研究项创建失败")
    except StudyStorageSetupError as exc:
        raise HTTPException(status_code=500, detail=f"研究项运行空间目录创建失败: {exc}")

    return to_study_response(result.study)


@router.delete("/{study_id}", response_model=StudyActionResponse)
def trash_study(
    study_id: str,
    payload: StudyTrashRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_or_404(db, study_id)
    ensure_study_delete_permission(study, db, current_user)

    if study.status == "trashed":
        return StudyActionResponse(study=to_study_response(study), message="研究项已在垃圾箱中")
    if study.status not in {"active", "archived"}:
        raise HTTPException(status_code=409, detail=f"当前研究项状态不允许删除: {study.status}")

    now = datetime.utcnow()
    study.status = "trashed"
    study.deleted_at = now
    study.deleted_by = current_user.id
    study.delete_reason = payload.reason if payload else None
    study.updated_at = now
    db.commit()
    db.refresh(study)

    return StudyActionResponse(study=to_study_response(study), message="研究项已移入垃圾箱")


@router.post("/{study_id}/restore", response_model=StudyActionResponse)
def restore_study(
    study_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = get_study_or_404(db, study_id)
    ensure_study_delete_permission(study, db, current_user)

    if study.status != "trashed":
        raise HTTPException(status_code=409, detail="只有垃圾箱中的研究项可以恢复")

    now = datetime.utcnow()
    study.status = "active"
    study.deleted_at = None
    study.deleted_by = None
    study.delete_reason = None
    study.updated_at = now
    db.commit()
    db.refresh(study)

    return StudyActionResponse(study=to_study_response(study), message="研究项已恢复")


@router.delete("/{study_id}/purge", response_model=StudyActionResponse)
def purge_study(
    study_id: str,
    payload: StudyPurgeRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_study_purge_permission(current_user)
    study = get_study_or_404(db, study_id)

    if payload.confirm_study_id != study.id:
        raise HTTPException(status_code=422, detail="确认 Study ID 不匹配")
    if study.status != "trashed":
        raise HTTPException(status_code=409, detail="请先将研究项移入垃圾箱，再执行永久删除")

    dependency_blockers = study_downstream_dependency_blockers(db, study_id=study.id)
    if dependency_blockers:
        add_study_audit_event(
            db,
            study=study,
            action="study.purge_blocked",
            actor=current_user,
            occurred_at=datetime.utcnow(),
            metadata={
                "confirm_study_id": payload.confirm_study_id,
                "dependency_blockers": dependency_blockers,
            },
        )
        db.commit()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "STUDY_PURGE_BLOCKED_BY_DOWNSTREAM_DEPENDENCIES",
                "message": "研究项中的 Run 或 Artifact 仍被下游运行引用，不能永久删除。",
                "dependencies": dependency_blockers,
            },
        )

    blocking_counts = {
        "recordings": db.query(Recording).filter(Recording.study_id == study.id).count(),
        "pipeline_executions": db.query(PipelineExecution).filter(PipelineExecution.study_id == study.id).count(),
        "derived_datasets": db.query(DerivedDataset).filter(DerivedDataset.study_id == study.id).count(),
        "pipeline_execution_dependencies": db.query(PipelineExecutionDependency).filter(PipelineExecutionDependency.study_id == study.id).count(),
    }
    if any(blocking_counts.values()):
        add_study_audit_event(
            db,
            study=study,
            action="study.purge_blocked",
            actor=current_user,
            occurred_at=datetime.utcnow(),
            metadata={
                "confirm_study_id": payload.confirm_study_id,
                "blocking_counts": blocking_counts,
            },
        )
        db.commit()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "STUDY_PURGE_BLOCKED_BY_DATA",
                "message": "研究项仍包含数据或运行追溯记录，不能通过普通 API 永久删除。",
                "blocking_counts": blocking_counts,
            },
        )

    now = datetime.utcnow()
    study.updated_at = now
    study_response = StudyResponse(
        **{
            **study.to_dict(),
            "status": "deleted",
            "updated_at": now.isoformat(),
        },
    )
    add_study_audit_event(
        db,
        study=study,
        action="study.purge",
        actor=current_user,
        occurred_at=now,
        metadata={
            "confirm_study_id": payload.confirm_study_id,
            "data_root": study.data_root,
        },
    )

    remove_study_directory(study)
    db.delete(study)
    db.commit()

    return StudyActionResponse(study=study_response, message="研究项已永久删除")
