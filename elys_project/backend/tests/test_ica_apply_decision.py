from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import os
import sys


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if os.environ.get("DEBUG", "").lower() == "release":
    os.environ["DEBUG"] = "false"
os.environ.setdefault("SECRET_KEY", "test-secret-key")


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

from app.pipeline.dispatcher import NodeDispatcher  # noqa: E402
from app.pipeline.executor import PipelineExecutor  # noqa: E402
from app.routers.pipelines import can_submit_interaction_decision, job_interaction  # noqa: E402


def _context(*, params: dict | None = None, output_json: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        params=params or {},
        job=SimpleNamespace(output_json=output_json or {}),
    )


def test_ica_apply_ignores_stale_node_params_without_current_decision():
    context = _context(
        params={
            "excluded_components": [0, 2],
            "excluded_components_by_dataset": {"old-matrix": [1]},
            "decision_version": 3,
        }
    )

    assert NodeDispatcher._ica_decision(context) is None


def test_ica_apply_uses_current_job_interaction_decision():
    context = _context(
        params={"decision_version": 99},
        output_json={
            "interaction": {
                "decision": {
                    "excluded_components": ["2", "0"],
                    "excluded_components_by_dataset": {"dataset-a": ["1", "3"]},
                    "decision_version": 4,
                }
            }
        },
    )

    decision = NodeDispatcher._ica_decision(context)

    assert decision is not None
    assert decision["excluded_components"] == [0, 2]
    assert decision["excluded_components_by_dataset"] == {"dataset-a": [1, 3]}
    assert decision["decision_version"] == 4


def test_interaction_decision_can_be_reopened_after_completed_execution():
    assert can_submit_interaction_decision(
        SimpleNamespace(status="running"),
        SimpleNamespace(status="waiting_user_input"),
    )
    assert can_submit_interaction_decision(
        SimpleNamespace(status="completed"),
        SimpleNamespace(status="success"),
    )
    assert can_submit_interaction_decision(
        SimpleNamespace(status="completed"),
        SimpleNamespace(status="cached"),
    )
    assert not can_submit_interaction_decision(
        SimpleNamespace(status="running"),
        SimpleNamespace(status="success"),
    )
    assert not can_submit_interaction_decision(
        SimpleNamespace(status="completed"),
        SimpleNamespace(status="failed"),
    )


def test_apply_success_output_preserves_submitted_interaction_payload():
    interaction = {
        "type": "ica_component_selection",
        "status": "decision_submitted",
        "decision_version": 2,
        "preview_json": {"datasets": [{"ica_artifact_id": "ica-output-1"}]},
        "decision": {"excluded_components": [1], "decision_version": 1},
    }
    success_output = {
        "node_id": "apply",
        "node_type": "eeg/ica/apply",
        "outputs": {"output": []},
        "metadata": {"decision": interaction["decision"]},
    }

    preserved = PipelineExecutor._attach_interaction(success_output, interaction)

    assert PipelineExecutor._interaction_from_output_json(preserved) == interaction
    assert preserved["interaction"]["preview_json"]["datasets"][0]["ica_artifact_id"] == "ica-output-1"
    assert preserved["metadata"]["interaction"]["decision"]["excluded_components"] == [1]


def test_completed_apply_interaction_rebuilds_from_upstream_compute_output():
    raw_info = {
        "dataset_id": "raw-1",
        "source_dataset_id": "source-1",
        "subject": "sub-001",
        "task": "task-test",
        "run": "run-01",
    }
    ica_info = {
        "artifact_id": "ica-output-1",
        "source_dataset_id": "source-1",
        "component_preview": [
            {"index": 0, "label": "IC000"},
            {"index": 1, "label": "IC001"},
        ],
    }
    compute_job = SimpleNamespace(
        node_id="compute",
        node_type="eeg/ica/compute",
        topo_index=4,
        output_json={"outputs": {"output": [raw_info], "ica_matrix": [ica_info]}},
    )
    execution = SimpleNamespace(
        definition_snapshot={
            "graph": {
                "links": [
                    {"from": {"node": "compute", "port": "output"}, "to": {"node": "apply", "port": "input"}},
                    {
                        "from": {"node": "compute", "port": "ica_matrix"},
                        "to": {"node": "apply", "port": "ica_matrix"},
                    },
                ]
            }
        },
        jobs=[compute_job],
    )
    apply_job = SimpleNamespace(
        node_id="apply",
        node_type="eeg/ica/apply",
        topo_index=5,
        output_json={
            "metadata": {
                "decision": {
                    "excluded_components": [0],
                    "excluded_components_by_dataset": {"ica-output-1": [1]},
                    "decision_version": 3,
                }
            }
        },
        params_json={},
        execution=execution,
    )

    interaction = job_interaction(apply_job)

    assert interaction["type"] == "ica_component_selection"
    assert interaction["status"] == "decision_submitted"
    assert interaction["decision_version"] == 4
    assert interaction["decision"]["excluded_components_by_dataset"] == {"ica-output-1": [1]}
    assert interaction["preview_json"]["datasets"][0]["ica_artifact_id"] == "ica-output-1"
    assert interaction["preview_json"]["datasets"][0]["data_info"]["subject"] == "sub-001"
    assert [item["index"] for item in interaction["components"]] == [0, 1]
