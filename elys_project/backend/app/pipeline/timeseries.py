"""
Purpose: 从结果 FIF 读取时域信号供"时域查看器"按需拉取，覆盖
         raw / filtered_raw / ica_cleaned / epochs / evoked 五种类型。
         支持：时间窗 (tmin/tmax 秒)、段选择 (epochs 选 epoch / evoked 选 condition)、
         通道与采样点下采样。返回统一结构，前端按 data_type 渲染同一套时域图。
Related: app/routers/pipelines.py, app/pipeline/previews.py（复用路径解析/校验）,
         frontend WaveformDetailPage.vue。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .montage_layout import channel_positions_2d
from .previews import StudyOutputPreviewError, resolve_study_output_path, validate_study_output_file

DEFAULT_MAX_POINTS = 2000
DEFAULT_MAX_CHANNELS = 64
RAW_DEFAULT_WINDOW_SEC = 10.0
CONTINUOUS_TYPES = ("raw", "filtered_raw", "ica_cleaned")


def _mne():
    try:
        import mne
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("MNE is required for timeseries.") from exc
    return mne


def _numpy():
    try:
        import numpy
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("NumPy is required for timeseries.") from exc
    return numpy


def _data_picks(mne, info, max_channels: int):
    """优先取 EEG 数据通道（排除 stim/misc/bads），取不到就退回全部通道。返回 (picks, names)。"""
    try:
        picks = list(
            mne.pick_types(info, eeg=True, meg=False, eog=False, ecg=False, stim=False, misc=False, exclude="bads")
        )
    except Exception:
        picks = []
    if not picks:
        picks = list(range(len(info["ch_names"])))
    picks = picks[: max(1, int(max_channels))]
    names = [str(info["ch_names"][i]) for i in picks]
    return picks, names


def _downsample(np, n: int, max_points: int):
    if n <= 0:
        return np.array([], dtype=int)
    count = min(max(2, int(max_points)), int(n))
    return np.unique(np.linspace(0, n - 1, count).astype(int))


# 通道 2D 投影助手已抽到 montage_layout.py（timeseries 与 ica_inspect 共用），见顶部 import channel_positions_2d。


def build_timeseries(
    study: Any,
    artifact: Any,
    *,
    tmin: float | None = None,
    tmax: float | None = None,
    index: int | None = None,
    max_points: int = DEFAULT_MAX_POINTS,
    max_channels: int = DEFAULT_MAX_CHANNELS,
    l_freq: float | None = None,
    h_freq: float | None = None,
    notch: float | None = None,
) -> dict[str, Any]:
    data_type = str(getattr(artifact, "data_type", "") or "").strip().lower()
    path = resolve_study_output_path(study, artifact)
    validate_study_output_file(path, artifact)
    if data_type in CONTINUOUS_TYPES:
        return _ts_raw(path, data_type, tmin, tmax, max_points, max_channels, l_freq, h_freq, notch)
    if data_type == "epochs":
        return _ts_epochs(path, tmin, tmax, index, max_points, max_channels, l_freq, h_freq, notch)
    if data_type == "evoked":
        return _ts_evoked(path, tmin, tmax, index, max_points, max_channels, l_freq, h_freq, notch)
    raise StudyOutputPreviewError(
        "DERIVED_DATASET_TIMESERIES_UNSUPPORTED",
        f"暂不支持 data_type={data_type or 'unknown'} 的时域曲线",
        status_code=400,
    )


def encode_timeseries_binary(payload: dict[str, Any]) -> bytes:
    """把 build_timeseries 的 JSON 结构编码为紧凑二进制（前端 plotCache 解码）。

    布局：b"EEGBIN01" + u32(metaLen, LE) + meta(JSON utf8) + f64 times[n] + f32 data[n_ch*n_times](C-order)。
    通道值由 V 换算成 µV，meta.unit="uV"（前端据此不再猜单位）。meta 含除 channels/times 外的全部字段
    + n_times / ch_names / n_channels。
    """
    import json
    import struct

    np = _numpy()
    channels = payload.get("channels") or []
    times = np.asarray(payload.get("times") or [], dtype="<f8")
    n_times = int(times.shape[0])
    ch_names = [str(c.get("name")) for c in channels]
    if channels:
        data = np.asarray([c.get("values") or [] for c in channels], dtype=np.float32)
    else:
        data = np.zeros((0, n_times), dtype=np.float32)
    data = np.ascontiguousarray(data * np.float32(1e6), dtype="<f4")  # V → µV

    meta = {k: v for k, v in payload.items() if k not in ("channels", "times")}
    meta["unit"] = "uV"
    meta["n_times"] = n_times
    meta["ch_names"] = ch_names
    meta["n_channels"] = len(ch_names)
    meta_bytes = json.dumps(meta, ensure_ascii=False).encode("utf-8")

    out = bytearray()
    out += b"EEGBIN01"
    out += struct.pack("<I", len(meta_bytes))
    out += meta_bytes
    out += times.tobytes()
    out += data.tobytes()
    return bytes(out)


def _apply_view_filter(np, data, sfreq, l_freq, h_freq, notch):
    """view-only 瞬时滤波（下采样前、在全分辨率窗口数据上跑），仅供观察、不存储、不影响 pipeline。

    data: (n_ch, n_times) 伏特；l_freq=高通、h_freq=低通、notch=陷波。
    任何失败（如窗口过短不够滤波长度）→ 原样返回，不阻断观察。
    """
    if data is None or getattr(data, "size", 0) == 0:
        return data
    has_band = l_freq is not None or h_freq is not None
    has_notch = notch is not None and float(notch) > 0
    if not has_band and not has_notch:
        return data
    try:
        from mne.filter import filter_data, notch_filter  # noqa: PLC0415

        out = np.asarray(data, dtype="float64")
        if has_band:
            out = filter_data(out, sfreq, l_freq, h_freq, verbose="ERROR")
        if has_notch:
            out = notch_filter(out, sfreq, float(notch), verbose="ERROR")
        return out
    except Exception:
        return data


def _ts_raw(path: Path, data_type: str, tmin, tmax, max_points, max_channels, l_freq=None, h_freq=None, notch=None) -> dict[str, Any]:
    mne = _mne()
    np = _numpy()
    raw = mne.io.read_raw_fif(path, preload=False, verbose="ERROR")
    sfreq = float(raw.info["sfreq"])
    n_times = int(raw.n_times)
    total = n_times / sfreq if sfreq > 0 else 0.0

    lo = 0.0 if tmin is None else max(0.0, float(tmin))
    hi = min(total, lo + RAW_DEFAULT_WINDOW_SEC) if tmax is None else min(total, float(tmax))
    if hi <= lo:
        hi = min(total, lo + RAW_DEFAULT_WINDOW_SEC)

    start = max(0, int(round(lo * sfreq)))
    stop = min(n_times, int(round(hi * sfreq)))
    if stop <= start:
        stop = min(n_times, start + 1)

    picks, names = _data_picks(mne, raw.info, max_channels)
    data, times = raw[picks, start:stop]  # data: (n_pick, n_samp); times: 秒（绝对）
    data = _apply_view_filter(np, data, sfreq, l_freq, h_freq, notch)
    idx = _downsample(np, data.shape[1], max_points)
    out_times = np.round(times[idx], 5).tolist()
    sub = data[:, idx].tolist()  # 一次性 numpy → list，避免逐元素 float() 循环
    channels = [{"name": names[k], "values": sub[k]} for k in range(len(picks))]
    return {
        "data_type": data_type,
        "sfreq": sfreq,
        "tmin": round(float(out_times[0]) if out_times else lo, 5),
        "tmax": round(float(out_times[-1]) if out_times else hi, 5),
        "total_duration": round(total, 5),
        "available_tmin": 0.0,
        "available_tmax": round(total, 5),
        "n_segments": None,
        "segment_index": None,
        "segment_label": None,
        "segment_kind": None,
        "segment_options": None,
        "n_channels_total": len(raw.ch_names),
        "ch_names_all": [str(c) for c in raw.ch_names],
        "ch_pos": channel_positions_2d(raw.info, names),
        "times": out_times,
        "channels": channels,
    }


def _ts_epochs(path: Path, tmin, tmax, index, max_points, max_channels, l_freq=None, h_freq=None, notch=None) -> dict[str, Any]:
    mne = _mne()
    np = _numpy()
    epochs = mne.read_epochs(path, preload=False, verbose="ERROR")
    n_epochs = len(epochs)
    if n_epochs == 0:
        raise StudyOutputPreviewError("DERIVED_DATASET_TIMESERIES_EMPTY", "epochs 不含任何片段", status_code=422)
    ei = 0 if index is None else max(0, min(int(index), n_epochs - 1))
    times_all = epochs.times  # 秒，epoch 相对
    picks, names = _data_picks(mne, epochs.info, max_channels)

    full = epochs[ei].get_data()[0]  # (n_ch, n_times)
    arr = full[np.asarray(picks, dtype=int)]
    arr = _apply_view_filter(np, arr, float(epochs.info["sfreq"]), l_freq, h_freq, notch)

    lo = float(times_all[0]) if tmin is None else float(tmin)
    hi = float(times_all[-1]) if tmax is None else float(tmax)
    mask = (times_all >= lo - 1e-9) & (times_all <= hi + 1e-9)
    sel = np.where(mask)[0]
    if sel.size == 0:
        sel = np.arange(len(times_all))
    tsel = times_all[sel]
    dsel = arr[:, sel]
    idx = _downsample(np, dsel.shape[1], max_points)
    out_times = np.round(tsel[idx], 5).tolist()
    sub = dsel[:, idx].tolist()  # 一次性 numpy → list
    channels = [{"name": names[k], "values": sub[k]} for k in range(len(picks))]

    inverse = {int(code): str(name) for name, code in epochs.event_id.items()}
    label: str | None = None
    try:
        label = inverse.get(int(epochs.events[ei, 2]), str(int(epochs.events[ei, 2])))
    except Exception:
        label = None

    return {
        "data_type": "epochs",
        "sfreq": float(epochs.info["sfreq"]),
        "tmin": round(float(out_times[0]) if out_times else lo, 5),
        "tmax": round(float(out_times[-1]) if out_times else hi, 5),
        "total_duration": round(float(times_all[-1] - times_all[0]), 5),
        "available_tmin": round(float(times_all[0]), 5),
        "available_tmax": round(float(times_all[-1]), 5),
        "n_segments": n_epochs,
        "segment_index": ei,
        "segment_label": label,
        "segment_kind": "epoch",
        "segment_options": None,
        "n_channels_total": len(epochs.ch_names),
        "ch_names_all": [str(c) for c in epochs.ch_names],
        "ch_pos": channel_positions_2d(epochs.info, names),
        "times": out_times,
        "channels": channels,
    }


def _ts_evoked(path: Path, tmin, tmax, index, max_points, max_channels, l_freq=None, h_freq=None, notch=None) -> dict[str, Any]:
    mne = _mne()
    np = _numpy()
    evokeds = mne.read_evokeds(path, condition=None, verbose="ERROR")
    if not isinstance(evokeds, list):
        evokeds = [evokeds]
    if not evokeds:
        raise StudyOutputPreviewError("DERIVED_DATASET_TIMESERIES_EMPTY", "evoked 不含任何条件", status_code=422)
    n = len(evokeds)
    ci = 0 if index is None else max(0, min(int(index), n - 1))
    ev = evokeds[ci]
    times_all = ev.times
    picks, names = _data_picks(mne, ev.info, max_channels)
    arr = ev.data[np.asarray(picks, dtype=int)]  # (n_pick, n_times) 伏特
    arr = _apply_view_filter(np, arr, float(ev.info["sfreq"]), l_freq, h_freq, notch)

    lo = float(times_all[0]) if tmin is None else float(tmin)
    hi = float(times_all[-1]) if tmax is None else float(tmax)
    mask = (times_all >= lo - 1e-9) & (times_all <= hi + 1e-9)
    sel = np.where(mask)[0]
    if sel.size == 0:
        sel = np.arange(len(times_all))
    tsel = times_all[sel]
    dsel = arr[:, sel]
    idx = _downsample(np, dsel.shape[1], max_points)
    out_times = np.round(tsel[idx], 5).tolist()
    sub = dsel[:, idx].tolist()  # 一次性 numpy → list
    channels = [{"name": names[k], "values": sub[k]} for k in range(len(picks))]
    options = [str(item.comment or f"evoked_{i}") for i, item in enumerate(evokeds)]

    return {
        "data_type": "evoked",
        "sfreq": float(ev.info["sfreq"]),
        "tmin": round(float(out_times[0]) if out_times else lo, 5),
        "tmax": round(float(out_times[-1]) if out_times else hi, 5),
        "total_duration": round(float(times_all[-1] - times_all[0]), 5),
        "available_tmin": round(float(times_all[0]), 5),
        "available_tmax": round(float(times_all[-1]), 5),
        "n_segments": n,
        "segment_index": ci,
        "segment_label": options[ci] if ci < len(options) else None,
        "segment_kind": "condition",
        "segment_options": options,
        "n_channels_total": len(ev.ch_names),
        "ch_names_all": [str(c) for c in ev.ch_names],
        "ch_pos": channel_positions_2d(ev.info, names),
        "times": out_times,
        "channels": channels,
    }
