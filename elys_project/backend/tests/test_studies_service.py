"""
Purpose: Test Study service helpers used by study creation and Dataset-first bootstrap.
Related: app/services/studies.py, app/routers/studies.py, docs_v2/5-10.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import ModuleType, SimpleNamespace
from uuid import uuid4
import sys


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def install_fastapi_stub() -> None:
    fastapi = ModuleType("fastapi")

    class HTTPException(Exception):
        def __init__(self, status_code=None, detail=None):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    fastapi.HTTPException = HTTPException
    fastapi.status = SimpleNamespace(HTTP_403_FORBIDDEN=403)
    sys.modules["fastapi"] = fastapi


install_fastapi_stub()

from app.models import AuditEvent, Study, AuditEvent, StudyMember, StudySettings
from app.services import studies


class FakeDb:
    def __init__(self) -> None:
        self.added = []
        self.committed = False
        self.refreshed = []
        self.rolled_back = False

    def add(self, item) -> None:
        self.added.append(item)

    def flush(self) -> None:
        for item in self.added:
            if isinstance(item, Study) and item.id is None:
                item.id = "202605000001"

    def commit(self) -> None:
        self.committed = True

    def refresh(self, item) -> None:
        self.refreshed.append(item)

    def rollback(self) -> None:
        self.rolled_back = True


class FakeUser:
    def __init__(self) -> None:
        self.id = uuid4()

    def has_role(self, role: str) -> bool:
        return role == "pi"

    def has_permission(self, permission: str) -> bool:
        return False


def make_settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        STUDIES_DIR=str(tmp_path / "studies"),
        STUDIES_STORAGE_ROOT=str(tmp_path / "storage" / "studies"),
    )


def test_create_study_initializes_owner_settings_audit_and_storage(tmp_path) -> None:
    db = FakeDb()
    owner = FakeUser()
    settings_obj = make_settings(tmp_path)

    result = studies.create_study(
        db,
        code="demo-study",
        name="Demo Study",
        description="demo",
        owner=owner,
        actor=owner,
        storage_quota_gb=2,
        settings_obj=settings_obj,
        commit=True,
    )

    study = result.study
    assert study.id == "202605000001"
    assert study.data_root == str(tmp_path / "studies" / study.id)
    assert study.storage_quota_bytes == 2 * 1024 * 1024 * 1024

    memberships = [item for item in db.added if isinstance(item, StudyMember)]
    assert len(memberships) == 1
    assert memberships[0].role == "owner"
    assert memberships[0].can_read is True
    assert memberships[0].can_write is True
    assert memberships[0].can_delete is True
    assert memberships[0].can_export is True
    assert memberships[0].can_run is True

    settings_records = [item for item in db.added if isinstance(item, StudySettings)]
    assert len(settings_records) == 1
    assert settings_records[0].storage_policy["study_storage_uri"] == f"elys://studies/{study.id}"

    assert any(isinstance(item, AuditEvent) for item in db.added)
    assert any(isinstance(item, AuditEvent) for item in db.added)
    assert result.study_audit_event is not None
    assert result.audit_event is not None

    legacy_root = Path(study.data_root)
    study_root = Path(settings_obj.STUDIES_STORAGE_ROOT) / study.id
    assert (legacy_root / "source_uploads").is_dir()
    assert (legacy_root / "pipeline_runs").is_dir()
    assert (study_root / "runs").is_dir()
    assert (study_root / "artifacts").is_dir()

    legacy_marker = json.loads((legacy_root / ".elys_study.json").read_text(encoding="utf-8"))
    study_marker = json.loads((study_root / ".elys_study.json").read_text(encoding="utf-8"))
    assert legacy_marker["study_id"] == study.id
    assert study_marker["study_storage_uri"] == f"elys://studies/{study.id}"

    assert db.committed is True
    assert study in db.refreshed
    assert db.rolled_back is False
