"""
Purpose: Test Pipeline DerivedDatasetStore writes to Study storage and previews resolve storage_uri.
Related: app/pipeline/derived_dataset_store.py, app/pipeline/previews.py, app/pipeline/cache.py.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys
import uuid


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

from app.pipeline.derived_dataset_store import DerivedDatasetStore  # noqa: E402
from app.pipeline.previews import build_derived_dataset_preview, resolve_derived_dataset_path  # noqa: E402


class FakeDerivedDataset:
    def __init__(self, **kwargs) -> None:
        self.id = uuid.uuid4()
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeDb:
    def __init__(self) -> None:
        self.added = []

    def add(self, record) -> None:
        self.added.append(record)

    def flush(self) -> None:
        return None


def fake_settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        STUDIES_DIR=str(tmp_path / "studies"),
        DATASETS_STORAGE_ROOT=str(tmp_path / "storage" / "datasets"),
        STUDIES_STORAGE_ROOT=str(tmp_path / "storage" / "studies"),
    )


def patch_storage_settings(monkeypatch, tmp_path: Path) -> None:
    import app.pipeline.derived_dataset_store as derived_dataset_store_module
    import app.services.storage as storage_module

    settings = fake_settings(tmp_path)
    monkeypatch.setattr(derived_dataset_store_module, "get_settings", lambda: settings)
    monkeypatch.setattr(storage_module, "get_settings", lambda: settings)


def make_context(tmp_path: Path):
    study = SimpleNamespace(id="202605000001", data_root=str(tmp_path / "studies" / "202605000001"))
    execution = SimpleNamespace(id=uuid.uuid4())
    job = SimpleNamespace(id=uuid.uuid4(), node_id="filter-1")
    Path(study.data_root).mkdir(parents=True, exist_ok=True)
    return study, execution, job


def test_derived_dataset_store_writes_new_files_to_study_content_addressed_storage(tmp_path, monkeypatch) -> None:
    clear_lightweight_app_stubs()
    patch_storage_settings(monkeypatch, tmp_path)
    study, execution, job = make_context(tmp_path)
    db = FakeDb()

    summary = DerivedDatasetStore(db, study, execution, job, derived_dataset_model=FakeDerivedDataset).save_json(
        "metrics.json",
        {"ok": True},
        kind="metadata",
        data_type="json",
        preview={"ok": True},
    )

    assert summary["storage_uri"].startswith(f"elys://studies/{study.id}/derived/")
    assert summary["storage_path"].startswith("derived/")
    derived_path = resolve_derived_dataset_path(study, db.added[0])
    assert derived_path.exists()
    assert derived_path.name == "metrics.json"
    assert derived_path.read_text(encoding="utf-8").strip().startswith("{")
    assert summary["sha256"] in derived_path.as_posix()
    assert not (Path(study.data_root) / "pipeline_runs").exists()


def test_derived_dataset_preview_resolves_study_storage_uri(tmp_path, monkeypatch) -> None:
    clear_lightweight_app_stubs()
    patch_storage_settings(monkeypatch, tmp_path)
    study, execution, job = make_context(tmp_path)
    db = FakeDb()
    summary = DerivedDatasetStore(db, study, execution, job, derived_dataset_model=FakeDerivedDataset).save_json(
        "summary.json",
        {"rows": 3},
        kind="metadata",
        data_type="json",
        preview={"rows": 3},
    )
    derived = db.added[0]

    preview = build_derived_dataset_preview(study, derived)

    assert preview["derived_dataset_id"] == str(derived.id)
    assert preview["storage_path"] == summary["storage_path"]
    assert preview["storage_uri"] == summary["storage_uri"]
    assert preview["preview_json"]["preview_source"] == "derived_dataset.preview_json"
    assert preview["preview_json"]["summary"] == {"rows": 3}
