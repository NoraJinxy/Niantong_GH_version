"""
Purpose: Provide reusable service-layer logic for Study/Study creation and storage setup.
Related: app/routers/studies.py, app/models/study.py, app/schemas/study.py, docs_v2/5-10.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AuditEvent, Study, StudyMember, StudySettings, User
from app.services.audit_events import record_audit_event


LEGACY_PROJECT_DIRECTORIES = (
    "source_uploads",
    "fifdata",
    "upload_staging",
    "validation",
    "bids_exports",
    "derivatives/preprocessing",
    "pipeline",
    "pipeline_runs",
)

STUDY_STORAGE_DIRECTORIES = (
    "executions",
    "derived",
    "previews",
    "temp",
    "exports",
    "pipeline_snapshots",
)


class StudyCreateCodeConflictError(Exception):
    """Raised when a Study/Study code already exists."""


class StudyCreateIntegrityError(Exception):
    """Raised when Study/Study creation fails with a non-code integrity error."""


class StudyStorageSetupError(Exception):
    """Raised when Study/Study directories cannot be initialized."""


@dataclass
class StudyCreateResult:
    study: Study
    owner_membership: StudyMember
    settings: StudySettings
    study_audit_event: AuditEvent | None  # event_scope='study',snapshot 填 study.to_dict()
    audit_event: AuditEvent | None


def _settings(settings_obj=None):
    return settings_obj or get_settings()


def ensure_study_create_permission(user: User) -> None:
    if user.has_role("admin") or user.has_role("pi"):
        return
    if user.has_permission("study:write"):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="当前用户没有创建研究项权限",
    )


def study_storage_root(study: Study, settings_obj=None) -> Path:
    return Path(_settings(settings_obj).STUDIES_STORAGE_ROOT) / study.id


def study_storage_uri(study: Study) -> str:
    return f"elys://studies/{study.id}"


def study_storage_policy(study: Study, settings_obj=None) -> dict:
    return {
        "study_storage_uri": study_storage_uri(study),
        "study_storage_root": str(study_storage_root(study, settings_obj=settings_obj)),
        "legacy_study_uri": f"study://{study.id}",
        "legacy_data_root": study.data_root,
    }


def create_legacy_study_directories(study: Study, settings_obj=None) -> None:
    root = Path(study.data_root)
    for relative in LEGACY_PROJECT_DIRECTORIES:
        (root / relative).mkdir(parents=True, exist_ok=True)

    marker = {
        "study_id": study.id,
        "code": study.code,
        "name": study.name,
        "data_root": study.data_root,
        "study_storage_uri": study_storage_uri(study),
        "study_storage_root": str(study_storage_root(study, settings_obj=settings_obj)),
    }
    (root / ".elys_study.json").write_text(
        json.dumps(marker, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _create_study_root_storage(study: Study, settings_obj=None) -> None:
    """内部函数:只建 STUDIES_STORAGE_ROOT 下的新 Study 目录。公共入口是 create_study_storage_directories。"""
    root = study_storage_root(study, settings_obj=settings_obj)
    for relative in STUDY_STORAGE_DIRECTORIES:
        (root / relative).mkdir(parents=True, exist_ok=True)

    marker = {
        "study_id": study.id,
        "code": study.code,
        "name": study.name,
        "study_storage_uri": study_storage_uri(study),
        "study_storage_root": str(root),
        "legacy_study_uri": f"study://{study.id}",
        "legacy_data_root": study.data_root,
    }
    (root / ".elys_study.json").write_text(
        json.dumps(marker, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


_CREATE_DIRS_REENTRY_GUARD: set[str] = set()


def create_study_storage_directories(study: Study, settings_obj=None) -> None:
    """公共入口:Orchestrator —— 先建旧目录兼容,再建新 Study 存储目录。

    带 reentry guard:同一 study.id 如果在同一栈帧内被二次调用,直接抛错而不是无限递归。
    这能把任何意外的递归从 RecursionError 转成可定位的 RuntimeError(含 stack)。
    """
    import sys
    import traceback as _tb

    study_id = getattr(study, "id", None) or "<unknown>"
    if study_id in _CREATE_DIRS_REENTRY_GUARD:
        # 打印完整 stack 然后明确 fail,避免 RecursionError 把栈耗尽
        sys.stderr.write(
            f"[ELYS-BUG] create_study_storage_directories 重入检测,study_id={study_id}\n"
        )
        _tb.print_stack(file=sys.stderr)
        sys.stderr.flush()
        raise RuntimeError(
            f"create_study_storage_directories reentered for study_id={study_id}; see stderr stack"
        )

    _CREATE_DIRS_REENTRY_GUARD.add(study_id)
    try:
        sys.stderr.write(f"[ELYS-TRACE] create_study_storage_directories start study_id={study_id}\n")
        sys.stderr.flush()
        create_legacy_study_directories(study, settings_obj=settings_obj)
        _create_study_root_storage(study, settings_obj=settings_obj)
        sys.stderr.write(f"[ELYS-TRACE] create_study_storage_directories done  study_id={study_id}\n")
        sys.stderr.flush()
    finally:
        _CREATE_DIRS_REENTRY_GUARD.discard(study_id)


def create_bids_directories(study: Study, settings_obj=None) -> None:
    create_study_storage_directories(study, settings_obj=settings_obj)


def default_study_settings_payload() -> dict:
    return {
        "default_dataset_filter": {
            "subjects": "all",
            "sessions": "all",
            "tasks": "all",
            "runs": "all",
            "qa_status": "all",
            "require_fif": True,
        },
        "run_policy": {"single_active_pipeline_run": True},
        "storage_policy": {},
    }


def add_study_audit_event(
    db: Session,
    *,
    study: Study,
    action: str,
    actor: User,
    occurred_at: datetime,
    metadata: dict | None = None,
) -> AuditEvent:
    """Write a study-scope audit event with snapshot for hard-delete survivability."""
    event = AuditEvent(
        study_id=study.id,
        event_scope="study",
        action=action,
        actor_id=actor.id,
        resource_kind="study",
        resource_id=study.id,
        resource_label=study.name,
        snapshot=study.to_dict(),
        metadata_json=metadata or {},
        occurred_at=occurred_at,
    )
    db.add(event)
    return event


def create_study(
    db: Session,
    *,
    code: str,
    name: str,
    description: str | None,
    owner: User,
    storage_quota_gb: int,
    actor: User | None = None,
    settings_obj=None,
    commit: bool = False,
    audit_action: str = "study.created",
) -> StudyCreateResult:
    actor = actor or owner
    config = _settings(settings_obj)
    quota_bytes = storage_quota_gb * 1024 * 1024 * 1024
    study = Study(
        code=code,
        name=name,
        description=description,
        owner_id=owner.id,
        data_root="pending",
        storage_quota_bytes=quota_bytes,
    )
    db.add(study)

    try:
        db.flush()
        study.data_root = os.path.join(config.STUDIES_DIR, study.id)
        create_study_storage_directories(study, settings_obj=config)

        membership = StudyMember(
            study_id=study.id,
            user_id=owner.id,
            role="owner",
            can_read=True,
            can_write=True,
            can_delete=True,
            can_export=True,
            can_run=True,
            added_by=actor.id,
        )
        db.add(membership)
        settings_record = StudySettings(
            study_id=study.id,
            storage_policy=study_storage_policy(study, settings_obj=config),
            updated_by=actor.id,
        )
        db.add(settings_record)

        now = datetime.utcnow()
        metadata = {
            "code": study.code,
            "storage_quota_bytes": study.storage_quota_bytes,
            "legacy_data_root": study.data_root,
            "study_storage_uri": study_storage_uri(study),
            "study_storage_root": str(study_storage_root(study, settings_obj=config)),
        }
        study_audit_event = add_study_audit_event(
            db,
            study=study,
            action=audit_action,
            actor=actor,
            occurred_at=now,
            metadata=metadata,
        )
        audit_event = record_audit_event(
            db,
            study_id=study.id,
            action=audit_action,
            actor_id=actor.id,
            event_scope="study",
            resource_kind="study",
            resource_id=study.id,
            resource_label=study.name,
            metadata=metadata,
            occurred_at=now,
        )

        if commit:
            db.commit()
            db.refresh(study)
        return StudyCreateResult(
            study=study,
            owner_membership=membership,
            settings=settings_record,
            study_audit_event=study_audit_event,
            audit_event=audit_event,
        )
    except IntegrityError as exc:
        db.rollback()
        if "studies_code_key" in str(exc.orig):
            raise StudyCreateCodeConflictError from exc
        raise StudyCreateIntegrityError from exc
    except OSError as exc:
        db.rollback()
        raise StudyStorageSetupError(str(exc)) from exc
