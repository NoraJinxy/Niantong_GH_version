"""
Purpose: 对 Epochs 做时频分解(Morlet 小波),生成 AverageTFR(时频功率谱)结果。
Related: app/pipeline/dispatcher.py, app/pipeline/nodes/eeg_analysis_tfr.json,
         app/engine/io.py(save_tfr_h5 / summarize_tfr), app/pipeline/tfr_view.py.

时频分析(time-frequency / TFR):把每个 trial 的信号在「时间 × 频率」两个维度上展开,看某段
时间里哪些频段的能量(功率)升高或降低。对运动想象(MI)等范式,关注的就是 α/β 频段在动作
前后的能量变化(ERD/ERS)。这里用 Morlet 小波逐 epoch 算功率再平均(= 总功率,含诱发+诱导),
是脑电时频最常用的做法。
"""

from __future__ import annotations

from typing import Any

from .erp import _normalize_event_labels


def run_tfr(epochs: Any, params: dict[str, Any]) -> Any:
    """按 condition 选 Epochs → Morlet 小波时频分解 → 基线校正 → 返回 AverageTFR。

    params:
      condition:      要分析的事件分组名(必填,与 ERP 同口径;dispatcher 按 condition 逐个展开)。
      fmin / fmax:    频率范围下/上限 Hz(默认 4 / 40)。fmax 会被自动夹到奈奎斯特频率以下。
      n_freqs:        频率点数(默认 30),在 [fmin, fmax] 上等距取点。
      n_cycles_factor:小波周期数 = freqs × factor(默认 0.5,即 n_cycles = freqs/2 的经典启发式)。
      decim:          时间抽取因子(默认 4),把输出时间点降采样以省内存/算力。
      baseline_mode:  基线归一化方式(默认 logratio,展示时换算成 dB);"none" 表示不做基线校正。
      baseline_tmin / baseline_tmax: 基线窗(秒)。tmin 缺省时用 epoch 起点,tmax 默认 0(刺激前)。
      channels:       可选,只算这些通道(默认全通道)。
    """
    mne = _mne()
    import numpy as np  # noqa: PLC0415

    labels = _normalize_event_labels(params.get("condition"))
    if not labels:
        raise ValueError("TFR.condition is required.")

    event_id_map = dict(getattr(epochs, "event_id", {}) or {})
    available = set(event_id_map)
    missing = [label for label in labels if label not in available]
    if missing:
        available_text = ", ".join(sorted(available)) or "none"
        raise ValueError(f"TFR condition not found: {missing}. Available conditions: {available_text}")

    # 与 ERP 同样绕过 MNE 的 "/" 层级标签解释,直接按数字 event id 过滤,行为最确定。
    target_ids = {event_id_map[label] for label in labels}
    events_arr = getattr(epochs, "events", None)
    if events_arr is None or len(events_arr) == 0:
        raise ValueError(f"TFR source epochs has no events for conditions: {labels}")
    mask_indices = [i for i, ev in enumerate(events_arr) if int(ev[2]) in target_ids]
    if not mask_indices:
        raise ValueError(f"TFR has no epochs matching conditions: {labels}")
    selected = epochs[mask_indices]

    channels = params.get("channels")
    if isinstance(channels, list) and channels:
        normalized = [str(channel) for channel in channels if str(channel).strip()]
        missing_channels = [channel for channel in normalized if channel not in selected.ch_names]
        if missing_channels:
            raise ValueError(f"TFR channels not found: {', '.join(missing_channels)}")
        selected = selected.copy().pick(normalized)

    fmin = float(params.get("fmin", 4.0))
    fmax = float(params.get("fmax", 40.0))
    if fmax <= fmin:
        raise ValueError("TFR.fmax must be greater than fmin.")
    n_freqs = int(params.get("n_freqs", 30) or 30)
    if n_freqs < 2:
        n_freqs = 2

    nyquist = float(selected.info["sfreq"]) / 2.0
    fmax = min(fmax, nyquist - 1e-6)
    if fmax <= fmin:
        raise ValueError(f"TFR.fmax({fmax:.3g}) must stay below Nyquist and above fmin({fmin:.3g}).")
    freqs = np.linspace(fmin, fmax, n_freqs)

    factor = float(params.get("n_cycles_factor", 0.5) or 0.5)
    n_cycles = np.maximum(freqs * factor, 1.0)

    decim = max(1, int(params.get("decim", 4) or 4))

    power = selected.compute_tfr(
        method="morlet",
        freqs=freqs,
        n_cycles=n_cycles,
        average=True,
        return_itc=False,
        decim=decim,
        verbose="ERROR",
    )

    mode = str(params.get("baseline_mode", "logratio") or "logratio").strip().lower()
    if mode and mode != "none":
        baseline_tmin = params.get("baseline_tmin", None)
        baseline_tmax = params.get("baseline_tmax", 0.0)
        bmin = float(baseline_tmin) if baseline_tmin not in (None, "") else None
        bmax = float(baseline_tmax) if baseline_tmax not in (None, "") else 0.0
        try:
            power.apply_baseline((bmin, bmax), mode=mode, verbose="ERROR")
        except Exception as exc:  # noqa: BLE001 — 基线窗越界等,给清楚的报错
            raise ValueError(f"TFR baseline correction failed (mode={mode}): {exc}") from exc

    # comment 携带 condition,供下游 / 预览标注(与 evoked.comment 同口径)
    power.comment = labels[0] if len(labels) == 1 else ",".join(labels)
    return power


def _mne():
    try:
        import mne
    except ImportError as exc:
        raise RuntimeError("MNE is required for time-frequency analysis.") from exc
    return mne
