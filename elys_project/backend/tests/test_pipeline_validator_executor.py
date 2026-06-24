"""
Purpose: Test Pipeline validation — every registered NodeSpec has a runtime executor,
and unknown node types are reported.
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
from app.pipeline.registry import get_node_registry  # noqa: E402
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


def make_definition(filter_type: str, filter_params: dict | None = None) -> dict:
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
                    "params": filter_params
                    if filter_params is not None
                    else {"filter_type": "bandpass", "l_freq": 0.5, "h_freq": 30.0},
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


def test_every_registered_nodespec_has_executor() -> None:
    """合并后所有内置 NodeSpec 都应有 dispatcher handler（不再有「有 spec 无执行器」的幽灵）。"""
    dispatcher = NodeDispatcher()
    registry = get_node_registry()

    assert "eeg/data/load" in dispatcher.supported_node_types()
    assert dispatcher.supports("eeg/filter/apply")
    for spec in registry.list_specs():
        assert dispatcher.supports(spec["type"]), f"NodeSpec without executor: {spec['type']}"


def test_validate_definition_reports_unknown_node_type() -> None:
    result = validate_definition(make_definition("eeg/does-not/exist", filter_params={}))

    assert not result.valid
    assert any(
        issue.code == "NODE_SPEC_NOT_FOUND" and issue.node_id == "filter-1"
        for issue in result.errors
    )


def test_validate_definition_allows_filter_node() -> None:
    result = validate_definition(make_definition("eeg/filter/apply"))

    blocking = [
        issue
        for issue in result.errors
        if issue.code in {"PIPELINE_NODE_EXECUTOR_NOT_IMPLEMENTED", "NODE_SPEC_NOT_FOUND"}
    ]
    assert blocking == []


def test_validate_filter_node_notch_only_params() -> None:
    """陷波类型：只给 notch_freq，不给 l_freq/h_freq，也应通过（visible_when 让它们非必填）。"""
    result = validate_definition(
        make_definition(
            "eeg/filter/apply",
            filter_params={"filter_type": "notch", "notch_freq": 50.0, "notch_harmonics": 3},
        )
    )

    param_errors = [issue for issue in result.errors if issue.code == "PARAM_REQUIRED"]
    assert param_errors == []
