"""
Purpose: Run EEG analysis operations such as epoching or ERP generation for Pipeline nodes.
Related: app/pipeline/dispatcher.py, app/pipeline/nodes/*.json, docs_v2/5-00.
"""

from __future__ import annotations

from typing import Any


def run_erp_average(epochs: Any, params: dict[str, Any]) -> Any:
    labels = _normalize_event_labels(params.get("condition"))
    if not labels:
        raise ValueError("ERP.condition is required.")

    event_id_map = dict(getattr(epochs, "event_id", {}) or {})
    available_conditions = set(event_id_map)
    missing = [label for label in labels if label not in available_conditions]
    if missing:
        available = ", ".join(sorted(available_conditions)) or "none"
        raise ValueError(f"ERP condition not found: {missing}. Available conditions: {available}")

    # MNE Epochs.__getitem__ 用 "/" 作 hierarchical tag 分隔符。例如 epochs["Stimulus/S 9"]
    # 会按 hierarchy 匹配（同时含 "Stimulus" 和 "S 9" 两个 tag），跟用户预期的"用整个字符串作为
    # event_id key 精确匹配"可能不一致 —— 特别当 event_id key 含空格、斜杠时容易踩坑。
    # 这里改成直接用底层 events 数组按数字 id 过滤，绕过 hierarchy 解释，行为最确定。
    target_ids = {event_id_map[label] for label in labels}
    events_arr = getattr(epochs, "events", None)
    if events_arr is None or len(events_arr) == 0:
        raise ValueError(f"ERP source epochs has no events for conditions: {labels}")

    # events[:, 2] 是 event id 数字列
    mask_indices = [i for i, ev in enumerate(events_arr) if int(ev[2]) in target_ids]
    if not mask_indices:
        raise ValueError(f"ERP average has no epochs matching conditions: {labels}")
    selected = epochs[mask_indices]

    channels = params.get("channels")
    if isinstance(channels, list) and channels:
        normalized = [str(channel) for channel in channels if str(channel).strip()]
        missing_channels = [channel for channel in normalized if channel not in selected.ch_names]
        if missing_channels:
            raise ValueError(f"ERP channels not found: {', '.join(missing_channels)}")
        selected = selected.copy().pick(normalized)

    evoked = selected.average()
    if evoked.nave <= 0:
        raise ValueError(f"ERP average has no epochs for conditions: {labels}")
    return evoked


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
