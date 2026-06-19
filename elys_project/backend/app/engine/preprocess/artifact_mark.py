"""
Purpose: Apply human-confirmed bad segments / bad channels for the interactive
         "Artifact Mark" pipeline node (MNE-based engine). raw -> raw.
Related: app/pipeline/dispatcher.py (_execute_artifact_mark),
         app/pipeline/nodes/eeg_preproc_artifact_mark.json,
         app/engine/preprocess/bad_channels.py（坏道插值同款球面样条路径）。

设计原则（对标 MNE / EEGLAB / FieldTrip 共识）：
  - 坏段非破坏：只写 BAD_ annotation，不删/不改样本；下游 Epoch 切分用
    reject_by_annotation 才真正跳过——标记与剔除解耦、可逆。
  - 坏道分级且默认保守：默认只写 info['bads']（mark，不改数据）；显式选
    interpolate 才用球面样条重建坏电极（需电极坐标），并在明细里留
    "此通道为插值重建"的痕迹（不抹溯源）。
"""

from __future__ import annotations

import json
from typing import Any


BAD_ANNOTATION_PREFIX = "BAD_"


def _mne():
    try:
        import mne
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("MNE is required for artifact-mark pipeline nodes.") from exc
    return mne


def _coerce_list(value: Any) -> list[Any]:
    """node property 既可能是 JSON 字符串（前端存）也可能是已解析的 list（decision 写回）。"""
    if value in (None, ""):
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (ValueError, TypeError):
            return []
        return parsed if isinstance(parsed, list) else []
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def parse_bad_segments(value: Any) -> list[dict[str, Any]]:
    """归一坏段为 [{onset, duration, source}]，丢非法/零长段，按 onset 排序后合并相邻/重叠段。"""
    items = _coerce_list(value)
    segments: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            onset = float(item.get("onset"))
            duration = float(item.get("duration"))
        except (TypeError, ValueError):
            continue
        if onset < 0 or not (duration > 0):
            continue
        source = str(item.get("source") or "manual")
        segments.append({"onset": onset, "duration": duration, "source": source})
    return _merge_segments(segments)


def _merge_segments(segments: list[dict[str, Any]], gap: float = 0.0) -> list[dict[str, Any]]:
    """排序后把相邻/重叠（间隔 <= gap）的坏段并起来——抄 niantong mergeBadSegments 的'贴边即合'。"""
    if not segments:
        return []
    ordered = sorted(segments, key=lambda s: s["onset"])
    merged: list[dict[str, Any]] = [dict(ordered[0])]
    for seg in ordered[1:]:
        prev = merged[-1]
        prev_stop = prev["onset"] + prev["duration"]
        if seg["onset"] <= prev_stop + gap:
            stop = max(prev_stop, seg["onset"] + seg["duration"])
            prev["duration"] = stop - prev["onset"]
            if seg["source"] != prev["source"]:
                prev["source"] = "mixed"
        else:
            merged.append(dict(seg))
    return merged


def parse_bad_channels(value: Any) -> list[str]:
    """归一坏道为去重的通道名列表（接受 list[str]、JSON 串或逗号串）。"""
    if isinstance(value, str) and value.strip().startswith("["):
        value = _coerce_list(value)
    if isinstance(value, str):
        names = [item.strip() for item in value.replace(";", ",").split(",")]
    else:
        names = [str(item).strip() for item in _coerce_list(value)]
    out: list[str] = []
    for name in names:
        if name and name not in out:
            out.append(name)
    return out


def run_artifact_mark(raw: Any, params: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """应用人工（或自动建议后人工确认的）坏段 / 坏道。raw→raw。

    返回 (raw, {"artifact_mark": 明细})；明细由 dispatcher 并入 preview / mne_summary，
    作为该步溯源（标了几段坏段 / 几个坏道 / 各来源 / 是否插值），喂 Methods 自动生成。
    """
    mne = _mne()
    segments = parse_bad_segments(params.get("bad_segments"))
    bad_channels = parse_bad_channels(params.get("bad_channels"))
    channel_action = str(params.get("channel_action") or "mark").strip().lower()
    reset_bads = bool(params.get("reset_bads", True))
    if channel_action not in {"mark", "interpolate"}:
        raise ValueError(f"Unknown channel_action: {channel_action!r} (expected 'mark' or 'interpolate').")

    work = raw.copy().load_data()

    # 坏道只认数据里真实存在的通道名（防手误 / 过期标记带进不存在的通道）
    valid_channels = [ch for ch in bad_channels if ch in work.ch_names]
    unknown_channels = [ch for ch in bad_channels if ch not in work.ch_names]
    preexisting_bads = list(work.info.get("bads", []) or [])
    all_bads = list(dict.fromkeys(preexisting_bads + valid_channels))
    work.info["bads"] = all_bads

    # 坏段 → BAD_ annotation（非破坏，不删样本）。onset 以记录起点为参考，与观察窗时间轴一致。
    # 注意：若 raw.first_samp != 0，annotation 对齐需在真机数据上复核（调试期数据多为 0）。
    n_segments_added = 0
    if segments:
        onsets = [seg["onset"] for seg in segments]
        durations = [seg["duration"] for seg in segments]
        descriptions = [f"{BAD_ANNOTATION_PREFIX}{seg['source']}" for seg in segments]
        existing = work.annotations
        new_annot = mne.Annotations(
            onset=onsets,
            duration=durations,
            description=descriptions,
            orig_time=existing.orig_time,
        )
        work.set_annotations(existing + new_annot)
        n_segments_added = len(segments)

    interpolated = False
    if channel_action == "interpolate" and all_bads:
        # 球面样条插值需要电极坐标
        if work.get_montage() is None:
            raise ValueError(
                "坏道插值需要电极坐标：请在本节点之前接 'Ch Loc Assign' 指派电极位置（10-20 / 10-05）。"
            )
        work.interpolate_bads(reset_bads=reset_bads, verbose="ERROR")
        interpolated = True

    detail: dict[str, Any] = {
        "n_bad_segments": n_segments_added,
        "bad_segment_seconds": round(sum(seg["duration"] for seg in segments), 3),
        "bad_segments": segments,
        "bad_channels": all_bads,
        "n_bad_channels": len(all_bads),
        "channel_action": channel_action,
        "interpolated": interpolated,
        "sources": sorted({seg["source"] for seg in segments}) if segments else [],
    }
    if unknown_channels:
        detail["unknown_channels"] = unknown_channels
    if interpolated:
        detail["interpolated_bads"] = all_bads
        detail["reset_bads"] = reset_bads
    return work, {"artifact_mark": detail}


def _robust_z(values: Any):
    """稳健 z-score（中位数 / MAD），抗坏道自污染。移植自 niantong _robust_z_scores。

    0.6744897501960817 = Φ⁻¹(0.75)，让 MAD 在正态分布下与标准差同尺度。
    MAD≈0 退普通 z（std），std 也≈0 退全 0。
    """
    import numpy as np  # noqa: PLC0415

    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return arr
    med = np.median(arr)
    mad = np.median(np.abs(arr - med))
    if mad > 1e-12:
        return 0.6744897501960817 * (arr - med) / mad
    std = np.std(arr)
    if std > 1e-12:
        return (arr - med) / std
    return np.zeros_like(arr)


def _segments_from_mask(mask: Any, sfreq: float, pad: float = 0.03, min_dur: float = 0.08) -> list[dict[str, Any]]:
    """布尔掩码（逐样本是否超阈）转坏段区间：前后补 False 找上升/下降沿，每段前后 pad 秒，丢太短段。"""
    import numpy as np  # noqa: PLC0415

    m = np.asarray(mask, dtype=bool)
    if not m.any() or sfreq <= 0:
        return []
    padded = np.concatenate(([False], m, [False]))
    diff = np.diff(padded.astype(np.int8))
    starts = np.where(diff == 1)[0]
    stops = np.where(diff == -1)[0]
    out: list[dict[str, Any]] = []
    for s, e in zip(starts, stops):
        onset = max(0.0, s / sfreq - pad)
        stop = e / sfreq + pad
        duration = stop - onset
        if duration >= min_dur:
            out.append({"onset": round(onset, 4), "duration": round(duration, 4), "source": "auto"})
    return out


def auto_detect_artifacts(raw: Any, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """自动检测坏道 / 坏段建议（不改数据，只产建议交人确认）。移植自 niantong auto_mark_artifacts_mne。

    坏道：每 EEG 道算 std / 峰峰值 / 高频噪声(diff std) 三指标，各取稳健 z 再取最大（任一异常即异常）；
          超 channel_z_threshold(3.5) 入选、按分降序、封顶 max_bad_channels(12) 防一锅端。
    坏段：优先 mne.annotate_amplitude(peak 200µV / flat 0.5µV)，再叠加跨通道绝对峰值掩码兜底，gap≤0.05 合并。
    """
    mne = _mne()
    import numpy as np  # noqa: PLC0415

    params = params or {}
    channel_z_threshold = float(params.get("channel_z_threshold", 3.5))
    max_bad_channels = int(params.get("max_bad_channels", 12))
    peak_uv = float(params.get("peak_threshold_uv", 200.0))
    flat_uv = float(params.get("flat_threshold_uv", 0.5))
    min_dur = float(params.get("min_bad_duration", 0.08))
    merge_gap = float(params.get("merge_gap", 0.05))

    work = raw.copy().load_data()
    sfreq = float(work.info["sfreq"])
    eeg_picks = mne.pick_types(work.info, eeg=True, meg=False, exclude=[])

    bad_channels: list[str] = []
    channel_metrics: list[dict[str, Any]] = []
    if len(eeg_picks) >= 3:
        data = work.get_data(picks=eeg_picks)  # (n_ch, n_times) V
        names = [work.ch_names[i] for i in eeg_picks]
        std_uv = np.std(data, axis=1) * 1e6
        ptp_uv = (np.max(data, axis=1) - np.min(data, axis=1)) * 1e6
        hf_uv = (np.std(np.diff(data, axis=1), axis=1) * 1e6) if data.shape[1] > 1 else np.zeros(data.shape[0])
        composite = np.maximum.reduce([np.abs(_robust_z(std_uv)), np.abs(_robust_z(ptp_uv)), np.abs(_robust_z(hf_uv))])
        order = list(np.argsort(composite)[::-1])
        for idx in order:
            if composite[idx] >= channel_z_threshold and len(bad_channels) < max_bad_channels:
                bad_channels.append(names[idx])
                channel_metrics.append({
                    "name": names[idx], "score": round(float(composite[idx]), 2),
                    "std_uv": round(float(std_uv[idx]), 1), "ptp_uv": round(float(ptp_uv[idx]), 1),
                    "hf_uv": round(float(hf_uv[idx]), 1),
                })

    segments: list[dict[str, Any]] = []
    try:
        annot, _amp_bads = mne.preprocessing.annotate_amplitude(
            work, peak=peak_uv * 1e-6, flat=flat_uv * 1e-6, bad_percent=5.0,
            min_duration=max(0.02, min_dur), picks="eeg", verbose="ERROR",
        )
        first_time = float(getattr(work, "first_time", 0.0) or 0.0)
        for onset, dur in zip(annot.onset, annot.duration):
            if float(dur) < min_dur:
                continue
            segments.append({"onset": round(max(0.0, float(onset) - first_time), 4), "duration": round(float(dur), 4), "source": "auto"})
    except Exception:
        pass  # annotate_amplitude 不可用/失败 → 仅靠下面的掩码兜底

    if len(eeg_picks) >= 1:
        eeg_data = work.get_data(picks=eeg_picks)
        abs_peak_uv = np.max(np.abs(eeg_data), axis=0) * 1e6
        segments.extend(_segments_from_mask(abs_peak_uv >= peak_uv, sfreq, pad=0.03, min_dur=min_dur))

    segments = _merge_segments(segments, gap=merge_gap)
    return {
        "bad_channels": bad_channels,
        "bad_segments": segments,
        "n_bad_channels": len(bad_channels),
        "n_bad_segments": len(segments),
        "channel_metrics": channel_metrics,
    }
