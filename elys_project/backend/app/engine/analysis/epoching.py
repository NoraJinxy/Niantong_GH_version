"""
Purpose: Run EEG analysis operations such as epoching or ERP generation for Pipeline nodes.
Related: app/pipeline/dispatcher.py, app/pipeline/nodes/*.json, docs_v2/5-00.
"""

from __future__ import annotations

from typing import Any


def run_epoch_segment(raw: Any, params: dict[str, Any]) -> Any:
    mne = _mne()
    labels = _normalize_event_labels(params.get("event_id"))
    if not labels:
        raise ValueError("Epoch.event_id is required.")

    events, event_id_map = mne.events_from_annotations(raw, verbose="ERROR")
    if events.size == 0 or not event_id_map:
        raise ValueError("No events found in Raw annotations.")

    missing = [label for label in labels if label not in event_id_map]
    if missing:
        available = ", ".join(sorted(event_id_map)) or "none"
        raise ValueError(f"Event not found: {missing}. Available events: {available}")

    selected_event_id = {label: event_id_map[label] for label in labels}

    tmin = float(params.get("tmin", -0.2))
    tmax = float(params.get("tmax", 1.0))
    if tmax <= tmin:
        raise ValueError("Epoch.tmax must be greater than tmin.")

    baseline = _baseline(params)
    epochs = mne.Epochs(
        raw,
        events,
        event_id=selected_event_id,
        tmin=tmin,
        tmax=tmax,
        baseline=baseline,
        preload=True,
        reject_by_annotation=True,
        verbose="ERROR",
    )
    if len(epochs) == 0:
        raise ValueError(f"No epochs were created for events: {labels}")
    return epochs


def _normalize_event_labels(raw: Any) -> list[str]:
    """Accept array / string / comma-separated string and return a clean list."""
    if raw is None:
        return []
    if isinstance(raw, list):
        items: list[Any] = raw
    elif isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        # 兼容旧版本可能存的逗号分隔字符串
        items = text.split(",") if "," in text else [text]
    else:
        items = [raw]

    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


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
