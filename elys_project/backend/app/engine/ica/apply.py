"""
Purpose: Run ICA compute/apply operations for Pipeline nodes in the EEG engine.
Related: app/pipeline/dispatcher.py, app/pipeline/nodes/eeg_ica_*.json, docs_v2/5-00.
"""

from __future__ import annotations

from typing import Any


def run_apply_ica(raw: Any, ica: Any, params: dict[str, Any]):
    excluded = parse_excluded_components(params.get("excluded_components"))
    cleaned = raw.copy()
    ica.exclude = excluded
    ica.apply(cleaned, verbose="ERROR")
    return cleaned


def parse_excluded_components(value: Any) -> list[int]:
    if value in (None, "", "null"):
        return []
    if isinstance(value, str):
        values = [item.strip() for item in value.replace(";", ",").replace(" ", ",").split(",")]
        return _normalize_component_indexes(values)
    if isinstance(value, (list, tuple, set)):
        return _normalize_component_indexes(value)
    return _normalize_component_indexes([value])


def _normalize_component_indexes(values: Any) -> list[int]:
    indexes: list[int] = []
    for value in values:
        if value in (None, ""):
            continue
        index = int(value)
        if index < 0:
            raise ValueError("ICA component indexes must be non-negative.")
        if index not in indexes:
            indexes.append(index)
    return sorted(indexes)
