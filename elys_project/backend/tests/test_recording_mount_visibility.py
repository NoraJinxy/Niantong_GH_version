"""
Purpose: Test Recording visibility through Study Dataset mounts.
Related: app/services/recordings.py, app/routers/datasets.py, docs_v2/3-30 and docs_v2/7-30.
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType, SimpleNamespace
import importlib.util
import sys
import uuid

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def clear_lightweight_app_stubs() -> None:
    for name in list(sys.modules):
        if not (
            name == "app.models"
            or name == "app.database"
            or name == "app.routers"
            or name == "app.routers.auth"
            or name == "app.services"
            or name == "sqlalchemy"
            or name.startswith("app.database.")
            or name.startswith("app.models.")
            or name.startswith("app.routers.")
            or name.startswith("app.services.")
            or name.startswith("sqlalchemy.")
        ):
            continue
        module = sys.modules.get(name)
        if module is not None and not getattr(module, "__file__", None):
            sys.modules.pop(name, None)


class FakeColumn:
    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other):
        return lambda item: getattr(item, self.name) == other

    def in_(self, values):
        value_set = set(values)
        return lambda item: getattr(item, self.name) in value_set

    def desc(self):
        return self


class FakeRecordingModel:
    id = FakeColumn("id")
    study_id = FakeColumn("study_id")
    dataset_asset_id = FakeColumn("dataset_asset_id")
    imported_at = FakeColumn("imported_at")


class FakeQuery:
    def __init__(self, items) -> None:
        self.items = list(items)

    def filter(self, *predicates):
        for predicate in predicates:
            self.items = [item for item in self.items if predicate(item)]
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self.items


class FakeDb:
    def __init__(self, recordings) -> None:
        self.recordings = recordings

    def query(self, model):
        assert model is FakeRecordingModel
        return FakeQuery(self.recordings)


def load_recordings_service(monkeypatch):
    clear_lightweight_app_stubs()
    from app.services import recordings

    monkeypatch.setattr(recordings, "Recording", FakeRecordingModel)
    monkeypatch.setattr(recordings, "or_", lambda *predicates: lambda item: any(predicate(item) for predicate in predicates))
    return recordings


def test_list_recordings_uses_active_mount_assets_and_legacy_study_fallback(monkeypatch) -> None:
    recordings = load_recordings_service(monkeypatch)
    study_b = SimpleNamespace(id="202605000002")
    mounted_asset_id = uuid.uuid4()
    own_unmounted_asset_id = uuid.uuid4()
    hidden_asset_id = uuid.uuid4()
    external_recording = SimpleNamespace(id=uuid.uuid4(), study_id="202605000001", dataset_asset_id=mounted_asset_id)
    old_study_recording = SimpleNamespace(id=uuid.uuid4(), study_id=study_b.id, dataset_asset_id=None)
    own_study_recording = SimpleNamespace(id=uuid.uuid4(), study_id=study_b.id, dataset_asset_id=own_unmounted_asset_id)
    hidden_recording = SimpleNamespace(id=uuid.uuid4(), study_id="202605000003", dataset_asset_id=hidden_asset_id)
    db = FakeDb([external_recording, old_study_recording, own_study_recording, hidden_recording])

    result = recordings.list_recordings_for_study(
        db,
        study=study_b,
        mounted_dataset_asset_ids=[mounted_asset_id],
    )

    assert external_recording in result
    assert old_study_recording in result
    assert own_study_recording in result
    assert hidden_recording not in result


def test_list_recordings_with_explicit_dataset_asset_does_not_require_recording_study_id(monkeypatch) -> None:
    recordings = load_recordings_service(monkeypatch)
    study_b = SimpleNamespace(id="202605000002")
    mounted_asset_id = uuid.uuid4()
    other_asset_id = uuid.uuid4()
    external_recording = SimpleNamespace(id=uuid.uuid4(), study_id="202605000001", dataset_asset_id=mounted_asset_id)
    fallback_recording = SimpleNamespace(id=uuid.uuid4(), study_id=study_b.id, dataset_asset_id=other_asset_id)
    db = FakeDb([external_recording, fallback_recording])

    result = recordings.list_recordings_for_study(
        db,
        study=study_b,
        dataset_asset_id=mounted_asset_id,
    )

    assert result == [external_recording]


def install_fastapi_and_router_stubs() -> None:
    fastapi = ModuleType("fastapi")

    class HTTPException(Exception):
        def __init__(self, status_code=None, detail=None):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class APIRouter:
        def __init__(self, *args, prefix="", tags=None, **kwargs):
            self.prefix = prefix
            self.tags = tags or []

        def get(self, *args, **kwargs):
            return lambda fn: fn

        def post(self, *args, **kwargs):
            return lambda fn: fn

        def patch(self, *args, **kwargs):
            return lambda fn: fn

        def delete(self, *args, **kwargs):
            return lambda fn: fn

    fastapi.APIRouter = APIRouter
    fastapi.Depends = lambda dependency=None, **kwargs: None
    fastapi.File = lambda *args, **kwargs: None
    fastapi.Form = lambda default=None, **kwargs: default
    fastapi.HTTPException = HTTPException
    fastapi.UploadFile = type("UploadFile", (), {})
    fastapi.status = SimpleNamespace(
        HTTP_201_CREATED=201,
        HTTP_400_BAD_REQUEST=400,
        HTTP_403_FORBIDDEN=403,
        HTTP_404_NOT_FOUND=404,
        HTTP_409_CONFLICT=409,
        HTTP_500_INTERNAL_SERVER_ERROR=500,
    )
    sys.modules["fastapi"] = fastapi

    auth = ModuleType("app.routers.auth")
    auth.get_current_user = lambda: None
    sys.modules["app.routers.auth"] = auth

    database = ModuleType("app.database")
    database.get_db = lambda: None
    sys.modules["app.database"] = database


def load_datasets_router_module():
    clear_lightweight_app_stubs()
    install_fastapi_and_router_stubs()
    spec = importlib.util.spec_from_file_location(
        "datasets_recording_mount_under_test",
        BACKEND_DIR / "app" / "routers" / "datasets.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["datasets_recording_mount_under_test"] = module
    spec.loader.exec_module(module)
    return module


def test_resolve_dataset_asset_filter_rejects_unmounted_dataset_asset() -> None:
    datasets = load_datasets_router_module()
    study = SimpleNamespace(id="202605000002")
    dataset_asset_id = uuid.uuid4()
    datasets.list_study_dataset_mounts = lambda db, study: []

    with pytest.raises(datasets.HTTPException) as exc:
        datasets.resolve_dataset_asset_filter(
            SimpleNamespace(),
            study=study,
            dataset_asset_id=dataset_asset_id,
        )

    assert exc.value.status_code == 404
    assert "未挂载" in exc.value.detail


def test_resolve_dataset_asset_filter_accepts_active_mount_name() -> None:
    datasets = load_datasets_router_module()
    study = SimpleNamespace(id="202605000002")
    dataset_asset_id = uuid.uuid4()
    mount = SimpleNamespace(dataset_asset_id=dataset_asset_id, is_active=True)
    datasets.get_study_dataset_mount_by_name = lambda db, study, mount_name: mount

    result = datasets.resolve_dataset_asset_filter(
        SimpleNamespace(),
        study=study,
        mount_name="external",
    )

    assert result == dataset_asset_id
