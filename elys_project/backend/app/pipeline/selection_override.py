"""
Purpose: Apply per-execution LoadData selection overrides without mutating Pipeline definitions.
Related: app/routers/pipelines.py, app/pipeline/executor.py, docs_v2/5-30.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


LOAD_DATA_OVERRIDE_KEYS = {"selection_mode", "dataset_filter", "dataset_ids"}


def normalize_selection_override(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for node_id, raw_override in value.items():
        if not isinstance(raw_override, dict):
            continue
        override = {key: deepcopy(raw_override[key]) for key in LOAD_DATA_OVERRIDE_KEYS if key in raw_override}
        if override:
            normalized[str(node_id)] = override
    return normalized


def selection_override_from_execution(execution: Any) -> dict[str, dict[str, Any]]:
    result_json = getattr(execution, "result_json", None)
    if not isinstance(result_json, dict):
        return {}
    return normalize_selection_override(result_json.get("selection_override"))


def load_data_override_for_node(
    selection_override: dict[str, dict[str, Any]],
    node_id: str,
) -> dict[str, Any]:
    override = selection_override.get(str(node_id))
    return deepcopy(override) if isinstance(override, dict) else {}


def apply_selection_override_to_params(
    params: dict[str, Any],
    override: dict[str, Any] | None,
) -> dict[str, Any]:
    effective = deepcopy(params)
    normalized = normalize_selection_override({"node": override or {}}).get("node", {})
    for key, value in normalized.items():
        effective[key] = value
    return effective


def apply_load_data_selection_overrides(
    definition_json: dict[str, Any],
    selection_override: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    normalized = normalize_selection_override(selection_override)
    if not normalized:
        return definition_json if isinstance(definition_json, dict) else {}

    effective_definition = deepcopy(definition_json if isinstance(definition_json, dict) else {})
    graph = effective_definition.get("graph")
    nodes = graph.get("nodes") if isinstance(graph, dict) else None
    if not isinstance(nodes, list):
        return effective_definition

    for node in nodes:
        if not isinstance(node, dict) or node.get("type") != "eeg/data/load":
            continue
        node_id = str(node.get("id") or "")
        override = load_data_override_for_node(normalized, node_id)
        if not override:
            continue
        params = node.get("params") if isinstance(node.get("params"), dict) else {}
        node["params"] = apply_selection_override_to_params(params, override)
    return effective_definition
