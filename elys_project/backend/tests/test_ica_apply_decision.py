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
