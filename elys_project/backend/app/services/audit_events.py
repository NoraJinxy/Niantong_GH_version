"""
Purpose: Write generic audit events for study actions.
Related: app/models/study.py, app/routers/*, docs_v2/7-30.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import AuditEvent


def record_audit_event(
    db: Session,
    *,
    action: str,
    study_id: str | None = None,
    actor_id: UUID | str | None = None,
    event_scope: str = "study",
    resource_kind: str | None = None,
    resource_id: UUID | str | int | None = None,
    resource_label: str | None = None,
    snapshot: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> AuditEvent:
    """Write a generic audit event. Pass `snapshot` for hard-delete events that must survive cascade."""
    event = AuditEvent(
        study_id=study_id,
        event_scope=event_scope,
        action=action,
        actor_id=actor_id,
        resource_kind=resource_kind,
        resource_id=str(resource_id) if resource_id is not None else None,
        resource_label=resource_label,
        snapshot=snapshot or {},
        metadata_json=metadata or {},
        occurred_at=occurred_at or datetime.utcnow(),
    )
    db.add(event)
    return event
