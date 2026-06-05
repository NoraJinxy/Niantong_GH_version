"""
Purpose: Test LoadData resolves Dataset files and freezes Execution input snapshots.
Related: app/pipeline/load_data.py, app/pipeline/executor.py, app/engine/io.py.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import sys
import uuid


def clear_lightweight_app_stubs() -> None:
    for name in list(sys.modules):
        if not (
            name == "app.models"
            or name == "app.database"
            or name == "app.services"
            or name.startswith("app.database.")
            or name == "sqlalchemy"
            or name.startswith("sqlalchemy.")
            or name.startswith("app.models.")
            or name.startswith("app.services.")
        ):
            continue
        module = sys.modules.get(name)
        if module is not None and not getattr(module, "__file__", None):
            sys.modules.pop(name, None)


clear_lightweight_app_stubs()

from app.engine.io import resolve_path_reference
from app.models import Recording, DatasetFile, PipelineJob, PipelineExecutionInput, StudyDatasetMount, StudySettings
from app.pipeline.executor import PipelineExecutor
from app.pipeline.load_data import resolve_load_data_selection


class FakeColumn:
    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other):
        return lambda item: getattr(item, self.name) == other

    def in_(self, values):
        value_set = set(values)
        return lambda item: getattr(item, self.name) in value_set

    def is_(self, other):
        return lambda item: getattr(item, self.name) is other

    def desc(self):
        return self


class FakeDatasetModel:
    id = FakeColumn("id")
    study_id = FakeColumn("study_id")
    dataset_asset_id = FakeColumn("dataset_asset_id")
    imported_at = FakeColumn("imported_at")
    subject = object()
    current_version = object()


class FakeDatasetFileModel:
    id = FakeColumn("id")
    study_id = FakeColumn("study_id")
    dataset_id = FakeColumn("dataset_id")
    dataset_upload_id = FakeColumn("dataset_upload_id")
    file_role = FakeColumn("file_role")
    storage_uri = FakeColumn("storage_uri")
    logical_path = FakeColumn("logical_path")
    relative_path = FakeColumn("relative_path")
    created_at = FakeColumn("created_at")


class FakeStudyDatasetMountModel:
    id = FakeColumn("id")
    study_id = FakeColumn("study_id")
    dataset_asset_id = FakeColumn("dataset_asset_id")
    mount_name = FakeColumn("mount_name")
    is_active = FakeColumn("is_active")
    mounted_at = FakeColumn("mounted_at")


class FakeQuery:
    def __init__(self, db: "FakeDb", model) -> None:
        self.db = db
        self.model = model
        if model in db.model_rows:
            self.items = list(db.model_rows[model])
        elif model is Recording:
            self.items = list(db.datasets)
        elif model is DatasetFile:
            self.items = list(db.dataset_files)
        elif model is StudyDatasetMount:
            self.items = [db.mount] if db.mount else []
        else:
            self.items = []

    def options(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        for predicate in args:
            if callable(predicate):
                self.items = [item for item in self.items if predicate(item)]
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return list(self.items)

    def first(self):
        return self.items[0] if self.items else None

    def scalar(self):
        return None


class FakeDb:
    def __init__(self, *, datasets=None, dataset_files=None, mount=None, model_rows=None) -> None:
        self.datasets = datasets or []
        self.dataset_files = dataset_files or []
        self.mount = mount
        self.model_rows = model_rows or {}
        self.added = []

    def query(self, model):
        return FakeQuery(self, model)

    def add(self, record) -> None:
        self.added.append(record)

    def flush(self) -> None:
        return None


def make_dataset_context(tmp_path: Path):
    study = SimpleNamespace(id="202605000001", data_root=str(tmp_path / "study"))
    Path(study.data_root).mkdir(parents=True, exist_ok=True)
    canonical = Path(study.data_root) / "fifdata" / "sub-001_raw.fif"
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_bytes(b"fif")

    dataset_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    version_id = uuid.uuid4()
    dataset_file_id = uuid.uuid4()
    dataset = SimpleNamespace(
        id=dataset_id,
        study_id=study.id,
        dataset_asset_id=asset_id,
        subject_id=uuid.uuid4(),
        subject=SimpleNamespace(bids_subject_id="sub-001"),
        session="ses-01",
        task="task-rest",
        run="run-01",
        source_format="EDF",
        source_path="sourcedata/raw.edf",
        fif_path="fifdata/sub-001_raw.fif",
        current_version_id=upload_id,
        current_version=SimpleNamespace(version_seq=1, fif_dir="fifdata", sidecar_paths={}),
        file_size=3,
        checksum="source-checksum",
        n_channels=2,
        sfreq=100.0,
        duration_seconds=1.0,
        n_events=0,
        qa_status="converted",
        imported_at=datetime.utcnow(),
    )
    dataset_file = SimpleNamespace(
        id=dataset_file_id,
        study_id=study.id,
        recording_id=dataset_id,
        recording_version_id=upload_id,
        dataset_version_id=version_id,
        file_role="canonical_fif",
        storage_uri=f"study://{study.id}/fifdata/sub-001_raw.fif",
        relative_path="fifdata/sub-001_raw.fif",
        logical_path="derivatives/elys-canonical-fif/sub-001/sub-001_raw.fif",
        sha256="canonical-sha256",
        file_size=3,
        created_at=datetime.utcnow(),
    )
    mount = SimpleNamespace(
        id=uuid.uuid4(),
        study_id=study.id,
        dataset_asset_id=asset_id,
        mount_name="raw-working",
        selection_json={"dataset_filter": {"subjects": "all"}},
        is_active=True,
    )
    return study, dataset, dataset_file, mount


def install_filtering_models(monkeypatch):
    from app.pipeline import executor, load_data

    monkeypatch.setattr(load_data, "Recording", FakeDatasetModel)
    monkeypatch.setattr(load_data, "DatasetFile", FakeDatasetFileModel)
    monkeypatch.setattr(load_data, "StudyDatasetMount", FakeStudyDatasetMountModel)
    monkeypatch.setattr(load_data, "joinedload", lambda *args, **kwargs: None)
    monkeypatch.setattr(load_data, "or_", lambda *predicates: lambda item: any(predicate(item) for predicate in predicates))
    monkeypatch.setattr(executor, "DatasetFile", FakeDatasetFileModel)
    return load_data


def test_load_data_resolves_canonical_dataset_file_snapshot(tmp_path) -> None:
    clear_lightweight_app_stubs()
    study, dataset, dataset_file, mount = make_dataset_context(tmp_path)
    db = FakeDb(datasets=[dataset], dataset_files=[dataset_file], mount=mount)

    resolved = resolve_load_data_selection(
        db=db,
        study=study,
        params={"selection_mode": "filter", "dataset_filter": {"mount_name": "raw-working"}},
        node_id="load-1",
    )

    assert resolved.valid is True
    assert resolved.dataset_count == 1
    data_info = resolved.data_infos[0]
    assert data_info.dataset_file_id == str(dataset_file.id)
    assert data_info.file_role == "canonical_fif"
    assert data_info.storage_uri == dataset_file.storage_uri
    assert data_info.logical_path == dataset_file.logical_path
    assert data_info.sha256 == "canonical-sha256"
    assert data_info.mount_id == str(mount.id)
    assert data_info.mount_name == "raw-working"


def test_load_data_defaults_to_active_mount_assets_with_study_fallback(monkeypatch, tmp_path) -> None:
    load_data = install_filtering_models(monkeypatch)
    study, mounted_dataset, _dataset_file, mount = make_dataset_context(tmp_path)
    external_study_id = "202605000099"
    mounted_dataset.study_id = external_study_id
    own_dataset = SimpleNamespace(
        **{
            **mounted_dataset.__dict__,
            "id": uuid.uuid4(),
            "study_id": study.id,
            "dataset_asset_id": uuid.uuid4(),
        }
    )
    hidden_dataset = SimpleNamespace(
        **{
            **mounted_dataset.__dict__,
            "id": uuid.uuid4(),
            "study_id": "202605000098",
            "dataset_asset_id": uuid.uuid4(),
        }
    )
    db = FakeDb(
        model_rows={
            FakeDatasetModel: [mounted_dataset, own_dataset, hidden_dataset],
            FakeStudyDatasetMountModel: [mount],
        }
    )

    result = load_data._load_filter_datasets(
        db,
        study,
        {},
        mounted_dataset_asset_ids=[mount.dataset_asset_id],
    )

    assert mounted_dataset in result
    assert own_dataset in result
    assert hidden_dataset not in result


def test_load_data_validates_direct_dataset_asset_filter_against_active_mount(monkeypatch, tmp_path) -> None:
    load_data = install_filtering_models(monkeypatch)
    study, _dataset, _dataset_file, mount = make_dataset_context(tmp_path)
    db = FakeDb(model_rows={FakeStudyDatasetMountModel: [mount]})

    merged, issue = load_data._resolve_mount_dataset_filter(
        db=db,
        study=study,
        dataset_filter={"dataset_asset_id": str(mount.dataset_asset_id)},
        node_id="load-1",
        node_type="eeg/data/load",
    )

    assert issue is None
    assert merged["dataset_asset_id"] == str(mount.dataset_asset_id)
    assert merged["mount_id"] == str(mount.id)
    assert merged["mount_name"] == "raw-working"

    _merged, missing_issue = load_data._resolve_mount_dataset_filter(
        db=db,
        study=study,
        dataset_filter={"dataset_asset_id": str(uuid.uuid4())},
        node_id="load-1",
        node_type="eeg/data/load",
    )
    assert missing_issue is not None
    assert missing_issue.code == "LOAD_DATA_DATASET_ASSET_NOT_MOUNTED"


def test_latest_dataset_file_uses_dataset_identity_not_current_study_study(monkeypatch, tmp_path) -> None:
    load_data = install_filtering_models(monkeypatch)
    study, dataset, dataset_file, _mount = make_dataset_context(tmp_path)
    dataset.study_id = "202605000099"
    dataset_file.study_id = dataset.study_id
    db = FakeDb(model_rows={FakeDatasetFileModel: [dataset_file]})

    found = load_data._latest_dataset_file(
        db,
        study=study,
        dataset=dataset,
        file_role="canonical_fif",
        current_upload_only=True,
    )

    assert found is dataset_file


def test_prepare_execution_writes_external_mount_file_snapshot_columns(monkeypatch, tmp_path) -> None:
    install_filtering_models(monkeypatch)
    study, dataset, dataset_file, mount = make_dataset_context(tmp_path)
    external_study_id = "202605000099"
    dataset.study_id = external_study_id
    dataset_file.study_id = external_study_id
    canonical = tmp_path / "mounted-canonical.fif"
    canonical.write_bytes(b"fif")
    dataset_file.storage_uri = str(canonical)
    db = FakeDb(
        model_rows={
            FakeDatasetModel: [dataset],
            FakeDatasetFileModel: [dataset_file],
            FakeStudyDatasetMountModel: [mount],
        }
    )
    pipeline = SimpleNamespace(
        id=7,
        definition_json={
            "graph": {
                "nodes": [
                    {
                        "id": "load-1",
                        "type": "eeg/data/load",
                        "title": "LoadData",
                        "params": {"selection_mode": "filter", "dataset_filter": {"mount_name": "raw-working"}},
                    }
                ],
                "links": [],
            }
        },
    )
    execution = SimpleNamespace(id=uuid.uuid4(), definition_snapshot=pipeline.definition_json, node_count=0, dataset_count=0)

    PipelineExecutor(db).prepare_execution(study=study, pipeline=pipeline, execution=execution)

    input_rows = [record for record in db.added if isinstance(record, PipelineExecutionInput)]
    dataset_input = next(record for record in input_rows if record.input_kind == "dataset_file")
    assert dataset_input.dataset_asset_id == dataset.dataset_asset_id
    assert dataset_input.dataset_file_id == dataset_file.id
    assert dataset_input.storage_uri == dataset_file.storage_uri
    assert dataset_input.logical_path == dataset_file.logical_path
    assert dataset_input.sha256 == dataset_file.sha256
    assert dataset_input.resolved_metadata_json["mount"]["mount_name"] == "raw-working"
    assert dataset_input.resolved_metadata_json["file_snapshot"]["dataset_file_id"] == str(dataset_file.id)


def test_prepare_execution_writes_dataset_file_snapshot_columns(tmp_path) -> None:
    clear_lightweight_app_stubs()
    study, dataset, dataset_file, mount = make_dataset_context(tmp_path)
    db = FakeDb(datasets=[dataset], dataset_files=[dataset_file], mount=mount)
    pipeline = SimpleNamespace(
        id=7,
        definition_json={
            "graph": {
                "nodes": [
                    {
                        "id": "load-1",
                        "type": "eeg/data/load",
                        "title": "LoadData",
                        "params": {"selection_mode": "filter", "dataset_filter": {"mount_name": "raw-working"}},
                    }
                ],
                "links": [],
            }
        },
    )
    execution = SimpleNamespace(id=uuid.uuid4(), definition_snapshot=pipeline.definition_json, node_count=0, dataset_count=0)

    PipelineExecutor(db).prepare_execution(study=study, pipeline=pipeline, execution=execution)

    input_rows = [record for record in db.added if isinstance(record, PipelineExecutionInput)]
    dataset_input = next(record for record in input_rows if record.input_kind == "dataset_file")
    assert dataset_input.dataset_file_id == dataset_file.id
    assert dataset_input.file_role == "canonical_fif"
    assert dataset_input.storage_uri == dataset_file.storage_uri
    assert dataset_input.logical_path == dataset_file.logical_path
    assert dataset_input.sha256 == "canonical-sha256"
    assert dataset_input.resolved_metadata_json["file_snapshot"]["storage_uri"] == dataset_file.storage_uri


def test_prepare_execution_uses_execution_selection_override_without_mutating_pipeline_definition(tmp_path) -> None:
    clear_lightweight_app_stubs()
    study, dataset, dataset_file, mount = make_dataset_context(tmp_path)
    db = FakeDb(datasets=[dataset], dataset_files=[dataset_file], mount=mount)
    pipeline = SimpleNamespace(
        id=7,
        definition_json={
            "graph": {
                "nodes": [
                    {
                        "id": "load-1",
                        "type": "eeg/data/load",
                        "title": "LoadData",
                        "params": {"selection_mode": "filter", "dataset_filter": {"mount_name": "raw-working"}},
                    }
                ],
                "links": [],
            }
        },
    )
    selection_override = {
        "load-1": {
            "selection_mode": "explicit",
            "dataset_ids": [str(dataset.id)],
            "dataset_filter": {"require_fif": True},
        }
    }
    execution = SimpleNamespace(
        id=uuid.uuid4(),
        definition_snapshot=pipeline.definition_json,
        node_count=0,
        dataset_count=0,
        result_json={"selection_override": selection_override},
    )

    PipelineExecutor(db).prepare_execution(study=study, pipeline=pipeline, execution=execution)

    input_rows = [record for record in db.added if isinstance(record, PipelineExecutionInput)]
    selector_input = next(record for record in input_rows if record.input_kind == "selector")
    dataset_input = next(record for record in input_rows if record.input_kind == "dataset_file")
    job = next(record for record in db.added if isinstance(record, PipelineJob))

    assert selector_input.selector_json["override_applied"] is True
    assert selector_input.selector_json["selection_override"] == selection_override["load-1"]
    assert selector_input.selector_json["params"]["selection_mode"] == "explicit"
    assert selector_input.selector_json["dataset_ids"] == [str(dataset.id)]
    assert selector_input.selector_json["base_params"]["selection_mode"] == "filter"
    assert dataset_input.selector_json["selection_override"] == selection_override["load-1"]
    assert job.params_json["selection_mode"] == "explicit"
    assert pipeline.definition_json["graph"]["nodes"][0]["params"]["selection_mode"] == "filter"
    assert pipeline.definition_json["graph"]["nodes"][0]["params"]["dataset_filter"] == {"mount_name": "raw-working"}


def test_engine_io_resolves_storage_uri_before_legacy_paths(tmp_path) -> None:
    clear_lightweight_app_stubs()
    study, _dataset, dataset_file, _mount = make_dataset_context(tmp_path)

    resolved_path = resolve_path_reference(
        {
            "study_id": study.id,
            "study_root": study.data_root,
            "storage_uri": dataset_file.storage_uri,
            "fif_abs_path": str(Path(study.data_root) / "missing.fif"),
        },
        ("storage_uri", "fif_abs_path"),
    )

    assert resolved_path == Path(study.data_root) / "fifdata" / "sub-001_raw.fif"
