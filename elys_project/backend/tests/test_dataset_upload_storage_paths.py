"""
Purpose: Test Dataset upload path helpers for the standard Dataset storage root.
Related: app/routers/datasets.py, app/services/storage.py, docs_v2/4-20.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest

from test_dataset_qa_mock_run import load_datasets_router


def make_settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(DATASETS_STORAGE_ROOT=str(tmp_path / "storage" / "datasets"))


def test_make_import_job_dir_uses_dataset_working_storage_root(tmp_path, monkeypatch) -> None:
    datasets = load_datasets_router()
    monkeypatch.setattr(datasets, "settings", make_settings(tmp_path))

    study = SimpleNamespace(id="202605000001", data_root=str(tmp_path / "studies" / "202605000001"))
    asset = SimpleNamespace(id="ds-000001")

    job_dir = datasets.make_import_job_dir(
        study,
        "sub-001",
        "ses-01",
        "task-rest",
        "run-01",
        7,
        dataset_asset=asset,
    )

    assert job_dir == (
        tmp_path
        / "storage"
        / "datasets"
        / "ds-000001"
        / "versions"
        / "working"
        / "sourcedata"
        / "original_uploads"
        / "upload-007"
    )


def test_relative_to_study_returns_dataset_storage_uri_for_dataset_root(tmp_path, monkeypatch) -> None:
    datasets = load_datasets_router()
    monkeypatch.setattr(datasets, "settings", make_settings(tmp_path))

    study = SimpleNamespace(id="202605000001", data_root=str(tmp_path / "studies" / "202605000001"))
    path = (
        tmp_path
        / "storage"
        / "datasets"
        / "ds-000001"
        / "versions"
        / "working"
        / "sourcedata"
        / "original_uploads"
        / "upload-001"
        / "raw.edf"
    )

    assert (
        datasets.relative_to_study(study, path)
        == "elys://datasets/ds-000001/versions/working/sourcedata/original_uploads/upload-001/raw.edf"
    )


def test_resolve_study_relative_path_accepts_dataset_storage_uri(tmp_path, monkeypatch) -> None:
    datasets = load_datasets_router()
    monkeypatch.setattr(datasets, "settings", make_settings(tmp_path))

    study = SimpleNamespace(id="202605000001", data_root=str(tmp_path / "studies" / "202605000001"))
    path = datasets.resolve_study_relative_path(
        study,
        "elys://datasets/ds-000001/versions/working/sourcedata/original_uploads/upload-001/raw.edf",
    )

    assert path == (
        tmp_path
        / "storage"
        / "datasets"
        / "ds-000001"
        / "versions"
        / "working"
        / "sourcedata"
        / "original_uploads"
        / "upload-001"
        / "raw.edf"
    )


def test_archive_uploads_can_write_directly_under_upload_directory(tmp_path) -> None:
    datasets = load_datasets_router()

    class FakeUpload:
        filename = "raw.edf"

        def __init__(self) -> None:
            self._chunks = [b"abc", b""]
            self.closed = False

        async def read(self, size: int) -> bytes:
            return self._chunks.pop(0)

        async def close(self) -> None:
            self.closed = True

    upload = FakeUpload()
    item = datasets.UploadItem(upload=upload, relative_path=Path("raw.edf"), extension=".edf")
    job_dir = tmp_path / "upload-001"

    archived = asyncio.run(datasets.archive_uploads({".edf": item}, job_dir, files_subdir=None))

    assert archived[".edf"] == job_dir / "raw.edf"
    assert (job_dir / "raw.edf").read_bytes() == b"abc"
    assert upload.closed is True


class FakeDb:
    def __init__(self) -> None:
        self.records = []

    def add(self, record) -> None:
        self.records.append(record)


def make_dataset_context(tmp_path: Path, datasets):
    study = SimpleNamespace(id="202605000001", data_root=str(tmp_path / "studies" / "202605000001"))
    dataset = SimpleNamespace(id=uuid.uuid4(), study_id=study.id)
    upload_record = SimpleNamespace(id=uuid.uuid4(), upload_seq=1)
    dataset_version = SimpleNamespace(id=uuid.uuid4(), dataset_asset_id="ds-000001", version_label="working")
    current_user = SimpleNamespace(id=uuid.uuid4())
    datasets.settings = make_settings(tmp_path)
    return study, dataset, upload_record, dataset_version, current_user


def file_records(db: FakeDb):
    return [record for record in db.records if hasattr(record, "file_role")]


def derivation_records(db: FakeDb):
    return [record for record in db.records if record.__class__.__name__ == "DatasetFileDerivation"]


def write_study_file(study, relative_path: str, content: bytes = b"x") -> str:
    path = Path(study.data_root) / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return relative_path


def write_dataset_file(tmp_path: Path, asset_id: str, logical_path: str, content: bytes = b"x") -> str:
    path = tmp_path / "storage" / "datasets" / asset_id / "versions" / "working" / logical_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return f"elys://datasets/{asset_id}/versions/working/{logical_path}"


def test_resolve_upload_dataset_asset_accepts_explicit_mounted_dataset_asset(monkeypatch) -> None:
    datasets = load_datasets_router()
    asset_id = uuid.uuid4()
    asset = SimpleNamespace(id=asset_id, status="active")
    mount = SimpleNamespace(id=uuid.uuid4(), dataset_asset_id=asset_id, mount_name="primary", is_active=True, dataset_asset=asset)
    study = SimpleNamespace(id="202605000001")
    current_user = SimpleNamespace(id=uuid.uuid4())

    monkeypatch.setattr(datasets, "get_dataset_asset_for_user", lambda db, asset_id, user: asset)
    monkeypatch.setattr(datasets, "get_active_study_dataset_mount_for_asset", lambda db, study, dataset_asset: mount)

    resolved_asset, resolved_mount = datasets.resolve_upload_dataset_asset(
        SimpleNamespace(),
        study=study,
        current_user=current_user,
        dataset_asset_id=asset_id,
        mount_name=None,
    )

    assert resolved_asset is asset
    assert resolved_mount is mount


def test_resolve_upload_dataset_asset_rejects_unmounted_dataset_asset(monkeypatch) -> None:
    datasets = load_datasets_router()
    asset_id = uuid.uuid4()
    asset = SimpleNamespace(id=asset_id, status="active")
    study = SimpleNamespace(id="202605000001")
    current_user = SimpleNamespace(id=uuid.uuid4())

    monkeypatch.setattr(datasets, "get_dataset_asset_for_user", lambda db, asset_id, user: asset)
    monkeypatch.setattr(datasets, "get_active_study_dataset_mount_for_asset", lambda db, study, dataset_asset: None)

    with pytest.raises(datasets.HTTPException) as exc:
        datasets.resolve_upload_dataset_asset(
            SimpleNamespace(),
            study=study,
            current_user=current_user,
            dataset_asset_id=asset_id,
            mount_name=None,
        )

    assert exc.value.status_code == 409
    assert "尚未挂载" in exc.value.detail


def test_create_dataset_file_records_registers_standard_raw_bids_roles_for_edf(tmp_path, monkeypatch) -> None:
    datasets = load_datasets_router()
    monkeypatch.setattr(datasets, "settings", make_settings(tmp_path))
    study, dataset, upload_record, dataset_version, current_user = make_dataset_context(tmp_path, datasets)
    db = FakeDb()

    original = (
        tmp_path
        / "storage"
        / "datasets"
        / "ds-000001"
        / "versions"
        / "working"
        / "sourcedata"
        / "original_uploads"
        / "upload-001"
        / "raw.edf"
    )
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(b"edf")

    conversion = {
        "fif_dir": "fifdata/sub-001/ses-01/task-rest/run-01/upload-001",
        "fif_path": write_study_file(
            study,
            "fifdata/sub-001/ses-01/task-rest/run-01/upload-001/sub-001_ses-01_task-rest_run-01_raw.fif",
        ),
        "sidecar_paths": {
            "eeg": write_study_file(
                study,
                "fifdata/sub-001/ses-01/task-rest/run-01/upload-001/sub-001_ses-01_task-rest_run-01_eeg.json",
            ),
            "channels": write_study_file(
                study,
                "fifdata/sub-001/ses-01/task-rest/run-01/upload-001/sub-001_ses-01_task-rest_run-01_channels.tsv",
            ),
            "events": write_study_file(
                study,
                "fifdata/sub-001/ses-01/task-rest/run-01/upload-001/sub-001_ses-01_task-rest_run-01_events.tsv",
            ),
            "import": write_study_file(
                study,
                "fifdata/sub-001/ses-01/task-rest/run-01/upload-001/sub-001_ses-01_task-rest_run-01_import.json",
            ),
        },
    }

    datasets.create_dataset_file_records(
        db,
        study=study,
        dataset=dataset,
        upload_record=upload_record,
        dataset_version=dataset_version,
        primary_source=original,
        source_format="EDF",
        archived_paths=[original],
        conversion=conversion,
        current_user=current_user,
        bids_subject_id="sub-001",
        session="ses-01",
        task="task-rest",
        run="run-01",
    )

    files = file_records(db)
    roles = [record.file_role for record in files]
    assert "raw_source" in roles
    assert "sidecar" in roles
    assert "original_upload" in roles
    assert "raw_bids_data" in roles
    assert "raw_bids_eeg_json" in roles
    assert "raw_bids_channels" in roles
    assert "raw_bids_events" in roles
    assert "canonical_fif" in roles

    original_upload = next(record for record in files if record.file_role == "original_upload")
    assert original_upload.storage_uri.endswith("/sourcedata/original_uploads/upload-001/raw.edf")
    assert original_upload.logical_path == "sourcedata/original_uploads/upload-001/raw.edf"

    raw_bids_data = next(record for record in files if record.file_role == "raw_bids_data")
    assert raw_bids_data.storage_uri == original_upload.storage_uri
    assert raw_bids_data.logical_path == "raw_bids/sub-001/ses-01/eeg/sub-001_ses-01_task-rest_run-01_eeg.edf"
    assert raw_bids_data.metadata_json["view_kind"] == "raw_bids_logical"
    assert raw_bids_data.metadata_json["physical_storage_uri"] == original_upload.storage_uri

    eeg_json = next(record for record in files if record.file_role == "raw_bids_eeg_json")
    assert eeg_json.logical_path == "raw_bids/sub-001/ses-01/eeg/sub-001_ses-01_task-rest_run-01_eeg.json"
    assert {record.derivation_kind for record in derivation_records(db)} >= {
        "canonical_fif",
        "canonical_fif_eeg",
        "canonical_fif_channels",
        "canonical_fif_events",
    }


def test_create_dataset_file_records_registers_canonical_fif_provenance_and_derivations(tmp_path, monkeypatch) -> None:
    datasets = load_datasets_router()
    monkeypatch.setattr(datasets, "settings", make_settings(tmp_path))
    study, dataset, upload_record, dataset_version, current_user = make_dataset_context(tmp_path, datasets)
    db = FakeDb()

    original = (
        tmp_path
        / "storage"
        / "datasets"
        / "ds-000001"
        / "versions"
        / "working"
        / "sourcedata"
        / "original_uploads"
        / "upload-001"
        / "raw.edf"
    )
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(b"edf")
    canonical_prefix = "derivatives/elys-canonical-fif/sub-001/u001/sub-001_task-rest"
    canonical_fif_uri = write_dataset_file(tmp_path, "ds-000001", f"{canonical_prefix}_raw.fif")
    canonical_eeg_uri = write_dataset_file(tmp_path, "ds-000001", f"{canonical_prefix}_eeg.json")
    canonical_channels_uri = write_dataset_file(tmp_path, "ds-000001", f"{canonical_prefix}_channels.tsv")
    canonical_events_uri = write_dataset_file(tmp_path, "ds-000001", f"{canonical_prefix}_events.tsv")
    canonical_provenance_uri = write_dataset_file(
        tmp_path,
        "ds-000001",
        f"{canonical_prefix}_provenance.json",
        b'{"GeneratedBy":"test"}',
    )
    conversion = {
        "canonical_fif_dir": "elys://datasets/ds-000001/versions/working/derivatives/elys-canonical-fif/sub-001/u001",
        "canonical_fif_path": canonical_fif_uri,
        "canonical_sidecar_paths": {
            "eeg": canonical_eeg_uri,
            "channels": canonical_channels_uri,
            "events": canonical_events_uri,
            "provenance": canonical_provenance_uri,
        },
        "canonical_provenance_path": canonical_provenance_uri,
        "fif_dir": "fifdata/sub-001/ses-01/task-rest/run-01/upload-001",
        "fif_path": write_study_file(
            study,
            "fifdata/sub-001/ses-01/task-rest/run-01/upload-001/sub-001_ses-01_task-rest_run-01_raw.fif",
        ),
        "sidecar_paths": {
            "eeg": write_study_file(
                study,
                "fifdata/sub-001/ses-01/task-rest/run-01/upload-001/sub-001_ses-01_task-rest_run-01_eeg.json",
            ),
            "channels": write_study_file(
                study,
                "fifdata/sub-001/ses-01/task-rest/run-01/upload-001/sub-001_ses-01_task-rest_run-01_channels.tsv",
            ),
            "events": write_study_file(
                study,
                "fifdata/sub-001/ses-01/task-rest/run-01/upload-001/sub-001_ses-01_task-rest_run-01_events.tsv",
            ),
            "import": write_study_file(
                study,
                "fifdata/sub-001/ses-01/task-rest/run-01/upload-001/sub-001_ses-01_task-rest_run-01_import.json",
            ),
        },
        "provenance": {
            "SourceRawBIDS": {"logical_path": "raw_bids/sub-001/ses-01/eeg/sub-001_ses-01_task-rest_run-01_eeg.edf"},
            "SourceEvents": {"logical_path": "raw_bids/sub-001/ses-01/eeg/sub-001_ses-01_task-rest_run-01_events.tsv"},
            "SourceChannels": {"logical_path": "raw_bids/sub-001/ses-01/eeg/sub-001_ses-01_task-rest_run-01_channels.tsv"},
            "SourceSHA256": "source-sha",
            "ConversionParams": {"output_format": "FIF"},
            "GeneratedBy": {"Step": "generate_canonical_fif"},
        },
    }

    datasets.create_dataset_file_records(
        db,
        study=study,
        dataset=dataset,
        upload_record=upload_record,
        dataset_version=dataset_version,
        primary_source=original,
        source_format="EDF",
        archived_paths=[original],
        conversion=conversion,
        current_user=current_user,
        bids_subject_id="sub-001",
        session="ses-01",
        task="task-rest",
        run="run-01",
    )

    files = file_records(db)
    canonical_fif = next(record for record in files if record.file_role == "canonical_fif")
    assert canonical_fif.storage_uri == canonical_fif_uri
    assert canonical_fif.logical_path == f"{canonical_prefix}_raw.fif"
    assert canonical_fif.metadata_json["legacy_fif_path"].endswith("_raw.fif")

    provenance = next(record for record in files if record.file_role == "canonical_fif_provenance")
    assert provenance.storage_uri == canonical_provenance_uri
    assert provenance.logical_path == f"{canonical_prefix}_provenance.json"

    eeg_json = next(record for record in files if record.file_role == "raw_bids_eeg_json")
    assert eeg_json.metadata_json["physical_storage_uri"] == canonical_eeg_uri

    derivations = derivation_records(db)
    kinds = {record.derivation_kind for record in derivations}
    assert {"canonical_fif", "canonical_fif_provenance", "canonical_fif_events"} <= kinds
    canonical_derivation = next(record for record in derivations if record.derivation_kind == "canonical_fif")
    assert canonical_derivation.metadata_json["SourceSHA256"] == "source-sha"
    assert canonical_derivation.parameters_json["output_format"] == "FIF"


def test_create_dataset_file_records_registers_brainvision_logical_view_with_rewrite_warning(tmp_path, monkeypatch) -> None:
    datasets = load_datasets_router()
    monkeypatch.setattr(datasets, "settings", make_settings(tmp_path))
    study, dataset, upload_record, dataset_version, current_user = make_dataset_context(tmp_path, datasets)
    db = FakeDb()

    upload_root = (
        tmp_path
        / "storage"
        / "datasets"
        / "ds-000001"
        / "versions"
        / "working"
        / "sourcedata"
        / "original_uploads"
        / "upload-001"
    )
    paths = []
    for name in ("raw.vhdr", "raw.eeg", "raw.vmrk"):
        path = upload_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(name.encode("utf-8"))
        paths.append(path)

    datasets.create_dataset_file_records(
        db,
        study=study,
        dataset=dataset,
        upload_record=upload_record,
        dataset_version=dataset_version,
        primary_source=paths[0],
        source_format="BRAINVISION",
        archived_paths=paths,
        conversion={"sidecar_paths": {}},
        current_user=current_user,
        bids_subject_id="sub-001",
        session=None,
        task="task-rest",
        run=None,
    )

    raw_bids_records = [record for record in file_records(db) if record.file_role == "raw_bids_data"]
    assert len(raw_bids_records) == 3
    assert {record.logical_path for record in raw_bids_records} == {
        "raw_bids/sub-001/eeg/sub-001_task-rest_eeg.vhdr",
        "raw_bids/sub-001/eeg/sub-001_task-rest_eeg.eeg",
        "raw_bids/sub-001/eeg/sub-001_task-rest_eeg.vmrk",
    }
    rewrite_flags = {
        record.logical_path.rsplit(".", 1)[-1]: record.metadata_json.get("requires_reference_rewrite")
        for record in raw_bids_records
    }
    assert rewrite_flags["vhdr"] is True
    assert rewrite_flags["vmrk"] is True
    assert rewrite_flags["eeg"] is False
