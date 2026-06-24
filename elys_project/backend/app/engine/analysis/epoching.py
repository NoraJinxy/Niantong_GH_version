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


def _mne():
    try:
        import mne
    except ImportError as exc:
        raise RuntimeError("MNE is required for epoching.") from exc
    return mne
