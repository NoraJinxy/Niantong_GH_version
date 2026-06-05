"""
Purpose: Test Pipeline validation catches NodeSpec entries without runtime executors.
Related: app/pipeline/validator.py, app/pipeline/dispatcher.py, app/pipeline/nodes/*.json.
"""

from __future__ import annotations

from pathlib import Path
import sys


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

from app.pipeline.dispatcher import NodeDispatcher  # noqa: E402
from app.pipeline.validator import validate_definition  # noqa: E402


VALID_LOAD_PARAMS = {
    "selection_mode": "filter",
    "dataset_filter": {
        "subjects": "all",
        "sessions": "all",
        "tasks": "all",
        "runs": "all",
        "qa_status": "all",
        "require_fif": True,
    },
}


def make_definition(filter_type: str) -> dict:
    return {
        "schema_version": "1.0",
        "graph": {
            "nodes": [
                {
                    "id": "load-1",
                    "type": "eeg/data/load",
                    "title": "LoadData",
                    "params": VALID_LOAD_PARAMS,
                },
                {
                    "id": "filter-1",
                    "type": filter_type,
                    "title": "Filter",
                    "params": {
                        "filter_mode": "bandpass",
                        "l_freq": 0.5,
                        "h_freq": 30.0,
                    },
                },
            ],
            "links": [
                {
                    "from": {"node": "load-1", "port": "output"},
                    "to": {"node": "filter-1", "port": "input"},
                }
            ],
        },
    }


def test_node_dispatcher_exposes_supported_node_types() -> None:
    dispatcher = NodeDispatcher()

    assert "eeg/data/load" in dispatcher.supported_node_types()
    assert dispatcher.supports("eeg/filter/fir")
    assert not dispatcher.supports("eeg/filter/butterworth")


def test_validate_definition_reports_nodespec_without_executor() -> None:
    result = validate_definition(make_definition("eeg/filter/butterworth"))

    assert not result.valid
    assert any(
        issue.code == "PIPELINE_NODE_EXECUTOR_NOT_IMPLEMENTED"
        and issue.node_id == "filter-1"
        and issue.node_type == "eeg/filter/butterworth"
        for issue in result.errors
    )


def test_validate_definition_allows_nodespec_with_executor() -> None:
    result = validate_definition(make_definition("eeg/filter/fir"))

    executor_errors = [
        issue for issue in result.errors if issue.code == "PIPELINE_NODE_EXECUTOR_NOT_IMPLEMENTED"
    ]
    assert executor_errors == []
