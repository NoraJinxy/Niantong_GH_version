"""
Purpose: Group Merge entry point.

The node collects stackable upstream artifacts and emits one or more
condition-aware unit_stack results. Units are always split by condition so EO/EC
(or any event groups) do not get pooled into the same grand average.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.engine.group.stack import (
    align_and_stack,
    collapse_repeated_subject_units,
    extract_block,
    normalize_block_metadata,
)


def _clean_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _normalise_params(params: dict[str, Any]) -> dict[str, Any]:
    merged = dict(params or {})
    if not merged.get("group_label") and merged.get("label"):
        merged["group_label"] = merged.get("label")
    merged["condition_mode"] = "split_by_condition"
    merged["unit_kind"] = "subject"
    merged["input_level"] = "subject_average"
    merged["duplicate_unit_policy"] = "error"
    merged["channel_policy"] = "require_identical"
    merged["axis_policy"] = "require_exact"
    return merged


def _subset_block_units(block: dict[str, Any], indices: list[int]) -> dict[str, Any]:
    import numpy as np  # noqa: PLC0415

    source = normalize_block_metadata(dict(block))
    subset = dict(source)
    subset["data"] = np.asarray(source["data"])[indices, ...]
    subset["n_units"] = len(indices)
    for key in (
        "unit_labels",
        "unit_subjects",
        "unit_conditions",
        "unit_sessions",
        "unit_runs",
        "unit_tasks",
        "unit_n",
    ):
        values = list(source.get(key) or [])
        subset[key] = [values[index] for index in indices if index < len(values)]
    unique_conditions = sorted({str(c) for c in subset.get("unit_conditions") or [] if c})
    if len(unique_conditions) == 1:
        subset["condition"] = unique_conditions[0]
    return subset


def _unique_unit_conditions(blocks: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for block in blocks:
        block = normalize_block_metadata(dict(block))
        for condition in block.get("unit_conditions") or []:
            text = _clean_text(condition, "unknown")
            if text not in seen:
                seen.add(text)
                ordered.append(text)
    return ordered


def _group_label(params: dict[str, Any], condition: str, mixed: bool = False) -> str:
    group_label = _clean_text(params.get("group_label") or params.get("label"))
    if mixed:
        return group_label or (condition if condition else "mixed")
    return condition if condition and condition != "unknown" else (group_label or condition or "unknown")


def _stack_group(blocks: list[dict[str, Any]], params: dict[str, Any], condition: str, *, mixed: bool = False) -> dict[str, Any]:
    stack_params = dict(params)
    stack_params["condition"] = condition
    stack_params["label"] = _group_label(params, condition, mixed=mixed)
    stack_params["group_label"] = _clean_text(params.get("group_label") or params.get("label"))
    stack_params["duplicate_unit_policy"] = "allow"
    return collapse_repeated_subject_units(align_and_stack(blocks, stack_params))


def run_group_merge(input_data_infos: list[dict[str, Any]], params: dict[str, Any]) -> list[dict[str, Any]]:
    """Read stackable inputs and emit condition-split unit_stack result(s)."""
    if not input_data_infos:
        raise ValueError("run_group_merge: input_data_infos is empty.")

    params = _normalise_params(params)
    blocks = [extract_block(data_info) for data_info in input_data_infos]

    conditions = _unique_unit_conditions(blocks)
    if not conditions:
        conditions = ["unknown"]

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for block in blocks:
        block = normalize_block_metadata(dict(block))
        per_condition: dict[str, list[int]] = defaultdict(list)
        for index, condition in enumerate(block.get("unit_conditions") or []):
            per_condition[_clean_text(condition, "unknown")].append(index)
        for condition, indices in per_condition.items():
            grouped[condition].append(_subset_block_units(block, indices))

    results = [
        _stack_group(grouped[condition], params, condition)
        for condition in conditions
        if grouped.get(condition)
    ]
    if not results:
        raise ValueError("Group Merge produced no unit_stack outputs.")
    return results
