"""
Purpose: Implement workflow/Pipeline runtime support for dispatcher, including validation, execution, artifacts, cache, or data resolution.
Related: app/routers/pipelines.py, app/tasks/pipeline_tasks.py, app/pipeline/nodes/*.json, docs_v2/5-00 and docs_v2/7-40.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.engine.analysis.baseline import run_baseline
from app.engine.analysis.epoching import run_epoch_segment
from app.engine.analysis.erp import _normalize_event_labels, run_erp_average
from app.engine.analysis.psd import run_psd
from app.engine.analysis.reject import run_reject_trials
from app.engine.analysis.tfr import run_tfr
from app.engine.group.average import build_grandavg_payload, run_group_average
from app.engine.group.compare import run_group_compare
from app.engine.group.merge import run_group_merge
from app.engine.io import (
    read_epochs_from_data_info,
    read_ica_from_data_info,
    read_raw_from_data_info,
    save_epochs_fif,
    save_evoked_fif,
    save_ica_fif,
    save_psd_npz,
    save_raw_fif,
    save_stat_map_npz,
    save_tfr_h5,
    save_unit_stack_npz,
    summarize_epochs,
    summarize_evoked,
    summarize_psd,
    summarize_raw,
    summarize_stat_map,
    summarize_tfr,
    summarize_unit_stack,
)
from app.engine.ica.apply import parse_excluded_components, run_apply_ica
from app.engine.ica.compute import run_compute_ica, summarize_ica
from app.engine.ica.iclabel import run_iclabel
from app.engine.preprocess.artifact_mark import parse_bad_channels, parse_bad_segments, run_artifact_mark
from app.engine.preprocess.bad_channels import run_bad_channels
from app.engine.preprocess.channel_location import run_channel_location
from app.engine.preprocess.event_manager import run_event_manager
from app.engine.preprocess.event_remap import run_event_remap
from app.engine.preprocess.filters import run_filter
from app.engine.preprocess.reference import run_rereference
from app.engine.preprocess.resample import run_resample
from app.models import PipelineExecutionInput
from app.pipeline.study_output_store import StudyOutputStore
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


def _concatenate_epochs(items: list[Any]) -> Any:
    if not items:
        raise ValueError("No epochs to concatenate.")
    import mne  # noqa: PLC0415

    normalized, per_epoch_annotations = _normalise_epochs_for_concatenation(items)
    merged = normalized[0] if len(normalized) == 1 else mne.concatenate_epochs(normalized, add_offset=True, verbose="ERROR")
    _restore_epoch_annotations(merged, per_epoch_annotations)
    return merged


def _normalise_epochs_for_concatenation(items: list[Any]) -> tuple[list[Any], list[list[tuple[Any, Any, Any]]]]:
    names: list[str] = []
    for epochs in items:
        for name in dict(getattr(epochs, "event_id", {}) or {}).keys():
            text = str(name or "").strip()
            if text and text not in names:
                names.append(text)
    if not names:
        raise ValueError("Epoch Merge input has no event_id labels.")

    unified_event_id = {name: index + 1 for index, name in enumerate(names)}
    normalized: list[Any] = []
    annotations: list[list[tuple[Any, Any, Any]]] = []
    for epochs in items:
        per_epoch = epochs.get_annotations_per_epoch() if callable(getattr(epochs, "get_annotations_per_epoch", None)) else []
        annotations.extend([list(row) for row in per_epoch])
        copy = epochs.copy()
        old_inverse = {int(code): str(name) for name, code in dict(getattr(copy, "event_id", {}) or {}).items()}
        if hasattr(copy, "events"):
            for row in copy.events:
                label = old_inverse.get(int(row[2]))
                if label in unified_event_id:
                    row[2] = unified_event_id[label]
        copy.event_id = dict(unified_event_id)
        elys_metadata = getattr(epochs, "_elys_condition_metadata", None)
        if isinstance(elys_metadata, list):
            copy._elys_condition_metadata = list(elys_metadata)  # type: ignore[attr-defined]
        normalized.append(copy)
    return normalized, annotations


def _restore_epoch_annotations(epochs: Any, per_epoch_annotations: list[list[tuple[Any, Any, Any]]]) -> None:
    if not per_epoch_annotations or not hasattr(epochs, "events"):
        return
    try:
        sfreq = float(epochs.info["sfreq"])
        import mne  # noqa: PLC0415

        onsets: list[float] = []
        durations: list[float] = []
        descriptions: list[str] = []
        for event, annotations in zip(epochs.events, per_epoch_annotations, strict=False):
            event_onset = float(event[0]) / sfreq
            for onset, duration, description in annotations:
                onsets.append(event_onset + float(onset))
                durations.append(float(duration))
                descriptions.append(str(description))
        if onsets:
            epochs.set_annotations(mne.Annotations(onset=onsets, duration=durations, description=descriptions))
    except Exception:
        return


class NodeDispatcher:
    def __init__(self):
        self._handlers: dict[str, Callable[[NodeExecutionContext], NodeDispatchResult]] = {
            "eeg/data/load": self._execute_load_data,
            "eeg/filter/apply": self._execute_filter,
            "eeg/preproc/resample": self._execute_resample,
            "eeg/preproc/rereference": self._execute_rereference,
            "eeg/preproc/channel_location": self._execute_channel_location,
            "eeg/preproc/bad_channels": self._execute_bad_channels,
            "eeg/preproc/artifact_mark": self._execute_artifact_mark,
            "eeg/preproc/event_manager": self._execute_event_manager,
            "eeg/preproc/event_remap": self._execute_event_remap,
            "eeg/ica/compute": self._execute_ica_compute,
            "eeg/ica/apply": self._execute_ica_apply,
            "eeg/ica/iclabel": self._execute_ica_iclabel,
            "eeg/epoch/segment": self._execute_epoch_segment,
            "eeg/epoch/merge": self._execute_epoch_merge,
            "eeg/epoch/baseline": self._execute_baseline,
            "eeg/epoch/reject": self._execute_reject_trials,
            "eeg/analysis/erp": self._execute_erp_average,
            "eeg/analysis/tfr": self._execute_tfr_average,
            "eeg/analysis/psd": self._execute_psd_average,
            "eeg/group/merge": self._execute_group_merge,
            "eeg/group/average": self._execute_group_average,
            "eeg/group/compare": self._execute_group_compare,
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

    def _execute_filter(self, context: NodeExecutionContext) -> NodeDispatchResult:
        # 统一滤波节点：按 filter_type / method 推导 save_descriptor（影响派生文件名后缀）
        params = context.params if isinstance(context.params, dict) else {}
        filter_type = str(params.get("filter_type") or "bandpass").strip().lower()
        method = str(params.get("method") or "fir").strip().lower()
        if filter_type == "notch":
            save_descriptor = "notch"
        elif method == "iir":
            save_descriptor = "iirfilt"
        else:
            save_descriptor = "firfilt"
        return self._execute_raw_preprocess(context, run_filter, save_descriptor=save_descriptor)

    def _execute_resample(self, context: NodeExecutionContext) -> NodeDispatchResult:
        return self._execute_raw_preprocess(context, run_resample, save_descriptor="resamp")

    def _execute_event_remap(self, context: NodeExecutionContext) -> NodeDispatchResult:
        return self._execute_raw_preprocess(context, run_event_remap, save_descriptor="evtmap")

    def _execute_rereference(self, context: NodeExecutionContext) -> NodeDispatchResult:
        return self._execute_raw_preprocess(context, run_rereference, save_descriptor="ref")

    def _execute_channel_location(self, context: NodeExecutionContext) -> NodeDispatchResult:
        # montage=custom 时按 custom_montage_file_id 在 DB 里解析出上传文件的绝对路径，用闭包喂给
        # run_channel_location——保持引擎函数纯净，也不把服务器物理路径塞进参数哈希（哈希仍认 file_id）。
        custom_montage_path = self._resolve_custom_montage_path(context)

        def processor(raw: Any, params: dict[str, Any]) -> Any:
            return run_channel_location(raw, params, custom_montage_path=custom_montage_path)

        return self._execute_raw_preprocess(context, processor, save_descriptor="chanloc")

    @staticmethod
    def _resolve_custom_montage_path(context: NodeExecutionContext) -> str | None:
        """montage=custom 时，把 custom_montage_file_id 解析成上传电极文件的绝对路径；否则 None。"""
        params = context.params if isinstance(context.params, dict) else {}
        if str(params.get("montage") or "").strip().lower() != "custom":
            return None
        file_id = params.get("custom_montage_file_id")
        if not file_id:
            raise ValueError("「通道定位」选择了自定义电极文件，但未指定文件（custom_montage_file_id 为空）。")
        from app.config import get_settings  # noqa: PLC0415
        from app.models import DatasetMontage  # noqa: PLC0415

        row = context.db.query(DatasetMontage).filter(DatasetMontage.id == str(file_id)).first()
        if row is None:
            raise ValueError(f"找不到自定义电极文件（id={file_id}），可能已被删除，请重新上传或选择。")
        root = Path(get_settings().DATASETS_STORAGE_ROOT) / str(row.dataset_asset_id)
        path = root / row.relative_path
        if not path.exists():
            raise ValueError(f"自定义电极文件物理缺失：{path}")
        return str(path)

    def _execute_bad_channels(self, context: NodeExecutionContext) -> NodeDispatchResult:
        # 仅标记 vs 插值修复用不同存储后缀（影响派生文件名）
        params = context.params if isinstance(context.params, dict) else {}
        action = str(params.get("action") or "interpolate").strip().lower()
        save_descriptor = "interp" if action == "interpolate" else "badchan"
        return self._execute_raw_preprocess(context, run_bad_channels, save_descriptor=save_descriptor)

    def _execute_artifact_mark(self, context: NodeExecutionContext) -> NodeDispatchResult:
        """人工去伪迹去坏段（交互节点，与 Apply ICA 同款回环）：
        无 decision → 返回 waiting_user_input + 审核 payload（前端双击开页框选/点选）；
        有 decision → 把人工标记合进 params，复用 raw→raw 保存循环落 BAD_ 标注 / info['bads'] / 可选插值。
        """
        node_id = str(context.node.get("id") or "")
        node_type = str(context.node.get("type") or "")
        input_data_infos = self._input_data_infos(context, "input")
        if not input_data_infos:
            issue = self._issue(
                code="PIPELINE_NODE_INPUT_MISSING",
                message="Artifact Mark has no upstream data_infos on input port.",
                node_id=node_id,
                node_type=node_type,
            )
            output = NodeOutput(node_id=node_id, node_type=node_type, outputs={"output": []}, data_infos=[])
            return NodeDispatchResult(output=output, status="failed", errors=[issue], output_ports=["output"])

        decision = self._artifact_decision(context)
        if decision is None:
            interaction = self._artifact_interaction_payload(context, input_data_infos)
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

        base_params = context.params if isinstance(context.params, dict) else {}
        channel_action = str(decision.get("channel_action") or base_params.get("channel_action") or "mark").strip().lower()
        params = {
            **base_params,
            "bad_segments": decision.get("bad_segments", []),
            "bad_channels": decision.get("bad_channels", []),
            "bad_segments_by_dataset": decision.get("bad_segments_by_dataset", {}),
            "bad_channels_by_dataset": decision.get("bad_channels_by_dataset", {}),
            "channel_action": channel_action,
            "decision_version": decision.get("decision_version", base_params.get("decision_version", 1)),
        }
        def params_for_input(data_info: dict[str, Any], index: int) -> dict[str, Any]:
            dataset_segments, dataset_channels = NodeDispatcher._artifact_marks_for_dataset(
                decision,
                data_info,
                index,
            )
            return {
                **params,
                "bad_segments": dataset_segments,
                "bad_channels": dataset_channels,
            }

        save_descriptor = "interp" if channel_action == "interpolate" else "artifact"
        return self._execute_raw_preprocess(
            context,
            run_artifact_mark,
            save_descriptor=save_descriptor,
            params_override=params,
            params_for_input=params_for_input,
        )

    def _execute_event_manager(self, context: NodeExecutionContext) -> NodeDispatchResult:
        """事件管理器（交互节点，与 Artifact Mark / Apply ICA 同款回环）：
        无 decision → 返回 waiting_user_input + 事件编辑 payload（前端双击开页改 marker）；
        有 decision → 把人工梳理合进 params 复用 raw→raw 保存循环改写 annotations。

        模式分流（事件按数据集逐条精修无法跨集套用，故按输入数量分流，见 event_manager.run_event_manager）：
          - 单数据集 + decision.events → literal：把最终事件清单写给这唯一数据集（最精确）。
          - 其余 → rules：只套 group_operations 分组级规则（改名/合并/丢弃/平移），逐事件编辑被略过。
        """
        node_id = str(context.node.get("id") or "")
        node_type = str(context.node.get("type") or "")
        input_data_infos = self._input_data_infos(context, "input")
        if not input_data_infos:
            issue = self._issue(
                code="PIPELINE_NODE_INPUT_MISSING",
                message="Event Manager has no upstream data_infos on input port.",
                node_id=node_id,
                node_type=node_type,
            )
            output = NodeOutput(node_id=node_id, node_type=node_type, outputs={"output": []}, data_infos=[])
            return NodeDispatchResult(output=output, status="failed", errors=[issue], output_ports=["output"])

        decision = self._event_manager_decision(context)
        if decision is None:
            interaction = self._event_manager_interaction_payload(context, input_data_infos)
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

        params = {
            **context.params,
            "group_operations": decision.get("group_operations") or [],
            "operations": decision.get("operations") or [],
            "decision_version": decision.get("decision_version", context.params.get("decision_version", 1)),
        }
        # 逐事件最终清单只在「唯一数据集」下落盘——多数据集时事件各不相同，无法套同一份清单，
        # 退回只套 group_operations 规则（promote-to-rule 桥的批量语义即在此）。
        events = decision.get("events")
        if isinstance(events, list) and len(events) > 0 and len(input_data_infos) == 1:
            params["events"] = events
        return self._execute_raw_preprocess(
            context, run_event_manager, save_descriptor="evtman", params_override=params
        )

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

        study_output_store = context.study_output_store or StudyOutputStore(context.db, context.study, context.execution, context.job)
        ica_data_infos: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for index, data_info in enumerate(input_data_infos):
            try:
                raw = read_raw_from_data_info(data_info, preload=True)
                ica = run_compute_ica(raw, context.params)
                summary = summarize_ica(ica, raw)
                # 记录源 raw 紧凑引用，供 ICA 成分审阅端点回溯载入（算时序 / 频谱 / 去除前后对比）
                summary["source_ref"] = self._compact_input_data_info(data_info)
                filename = self._derived_fif_filename(data_info, "ica", index, kind="ica")
                upstream_dataset_ids, upstream_recording_ids = self._lineage_for_input(data_info)
                save_meta = self._save_settings_metadata(context, data_info=data_info, index=index)
                artifact = study_output_store.save_file_from_writer(
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

        study_output_store = context.study_output_store or StudyOutputStore(context.db, context.study, context.execution, context.job)
        base_params = {
            **context.params,
            "excluded_components": decision.get("excluded_components", []),
            "excluded_components_by_dataset": decision.get("excluded_components_by_dataset", {}),
            "decision_version": decision.get("decision_version", context.params.get("decision_version", 1)),
        }
        output_data_infos: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for index, data_info in enumerate(input_data_infos):
            try:
                ica_info = self._matching_ica_info(data_info, ica_infos, index)
                excluded_components = self._ica_excluded_for_dataset(decision, data_info, ica_info, index)
                params = {
                    **base_params,
                    "excluded_components": excluded_components,
                }
                raw = read_raw_from_data_info(data_info, preload=True)
                ica = read_ica_from_data_info(ica_info)
                cleaned = run_apply_ica(raw, ica, params)
                summary = summarize_raw(cleaned)
                filename = self._derived_raw_filename(data_info, "clean", index)
                # ICA Apply 的上游是 EEG input + ICA matrix 两条结果
                upstream_dataset_ids, upstream_recording_ids = self._lineage_for_input(data_info, ica_info)
                save_meta = self._save_settings_metadata(context, data_info=data_info, index=index)
                artifact = study_output_store.save_file_from_writer(
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

    def _execute_ica_iclabel(self, context: NodeExecutionContext) -> NodeDispatchResult:
        """ICLabel 自动选成分：input(EEG) + ica_matrix → cleaned EEG。非交互（无人工审阅门）——
        引擎内自动分类 + 按类别/阈值定剔除集 + 重建，分类明细并入 preview 作溯源。"""
        node_id = str(context.node.get("id") or "")
        node_type = str(context.node.get("type") or "")
        input_data_infos = self._input_data_infos(context, "input")
        ica_infos = self._input_data_infos(context, "ica_matrix")
        if not input_data_infos or not ica_infos:
            issue = self._issue(
                code="PIPELINE_NODE_INPUT_MISSING",
                message="ICLabel auto-select requires both input EEG data_infos and ica_matrix data_infos.",
                node_id=node_id,
                node_type=node_type,
            )
            output = NodeOutput(node_id=node_id, node_type=node_type, outputs={"output": []}, data_infos=[])
            return NodeDispatchResult(output=output, status="failed", errors=[issue], output_ports=["output"])

        study_output_store = context.study_output_store or StudyOutputStore(context.db, context.study, context.execution, context.job)
        params = context.params if isinstance(context.params, dict) else {}
        # mark 模式数据未改：用区分后缀 + raw 类型，别把未清洗的输出冒充成 cleaned（溯源要诚实）
        action = str(params.get("action") or "apply").strip().lower()
        save_descriptor = "iclabel" if action == "apply" else "iclabel_marked"
        default_data_type = "ica_cleaned" if action == "apply" else "raw"
        output_data_infos: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for index, data_info in enumerate(input_data_infos):
            raw = None
            cleaned = None
            ica = None
            try:
                ica_info = self._matching_ica_info(data_info, ica_infos, index)
                raw = read_raw_from_data_info(data_info, preload=True)
                ica = read_ica_from_data_info(ica_info)
                cleaned, detail = run_iclabel(raw, ica, params)
                raw = None
                summary = summarize_raw(cleaned)
                if detail:
                    # 并入 summary，使 ICLabel 分类明细同时进 preview 与 mne_summary（溯源）
                    summary = {**summary, **detail}
                filename = self._derived_raw_filename(data_info, save_descriptor, index)
                upstream_dataset_ids, upstream_recording_ids = self._lineage_for_input(data_info, ica_info)
                save_meta = self._save_settings_metadata(context, data_info=data_info, index=index)
                artifact = study_output_store.save_file_from_writer(
                    filename,
                    lambda path, cleaned=cleaned: save_raw_fif(cleaned, path),
                    kind="derivative",
                    data_type=save_meta.get("data_type") or default_data_type,
                    metadata={
                        "node_id": node_id,
                        "node_type": node_type,
                        "params": params,
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
            finally:
                # 单 dataset 处理完显式释放 raw / cleaned / ica（~500MB 级），触发 GC 防累积 OOM
                raw = None  # noqa: F841
                cleaned = None  # noqa: F841
                ica = None  # noqa: F841
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

    def _execute_epoch_segment(self, context: NodeExecutionContext) -> NodeDispatchResult:
        return self._execute_epochs_output(context, run_epoch_segment, save_descriptor="epo")

    def _execute_epoch_merge(self, context: NodeExecutionContext) -> NodeDispatchResult:
        """Merge multiple epochs artifacts back into epochs, preserving per-epoch annotations."""
        node_id = str(context.node.get("id") or "")
        node_type = str(context.node.get("type") or "")
        input_data_infos = self._input_data_infos(context, "input")
        if not input_data_infos:
            issue = self._issue(
                code="PIPELINE_NODE_INPUT_MISSING",
                message="Epoch Merge node has no upstream epochs data_infos on input port.",
                node_id=node_id,
                node_type=node_type,
            )
            output = NodeOutput(node_id=node_id, node_type=node_type, outputs={"output": []}, data_infos=[])
            return NodeDispatchResult(output=output, status="failed", errors=[issue], output_ports=["output"])

        params = context.params if isinstance(context.params, dict) else {}
        merge_scope = str(params.get("merge_scope") or "source_recording").strip().lower()
        if merge_scope not in {"source_recording", "condition", "all_inputs"}:
            merge_scope = "source_recording"

        study_output_store = context.study_output_store or StudyOutputStore(context.db, context.study, context.execution, context.job)
        groups: dict[tuple[str, str, str], dict[str, Any]] = {}
        group_order: list[tuple[str, str, str]] = []
        errors: list[dict[str, Any]] = []
        output_data_infos: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []

        def ensure_group(
            key: tuple[str, str, str],
            *,
            label: str,
            condition: str | None,
            subject_key: str | None = None,
        ) -> dict[str, Any]:
            if key not in groups:
                groups[key] = {
                    "label": label,
                    "condition": condition,
                    "subject_key": subject_key,
                    "epochs": [],
                    "data_infos": [],
                    "conditions": [],
                    "context_annotation_count": 0,
                    "context_parent_conditions": [],
                }
                group_order.append(key)
            return groups[key]

        for index, data_info in enumerate(input_data_infos):
            try:
                epochs = read_epochs_from_data_info(data_info, preload=True)
                epochs, context_summary = self._rewrite_epoch_annotations_with_parent_context(epochs, data_info)
                if merge_scope == "condition":
                    event_id_map = dict(getattr(epochs, "event_id", {}) or {})
                    labels = self._epochs_condition_names(epochs, data_info) or sorted(event_id_map.keys()) or ["unknown"]
                    subject_key = self._condition_merge_subject_key(data_info, index)
                    for label in labels:
                        selector = label if label in event_id_map else str(data_info.get("child_condition") or "")
                        sub_epochs = epochs[selector] if selector in event_id_map else epochs
                        self._attach_condition_metadata_subset(epochs, sub_epochs, selector or label)
                        key = ("condition", subject_key, label)
                        group = ensure_group(key, label=label, condition=label, subject_key=subject_key)
                        group["epochs"].append(sub_epochs)
                        group["data_infos"].append(data_info)
                        group["conditions"].append(label)
                        group["context_annotation_count"] += int(context_summary.get("context_annotation_count") or 0)
                        group["context_parent_conditions"].extend(context_summary.get("context_parent_conditions") or [])
                else:
                    if merge_scope == "all_inputs":
                        key = ("all_inputs", "all", "all")
                        label = "all"
                    else:
                        label = self._condition_group_source_key(data_info, index)
                        key = ("source_recording", label, "")
                    group = ensure_group(key, label=label, condition=None)
                    group["epochs"].append(epochs)
                    group["data_infos"].append(data_info)
                    group["conditions"].extend(self._epochs_condition_names(epochs, data_info))
                    group["context_annotation_count"] += int(context_summary.get("context_annotation_count") or 0)
                    group["context_parent_conditions"].extend(context_summary.get("context_parent_conditions") or [])
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

        if not errors:
            for key in group_order:
                group = groups[key]
                data_infos = [item for item in group.get("data_infos") or [] if isinstance(item, dict)]
                representative = data_infos[0] if data_infos else {}
                condition = group.get("condition") if isinstance(group.get("condition"), str) else None
                conditions = self._unique_texts(group.get("conditions") or [])
                context_parent_conditions = self._unique_texts(group.get("context_parent_conditions") or [])
                merge_subject_key = str(group.get("subject_key") or "")
                merged = _concatenate_epochs(group["epochs"])
                merged, post_context_summary = self._rewrite_epoch_annotations_with_parent_context(merged, representative)
                context_annotation_count = int(group.get("context_annotation_count") or 0) + int(
                    post_context_summary.get("context_annotation_count") or 0
                )
                context_parent_conditions = self._unique_texts(
                    [
                        *context_parent_conditions,
                        *(post_context_summary.get("context_parent_conditions") or []),
                    ]
                )
                display_name_override = None
                if merge_scope == "all_inputs":
                    node_title = str(context.node.get("title") or "Epoch Merge").strip() or "Epoch Merge"
                    display_name_override = f"{node_title} · 全部输入合并"
                info = self._save_epochs_dataset(
                    context=context,
                    data_info=representative,
                    lineage_data_infos=data_infos,
                    epochs=merged,
                    study_output_store=study_output_store,
                    artifacts=artifacts,
                    save_descriptor="epmerge",
                    index=len(output_data_infos),
                    condition=condition,
                    node_id=node_id,
                    node_type=node_type,
                    display_name_override=display_name_override,
                    extra_summary={
                        "merge_scope": merge_scope,
                        "merge_group": str(group.get("label") or ""),
                        "merge_subject": merge_subject_key,
                        "merged_input_count": len(data_infos),
                        "merged_conditions": conditions,
                        "context_annotations": True,
                        "context_annotation_count": context_annotation_count,
                        "context_parent_conditions": context_parent_conditions,
                    },
                )
                info["merge_scope"] = merge_scope
                info["merge_group"] = str(group.get("label") or "")
                if merge_subject_key:
                    info["merge_subject"] = merge_subject_key
                info["merged_input_count"] = len(data_infos)
                info["merged_conditions"] = conditions
                output_data_infos.append(info)

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
                "merge_scope": merge_scope,
                "save_descriptor": "epmerge",
            },
        )
        return NodeDispatchResult(
            output=output,
            status="failed" if errors else "success",
            dataset_count=len(emitted_data_infos),
            output_ports=["output"],
            errors=errors,
        )

    def _execute_baseline(self, context: NodeExecutionContext) -> NodeDispatchResult:
        """Baseline 基线校正:epochs → epochs(逐输入 apply_baseline,复用 epochs 保存路径)。"""
        node_id = str(context.node.get("id") or "")
        node_type = str(context.node.get("type") or "")
        input_data_infos = self._input_data_infos(context, "input")
        if not input_data_infos:
            issue = self._issue(
                code="PIPELINE_NODE_INPUT_MISSING",
                message="Baseline node has no upstream epochs data_infos on input port.",
                node_id=node_id,
                node_type=node_type,
            )
            output = NodeOutput(node_id=node_id, node_type=node_type, outputs={"output": []}, data_infos=[])
            return NodeDispatchResult(output=output, status="failed", errors=[issue], output_ports=["output"])

        study_output_store = context.study_output_store or StudyOutputStore(context.db, context.study, context.execution, context.job)
        output_data_infos: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for index, data_info in enumerate(input_data_infos):
            try:
                epochs = read_epochs_from_data_info(data_info, preload=True)
                baselined = run_baseline(epochs, context.params)
                input_condition = data_info.get("condition") if isinstance(data_info.get("condition"), str) else None
                info = self._save_epochs_dataset(
                    context=context,
                    data_info=data_info,
                    epochs=baselined,
                    study_output_store=study_output_store,
                    artifacts=artifacts,
                    save_descriptor="bl",
                    index=index,
                    condition=input_condition,
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
                "save_descriptor": "bl",
            },
        )
        return NodeDispatchResult(
            output=output,
            status="failed" if errors else "success",
            dataset_count=len(emitted_data_infos),
            output_ports=["output"],
            errors=errors,
        )

    def _execute_reject_trials(self, context: NodeExecutionContext) -> NodeDispatchResult:
        """Reject Trials 自动试次剔除:epochs → epochs(逐输入剔坏 epoch,复用 epochs 保存路径)。

        与 Baseline 同构(epochs→epochs、保留上游 condition),区别:processor 返回 (cleaned, meta),
        meta(剔了几个 / 剔除率 / 判据)并进 summary 进 preview 作溯源。
        """
        node_id = str(context.node.get("id") or "")
        node_type = str(context.node.get("type") or "")
        input_data_infos = self._input_data_infos(context, "input")
        if not input_data_infos:
            issue = self._issue(
                code="PIPELINE_NODE_INPUT_MISSING",
                message="Reject Trials node has no upstream epochs data_infos on input port.",
                node_id=node_id,
                node_type=node_type,
            )
            output = NodeOutput(node_id=node_id, node_type=node_type, outputs={"output": []}, data_infos=[])
            return NodeDispatchResult(output=output, status="failed", errors=[issue], output_ports=["output"])

        study_output_store = context.study_output_store or StudyOutputStore(context.db, context.study, context.execution, context.job)
        output_data_infos: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        for index, data_info in enumerate(input_data_infos):
            try:
                epochs = read_epochs_from_data_info(data_info, preload=True)
                cleaned, reject_meta = run_reject_trials(epochs, context.params)
                input_condition = data_info.get("condition") if isinstance(data_info.get("condition"), str) else None

                # 剔除率体检:剔得太多(健康区通常 ≤5–10%)会让后续平均建立在很少试次上、SNR 崩塌。
                # 只剔光才 raise,这里对"剔很多但没剔光"补一条 warning(不拦,符合厚层放行)。
                drop_frac = float(reject_meta.get("drop_fraction") or 0.0)
                if drop_frac >= 0.3:
                    who = input_condition or self._source_dataset_id(data_info) or f"#{index}"
                    warnings.append(
                        self._issue(
                            code="PIPELINE_REJECT_HIGH_DROP_RATE",
                            message=(
                                f"试次剔除率偏高：{who} 剔掉 {reject_meta.get('n_dropped')}/"
                                f"{reject_meta.get('n_epochs_before')}（{drop_frac:.0%}）。健康区通常 ≤5–10%，"
                                "剔太多会让平均/统计建立在很少试次上、SNR 下降——请检查上游预处理或放宽阈值。"
                            ),
                            node_id=node_id,
                            node_type=node_type,
                            severity="warning",
                        )
                    )
                info = self._save_epochs_dataset(
                    context=context,
                    data_info=data_info,
                    epochs=cleaned,
                    study_output_store=study_output_store,
                    artifacts=artifacts,
                    save_descriptor="rej",
                    index=index,
                    condition=input_condition,
                    node_id=node_id,
                    node_type=node_type,
                    extra_summary=reject_meta,
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
                "save_descriptor": "rej",
            },
        )
        return NodeDispatchResult(
            output=output,
            status="failed" if errors else "success",
            dataset_count=len(emitted_data_infos),
            output_ports=["output"],
            errors=errors,
            warnings=warnings,
        )

    def _execute_erp_average(self, context: NodeExecutionContext) -> NodeDispatchResult:
        return self._execute_evoked_output(context, run_erp_average, save_descriptor="erp")

    def _execute_tfr_average(self, context: NodeExecutionContext) -> NodeDispatchResult:
        return self._execute_tfr_output(context, run_tfr, save_descriptor="tfr")

    def _execute_psd_average(self, context: NodeExecutionContext) -> NodeDispatchResult:
        return self._execute_psd_output(context, run_psd, save_descriptor="psd")

    def _execute_group_merge(self, context: NodeExecutionContext) -> NodeDispatchResult:
        """N-to-many: collect ERP/PSD/TFR/unit_stack inputs into condition-aware unit_stack artifacts."""
        node_id = str(context.node.get("id") or "")
        node_type = str(context.node.get("type") or "")
        input_data_infos = self._input_data_infos(context, "input")

        if not input_data_infos:
            issue = self._issue(
                code="PIPELINE_NODE_INPUT_MISSING",
                message="Group Merge node has no upstream artifacts on input.",
                node_id=node_id,
                node_type=node_type,
            )
            output = NodeOutput(node_id=node_id, node_type=node_type, outputs={"output": []}, data_infos=[])
            return NodeDispatchResult(output=output, status="failed", errors=[issue], output_ports=["output"])

        study_output_store = context.study_output_store or StudyOutputStore(
            context.db, context.study, context.execution, context.job
        )
        params = context.params if isinstance(context.params, dict) else {}

        try:
            results = run_group_merge(input_data_infos, params)
            upstream_ids = [
                str(di.get("artifact_id") or di.get("study_output_id") or "")
                for di in input_data_infos
                if di.get("artifact_id") or di.get("study_output_id")
            ]
            output_data_infos: list[dict[str, Any]] = []
            artifacts: list[dict[str, Any]] = []
            group_warnings: list[dict[str, Any]] = []

            for index, result in enumerate(results):
                summary = summarize_unit_stack(result)
                base_type = str(result.get("base_type") or "")
                subjects = list(result.get("unit_subjects") or [])
                condition = str(result.get("condition") or result.get("label") or "")
                label = str(result.get("label") or condition or "group")
                group_label = str(result.get("group_label") or "")

                coverage = result.get("coverage") if isinstance(result, dict) else None
                if isinstance(coverage, dict):
                    n_common = int(coverage.get("n_common") or 0)
                    n_union = int(coverage.get("n_union") or 0)
                    ratio = float(coverage.get("coverage_ratio") or 0.0)
                    if n_union and ratio < 0.5:
                        group_warnings.append(
                            self._issue(
                                code="PIPELINE_GROUP_LOW_CHANNEL_COVERAGE",
                                message=(
                                    f"Group Merge condition={condition or label!r} kept only "
                                    f"{n_common}/{n_union} shared channels after intersection "
                                    f"(coverage {ratio:.0%}). Check montage consistency."
                                ),
                                node_id=node_id,
                                node_type=node_type,
                                severity="warning",
                            )
                        )

                safe_label = "".join(
                    c if c.isalnum() or c in {"-", "_"} else "_" for c in label
                ).strip("_") or "group"
                filename = f"{safe_label}_unitstack.npz"

                save_meta = self._save_settings_metadata(
                    context,
                    data_info={"condition": condition or label, "task": group_label or condition or label},
                    index=index,
                    split_value=condition or label or None,
                )

                artifact = study_output_store.save_file_from_writer(
                    filename,
                    lambda path, r=result: save_unit_stack_npz(r, path),
                    kind="analysis_result",
                    data_type="unit_stack",
                    metadata={
                        "node_id": node_id,
                        "node_type": node_type,
                        "params": params,
                        "mne_summary": summary,
                        "upstream_dataset_ids": upstream_ids,
                        "upstream_recording_ids": [],
                        "base_type": base_type,
                        "n_units": result["n_units"],
                        "subjects": subjects,
                        "condition": condition or label,
                        "group_label": group_label,
                        "label": label,
                        **save_meta,
                    },
                    preview=summary,
                    source_dataset_id=None,
                    node_id=node_id,
                )
                artifacts.append(artifact)

                storage_path = str(artifact.get("storage_path") or "")
                artifact_path = self._artifact_path(context.study, artifact)
                fif_abs_path = str(artifact_path) if artifact_path else None

                group_data_info: dict[str, Any] = {
                    "data_type": "unit_stack",
                    "base_type": base_type,
                    "file_role": "pipeline_artifact",
                    "artifact_id": artifact.get("artifact_id"),
                    "study_output_id": artifact.get("study_output_id"),
                    "study_id": str(getattr(context.study, "id", "")),
                    "study_root": str(
                        getattr(context.study, "data_dir", getattr(context.study, "data_root", ""))
                    ),
                    "storage_path": storage_path,
                    "storage_uri": artifact.get("storage_uri"),
                    "logical_path": storage_path,
                    "artifact_storage_path": storage_path,
                    "artifact_storage_uri": artifact.get("storage_uri"),
                    "fif_path": storage_path,
                    "fif_abs_path": fif_abs_path,
                    "fif_exists": bool(fif_abs_path and Path(fif_abs_path).exists()),
                    "pipeline_execution_id": str(getattr(context.execution, "id", "")),
                    "job_id": str(getattr(context.job, "id", "")),
                    "file_size": artifact.get("file_size"),
                    "checksum": artifact.get("checksum"),
                    "sha256": artifact.get("sha256") or artifact.get("checksum"),
                    "content_hash": artifact.get("content_hash") or artifact.get("checksum"),
                    "condition": condition,
                    "group_label": group_label,
                    "label": label,
                    "n_units": result["n_units"],
                    "subjects": subjects,
                    **summary,
                }
                output_data_infos.append(group_data_info)

            output = NodeOutput(
                node_id=node_id,
                node_type=node_type,
                outputs={"output": output_data_infos},
                data_infos=output_data_infos,
                artifacts=artifacts,
                metadata={
                    "dataset_count": len(output_data_infos),
                    "conditions": [item.get("condition") for item in output_data_infos],
                    "base_type": output_data_infos[0].get("base_type") if output_data_infos else "",
                },
            )
            return NodeDispatchResult(
                output=output,
                status="success",
                dataset_count=len(output_data_infos),
                output_ports=["output"],
                warnings=group_warnings,
            )
        except Exception as exc:
            error = self._issue(
                code="PIPELINE_NODE_DATASET_FAILED",
                message=f"Group Merge failed: {exc}",
                node_id=node_id,
                node_type=node_type,
            )
            output = NodeOutput(node_id=node_id, node_type=node_type, outputs={"output": []}, data_infos=[])
            return NodeDispatchResult(output=output, status="failed", errors=[error], output_ports=["output"])

    def _execute_group_average(self, context: NodeExecutionContext) -> NodeDispatchResult:
        """1-to-1: 从 unit_stack 读取张量，沿 unit 轴求 mean ± SEM，回吐成原形态(evoked/psd/tfr)。"""
        node_id = str(context.node.get("id") or "")
        node_type = str(context.node.get("type") or "")
        input_data_infos = self._input_data_infos(context, "input")

        if not input_data_infos:
            issue = self._issue(
                code="PIPELINE_NODE_INPUT_MISSING",
                message="Grand Average 节点没有收到上游 unit_stack data_infos（input 端口为空）。",
                node_id=node_id,
                node_type=node_type,
            )
            output = NodeOutput(node_id=node_id, node_type=node_type, outputs={"output": []}, data_infos=[])
            return NodeDispatchResult(output=output, status="failed", errors=[issue], output_ports=["output"])

        study_output_store = context.study_output_store or StudyOutputStore(
            context.db, context.study, context.execution, context.job
        )
        output_data_infos: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        # grand average 回吐形态 → 落盘文件名后缀(saver 也会按形态兜底纠正)
        ext_by_type = {
            "psd_grandavg": "_grandavg_psd.npz",
            "evoked": "_grandavg-ave.fif",
            "tfr": "_grandavg-tfr.h5",
        }

        for index, data_info in enumerate(input_data_infos):
            try:
                result = run_group_average(data_info, context.params)
                out_type, writer, summary = build_grandavg_payload(result)

                label = str(result.get("label") or data_info.get("label") or "")
                safe_label = "".join(
                    c if c.isalnum() or c in {"-", "_"} else "_" for c in label
                ).strip("_") or "grandavg"
                filename = f"{safe_label}{ext_by_type.get(out_type, '_grandavg.npz')}"

                upstream_ids = [str(data_info.get("artifact_id") or data_info.get("study_output_id") or "")]

                # 命名：英文 base「Grand Average」+ 区分信息（条件 / unit 数），避免多个组平均都叫
                # 「Grand Average」撞名后只能靠后端补 (2) 区分（用户看不出谁是谁）。
                n_units = int(result.get("n_units") or 0)
                unit_word = {"subject": "subj", "trial": "trials", "run": "runs", "epoch": "epochs"}.get(
                    str(result.get("unit_kind") or "subject"), str(result.get("unit_kind") or "subject")
                )
                ga_name_parts = ["Grand Average"]
                if label.strip() and label.strip().lower() not in {"grandavg", "grand average", "grandaverage"}:
                    ga_name_parts.append(f"· {label.strip()}")
                if n_units > 0:
                    ga_name_parts.append(f"({n_units} {unit_word})")
                ga_display_name = " ".join(ga_name_parts)

                # 保存设置：Grand Average 是终端 leaf，拓扑驱动下 keep=True → 结果页可见。
                save_meta = self._save_settings_metadata(
                    context,
                    data_info={"condition": label, "task": label},
                    index=index,
                    split_value=label or None,
                    display_name_override=ga_display_name,
                )

                artifact = study_output_store.save_file_from_writer(
                    filename,
                    writer,
                    kind="analysis_result",
                    data_type=out_type,
                    metadata={
                        "node_id": node_id,
                        "node_type": node_type,
                        "params": context.params,
                        "mne_summary": summary,
                        "upstream_dataset_ids": upstream_ids,
                        "upstream_recording_ids": [],
                        "label": label,
                        "base_type": result.get("base_type"),
                        "n_units": result.get("n_units"),
                        **save_meta,
                    },
                    preview=summary,
                    source_dataset_id=None,
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
                        message=f"Grand Average [{index}] 失败：{exc}",
                        node_id=node_id,
                        node_type=node_type,
                    )
                )
                break

        emitted = [] if errors else output_data_infos
        output = NodeOutput(
            node_id=node_id,
            node_type=node_type,
            outputs={"output": emitted},
            data_infos=emitted,
            artifacts=artifacts,
            metadata={"dataset_count": len(output_data_infos)},
        )
        return NodeDispatchResult(
            output=output,
            status="failed" if errors else "success",
            dataset_count=len(emitted),
            output_ports=["output"],
            errors=errors,
        )

    def _execute_group_compare(self, context: NodeExecutionContext) -> NodeDispatchResult:
        """N-to-N(双口): 收 A/B 两组 unit_stack，按 condition 配对统计，输出 stat_map artifact。"""
        node_id = str(context.node.get("id") or "")
        node_type = str(context.node.get("type") or "")
        a_infos = self._input_data_infos(context, "a")
        b_infos = self._input_data_infos(context, "b")

        if not a_infos or not b_infos:
            missing = "a" if not a_infos else "b"
            issue = self._issue(
                code="PIPELINE_NODE_INPUT_MISSING",
                message=f"Group Compare 缺少上游输入（端口 {missing} 为空，需 A/B 各接一组 unit_stack）。",
                node_id=node_id,
                node_type=node_type,
            )
            output = NodeOutput(node_id=node_id, node_type=node_type, outputs={"output": []}, data_infos=[])
            return NodeDispatchResult(output=output, status="failed", errors=[issue], output_ports=["output"])

        study_output_store = context.study_output_store or StudyOutputStore(
            context.db, context.study, context.execution, context.job
        )
        params = context.params if isinstance(context.params, dict) else {}

        try:
            raw_results = run_group_compare(a_infos, b_infos, params)
            results = raw_results if isinstance(raw_results, list) else [raw_results]

            output_data_infos: list[dict[str, Any]] = []
            artifacts: list[dict[str, Any]] = []
            base_type = ""
            contrasts: list[str] = []
            for index, result in enumerate(results):
                summary = summarize_stat_map(result)
                contrast = str(result.get("contrast_label") or "")
                condition = str(result.get("condition") or "")
                base_type = str(result.get("base_type") or base_type or "")
                contrasts.append(contrast)

                label_for_file = condition or contrast or f"compare_{index + 1}"
                safe_label = "".join(
                    c if c.isalnum() or c in {"-", "_"} else "_" for c in label_for_file
                ).strip("_") or f"compare_{index + 1}"
                filename = f"{safe_label}_statmap.npz"

                upstream_ids = [
                    str(di.get("artifact_id") or di.get("study_output_id") or "")
                    for di in (a_infos + b_infos)
                    if di.get("artifact_id") or di.get("study_output_id")
                ]

                display_name = f"Group Compare · {condition or contrast}" if (condition or contrast) else None
                save_meta = self._save_settings_metadata(
                    context,
                    data_info={"condition": condition or contrast, "task": contrast},
                    index=index,
                    split_value=condition or contrast or None,
                    display_name_override=display_name,
                )

                artifact = study_output_store.save_file_from_writer(
                    filename,
                    lambda path, r=result: save_stat_map_npz(r, path),
                    kind="analysis_result",
                    data_type="stat_map",
                    metadata={
                        "node_id": node_id,
                        "node_type": node_type,
                        "params": params,
                        "mne_summary": summary,
                        "upstream_dataset_ids": upstream_ids,
                        "upstream_recording_ids": [],
                        "base_type": base_type,
                        "condition": condition,
                        "contrast_label": contrast,
                        **save_meta,
                    },
                    preview=summary,
                    source_dataset_id=None,
                    node_id=node_id,
                )
                artifacts.append(artifact)

                storage_path = str(artifact.get("storage_path") or "")
                artifact_path = self._artifact_path(context.study, artifact)
                fif_abs_path = str(artifact_path) if artifact_path else None

                stat_data_info: dict[str, Any] = {
                    "data_type": "stat_map",
                    "base_type": base_type,
                    "file_role": "pipeline_artifact",
                    "artifact_id": artifact.get("artifact_id"),
                    "study_output_id": artifact.get("study_output_id"),
                    "study_id": str(getattr(context.study, "id", "")),
                    "study_root": str(
                        getattr(context.study, "data_dir", getattr(context.study, "data_root", ""))
                    ),
                    "storage_path": storage_path,
                    "storage_uri": artifact.get("storage_uri"),
                    "logical_path": storage_path,
                    "artifact_storage_path": storage_path,
                    "artifact_storage_uri": artifact.get("storage_uri"),
                    "fif_path": storage_path,
                    "fif_abs_path": fif_abs_path,
                    "fif_exists": bool(fif_abs_path and Path(fif_abs_path).exists()),
                    "pipeline_execution_id": str(getattr(context.execution, "id", "")),
                    "job_id": str(getattr(context.job, "id", "")),
                    "file_size": artifact.get("file_size"),
                    "checksum": artifact.get("checksum"),
                    "sha256": artifact.get("sha256") or artifact.get("checksum"),
                    "content_hash": artifact.get("content_hash") or artifact.get("checksum"),
                    "condition": condition,
                    "contrast_label": contrast,
                    **summary,
                }
                output_data_infos.append(stat_data_info)

            output = NodeOutput(
                node_id=node_id,
                node_type=node_type,
                outputs={"output": output_data_infos},
                data_infos=output_data_infos,
                artifacts=artifacts,
                metadata={"dataset_count": len(output_data_infos), "base_type": base_type, "contrasts": contrasts},
            )
            return NodeDispatchResult(
                output=output,
                status="success",
                dataset_count=len(output_data_infos),
                output_ports=["output"],
            )
        except Exception as exc:
            error = self._issue(
                code="PIPELINE_NODE_DATASET_FAILED",
                message=f"Group Compare 失败：{exc}",
                node_id=node_id,
                node_type=node_type,
            )
            output = NodeOutput(node_id=node_id, node_type=node_type, outputs={"output": []}, data_infos=[])
            return NodeDispatchResult(output=output, status="failed", errors=[error], output_ports=["output"])

    def _execute_raw_preprocess(
        self,
        context: NodeExecutionContext,
        processor: Callable[[Any, dict[str, Any]], Any],
        *,
        save_descriptor: str,
        params_override: dict[str, Any] | None = None,
        params_for_input: Callable[[dict[str, Any], int], dict[str, Any]] | None = None,
    ) -> NodeDispatchResult:
        # 交互节点（如 artifact_mark）把人工 decision 合进 params 后用 params_override 传入；
        # 普通预处理节点不传，沿用 context.params——老调用行为零变化。
        params = params_override if params_override is not None else context.params
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

        study_output_store = context.study_output_store or StudyOutputStore(context.db, context.study, context.execution, context.job)
        output_data_infos: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for index, data_info in enumerate(input_data_infos):
            raw = None
            processed = None
            try:
                dataset_params = params_for_input(data_info, index) if params_for_input is not None else params
                raw = read_raw_from_data_info(data_info, preload=True)
                processed = processor(raw, dataset_params)
                # 预处理引擎可返回 (raw, extra_meta)：extra_meta 记录如坏道检测明细之类的溯源信息
                processor_meta: dict[str, Any] = {}
                if isinstance(processed, tuple):
                    processed, processor_meta = processed
                # processor 内部已经 raw.copy() 出新对象，原 raw 不再用，立刻释放避免重复 ~500MB
                raw = None
                summary = summarize_raw(processed)
                if processor_meta:
                    # 并入 summary，使溯源同时进 preview 与 mne_summary
                    summary = {**summary, **processor_meta}
                filename = self._derived_raw_filename(data_info, save_descriptor, index)
                upstream_dataset_ids, upstream_recording_ids = self._lineage_for_input(data_info)
                save_meta = self._save_settings_metadata(context, data_info=data_info, index=index)
                artifact = study_output_store.save_file_from_writer(
                    filename,
                    lambda path, processed=processed: save_raw_fif(processed, path),
                    kind="derivative",
                    data_type=save_meta.get("data_type") or self._normalise_raw_data_type(save_descriptor),
                    metadata={
                        "node_id": node_id,
                        "node_type": node_type,
                        "params": dataset_params,
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
        processor: Callable[[Any, dict[str, Any]], tuple[Any, dict[str, Any]]],
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

        study_output_store = context.study_output_store or StudyOutputStore(context.db, context.study, context.execution, context.job)
        output_data_infos: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        skipped_by_condition: dict[str, int] = {}  # condition 名 → 在几个数据集里切不出（循环后聚合成一条警告，避免多数据集刷屏）
        dropped_outside_parent_count = 0

        # split_by 决定输出 cardinality：none → 一进一出；condition → 一进 N 出
        split_mode = str(context.params.get("split_by") or "none").strip().lower()
        condition_split_groups: dict[tuple[str, str], dict[str, Any]] = {}
        condition_split_order: list[tuple[str, str]] = []

        for index, data_info in enumerate(input_data_infos):
            try:
                source_is_epochs = self._data_info_is_epochs(data_info)
                source = (
                    read_epochs_from_data_info(data_info, preload=True)
                    if source_is_epochs
                    else read_raw_from_data_info(data_info, preload=True)
                )
                epochs, diagnostics = processor(source, context.params)

                # 勾了但这份数据切不出的 condition → 累积，循环后按条件聚合成「一个节点一条」警告
                skipped = (
                    list(diagnostics.get("skipped_conditions") or [])
                    if isinstance(diagnostics, dict)
                    else []
                )
                for _name in skipped:
                    skipped_by_condition[_name] = skipped_by_condition.get(_name, 0) + 1

                if isinstance(diagnostics, dict):
                    try:
                        dropped_outside_parent_count += int(diagnostics.get("dropped_outside_parent") or 0)
                    except (TypeError, ValueError):
                        pass

                if split_mode in {"condition", "child_condition"}:
                    event_id_map = dict(getattr(epochs, "event_id", {}) or {})
                    source_key = self._condition_group_source_key(data_info, index)
                    for condition_label in sorted(event_id_map.keys()):
                        sub_epochs = epochs[condition_label]
                        self._attach_condition_metadata_subset(epochs, sub_epochs, condition_label)
                        if len(sub_epochs) == 0:
                            continue
                        split_items = self._split_epochs_by_condition_context(
                            sub_epochs,
                            data_info,
                            condition_label,
                            source_is_epochs=source_is_epochs,
                        )
                        for item in split_items:
                            item_epochs = item["epochs"]
                            if len(item_epochs) == 0:
                                continue
                            if split_mode == "child_condition" and source_is_epochs:
                                group_condition = str(item.get("condition") or condition_label)
                                group_key = (source_key, group_condition)
                                if group_key not in condition_split_groups:
                                    condition_split_groups[group_key] = {
                                        "condition": group_condition,
                                        "child_condition": item.get("child_condition"),
                                        "epochs": [],
                                        "data_infos": [],
                                        "parent_conditions": [],
                                    }
                                    condition_split_order.append(group_key)
                                group = condition_split_groups[group_key]
                                group["epochs"].append(item_epochs)
                                group["data_infos"].append(data_info)
                                group["parent_conditions"].extend(item.get("parent_conditions") or [])
                            else:
                                info = self._save_epochs_dataset(
                                    context=context,
                                    data_info=data_info,
                                    epochs=item_epochs,
                                    study_output_store=study_output_store,
                                    artifacts=artifacts,
                                    save_descriptor=save_descriptor,
                                    index=len(output_data_infos),
                                    condition=str(item.get("condition") or condition_label),
                                    node_id=node_id,
                                    node_type=node_type,
                                    parent_conditions=item.get("parent_conditions") or [],
                                    child_condition=item.get("child_condition"),
                                )
                                output_data_infos.append(info)
                else:
                    info = self._save_epochs_dataset(
                        context=context,
                        data_info=data_info,
                        epochs=epochs,
                        study_output_store=study_output_store,
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

        if not errors and condition_split_groups:
            for group_key in condition_split_order:
                group = condition_split_groups[group_key]
                grouped_epochs = _concatenate_epochs(group["epochs"])
                parent_conditions = self._unique_texts(group.get("parent_conditions") or [])
                data_infos = [item for item in group.get("data_infos") or [] if isinstance(item, dict)]
                representative = data_infos[0] if data_infos else {}
                condition_label = str(group.get("condition") or "")
                info = self._save_epochs_dataset(
                    context=context,
                    data_info=representative,
                    lineage_data_infos=data_infos,
                    epochs=grouped_epochs,
                    study_output_store=study_output_store,
                    artifacts=artifacts,
                    save_descriptor=save_descriptor,
                    index=len(output_data_infos),
                    condition=condition_label,
                    node_id=node_id,
                    node_type=node_type,
                    parent_conditions=parent_conditions,
                    child_condition=group.get("child_condition"),
                )
                output_data_infos.append(info)

        # 按条件聚合跳过情况，每个节点最多一条警告（其余条件正常切分；只 warning 不 block）
        if skipped_by_condition:
            n_total = len(input_data_infos)
            summary = "；".join(
                f"{name}（{cnt}/{n_total} 个数据集无匹配）"
                for name, cnt in skipped_by_condition.items()
            )
            warnings.append(
                self._issue(
                    code="PIPELINE_EPOCH_CONDITIONS_SKIPPED",
                    message=f"勾选的部分条件在数据中无匹配、已跳过（其余正常切分）：{summary}",
                    node_id=node_id,
                    node_type=node_type,
                    severity="warning",
                )
            )

        if dropped_outside_parent_count:
            warnings.append(
                self._issue(
                    code="PIPELINE_EPOCH_CHILD_WINDOW_OUTSIDE_PARENT",
                    message=(
                        f"有 {dropped_outside_parent_count} 个子事件因 tmin/tmax 窗口超出上游 Epoch 边界被跳过；"
                        "如需保留这些事件，请放宽上游 Epoch 窗口，或缩短当前 Epoch 的时间窗。"
                    ),
                    node_id=node_id,
                    node_type=node_type,
                    severity="warning",
                )
            )

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
            warnings=warnings,
        )

    @staticmethod
    def _clean_condition_text(value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None

    @staticmethod
    def _condition_leaf(value: Any) -> str | None:
        text = NodeDispatcher._clean_condition_text(value)
        if not text:
            return None
        if " / " not in text:
            return text
        return text.split(" / ")[-1].strip() or None

    @staticmethod
    def _condition_parent(value: Any) -> str | None:
        text = NodeDispatcher._clean_condition_text(value)
        if not text or " / " not in text:
            return None
        parent = " / ".join(part.strip() for part in text.split(" / ")[:-1] if part.strip())
        return parent or None

    @staticmethod
    def _contextual_annotation_label(parent_condition: Any, child_label: Any, parent_labels: set[str]) -> str:
        parent = NodeDispatcher._clean_condition_text(parent_condition)
        child = NodeDispatcher._clean_condition_text(child_label)
        if not parent or not child:
            return child or ""
        if " / " in child or child == parent or child in parent_labels:
            return child
        upper = child.upper()
        if upper.startswith("BAD_") or upper.startswith("EDGE"):
            return child
        return f"{parent} / {child}"

    def _rewrite_epoch_annotations_with_parent_context(
        self, epochs: Any, data_info: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        """Prefix inner annotations with the parent epoch condition.

        Epoch Merge does not create child epochs. It only makes the next Epoch
        node see context-aware events such as "block/A / sound/low" while the
        saved node params can still contain the leaf label "sound/low".
        """
        if not (callable(getattr(epochs, "get_annotations_per_epoch", None)) and hasattr(epochs, "events")):
            return epochs, {"context_annotation_count": 0, "context_parent_conditions": []}
        try:
            per_epoch = epochs.get_annotations_per_epoch()
        except Exception:
            return epochs, {"context_annotation_count": 0, "context_parent_conditions": []}
        if not per_epoch:
            return epochs, {"context_annotation_count": 0, "context_parent_conditions": []}

        event_id_map = dict(getattr(epochs, "event_id", {}) or {})
        parent_by_code = {int(code): str(name) for name, code in event_id_map.items()}
        parent_labels = {str(name).strip() for name in event_id_map.keys() if str(name).strip()}
        fallback_parent = self._clean_condition_text(data_info.get("condition_path") or data_info.get("condition"))
        if fallback_parent:
            parent_labels.add(fallback_parent)

        try:
            rewritten_epochs = epochs.copy()
            import mne  # noqa: PLC0415

            sfreq = float(rewritten_epochs.info["sfreq"])
            onsets: list[float] = []
            durations: list[float] = []
            descriptions: list[str] = []
            rewritten_count = 0
            used_parents: list[str] = []
            for event, annotations in zip(rewritten_epochs.events, per_epoch, strict=False):
                parent = parent_by_code.get(int(event[2])) or fallback_parent or ""
                if parent:
                    used_parents.append(parent)
                event_onset = float(event[0]) / sfreq
                for onset, duration, description in annotations:
                    old_desc = str(description)
                    new_desc = self._contextual_annotation_label(parent, old_desc, parent_labels)
                    if new_desc != old_desc:
                        rewritten_count += 1
                    onsets.append(event_onset + float(onset))
                    durations.append(float(duration))
                    descriptions.append(new_desc)
            if onsets:
                rewritten_epochs.set_annotations(
                    mne.Annotations(onset=onsets, duration=durations, description=descriptions)
                )
            return rewritten_epochs, {
                "context_annotation_count": rewritten_count,
                "context_parent_conditions": self._unique_texts(used_parents),
            }
        except Exception:
            return epochs, {"context_annotation_count": 0, "context_parent_conditions": []}

    @staticmethod
    def _condition_path_from_parts(parent_conditions: list[str], child_condition: str | None) -> str | None:
        parents = NodeDispatcher._unique_texts(parent_conditions)
        child = NodeDispatcher._clean_condition_text(child_condition)
        if parents and child:
            return f"{' + '.join(parents)} / {child}"
        if child:
            return child
        if parents:
            return " + ".join(parents)
        return None

    @staticmethod
    def _condition_metadata_rows(epochs: Any) -> list[dict[str, Any]]:
        metadata = getattr(epochs, "metadata", None)
        if metadata is not None:
            try:
                rows = metadata.to_dict("records")
                if isinstance(rows, list):
                    return [dict(row) for row in rows if isinstance(row, dict)]
            except Exception:
                pass
        rows = getattr(epochs, "_elys_condition_metadata", None)
        if isinstance(rows, list):
            return [dict(row) for row in rows if isinstance(row, dict)]
        return []

    @staticmethod
    def _set_condition_metadata_rows(epochs: Any, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        epochs._elys_condition_metadata = list(rows)  # type: ignore[attr-defined]
        try:
            import pandas as pd  # noqa: PLC0415

            epochs.metadata = pd.DataFrame(rows)
        except Exception:
            pass

    @staticmethod
    def _take_epochs_by_indices(epochs: Any, indices: list[int], rows: list[dict[str, Any]]) -> Any | None:
        if not indices:
            return None
        try:
            if len(indices) == len(epochs) and indices == list(range(len(epochs))):
                subset = epochs
            else:
                subset = epochs[indices]
        except Exception:
            try:
                import numpy as np  # noqa: PLC0415

                subset = epochs[np.asarray(indices, dtype=int)]
            except Exception:
                return None
        NodeDispatcher._set_condition_metadata_rows(subset, rows)
        return subset

    def _split_epochs_by_condition_context(
        self,
        epochs: Any,
        data_info: dict[str, Any],
        condition_label: str,
        *,
        source_is_epochs: bool,
    ) -> list[dict[str, Any]]:
        """Return save groups for one event label, preserving parent/child condition paths."""
        condition_label = str(condition_label or "").strip()
        parent_conditions = self._parent_conditions_for_epochs(epochs, data_info) if source_is_epochs else []

        if source_is_epochs:
            rows = self._condition_metadata_rows(epochs)
            if rows and len(rows) == len(epochs):
                grouped: dict[str, dict[str, Any]] = {}
                for index, row in enumerate(rows):
                    child = self._clean_condition_text(row.get("child_condition")) or condition_label
                    parent = self._clean_condition_text(row.get("parent_condition"))
                    row_path = (
                        self._clean_condition_text(row.get("condition_path"))
                        or self._condition_path_from_parts([parent] if parent else [], child)
                        or child
                    )
                    slot = grouped.setdefault(
                        row_path,
                        {
                            "indices": [],
                            "rows": [],
                            "parent_conditions": [],
                            "child_condition": child,
                        },
                    )
                    slot["indices"].append(index)
                    slot["rows"].append(row)
                    if parent:
                        slot["parent_conditions"].append(parent)
                split_items: list[dict[str, Any]] = []
                for path, slot in grouped.items():
                    subset = self._take_epochs_by_indices(epochs, slot["indices"], slot["rows"])
                    if subset is None:
                        continue
                    parents = self._unique_texts(slot.get("parent_conditions") or parent_conditions)
                    child = self._clean_condition_text(slot.get("child_condition")) or condition_label
                    split_items.append(
                        {
                            "condition": path,
                            "epochs": subset,
                            "parent_conditions": parents,
                            "child_condition": child,
                        }
                    )
                if split_items:
                    return split_items

        if parent_conditions:
            return [
                {
                    "condition": self._condition_path_from_parts(parent_conditions, condition_label) or condition_label,
                    "epochs": epochs,
                    "parent_conditions": parent_conditions,
                    "child_condition": condition_label,
                }
            ]
        return [
            {
                "condition": condition_label,
                "epochs": epochs,
                "parent_conditions": [],
                "child_condition": None,
            }
        ]

    def _save_epochs_dataset(
        self,
        *,
        context: NodeExecutionContext,
        data_info: dict[str, Any],
        lineage_data_infos: list[dict[str, Any]] | None = None,
        epochs: Any,
        study_output_store: StudyOutputStore,
        artifacts: list[dict[str, Any]],
        save_descriptor: str,
        index: int,
        condition: str | None,
        node_id: str,
        node_type: str,
        parent_conditions: list[str] | None = None,
        child_condition: str | None = None,
        extra_summary: dict[str, Any] | None = None,
        display_name_override: str | None = None,
    ) -> dict[str, Any]:
        """把一份 (子)epochs 写入磁盘 + 登记 study_output，返回 data_info。

        condition 非空时：文件名加 condition 后缀；apply_save_settings 用 split_value
        触发 dynamic_tags_when_split + name_template_default_split；输出 data_info 带 condition 字段。
        parent_conditions / child_condition 用于 Epochs→Epochs 的层级条件模型：主 condition 写完整
        condition_path，child_condition 只保留下游分析实际选择 MNE event_id 时使用的叶子事件名。
        extra_summary 非空时并进 summary（如 Reject Trials 的剔除溯源），同时进 preview 与 mne_summary。
        """
        summary = summarize_epochs(epochs)
        parent_conditions = self._unique_texts(parent_conditions or [])
        condition = str(condition or "").strip() or None
        child_condition = str(child_condition or "").strip() or None
        effective_condition = condition
        condition_hierarchy: dict[str, Any] = {}
        if parent_conditions and child_condition:
            condition_path = condition or self._condition_path_from_parts(parent_conditions, child_condition)
            effective_condition = condition_path
            condition_hierarchy = {
                "condition_model": "hierarchical",
                "parent_conditions": parent_conditions,
                "child_condition": child_condition,
                "condition_path": condition_path,
            }
            summary = {**summary, **condition_hierarchy}
        if extra_summary:
            summary = {**summary, **extra_summary}
        filename = self._derived_fif_filename(
            data_info, save_descriptor, index, kind="epochs", condition=effective_condition
        )
        lineage_inputs = lineage_data_infos if lineage_data_infos else [data_info]
        upstream_dataset_ids, upstream_recording_ids = self._lineage_for_input(*lineage_inputs)
        save_meta = self._save_settings_metadata(
            context,
            data_info=data_info,
            index=index,
            split_value=effective_condition,
            display_name_override=display_name_override,
        )
        artifact = study_output_store.save_file_from_writer(
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
                "condition": effective_condition,  # 让 _register_artifact 写入 derived.condition 列
                **condition_hierarchy,
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
        if effective_condition:
            info["condition"] = effective_condition
        info.update(condition_hierarchy)
        return info

    def _analysis_condition_plan(
        self,
        data_info: dict[str, Any],
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        input_condition = self._clean_condition_text(data_info.get("condition"))
        if input_condition:
            select_condition = self._clean_condition_text(data_info.get("child_condition")) or input_condition
            hierarchy = self._condition_hierarchy_from_data_info(
                data_info,
                output_condition=input_condition,
                select_condition=select_condition,
            )
            return [
                {
                    "select_condition": select_condition,
                    "output_condition": input_condition,
                    "hierarchy": hierarchy,
                }
            ]
        return [
            {"select_condition": cond, "output_condition": cond, "hierarchy": {}}
            for cond in _normalize_event_labels(params.get("condition"))
        ]

    def _condition_hierarchy_from_data_info(
        self,
        data_info: dict[str, Any],
        *,
        output_condition: str,
        select_condition: str,
    ) -> dict[str, Any]:
        parent_conditions: list[str] = []
        raw_parents = data_info.get("parent_conditions")
        if isinstance(raw_parents, (list, tuple, set)):
            parent_conditions = self._unique_texts(raw_parents)
        raw_parent = self._clean_condition_text(data_info.get("parent_condition"))
        if raw_parent:
            parent_conditions = self._unique_texts([*parent_conditions, raw_parent])
        child_condition = self._clean_condition_text(data_info.get("child_condition"))
        condition_path = self._clean_condition_text(data_info.get("condition_path"))
        if not parent_conditions and condition_path and child_condition:
            suffix = f" / {child_condition}"
            if condition_path.endswith(suffix):
                parent = condition_path[: -len(suffix)].strip()
                if parent:
                    parent_conditions = [parent]

        if not (parent_conditions or child_condition or condition_path):
            return {}
        child_condition = child_condition or select_condition
        condition_path = condition_path or output_condition
        return {
            "condition_model": data_info.get("condition_model") or "hierarchical",
            "parent_conditions": parent_conditions,
            "child_condition": child_condition,
            "condition_path": condition_path,
            "analysis_condition": select_condition,
        }

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

        study_output_store = context.study_output_store or StudyOutputStore(context.db, context.study, context.execution, context.job)
        output_data_infos: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        outer_break = False
        for index, data_info in enumerate(input_data_infos):
            if outer_break:
                break

            condition_plan = self._analysis_condition_plan(data_info, context.params)
            if not condition_plan:
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
            for item in condition_plan:
                select_condition = str(item.get("select_condition") or "")
                output_condition = str(item.get("output_condition") or select_condition)
                condition_hierarchy = item.get("hierarchy") if isinstance(item.get("hierarchy"), dict) else {}
                evoked = None
                try:
                    erp_params: dict[str, Any] = {**context.params, "condition": select_condition}
                    evoked = processor(epochs, erp_params)
                    summary = {
                        **summarize_evoked(evoked),
                        "condition": output_condition,
                        **condition_hierarchy,
                    }
                    # 为避免多 condition 同名，artifact filename 用 condition 区分
                    filename = self._derived_fif_filename(
                        data_info,
                        save_descriptor,
                        index * 1000 + artifact_index_in_data_info,
                        kind="evoked",
                        condition=output_condition,
                    )
                    upstream_dataset_ids, upstream_recording_ids = self._lineage_for_input(data_info)
                    save_meta = self._save_settings_metadata(
                        context,
                        data_info=data_info,
                        index=index,
                        split_value=output_condition,
                    )
                    artifact = study_output_store.save_file_from_writer(
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
                            "condition": output_condition,
                            "analysis_condition": select_condition,
                            **condition_hierarchy,
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
                    info["condition"] = output_condition
                    info["analysis_condition"] = select_condition
                    info.update(condition_hierarchy)
                    output_data_infos.append(info)
                    artifact_index_in_data_info += 1
                except Exception as exc:
                    errors.append(
                        self._issue(
                            code="PIPELINE_NODE_DATASET_FAILED",
                            message=f"Recording {self._source_dataset_id(data_info) or index} "
                                    f"condition={output_condition!r} failed in {node_type}: {exc}",
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

    def _execute_tfr_output(
        self,
        context: NodeExecutionContext,
        processor: Callable[[Any, dict[str, Any]], Any],
        *,
        save_descriptor: str,
    ) -> NodeDispatchResult:
        """TFR(时频)节点执行:每个 (input epochs, condition) → 一个 AverageTFR(-tfr.h5)。

        与 ERP/Evoked 同构(condition 展开逻辑一致),只是输出对象是时频功率谱、存成 HDF5。
        """
        node_id = str(context.node.get("id") or "")
        node_type = str(context.node.get("type") or "")
        input_data_infos = self._input_data_infos(context, "input")
        if not input_data_infos:
            issue = self._issue(
                code="PIPELINE_NODE_INPUT_MISSING",
                message="TFR node has no upstream epochs data_infos on input port.",
                node_id=node_id,
                node_type=node_type,
            )
            output = NodeOutput(node_id=node_id, node_type=node_type, outputs={"output": []}, data_infos=[])
            return NodeDispatchResult(output=output, status="failed", errors=[issue], output_ports=["output"])

        study_output_store = context.study_output_store or StudyOutputStore(context.db, context.study, context.execution, context.job)
        output_data_infos: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        outer_break = False
        for index, data_info in enumerate(input_data_infos):
            if outer_break:
                break

            condition_plan = self._analysis_condition_plan(data_info, context.params)
            if not condition_plan:
                errors.append(
                    self._issue(
                        code="PIPELINE_NODE_DATASET_FAILED",
                        message=f"Recording {self._source_dataset_id(data_info) or index} failed in {node_type}: "
                                "TFR.condition is required (上游 epochs 含多 condition,请在 TFR 节点选至少一个).",
                        node_id=node_id,
                        node_type=node_type,
                    )
                )
                break

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
            for item in condition_plan:
                select_condition = str(item.get("select_condition") or "")
                output_condition = str(item.get("output_condition") or select_condition)
                condition_hierarchy = item.get("hierarchy") if isinstance(item.get("hierarchy"), dict) else {}
                power = None
                try:
                    tfr_params: dict[str, Any] = {**context.params, "condition": select_condition}
                    power = processor(epochs, tfr_params)
                    summary = {
                        **summarize_tfr(power),
                        "condition": output_condition,
                        **condition_hierarchy,
                    }
                    # 把基线模式记进 preview,前端据此决定展示单位(dB / % / z)
                    summary["baseline_mode"] = str(tfr_params.get("baseline_mode", "logratio") or "logratio")
                    filename = self._derived_tfr_filename(
                        data_info,
                        save_descriptor,
                        index * 1000 + artifact_index_in_data_info,
                        condition=output_condition,
                    )
                    upstream_dataset_ids, upstream_recording_ids = self._lineage_for_input(data_info)
                    save_meta = self._save_settings_metadata(
                        context,
                        data_info=data_info,
                        index=index,
                        split_value=output_condition,
                    )
                    artifact = study_output_store.save_file_from_writer(
                        filename,
                        lambda path, tfr=power: save_tfr_h5(tfr, path),
                        kind="analysis_result",
                        data_type=save_meta.get("data_type") or "tfr",
                        metadata={
                            "node_id": node_id,
                            "node_type": node_type,
                            "params": tfr_params,
                            "input_data_info": self._compact_input_data_info(data_info),
                            "mne_summary": summary,
                            "upstream_dataset_ids": upstream_dataset_ids,
                            "upstream_recording_ids": upstream_recording_ids,
                            "condition": output_condition,
                            "analysis_condition": select_condition,
                            **condition_hierarchy,
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
                    info["condition"] = output_condition
                    info["analysis_condition"] = select_condition
                    info.update(condition_hierarchy)
                    output_data_infos.append(info)
                    artifact_index_in_data_info += 1
                except Exception as exc:
                    errors.append(
                        self._issue(
                            code="PIPELINE_NODE_DATASET_FAILED",
                            message=f"Recording {self._source_dataset_id(data_info) or index} "
                                    f"condition={output_condition!r} failed in {node_type}: {exc}",
                            node_id=node_id,
                            node_type=node_type,
                        )
                    )
                    outer_break = True
                    break
                finally:
                    power = None

            epochs = None  # noqa: F841 — 显式断引用让 GC 回收(epochs 可达百 MB)
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

    def _execute_psd_output(
        self,
        context: NodeExecutionContext,
        processor: Callable[[Any, dict[str, Any]], Any],
        *,
        save_descriptor: str,
    ) -> NodeDispatchResult:
        """PSD(功率谱)节点执行:每个 (input epochs, condition) → 一条平均功率谱(_psd.npz)。

        与 TFR 同构(condition 展开逻辑一致),只是输出对象是功率谱数组、存成 numpy .npz(无基线步)。
        """
        node_id = str(context.node.get("id") or "")
        node_type = str(context.node.get("type") or "")
        input_data_infos = self._input_data_infos(context, "input")
        if not input_data_infos:
            issue = self._issue(
                code="PIPELINE_NODE_INPUT_MISSING",
                message="PSD node has no upstream epochs data_infos on input port.",
                node_id=node_id,
                node_type=node_type,
            )
            output = NodeOutput(node_id=node_id, node_type=node_type, outputs={"output": []}, data_infos=[])
            return NodeDispatchResult(output=output, status="failed", errors=[issue], output_ports=["output"])

        study_output_store = context.study_output_store or StudyOutputStore(context.db, context.study, context.execution, context.job)
        output_data_infos: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        outer_break = False
        for index, data_info in enumerate(input_data_infos):
            if outer_break:
                break

            # 连续数据(Raw)输入:无 condition,整段算一条 PSD(静息态频域)。一进一出,不展开 condition。
            if not self._data_info_is_epochs(data_info):
                raw = None
                spectrum = None
                try:
                    raw = read_raw_from_data_info(data_info, preload=True)
                    spectrum = run_psd(raw, context.params)
                    summary = summarize_psd(spectrum)
                    filename = self._derived_psd_filename(data_info, save_descriptor, index, condition=None)
                    upstream_dataset_ids, upstream_recording_ids = self._lineage_for_input(data_info)
                    save_meta = self._save_settings_metadata(context, data_info=data_info, index=index, split_value=None)
                    artifact = study_output_store.save_file_from_writer(
                        filename,
                        lambda path, spec=spectrum: save_psd_npz(spec, path),
                        kind="analysis_result",
                        data_type=save_meta.get("data_type") or "psd",
                        metadata={
                            "node_id": node_id,
                            "node_type": node_type,
                            "params": context.params,
                            "input_data_info": self._compact_input_data_info(data_info),
                            "mne_summary": summary,
                            "upstream_dataset_ids": upstream_dataset_ids,
                            "upstream_recording_ids": upstream_recording_ids,
                            "condition": None,
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
                finally:
                    raw = None  # noqa: F841 — 显式断引用让 GC 回收(连续 raw 可达 ~500MB)
                    spectrum = None
                    import gc  # noqa: PLC0415
                    gc.collect()
                continue

            condition_plan = self._analysis_condition_plan(data_info, context.params)
            if not condition_plan:
                errors.append(
                    self._issue(
                        code="PIPELINE_NODE_DATASET_FAILED",
                        message=f"Recording {self._source_dataset_id(data_info) or index} failed in {node_type}: "
                                "PSD.condition is required (上游 epochs 含多 condition,请在 PSD 节点选至少一个).",
                        node_id=node_id,
                        node_type=node_type,
                    )
                )
                break

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
            for item in condition_plan:
                select_condition = str(item.get("select_condition") or "")
                output_condition = str(item.get("output_condition") or select_condition)
                condition_hierarchy = item.get("hierarchy") if isinstance(item.get("hierarchy"), dict) else {}
                spectrum = None
                try:
                    psd_params: dict[str, Any] = {**context.params, "condition": select_condition}
                    spectrum = processor(epochs, psd_params)
                    summary = {
                        **summarize_psd(spectrum),
                        "condition": output_condition,
                        **condition_hierarchy,
                    }
                    filename = self._derived_psd_filename(
                        data_info,
                        save_descriptor,
                        index * 1000 + artifact_index_in_data_info,
                        condition=output_condition,
                    )
                    upstream_dataset_ids, upstream_recording_ids = self._lineage_for_input(data_info)
                    save_meta = self._save_settings_metadata(
                        context,
                        data_info=data_info,
                        index=index,
                        split_value=output_condition,
                    )
                    artifact = study_output_store.save_file_from_writer(
                        filename,
                        lambda path, spec=spectrum: save_psd_npz(spec, path),
                        kind="analysis_result",
                        data_type=save_meta.get("data_type") or "psd",
                        metadata={
                            "node_id": node_id,
                            "node_type": node_type,
                            "params": psd_params,
                            "input_data_info": self._compact_input_data_info(data_info),
                            "mne_summary": summary,
                            "upstream_dataset_ids": upstream_dataset_ids,
                            "upstream_recording_ids": upstream_recording_ids,
                            "condition": output_condition,
                            "analysis_condition": select_condition,
                            **condition_hierarchy,
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
                    info["condition"] = output_condition
                    info["analysis_condition"] = select_condition
                    info.update(condition_hierarchy)
                    output_data_infos.append(info)
                    artifact_index_in_data_info += 1
                except Exception as exc:
                    errors.append(
                        self._issue(
                            code="PIPELINE_NODE_DATASET_FAILED",
                            message=f"Recording {self._source_dataset_id(data_info) or index} "
                                    f"condition={output_condition!r} failed in {node_type}: {exc}",
                            node_id=node_id,
                            node_type=node_type,
                        )
                    )
                    outer_break = True
                    break
                finally:
                    spectrum = None

            epochs = None  # noqa: F841 — 显式断引用让 GC 回收(epochs 可达百 MB)
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
    def _data_info_is_epochs(data_info: dict[str, Any]) -> bool:
        """判断一份 data_info 指向 Epochs 还是连续 Raw(供 PSD 等同时接受两种输入的节点分流)。

        判定优先级:
          - data_type == "epochs" → Epochs
          - data_type ∈ {raw, filtered_raw, ica_cleaned} → Raw
          - 兜底看文件名后缀(-epo.fif = Epochs),否则按连续 Raw 处理。
        """
        data_type = str(data_info.get("data_type") or "").strip().lower()
        if data_type == "epochs":
            return True
        if data_type in {"raw", "filtered_raw", "ica_cleaned"}:
            return False
        for key in ("fif_path", "storage_path", "artifact_storage_path", "source_path"):
            value = data_info.get(key)
            if value and str(value).lower().endswith(("-epo.fif", "-epo.fif.gz")):
                return True
        return False

    @staticmethod
    def _unique_texts(values: Any) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for value in values or []:
            text = str(value or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            out.append(text)
        return out

    @staticmethod
    def _metadata_column_values(epochs: Any, column: str) -> list[str]:
        metadata = getattr(epochs, "metadata", None)
        if metadata is not None:
            try:
                if column in metadata:
                    values = metadata[column].dropna().tolist()
                    return NodeDispatcher._unique_texts(values)
            except Exception:
                pass
        elys_metadata = getattr(epochs, "_elys_condition_metadata", None)
        if isinstance(elys_metadata, list):
            return NodeDispatcher._unique_texts(
                row.get(column) for row in elys_metadata if isinstance(row, dict)
            )
        return []

    @staticmethod
    def _attach_condition_metadata_subset(source_epochs: Any, target_epochs: Any, condition_label: str) -> None:
        rows = getattr(source_epochs, "_elys_condition_metadata", None)
        if not isinstance(rows, list):
            return
        label = str(condition_label or "").strip()
        leaf = NodeDispatcher._condition_leaf(label)
        subset = [
            row
            for row in rows
            if isinstance(row, dict)
            and (
                str(row.get("condition_path") or "").strip() == label
                or str(row.get("child_condition") or "").strip() == label
                or (leaf and str(row.get("child_condition") or "").strip() == leaf)
            )
        ]
        if subset:
            target_epochs._elys_condition_metadata = subset  # type: ignore[attr-defined]

    @staticmethod
    def _parent_conditions_for_epochs(epochs: Any, data_info: dict[str, Any]) -> list[str]:
        from_metadata = NodeDispatcher._metadata_column_values(epochs, "parent_condition")
        if from_metadata:
            return from_metadata
        raw_list = data_info.get("parent_conditions")
        if isinstance(raw_list, (list, tuple, set)):
            return NodeDispatcher._unique_texts(raw_list)
        raw = data_info.get("parent_condition")
        if isinstance(raw, str) and raw.strip():
            return [raw.strip()]
        raw_path = data_info.get("condition_path") or data_info.get("condition")
        child = data_info.get("child_condition")
        if isinstance(raw_path, str) and isinstance(child, str):
            suffix = f" / {child.strip()}"
            if raw_path.strip().endswith(suffix):
                parent = raw_path.strip()[: -len(suffix)].strip()
                if parent:
                    return [parent]
        raw = data_info.get("condition")
        if isinstance(raw, str) and raw.strip():
            return [raw.strip()]
        return []

    @staticmethod
    def _epochs_condition_names(epochs: Any, data_info: dict[str, Any]) -> list[str]:
        raw = data_info.get("condition_path") or data_info.get("condition")
        if isinstance(raw, str) and raw.strip():
            return [raw.strip()]
        raw_list = data_info.get("conditions") or data_info.get("merged_conditions")
        if isinstance(raw_list, (list, tuple, set)):
            return NodeDispatcher._unique_texts(raw_list)
        event_id_map = dict(getattr(epochs, "event_id", {}) or {})
        return NodeDispatcher._unique_texts(event_id_map.keys())

    @staticmethod
    def _condition_group_source_key(data_info: dict[str, Any], index: int) -> str:
        for key in (
            NodeDispatcher._source_dataset_id(data_info),
            data_info.get("source_dataset_file_id"),
            data_info.get("bids_subject_id"),
            data_info.get("subject"),
            data_info.get("subject_id"),
            data_info.get("dataset_id"),
        ):
            text = str(key or "").strip()
            if text:
                return text
        return f"input-{index}"

    @staticmethod
    def _condition_merge_subject_key(data_info: dict[str, Any], index: int) -> str:
        """Group condition-merge outputs within a subject, not across subjects."""
        for key in (
            data_info.get("bids_subject_id"),
            data_info.get("subject"),
            data_info.get("subject_id"),
        ):
            text = str(key or "").strip()
            if text:
                return text
        return NodeDispatcher._condition_group_source_key(data_info, index)

    @staticmethod
    def _lineage_for_input(*data_infos: dict[str, Any]) -> tuple[list[str], list[str]]:
        """从一个或多个上游 data_info 推导 (upstream_dataset_ids, upstream_recording_ids).

        - upstream_dataset_ids: 直接上游的 study_output id（来自上游 data_info["artifact_id"]）。
          LoadData 不写 study_output，所以 LoadData 输出的 data_info 没有 artifact_id，对应空列表。
        - upstream_recording_ids: 最终回溯到的原始 recording id（来自 source_dataset_id / dataset_id）。
        """
        dataset_ids: list[str] = []
        recording_ids: list[str] = []
        dataset_seen: set[str] = set()
        recording_seen: set[str] = set()
        for data_info in data_infos:
            if not isinstance(data_info, dict):
                continue
            upstream = data_info.get("artifact_id") or data_info.get("study_output_id")
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
        display_name_override: str | None = None,
    ) -> dict[str, Any]:
        """调 apply_save_settings 并返回可直接 merge 进 metadata 的 dict。

        返回字段:
          display_name / tags / keep / cache_eligible / retention_expires_at /
          step_label / data_type

        dispatcher 把它 update 到传给 study_output_store.save_file_from_writer 的
        metadata，让 _register_study_output 接管写入 study_outputs。
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
            display_name_override=display_name_override,
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
    def _derived_psd_filename(
        data_info: dict[str, Any],
        save_descriptor: str,
        index: int,
        *,
        condition: str | None = None,
    ) -> str:
        """生成 PSD 派生文件名,以 _psd.npz 结尾。

        例:sub-01_rest_target_psd.npz(含 condition) / sub-01_rest_psd.npz(不含)。
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
        for suffix in (".fif.gz", ".fif", "_psd.npz", ".npz", "-tfr.h5", ".h5", ".hdf5"):
            if lower_name.endswith(suffix):
                name = name[: -len(suffix)]
                lower_name = name.lower()
                break
        for suffix in ("-epo", "_epo", "-raw", "_raw", "-ave"):
            if lower_name.endswith(suffix):
                name = name[: -len(suffix)]
                break
        safe_base = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in name).strip("_")
        if not safe_base:
            safe_base = f"dataset-{index + 1}"
        if condition:
            safe_condition = "".join(
                char if char.isalnum() or char in {"-", "_"} else "_" for char in str(condition)
            ).strip("_")
            if safe_condition:
                return f"{safe_base}_{safe_condition}_psd.npz"
        return f"{safe_base}_psd.npz"

    @staticmethod
    def _derived_tfr_filename(
        data_info: dict[str, Any],
        save_descriptor: str,
        index: int,
        *,
        condition: str | None = None,
    ) -> str:
        """生成 TFR 派生文件名,必须以 -tfr.h5 结尾(MNE 硬约束)。

        例:sub-01_rest_LeftMI-tfr.h5(含 condition) / sub-01_rest-tfr.h5(不含)。
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
        for suffix in (".fif.gz", ".fif", "-tfr.h5", ".h5", ".hdf5"):
            if lower_name.endswith(suffix):
                name = name[: -len(suffix)]
                lower_name = name.lower()
                break
        for suffix in ("-epo", "_epo", "-raw", "_raw", "-ave"):
            if lower_name.endswith(suffix):
                name = name[: -len(suffix)]
                break
        safe_base = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in name).strip("_")
        if not safe_base:
            safe_base = f"dataset-{index + 1}"
        if save_descriptor and not safe_base.lower().endswith(save_descriptor.lower()):
            safe_base = f"{safe_base}_{save_descriptor}"
        if condition:
            safe_condition = "".join(
                char if char.isalnum() or char in {"-", "_"} else "_" for char in str(condition)
            ).strip("_")
            if safe_condition:
                return f"{safe_base}_{safe_condition}-tfr.h5"
        return f"{safe_base}-tfr.h5"

    @staticmethod
    def _compact_input_data_info(data_info: dict[str, Any]) -> dict[str, Any]:
        keys = (
            "dataset_id",
            "source_dataset_id",
            "study_id",
            "subject_id",
            "subject",
            "bids_subject_id",
            "session",
            "task",
            "run",
            "sfreq",
            "n_times",
            "duration_seconds",
            "n_channels",
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
            "condition",
            "condition_model",
            "parent_condition",
            "parent_conditions",
            "child_condition",
            "condition_path",
            "analysis_condition",
            # 不收 *_abs_path / study_root 等服务器绝对路径：紧凑表示会进交互 payload、preview_json.source_ref、
            # 产物 metadata 等会回前端的位置（泄漏服务器路径）。回溯载入源 raw（ica_inspect._load_source_raw）
            # 走 storage_uri/fif_path 即可，从不需要绝对路径；引擎读 ICA 用的是 _ica_data_info 的独立 data_info。
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
        # ICA component indexes belong to the current ICA matrix. Static node
        # params may be stale after Compute ICA changes, so only the decision
        # submitted for this waiting job may resume Apply ICA.
        output_json = getattr(context.job, "output_json", None) or {}
        interaction = NodeDispatcher._interaction_from_output(output_json)
        decision = interaction.get("decision") if isinstance(interaction, dict) else None
        if isinstance(decision, dict):
            excluded = parse_excluded_components(decision.get("excluded_components", []))
            excluded_by_dataset = NodeDispatcher._normalize_ica_excluded_by_dataset(
                decision.get("excluded_components_by_dataset")
            )
            return {
                **decision,
                "excluded_components": excluded,
                "excluded_components_by_dataset": excluded_by_dataset,
                "decision_version": int(decision.get("decision_version") or context.params.get("decision_version") or 1),
            }
        return None

    @staticmethod
    def _normalize_ica_excluded_by_dataset(value: Any) -> dict[str, list[int]]:
        if not isinstance(value, dict):
            return {}
        normalized: dict[str, list[int]] = {}
        for key, items in value.items():
            key_text = str(key or "").strip()
            if not key_text:
                continue
            normalized[key_text] = parse_excluded_components(items)
        return normalized

    @staticmethod
    def _ica_excluded_for_dataset(
        decision: dict[str, Any],
        data_info: dict[str, Any],
        ica_info: dict[str, Any],
        index: int,
    ) -> list[int]:
        by_dataset = NodeDispatcher._normalize_ica_excluded_by_dataset(
            decision.get("excluded_components_by_dataset")
        )
        if by_dataset:
            candidate_keys = [
                ica_info.get("artifact_id"),
                ica_info.get("analysis_result_id"),
                data_info.get("artifact_id"),
                data_info.get("dataset_id"),
                NodeDispatcher._source_dataset_id(data_info),
                NodeDispatcher._source_dataset_id(ica_info),
                index,
            ]
            for key in candidate_keys:
                key_text = str(key or "").strip()
                if key_text and key_text in by_dataset:
                    return by_dataset[key_text]
        return parse_excluded_components(decision.get("excluded_components", []))

    @staticmethod
    def _normalize_artifact_segments_by_dataset(value: Any) -> dict[str, list[dict[str, Any]]]:
        if not isinstance(value, dict):
            return {}
        normalized: dict[str, list[dict[str, Any]]] = {}
        for key, items in value.items():
            if key is None:
                continue
            key_text = str(key).strip()
            if key_text:
                normalized[key_text] = parse_bad_segments(items)
        return normalized

    @staticmethod
    def _normalize_artifact_channels_by_dataset(value: Any) -> dict[str, list[str]]:
        if not isinstance(value, dict):
            return {}
        normalized: dict[str, list[str]] = {}
        for key, items in value.items():
            if key is None:
                continue
            key_text = str(key).strip()
            if key_text:
                normalized[key_text] = parse_bad_channels(items)
        return normalized

    @staticmethod
    def _artifact_dataset_key(data_info: dict[str, Any], index: int) -> str:
        for key in (
            data_info.get("artifact_id"),
            data_info.get("analysis_result_id"),
            data_info.get("dataset_id"),
            NodeDispatcher._source_dataset_id(data_info),
        ):
            if key is not None and str(key).strip():
                return str(key).strip()
        return str(index)

    @staticmethod
    def _artifact_marks_for_dataset(
        decision: dict[str, Any],
        data_info: dict[str, Any],
        index: int,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        segments_by_dataset = NodeDispatcher._normalize_artifact_segments_by_dataset(
            decision.get("bad_segments_by_dataset")
        )
        channels_by_dataset = NodeDispatcher._normalize_artifact_channels_by_dataset(
            decision.get("bad_channels_by_dataset")
        )
        candidate_keys = [
            data_info.get("artifact_id"),
            data_info.get("analysis_result_id"),
            data_info.get("dataset_id"),
            NodeDispatcher._source_dataset_id(data_info),
            index,
        ]

        segments: list[dict[str, Any]] | None = None
        channels: list[str] | None = None
        for key in candidate_keys:
            if key is None:
                continue
            key_text = str(key).strip()
            if not key_text:
                continue
            if segments is None and key_text in segments_by_dataset:
                segments = segments_by_dataset[key_text]
            if channels is None and key_text in channels_by_dataset:
                channels = channels_by_dataset[key_text]
        if segments is None:
            segments = parse_bad_segments(decision.get("bad_segments", []))
        if channels is None:
            channels = parse_bad_channels(decision.get("bad_channels", []))
        return segments, channels

    @staticmethod
    def _artifact_decision(context: NodeExecutionContext) -> dict[str, Any] | None:
        """读人工去伪迹决策：优先取 job interaction 里已提交的 decision，
        否则回退节点 params（允许完全在图上写死坏段/坏道直接跑，与 ICA 同口径）。无标记则返回 None → 等待。"""
        params = context.params if isinstance(context.params, dict) else {}
        output_json = getattr(context.job, "output_json", None) or {}
        interaction = NodeDispatcher._interaction_from_output(output_json)
        decision = interaction.get("decision") if isinstance(interaction, dict) else None
        if isinstance(decision, dict) and (
            decision.get("type") == "artifact_marking"
            or "bad_segments" in decision
            or "bad_channels" in decision
            or "bad_segments_by_dataset" in decision
            or "bad_channels_by_dataset" in decision
        ):
            return {
                "bad_segments": parse_bad_segments(decision.get("bad_segments", [])),
                "bad_channels": parse_bad_channels(decision.get("bad_channels", [])),
                "bad_segments_by_dataset": NodeDispatcher._normalize_artifact_segments_by_dataset(
                    decision.get("bad_segments_by_dataset")
                ),
                "bad_channels_by_dataset": NodeDispatcher._normalize_artifact_channels_by_dataset(
                    decision.get("bad_channels_by_dataset")
                ),
                "channel_action": decision.get("channel_action") or params.get("channel_action") or "mark",
                "decision_version": int(decision.get("decision_version") or params.get("decision_version") or 1),
            }

        raw_segments = params.get("bad_segments")
        raw_channels = params.get("bad_channels")
        raw_segments_by_dataset = NodeDispatcher._normalize_artifact_segments_by_dataset(
            params.get("bad_segments_by_dataset")
        )
        raw_channels_by_dataset = NodeDispatcher._normalize_artifact_channels_by_dataset(
            params.get("bad_channels_by_dataset")
        )
        if (
            raw_segments not in (None, "", [])
            or raw_channels not in (None, "", [])
            or raw_segments_by_dataset
            or raw_channels_by_dataset
        ):
            return {
                "bad_segments": parse_bad_segments(raw_segments or []),
                "bad_channels": parse_bad_channels(raw_channels or []),
                "bad_segments_by_dataset": raw_segments_by_dataset,
                "bad_channels_by_dataset": raw_channels_by_dataset,
                "channel_action": params.get("channel_action") or "mark",
                "decision_version": int(params.get("decision_version") or 1),
                "source": "node_params",
            }
        return None

    @staticmethod
    def _artifact_interaction_payload(
        context: NodeExecutionContext,
        input_data_infos: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """伪迹审核 waiting payload：把节点 raw 输入的标识喂给前端（页面据此调观察窗端点画波形），
        并回填节点上已有的草稿标记作初始态。具体波形不进 payload——按需走窗口端点取。"""
        params = context.params if isinstance(context.params, dict) else {}
        segments_by_dataset = NodeDispatcher._normalize_artifact_segments_by_dataset(
            params.get("bad_segments_by_dataset")
        )
        channels_by_dataset = NodeDispatcher._normalize_artifact_channels_by_dataset(
            params.get("bad_channels_by_dataset")
        )
        has_dataset_initial = bool(segments_by_dataset or channels_by_dataset)
        global_segments = parse_bad_segments(params.get("bad_segments") or [])
        global_channels = parse_bad_channels(params.get("bad_channels") or [])
        datasets: list[dict[str, Any]] = []
        initial_by_dataset: dict[str, dict[str, Any]] = {}
        for index, data_info in enumerate(input_data_infos):
            key = NodeDispatcher._artifact_dataset_key(data_info, index)
            segments, channels = NodeDispatcher._artifact_marks_for_dataset(
                {
                    "bad_segments": [] if has_dataset_initial else global_segments,
                    "bad_channels": [] if has_dataset_initial else global_channels,
                    "bad_segments_by_dataset": segments_by_dataset,
                    "bad_channels_by_dataset": channels_by_dataset,
                },
                data_info,
                index,
            )
            initial = {"bad_segments": segments, "bad_channels": channels}
            initial_by_dataset[key] = initial
            datasets.append(
                {
                    "key": key,
                    "dataset_id": data_info.get("dataset_id"),
                    "source_dataset_id": NodeDispatcher._source_dataset_id(data_info),
                    # 上游 raw 的 StudyOutput id：前端据此调 input-timeseries 画波形让用户框选
                    "output_id": data_info.get("artifact_id"),
                    "data_info": NodeDispatcher._compact_input_data_info(data_info),
                    "initial": initial,
                }
            )
        return {
            "type": "artifact_marking",
            "status": "waiting_user_input",
            "decision_version": int(params.get("decision_version") or 1),
            "preview_json": {
                "datasets": datasets,
                "channel_action": params.get("channel_action") or "mark",
                "initial": {
                    "bad_segments": global_segments,
                    "bad_channels": global_channels,
                },
                "initial_by_dataset": initial_by_dataset,
            },
        }

    @staticmethod
    def _event_manager_decision(context: NodeExecutionContext) -> dict[str, Any] | None:
        """读事件梳理决策：优先取 job interaction 里已提交的 decision；否则回退节点 params
        （允许在图上写死 group_operations 声明式直接跑，与 Event Remap 同口径）。无任何编辑则返回 None → 等待。"""
        output_json = getattr(context.job, "output_json", None) or {}
        interaction = NodeDispatcher._interaction_from_output(output_json)
        decision = interaction.get("decision") if isinstance(interaction, dict) else None
        if isinstance(decision, dict) and (
            decision.get("type") == "event_editing"
            or "events" in decision
            or "group_operations" in decision
        ):
            return {
                "events": decision.get("events"),
                "group_operations": decision.get("group_operations") or [],
                "operations": decision.get("operations") or [],
                "decision_version": int(
                    decision.get("decision_version") or context.params.get("decision_version") or 1
                ),
            }

        raw_ops = context.params.get("group_operations")
        if raw_ops not in (None, "", []):
            return {
                "events": None,
                "group_operations": raw_ops,
                "operations": [],
                "decision_version": int(context.params.get("decision_version") or 1),
                "source": "node_params",
            }
        return None

    @staticmethod
    def _event_manager_interaction_payload(
        context: NodeExecutionContext,
        input_data_infos: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """事件编辑 waiting payload：把每个输入数据集「当前全部事件」（读上游 fif 注解，非破坏、不预载样本）
        全量喂给前端作初始态；波形按需走 input-timeseries 端点。BAD_ 注解单列作只读上下文层。"""
        datasets = []
        for data_info in input_data_infos:
            events, bad_segments = NodeDispatcher._read_managed_events(data_info)
            datasets.append(
                {
                    "dataset_id": data_info.get("dataset_id"),
                    "source_dataset_id": NodeDispatcher._source_dataset_id(data_info),
                    # 上游 raw 的 StudyOutput id：前端据此调 input-timeseries 画波形叠 marker
                    "output_id": data_info.get("artifact_id"),
                    "data_info": NodeDispatcher._compact_input_data_info(data_info),
                    "events": events,
                    "bad_segments": bad_segments,
                }
            )
        return {
            "type": "event_editing",
            "status": "waiting_user_input",
            "decision_version": int(context.params.get("decision_version") or 1),
            "preview_json": {"datasets": datasets},
        }

    @staticmethod
    def _read_managed_events(data_info: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """读上游 raw 的注解，拆成（managed=非 BAD 事件, bad=BAD_ 注解）。preload=False 只读头部注解、不载样本。
        失败（文件缺失等）→ 返回空，前端给空编辑器，不阻断开页。"""
        from app.engine.preprocess.event_manager import BAD_ANNOTATION_PREFIX  # noqa: PLC0415

        try:
            raw = read_raw_from_data_info(data_info, preload=False)
        except Exception:
            return [], []
        annotations = getattr(raw, "annotations", None)
        events: list[dict[str, Any]] = []
        bads: list[dict[str, Any]] = []
        if annotations is None or len(annotations) == 0:
            return events, bads
        for onset, duration, desc in zip(
            annotations.onset, annotations.duration, annotations.description
        ):
            rec = {
                "onset": round(float(onset), 4),
                "duration": round(float(duration), 4),
                "description": str(desc),
            }
            if rec["description"].startswith(BAD_ANNOTATION_PREFIX):
                bads.append(rec)
            else:
                events.append(rec)
        events.sort(key=lambda e: e["onset"])
        return events, bads

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
                    "data_info": NodeDispatcher._compact_input_data_info(data_info),
                    "ica_info": NodeDispatcher._compact_input_data_info(ica_info),
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
    def _issue(
        *, code: str, message: str, node_id: str, node_type: str, severity: str = "error"
    ) -> dict[str, Any]:
        return PipelineValidationIssue(
            code=code,
            message=message,
            node_id=node_id,
            node_type=node_type,
            severity=severity,
        ).model_dump(mode="json")
