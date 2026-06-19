"""
Purpose: Group analysis – 通用 unit 堆叠。把任意分析产物(evoked/psd/tfr)抽成统一数值块
         (unit, *feature_axes),沿 unit 轴对齐并堆叠。merge/average/compare 共用本层。
Related: app/engine/group/merge.py, app/engine/group/average.py, app/engine/io.py.

原则:任何产物 = (unit, *feature_axes)。unit=trial/run/subject(只是语义标签),feature 轴随形态:
  evoked → (通道, 时间)   psd → (通道, 频率)   tfr → (通道, 频率, 时间)
group 操作全是对 unit 轴动手,与 feature 轴无关 → 一套机制通吃三类。连续数据(raw)没有 unit 轴,
不可堆叠(需先 Epoch/分析成产物)。
"""

from __future__ import annotations

from typing import Any

from app.engine.io import (
    load_psd_npz,
    load_unit_stack_npz,
    read_evoked_from_data_info,
    read_tfr_from_data_info,
    resolve_path_reference,
)


# 各形态 feature 轴(unit 轴之后的轴),仅供文档/校验参考。
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


def _subject_of(data_info: dict[str, Any]) -> str:
    return str(
        data_info.get("subject")
        or data_info.get("bids_subject_id")
        or data_info.get("subject_id")
        or ""
    )


def extract_block(data_info: dict[str, Any]) -> dict[str, Any]:
    """把一个上游产物抽成统一块:data=(n_units, n_channels, *feature) + 坐标轴 + 逐 unit 元数据。

    单产物(evoked/psd/tfr)= 1 个 unit;已堆叠的 unit_stack = 其携带的 m 个 unit(直接透传)。
    连续数据(raw 等)抛错——没有可交换的 unit 轴。
    """
    import numpy as np  # noqa: PLC0415

    dt = str(data_info.get("data_type") or "").lower()
    subject = _subject_of(data_info)

    if dt == "unit_stack":
        path = resolve_path_reference(data_info, _PATH_KEYS)
        return load_unit_stack_npz(path)

    if dt in ("psd", "psd_grandavg"):
        path = resolve_path_reference(data_info, _PATH_KEYS)
        p = load_psd_npz(path)
        psds = np.asarray(p["psds"], dtype=float)  # (n_ch, n_freq)
        ch_names = [str(c) for c in p["ch_names"]]
        return {
            "base_type": "psd",
            "data": psds[None, ...],  # (1, n_ch, n_freq)
            "ch_names": ch_names,
            "ch_types": ["eeg"] * len(ch_names),
            "times": None,
            "freqs": np.asarray(p["freqs"], dtype=float),
            "sfreq": float(p.get("sfreq") or 0.0),
            "unit_labels": [str(data_info.get("label") or subject or "0")],
            "unit_subjects": [subject],
            "unit_n": [float(data_info.get("n_epochs") or 0)],
            "n_units": 1,
        }

    if dt == "evoked":
        ev = read_evoked_from_data_info(data_info)
        data = np.asarray(ev.data, dtype=float)  # (n_ch, n_times)
        return {
            "base_type": "evoked",
            "data": data[None, ...],
            "ch_names": [str(c) for c in ev.ch_names],
            "ch_types": [str(t) for t in ev.get_channel_types()],
            "times": np.asarray(ev.times, dtype=float),
            "freqs": None,
            "sfreq": float(ev.info["sfreq"]),
            "unit_labels": [str(getattr(ev, "comment", "") or subject or "0")],
            "unit_subjects": [subject],
            "unit_n": [float(getattr(ev, "nave", 0) or 0)],
            "n_units": 1,
        }

    if dt == "tfr":
        tf = read_tfr_from_data_info(data_info)
        data = np.asarray(tf.data, dtype=float)  # (n_ch, n_freq, n_times)
        return {
            "base_type": "tfr",
            "data": data[None, ...],
            "ch_names": [str(c) for c in tf.ch_names],
            "ch_types": [str(t) for t in tf.get_channel_types()],
            "times": np.asarray(tf.times, dtype=float),
            "freqs": np.asarray(tf.freqs, dtype=float),
            "sfreq": float(tf.info["sfreq"]),
            "unit_labels": [str(getattr(tf, "comment", "") or subject or "0")],
            "unit_subjects": [subject],
            "unit_n": [float(getattr(tf, "nave", 0) or 0)],
            "n_units": 1,
        }

    raise ValueError(
        f"Group 操作不支持的数据形态: '{dt or '未知'}'。可堆叠的只有 evoked / psd / tfr / unit_stack;"
        "连续数据(raw 等)没有 unit 轴,需先 Epoch 或做 ERP/PSD/TFR 分析成产物再合并。"
    )


def _assert_axis_match(ref: Any, other: Any, axis_name: str, base_type: str) -> None:
    """校验两块的某条 feature 坐标轴逐点一致(times/freqs)。numpy 数组,严禁 `if 数组`。"""
    import numpy as np  # noqa: PLC0415

    has_ref = ref is not None and len(ref) > 0
    has_other = other is not None and len(other) > 0
    if has_ref != has_other:
        raise ValueError(f"{base_type} 各输入的{axis_name}存在/缺失不一致,无法堆叠。")
    if not has_ref:
        return
    a = np.asarray(ref, dtype=float)
    b = np.asarray(other, dtype=float)
    if a.shape != b.shape or not np.allclose(a, b):
        raise ValueError(
            f"{base_type} 各输入的{axis_name}不一致(采样率/谱网格/时间窗不同),无法跨 unit 堆叠。"
            "请保证参与合并的产物用同一套分析参数。"
        )


def _ch_types_for(block: dict[str, Any], common: list[str]) -> list[str]:
    names = list(block.get("ch_names") or [])
    types = list(block.get("ch_types") or [])
    tmap = {n: (types[i] if i < len(types) else "eeg") for i, n in enumerate(names)}
    return [str(tmap.get(c, "eeg")) for c in common]


def align_and_stack(blocks: list[dict[str, Any]], params: dict[str, Any]) -> dict[str, Any]:
    """把多个块沿 unit 轴对齐堆叠:① 同形态 ② 通道取交集 ③ feature 轴逐点一致 → 拼接。"""
    import numpy as np  # noqa: PLC0415

    if not blocks:
        raise ValueError("align_and_stack: 没有可堆叠的输入块。")

    base_types = {b["base_type"] for b in blocks}
    if len(base_types) > 1:
        raise ValueError(
            f"不能跨形态堆叠:收到 {sorted(base_types)}。一个 group 里只能全是同一种形态"
            "(全 ERP / 全 PSD / 全 TFR)。"
        )
    base_type = next(iter(base_types))

    # 1) 通道取交集(保第一个块顺序,结果确定)。montage 不一致只在共有电极上做。
    first_ch = list(blocks[0]["ch_names"])
    common = [c for c in first_ch if all(c in set(b["ch_names"]) for b in blocks[1:])]
    if not common:
        raise ValueError(
            "各输入没有共有通道,无法堆叠(被试 montage 不一致,如 Emotiv 不同型号电极数不同)。"
            "请筛选同导联的输入再合并。"
        )

    # 2) feature 坐标轴逐点一致(times / freqs)
    ref_times = blocks[0].get("times")
    ref_freqs = blocks[0].get("freqs")
    for b in blocks[1:]:
        _assert_axis_match(ref_times, b.get("times"), "时间轴", base_type)
        _assert_axis_match(ref_freqs, b.get("freqs"), "频率轴", base_type)

    # 3) 逐块按交集通道重排(通道恒在 axis=1)+ 沿 unit 轴(axis=0)拼接
    stacked: list[Any] = []
    unit_labels: list[str] = []
    unit_subjects: list[str] = []
    unit_n: list[float] = []
    for b in blocks:
        idx = {c: i for i, c in enumerate(b["ch_names"])}
        sel = [idx[c] for c in common]
        arr = np.asarray(b["data"], dtype=float)[:, sel, ...]
        stacked.append(arr)
        m = int(arr.shape[0])
        bl = [str(x) for x in (b.get("unit_labels") or [])]
        bs = [str(x) for x in (b.get("unit_subjects") or [])]
        bn = [float(x) for x in (b.get("unit_n") or [])]
        unit_labels += (bl + [""] * m)[:m]
        unit_subjects += (bs + [""] * m)[:m]
        unit_n += (bn + [0.0] * m)[:m]
    data = np.concatenate(stacked, axis=0)  # (Σunits, n_common_ch, *feature)

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
        "unit_n": unit_n,
        "unit_kind": str(params.get("unit_label") or params.get("unit_kind") or "subject"),
        "label": str(params.get("label") or ""),
        "n_units": int(data.shape[0]),
    }
