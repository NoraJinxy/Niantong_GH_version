"""
Purpose: shared unit-stack helpers for group analysis.

Any stackable analysis artifact is represented as:
    data = (unit, channel, *feature_axes)

`unit` can mean subject, session, run, or trial. Group Merge/Grand Average/
Compare operate on that unit axis and keep ERP/PSD/TFR feature axes intact.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.engine.io import (
    load_psd_npz,
    load_unit_stack_npz,
    read_evoked_from_data_info,
    read_tfr_from_data_info,
    resolve_path_reference,
)


FEATURE_AXES: dict[str, tuple[str, ...]] = {
    "evoked": ("channels", "times"),
    "psd": ("channels", "freqs"),
    "tfr": ("channels", "freqs", "times"),
}

_PATH_KEYS = (
    "storage_uri",
    "artifact_storage_uri",
    "fif_abs_path",
    "fif_path",
    "storage_path",
    "artifact_storage_path",
)

_UNKNOWN = "unknown"
_UNIT_LIST_KEYS = (
    "unit_labels",
    "unit_subjects",
    "unit_conditions",
    "unit_sessions",
    "unit_runs",
    "unit_tasks",
    "unit_n",
)


def _clean_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _subject_of(data_info: dict[str, Any]) -> str:
    return _clean_text(
        data_info.get("subject")
        or data_info.get("bids_subject_id")
        or data_info.get("subject_id")
        or data_info.get("source_subject")
    )


def _condition_of(data_info: dict[str, Any]) -> str:
    return _clean_text(
        data_info.get("condition")
        or data_info.get("event_label")
        or data_info.get("comment")
        or data_info.get("label"),
        _UNKNOWN,
    )


def _session_of(data_info: dict[str, Any]) -> str:
    return _clean_text(data_info.get("session") or data_info.get("ses") or data_info.get("bids_session"))


def _run_of(data_info: dict[str, Any]) -> str:
    return _clean_text(data_info.get("run") or data_info.get("run_label") or data_info.get("bids_run"))


def _task_of(data_info: dict[str, Any]) -> str:
    return _clean_text(data_info.get("task") or data_info.get("bids_task"))


def _single_unit_metadata(data_info: dict[str, Any], *, label: str, n: float) -> dict[str, Any]:
    subject = _subject_of(data_info)
    condition = _condition_of(data_info)
    return {
        "unit_labels": [_clean_text(label, subject or condition or "0")],
        "unit_subjects": [subject],
        "unit_conditions": [condition],
        "unit_sessions": [_session_of(data_info)],
        "unit_runs": [_run_of(data_info)],
        "unit_tasks": [_task_of(data_info)],
        "unit_n": [float(n or 0.0)],
        "n_units": 1,
    }


def _fill_unit_list(values: Any, n_units: int, default: Any) -> list[Any]:
    if isinstance(values, (list, tuple)):
        items = list(values)
    else:
        try:
            import numpy as np  # noqa: PLC0415

            if values is not None and isinstance(values, np.ndarray):
                items = list(values.tolist())
            else:
                items = []
        except Exception:  # noqa: BLE001
            items = []
    return (items + [default] * n_units)[:n_units]


def normalize_block_metadata(block: dict[str, Any]) -> dict[str, Any]:
    """Ensure every block has a per-unit metadata list for condition-aware ops."""
    import numpy as np  # noqa: PLC0415

    data = np.asarray(block.get("data"))
    n_units = int(block.get("n_units") or (data.shape[0] if data.ndim else 0))
    condition = _clean_text(block.get("condition") or block.get("label"), _UNKNOWN)
    block["n_units"] = n_units
    block["unit_labels"] = [
        _clean_text(item) for item in _fill_unit_list(block.get("unit_labels"), n_units, "")
    ]
    block["unit_subjects"] = [
        _clean_text(item) for item in _fill_unit_list(block.get("unit_subjects"), n_units, "")
    ]
    block["unit_conditions"] = [
        _clean_text(item, condition) for item in _fill_unit_list(block.get("unit_conditions"), n_units, condition)
    ]
    block["unit_sessions"] = [
        _clean_text(item) for item in _fill_unit_list(block.get("unit_sessions"), n_units, "")
    ]
    block["unit_runs"] = [
        _clean_text(item) for item in _fill_unit_list(block.get("unit_runs"), n_units, "")
    ]
    block["unit_tasks"] = [
        _clean_text(item) for item in _fill_unit_list(block.get("unit_tasks"), n_units, "")
    ]
    block["unit_n"] = [
        float(item or 0.0) for item in _fill_unit_list(block.get("unit_n"), n_units, 0.0)
    ]
    if "condition" not in block:
        unique_conditions = sorted({c for c in block["unit_conditions"] if c})
        block["condition"] = unique_conditions[0] if len(unique_conditions) == 1 else condition
    return block


def extract_block(data_info: dict[str, Any]) -> dict[str, Any]:
    """Convert one upstream artifact to a stackable numeric block.

    Single evoked/PSD/TFR artifacts become one unit. Existing unit_stack
    artifacts pass through with their per-unit metadata preserved.
    """
    import numpy as np  # noqa: PLC0415

    dt = str(data_info.get("data_type") or "").lower()
    subject = _subject_of(data_info)

    if dt == "unit_stack":
        path = resolve_path_reference(data_info, _PATH_KEYS)
        block = load_unit_stack_npz(path)
        fallback_condition = _condition_of(data_info)
        if not block.get("condition") or block.get("condition") == _UNKNOWN:
            block["condition"] = fallback_condition
        return normalize_block_metadata(block)

    if dt in ("psd", "psd_grandavg"):
        path = resolve_path_reference(data_info, _PATH_KEYS)
        p = load_psd_npz(path)
        psds = np.asarray(p["psds"], dtype=float)
        ch_names = [str(c) for c in p["ch_names"]]
        label = _clean_text(data_info.get("label") or data_info.get("comment"), subject or _condition_of(data_info))
        block = {
            "base_type": "psd",
            "data": psds[None, ...],
            "ch_names": ch_names,
            "ch_types": ["eeg"] * len(ch_names),
            "times": None,
            "freqs": np.asarray(p["freqs"], dtype=float),
            "sfreq": float(p.get("sfreq") or 0.0),
            "condition": _condition_of(data_info),
            **_single_unit_metadata(data_info, label=label, n=float(data_info.get("n_epochs") or 0)),
        }
        return normalize_block_metadata(block)

    if dt == "evoked":
        ev = read_evoked_from_data_info(data_info)
        data = np.asarray(ev.data, dtype=float)
        condition = _clean_text(data_info.get("condition") or getattr(ev, "comment", None), _UNKNOWN)
        label = _clean_text(data_info.get("label") or getattr(ev, "comment", None), subject or condition)
        block = {
            "base_type": "evoked",
            "data": data[None, ...],
            "ch_names": [str(c) for c in ev.ch_names],
            "ch_types": [str(t) for t in ev.get_channel_types()],
            "times": np.asarray(ev.times, dtype=float),
            "freqs": None,
            "sfreq": float(ev.info["sfreq"]),
            "condition": condition,
            **_single_unit_metadata(data_info, label=label, n=float(getattr(ev, "nave", 0) or 0)),
        }
        block["unit_conditions"] = [condition]
        return normalize_block_metadata(block)

    if dt == "tfr":
        tf = read_tfr_from_data_info(data_info)
        data = np.asarray(tf.data, dtype=float)
        condition = _clean_text(data_info.get("condition") or getattr(tf, "comment", None), _UNKNOWN)
        label = _clean_text(data_info.get("label") or getattr(tf, "comment", None), subject or condition)
        block = {
            "base_type": "tfr",
            "data": data[None, ...],
            "ch_names": [str(c) for c in tf.ch_names],
            "ch_types": [str(t) for t in tf.get_channel_types()],
            "times": np.asarray(tf.times, dtype=float),
            "freqs": np.asarray(tf.freqs, dtype=float),
            "sfreq": float(tf.info["sfreq"]),
            "condition": condition,
            **_single_unit_metadata(data_info, label=label, n=float(getattr(tf, "nave", 0) or 0)),
        }
        block["unit_conditions"] = [condition]
        return normalize_block_metadata(block)

    raise ValueError(
        f"Group operation does not support data_type={dt or 'unknown'}. "
        "Stackable inputs are evoked, psd, tfr, or unit_stack; raw data must be epoched/analyzed first."
    )


def _assert_axis_match(ref: Any, other: Any, axis_name: str, base_type: str) -> None:
    """Validate exact feature-axis equality for times/freqs."""
    import numpy as np  # noqa: PLC0415

    has_ref = ref is not None and len(ref) > 0
    has_other = other is not None and len(other) > 0
    if has_ref != has_other:
        raise ValueError(f"{base_type} inputs disagree on whether {axis_name} exists; cannot stack.")
    if not has_ref:
        return
    a = np.asarray(ref, dtype=float)
    b = np.asarray(other, dtype=float)
    if a.shape != b.shape or not np.allclose(a, b):
        raise ValueError(
            f"{base_type} inputs have different {axis_name} grids. "
            "Use the same analysis parameters before Group Merge."
        )


def _ch_types_for(block: dict[str, Any], common: list[str]) -> list[str]:
    names = list(block.get("ch_names") or [])
    types = list(block.get("ch_types") or [])
    tmap = {n: (types[i] if i < len(types) else "eeg") for i, n in enumerate(names)}
    return [str(tmap.get(c, "eeg")) for c in common]


def _common_channels(blocks: list[dict[str, Any]], channel_policy: str) -> list[str]:
    first_ch = list(blocks[0]["ch_names"])
    if channel_policy == "require_identical":
        first_set = set(first_ch)
        mismatches: list[str] = []
        for index, block in enumerate(blocks[1:], start=2):
            other = set(block["ch_names"])
            if other != first_set:
                missing = sorted(first_set - other)[:5]
                extra = sorted(other - first_set)[:5]
                mismatches.append(
                    f"input {index}: n_ch={len(other)}, missing={missing}, extra={extra}"
                )
        if mismatches:
            raise ValueError(
                "Group Merge requires identical channel sets. "
                "Harmonize channels upstream before group-level merging. "
                + "; ".join(mismatches)
            )
        return first_ch

    if channel_policy != "intersection":
        raise ValueError("channel_policy must be require_identical or intersection.")

    common = [c for c in first_ch if all(c in set(b["ch_names"]) for b in blocks[1:])]
    if not common:
        raise ValueError("Inputs have no shared channels; cannot stack.")
    return common


def _coverage(blocks: list[dict[str, Any]], common: list[str]) -> dict[str, Any]:
    union_ch: list[str] = []
    seen_ch: set[str] = set()
    for block in blocks:
        for channel in block["ch_names"]:
            if channel not in seen_ch:
                seen_ch.add(channel)
                union_ch.append(channel)
    n_union = len(union_ch)
    return {
        "n_common": len(common),
        "n_union": n_union,
        "per_input_n_ch": [len(list(block["ch_names"])) for block in blocks],
        "coverage_ratio": round(len(common) / n_union, 4) if n_union else 0.0,
    }


def _validate_duplicate_units(
    *,
    unit_kind: str,
    unit_labels: list[str],
    unit_subjects: list[str],
    unit_sessions: list[str],
    unit_runs: list[str],
    unit_conditions: list[str],
    policy: str,
) -> None:
    if policy == "allow":
        return
    if policy != "error":
        raise ValueError("duplicate_unit_policy must be error or allow.")

    identities: list[str] = []
    for index, subject in enumerate(unit_subjects):
        session = unit_sessions[index] if index < len(unit_sessions) else ""
        run = unit_runs[index] if index < len(unit_runs) else ""
        label = unit_labels[index] if index < len(unit_labels) else ""
        condition = unit_conditions[index] if index < len(unit_conditions) else ""
        if unit_kind == "subject":
            parts = [subject]
        elif unit_kind == "session":
            parts = [subject, session]
        elif unit_kind == "run":
            parts = [subject, session, run]
        elif unit_kind in {"trial", "epoch"}:
            parts = [subject, session, run, condition, label or str(index + 1)]
        else:
            parts = [subject, session, run, label or str(index + 1)]
        meaningful = [p for p in parts if p and p != _UNKNOWN]
        if meaningful:
            identities.append("|".join(parts))

    duplicates = [identity for identity, count in Counter(identities).items() if count > 1]
    if duplicates:
        sample = ", ".join(duplicates[:5])
        raise ValueError(
            f"Duplicate {unit_kind} units in one stack: {sample}. "
            "Each condition stack must contain one sample per unit; aggregate repeated runs upstream first."
        )


def collapse_repeated_subject_units(stack: dict[str, Any]) -> dict[str, Any]:
    """Collapse repeated subject units inside one condition into one weighted unit.

    Group Merge exposes subject-level stacks to Grand Average. When upstream ERP
    / PSD / TFR nodes emit one artifact per run or session, the same subject can
    appear several times inside the same condition. Those repeats are technical
    repetitions, not independent group samples, so they are averaged here before
    the final unit_stack is saved.
    """
    import numpy as np  # noqa: PLC0415

    source = normalize_block_metadata(dict(stack))
    data = np.asarray(source["data"], dtype=float)
    n_units = int(source.get("n_units") or (data.shape[0] if data.ndim else 0))
    if n_units <= 1:
        return source

    unit_labels = list(source.get("unit_labels") or [])
    unit_subjects = list(source.get("unit_subjects") or [])
    unit_conditions = list(source.get("unit_conditions") or [])
    unit_sessions = list(source.get("unit_sessions") or [])
    unit_runs = list(source.get("unit_runs") or [])
    unit_tasks = list(source.get("unit_tasks") or [])
    unit_n = [float(item or 0.0) for item in list(source.get("unit_n") or [])]

    ordered_keys: list[str] = []
    groups: dict[str, list[int]] = {}
    for index in range(n_units):
        subject = _clean_text(unit_subjects[index] if index < len(unit_subjects) else "")
        label = _clean_text(unit_labels[index] if index < len(unit_labels) else "")
        key = subject or label or f"unit-{index + 1}"
        if key not in groups:
            ordered_keys.append(key)
            groups[key] = []
        groups[key].append(index)

    if all(len(indices) == 1 for indices in groups.values()):
        return source

    def _join_unique(values: list[str], fallback: str = "") -> str:
        unique: list[str] = []
        for value in values:
            text = _clean_text(value)
            if text and text not in unique:
                unique.append(text)
        return "+".join(unique) if unique else fallback

    collapsed_data: list[Any] = []
    collapsed_labels: list[str] = []
    collapsed_subjects: list[str] = []
    collapsed_conditions: list[str] = []
    collapsed_sessions: list[str] = []
    collapsed_runs: list[str] = []
    collapsed_tasks: list[str] = []
    collapsed_n: list[float] = []
    repeat_summary: list[dict[str, Any]] = []

    for key in ordered_keys:
        indices = groups[key]
        weights = np.asarray([unit_n[index] if index < len(unit_n) else 0.0 for index in indices], dtype=float)
        if not np.any(weights > 0):
            weights = np.ones(len(indices), dtype=float)
        else:
            weights = np.where(weights > 0, weights, 0.0)
        collapsed_data.append(np.average(data[indices, ...], axis=0, weights=weights))
        subjects = [unit_subjects[index] if index < len(unit_subjects) else "" for index in indices]
        labels = [unit_labels[index] if index < len(unit_labels) else "" for index in indices]
        conditions = [unit_conditions[index] if index < len(unit_conditions) else "" for index in indices]
        sessions = [unit_sessions[index] if index < len(unit_sessions) else "" for index in indices]
        runs = [unit_runs[index] if index < len(unit_runs) else "" for index in indices]
        tasks = [unit_tasks[index] if index < len(unit_tasks) else "" for index in indices]
        subject = _join_unique(subjects, key)
        collapsed_subjects.append(subject)
        collapsed_labels.append(subject or _join_unique(labels, key))
        collapsed_conditions.append(_join_unique(conditions, _clean_text(source.get("condition"), _UNKNOWN)))
        collapsed_sessions.append(_join_unique(sessions))
        collapsed_runs.append(_join_unique(runs))
        collapsed_tasks.append(_join_unique(tasks))
        collapsed_n.append(float(np.sum(weights)))
        if len(indices) > 1:
            repeat_summary.append(
                {
                    "unit": subject or key,
                    "count": len(indices),
                    "sessions": _join_unique(sessions),
                    "runs": _join_unique(runs),
                    "weight_sum": float(np.sum(weights)),
                }
            )

    collapsed = dict(source)
    collapsed["data"] = np.stack(collapsed_data, axis=0)
    collapsed["unit_labels"] = collapsed_labels
    collapsed["unit_subjects"] = collapsed_subjects
    collapsed["unit_conditions"] = collapsed_conditions
    collapsed["unit_sessions"] = collapsed_sessions
    collapsed["unit_runs"] = collapsed_runs
    collapsed["unit_tasks"] = collapsed_tasks
    collapsed["unit_n"] = collapsed_n
    collapsed["n_units"] = len(collapsed_labels)
    collapsed["collapsed_repeated_units"] = repeat_summary
    return collapsed


def align_and_stack(blocks: list[dict[str, Any]], params: dict[str, Any]) -> dict[str, Any]:
    """Align stackable blocks and concatenate them along the unit axis."""
    import numpy as np  # noqa: PLC0415

    if not blocks:
        raise ValueError("align_and_stack: no input blocks.")

    blocks = [normalize_block_metadata(dict(block)) for block in blocks]
    base_types = {str(block["base_type"]) for block in blocks}
    if len(base_types) > 1:
        raise ValueError(
            f"Cannot stack different analysis forms: {sorted(base_types)}. "
            "A group must be all ERP, all PSD, or all TFR."
        )
    base_type = next(iter(base_types))

    channel_policy = str(params.get("channel_policy") or "require_identical")
    common = _common_channels(blocks, channel_policy)
    coverage = _coverage(blocks, common)

    axis_policy = str(params.get("axis_policy") or "require_exact")
    if axis_policy != "require_exact":
        raise ValueError("axis_policy currently supports require_exact only.")
    ref_times = blocks[0].get("times")
    ref_freqs = blocks[0].get("freqs")
    for block in blocks[1:]:
        _assert_axis_match(ref_times, block.get("times"), "time axis", base_type)
        _assert_axis_match(ref_freqs, block.get("freqs"), "frequency axis", base_type)

    stacked: list[Any] = []
    unit_labels: list[str] = []
    unit_subjects: list[str] = []
    unit_conditions: list[str] = []
    unit_sessions: list[str] = []
    unit_runs: list[str] = []
    unit_tasks: list[str] = []
    unit_n: list[float] = []
    for block in blocks:
        idx = {channel: i for i, channel in enumerate(block["ch_names"])}
        sel = [idx[channel] for channel in common]
        arr = np.asarray(block["data"], dtype=float)[:, sel, ...]
        stacked.append(arr)
        m = int(arr.shape[0])
        unit_labels += [str(x) for x in _fill_unit_list(block.get("unit_labels"), m, "")]
        unit_subjects += [str(x) for x in _fill_unit_list(block.get("unit_subjects"), m, "")]
        unit_conditions += [str(x) for x in _fill_unit_list(block.get("unit_conditions"), m, _UNKNOWN)]
        unit_sessions += [str(x) for x in _fill_unit_list(block.get("unit_sessions"), m, "")]
        unit_runs += [str(x) for x in _fill_unit_list(block.get("unit_runs"), m, "")]
        unit_tasks += [str(x) for x in _fill_unit_list(block.get("unit_tasks"), m, "")]
        unit_n += [float(x or 0.0) for x in _fill_unit_list(block.get("unit_n"), m, 0.0)]

    data = np.concatenate(stacked, axis=0)
    unit_kind = str(params.get("unit_kind") or params.get("unit_label") or "subject")
    _validate_duplicate_units(
        unit_kind=unit_kind,
        unit_labels=unit_labels,
        unit_subjects=unit_subjects,
        unit_sessions=unit_sessions,
        unit_runs=unit_runs,
        unit_conditions=unit_conditions,
        policy=str(params.get("duplicate_unit_policy") or "error"),
    )

    condition = _clean_text(params.get("condition"), _UNKNOWN)
    group_label = _clean_text(params.get("group_label") or params.get("label"))
    label = _clean_text(params.get("label"), condition if condition != _UNKNOWN else group_label)

    return {
        "base_type": base_type,
        "data": data,
        "ch_names": common,
        "ch_types": _ch_types_for(blocks[0], common),
        "times": ref_times,
        "freqs": ref_freqs,
        "sfreq": float(blocks[0].get("sfreq") or 0.0),
        "unit_labels": unit_labels,
        "unit_subjects": unit_subjects,
        "unit_conditions": unit_conditions,
        "unit_sessions": unit_sessions,
        "unit_runs": unit_runs,
        "unit_tasks": unit_tasks,
        "unit_n": unit_n,
        "unit_kind": unit_kind,
        "input_level": str(params.get("input_level") or "subject_average"),
        "condition": condition,
        "group_label": group_label,
        "label": label,
        "n_units": int(data.shape[0]),
        "coverage": coverage,
    }
