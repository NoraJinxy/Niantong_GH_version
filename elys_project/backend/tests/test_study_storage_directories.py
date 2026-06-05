"""
Purpose: Test Study storage directory creation while preserving legacy Study directories.
Related: app/routers/studies.py, app/config.py, docs_v2/4-00.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import ModuleType, SimpleNamespace
import importlib
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

        def get(self, *args, **kwargs):
            return lambda fn: fn

        def post(self, *args, **kwargs):
            return lambda fn: fn

        def put(self, *args, **kwargs):
            return lambda fn: fn

        def delete(self, *args, **kwargs):
            return lambda fn: fn

    fastapi.APIRouter = APIRouter
    fastapi.Body = lambda default=None, **kwargs: default
    fastapi.Depends = lambda dependency=None, **kwargs: None
    fastapi.HTTPException = HTTPException
    fastapi.status = SimpleNamespace(
        HTTP_201_CREATED=201,
        HTTP_204_NO_CONTENT=204,
        HTTP_400_BAD_REQUEST=400,
        HTTP_403_FORBIDDEN=403,
        HTTP_404_NOT_FOUND=404,
        HTTP_409_CONFLICT=409,
        HTTP_422_UNPROCESSABLE_ENTITY=422,
        HTTP_500_INTERNAL_SERVER_ERROR=500,
    )
    sys.modules["fastapi"] = fastapi

    auth = ModuleType("app.routers.auth")
    auth.get_current_user = lambda: None
    auth.router = APIRouter()
    sys.modules["app.routers.auth"] = auth


def import_studies_module():
    routers_pkg = ModuleType("app.routers")
    routers_pkg.__path__ = [str(BACKEND_DIR / "app" / "routers")]
    sys.modules["app.routers"] = routers_pkg

    for module_name in ("app.services.studies", "app.services"):
        module = sys.modules.get(module_name)
        if getattr(module, "__path__", None) == [] or (module is not None and not getattr(module, "__file__", None)):
            sys.modules.pop(module_name, None)
    for module_name in ("app.models", "app.database", "sqlalchemy", "sqlalchemy.orm", "sqlalchemy.exc"):
        module = sys.modules.get(module_name)
        if module is not None and not getattr(module, "__file__", None):
            sys.modules.pop(module_name, None)
    sys.modules.pop("app.routers.studies", None)
    install_fastapi_stub()
    return importlib.import_module("app.routers.studies")


def make_settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        STUDIES_DIR=str(tmp_path / "studies"),
        STUDIES_STORAGE_ROOT=str(tmp_path / "storage" / "studies"),
    )


def make_study(tmp_path: Path) -> SimpleNamespace:
    study_id = "202605000001"
    return SimpleNamespace(
        id=study_id,
        code="demo-study",
        name="Demo Study",
        data_root=str(tmp_path / "studies" / study_id),
    )


def test_create_study_storage_directories_keeps_legacy_and_study_roots(tmp_path, monkeypatch) -> None:
    studies = import_studies_module()
    study = make_study(tmp_path)
    monkeypatch.setattr(studies, "settings", make_settings(tmp_path))

    studies.create_study_storage_directories(study)

    legacy_root = Path(study.data_root)
    for relative in studies.LEGACY_PROJECT_DIRECTORIES:
        assert (legacy_root / relative).is_dir()
    assert (legacy_root / "source_uploads").is_dir()
    assert (legacy_root / "fifdata").is_dir()
    assert (legacy_root / "pipeline_runs").is_dir()

    study_root = Path(studies.settings.STUDIES_STORAGE_ROOT) / study.id
    for relative in studies.STUDY_STORAGE_DIRECTORIES:
        assert (study_root / relative).is_dir()

    legacy_marker = json.loads((legacy_root / ".elys_study.json").read_text(encoding="utf-8"))
    study_marker = json.loads((study_root / ".elys_study.json").read_text(encoding="utf-8"))
    assert legacy_marker["data_root"] == study.data_root
    assert study_marker["study_storage_uri"] == f"elys://studies/{study.id}"

    policy = studies.study_storage_policy(study)
    assert policy["legacy_data_root"] == study.data_root
    assert policy["study_storage_uri"] == f"elys://studies/{study.id}"


def test_study_response_schema_preserves_legacy_api_shape() -> None:
    import_studies_module()
    from app.schemas.study import StudyResponse

    fields = set(StudyResponse.model_fields)
    assert "data_root" in fields
    assert "study_storage_root" not in fields
    assert "study_storage_uri" not in fields


def test_remove_study_directory_cleans_legacy_and_study_roots(tmp_path, monkeypatch) -> None:
    studies = import_studies_module()
    study = make_study(tmp_path)
    monkeypatch.setattr(studies, "settings", make_settings(tmp_path))

    studies.create_study_storage_directories(study)
    studies.remove_study_directory(study)

    assert not Path(study.data_root).exists()
    assert not (Path(studies.settings.STUDIES_STORAGE_ROOT) / study.id).exists()
