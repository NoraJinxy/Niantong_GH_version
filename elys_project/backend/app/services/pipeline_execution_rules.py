"""
Purpose: Centralize Pipeline status rules for creating Pipeline Executions.
Related: app/routers/pipelines.py, app/schemas/pipeline.py, docs_v2/5-20.
"""

from __future__ import annotations


ALLOWED_EXECUTION_MODES_BY_PIPELINE_STATUS: dict[str, set[str]] = {
    "active": {"analysis", "trial"},
    "draft": {"trial"},
}


def pipeline_execution_status_violation(pipeline_status: str | None, execution_mode: str) -> dict[str, str] | None:
    status = (pipeline_status or "unknown").lower()
    allowed_modes = ALLOWED_EXECUTION_MODES_BY_PIPELINE_STATUS.get(status)
    if allowed_modes is not None and execution_mode in allowed_modes:
        return None

    if status == "active":
        message = "active Pipeline only allows analysis or trial executions."
    elif status == "draft":
        message = "draft Pipeline only allows trial executions."
    elif status == "archived":
        message = "archived Pipeline cannot create new executions."
    else:
        message = f"Pipeline status {status} cannot create executions."

    return {
        "code": "PIPELINE_EXECUTION_STATUS_NOT_ALLOWED",
        "message": message,
        "pipeline_status": status,
        "execution_mode": execution_mode,
    }
