"""
Purpose: Run EEG analysis operations such as epoching or ERP generation for Pipeline nodes.
Related: app/pipeline/dispatcher.py, app/pipeline/nodes/*.json, docs_v2/5-00.
"""

from __future__ import annotations

from typing import Any

from .event_conditions import (
    match_conditions,
    rules_for_selection,
    summarize_event_vocabulary,
)


def run_epoch_segment(raw: Any, params: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """按 condition 切分 Epochs(condition 统一模型)。

    params["conditions"]: 用户在 Epoch 节点勾选的「事件分组名」列表(前端 chips 来自 LoadData
    自动算出的分组);也接受 [{"name","pattern","mode"?}, ...] 规则列表。运行时按当前数据重算
    分组、按所选名还原规则,与前端显示用同一套分组逻辑,保证一致。

    返回 (epochs, diagnostics)。diagnostics["skipped_conditions"] = 用户勾了、但在「这份」数据
    里切不出任何 epoch 的 condition(上游不存在 or 命中 0 条);调用方(dispatcher)据此回吐节点
    warning,不再「默默少切一类」。按单份 raw 算——多数据集异质时某条件只在部分文件缺失属正常,
    故只 warning、不 block(全部条件都切不出才在下面 raise)。
    """
    if _is_epochs_like(raw):
        return _run_epoch_segment_from_epochs(raw, params)
    return _run_epoch_segment_from_raw(raw, params)


def _run_epoch_segment_from_raw(raw: Any, params: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """Raw → Epochs：沿用 MNE 对 annotations / first_samp 的标准折算口径。"""
    mne = _mne()
    import numpy as np  # noqa: PLC0415

    annotations = getattr(raw, "annotations", None)
    if annotations is None or len(annotations) == 0:
        raise ValueError("No events found in Raw annotations.")
    descriptions = list(annotations.description)

    rules, unknown_conditions = rules_for_selection(params.get("conditions"), descriptions)
    if not rules and not unknown_conditions:
        raise ValueError("Epoch.conditions is required.")
    if not rules:
        summary = summarize_event_vocabulary(descriptions)
        raise ValueError(
            f"None of the selected conditions {unknown_conditions} exist in this data. "
            f"{summary['hint']}"
        )

    # onset→样本:交给 MNE 的 events_from_annotations(喂 mne.Epochs 的标准口径),它正确处理
    # first_samp / orig_time / meas_date 的所有组合,避免手算折算在裁剪/拼接/部分采集系统的数据
    # (first_samp≠0、或 orig_time≠meas_date)上整体错位且不报错。regexp=None 不过滤(含 BAD_/EDGE,
    # 留给 rules 决定),保持与旧"对全部注释套规则"一致。再把每条事件的 description 还原后套 rules。
    ev_arr, desc_to_code = mne.events_from_annotations(raw, regexp=None, verbose="ERROR")
    code_to_desc = {int(code): str(desc) for desc, code in desc_to_code.items()}
    ev_samples = [int(row[0]) for row in ev_arr]
    ev_descs = [code_to_desc.get(int(row[2]), "") for row in ev_arr]

    events_list, event_id_map, report = match_conditions(ev_samples, ev_descs, rules)
    if not event_id_map:
        summary = summarize_event_vocabulary(descriptions)
        raise ValueError(
            "No annotations matched the requested conditions "
            f"{[r.name for r in rules]}. {summary['hint']}"
        )

    # 勾了但这份数据切不出 epoch 的:上游根本没有(unknown)+ 规则建起来却命中 0 条(empty)。
    empty_conditions = [r.name for r in rules if report["counts"].get(r.name, 0) == 0]
    skipped_conditions = unknown_conditions + empty_conditions

    events = np.array(sorted(events_list), dtype=int)

    tmin = float(params.get("tmin", -0.2))
    tmax = float(params.get("tmax", 1.0))
    if tmax <= tmin:
        raise ValueError("Epoch.tmax must be greater than tmin.")

    epochs = mne.Epochs(
        raw,
        events,
        event_id=event_id_map,
        tmin=tmin,
        tmax=tmax,
        baseline=None,  # 原子化:Epoch 只负责切分;基线校正交给独立节点(MNE 把两步合并,我们拆开)
        preload=True,
        reject_by_annotation=True,
        verbose="ERROR",
    )
    if len(epochs) == 0:
        raise ValueError(f"No epochs were created for conditions: {list(event_id_map)}")
    diagnostics = {"skipped_conditions": skipped_conditions}
    return epochs, diagnostics


def _run_epoch_segment_from_epochs(parent_epochs: Any, params: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """Epochs → Epochs：在父 epoch 内按内部 annotations 再次切分。

    典型场景：先用 block / trial-start 标签切出长窗，再在这些父窗内部按具体 stimulus / response
    标签切短窗。MNE Epochs 会保存原始 annotations，并可通过 get_annotations_per_epoch() 取出每个
    父 epoch 内的相对事件时间；这里基于这些相对时间手动构造新的 EpochsArray，避免把父 epoch
    拼成连续 Raw 后让子窗跨越父窗边界。
    """
    mne = _mne()
    import numpy as np  # noqa: PLC0415

    per_parent = parent_epochs.get_annotations_per_epoch()
    if not per_parent:
        raise ValueError("Source Epochs has no per-epoch annotations.")

    sfreq = float(parent_epochs.info["sfreq"])
    parent_tmin = float(parent_epochs.tmin)
    parent_n_times = int(len(parent_epochs.times))

    samples: list[int] = []
    descriptions: list[str] = []
    lookup: dict[int, tuple[int, int, float]] = {}
    lookup_key = 0
    for parent_index, annotations in enumerate(per_parent):
        for ann in annotations:
            onset = float(ann[0])
            desc = str(ann[2])
            center = int(round((onset - parent_tmin) * sfreq))
            if center < 0 or center >= parent_n_times:
                continue
            # match_conditions 只需要稳定样本序；lookup_key 避免同一采样点多个 annotation 时丢信息。
            samples.append(lookup_key)
            descriptions.append(desc)
            lookup[lookup_key] = (parent_index, center, onset)
            lookup_key += 1

    if not descriptions:
        raise ValueError("No events found in source Epochs annotations.")

    rules, unknown_conditions = rules_for_selection(params.get("conditions"), descriptions)
    if not rules and not unknown_conditions:
        raise ValueError("Epoch.conditions is required.")
    if not rules:
        summary = summarize_event_vocabulary(descriptions)
        raise ValueError(
            f"None of the selected conditions {unknown_conditions} exist in this source Epochs. "
            f"{summary['hint']}"
        )

    events_list, event_id_map, report = match_conditions(samples, descriptions, rules)
    if not event_id_map:
        summary = summarize_event_vocabulary(descriptions)
        raise ValueError(
            "No annotations in source Epochs matched the requested conditions "
            f"{[r.name for r in rules]}. {summary['hint']}"
        )

    tmin = float(params.get("tmin", -0.2))
    tmax = float(params.get("tmax", 1.0))
    if tmax <= tmin:
        raise ValueError("Epoch.tmax must be greater than tmin.")

    parent_data = _epochs_data(parent_epochs)
    n_child_times = int(round((tmax - tmin) * sfreq)) + 1
    start_offset = int(round(tmin * sfreq))
    code_to_name = {int(code): name for name, code in event_id_map.items()}
    child_blocks: list[Any] = []
    child_events: list[list[int]] = []
    created_counts: dict[str, int] = {r.name: 0 for r in rules}
    dropped_outside_parent = 0

    annotation_onsets: list[float] = []
    annotation_durations: list[float] = []
    annotation_descriptions: list[str] = []
    event_stride = max(n_child_times + 1, int(round((tmax - tmin + 2.0) * sfreq)))

    for matched in sorted(events_list, key=lambda row: (lookup[int(row[0])][0], lookup[int(row[0])][1], int(row[0]))):
        sample_key = int(matched[0])
        event_code = int(matched[2])
        parent_index, center, onset = lookup[sample_key]
        start = center + start_offset
        stop = start + n_child_times
        condition_name = code_to_name.get(event_code, "")
        if start < 0 or stop > parent_n_times:
            dropped_outside_parent += 1
            continue

        child_index = len(child_blocks)
        child_sample = (child_index + 1) * event_stride
        child_blocks.append(parent_data[parent_index, :, start:stop])
        child_events.append([child_sample, 0, event_code])
        if condition_name:
            created_counts[condition_name] = created_counts.get(condition_name, 0) + 1

        # Preserve annotations that fall inside this new child epoch so a later Epoch node can still chain.
        for ann in per_parent[parent_index]:
            ann_onset = float(ann[0])
            rel_onset = ann_onset - onset
            if rel_onset < tmin - 1e-9 or rel_onset > tmax + 1e-9:
                continue
            annotation_onsets.append((child_sample / sfreq) + rel_onset)
            annotation_durations.append(float(ann[1]))
            annotation_descriptions.append(str(ann[2]))

    if not child_blocks:
        raise ValueError(
            "No child epochs were created inside source Epochs. "
            "Check the selected event labels and ensure the child tmin/tmax window stays within the parent epoch."
        )

    present_codes = {int(row[2]) for row in child_events}
    filtered_event_id = {name: code for name, code in event_id_map.items() if int(code) in present_codes}
    child_epochs = mne.EpochsArray(
        np.stack(child_blocks, axis=0),
        parent_epochs.info.copy(),
        events=np.array(child_events, dtype=int),
        event_id=filtered_event_id,
        tmin=tmin,
        baseline=None,
        verbose="ERROR",
    )
    if annotation_onsets:
        child_epochs.set_annotations(
            mne.Annotations(
                onset=annotation_onsets,
                duration=annotation_durations,
                description=annotation_descriptions,
            )
        )

    skipped_conditions = unknown_conditions + [
        r.name for r in rules if int(created_counts.get(r.name, 0)) == 0
    ]
    diagnostics = {
        "skipped_conditions": skipped_conditions,
        "dropped_outside_parent": dropped_outside_parent,
        "source": "epochs",
    }
    return child_epochs, diagnostics


def _is_epochs_like(data: Any) -> bool:
    return callable(getattr(data, "get_annotations_per_epoch", None)) and hasattr(data, "events")


def _epochs_data(epochs: Any) -> Any:
    try:
        return epochs.get_data(copy=False)
    except TypeError:
        return epochs.get_data()


def _mne():
    try:
        import mne
    except ImportError as exc:
        raise RuntimeError("MNE is required for epoching.") from exc
    return mne
