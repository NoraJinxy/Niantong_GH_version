"""
Purpose: Guard Pipeline Execution create route and shared implementation wiring.
Related: app/routers/pipelines.py, docs/5-30.
"""

from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.pipeline import (
    PipelineEditLockResponse,
    PipelineExecutionCreate,
    PipelineExecutionDetailResponse,
    PipelineExecutionLineageResponse,
    PipelineUpdate,
)
from app.services.study_locks import refresh_study_lock


BACKEND_DIR = Path(__file__).resolve().parents[1]
PIPELINES_ROUTER = BACKEND_DIR / "app" / "routers" / "pipelines.py"
PIPELINE_BACKGROUND = BACKEND_DIR / "app" / "pipeline" / "background.py"
FILE_TASKS = BACKEND_DIR / "app" / "tasks" / "file_tasks.py"


def load_router_tree() -> ast.Module:
    return ast.parse(PIPELINES_ROUTER.read_text(encoding="utf-8-sig"))


def load_router_source() -> str:
    return PIPELINES_ROUTER.read_text(encoding="utf-8-sig")


def load_background_source() -> str:
    return PIPELINE_BACKGROUND.read_text(encoding="utf-8-sig")


def load_file_tasks_source() -> str:
    return FILE_TASKS.read_text(encoding="utf-8-sig")


def router_post_path(function: ast.FunctionDef) -> str | None:
    return router_method_path(function, "post")


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


def calls_create_pipeline_execution(function: ast.FunctionDef) -> bool:
    for node in ast.walk(function):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "_create_pipeline_execution":
                return True
    return False


def router_function_source(function_name: str) -> str:
    tree = load_router_tree()
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    segment = ast.get_source_segment(load_router_source(), functions[function_name])
    assert segment is not None
    return segment


def test_pipeline_execution_create_route_uses_shared_implementation() -> None:
    tree = load_router_tree()
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}

    assert "_create_pipeline_execution" in functions
    assert router_post_path(functions["create_pipeline_execution"]) == "/studies/{study_id}/pipelines/{pipeline_id}/executions"
    assert calls_create_pipeline_execution(functions["create_pipeline_execution"])


def test_pipeline_update_requires_expected_version() -> None:
    assert PipelineUpdate.model_fields["expected_version"].is_required()

    with pytest.raises(ValidationError):
        PipelineUpdate(name="Renamed")

    payload = PipelineUpdate(name="Renamed", expected_version=3)
    assert payload.expected_version == 3
    assert payload.name == "Renamed"


def test_pipeline_update_version_conflict_check_is_unconditional() -> None:
    source = load_router_source()

    assert "payload.expected_version is not None" not in source
    assert "payload.expected_version != pipeline.version" in source
    assert "status.HTTP_409_CONFLICT" in source


def test_pipeline_edit_lock_routes_use_write_permission_and_standard_paths() -> None:
    tree = load_router_tree()
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}

    assert router_post_path(functions["acquire_pipeline_edit_lock"]) == (
        "/studies/{study_id}/pipelines/{pipeline_id}/edit-lock"
    )
    assert router_post_path(functions["refresh_pipeline_edit_lock"]) == (
        "/studies/{study_id}/pipelines/{pipeline_id}/edit-lock/refresh"
    )
    assert router_method_path(functions["release_pipeline_edit_lock"], "delete") == (
        "/studies/{study_id}/pipelines/{pipeline_id}/edit-lock"
    )

    for function_name in ("acquire_pipeline_edit_lock", "refresh_pipeline_edit_lock", "release_pipeline_edit_lock"):
        segment = ast.get_source_segment(load_router_source(), functions[function_name])
        assert segment is not None
        assert "get_study_for_write(study_id, db, current_user)" in segment


def test_pipeline_update_checks_other_user_edit_lock_before_version_save() -> None:
    source = load_router_source()
    lock_check_index = source.index("edit_lock = ensure_pipeline_edit_lock_available")
    version_check_index = source.index("payload.expected_version != pipeline.version")

    assert lock_check_index < version_check_index
    assert '"edit_lock_id": str(edit_lock.id)' in source
    assert '"code": "PIPELINE_EDIT_LOCKED"' in source
    assert "lock_type=\"edit\"" in source


def test_pipeline_edit_lock_response_schema_and_refresh_metadata() -> None:
    assert "expires_at" in PipelineEditLockResponse.model_fields
    assert "locked_by" in PipelineEditLockResponse.model_fields

    class FakeDb:
        flushed = False

        def flush(self) -> None:
            self.flushed = True

    db = FakeDb()
    lock = SimpleNamespace(
        expires_at=datetime(2026, 5, 21, 12, 0, 0),
        metadata_json={"reason": "pipeline_edit_acquire"},
    )

    refreshed = refresh_study_lock(
        db,
        lock,
        ttl_seconds=60,
        refreshed_by="user-1",
        reason="pipeline_edit_refresh",
    )

    assert db.flushed is True
    assert refreshed.expires_at > datetime(2026, 5, 21, 12, 0, 0)
    assert refreshed.metadata_json["reason"] == "pipeline_edit_acquire"
    assert refreshed.metadata_json["refresh_reason"] == "pipeline_edit_refresh"
    assert refreshed.metadata_json["refreshed_by"] == "user-1"


def test_pipeline_execution_cancel_route_uses_run_permission_and_standard_path() -> None:
    tree = load_router_tree()
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    segment = ast.get_source_segment(load_router_source(), functions["cancel_pipeline_execution"])

    assert router_post_path(functions["cancel_pipeline_execution"]) == "/studies/{study_id}/pipeline-executions/{execution_id}/cancel"
    assert segment is not None
    assert "get_study_for_run(study_id, db, current_user)" in segment
    assert "execution.status not in RUN_CANCELABLE_STATUSES" in segment
    assert "status.HTTP_409_CONFLICT" in segment


def test_pipeline_execution_cancel_updates_execution_task_lock_audit_and_manifest() -> None:
    source = load_router_source()

    assert 'RUN_CANCELABLE_STATUSES = {"queued", "running", "waiting_user_input"}' in source
    assert 'RUN_CANCELLED_STATUS = "canceled"' in source
    assert "best_effort_revoke_pipeline_task(async_task)" in source
    assert "run_pipeline_task.app.control.revoke" in source
    assert "release_pipeline_execution_locks_for_cancel" in source
    assert "release_study_lock_by_id" in source
    assert "release_study_locks_for_resource" in source
    assert "mark_pipeline_execution_canceled" in source
    assert "execution.status = RUN_CANCELLED_STATUS" in source
    assert 'record_task_event(\n            db,\n            async_task,\n            "execution_canceled"' in source
    assert "generate_execution_manifest(db, study=study, pipeline=pipeline, execution=execution)" in source
    assert 'action="pipeline.execution.canceled"' in source


def test_pipeline_execution_delete_route_uses_run_permission_and_standard_path() -> None:
    tree = load_router_tree()
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    segment = router_function_source("delete_pipeline_execution")

    assert router_method_path(functions["delete_pipeline_execution"], "delete") == "/studies/{study_id}/pipeline-executions/{execution_id}"
    assert "get_study_for_run(study_id, db, current_user)" in segment
    assert "execution.status not in RUN_DELETABLE_STATUSES" in segment
    assert "status.HTTP_409_CONFLICT" in segment
    assert "pipeline_execution_delete_conflict_detail(execution)" in segment


def test_pipeline_execution_delete_cancels_active_run_and_cleans_dependents() -> None:
    source = load_router_source()
    segment = router_function_source("delete_pipeline_execution")
    helper_segment = router_function_source("delete_pipeline_execution_rows")

    assert 'RUN_DELETABLE_STATUSES = RUN_CANCELABLE_STATUSES | {"failed", RUN_CANCELLED_STATUS}' in source
    assert "best_effort_revoke_pipeline_task(async_task)" in segment
    assert "reason=\"execution_deleted\"" in segment
    assert "mark_pipeline_execution_canceled(" in segment
    assert "delete_pipeline_execution_rows(db, execution=execution, async_tasks=async_tasks)" in segment
    assert 'action="pipeline.execution.deleted"' in segment
    assert "db.delete(execution)" in helper_segment
    assert "ExecutionOutput" in helper_segment
    assert "PipelineExecutionInput.upstream_execution_id == execution.id" in helper_segment
    assert "PipelineExecutionDependency.depends_on_execution_id == execution.id" in helper_segment
    assert "StudyOutput.produced_by_execution_id == execution.id" in helper_segment
    assert "StudyOutput.produced_by_job_id.in_(job_ids)" in helper_segment
    assert "DatasetFileDerivation.execution_id == execution.id" in helper_segment
    assert "TaskEvent.task_id.in_(task_ids)" in helper_segment
    assert "AsyncTask.id.in_(task_ids)" in helper_segment


def test_pipeline_execution_retry_route_uses_run_permission_and_standard_path() -> None:
    tree = load_router_tree()
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    segment = router_function_source("retry_pipeline_execution")

    assert router_post_path(functions["retry_pipeline_execution"]) == "/studies/{study_id}/pipeline-executions/{execution_id}/retry"
    assert "get_study_for_run(study_id, db, current_user)" in segment
    assert "source_execution.status not in RUN_RETRYABLE_STATUSES" in segment
    assert "pipeline_execution_retry_conflict_detail(source_execution)" in segment
    assert "PipelineExecutionRetryRequest" in segment


def test_pipeline_execution_retry_creates_new_execution_task_lineage_and_reuses_snapshot() -> None:
    source = load_router_source()
    segment = router_function_source("retry_pipeline_execution")

    assert 'RUN_RETRYABLE_STATUSES = {"failed", "canceled"}' in source
    assert 'trigger="retry"' in segment
    assert "definition_snapshot=definition_snapshot" in segment
    assert "clone_pipeline_execution_inputs(db, source_execution=source_execution, retry_execution=retry_execution)" in segment
    assert "attach_retry_input_snapshots_to_jobs(db, execution=retry_execution)" in segment
    assert 'dependency_kind="retry_of"' in segment
    assert '"retry_of_execution_id": str(source_execution.id)' in segment
    assert '"input_policy": payload.input_policy' in segment
    assert "AsyncTask(" in segment
    assert "run_pipeline_task.apply_async" in segment
    assert 'action="pipeline.execution.retry_queued"' in segment


def test_pipeline_execution_retry_can_re_resolve_and_reject_missing_reuse_snapshot() -> None:
    source = load_router_source()
    segment = router_function_source("retry_pipeline_execution")

    assert 'input_policy: Literal["reuse_snapshot", "re_resolve"] = "reuse_snapshot"' in (
        (BACKEND_DIR / "app" / "schemas" / "pipeline.py").read_text(encoding="utf-8-sig")
    )
    assert 'payload.input_policy == "reuse_snapshot"' in segment
    assert "definition_has_load_data(definition_snapshot)" in segment
    assert "retry_snapshot_missing_detail(source_execution)" in segment
    assert "PIPELINE_EXECUTION_INPUT_SNAPSHOT_MISSING" in source


def test_async_task_cancel_retry_routes_use_standard_paths_and_permissions() -> None:
    tree = load_router_tree()
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    cancel_segment = router_function_source("cancel_async_task")
    retry_segment = router_function_source("retry_async_task")

    assert router_post_path(functions["cancel_async_task"]) == "/studies/{study_id}/tasks/{task_id}/cancel"
    assert router_post_path(functions["retry_async_task"]) == "/studies/{study_id}/tasks/{task_id}/retry"
    assert "get_study_for_read(study_id, db, current_user)" in cancel_segment
    assert "require_study_run(study, db, current_user)" in cancel_segment
    assert "require_study_write(study, db, current_user)" in cancel_segment
    assert "require_study_run(study, db, current_user)" in retry_segment
    assert "require_study_write(study, db, current_user)" in retry_segment


def test_async_task_cancel_records_event_revoke_and_syncs_pipeline_execution() -> None:
    source = load_router_source()
    segment = router_function_source("cancel_async_task")

    assert 'TASK_CANCELABLE_STATUSES = {"queued", "running", "retrying"}' in source
    assert "best_effort_revoke_async_task(task)" in segment
    assert "best_effort_revoke_pipeline_task(task)" in segment
    assert 'record_task_event(\n        db,\n        task,\n        "canceled"' in segment
    assert "mark_pipeline_execution_canceled" in segment
    assert "release_pipeline_execution_locks_for_cancel" in segment
    assert "generate_execution_manifest(db, study=study, pipeline=pipeline, execution=execution)" in segment
    assert '"source": "task_cancel"' in segment
    assert 'action="async_task.canceled"' in segment


def test_async_task_retry_creates_file_task_and_dispatches_pipeline_execution_retry() -> None:
    source = load_router_source()
    segment = router_function_source("retry_async_task")

    assert 'TASK_RETRYABLE_STATUSES = {"failed", "canceled"}' in source
    assert 'FILE_TASK_TYPES = {"study_output_cleanup", "study_output_gc", "dataset_import", "canonical_fif_rebuild"}' in source
    # pipeline_execution 类的 retry 内部转发到 retry_pipeline_execution，不再向前端抛 409 redirect。
    assert "is_pipeline_execution_task(task)" in segment
    assert "retry_pipeline_execution(" in segment
    assert "async_task_id" in segment
    # 普通 file task 分支：建新 task 落 audit
    assert "task.task_type not in FILE_TASK_TYPES" in segment
    assert '"retry_of_task_id": str(task.id)' in segment
    assert "create_and_dispatch_file_task(" in segment
    assert 'action="async_task.retry_queued"' in segment


def test_async_task_events_stream_route_uses_sse_and_reconnect_cursor() -> None:
    tree = load_router_tree()
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    segment = router_function_source("stream_async_task_events")

    assert router_method_path(functions["stream_async_task_events"], "get") == (
        "/studies/{study_id}/tasks/{task_id}/events/stream"
    )
    assert "get_study_for_read(study_id, db, current_user)" in segment
    assert "get_async_task_or_404(db, study.id, task_id)" in segment
    assert "since: str | None = Query(default=None)" in segment
    assert 'Header(default=None, alias="Last-Event-ID")' in segment
    assert "cursor = since or last_event_id" in segment
    assert "StreamingResponse(" in segment
    assert 'media_type="text/event-stream"' in segment
    assert '"X-Accel-Buffering": "no"' in segment


def test_async_task_event_stream_generator_polls_sessionlocal_and_emits_sse_events() -> None:
    source = load_router_source()

    assert "import asyncio" in source
    assert "import json" in source
    assert "from app.database import SessionLocal, get_db" in source
    assert "async def task_event_stream_generator" in source
    assert "SessionLocal()" in source
    assert "query_task_events(db, task_id, since=cursor, limit=TASK_EVENT_STREAM_BATCH_LIMIT)" in source
    assert 'yield format_sse_event("task_event", task_event_stream_payload(event), event_id=cursor)' in source
    assert 'yield format_sse_event(\n                "heartbeat"' in source
    assert 'yield format_sse_event(\n        "stream_closed"' in source
    assert "await asyncio.sleep(poll_interval_seconds)" in source


def test_async_task_events_list_supports_since_without_replacing_compat_api() -> None:
    segment = router_function_source("list_async_task_events")
    source = load_router_source()

    assert "since: str | None = Query(default=None)" in segment
    assert "query_task_events(db, task.id, since=since)" in segment
    assert "def normalize_task_event_since" in source
    assert '"TASK_EVENT_CURSOR_INVALID"' in source
    assert "TaskEvent.created_at > since_at" in source


def test_pipeline_execution_lineage_route_uses_read_permission_and_separate_response() -> None:
    tree = load_router_tree()
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    segment = router_function_source("get_pipeline_execution_lineage")

    assert router_method_path(functions["get_pipeline_execution_lineage"], "get") == (
        "/studies/{study_id}/pipeline-executions/{execution_id}/lineage"
    )
    assert "get_study_for_read(study_id, db, current_user)" in segment
    assert "get_pipeline_execution_or_404(db, study.id, execution_id)" in segment
    assert "build_pipeline_execution_lineage_response(db, study=study, execution=execution)" in segment
    assert "response_model=PipelineExecutionLineageResponse" in load_router_source()


def test_pipeline_execution_lineage_response_schema_keeps_detail_response_unchanged() -> None:
    assert "upstream_executions" in PipelineExecutionLineageResponse.model_fields
    assert "downstream_executions" in PipelineExecutionLineageResponse.model_fields
    assert "upstream_dependencies" in PipelineExecutionLineageResponse.model_fields
    assert "downstream_dependencies" in PipelineExecutionLineageResponse.model_fields
    assert "graph_nodes" in PipelineExecutionLineageResponse.model_fields
    assert "graph_edges" in PipelineExecutionLineageResponse.model_fields

    assert "upstream_executions" not in PipelineExecutionDetailResponse.model_fields
    assert "downstream_executions" not in PipelineExecutionDetailResponse.model_fields
    assert "graph_nodes" not in PipelineExecutionDetailResponse.model_fields
    assert "graph_edges" not in PipelineExecutionDetailResponse.model_fields


def test_pipeline_execution_lineage_aggregates_inputs_artifacts_dependencies_and_graph() -> None:
    segment = router_function_source("build_pipeline_execution_lineage_response")

    assert "db.query(PipelineExecutionInput)" in segment
    assert "db.query(StudyOutput)" in segment
    assert "db.query(PipelineExecutionDependency)" in segment
    assert "PipelineExecutionDependency.depends_on_execution_id == execution.id" in segment
    assert "PipelineExecutionDependency.upstream_dataset_id.in_(study_output_ids)" in segment
    assert "upstream_execution_ids = unique_pipeline_execution_ids" in segment
    assert "downstream_execution_ids = unique_pipeline_execution_ids" in segment
    assert "upstream_executions = load_pipeline_executions_by_ids" in segment
    assert "downstream_executions = load_pipeline_executions_by_ids" in segment
    assert "add_lineage_graph_node" in segment
    assert "add_lineage_graph_edge" in segment
    assert "graph_nodes=list(graph_nodes.values())" in segment
    assert "graph_edges=list(graph_edges.values())" in segment


def test_study_output_retention_patch_shares_delete_blocker() -> None:
    helper_segment = router_function_source("apply_study_output_retention_action")

    assert "assert_artifact_can_be_deleted(db, artifact=dataset)" in helper_segment
    assert "ArtifactDependencyError" in helper_segment
    assert "status.HTTP_409_CONFLICT" in helper_segment


def test_study_output_restore_rejects_purged_rows_before_clearing_deleted_at() -> None:
    # GC 已物理清盘（purged_at 非空）的行磁盘文件已删，恢复必须 409，
    # 且守卫要排在清 deleted_at 之前，不能先恢复再报错。
    helper_segment = router_function_source("apply_study_output_retention_action")

    purged_guard_index = helper_segment.index("dataset.purged_at is not None")
    clear_deleted_index = helper_segment.index("dataset.deleted_at = None")
    assert purged_guard_index < clear_deleted_index
    assert '"code": "OUTPUT_PURGED"' in helper_segment


def test_study_output_unkeep_and_restore_refresh_retention_ttl() -> None:
    # keep=false / 回收站恢复后必须按用户动作口径重算 TTL，否则 NULL/已过期的
    # retention_expires_at 会让下一轮每日 cleanup 立即把行再次软删。
    helper_segment = router_function_source("apply_study_output_retention_action")

    assert helper_segment.count("retention_expiry_after_user_action(") == 2
    assert "restoring = deleted is False" in helper_segment
    assert "elif restoring and not dataset.keep:" in helper_segment


def test_study_output_batch_restore_pre_checks_purged_rows() -> None:
    # 批量恢复与批量删除同口径：先全量预检，任一被挡在改动任何数据之前整体 409。
    batch_segment = router_function_source("batch_update_study_outputs")

    assert "if upd.deleted is False:" in batch_segment
    assert '"code": "OUTPUT_BATCH_PURGED"' in batch_segment
    precheck_index = batch_segment.index("OUTPUT_BATCH_PURGED")
    apply_loop_index = batch_segment.index("apply_study_output_retention_action(")
    assert precheck_index < apply_loop_index


def test_file_task_worker_skips_pre_canceled_tasks() -> None:
    source = load_file_tasks_source()
    cancel_check_index = source.index('task.status == "canceled"')
    started_event_index = source.index('"started"')

    assert cancel_check_index < started_event_index


def test_pipeline_worker_skips_canceled_execution_before_execution() -> None:
    source = load_background_source()
    cancel_check_index = source.index('execution.status == "canceled"')
    context_query_index = source.index("study = db.query(Study)")

    assert cancel_check_index < context_query_index
    assert "return execution" in source[cancel_check_index:context_query_index]


def test_pipeline_execution_policy_schema_defaults_and_validation() -> None:
    payload = PipelineExecutionCreate()
    assert payload.trigger == "manual"

    payload = PipelineExecutionCreate(
        selection_override={
            "load-1": {
                "selection_mode": "explicit",
                "dataset_ids": ["11111111-1111-1111-1111-111111111111"],
            }
        }
    )
    assert payload.selection_override["load-1"].selection_mode == "explicit"
    assert payload.selection_override["load-1"].dataset_ids == ["11111111-1111-1111-1111-111111111111"]

    with pytest.raises(ValidationError):
        PipelineExecutionCreate(selection_override={"load-1": {"selection_mode": "current"}})


def test_pipeline_execution_policy_fields_are_persisted_and_tracked() -> None:
    source = load_router_source()

    assert "payload = payload or PipelineExecutionCreate()" in source
    assert "selection_override = normalize_selection_override" in source
    assert '"selection_override": selection_override' in source
