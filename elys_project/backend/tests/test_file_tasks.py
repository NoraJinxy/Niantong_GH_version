"""
Purpose: Test asynchronous file task helpers and Artifact cleanup safety rules.
Related: app/tasks/file_tasks.py, app/services/async_tasks.py, app/services/execution_dependencies.py.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
import sys
import uuid
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def clear_lightweight_app_stubs() -> None:
    for name in list(sys.modules):
        if not (
            name == "app.database"
            or name == "app.models"
            or name == "app.services"
            or name == "sqlalchemy"
            or name.startswith("app.database.")
            or name.startswith("app.models.")
            or name.startswith("app.services.")
            or name.startswith("sqlalchemy.")
        ):
            continue
        module = sys.modules.get(name)
        if module is not None and not getattr(module, "__file__", None):
            sys.modules.pop(name, None)


clear_lightweight_app_stubs()

from app.models import DerivedDataset  # noqa: E402
from app.services.async_tasks import create_async_task  # noqa: E402
from app.tasks.file_tasks import run_artifact_cleanup  # noqa: E402


class FakeQuery:
    def __init__(self, rows) -> None:
        self.rows = rows

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def all(self):
        return list(self.rows)


class FakeDb:
    def __init__(self, rows=None) -> None:
        self.rows = rows or {}
        self.added = []

    def add(self, record) -> None:
        self.added.append(record)

    def query(self, model):
        return FakeQuery(self.rows.get(model, []))


def test_create_async_task_records_created_event() -> None:
    clear_lightweight_app_stubs()
    db = FakeDb()
    user_id = uuid.uuid4()

    task = create_async_task(
        db,
        task_type="derived_dataset_cleanup",
        queue_name="workflow.default",
        study_id="202605000001",
        resource_kind="study_artifacts",
        resource_id=None,
        payload_json={"dry_run": True},
        created_by=user_id,
    )

    assert task.task_type == "artifact_cleanup"
    assert task.status == "queued"
    assert task.celery_task_id == str(task.id)
    assert task.payload_json == {"dry_run": True}
    assert task.created_by == user_id
    assert any(getattr(item, "event_type", None) == "created" for item in db.added)


def test_artifact_cleanup_only_marks_unblocked_cached_or_temporary(monkeypatch) -> None:
    clear_lightweight_app_stubs()
    study_id = "202605000001"
    clean_artifact = SimpleNamespace(
        id=uuid.uuid4(),
        study_id=study_id,
        retention_status="cached",
        storage_uri=f"elys://studies/{study_id}/derived/aa/hash/clean.fif",
        storage_path="derived/aa/hash/clean.fif",
        deleted_at=None,
        deleted_by=None,
        last_accessed_at=None,
        created_at=datetime(2026, 5, 21, 10, 0, 0),
    )
    blocked_artifact = SimpleNamespace(
        id=uuid.uuid4(),
        study_id=study_id,
        retention_status="temporary",
        storage_uri=f"elys://studies/{study_id}/derived/bb/hash/blocked.fif",
        storage_path="derived/bb/hash/blocked.fif",
        deleted_at=None,
        deleted_by=None,
        last_accessed_at=None,
        created_at=datetime(2026, 5, 21, 10, 1, 0),
    )
    task = SimpleNamespace(
        study_id=study_id,
        created_by=uuid.uuid4(),
        payload_json={"retention_statuses": ["cached", "temporary"], "dry_run": False, "limit": 100},
    )
    db = FakeDb(rows={DerivedDataset: [clean_artifact, blocked_artifact]})

    import app.tasks.file_tasks as file_tasks_module

    monkeypatch.setattr(
        file_tasks_module,
        "artifact_dependency_blockers",
        lambda db, artifact, limit=5: [{"execution_id": "downstream"}] if artifact.id == blocked_artifact.id else [],
    )

    result = run_artifact_cleanup(db, task)

    assert result["cleaned_count"] == 1
    assert result["skipped_count"] == 1
    assert clean_artifact.retention_status == "deleted"
    assert clean_artifact.deleted_by == task.created_by
    assert blocked_artifact.retention_status == "temporary"
    assert result["skipped"][0]["reason"] == "has_downstream_dependencies"
