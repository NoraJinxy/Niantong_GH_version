"""
Purpose: Test Pipeline Execution dependency snapshots and cleanup blockers.
Related: app/services/execution_dependencies.py, app/pipeline/executor.py, app/routers/pipelines.py.
"""

from __future__ import annotations

from datetime import datetime
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

import pytest  # noqa: E402

from app.models import StudyOutput, PipelineExecutionDependency, PipelineExecutionInput  # noqa: E402
from app.pipeline.contracts import NodeInput  # noqa: E402
from app.services.execution_dependencies import (  # noqa: E402
    ArtifactDependencyError,
    artifact_dependency_blockers,
    assert_artifact_can_be_deleted,
    record_execution_artifact_dependencies,
)


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
        self.added = []
        self.flushed = False

    def query(self, model):
        return FakeQuery(self, model)

    def add(self, row) -> None:
        self.added.append(row)

    def flush(self) -> None:
        self.flushed = True


def make_context():
    study = SimpleNamespace(id="202605000001")
    pipeline = SimpleNamespace(id=7)
    execution = SimpleNamespace(id=uuid.uuid4())
    job = SimpleNamespace(id=uuid.uuid4(), node_id="filter-1", node_type="eeg/filter/fir")
    node = {"id": "filter-1", "type": "eeg/filter/fir"}
    return study, pipeline, execution, job, node


def test_record_execution_artifact_dependencies_writes_input_snapshot_and_cross_execution_dependency() -> None:
    clear_lightweight_app_stubs()
    study, pipeline, execution, job, node = make_context()
    artifact_id = uuid.uuid4()
    upstream_execution_id = uuid.uuid4()
    artifact = SimpleNamespace(
        id=artifact_id,
        execution_id=upstream_execution_id,
        storage_uri=f"elys://studies/{study.id}/derived/aa/hash/output.fif",
        storage_path="derived/aa/hash/output.fif",
        sha256="artifact-sha",
    )
    db = FakeDb(rows={StudyOutput: [artifact]})
    inputs = {
        "input": NodeInput(
            port="input",
            data_infos=[
                {
                    "artifact_id": str(artifact_id),
                    "pipeline_execution_id": str(upstream_execution_id),
                    "source_dataset_id": str(uuid.uuid4()),
                    "storage_uri": artifact.storage_uri,
                    "storage_path": artifact.storage_path,
                    "content_hash": "artifact-sha",
                    "data_type": "raw",
                }
            ],
            metadata={"source_nodes": ["load-1"]},
        )
    }

    added_count = record_execution_artifact_dependencies(
        db,
        study=study,
        pipeline=pipeline,
        execution=execution,
        job=job,
        node=node,
        inputs=inputs,
    )

    input_rows = [row for row in db.added if isinstance(row, PipelineExecutionInput)]
    dependency_rows = [row for row in db.added if isinstance(row, PipelineExecutionDependency)]
    assert added_count == 2
    assert db.flushed is True
    assert input_rows[0].upstream_dataset_id == artifact_id
    assert input_rows[0].upstream_execution_id == upstream_execution_id
    assert input_rows[0].input_kind == "study_output"
    assert input_rows[0].storage_uri == artifact.storage_uri
    assert dependency_rows[0].depends_on_execution_id == upstream_execution_id
    assert dependency_rows[0].upstream_dataset_id == artifact_id
    assert dependency_rows[0].dependency_kind == "upstream_study_output"


def test_record_execution_artifact_dependencies_does_not_write_self_execution_dependency() -> None:
    clear_lightweight_app_stubs()
    study, pipeline, execution, job, node = make_context()
    artifact_id = uuid.uuid4()
    db = FakeDb()
    inputs = {
        "input": NodeInput(
            port="input",
            data_infos=[{"artifact_id": str(artifact_id), "pipeline_execution_id": str(execution.id), "storage_uri": "uri"}],
        )
    }

    record_execution_artifact_dependencies(db, study=study, pipeline=pipeline, execution=execution, job=job, node=node, inputs=inputs)

    assert any(isinstance(row, PipelineExecutionInput) for row in db.added)
    assert not any(isinstance(row, PipelineExecutionDependency) for row in db.added)


def test_artifact_dependency_blockers_prevent_cleanup() -> None:
    clear_lightweight_app_stubs()
    artifact_id = uuid.uuid4()
    downstream_execution_id = uuid.uuid4()
    input_row = SimpleNamespace(
        id=uuid.uuid4(),
        execution_id=downstream_execution_id,
        study_id="202605000001",
        pipeline_id=7,
        node_id="filter-1",
        node_type="eeg/filter/fir",
        input_slot="input",
        input_index=0,
        upstream_execution_id=uuid.uuid4(),
        upstream_dataset_id=artifact_id,
        storage_uri="elys://studies/202605000001/derived/aa/hash/output.fif",
        created_at=datetime(2026, 5, 21, 9, 0, 0),
    )
    dependency_row = SimpleNamespace(
        id=uuid.uuid4(),
        execution_id=downstream_execution_id,
        study_id="202605000001",
        depends_on_execution_id=input_row.upstream_execution_id,
        upstream_dataset_id=artifact_id,
        dependency_kind="upstream_study_output",
        metadata_json={"node_id": "filter-1"},
        created_at=datetime(2026, 5, 21, 9, 0, 1),
    )
    artifact = SimpleNamespace(id=artifact_id)
    db = FakeDb(rows={PipelineExecutionInput: [input_row], PipelineExecutionDependency: [dependency_row]})

    blockers = artifact_dependency_blockers(db, artifact=artifact)

    assert blockers[0]["source"] == "pipeline_execution_inputs"
    assert blockers[0]["execution_id"] == str(downstream_execution_id)
    with pytest.raises(ArtifactDependencyError) as exc_info:
        assert_artifact_can_be_deleted(db, artifact=artifact)
    assert exc_info.value.to_detail()["code"] == "PIPELINE_ARTIFACT_HAS_DOWNSTREAM_DEPENDENCIES"
