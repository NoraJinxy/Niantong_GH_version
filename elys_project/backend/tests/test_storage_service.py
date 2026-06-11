"""
Purpose: Test storage URI resolution for legacy study roots and new Dataset/Study roots.
Related: app/services/storage.py, app/config.py, docs_v2/4-00.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if getattr(sys.modules.get("app.services"), "__path__", None) == []:
    sys.modules.pop("app.services", None)

from app.config import Settings
from app.services.storage import StorageService, StorageUriError


def make_settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        STUDIES_DIR=str(tmp_path / "studies"),
        ELYS_STORAGE_ROOT=str(tmp_path / "storage"),
        DATASETS_STORAGE_ROOT=str(tmp_path / "storage" / "datasets"),
        STUDIES_STORAGE_ROOT=str(tmp_path / "storage" / "studies"),
        TRASH_STORAGE_ROOT=str(tmp_path / "storage" / "trash"),
    )


def test_storage_settings_expose_new_roots() -> None:
    settings = Settings()

    assert settings.ELYS_STORAGE_ROOT.endswith("/mnt/elys_data/storage")
    assert settings.DATASETS_STORAGE_ROOT.endswith("/mnt/elys_data/storage/datasets")
    assert settings.STUDIES_STORAGE_ROOT.endswith("/mnt/elys_data/storage/studies")
    assert settings.TRASH_STORAGE_ROOT.endswith("/mnt/elys_data/storage/trash")


def test_study_uri_resolves_against_legacy_studies_dir(tmp_path: Path) -> None:
    service = StorageService(settings=make_settings(tmp_path))

    ref = service.resolve_uri("study://202605000001/source_uploads/sub-001/eeg/raw.vhdr")

    assert ref.study_id == "202605000001"
    assert ref.relative_path == "source_uploads/sub-001/eeg/raw.vhdr"
    assert ref.path == (tmp_path / "studies" / "202605000001" / "source_uploads" / "sub-001" / "eeg" / "raw.vhdr").resolve()


def test_study_uri_can_use_database_study_root_resolver(tmp_path: Path) -> None:
    legacy_root = tmp_path / "custom-study-root"
    service = StorageService(
        settings=make_settings(tmp_path),
        study_root_resolver=lambda study_id: legacy_root / study_id,
    )

    ref = service.resolve_uri("study://study-a/fifdata/sub-001/run-01_raw.fif")

    assert ref.root == (legacy_root / "study-a").resolve()
    assert ref.path == (legacy_root / "study-a" / "fifdata" / "sub-001" / "run-01_raw.fif").resolve()


def test_dataset_uri_resolves_to_dataset_asset_root(tmp_path: Path) -> None:
    service = StorageService(settings=make_settings(tmp_path))

    # 两层重构：dataset URI = elys://datasets/{asset_id}/{logical_path}（无 versions/{label} 段）。
    ref = service.resolve_uri(
        "elys://datasets/ds-000001/BIDSdata/sub-001/eeg/sub-001_task-rest_eeg.fif"
    )

    assert ref.namespace == "datasets"
    assert ref.dataset_asset_id == "ds-000001"
    assert ref.dataset_version is None
    assert ref.root == (tmp_path / "storage" / "datasets" / "ds-000001").resolve()
    assert ref.relative_path == "BIDSdata/sub-001/eeg/sub-001_task-rest_eeg.fif"


def test_study_uri_resolves_to_study_root(tmp_path: Path) -> None:
    service = StorageService(settings=make_settings(tmp_path))

    ref = service.resolve_uri("elys://studies/st-202605000001/artifacts/runs/run-001/report.json")

    assert ref.namespace == "studies"
    assert ref.study_id == "st-202605000001"
    assert ref.root == (tmp_path / "storage" / "studies" / "st-202605000001").resolve()
    assert ref.path == (tmp_path / "storage" / "studies" / "st-202605000001" / "artifacts" / "runs" / "run-001" / "report.json").resolve()


def test_resolve_path_supports_legacy_study_relative_paths(tmp_path: Path) -> None:
    service = StorageService(settings=make_settings(tmp_path))

    path = service.resolve_path("fifdata/sub-001/run-01_raw.fif", study_id="202605000001")

    assert path == (tmp_path / "studies" / "202605000001" / "fifdata" / "sub-001" / "run-01_raw.fif").resolve()


@pytest.mark.parametrize(
    "uri",
    [
        "study://202605000001/../outside.txt",
        "study://202605000001/%2e%2e/outside.txt",
        "elys://datasets/ds-000001/BIDSdata/../../outside.txt",
        "elys://studies/st-202605000001/%2e%2e/outside.txt",
        "file:///tmp/outside.txt",
    ],
)
def test_storage_uri_rejects_unsafe_or_unsupported_paths(tmp_path: Path, uri: str) -> None:
    service = StorageService(settings=make_settings(tmp_path))

    with pytest.raises(StorageUriError):
        service.resolve_uri(uri)
