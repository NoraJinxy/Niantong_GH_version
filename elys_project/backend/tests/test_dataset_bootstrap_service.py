"""
Purpose: Test Dataset-first bootstrap service and route registration.
Related: app/services/dataset_bootstrap.py, app/routers/datasets.py, docs_v2/2-50.
"""

from __future__ import annotations

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

    class APIRouter:
        def __init__(self, *args, prefix="", tags=None, **kwargs):
            self.prefix = prefix
            self.tags = tags or []
            self.routes = []

        def get(self, path, **kwargs):
            return self._route(path, {"GET"}, kwargs)

        def post(self, path, **kwargs):
            return self._route(path, {"POST"}, kwargs)

        def patch(self, path, **kwargs):
            return self._route(path, {"PATCH"}, kwargs)

        def delete(self, path, **kwargs):
            return self._route(path, {"DELETE"}, kwargs)

        def _route(self, path, methods, kwargs):
            def decorator(fn):
                self.routes.append(SimpleNamespace(path=self.prefix + path, endpoint=fn, methods=methods, **kwargs))
                return fn

            return decorator

    marker = lambda *args, **kwargs: None
    fastapi.APIRouter = APIRouter
    fastapi.Body = lambda default=None, **kwargs: default
    fastapi.Depends = marker
    fastapi.File = marker
    fastapi.Form = marker
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


install_fastapi_stub()

from app.models import AuditEvent, DatasetAsset, DatasetVersion, Study, AuditEvent, StudyMember, StudyDatasetMount, StudySettings
from app.services import dataset_bootstrap


class FakeQuery:
    def __init__(self, db, model) -> None:
        self.db = db
        self.model = model

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        for item in self.db.added:
            if isinstance(item, self.model):
                return item if self.model not in {DatasetAsset, DatasetVersion, StudyDatasetMount} else None
        return None


class FakeDb:
    def __init__(self) -> None:
        self.added = []
        self.committed = False
        self.rolled_back = False
        self.refreshed = []
        self.study_sequence = 0

    def add(self, item) -> None:
        self.added.append(item)

    def query(self, model):
        return FakeQuery(self, model)

    def flush(self) -> None:
        for item in self.added:
            if isinstance(item, Study) and item.id is None:
                self.study_sequence += 1
                item.id = f"202605{self.study_sequence:06d}"
            if isinstance(item, (DatasetAsset, DatasetVersion, StudyMember, StudyDatasetMount, AuditEvent, AuditEvent)):
                if getattr(item, "id", None) is None:
                    item.id = uuid4()

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
        return permission in {"data:write", "study:write"}


def make_settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        STUDIES_DIR=str(tmp_path / "studies"),
        STUDIES_STORAGE_ROOT=str(tmp_path / "storage" / "studies"),
        DATASETS_STORAGE_ROOT=str(tmp_path / "storage" / "datasets"),
    )


def audit_events(db: FakeDb):
    return [item for item in db.added if isinstance(item, AuditEvent)]


def test_bootstrap_dataset_create_mode_creates_asset_version_study_mount_and_next_upload(tmp_path) -> None:
    db = FakeDb()
    user = FakeUser()
    settings_obj = make_settings(tmp_path)

    result = dataset_bootstrap.bootstrap_dataset(
        db,
        dataset_name="Demo Dataset",
        dataset_code="demo-dataset",
        dataset_description="demo",
        dataset_visibility="private",
        dataset_metadata_json={"device": "EEG"},
        paired_study_mode="create",
        paired_study_code="demo-study",
        paired_study_name="Demo Study",
        paired_study_description="paired",
        paired_study_storage_quota_gb=1,
        current_user=user,
        mount_name="primary",
        selection_json={"dataset_filter": {"subjects": "all"}},
        settings_obj=settings_obj,
        commit=True,
    )

    assert result.dataset_asset.code == "demo-dataset"
    assert result.dataset_version.version_label == "working"
    assert result.dataset_version.storage_uri == f"elys://datasets/{result.dataset_asset.id}/versions/working"
    assert result.study.code == "demo-study"
    assert result.mount.study_id == result.study.id
    assert result.mount.dataset_asset_id == result.dataset_asset.id
    assert result.mount.mount_name == "primary"
    assert result.dataset_asset.metadata_json["paired_study"]["study_id"] == result.study.id
    # Phase 2 (docs_v2/3-25): 新模型字段
    assert result.dataset_version.state == "draft"
    assert result.dataset_version.qa_status == "not_run"
    assert result.dataset_asset.primary_study_id == result.study.id
    assert result.dataset_asset.current_version_id == result.dataset_version.id
    assert result.mount.dataset_version_id == result.dataset_version.id
    assert result.next_upload.upload_endpoint == f"/api/v1/studies/{result.study.id}/recordings/import"
    assert result.next_upload.form_fields["dataset_asset_id"] == str(result.dataset_asset.id)
    assert result.next_upload.form_fields["mount_name"] == "primary"

    assert (Path(settings_obj.STUDIES_DIR) / result.study.id / "source_uploads").is_dir()
    assert (Path(settings_obj.STUDIES_STORAGE_ROOT) / result.study.id / "runs").is_dir()
    assert (Path(settings_obj.DATASETS_STORAGE_ROOT) / str(result.dataset_asset.id) / "versions" / "working").is_dir()
    assert any(isinstance(item, AuditEvent) for item in db.added)
    assert {"study.created", "dataset_asset.created", "dataset_version.created", "study.dataset_mount.created", "dataset.bootstrap.completed"} <= {
        item.action for item in audit_events(db)
    }
    assert db.committed is True
    assert result.dataset_asset in db.refreshed


def test_bootstrap_dataset_existing_mode_mounts_existing_study_without_creating_study(tmp_path) -> None:
    db = FakeDb()
    user = FakeUser()
    settings_obj = make_settings(tmp_path)
    existing_study = Study(
        id="202605000999",
        code="existing-study",
        name="Existing Study",
        owner_id=user.id,
        data_root=str(tmp_path / "studies" / "202605000999"),
        storage_quota_bytes=1024,
    )

    result = dataset_bootstrap.bootstrap_dataset(
        db,
        dataset_name="External Dataset",
        dataset_code="external-dataset",
        dataset_description=None,
        dataset_visibility="private",
        dataset_metadata_json={},
        paired_study_mode="existing",
        paired_study=existing_study,
        current_user=user,
        mount_name="external-control",
        settings_obj=settings_obj,
        commit=True,
    )

    assert result.study is existing_study
    assert result.mount.study_id == "202605000999"
    assert result.dataset_asset.metadata_json["paired_study"]["mode"] == "existing"
    assert result.next_upload.study_id == "202605000999"
    assert not any(isinstance(item, Study) for item in db.added)
    # Phase 2 (docs_v2/3-25): 新模型字段（existing mode 下主 Study 是已有的）
    assert result.dataset_version.state == "draft"
    assert result.dataset_asset.primary_study_id == "202605000999"
    assert result.dataset_asset.current_version_id == result.dataset_version.id
    assert result.mount.dataset_version_id == result.dataset_version.id
    assert not any(isinstance(item, StudySettings) for item in db.added)
    assert not any(isinstance(item, AuditEvent) for item in db.added)


def test_dataset_bootstrap_route_is_registered() -> None:
    from test_dataset_qa_mock_run import load_datasets_router

    datasets = load_datasets_router()
    routes = {(route.path, tuple(sorted(route.methods))) for route in datasets.asset_router.routes}
    assert ("/api/v1/dataset-assets/bootstrap", ("POST",)) in routes
