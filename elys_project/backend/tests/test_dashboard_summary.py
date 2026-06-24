"""
Purpose: Guard Dashboard summary API shape and summary-only sorting rules.
Related: app/services/dashboard_summary.py, app/schemas/dashboard.py, app/routers/dashboard.py.
"""

from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from app.schemas.dashboard import DashboardActiveExecution, DashboardActivityItem, DashboardSummaryResponse
from app.services.dashboard_summary import audit_action_label, audit_event_to_activity, dashboard_execution_sort_key, execution_stage_label


BACKEND_DIR = Path(__file__).resolve().parents[1]
MAIN_PY = BACKEND_DIR / "app" / "main.py"
DASHBOARD_ROUTER = BACKEND_DIR / "app" / "routers" / "dashboard.py"


def router_method_path(function: ast.FunctionDef, method: str) -> str | None:
    for decorator in function.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        if not isinstance(decorator.func, ast.Attribute):
            continue
        if decorator.func.attr != method:
            continue
        if not decorator.args or not isinstance(decorator.args[0], ast.Constant):
            continue
        return str(decorator.args[0].value)
    return None


def test_dashboard_summary_route_is_registered() -> None:
    router_tree = ast.parse(DASHBOARD_ROUTER.read_text(encoding="utf-8-sig"))
    functions = {node.name: node for node in router_tree.body if isinstance(node, ast.FunctionDef)}

    assert router_method_path(functions["get_dashboard_summary"], "get") == "/summary"
    assert "dashboard_router" in MAIN_PY.read_text(encoding="utf-8-sig")


def test_dashboard_summary_schema_excludes_default_view_technical_fields() -> None:
    assert "counts" in DashboardSummaryResponse.model_fields
    assert "states" in DashboardSummaryResponse.model_fields
    assert "recent_studies" in DashboardSummaryResponse.model_fields
    assert "active_executions" in DashboardSummaryResponse.model_fields
    assert "recent_activity" in DashboardSummaryResponse.model_fields
    assert {"object_kind", "object_name", "action_label", "created_at", "target_url"}.issubset(
        DashboardActivityItem.model_fields
    )

    technical_fields = {
        "payload_json",
        "metadata_json",
        "definition_snapshot",
        "manifest_json",
        "result_json",
        "error_json",
        "storage_path",
        "storage_uri",
        "source_path",
        "fif_path",
    }
    activity_legacy_fields = {"id", "event_id", "object_type", "time", "target_path"}
    assert technical_fields.isdisjoint(DashboardActiveExecution.model_fields)
    assert technical_fields.isdisjoint(DashboardActivityItem.model_fields)
    assert activity_legacy_fields.isdisjoint(DashboardActivityItem.model_fields)


def test_dashboard_execution_priority_orders_attention_before_background_work() -> None:
    base = datetime(2026, 5, 23, 8, 0, 0)
    executions = [
        SimpleNamespace(status="queued", started_at=base),
        SimpleNamespace(status="running", started_at=base),
        SimpleNamespace(status="failed", started_at=base),
        SimpleNamespace(status="waiting_user_input", started_at=base),
        SimpleNamespace(status="pending", started_at=base),
    ]

    ordered = sorted(executions, key=dashboard_execution_sort_key)

    assert [execution.status for execution in ordered] == [
        "waiting_user_input",
        "failed",
        "running",
        "queued",
        "pending",
    ]


def test_dashboard_summary_uses_business_language_for_execution_and_activity_labels() -> None:
    assert execution_stage_label("waiting_user_input") == "等待人工确认"
    assert execution_stage_label("failed") == "运行失败，请查看错误"
    # 活动文案全中文、无英文实体词；低价值的"更新/中间态"返回 None 被过滤
    assert audit_action_label("dataset.uploaded") == "导入完成"
    assert audit_action_label("pipeline.created") == "新建分析流程"
    assert audit_action_label("pipeline.execution.completed") == "分析完成，结果就绪"
    assert audit_action_label("pipeline.execution.failed") == "分析失败"
    assert audit_action_label("pipeline.updated") is None
    assert audit_action_label("dataset_asset.updated") is None


def test_dashboard_activity_maps_audit_event_without_payload_or_event_id() -> None:
    event = SimpleNamespace(
        resource_kind="pipeline_execution",
        action="pipeline.execution.failed",
        resource_label="Preprocess Pipeline v3",
        occurred_at=datetime(2026, 5, 23, 8, 10, 0),
        study_id="study-1",
        resource_id="run-18",
        metadata_json={"pipeline_id": 11, "error": "raw stack should stay hidden"},
    )

    item = audit_event_to_activity(event)

    assert item is not None
    assert item.object_kind == "execution"
    assert item.object_name == "Preprocess Pipeline v3"
    assert item.action_label == "分析失败"
    assert item.created_at == datetime(2026, 5, 23, 8, 10, 0)
    assert item.target_url == "/studies/study-1/pipeline?pipeline_id=11&execution_id=run-18"
    assert "metadata_json" not in DashboardActivityItem.model_fields
    assert "event_id" not in DashboardActivityItem.model_fields
