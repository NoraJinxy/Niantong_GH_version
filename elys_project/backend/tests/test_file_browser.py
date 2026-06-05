"""
Purpose: Test Dataset file browser helpers and public API route registration.
Related: app/services/file_browser.py, app/routers/datasets.py, app/routers/pipelines.py.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import uuid


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

from app.services.file_browser import (  # noqa: E402
    build_dataset_file_tree,
    dataset_file_metadata,
    dataset_file_preview,
    download_filename,
    resolve_dataset_file_path,
)


def make_file_record(study_id: str, *, logical_path: str, relative_path: str, file_role: str = "raw_bids_eeg_json"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        study_id=study_id,
        recording_id=uuid.uuid4(),
        recording_version_id=uuid.uuid4(),
        dataset_version_id=uuid.uuid4(),
        file_role=file_role,
        storage_uri=f"study://{study_id}/{relative_path}",
        relative_path=relative_path,
        logical_path=logical_path,
        file_size=27,
        sha256="sha",
        mime_type="application/json",
        metadata_json={"sidecar": True},
        created_by=uuid.uuid4(),
        created_at=datetime(2026, 5, 21, 10, 0, 0),
    )


def test_dataset_file_metadata_preview_and_download_name_hide_absolute_paths(tmp_path) -> None:
    clear_lightweight_app_stubs()
    study_id = "202605000001"
    study_root = tmp_path / "study" / study_id
    relative_path = "raw_bids/sub-001/eeg/sub-001_task-rest_eeg.json"
    file_path = study_root / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text('{"TaskName": "rest", "SamplingFrequency": 100}', encoding="utf-8")
    study = SimpleNamespace(id=study_id, data_root=str(study_root))
    file_record = make_file_record(study_id, logical_path=relative_path, relative_path=relative_path)

    resolved = resolve_dataset_file_path(file_record, study=study)
    metadata = dataset_file_metadata(file_record, study=study)
    preview = dataset_file_preview(file_record, study=study)

    assert resolved == file_path.resolve()
    assert metadata["exists"] is True
    assert metadata["file_name"] == "sub-001_task-rest_eeg.json"
    assert metadata["download_name"] == "sub-001_task-rest_eeg.json"
    assert preview["preview_json"]["preview_kind"] == "json"
    assert preview["preview_json"]["summary"]["TaskName"] == "rest"
    assert str(tmp_path) not in json.dumps(metadata, ensure_ascii=False, default=str)
    assert download_filename(file_record) == "sub-001_task-rest_eeg.json"


def test_raw_bids_tree_uses_logical_paths_and_file_ids() -> None:
    clear_lightweight_app_stubs()
    study_id = "202605000001"
    eeg_json = make_file_record(
        study_id,
        logical_path="raw_bids/sub-001/eeg/sub-001_task-rest_eeg.json",
        relative_path="uploads/sub-001_task-rest_eeg.json",
        file_role="raw_bids_eeg_json",
    )
    channels = make_file_record(
        study_id,
        logical_path="raw_bids/sub-001/eeg/sub-001_task-rest_channels.tsv",
        relative_path="uploads/sub-001_task-rest_channels.tsv",
        file_role="raw_bids_channels",
    )
    original = make_file_record(
        study_id,
        logical_path="sourcedata/original_uploads/upload-1/raw.edf",
        relative_path="uploads/raw.edf",
        file_role="original_upload",
    )

    tree = build_dataset_file_tree([original, channels, eeg_json], prefix="raw_bids")

    assert tree["path"] == "raw_bids"
    assert tree["children"][0]["name"] == "sub-001"
    eeg_dir = tree["children"][0]["children"][0]
    leaf_names = [item["name"] for item in eeg_dir["children"]]
    assert leaf_names == ["sub-001_task-rest_channels.tsv", "sub-001_task-rest_eeg.json"]
    assert eeg_dir["children"][0]["file_id"] == str(channels.id)
    assert all("sourcedata" not in item["path"] for item in eeg_dir["children"])
