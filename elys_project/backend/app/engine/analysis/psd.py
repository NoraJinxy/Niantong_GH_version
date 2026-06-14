"""
Purpose: 对 Epochs 做功率谱密度(PSD)估计(Welch),生成各频段平均功率。
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


def run_psd(epochs: Any, params: dict[str, Any]) -> dict[str, Any]:
    """按 condition 选 Epochs → Welch PSD → 跨 epoch 平均 → 返回数组 dict。

    params:
      condition:   要分析的事件分组名(必填,与 ERP/TFR 同口径;dispatcher 按 condition 逐个展开)。
      fmin / fmax: 频率范围下/上限 Hz(默认 1 / 40)。fmax 会被自动夹到奈奎斯特频率以下。
      method:      "welch"(默认)或 "multitaper"。
      n_fft:       仅 Welch;每段 FFT 点数,留空用 MNE 默认。
      channels:    可选,只算这些通道(默认全通道)。
    """
    import numpy as np  # noqa: PLC0415

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

    method = str(params.get("method", "welch") or "welch").strip().lower()
    if method not in ("welch", "multitaper"):
        method = "welch"
    psd_kwargs: dict[str, Any] = {"method": method, "fmin": fmin, "fmax": fmax, "verbose": "ERROR"}
    if method == "welch":
        n_fft = params.get("n_fft")
        if n_fft not in (None, ""):
            psd_kwargs["n_fft"] = int(n_fft)

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
        "ch_names": list(selected.ch_names),
        "channel_types": list(selected.info.get_channel_types()),
        "sfreq": float(selected.info["sfreq"]),
        "n_epochs": n_epochs,
        "method": method,
        "condition": labels[0] if len(labels) == 1 else ",".join(labels),
    }
