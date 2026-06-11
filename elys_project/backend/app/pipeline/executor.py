"""
Purpose: Implement workflow/Pipeline runtime support for executor, including validation, execution, artifacts, cache, or data resolution.
Related: app/routers/pipelines.py, app/tasks/pipeline_tasks.py, app/pipeline/nodes/*.json, docs_v2/5-00 and docs_v2/7-40.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID
import hashlib
import json

from sqlalchemy.orm import Session

from app.models import DatasetFile, PipelineDefinition, PipelineJob, PipelineExecution, PipelineExecutionInput, Study
from app.pipeline.study_output_store import StudyOutputStore
from app.pipeline.cache import PipelineCache
from app.pipeline.contracts import NodeExecutionContext, NodeInput, NodeOutput
from app.pipeline.dispatcher import NodeDispatcher, NodeExecutorNotImplemented
from app.pipeline.hash import input_hash, node_hash, params_hash, trace_code
from app.pipeline.load_data import resolve_load_data_selection
from app.pipeline.registry import NodeRegistry, get_node_registry
from app.pipeline.execution_manifest import generate_execution_manifest, should_generate_execution_manifest
from app.pipeline.topology import analyze_pipeline_topology
from app.pipeline.selection_override import (
    apply_selection_override_to_params,
    load_data_override_for_node,
    selection_override_from_execution,
)
from app.pipeline.validator import topological_node_order, validate_definition
from app.schemas.pipeline import PipelineValidationIssue
from app.services.execution_dependencies import record_execution_artifact_dependencies


class PipelineExecutor:
    def __init__(
        self,
        db: Session,
        dispatcher: NodeDispatcher | None = None,
        node_registry: NodeRegistry | None = None,
    ):
        self.db = db
        self.dispatcher = dispatcher or NodeDispatcher()
        self.node_registry = node_registry or get_node_registry()
        # 拓扑角色缓存：{node_id: "leaf" | "intermediate" | "source"}，
        # 每次 execute_prepared_execution 入口时根据 definition_json.graph 重新计算。
        self._topology: dict[str, str] = {}

    def prepare_execution(self, *, study: Study, pipeline: PipelineDefinition, execution: PipelineExecution) -> list[PipelineJob]:
        definition_json = self._definition_for_execution(pipeline=pipeline, execution=execution)
        ordered_nodes = topological_node_order(definition_json)
        jobs = self._get_or_create_jobs(
            study=study,
            pipeline=pipeline,
            execution=execution,
            definition_json=definition_json,
            nodes=ordered_nodes,
        )
        self._ensure_execution_input_snapshots(
            study=study,
            pipeline=pipeline,
            execution=execution,
            nodes=ordered_nodes,
            jobs=jobs,
        )
        return jobs

    def execute(self, *, study: Study, pipeline: PipelineDefinition, execution: PipelineExecution, commit_progress: bool = False) -> None:
        self.prepare_execution(study=study, pipeline=pipeline, execution=execution)
        self.execute_prepared_execution(study=study, pipeline=pipeline, execution=execution, commit_progress=commit_progress)

    def execute_prepared_execution(
        self,
        *,
        study: Study,
        pipeline: PipelineDefinition,
        execution: PipelineExecution,
        commit_progress: bool = False,
        start_topo_index: int = 0,
    ) -> None:
        definition_json = self._definition_for_execution(pipeline=pipeline, execution=execution)
        validation = validate_definition(definition_json, db=self.db, study=study)
        ordered_nodes = topological_node_order(definition_json)
        # 计算节点拓扑角色（leaf / intermediate / source），供 dispatcher 决定默认 retention
        self._topology = analyze_pipeline_topology(
            definition_json.get("graph") if isinstance(definition_json, dict) else None
        )
        jobs = self._get_or_create_jobs(
            study=study,
            pipeline=pipeline,
            execution=execution,
            definition_json=definition_json,
            nodes=ordered_nodes,
        )
        errors = [issue.model_dump(mode="json") for issue in validation.errors]
        warnings = [issue.model_dump(mode="json") for issue in validation.warnings]
        node_results: list[dict[str, Any]] = []
        data_infos_by_node: dict[str, list[dict[str, Any]]] = {}
        outputs_by_node: dict[str, NodeOutput] = {}
        base_result_json = execution.result_json or {}
        execution_mode = base_result_json.get("mode", "sync")
        waiting_for_user = False

        execution.status = "running"
        execution.finished_at = None
        execution.result_json = {
            **base_result_json,
            "mode": execution_mode,
            "executor": "PipelineExecutor",
            "message": "Pipeline execution is running.",
            "node_results": [],
            "data_infos_by_node": {},
            "warnings": warnings,
        }
        execution.error_json = {"errors": errors} if errors else {}
        self._commit_progress(commit_progress)

        if validation.valid:
            for node, job in zip(ordered_nodes, jobs):
                if int(job.topo_index or 0) < int(start_topo_index or 0):
                    output = self._output_from_job(job, node)
                    if output is not None:
                        outputs_by_node[str(node.get("id") or "")] = output
                        if output.data_infos:
                            data_infos_by_node[str(node.get("id") or "")] = output.data_infos
                    node_results.append(
                        self._node_result(
                            node=node,
                            status=job.status,
                            dataset_count=len(output.data_infos) if output is not None else 0,
                            output_ports=list(output.outputs.keys()) if output is not None else [],
                            errors=self._errors_from_json(job.error_json),
                            warnings=[],
                        )
                    )
                    continue

                inputs = self._resolve_node_inputs(definition_json, node, outputs_by_node)
                record_execution_artifact_dependencies(
                    self.db,
                    study=study,
                    pipeline=pipeline,
                    execution=execution,
                    job=job,
                    node=node,
                    inputs=inputs,
                )
                result = self._execute_node(
                    study=study,
                    pipeline=pipeline,
                    execution=execution,
                    node=node,
                    job=job,
                    inputs=inputs,
                    commit_progress=commit_progress,
                )
                node_results.append(result["node_result"])
                errors.extend(result["errors"])
                warnings.extend(result["warnings"])
                if result["data_infos"]:
                    data_infos_by_node[str(node.get("id") or "")] = result["data_infos"]
                if result["output"] is not None:
                    outputs_by_node[str(node.get("id") or "")] = result["output"]
                if result["status"] == "waiting_user_input":
                    waiting_for_user = True
                    break
        else:
            for node, job in zip(ordered_nodes, jobs):
                node_errors = self._issues_for_node(errors, str(node.get("id") or ""))
                result_errors = node_errors or errors
                self._finish_job(
                    job,
                    status="failed",
                    error_json={"errors": result_errors} if result_errors else {},
                    output_json={},
                )
                self._commit_progress(commit_progress)
                node_results.append(
                    self._node_result(
                        node=node,
                        status="failed",
                        dataset_count=0,
                        output_ports=[],
                        errors=result_errors,
                        warnings=[],
                    )
                )

        dataset_count = sum(len(items) for items in data_infos_by_node.values())
        if errors:
            execution.status = "failed"
        elif waiting_for_user:
            execution.status = "waiting_user_input"
        else:
            execution.status = "completed"
        execution.dataset_count = dataset_count
        base_result_json = execution.result_json or {}
        execution.result_json = {
            **base_result_json,
            "mode": execution_mode,
            "executor": "PipelineExecutor",
            "message": (
                "Pipeline execution completed."
                if execution.status == "completed"
                else "Pipeline execution is waiting for user input."
                if execution.status == "waiting_user_input"
                else "Pipeline execution failed. See node_results and error_json for details."
            ),
            "node_results": node_results,
            "data_infos_by_node": data_infos_by_node,
            "warnings": warnings,
        }
        execution.error_json = {"errors": errors} if errors else {}
        execution.finished_at = None if execution.status == "waiting_user_input" else datetime.utcnow()
        if should_generate_execution_manifest(execution):
            generate_execution_manifest(self.db, study=study, pipeline=pipeline, execution=execution)
        self._commit_progress(commit_progress)

    def _get_or_create_jobs(
        self,
        *,
        study: Study,
        pipeline: PipelineDefinition,
        execution: PipelineExecution,
        definition_json: dict[str, Any],
        nodes: list[dict[str, Any]],
    ) -> list[PipelineJob]:
        existing = (
            self.db.query(PipelineJob)
            .filter(PipelineJob.execution_id == execution.id)
            .order_by(PipelineJob.topo_index.asc(), PipelineJob.node_id.asc())
            .all()
        )
        if existing:
            execution.node_count = len(existing)
            return existing
        return self._create_jobs(
            study=study,
            pipeline=pipeline,
            execution=execution,
            definition_json=definition_json,
            nodes=nodes,
        )

    def _create_jobs(
        self,
        *,
        study: Study,
        pipeline: PipelineDefinition,
        execution: PipelineExecution,
        definition_json: dict[str, Any],
        nodes: list[dict[str, Any]],
    ) -> list[PipelineJob]:
        jobs: list[PipelineJob] = []
        for index, node in enumerate(nodes):
            node_id = str(node.get("id") or "")
            node_type = str(node.get("type") or "")
            params = node.get("params") if isinstance(node.get("params"), dict) else {}
            job = PipelineJob(
                execution_id=execution.id,
                study_id=study.id,
                pipeline_id=pipeline.id,
                node_id=node_id,
                node_type=node_type,
                node_title=node.get("title") or node_type,
                status="pending",
                topo_index=index,
                params_json=params,
                input_json=self._node_input_json(definition_json, node_id),
                output_json={},
                error_json={},
            )
            self.db.add(job)
            jobs.append(job)
        self.db.flush()
        execution.node_count = len(jobs)
        return jobs

    def _ensure_execution_input_snapshots(
        self,
        *,
        study: Study,
        pipeline: PipelineDefinition,
        execution: PipelineExecution,
        nodes: list[dict[str, Any]],
        jobs: list[PipelineJob],
    ) -> None:
        existing = self.db.query(PipelineExecutionInput.id).filter(PipelineExecutionInput.execution_id == execution.id).first()
        if existing:
            return

        selection_override = selection_override_from_execution(execution)
        total_dataset_inputs = 0
        for node, job in zip(nodes, jobs):
            node_type = str(node.get("type") or "")
            if node_type != "eeg/data/load":
                continue

            node_id = str(node.get("id") or job.node_id or "")
            base_params = self._params_for_job(node, job)
            node_override = load_data_override_for_node(selection_override, node_id)
            params = apply_selection_override_to_params(base_params, node_override)
            if node_override:
                job.params_json = params
            resolved = resolve_load_data_selection(
                db=self.db,
                study=study,
                params=params,
                node_id=node_id,
                node_type=node_type,
            )
            selector_json = {
                "node_id": node_id,
                "node_type": node_type,
                "params": params,
                "base_params": base_params,
                "selection_override": node_override,
                "override_applied": bool(node_override),
                "selection_mode": resolved.selection_mode,
                "dataset_filter": params.get("dataset_filter") if isinstance(params.get("dataset_filter"), dict) else {},
                "dataset_ids": params.get("dataset_ids") if isinstance(params.get("dataset_ids"), list) else [],
            }
            selector_metadata = {
                "valid": resolved.valid,
                "selection_mode": resolved.selection_mode,
                "dataset_count": resolved.dataset_count,
                "resolved_filter": resolved.resolved_filter,
                "missing_dataset_ids": resolved.missing_dataset_ids,
                "errors": [issue.model_dump(mode="json") for issue in resolved.errors],
                "warnings": [issue.model_dump(mode="json") for issue in resolved.warnings],
                "resolved_at": datetime.utcnow().isoformat() + "Z",
            }
            self.db.add(
                PipelineExecutionInput(
                    execution_id=execution.id,
                    study_id=study.id,
                    pipeline_id=pipeline.id,
                    job_id=job.id,
                    node_id=node_id,
                    node_type=node_type,
                    input_slot=f"{node_id}:selector",
                    input_index=0,
                    input_kind="selector",
                    selector_json=selector_json,
                    resolved_metadata_json=selector_metadata,
                    sha256=self._snapshot_hash({"selector": selector_json, "resolved": selector_metadata}),
                )
            )

            for index, item in enumerate(resolved.data_infos, start=1):
                data_info = item.model_dump(mode="json")
                dataset_file = self._dataset_file_for_data_info(study=study, data_info=data_info)
                resolved_metadata = dict(data_info)
                if data_info.get("mount_id") or data_info.get("mount_name"):
                    resolved_metadata["mount"] = {
                        "mount_id": data_info.get("mount_id"),
                        "mount_name": data_info.get("mount_name"),
                        "dataset_asset_id": data_info.get("dataset_asset_id"),
                    }
                resolved_metadata["input_snapshot"] = {
                    "node_id": node_id,
                    "node_type": node_type,
                    "input_index": index,
                    "frozen_at": datetime.utcnow().isoformat() + "Z",
                }
                if dataset_file:
                    resolved_metadata["dataset_file"] = {
                        "id": str(dataset_file.id),
                        "file_role": dataset_file.file_role,
                        "storage_uri": dataset_file.storage_uri,
                        "relative_path": dataset_file.relative_path,
                        "logical_path": dataset_file.logical_path,
                        "sha256": dataset_file.sha256,
                    }
                file_role = data_info.get("file_role") or (dataset_file.file_role if dataset_file else None)
                storage_uri = data_info.get("storage_uri") or (dataset_file.storage_uri if dataset_file else None)
                logical_path = data_info.get("logical_path") or (dataset_file.logical_path if dataset_file else None)
                file_sha256 = (
                    data_info.get("sha256")
                    or (dataset_file.sha256 if dataset_file else None)
                    or data_info.get("checksum")
                    or data_info.get("content_hash")
                )
                resolved_metadata["file_snapshot"] = {
                    "dataset_file_id": str(dataset_file.id) if dataset_file else data_info.get("dataset_file_id"),
                    "file_role": file_role,
                    "storage_uri": storage_uri,
                    "logical_path": logical_path,
                    "sha256": file_sha256,
                }
                self.db.add(
                    PipelineExecutionInput(
                        execution_id=execution.id,
                        study_id=study.id,
                        pipeline_id=pipeline.id,
                        job_id=job.id,
                        node_id=node_id,
                        node_type=node_type,
                        input_slot=f"{node_id}:output",
                        input_index=index,
                        input_kind="dataset_file" if dataset_file else "dataset",
                        dataset_asset_id=self._uuid_or_none(data_info.get("dataset_asset_id")),
                        recording_id=self._uuid_or_none(data_info.get("dataset_id")),
                        recording_version_id=self._uuid_or_none(data_info.get("current_upload_id")),
                        dataset_file_id=dataset_file.id if dataset_file else None,
                        file_role=file_role,
                        storage_uri=storage_uri,
                        logical_path=logical_path,
                        selector_json=selector_json,
                        resolved_metadata_json=resolved_metadata,
                        sha256=file_sha256,
                    )
                )
                total_dataset_inputs += 1

        if total_dataset_inputs:
            execution.dataset_count = total_dataset_inputs
        self.db.flush()

    def _dataset_file_for_data_info(self, *, study: Study, data_info: dict[str, Any]) -> DatasetFile | None:
        dataset_file_id = self._uuid_or_none(data_info.get("dataset_file_id"))
        if dataset_file_id:
            found = (
                self.db.query(DatasetFile)
                .filter(DatasetFile.id == dataset_file_id)
                .first()
            )
            if found:
                return found

        dataset_id = self._uuid_or_none(data_info.get("dataset_id"))
        dataset_upload_id = self._uuid_or_none(data_info.get("current_upload_id"))
        storage_uri = data_info.get("storage_uri")
        file_role = data_info.get("file_role") or "fif"
        if storage_uri:
            query = self.db.query(DatasetFile).filter(
                DatasetFile.file_role == file_role,
                DatasetFile.storage_uri == str(storage_uri),
            )
            if dataset_id:
                query = query.filter(DatasetFile.recording_id == dataset_id)
            if dataset_upload_id:
                query = query.filter(DatasetFile.recording_version_id == dataset_upload_id)
            found = query.order_by(DatasetFile.created_at.desc(), DatasetFile.id.desc()).first()
            if found:
                return found

        logical_path = data_info.get("logical_path")
        if logical_path:
            query = self.db.query(DatasetFile).filter(
                DatasetFile.file_role == file_role,
                DatasetFile.logical_path == self._normalize_relative_path(str(logical_path)),
            )
            if dataset_id:
                query = query.filter(DatasetFile.recording_id == dataset_id)
            if dataset_upload_id:
                query = query.filter(DatasetFile.recording_version_id == dataset_upload_id)
            found = query.order_by(DatasetFile.created_at.desc(), DatasetFile.id.desc()).first()
            if found:
                return found

        candidates = [
            ("fif", data_info.get("fif_path")),
            ("original_upload", data_info.get("source_path")),
        ]
        for file_role, relative_path in candidates:
            if not relative_path:
                continue
            query = self.db.query(DatasetFile).filter(
                DatasetFile.file_role == file_role,
                DatasetFile.relative_path == self._normalize_relative_path(str(relative_path)),
            )
            if dataset_id:
                query = query.filter(DatasetFile.recording_id == dataset_id)
            if dataset_upload_id:
                query = query.filter(DatasetFile.recording_version_id == dataset_upload_id)
            found = query.order_by(DatasetFile.created_at.desc(), DatasetFile.id.desc()).first()
            if found:
                return found
        return None

    @staticmethod
    def _uuid_or_none(value: Any) -> UUID | None:
        if not value:
            return None
        try:
            return UUID(str(value))
        except ValueError:
            return None

    @staticmethod
    def _normalize_relative_path(value: str) -> str:
        return value.replace("\\", "/")

    @staticmethod
    def _snapshot_hash(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _execute_node(
        self,
        *,
        study: Study,
        pipeline: PipelineDefinition,
        execution: PipelineExecution,
        node: dict[str, Any],
        job: PipelineJob,
        inputs: dict[str, NodeInput],
        commit_progress: bool = False,
    ) -> dict[str, Any]:
        started_at = datetime.utcnow()
        node_id = str(node.get("id") or "")
        node_type = str(node.get("type") or "")
        params = self._params_for_job(node, job)
        node_spec = self.node_registry.get(node_type) or {}
        params_digest = params_hash(params, node_spec)
        input_digest = input_hash(inputs)
        node_digest = node_hash(
            node_type=node_type,
            params_digest=params_digest,
            input_digest=input_digest,
            node_spec=node_spec,
        )
        job.status = "running"
        job.started_at = started_at
        job.input_json = self._node_input_runtime_json(job.input_json or {}, inputs)
        job.params_json = params
        job.params_hash = params_digest
        job.input_hash = input_digest
        job.node_hash = node_digest
        job.trace_code = trace_code(node_type=node_type, node_digest=node_digest)
        self._commit_progress(commit_progress)

        cache_result = self._restore_cached_node_output(
            study=study,
            execution=execution,
            node=node,
            job=job,
            node_spec=node_spec,
            node_digest=node_digest,
        )
        if cache_result is not None:
            output_json = cache_result.output.to_output_json()
            self._finish_job(
                job,
                status="cached",
                error_json={},
                output_json=output_json,
            )
            job.log_tail = f"Cache hit from job {cache_result.source_job_id}"
            self._commit_progress(commit_progress)
            return {
                "node_result": self._node_result(
                    node=node,
                    status="cached",
                    dataset_count=cache_result.dataset_count,
                    output_ports=cache_result.output_ports,
                    errors=[],
                    warnings=[],
                ),
                "errors": [],
                "warnings": [],
                "data_infos": cache_result.output.data_infos,
                "output": cache_result.output,
                "status": "cached",
            }

        context = NodeExecutionContext(
            db=self.db,
            study=study,
            pipeline=pipeline,
            execution=execution,
            job=job,
            node=node,
            params=params,
            inputs=inputs,
            study_output_store=StudyOutputStore(self.db, study, execution, job),
            node_spec=node_spec or {},
            topology=dict(self._topology),
        )
        try:
            dispatch_result = self.dispatcher.dispatch(context)
        except NodeExecutorNotImplemented as exc:
            node_error = exc.to_issue()
            self._finish_job(job, status="failed", error_json={"errors": [node_error]}, output_json={})
            self._commit_progress(commit_progress)
            return {
                "node_result": self._node_result(
                    node=node,
                    status="failed",
                    dataset_count=0,
                    output_ports=[],
                    errors=[node_error],
                    warnings=[],
                ),
                "errors": [node_error],
                "warnings": [],
                "data_infos": [],
                "output": None,
                "status": "failed",
            }
        except Exception as exc:
            node_error = PipelineValidationIssue(
                code="PIPELINE_NODE_EXECUTION_ERROR",
                message=str(exc),
                node_id=str(node.get("id") or ""),
                node_type=str(node.get("type") or ""),
            ).model_dump(mode="json")
            self._finish_job(job, status="failed", error_json={"errors": [node_error]}, output_json={})
            self._commit_progress(commit_progress)
            return {
                "node_result": self._node_result(
                    node=node,
                    status="failed",
                    dataset_count=0,
                    output_ports=[],
                    errors=[node_error],
                    warnings=[],
                ),
                "errors": [node_error],
                "warnings": [],
                "data_infos": [],
                "output": None,
                "status": "failed",
            }

        output_json = dispatch_result.output.to_output_json()
        if dispatch_result.status == "waiting_user_input":
            interaction = output_json.get("metadata", {}).get("interaction") if isinstance(output_json.get("metadata"), dict) else None
            if isinstance(interaction, dict):
                output_json["interaction"] = interaction
        self._finish_job(
            job,
            status=dispatch_result.status,
            error_json={"errors": dispatch_result.errors} if dispatch_result.errors else {},
            output_json=output_json,
        )
        self._commit_progress(commit_progress)
        return {
            "node_result": self._node_result(
                node=node,
                status=(
                    "completed"
                    if dispatch_result.status == "success"
                    else "waiting_user_input"
                    if dispatch_result.status == "waiting_user_input"
                    else "failed"
                ),
                dataset_count=dispatch_result.dataset_count,
                output_ports=dispatch_result.output_ports,
                errors=dispatch_result.errors,
                warnings=dispatch_result.warnings,
            ),
            "errors": dispatch_result.errors,
            "warnings": dispatch_result.warnings,
            "data_infos": dispatch_result.output.data_infos,
            "output": dispatch_result.output,
            "status": dispatch_result.status,
        }

    def _restore_cached_node_output(
        self,
        *,
        study: Study,
        execution: PipelineExecution,
        node: dict[str, Any],
        job: PipelineJob,
        node_spec: dict[str, Any],
        node_digest: str,
    ):
        from app.pipeline.cache_policy import is_cache_eligible

        if not is_cache_eligible(node_spec):
            return None
        return PipelineCache(
            self.db, study, execution, job, topology=dict(self._topology)
        ).restore_node_output(
            node_hash=node_digest,
            node=node,
        )

    def _finish_job(
        self,
        job: PipelineJob,
        *,
        status: str,
        error_json: dict[str, Any],
        output_json: dict[str, Any],
    ) -> None:
        finished_at = datetime.utcnow()
        job.status = status
        job.finished_at = finished_at
        job.output_json = output_json
        job.error_json = error_json
        if job.started_at:
            job.duration_ms = max(0, int((finished_at - job.started_at).total_seconds() * 1000))

    @staticmethod
    def _params_for_job(node: dict[str, Any], job: PipelineJob) -> dict[str, Any]:
        params = dict(node.get("params") if isinstance(node.get("params"), dict) else {})
        if str(node.get("type") or "") != "eeg/ica/apply":
            return params

        output_json = job.output_json or {}
        interaction = {}
        if isinstance(output_json, dict):
            if isinstance(output_json.get("interaction"), dict):
                interaction = output_json["interaction"]
            elif isinstance(output_json.get("metadata"), dict) and isinstance(output_json["metadata"].get("interaction"), dict):
                interaction = output_json["metadata"]["interaction"]
        decision = interaction.get("decision") if isinstance(interaction, dict) else None
        if isinstance(decision, dict):
            params["excluded_components"] = decision.get("excluded_components", [])
            params["decision_version"] = decision.get("decision_version", params.get("decision_version", 1))
            params["interaction_decision"] = {
                "excluded_components": params["excluded_components"],
                "decision_version": params["decision_version"],
            }
        return params

    def _commit_progress(self, enabled: bool) -> None:
        if enabled:
            self.db.commit()
        else:
            self.db.flush()

    @staticmethod
    def _definition_for_execution(*, pipeline: PipelineDefinition, execution: PipelineExecution) -> dict[str, Any]:
        snapshot = execution.definition_snapshot if isinstance(execution.definition_snapshot, dict) else None
        if snapshot:
            return snapshot
        return pipeline.definition_json if isinstance(pipeline.definition_json, dict) else {}

    @staticmethod
    def _node_result(
        *,
        node: dict[str, Any],
        status: str,
        dataset_count: int,
        output_ports: list[str],
        errors: list[dict[str, Any]],
        warnings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        node_type = str(node.get("type") or "")
        return {
            "node_id": str(node.get("id") or ""),
            "node_type": node_type,
            "title": node.get("title") or node_type,
            "status": status,
            "dataset_count": dataset_count,
            "output_ports": output_ports,
            "warnings": warnings,
            "errors": errors,
        }

    @staticmethod
    def _node_input_json(definition_json: dict[str, Any], node_id: str) -> dict[str, Any]:
        graph = definition_json.get("graph") if isinstance(definition_json, dict) else {}
        links = graph.get("links", []) if isinstance(graph, dict) else []
        incoming_links = []
        if isinstance(links, list):
            for link in links:
                if not isinstance(link, dict):
                    continue
                target = link.get("to") or {}
                if target.get("node") == node_id:
                    incoming_links.append(link)
        return {"incoming_links": incoming_links}

    @staticmethod
    def _node_input_runtime_json(base_input_json: dict[str, Any], inputs: dict[str, NodeInput]) -> dict[str, Any]:
        runtime = {
            port: {
                "dataset_count": len(node_input.data_infos),
                "artifact_count": len(node_input.artifacts),
            }
            for port, node_input in inputs.items()
        }
        merged = dict(base_input_json)
        merged["inputs"] = runtime
        return merged

    @staticmethod
    def _resolve_node_inputs(
        definition_json: dict[str, Any],
        node: dict[str, Any],
        outputs_by_node: dict[str, NodeOutput],
    ) -> dict[str, NodeInput]:
        node_id = str(node.get("id") or "")
        graph = definition_json.get("graph") if isinstance(definition_json, dict) else {}
        links = graph.get("links", []) if isinstance(graph, dict) else []
        inputs: dict[str, NodeInput] = {}
        if not isinstance(links, list):
            return inputs

        for link in links:
            if not isinstance(link, dict):
                continue
            target = link.get("to") or {}
            if target.get("node") != node_id:
                continue
            source = link.get("from") or {}
            source_node_id = str(source.get("node") or "")
            source_port = str(source.get("port") or "output")
            target_port = str(target.get("port") or "input")
            source_output = outputs_by_node.get(source_node_id)
            if source_output is None:
                inputs.setdefault(target_port, NodeInput(port=target_port))
                continue

            port_value = source_output.outputs.get(source_port)
            data_infos = PipelineExecutor._extract_data_infos(port_value)
            if not data_infos and source_output.data_infos:
                data_infos = list(source_output.data_infos)
            node_input = inputs.setdefault(target_port, NodeInput(port=target_port))
            node_input.data_infos.extend(data_infos)
            node_input.artifacts.extend(source_output.artifacts)
            node_input.metadata.setdefault("source_nodes", []).append(source_node_id)

        return inputs

    @staticmethod
    def _extract_data_infos(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            return [value]
        return []

    @staticmethod
    def _issues_for_node(issues: list[dict[str, Any]], node_id: str) -> list[dict[str, Any]]:
        return [issue for issue in issues if issue.get("node_id") == node_id]

    @staticmethod
    def _output_from_job(job: PipelineJob, node: dict[str, Any]) -> NodeOutput | None:
        output_json = job.output_json or {}
        if not isinstance(output_json, dict) or not output_json:
            return None
        return NodeOutput(
            node_id=str(output_json.get("node_id") or node.get("id") or job.node_id),
            node_type=str(output_json.get("node_type") or node.get("type") or job.node_type),
            outputs=output_json.get("outputs") if isinstance(output_json.get("outputs"), dict) else {},
            data_infos=output_json.get("data_infos") if isinstance(output_json.get("data_infos"), list) else [],
            artifacts=output_json.get("artifacts") if isinstance(output_json.get("artifacts"), list) else [],
            metadata=output_json.get("metadata") if isinstance(output_json.get("metadata"), dict) else {},
        )

    @staticmethod
    def _errors_from_json(error_json: Any) -> list[dict[str, Any]]:
        if isinstance(error_json, dict) and isinstance(error_json.get("errors"), list):
            return [item for item in error_json["errors"] if isinstance(item, dict)]
        return []
