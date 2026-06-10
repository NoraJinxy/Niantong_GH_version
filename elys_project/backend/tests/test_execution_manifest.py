"""
Purpose: Test Pipeline Execution manifest generation for completed and failed executions.
Related: app/pipeline/execution_manifest.py, app/pipeline/executor.py, app/routers/pipelines.py.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
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

from app.models import AsyncTask, StudyOutput, PipelineJob, PipelineExecutionDependency, PipelineExecutionInput, TaskEvent  # noqa: E402
from app.pipeline.execution_manifest import generate_execution_manifest, read_execution_manifest  # noqa: E402


class FakeQuery:
    def __init__(self, db: "FakeDb", model) -> None:
        self.db = db
        self.model = model

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return list(self.db.rows.get(self.model, []))

    def first(self):
        rows = self.all()
        return rows[0] if rows else None


class FakeDb:
    def __init__(self, rows: dict[type, list] | None = None) -> None:
        self.rows = rows or {}

    def query(self, model):
        return FakeQuery(self, model)


def fake_settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        STUDIES_DIR=str(tmp_path / "studies"),
        ELYS_STORAGE_ROOT=str(tmp_path / "storage"),
        DATASETS_STORAGE_ROOT=str(tmp_path / "storage" / "datasets"),
        STUDIES_STORAGE_ROOT=str(tmp_path / "storage" / "studies"),
        TRASH_STORAGE_ROOT=str(tmp_path / "storage" / "trash"),
    )


def patch_storage_settings(monkeypatch, tmp_path: Path) -> None:
    import app.services.storage as storage_module

    monkeypatch.setattr(storage_module, "get_settings", lambda: fake_settings(tmp_path))


def make_execution(status: str):
    return SimpleNamespace(
        id=uuid.uuid4(),
        study_id="202605000001",
        pipeline_id=7,
        pipeline_version=3,
        execution_seq=4,
        trigger="manual",
        status=status,
        execution_mode="analysis",
        node_count=1,
        dataset_count=1,
        definition_snapshot={
            "graph": {
                "nodes": [{"id": "load-1", "type": "eeg/data/load", "params": {"selection_mode": "filter"}}],
                "links": [],
            }
        },
        manifest_json={},
        result_json={
            "warnings": [{"code": "TEST_WARNING", "message": "kept for manifest"}],
            "data_infos_by_node": {"load-1": [{"dataset_file_id": "file-1"}]},
            "node_results": [{"node_id": "load-1", "status": status}],
        },
        error_json={},
        started_by=uuid.uuid4(),
        started_at=datetime(2026, 5, 21, 8, 0, 0),
        finished_at=datetime(2026, 5, 21, 8, 0, 5),
    )


def make_rows(execution, *, failed: bool = False) -> dict[type, list]:
    job_id = uuid.uuid4()
    artifact_id = uuid.uuid4()
    task_id = uuid.uuid4()
    input_row = SimpleNamespace(
        id=uuid.uuid4(),
        execution_id=execution.id,
        study_id=execution.study_id,
        pipeline_id=execution.pipeline_id,
        job_id=job_id,
        node_id="load-1",
        node_type="eeg/data/load",
        input_slot="datasets",
        input_index=0,
        input_kind="dataset_file",
        dataset_asset_id=uuid.uuid4(),
        recording_id=uuid.uuid4(),
        recording_version_id=uuid.uuid4(),
        dataset_file_id=uuid.uuid4(),
        file_role="canonical_fif",
        storage_uri="elys://datasets/ds-001/versions/working/derivatives/elys-canonical-fif/sub-001_raw.fif",
        logical_path="derivatives/elys-canonical-fif/sub-001/sub-001_raw.fif",
        upstream_execution_id=None,
        upstream_dataset_id=None,
        selector_json={
            "dataset_filter": {"subjects": "all"},
            "selection_override": {"selection_mode": "explicit", "dataset_ids": ["dataset-1"]},
            "override_applied": True,
        },
        resolved_metadata_json={"file_snapshot": {"sha256": "input-sha256"}},
        sha256="input-sha256",
        created_at=datetime(2026, 5, 21, 8, 0, 1),
    )
    job = SimpleNamespace(
        id=job_id,
        execution_id=execution.id,
        study_id=execution.study_id,
        pipeline_id=execution.pipeline_id,
        node_id="load-1",
        node_type="eeg/data/load",
        node_title="LoadData",
        status="failed" if failed else "completed",
        topo_index=0,
        params_json={"selection_mode": "filter"},
        input_json={},
        output_json={"dataset_count": 1},
        input_hash="input-hash",
        params_hash="params-hash",
        node_hash="node-hash",
        trace_code="trace-code",
        error_json={"errors": execution.error_json.get("errors", [])} if failed else {},
        log_tail="boom" if failed else None,
        started_at=datetime(2026, 5, 21, 8, 0, 1),
        finished_at=datetime(2026, 5, 21, 8, 0, 4),
        duration_ms=3000,
    )
    artifact = SimpleNamespace(
        id=artifact_id,
        study_id=execution.study_id,
        execution_id=execution.id,
        job_id=job_id,
        source_dataset_id=None,
        kind="metadata",
        data_type="json",
        storage_path="derived/ab/hash/summary.json",
        storage_uri=f"elys://studies/{execution.study_id}/derived/ab/hash/summary.json",
        file_size=32,
        checksum="artifact-sha",
        sha256="artifact-sha",
        content_hash="artifact-sha",
        keep=True,
        cache_eligible=False,
        deleted_at=None,
        last_accessed_at=None,
        metadata_json={"node_id": "load-1"},
        preview_json={"rows": 1},
        created_at=datetime(2026, 5, 21, 8, 0, 4),
    )
    dependency = SimpleNamespace(
        id=uuid.uuid4(),
        study_id=execution.study_id,
        execution_id=execution.id,
        depends_on_execution_id=uuid.uuid4(),
        upstream_dataset_id=artifact_id,
        dependency_kind="upstream_execution",
        metadata_json={"reason": "test"},
        created_at=datetime(2026, 5, 21, 8, 0, 2),
    )
    task = SimpleNamespace(
        id=task_id,
        celery_task_id=str(task_id),
        task_type="pipeline_execution",
        queue_name="workflows",
        status="failed" if failed else "succeeded",
        progress=Decimal("100.00"),
        study_id=execution.study_id,
        resource_kind="pipeline_execution",
        resource_id=execution.id,
        payload_json={"execution_id": str(execution.id)},
        result_json={"execution_status": execution.status},
        error_json=execution.error_json if failed else {},
        idempotency_key=None,
        created_by=execution.started_by,
        created_at=datetime(2026, 5, 21, 8, 0, 0),
        started_at=datetime(2026, 5, 21, 8, 0, 1),
        finished_at=datetime(2026, 5, 21, 8, 0, 5),
        attempt=1,
        max_attempts=1,
    )
    task_event = SimpleNamespace(
        id=uuid.uuid4(),
        task_id=task_id,
        event_type="failed" if failed else "completed",
        status=task.status,
        progress=Decimal("100.00"),
        message="done" if not failed else "boom",
        payload_json={"execution_id": str(execution.id)},
        created_at=datetime(2026, 5, 21, 8, 0, 5),
    )
    return {
        PipelineExecutionInput: [input_row],
        PipelineJob: [job],
        StudyOutput: [artifact],
        PipelineExecutionDependency: [dependency],
        AsyncTask: [task],
        TaskEvent: [task_event],
    }


def test_execution_manifest_writes_completed_execution_file_and_summary(tmp_path, monkeypatch) -> None:
    clear_lightweight_app_stubs()
    patch_storage_settings(monkeypatch, tmp_path)
    study = SimpleNamespace(id="202605000001", name="Demo Study")
    execution = make_execution("completed")
    pipeline = SimpleNamespace(id=execution.pipeline_id, name="Prep", version=execution.pipeline_version)
    db = FakeDb(make_rows(execution))

    manifest = generate_execution_manifest(db, study=study, pipeline=pipeline, execution=execution)

    manifest_path = tmp_path / "storage" / "studies" / study.id / "executions" / str(execution.id) / "execution_manifest.json"
    logs_path = tmp_path / "storage" / "studies" / study.id / "executions" / str(execution.id) / "logs"
    assert manifest_path.exists()
    assert logs_path.is_dir()
    assert manifest["execution"]["status"] == "completed"
    assert manifest["inputs"][0]["dataset_file_id"]
    assert manifest["inputs"][0]["selector_json"]["override_applied"] is True
    assert manifest["inputs"][0]["selector_json"]["selection_override"]["selection_mode"] == "explicit"
    assert manifest["outputs"]["artifacts"][0]["storage_uri"].startswith(f"elys://studies/{study.id}/derived/")
    assert manifest["tasks"][0]["events"][0]["status"] == "succeeded"
    assert execution.manifest_json["manifest_uri"] == f"elys://studies/{study.id}/executions/{execution.id}/execution_manifest.json"
    assert execution.manifest_json["input_count"] == 1
    assert execution.manifest_json["artifact_count"] == 1
    assert read_execution_manifest(study, execution)["definition_snapshot_hash"] == execution.manifest_json["definition_snapshot_hash"]


def test_execution_manifest_writes_failed_execution_errors(tmp_path, monkeypatch) -> None:
    clear_lightweight_app_stubs()
    patch_storage_settings(monkeypatch, tmp_path)
    study = SimpleNamespace(id="202605000001", name="Demo Study")
    execution = make_execution("failed")
    execution.error_json = {"errors": [{"code": "NODE_FAILED", "message": "boom", "severity": "error"}]}
    pipeline = SimpleNamespace(id=execution.pipeline_id, name="Prep", version=execution.pipeline_version)
    db = FakeDb(make_rows(execution, failed=True))

    manifest = generate_execution_manifest(db, study=study, pipeline=pipeline, execution=execution)

    assert manifest["execution"]["status"] == "failed"
    assert manifest["errors"][0]["code"] == "NODE_FAILED"
    assert manifest["tasks"][0]["status"] == "failed"
    assert execution.manifest_json["status"] == "failed"
    assert execution.manifest_json["error_count"] == 1
