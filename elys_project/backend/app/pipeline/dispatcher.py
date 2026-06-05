"""
Purpose: Implement workflow/Pipeline runtime support for dispatcher, including validation, execution, artifacts, cache, or data resolution.
Related: app/routers/pipelines.py, app/tasks/pipeline_tasks.py, app/pipeline/nodes/*.json, docs_v2/5-00 and docs_v2/7-40.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.engine.analysis.epoching import run_epoch_segment
from app.engine.analysis.erp import _normalize_event_labels, run_erp_average
from app.engine.io import (
    read_epochs_from_data_info,
    read_ica_from_data_info,
    read_raw_from_data_info,
    save_epochs_fif,
    save_evoked_fif,
    save_ica_fif,
    save_raw_fif,
    summarize_epochs,
    summarize_evoked,
    summarize_raw,
)
from app.engine.ica.apply import parse_excluded_components, run_apply_ica
from app.engine.ica.compute import run_compute_ica, summarize_ica
from app.engine.preprocess.filters import run_butterworth_filter, run_fir_filter, run_notch_filter
from app.engine.preprocess.reference import run_rereference
from app.engine.preprocess.resample import run_resample
from app.models import PipelineExecutionInput
from app.pipeline.derived_dataset_store import DerivedDatasetStore
from app.pipeline.contracts import NodeExecutionContext, NodeOutput
from app.pipeline.load_data import resolve_load_data_selection
from app.pipeline.save_settings import apply_save_settings
from app.schemas.pipeline import PipelineValidationIssue
from app.services.storage import StorageService, StorageUriError


@dataclass
class NodeDispatchResult:
    output: NodeOutput
    status: str
    dataset_count: int = 0
    output_ports: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)


class NodeExecutorNotImplemented(Exception):
    def __init__(self, node_id: str, node_type: str, title: str):
        self.node_id = node_id
        self.node_type = node_type
        self.title = title
        super().__init__(f"Node executor is not implemented: {title} ({node_type})")

    def to_issue(self) -> dict[str, Any]:
        return PipelineValidationIssue(
            code="PIPELINE_NODE_EXECUTOR_NOT_IMPLEMENTED",
            message=str(self),
            node_id=self.node_id,
            node_type=self.node_type,
        ).model_dump(mode="json")


class NodeDispatcher:
    def __init__(self):
        self._handlers: dict[str, Callable[[NodeExecutionContext], NodeDispatchResult]] = {
            "eeg/data/load": self._execute_load_data,
            "eeg/filter/fir": self._execute_fir_filter,
            "eeg/filter/butterworth": self._execute_butterworth_filter,
            "eeg/filter/notch": self._execute_notch_filter,
            "eeg/preproc/resample": self._execute_resample,
            "eeg/preproc/rereference": self._execute_rereference,
            "eeg/ica/compute": self._execute_ica_compute,
            "eeg/ica/apply": self._execute_ica_apply,
            "eeg/epoch/segment": self._execute_epoch_segment,
            "eeg/analysis/erp": self._execute_erp_average,
        }

    def supported_node_types(self) -> set[str]:
        return set(self._handlers)

    def supports(self, node_type: str) -> bool:
        return node_type in self._handlers

    def dispatch(self, context: NodeExecutionContext) -> NodeDispatchResult:
        node_type = str(context.node.get("type") or "")
        handler = self._handlers.get(node_type)
        if handler is None:
            raise NodeExecutorNotImplemented(
                node_id=str(context.node.get("id") or ""),
                node_type=node_type,
                title=str(context.node.get("title") or node_type),
            )
        return handler(context)

    def _execute_load_data(self, context: NodeExecutionContext) -> NodeDispatchResult:
        snapshot_result = self._execute_load_data_from_snapshot(context)
        if snapshot_result is not None:
            return snapshot_result

        node_id = str(context.node.get("id") or "")
        node_type = str(context.node.get("type") or "eeg/data/load")
        resolved = resolve_load_data_selection(
            db=context.db,
            study=context.study,
            params=context.params,
            node_id=node_id,
            node_type=node_type,
        )
        data_infos = [item.model_dump(mode="json") for item in resolved.data_infos]
        errors = [issue.model_dump(mode="json") for issue in resolved.errors]
        warnings = [issue.model_dump(mode="json") for issue in resolved.warnings]
        output = NodeOutput(
            node_id=node_id,
            node_type=node_type,
            outputs={"output": data_infos},
            data_infos=data_infos,
            metadata={
                "dataset_count": resolved.dataset_count,
                "selection_mode": resolved.selection_mode,
                "missing_dataset_ids": resolved.missing_dataset_ids,
            },
        )
        return NodeDispatchResult(
            output=output,
            status="success" if resolved.valid else "failed",
            dataset_count=resolved.dataset_count,
            output_ports=["output"],
            errors=errors,
            warnings=warnings,
        )

    def _execute_load_data_from_snapshot(self, context: NodeExecutionContext) -> NodeDispatchResult | None:
        node_id = str(context.node.get("id") or "")
        node_type = str(context.node.get("type") or "eeg/data/load")
        selector = (
            context.db.query(PipelineExecutionInput)
            .filter(
                PipelineExecutionInput.execution_id == context.execution.id,
                PipelineExecutionInput.node_id == node_id,
                PipelineExecutionInput.input_kind == "selector",
            )
            .order_by(PipelineExecutionInput.input_index.asc(), PipelineExecutionInput.created_at.asc())
            .first()
        )
        if selector is None:
            return None

        input_rows = (
            context.db.query(PipelineExecutionInput)
            .filter(
                PipelineExecutionInput.execution_id == context.execution.id,
                PipelineExecutionInput.node_id == node_id,
                PipelineExecutionInput.input_kind.in_(["dataset_file", "dataset"]),
            )
            .order_by(PipelineExecutionInput.input_index.asc(), PipelineExecutionInput.created_at.asc(), PipelineExecutionInput.id.asc())
            .all()
        )
        selector_metadata = selector.resolved_metadata_json if isinstance(selector.resolved_metadata_json, dict) else {}
        data_infos: list[dict[str, Any]] = []
        for row in input_rows:
            data_info = dict(row.resolved_metadata_json or {})
            data_info.setdefault("input_snapshot", {})
            if isinstance(data_info["input_snapshot"], dict):
                data_info["input_snapshot"] = {
                    **data_info["input_snapshot"],
                    "id": str(row.id),
                    "input_kind": row.input_kind,
                    "dataset_file_id": str(row.dataset_file_id) if row.dataset_file_id else None,
                }
            data_infos.append(data_info)

        errors = selector_metadata.get("errors") if isinstance(selector_metadata.get("errors"), list) else []
        warnings = selector_metadata.get("warnings") if isinstance(selector_metadata.get("warnings"), list) else []
        valid = bool(selector_metadata.get("valid")) and not errors
        output = NodeOutput(
            node_id=node_id,
            node_type=node_type,
            outputs={"output": data_infos},
            data_infos=data_infos,
            metadata={
                "dataset_count": len(data_infos),
                "selection_mode": selector_metadata.get("selection_mode"),
                "missing_dataset_ids": selector_metadata.get("missing_dataset_ids", []),
                "input_snapshot": True,
                "selector_snapshot_id": str(selector.id),
            },
        )
        return NodeDispatchResult(
            output=output,
            status="success" if valid else "failed",
            dataset_count=len(data_infos),
            output_ports=["output"],
            errors=errors,
            warnings=warnings,
        )

    def _execute_fir_filter(self, context: NodeExecutionContext) -> NodeDispatchResult:
        return self._execute_raw_preprocess(context, run_fir_filter, save_descriptor="filt")

    def _execute_butterworth_filter(self, context: NodeExecutionContext) -> NodeDispatchResult:
        return self._execute_raw_preprocess(context, run_butterworth_filter, save_descriptor="iirfilt")

    def _execute_notch_filter(self, context: NodeExecutionContext) -> NodeDispatchResult:
        return self._execute_raw_preprocess(context, run_notch_filter, save_descriptor="notch")

    def _execute_resample(self, context: NodeExecutionContext) -> NodeDispatchResult:
        return self._execute_raw_preprocess(context, run_resample, save_descriptor="resamp")

    def _execute_rereference(self, context: NodeExecutionContext) -> NodeDispatchResult:
        return self._execute_raw_preprocess(context, run_rereference, save_descriptor="ref")

    def _execute_ica_compute(self, context: NodeExecutionContext) -> NodeDispatchResult:
        node_id = str(context.node.get("id") or "")
        node_type = str(context.node.get("type") or "")
        input_data_infos = self._input_data_infos(context, "input")
        if not input_data_infos:
            issue = self._issue(
                code="PIPELINE_NODE_INPUT_MISSING",
                message="Compute ICA has no upstream data_infos on input port.",
                node_id=node_id,
                node_type=node_type,
            )
            output = NodeOutput(node_id=node_id, node_type=node_type, outputs={"output": [], "ica_matrix": []}, data_infos=[])
            return NodeDispatchResult(output=output, status="failed", errors=[issue], output_ports=["output", "ica_matrix"])

        derived_dataset_store = context.derived_dataset_store or DerivedDatasetStore(context.db, context.study, context.execution, context.job)
        ica_data_infos: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for index, data_info in enumerate(input_data_infos):
            try:
                raw = read_raw_from_data_info(data_info, preload=True)
                ica = run_compute_ica(raw, context.params)
                summary = summarize_ica(ica, raw)
                filename = self._derived_fif_filename(data_info, "ica", index, kind="ica")
                upstream_dataset_ids, upstream_recording_ids = self._lineage_for_input(data_info)
                save_meta = self._save_settings_metadata(context, data_info=data_info, index=index)
                artifact = derived_dataset_store.save_file_from_writer(
                    filename,
                    lambda path, ica=ica: save_ica_fif(ica, path),
                    kind="ica_matrix",
                    data_type=save_meta.get("data_type") or "ica_matrix",
                    metadata={
                        "node_id": node_id,
                        "node_type": node_type,
                        "params": context.params,
                        "input_data_info": self._compact_input_data_info(data_info),
                        "mne_summary": {key: value for key, value in summary.items() if key != "components"},
                        "upstream_dataset_ids": upstream_dataset_ids,
                        "upstream_recording_ids": upstream_recording_ids,
                        **save_meta,
                    },
                    preview=summary,
                    source_dataset_id=self._source_dataset_id(data_info),
                    node_id=node_id,
                )
                artifacts.append(artifact)
                ica_data_infos.append(
                    self._ica_data_info(
                        context=context,
                        input_data_info=data_info,
                        artifact=artifact,
                        summary=summary,
                    )
                )
            except Exception as exc:
                errors.append(
                    self._issue(
                        code="PIPELINE_NODE_DATASET_FAILED",
                        message=f"Recording {self._source_dataset_id(data_info) or index} failed in {node_type}: {exc}",
                        node_id=node_id,
                        node_type=node_type,
                    )
                )
                break

        emitted_ica_infos = [] if errors else ica_data_infos
        passthrough_infos = [] if errors else [dict(item) for item in input_data_infos]
        output = NodeOutput(
            node_id=node_id,
            node_type=node_type,
            outputs={"output": passthrough_infos, "ica_matrix": emitted_ica_infos},
            data_infos=emitted_ica_infos,
            artifacts=artifacts,
            metadata={
                "dataset_count": len(emitted_ica_infos),
                "input_dataset_count": len(input_data_infos),
                "save_descriptor": "ica",
            },
        )
        return NodeDispatchResult(
            output=output,
            status="failed" if errors else "success",
            dataset_count=len(emitted_ica_infos),
            output_ports=["output", "ica_matrix"],
            errors=errors,
        )

    def _execute_ica_apply(self, context: NodeExecutionContext) -> NodeDispatchResult:
        node_id = str(context.node.get("id") or "")
        node_type = str(context.node.get("type") or "")
        input_data_infos = self._input_data_infos(context, "input")
        ica_infos = self._input_data_infos(context, "ica_matrix")
        if not input_data_infos or not ica_infos:
            issue = self._issue(
                code="PIPELINE_NODE_INPUT_MISSING",
                message="Apply ICA requires both input EEG data_infos and ica_matrix data_infos.",
                node_id=node_id,
                node_type=node_type,
            )
            output = NodeOutput(node_id=node_id, node_type=node_type, outputs={"output": []}, data_infos=[])
            return NodeDispatchResult(output=output, status="failed", errors=[issue], output_ports=["output"])

        decision = self._ica_decision(context)
        if decision is None:
            interaction = self._ica_interaction_payload(context, input_data_infos, ica_infos)
            output = NodeOutput(
                node_id=node_id,
                node_type=node_type,
                outputs={"output": []},
                data_infos=[],
                artifacts=[item for node_input in context.inputs.values() for item in node_input.artifacts],
                metadata={"interaction": interaction},
            )
            return NodeDispatchResult(
                output=output,
                status="waiting_user_input",
                dataset_count=0,
                output_ports=["output"],
            )

        derived_dataset_store = context.derived_dataset_store or DerivedDatasetStore(context.db, context.study, context.execution, context.job)
        params = {
            **context.params,
            "excluded_components": decision.get("excluded_components", []),
            "decision_version": decision.get("decision_version", context.params.get("decision_version", 1)),
        }
        output_data_infos: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for index, data_info in enumerate(input_data_infos):
            try:
                ica_info = self._matching_ica_info(data_info, ica_infos, index)
                raw = read_raw_from_data_info(data_info, preload=True)
                ica = read_ica_from_data_info(ica_info)
                cleaned = run_apply_ica(raw, ica, params)
                summary = summarize_raw(cleaned)
                filename = self._derived_raw_filename(data_info, "clean", index)
                # ICA Apply 的上游是 EEG input + ICA matrix 两条派生数据
                upstream_dataset_ids, upstream_recording_ids = self._lineage_for_input(data_info, ica_info)
                save_meta = self._save_settings_metadata(context, data_info=data_info, index=index)
                artifact = derived_dataset_store.save_file_from_writer(
                    filename,
                    lambda path, cleaned=cleaned: save_raw_fif(cleaned, path),
                    kind="derivative",
                    data_type=save_meta.get("data_type") or "ica_cleaned",
                    metadata={
                        "node_id": node_id,
                        "node_type": node_type,
                        "params": params,
                        "decision": decision,
                        "input_data_info": self._compact_input_data_info(data_info),
                        "ica_data_info": self._compact_input_data_info(ica_info),
                        "mne_summary": summary,
                        "upstream_dataset_ids": upstream_dataset_ids,
                        "upstream_recording_ids": upstream_recording_ids,
                        **save_meta,
                    },
                    preview=summary,
                    source_dataset_id=self._source_dataset_id(data_info),
                    node_id=node_id,
                )
                artifacts.append(artifact)
                output_data_infos.append(
                    self._derived_data_info(
                        context=context,
                        input_data_info=data_info,
                        artifact=artifact,
                        summary=summary,
                    )
                )
            except Exception as exc:
                errors.append(
                    self._issue(
                        code="PIPELINE_NODE_DATASET_FAILED",
                        message=f"Recording {self._source_dataset_id(data_info) or index} failed in {node_type}: {exc}",
                        node_id=node_id,
                        node_type=node_type,
                    )
                )
                break

        emitted_data_infos = [] if errors else output_data_infos
        output = NodeOutput(
            node_id=node_id,
            node_type=node_type,
            outputs={"output": emitted_data_infos},
            data_infos=emitted_data_infos,
            artifacts=artifacts,
            metadata={
                "dataset_count": len(output_data_infos),
                "input_dataset_count": len(input_data_infos),
                "decision": decision,
                "save_descriptor": "clean",
            },
        )
        return NodeDispatchResult(
            output=output,
            status="failed" if errors else "success",
            dataset_count=len(emitted_data_infos),
            output_ports=["output"],
            errors=errors,
        )

    def _execute_epoch_segment(self, context: NodeExecutionContext) -> NodeDispatchResult:
        return self._execute_epochs_output(context, run_epoch_segment, save_descriptor="epo")

    def _execute_erp_average(self, context: NodeExecutionContext) -> NodeDispatchResult:
        return self._execute_evoked_output(context, run_erp_average, save_descriptor="erp")

    def _execute_raw_preprocess(
        self,
        context: NodeExecutionContext,
        processor: Callable[[Any, dict[str, Any]], Any],
        *,
        save_descriptor: str,
    ) -> NodeDispatchResult:
        node_id = str(context.node.get("id") or "")
        node_type = str(context.node.get("type") or "")
        input_data_infos = self._input_data_infos(context, "input")
        if not input_data_infos:
            issue = self._issue(
                code="PIPELINE_NODE_INPUT_MISSING",
                message="Node has no upstream data_infos on input port.",
                node_id=node_id,
                node_type=node_type,
            )
            output = NodeOutput(node_id=node_id, node_type=node_type, outputs={"output": []}, data_infos=[])
            return NodeDispatchResult(output=output, status="failed", errors=[issue], output_ports=["output"])

        derived_dataset_store = context.derived_dataset_store or DerivedDatasetStore(context.db, context.study, context.execution, context.job)
        output_data_infos: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for index, data_info in enumerate(input_data_infos):
            raw = None
            processed = None
            try:
                raw = read_raw_from_data_info(data_info, preload=True)
                processed = processor(raw, context.params)
                # processor 内部已经 raw.copy() 出新对象，原 raw 不再用，立刻释放避免重复 ~500MB
                raw = None
                summary = summarize_raw(processed)
                filename = self._derived_raw_filename(data_info, save_descriptor, index)
                upstream_dataset_ids, upstream_recording_ids = self._lineage_for_input(data_info)
                save_meta = self._save_settings_metadata(context, data_info=data_info, index=index)
                artifact = derived_dataset_store.save_file_from_writer(
                    filename,
                    lambda path, processed=processed: save_raw_fif(processed, path),
                    kind="derivative",
                    data_type=save_meta.get("data_type") or self._normalise_raw_data_type(save_descriptor),
                    metadata={
                        "node_id": node_id,
                        "node_type": node_type,
                        "params": context.params,
                        "input_data_info": self._compact_input_data_info(data_info),
                        "mne_summary": summary,
                        "upstream_dataset_ids": upstream_dataset_ids,
                        "upstream_recording_ids": upstream_recording_ids,
                        **save_meta,
                    },
                    preview=summary,
                    source_dataset_id=self._source_dataset_id(data_info),
                    node_id=node_id,
                )
                artifacts.append(artifact)
                output_data_infos.append(
                    self._derived_data_info(
                        context=context,
                        input_data_info=data_info,
                        artifact=artifact,
                        summary=summary,
                    )
                )
            except Exception as exc:
                errors.append(
                    self._issue(
                        code="PIPELINE_NODE_DATASET_FAILED",
                        message=f"Recording {data_info.get('dataset_id') or index} failed in {node_type}: {exc}",
                        node_id=node_id,
                        node_type=node_type,
                    )
                )
                break
            finally:
                # 一个 dataset 处理完显式释放 raw + processed（~500MB 级），触发 GC，避免累积到 OOM
                raw = None  # noqa: F841
                processed = None  # noqa: F841
                import gc  # noqa: PLC0415
                gc.collect()

        emitted_data_infos = [] if errors else output_data_infos
        output = NodeOutput(
            node_id=node_id,
            node_type=node_type,
            outputs={"output": emitted_data_infos},
            data_infos=emitted_data_infos,
            artifacts=artifacts,
            metadata={
                "dataset_count": len(output_data_infos),
                "input_dataset_count": len(input_data_infos),
                "save_descriptor": save_descriptor,
            },
        )
        return NodeDispatchResult(
            output=output,
            status="failed" if errors else "success",
            dataset_count=len(emitted_data_infos),
            output_ports=["output"],
            errors=errors,
        )

    @staticmethod
    def _normalise_raw_data_type(save_descriptor: str) -> str:
        """save_descriptor 是节点的存储描述符（例如 iirfilt / firfilt / car / resample / clean）；
        映射到统一的 data_type 枚举值，便于 /results 页面按类型过滤。"""
        mapping = {
            "iirfilt": "filtered_raw",
            "firfilt": "filtered_raw",
            "notch": "filtered_raw",
            "car": "filtered_raw",
            "resample": "filtered_raw",
            "clean": "ica_cleaned",
        }
        return mapping.get(save_descriptor, "raw")

    def _execute_epochs_output(
        self,
        context: NodeExecutionContext,
        processor: Callable[[Any, dict[str, Any]], Any],
        *,
        save_descriptor: str,
    ) -> NodeDispatchResult:
        node_id = str(context.node.get("id") or "")
        node_type = str(context.node.get("type") or "")
        input_data_infos = self._input_data_infos(context, "input")
        if not input_data_infos:
            issue = self._issue(
                code="PIPELINE_NODE_INPUT_MISSING",
                message="Epoch node has no upstream data_infos on input port.",
                node_id=node_id,
                node_type=node_type,
            )
            output = NodeOutput(node_id=node_id, node_type=node_type, outputs={"output": []}, data_infos=[])
            return NodeDispatchResult(output=output, status="failed", errors=[issue], output_ports=["output"])

        derived_dataset_store = context.derived_dataset_store or DerivedDatasetStore(context.db, context.study, context.execution, context.job)
        output_data_infos: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        # split_by 决定输出 cardinality：none → 一进一出；condition → 一进 N 出
        split_mode = str(context.params.get("split_by") or "none").strip().lower()

        for index, data_info in enumerate(input_data_infos):
            try:
                raw = read_raw_from_data_info(data_info, preload=True)
                epochs = processor(raw, context.params)

                if split_mode == "condition":
                    # 按 condition 拆分 —— 每个 event label 一组 sub-epochs，单独保存
                    event_id_map = dict(getattr(epochs, "event_id", {}) or {})
                    for condition_label in sorted(event_id_map.keys()):
                        sub_epochs = epochs[condition_label]
                        if len(sub_epochs) == 0:
                            continue
                        info = self._save_epochs_dataset(
                            context=context,
                            data_info=data_info,
                            epochs=sub_epochs,
                            derived_dataset_store=derived_dataset_store,
                            artifacts=artifacts,
                            save_descriptor=save_descriptor,
                            index=index,
                            condition=condition_label,
                            node_id=node_id,
                            node_type=node_type,
                        )
                        output_data_infos.append(info)
                else:
                    info = self._save_epochs_dataset(
                        context=context,
                        data_info=data_info,
                        epochs=epochs,
                        derived_dataset_store=derived_dataset_store,
                        artifacts=artifacts,
                        save_descriptor=save_descriptor,
                        index=index,
                        condition=None,
                        node_id=node_id,
                        node_type=node_type,
                    )
                    output_data_infos.append(info)
            except Exception as exc:
                errors.append(
                    self._issue(
                        code="PIPELINE_NODE_DATASET_FAILED",
                        message=f"Recording {self._source_dataset_id(data_info) or index} failed in {node_type}: {exc}",
                        node_id=node_id,
                        node_type=node_type,
                    )
                )
                break

        emitted_data_infos = [] if errors else output_data_infos
        output = NodeOutput(
            node_id=node_id,
            node_type=node_type,
            outputs={"output": emitted_data_infos},
            data_infos=emitted_data_infos,
            artifacts=artifacts,
            metadata={
                "dataset_count": len(output_data_infos),
                "input_dataset_count": len(input_data_infos),
                "save_descriptor": save_descriptor,
                "split_mode": split_mode,
            },
        )
        return NodeDispatchResult(
            output=output,
            status="failed" if errors else "success",
            dataset_count=len(emitted_data_infos),
            output_ports=["output"],
            errors=errors,
        )

    def _save_epochs_dataset(
        self,
        *,
        context: NodeExecutionContext,
        data_info: dict[str, Any],
        epochs: Any,
        derived_dataset_store: DerivedDatasetStore,
        artifacts: list[dict[str, Any]],
        save_descriptor: str,
        index: int,
        condition: str | None,
        node_id: str,
        node_type: str,
    ) -> dict[str, Any]:
        """把一份 (子)epochs 写入磁盘 + 登记 derived_dataset，返回 data_info。

        condition 非空时：文件名加 condition 后缀；apply_save_settings 用 split_value
        触发 dynamic_tags_when_split + name_template_default_split；输出 data_info 带 condition 字段。
        """
        summary = summarize_epochs(epochs)
        filename = self._derived_fif_filename(
            data_info, save_descriptor, index, kind="epochs", condition=condition
        )
        upstream_dataset_ids, upstream_recording_ids = self._lineage_for_input(data_info)
        save_meta = self._save_settings_metadata(
            context, data_info=data_info, index=index, split_value=condition
        )
        artifact = derived_dataset_store.save_file_from_writer(
            filename,
            lambda path, epochs=epochs: save_epochs_fif(epochs, path),
            kind="derivative",
            data_type=save_meta.get("data_type") or "epochs",
            metadata={
                "node_id": node_id,
                "node_type": node_type,
                "params": context.params,
                "input_data_info": self._compact_input_data_info(data_info),
                "mne_summary": summary,
                "upstream_dataset_ids": upstream_dataset_ids,
                "upstream_recording_ids": upstream_recording_ids,
                "condition": condition,  # 让 _register_artifact 写入 derived.condition 列
                **save_meta,
            },
            preview=summary,
            source_dataset_id=self._source_dataset_id(data_info),
            node_id=node_id,
        )
        artifacts.append(artifact)
        info = self._derived_data_info(
            context=context,
            input_data_info=data_info,
            artifact=artifact,
            summary=summary,
        )
        if condition:
            info["condition"] = condition
        return info

    def _execute_evoked_output(
        self,
        context: NodeExecutionContext,
        processor: Callable[[Any, dict[str, Any]], Any],
        *,
        save_descriptor: str,
    ) -> NodeDispatchResult:
        """ERP / Evoked-class 节点的执行：每个 (input data_info, condition) 组合 → 一个 evoked artifact。

        condition 来源优先级：
          1. 上游已经 split (input data_info.condition 是单字符串) → 直接用，忽略 params.condition
          2. 用户在 ERP 节点参数里选的 condition（可能是字符串 / list / 逗号分隔）
              - 列表中的每个 condition 单独 average → 多个 artifact
              - 这跟节点 spec.save.always_per_condition=true 一致

        历史 bug：之前 len(labels) > 1 时直接 epochs[labels].average()，把所有 condition pool
        在一起出 1 个 evoked，与"每 condition 一个 ERP"的设计相悖。这里改为外层循环展开。
        """
        node_id = str(context.node.get("id") or "")
        node_type = str(context.node.get("type") or "")
        input_data_infos = self._input_data_infos(context, "input")
        if not input_data_infos:
            issue = self._issue(
                code="PIPELINE_NODE_INPUT_MISSING",
                message="ERP node has no upstream epochs data_infos on input port.",
                node_id=node_id,
                node_type=node_type,
            )
            output = NodeOutput(node_id=node_id, node_type=node_type, outputs={"output": []}, data_infos=[])
            return NodeDispatchResult(output=output, status="failed", errors=[issue], output_ports=["output"])

        derived_dataset_store = context.derived_dataset_store or DerivedDatasetStore(context.db, context.study, context.execution, context.job)
        output_data_infos: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        outer_break = False
        for index, data_info in enumerate(input_data_infos):
            if outer_break:
                break

            # 决定本次 input data_info 要展开哪些 condition
            input_condition_raw = data_info.get("condition") if isinstance(data_info.get("condition"), str) else None
            input_condition = input_condition_raw.strip() if input_condition_raw else None

            if input_condition:
                # 上游 split 后已是单 condition → 直接用
                conditions_to_run = [input_condition]
            else:
                # 上游合并模式 → 用 params.condition 展开
                conditions_to_run = _normalize_event_labels(context.params.get("condition"))
                if not conditions_to_run:
                    errors.append(
                        self._issue(
                            code="PIPELINE_NODE_DATASET_FAILED",
                            message=f"Recording {self._source_dataset_id(data_info) or index} failed in {node_type}: "
                                    "ERP.condition is required (上游 epochs 含多 condition，请在 ERP 节点选至少一个).",
                            node_id=node_id,
                            node_type=node_type,
                        )
                    )
                    break

            # 一次 read_epochs，多个 condition 复用
            try:
                epochs = read_epochs_from_data_info(data_info, preload=True)
            except Exception as exc:
                errors.append(
                    self._issue(
                        code="PIPELINE_NODE_DATASET_FAILED",
                        message=f"Recording {self._source_dataset_id(data_info) or index} failed in {node_type}: "
                                f"read_epochs failed: {exc}",
                        node_id=node_id,
                        node_type=node_type,
                    )
                )
                break

            artifact_index_in_data_info = 0
            for cond in conditions_to_run:
                evoked = None
                try:
                    erp_params: dict[str, Any] = {**context.params, "condition": cond}
                    evoked = processor(epochs, erp_params)
                    summary = summarize_evoked(evoked)
                    # 为避免多 condition 同名，artifact filename 用 condition 区分
                    filename = self._derived_fif_filename(
                        data_info,
                        save_descriptor,
                        index * 1000 + artifact_index_in_data_info,
                        kind="evoked",
                        condition=cond,
                    )
                    upstream_dataset_ids, upstream_recording_ids = self._lineage_for_input(data_info)
                    save_meta = self._save_settings_metadata(
                        context,
                        data_info=data_info,
                        index=index,
                        split_value=cond,
                    )
                    artifact = derived_dataset_store.save_file_from_writer(
                        filename,
                        lambda path, ev=evoked: save_evoked_fif(ev, path),
                        kind="analysis_result",
                        data_type=save_meta.get("data_type") or "evoked",
                        metadata={
                            "node_id": node_id,
                            "node_type": node_type,
                            "params": erp_params,
                            "input_data_info": self._compact_input_data_info(data_info),
                            "mne_summary": summary,
                            "upstream_dataset_ids": upstream_dataset_ids,
                            "upstream_recording_ids": upstream_recording_ids,
                            "condition": cond,
                            **save_meta,
                        },
                        preview=summary,
                        source_dataset_id=self._source_dataset_id(data_info),
                        node_id=node_id,
                    )
                    artifacts.append(artifact)
                    output_data_infos.append(
                        self._derived_data_info(
                            context=context,
                            input_data_info=data_info,
                            artifact=artifact,
                            summary=summary,
                        )
                    )
                    artifact_index_in_data_info += 1
                except Exception as exc:
                    errors.append(
                        self._issue(
                            code="PIPELINE_NODE_DATASET_FAILED",
                            message=f"Recording {self._source_dataset_id(data_info) or index} "
                                    f"condition={cond!r} failed in {node_type}: {exc}",
                            node_id=node_id,
                            node_type=node_type,
                        )
                    )
                    outer_break = True
                    break
                finally:
                    # 每个 condition 处理完立刻释放 evoked，避免在低内存机器上累积
                    evoked = None

            # 一个 data_info 处理完，立刻释放 epochs（176MB 级）+ 触发 GC，避免被 OOM 杀
            epochs = None  # noqa: F841 — 显式断引用让 GC 回收
            import gc  # noqa: PLC0415
            gc.collect()

        emitted_data_infos = [] if errors else output_data_infos
        output = NodeOutput(
            node_id=node_id,
            node_type=node_type,
            outputs={"output": emitted_data_infos},
            data_infos=emitted_data_infos,
            artifacts=artifacts,
            metadata={
                "dataset_count": len(output_data_infos),
                "input_dataset_count": len(input_data_infos),
                "save_descriptor": save_descriptor,
            },
        )
        return NodeDispatchResult(
            output=output,
            status="failed" if errors else "success",
            dataset_count=len(emitted_data_infos),
            output_ports=["output"],
            errors=errors,
        )

    @staticmethod
    def _input_data_infos(context: NodeExecutionContext, port: str) -> list[dict[str, Any]]:
        node_input = context.inputs.get(port)
        return list(node_input.data_infos) if node_input else []

    @staticmethod
    def _lineage_for_input(*data_infos: dict[str, Any]) -> tuple[list[str], list[str]]:
        """从一个或多个上游 data_info 推导 (upstream_dataset_ids, upstream_recording_ids).

        - upstream_dataset_ids: 直接上游的 derived_dataset id（来自上游 data_info["artifact_id"]）。
          LoadData 不写 derived_dataset，所以 LoadData 输出的 data_info 没有 artifact_id，对应空列表。
        - upstream_recording_ids: 最终回溯到的原始 recording id（来自 source_dataset_id / dataset_id）。
        """
        dataset_ids: list[str] = []
        recording_ids: list[str] = []
        dataset_seen: set[str] = set()
        recording_seen: set[str] = set()
        for data_info in data_infos:
            if not isinstance(data_info, dict):
                continue
            upstream = data_info.get("artifact_id") or data_info.get("derived_dataset_id")
            if upstream:
                key = str(upstream)
                if key not in dataset_seen:
                    dataset_seen.add(key)
                    dataset_ids.append(key)
            rec = data_info.get("source_dataset_id") or data_info.get("dataset_id")
            if rec:
                rkey = str(rec)
                if rkey not in recording_seen:
                    recording_seen.add(rkey)
                    recording_ids.append(rkey)
        return dataset_ids, recording_ids

    @staticmethod
    def _save_settings_metadata(
        context: NodeExecutionContext,
        *,
        data_info: dict[str, Any],
        index: int,
        split_value: str | None = None,
    ) -> dict[str, Any]:
        """调 apply_save_settings 并返回可直接 merge 进 metadata 的 dict。

        返回字段:
          display_name / tags / retention_status / retention_expires_at /
          step_label / data_type

        dispatcher 把它 update 到传给 derived_dataset_store.save_file_from_writer 的
        metadata，让 _register_derived_dataset 接管写入 derived_datasets。
        """
        return apply_save_settings(
            db=context.db,
            study_id=getattr(context.study, "id", None),
            node=context.node,
            node_spec=context.node_spec,
            params=context.params,
            topology=context.topology,
            bids_entities=data_info,
            split_value=split_value,
            index=index,
        )

    @staticmethod
    def _derived_raw_filename(data_info: dict[str, Any], save_descriptor: str, index: int) -> str:
        return NodeDispatcher._derived_fif_filename(data_info, save_descriptor, index, kind="raw")

    @staticmethod
    def _derived_fif_filename(
        data_info: dict[str, Any],
        save_descriptor: str,
        index: int,
        *,
        kind: str,
        condition: str | None = None,
    ) -> str:
        """生成派生 .fif 文件名。

        condition 非空时插在 save_descriptor 前面：
          sub-01_rest_go_epo.fif（含 condition）
          sub-01_rest_epo.fif（不分 condition）
        """
        source = (
            data_info.get("fif_path")
            or data_info.get("storage_path")
            or data_info.get("artifact_storage_path")
            or data_info.get("source_path")
            or data_info.get("dataset_id")
            or f"dataset-{index + 1}"
        )
        name = Path(str(source)).name
        lower_name = name.lower()
        for suffix in (".fif.gz", ".fif"):
            if lower_name.endswith(suffix):
                name = name[: -len(suffix)]
                lower_name = name.lower()
                break
        for suffix in ("-raw", "_raw", "-epo", "-ave"):
            if lower_name.endswith(suffix):
                name = name[: -len(suffix)]
                break
        safe_base = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in name).strip("_")
        if not safe_base:
            safe_base = f"dataset-{index + 1}"
        output_suffix = {"raw": "-raw.fif", "epochs": "-epo.fif", "evoked": "-ave.fif", "ica": "-ica.fif"}[kind]
        if condition:
            safe_condition = "".join(
                char if char.isalnum() or char in {"-", "_"} else "_" for char in str(condition)
            ).strip("_")
            if safe_condition:
                return f"{safe_base}_{safe_condition}_{save_descriptor}{output_suffix}"
        return f"{safe_base}_{save_descriptor}{output_suffix}"

    @staticmethod
    def _compact_input_data_info(data_info: dict[str, Any]) -> dict[str, Any]:
        keys = (
            "dataset_id",
            "source_dataset_id",
            "study_id",
            "subject_id",
            "subject",
            "task",
            "run",
            "storage_path",
            "storage_uri",
            "logical_path",
            "fif_path",
            "dataset_file_id",
            "source_dataset_file_id",
            "file_role",
            "sha256",
            "artifact_id",
            "artifact_storage_uri",
            "artifact_storage_path",
            "analysis_result_id",
            "content_hash",
            "data_type",
            "ica_path",
            "ica_abs_path",
        )
        return {key: data_info.get(key) for key in keys if key in data_info}

    @staticmethod
    def _derived_data_info(
        *,
        context: NodeExecutionContext,
        input_data_info: dict[str, Any],
        artifact: dict[str, Any],
        summary: dict[str, Any],
    ) -> dict[str, Any]:
        storage_path = str(artifact.get("storage_path") or "")
        artifact_path = NodeDispatcher._artifact_path(context.study, artifact)
        fif_abs_path = str(artifact_path) if artifact_path else None
        derived = dict(input_data_info)
        derived.update(
            {
                "source_dataset_id": NodeDispatcher._source_dataset_id(input_data_info),
                "source_dataset_file_id": input_data_info.get("source_dataset_file_id") or input_data_info.get("dataset_file_id"),
                "dataset_file_id": None,
                "file_role": "pipeline_artifact",
                "artifact_id": artifact.get("artifact_id"),
                "storage_path": storage_path,
                "storage_uri": artifact.get("storage_uri"),
                "logical_path": storage_path,
                "artifact_storage_path": storage_path,
                "artifact_storage_uri": artifact.get("storage_uri"),
                "pipeline_execution_id": str(getattr(context.execution, "id", "")),
                "job_id": str(getattr(context.job, "id", "")),
                "fif_path": storage_path,
                "fif_abs_path": fif_abs_path,
                "fif_exists": bool(fif_abs_path and Path(fif_abs_path).exists()),
                "file_size": artifact.get("file_size"),
                "checksum": artifact.get("checksum"),
                "sha256": artifact.get("sha256") or artifact.get("checksum"),
                "content_hash": artifact.get("content_hash") or artifact.get("checksum"),
                "data_type": summary.get("data_type", "raw"),
                "processing": {
                    "node_id": str(context.node.get("id") or ""),
                    "node_type": str(context.node.get("type") or ""),
                    "params": context.params,
                },
            }
        )
        for key, value in summary.items():
            if key not in {"ch_names", "channel_types"}:
                derived[key] = value
        return derived

    @staticmethod
    def _source_dataset_id(data_info: dict[str, Any]) -> Any:
        return data_info.get("source_dataset_id") or data_info.get("dataset_id")

    @staticmethod
    def _artifact_path(study: Any, artifact: dict[str, Any]) -> Path | None:
        storage_uri = artifact.get("storage_uri")
        if storage_uri:
            try:
                return StorageService().resolve_path(
                    str(storage_uri),
                    study_id=str(getattr(study, "id", "") or ""),
                    study_root=getattr(study, "data_root", None),
                )
            except (StorageUriError, ValueError):
                pass
        storage_path = str(artifact.get("storage_path") or "")
        if not storage_path:
            return None
        path = Path(storage_path).expanduser()
        if path.is_absolute():
            return path
        return (Path(study.data_root).expanduser().resolve() / storage_path).resolve()

    @staticmethod
    def _ica_data_info(
        *,
        context: NodeExecutionContext,
        input_data_info: dict[str, Any],
        artifact: dict[str, Any],
        summary: dict[str, Any],
    ) -> dict[str, Any]:
        storage_path = str(artifact.get("storage_path") or "")
        artifact_path = NodeDispatcher._artifact_path(context.study, artifact)
        abs_path = str(artifact_path) if artifact_path else None
        derived = dict(input_data_info)
        derived.update(
            {
                "source_dataset_id": NodeDispatcher._source_dataset_id(input_data_info),
                "source_dataset_file_id": input_data_info.get("source_dataset_file_id") or input_data_info.get("dataset_file_id"),
                "dataset_file_id": None,
                "file_role": "pipeline_artifact",
                "artifact_id": artifact.get("artifact_id"),
                "storage_path": storage_path,
                "storage_uri": artifact.get("storage_uri"),
                "logical_path": storage_path,
                "artifact_storage_path": storage_path,
                "artifact_storage_uri": artifact.get("storage_uri"),
                "pipeline_execution_id": str(getattr(context.execution, "id", "")),
                "job_id": str(getattr(context.job, "id", "")),
                "ica_path": storage_path,
                "ica_abs_path": abs_path,
                "fif_path": storage_path,
                "fif_abs_path": abs_path,
                "fif_exists": bool(abs_path and Path(abs_path).exists()),
                "file_size": artifact.get("file_size"),
                "checksum": artifact.get("checksum"),
                "sha256": artifact.get("sha256") or artifact.get("checksum"),
                "content_hash": artifact.get("content_hash") or artifact.get("checksum"),
                "data_type": "ica",
                "component_count": summary.get("n_components"),
                "component_preview": summary.get("components", []),
                "processing": {
                    "node_id": str(context.node.get("id") or ""),
                    "node_type": str(context.node.get("type") or ""),
                    "params": context.params,
                },
            }
        )
        for key, value in summary.items():
            if key not in {"components"}:
                derived[key] = value
        return derived

    @staticmethod
    def _ica_decision(context: NodeExecutionContext) -> dict[str, Any] | None:
        output_json = getattr(context.job, "output_json", None) or {}
        interaction = NodeDispatcher._interaction_from_output(output_json)
        decision = interaction.get("decision") if isinstance(interaction, dict) else None
        if isinstance(decision, dict):
            excluded = parse_excluded_components(decision.get("excluded_components", []))
            return {
                **decision,
                "excluded_components": excluded,
                "decision_version": int(decision.get("decision_version") or context.params.get("decision_version") or 1),
            }

        raw_param = context.params.get("excluded_components")
        if raw_param not in (None, ""):
            excluded = parse_excluded_components(raw_param)
            return {
                "excluded_components": excluded,
                "decision_version": int(context.params.get("decision_version") or 1),
                "source": "node_params",
            }
        return None

    @staticmethod
    def _interaction_from_output(output_json: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(output_json, dict):
            return {}
        interaction = output_json.get("interaction")
        if isinstance(interaction, dict):
            return interaction
        metadata = output_json.get("metadata")
        if isinstance(metadata, dict) and isinstance(metadata.get("interaction"), dict):
            return metadata["interaction"]
        return {}

    @staticmethod
    def _ica_interaction_payload(
        context: NodeExecutionContext,
        input_data_infos: list[dict[str, Any]],
        ica_infos: list[dict[str, Any]],
    ) -> dict[str, Any]:
        datasets = []
        components_by_key: dict[str, dict[str, Any]] = {}
        for index, data_info in enumerate(input_data_infos):
            ica_info = NodeDispatcher._matching_ica_info(data_info, ica_infos, index)
            components = NodeDispatcher._component_preview_from_ica_info(ica_info)
            key = str(NodeDispatcher._source_dataset_id(data_info) or data_info.get("dataset_id") or index)
            datasets.append(
                {
                    "dataset_id": data_info.get("dataset_id"),
                    "source_dataset_id": NodeDispatcher._source_dataset_id(data_info),
                    "ica_artifact_id": ica_info.get("artifact_id"),
                    "components": components,
                }
            )
            for component in components:
                component_key = str(component.get("index"))
                components_by_key.setdefault(component_key, component)

        return {
            "type": "ica_component_selection",
            "status": "waiting_user_input",
            "decision_version": int(context.params.get("decision_version") or 1),
            "components": list(components_by_key.values()),
            "preview_json": {"datasets": datasets},
        }

    @staticmethod
    def _component_preview_from_ica_info(ica_info: dict[str, Any]) -> list[dict[str, Any]]:
        components = ica_info.get("component_preview")
        if isinstance(components, list):
            return [item for item in components if isinstance(item, dict)]
        preview = ica_info.get("preview_json")
        if isinstance(preview, dict) and isinstance(preview.get("components"), list):
            return [item for item in preview["components"] if isinstance(item, dict)]
        if isinstance(ica_info.get("components"), list):
            return [item for item in ica_info["components"] if isinstance(item, dict)]
        return []

    @staticmethod
    def _matching_ica_info(data_info: dict[str, Any], ica_infos: list[dict[str, Any]], index: int) -> dict[str, Any]:
        source_id = NodeDispatcher._source_dataset_id(data_info)
        if source_id is not None:
            for ica_info in ica_infos:
                if NodeDispatcher._source_dataset_id(ica_info) == source_id:
                    return ica_info
        if index < len(ica_infos):
            return ica_infos[index]
        if len(ica_infos) == 1:
            return ica_infos[0]
        raise ValueError("Could not match ICA matrix data_info to input dataset.")

    @staticmethod
    def _issue(*, code: str, message: str, node_id: str, node_type: str) -> dict[str, Any]:
        return PipelineValidationIssue(
            code=code,
            message=message,
            node_id=node_id,
            node_type=node_type,
        ).model_dump(mode="json")
