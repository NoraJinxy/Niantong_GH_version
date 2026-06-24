"""
Purpose: Query Recording compatibility views while old datasets tables remain in use.
Related: app/models/study.py, app/routers/datasets.py, docs_v2/3-00 and docs_v2/7-30.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models import Study, Recording, RecordingVersion


def list_recordings_for_study(
    db: Session,
    *,
    study: Study,
    dataset_asset_id: UUID | None = None,
    mounted_dataset_asset_ids: list[UUID] | tuple[UUID, ...] | set[UUID] | None = None,
) -> list[Recording]:
    if dataset_asset_id is not None:
        query = db.query(Recording).filter(Recording.dataset_asset_id == dataset_asset_id)
    else:
        mounted_ids = list(dict.fromkeys(mounted_dataset_asset_ids or []))
        query = db.query(Recording)
        if mounted_ids:
            query = query.filter(
                or_(
                    Recording.dataset_asset_id.in_(mounted_ids),
                    Recording.study_id == study.id,
                )
            )
        else:
            query = query.filter(Recording.study_id == study.id)
    return (
        query.options(joinedload(Recording.subject), joinedload(Recording.current_version))
        .order_by(Recording.imported_at.desc(), Recording.id.desc())
        .all()
    )


def get_recording_for_study(db: Session, *, study: Study, recording_id: UUID) -> Recording | None:
    return db.query(Recording).filter(Recording.study_id == study.id, Recording.id == recording_id).first()


def list_recording_versions_for_study(
    db: Session,
    *,
    study: Study,
    recording_id: UUID,
) -> list[RecordingVersion]:
    return (
        db.query(RecordingVersion)
        .filter(RecordingVersion.recording_id == recording_id)
        .order_by(RecordingVersion.version_seq.desc(), RecordingVersion.uploaded_at.desc())
        .all()
    )
