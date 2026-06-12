"""
Purpose: Run EEG analysis operations such as epoching or ERP generation for Pipeline nodes.
Related: app/pipeline/dispatcher.py, app/pipeline/nodes/*.json, docs_v2/5-00.
"""

from __future__ import annotations

from typing import Any

from .event_conditions import match_conditions, parse_condition_rules


def run_epoch_segment(raw: Any, params: dict[str, Any]) -> Any:
    """按 condition 切分 Epochs。事件选择两种写法都收(向后兼容):

    - params["event_groups"]: [{"name","pattern","mode"?}, ...] —— 按 condition 分组(含/正则),
      把"原始注释里带序号的一堆唯一串"归并成少数干净 condition(econ 这类数据的正解)。
    - params["event_id"]: ["S1", ...] / "S1,S2" —— 逐字符串精确匹配(旧行为)。
    """
    mne = _mne()
    import numpy as np  # noqa: PLC0415

    rules = parse_condition_rules(params.get("event_groups") or params.get("event_id"))
    if not rules:
        raise ValueError("Epoch.event_id is required.")

    annotations = getattr(raw, "annotations", None)
    if annotations is None or len(annotations) == 0:
        raise ValueError("No events found in Raw annotations.")

    sfreq = float(raw.info["sfreq"])
    events_list, event_id_map, _report = match_conditions(
        annotations.onset, annotations.description, sfreq, rules
    )
    if not event_id_map:
        from .event_conditions import summarize_event_vocabulary  # noqa: PLC0415

        summary = summarize_event_vocabulary(list(annotations.description))
        raise ValueError(
            "No annotations matched the requested conditions "
            f"{[r.name for r in rules]}. {summary['hint']}"
        )

    events = np.array(sorted(events_list), dtype=int)

    tmin = float(params.get("tmin", -0.2))
    tmax = float(params.get("tmax", 1.0))
    if tmax <= tmin:
        raise ValueError("Epoch.tmax must be greater than tmin.")

    baseline = _baseline(params)
    epochs = mne.Epochs(
        raw,
        events,
        event_id=event_id_map,
        tmin=tmin,
        tmax=tmax,
        baseline=baseline,
        preload=True,
        reject_by_annotation=True,
        verbose="ERROR",
    )
    if len(epochs) == 0:
        raise ValueError(f"No epochs were created for conditions: {list(event_id_map)}")
    return epochs


def _baseline(params: dict[str, Any]) -> tuple[float | None, float | None] | None:
    start = params.get("baseline_start", -0.2)
    end = params.get("baseline_end", 0.0)
    if start in (None, "") and end in (None, ""):
        return None
    baseline_start = None if start in (None, "") else float(start)
    baseline_end = None if end in (None, "") else float(end)
    return (baseline_start, baseline_end)


def _mne():
    try:
        import mne
    except ImportError as exc:
        raise RuntimeError("MNE is required for epoching.") from exc
    return mne
