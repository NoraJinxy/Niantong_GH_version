"""
Purpose: 对 Epochs / 连续 Raw 做功率谱密度(PSD)估计(Welch / Multitaper / FFT 单段),并算各频段绝对+相对功率。
Related: app/pipeline/dispatcher.py, app/pipeline/nodes/eeg_analysis_psd.json,
         app/engine/io.py(save_psd_npz / summarize_psd).

功率谱密度(power spectral density / PSD):把信号在频率维度展开,看每个频段(δ/θ/α/β/γ)的能量
(功率)有多强。和时频(TFR)不同,PSD 把整段时间压成一条「频率 → 功率」的谱线(不保留时间维)。
这里按 condition 选 Epochs → Welch 方法逐 epoch 估计 → 跨 epoch 平均,是脑电频谱最常用的做法。

注意:输出不是 MNE 对象,而是纯 numpy 数组的 dict(freqs / psds / ch_names),由 io.save_psd_npz
存成 .npz。这样 IO 不依赖 MNE Spectrum 的跨版本存取 API(版本间易变),自给自足、最稳。
"""

from __future__ import annotations

from typing import Any

from .erp import _normalize_event_labels


def run_psd(data: Any, params: dict[str, Any]) -> dict[str, Any]:
    """对 Epochs(按 condition)或连续 Raw(整段)估功率谱,返回数组 dict。

    输入二选一:
      - Epochs:按 condition 选 → Welch PSD → 跨 epoch 平均(原口径,需 condition)。
      - Raw(连续):无事件/无 condition,直接对整段连续数据估 PSD(静息态频域常用)。
        以 `hasattr(data, "event_id")` 区分:只有 Epochs 有 event_id 属性。

    params:
      condition:   事件分组名(仅 Epochs 输入必填;与 ERP/TFR 同口径,dispatcher 按 condition 展开)。
      fmin / fmax: 频率范围下/上限 Hz(默认 1 / 40)。fmax 会被自动夹到奈奎斯特频率以下。
      method:      "welch"(默认)或 "multitaper"。
      n_fft:       仅 Welch;每段 FFT 点数,留空用 MNE 默认。
      channels:    可选,只算这些通道(默认全通道)。
    """
    import numpy as np  # noqa: PLC0415

    # 连续数据(Raw)分支:无 condition,整段算一条 PSD。Raw 没有 event_id 属性,以此与 Epochs 区分。
    if not hasattr(data, "event_id"):
        return _run_psd_continuous(data, params)

    epochs = data
    labels = _normalize_event_labels(params.get("condition"))
    if not labels:
        raise ValueError("PSD.condition is required.")

    event_id_map = dict(getattr(epochs, "event_id", {}) or {})
    available = set(event_id_map)
    missing = [label for label in labels if label not in available]
    if missing:
        available_text = ", ".join(sorted(available)) or "none"
        raise ValueError(f"PSD condition not found: {missing}. Available conditions: {available_text}")

    # 与 ERP/TFR 同样绕过 MNE 的 "/" 层级标签解释,直接按数字 event id 过滤,行为最确定。
    target_ids = {event_id_map[label] for label in labels}
    events_arr = getattr(epochs, "events", None)
    if events_arr is None or len(events_arr) == 0:
        raise ValueError(f"PSD source epochs has no events for conditions: {labels}")
    mask_indices = [i for i, ev in enumerate(events_arr) if int(ev[2]) in target_ids]
    if not mask_indices:
        raise ValueError(f"PSD has no epochs matching conditions: {labels}")
    selected = epochs[mask_indices]

    channels = params.get("channels")
    if isinstance(channels, list) and channels:
        normalized = [str(channel) for channel in channels if str(channel).strip()]
        missing_channels = [channel for channel in normalized if channel not in selected.ch_names]
        if missing_channels:
            raise ValueError(f"PSD channels not found: {', '.join(missing_channels)}")
        selected = selected.copy().pick(normalized)

    fmin = float(params.get("fmin", 1.0))
    fmax = float(params.get("fmax", 40.0))
    if fmax <= fmin:
        raise ValueError("PSD.fmax must be greater than fmin.")
    nyquist = float(selected.info["sfreq"]) / 2.0
    fmax = min(fmax, nyquist - 1e-6)
    if fmax <= fmin:
        raise ValueError(f"PSD.fmax({fmax:.3g}) must stay below Nyquist and above fmin({fmin:.3g}).")

    # n_times = 每 epoch 采样点数;method=fft 用它把 Welch 退化成单段整段周期图(满频率分辨率,SSVEP 用)
    psd_kwargs, reported_method = _psd_kwargs(params, fmin, fmax, int(len(selected.times)))

    # EpochsSpectrum.get_data() → (n_epochs, n_channels, n_freqs);跨 epoch 求平均得 (n_channels, n_freqs)
    spectrum = selected.compute_psd(**psd_kwargs)
    psds = np.asarray(spectrum.get_data(), dtype=float)
    freqs = np.asarray(spectrum.freqs, dtype=float)
    if psds.ndim == 3:
        n_epochs = int(psds.shape[0])
        mean_psds = psds.mean(axis=0)
    else:
        n_epochs = len(selected)
        mean_psds = psds

    return {
        "freqs": freqs,
        "psds": mean_psds,
        # compute_psd 只对数据通道估谱(丢 stim/EOG);ch_names/types 对齐 spectrum 才与 psds 行一一对应
        "ch_names": list(spectrum.ch_names),
        "channel_types": list(selected.get_channel_types(picks=list(spectrum.ch_names))),
        "sfreq": float(selected.info["sfreq"]),
        "n_epochs": n_epochs,
        "method": reported_method,
        "band_powers": _band_powers(np, freqs, mean_psds),
        "condition": labels[0] if len(labels) == 1 else ",".join(labels),
    }


def _run_psd_continuous(raw: Any, params: dict[str, Any]) -> dict[str, Any]:
    """连续 Raw 整段估 PSD(无 condition / 无 epoch 平均),用于静息态等无事件数据。"""
    import numpy as np  # noqa: PLC0415

    channels = params.get("channels")
    selected = raw
    if isinstance(channels, list) and channels:
        normalized = [str(channel) for channel in channels if str(channel).strip()]
        missing_channels = [channel for channel in normalized if channel not in raw.ch_names]
        if missing_channels:
            raise ValueError(f"PSD channels not found: {', '.join(missing_channels)}")
        selected = raw.copy().pick(normalized)

    fmin = float(params.get("fmin", 1.0))
    fmax = float(params.get("fmax", 40.0))
    if fmax <= fmin:
        raise ValueError("PSD.fmax must be greater than fmin.")
    nyquist = float(selected.info["sfreq"]) / 2.0
    fmax = min(fmax, nyquist - 1e-6)
    if fmax <= fmin:
        raise ValueError(f"PSD.fmax({fmax:.3g}) must stay below Nyquist and above fmin({fmin:.3g}).")

    # method=fft 用整段点数把 Welch 退化成单段周期图(满频率分辨率)
    psd_kwargs, reported_method = _psd_kwargs(params, fmin, fmax, int(selected.n_times))

    # RawSpectrum.get_data() → (n_channels, n_freqs);连续数据无需跨 epoch 平均。
    spectrum = selected.compute_psd(**psd_kwargs)
    psds = np.asarray(spectrum.get_data(), dtype=float)
    freqs = np.asarray(spectrum.freqs, dtype=float)

    return {
        "freqs": freqs,
        "psds": psds,
        # compute_psd 只对数据通道估谱(丢 stim/EOG);ch_names/types 对齐 spectrum 才与 psds 行一一对应
        "ch_names": list(spectrum.ch_names),
        "channel_types": list(selected.get_channel_types(picks=list(spectrum.ch_names))),
        "sfreq": float(selected.info["sfreq"]),
        "n_epochs": 0,
        "method": reported_method,
        "band_powers": _band_powers(np, freqs, psds),
        "condition": None,
    }


def _psd_kwargs(params: dict[str, Any], fmin: float, fmax: float, n_times: int) -> tuple[dict[str, Any], str]:
    """构造 compute_psd kwargs,返回 (kwargs, 上报 method 名)。

    method:
      welch(默认)/ multitaper —— 常规宽带谱。
      fft —— 单段整段周期图:底层走 Welch 但 n_per_seg=整段、不重叠,频率分辨率拉满(=1/时长),
             用于 SSVEP / 窄带稳态等"盯单个刺激频率点"的分析(Welch 分段会牺牲频率分辨率)。
    """
    method = str(params.get("method", "welch") or "welch").strip().lower()
    if method not in ("welch", "multitaper", "fft"):
        method = "welch"
    if method == "fft":
        seg = max(1, int(n_times))
        return (
            {"method": "welch", "fmin": fmin, "fmax": fmax, "verbose": "ERROR",
             "n_fft": seg, "n_per_seg": seg, "n_overlap": 0},
            "fft",
        )
    kwargs: dict[str, Any] = {"method": method, "fmin": fmin, "fmax": fmax, "verbose": "ERROR"}
    if method == "welch":
        n_fft = params.get("n_fft")
        if n_fft not in (None, ""):
            kwargs["n_fft"] = int(n_fft)
    return kwargs, method


# 标准频带(Hz),与 psd_view 显示层一致
_PSD_BANDS: tuple[tuple[str, float, float], ...] = (
    ("delta", 1.0, 4.0),
    ("theta", 4.0, 8.0),
    ("alpha", 8.0, 13.0),
    ("beta", 13.0, 30.0),
    ("gamma", 30.0, 80.0),
)


def _band_powers(np: Any, freqs: Any, psds: Any) -> list[dict[str, Any]]:
    """线性域积分各频段绝对功率(µV²) + 相对功率(频段/所分析全谱),跨通道取均值进 preview。

    严格用梯形积分(∑PSD·Δf),不是显示层那种"dB 域求平均";相对功率必须在线性域算(dB 不能相除)。
    相对功率分母 = 当前分析频率范围内的总功率(常规做法,非 0..Nyquist 全频)。
    完整 per-channel 频段功率(可下游/导出)留给将来的专门 band_power 节点。
    """
    freqs = np.asarray(freqs, dtype=float)
    psds = np.asarray(psds, dtype=float)
    if psds.ndim == 1:
        psds = psds[None, :]
    if freqs.size < 2:
        return []
    total = np.trapz(psds, freqs, axis=1)  # (n_channels,) 全谱总功率
    out: list[dict[str, Any]] = []
    for name, lo, hi in _PSD_BANDS:
        mask = (freqs >= lo) & (freqs < hi)
        if not bool(mask.any()):
            continue
        abs_power = np.trapz(psds[:, mask], freqs[mask], axis=1)  # (n_channels,) V²
        with np.errstate(divide="ignore", invalid="ignore"):
            rel = np.where(total > 0, abs_power / total, 0.0)
        out.append({
            "name": name,
            "fmin": lo,
            "fmax": hi,
            "abs_power_uv2": float(np.mean(abs_power) * 1e12),  # 跨通道均值, µV²
            "rel_power": float(np.mean(rel)),                    # 跨通道均值, 0-1
        })
    return out
