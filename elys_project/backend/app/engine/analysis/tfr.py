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

from .erp import _normalize_event_labels, _normalized_event_id_map


def run_tfr(epochs: Any, params: dict[str, Any]) -> Any:
    """按 condition 选 Epochs → Morlet 小波时频分解 → 基线校正 → 返回 AverageTFR。

    params:
      condition:      要分析的事件分组名(必填,与 ERP 同口径;dispatcher 按 condition 逐个展开)。
      fmin / fmax:    频率范围下/上限 Hz(默认 4 / 40)。fmax 会被自动夹到奈奎斯特频率以下。
      n_freqs:        频率点数(默认 30),在 [fmin, fmax] 上取点。
      freq_scale:     频率轴刻度("linear"=等距 / "log"=对数等距,默认 linear)。
                      小波 TFR 宽频带时对数更合理(低频密、高频疏)。
      n_cycles_mode:  小波周期数模式("factor"=随频率成比例 / "fixed"=固定周期数,默认 factor)。
      n_cycles_factor:mode=factor 时,n_cycles = freqs × factor(默认 0.5)。
      n_cycles_fixed: mode=fixed 时,所有频率统一用该固定周期数(默认 7)。
                      低频做 delta 时固定周期数频率定位更好。
      decim:          时间抽取因子(默认 4),把输出时间点降采样以省内存/算力。
      baseline_mode:  基线归一化方式(默认 logratio,展示时换算成 dB);"none" 表示不做基线校正。
      baseline_tmin / baseline_tmax: 基线窗(秒)。tmin 缺省时用 epoch 起点,tmax 默认 0(刺激前)。
      channels:       可选,只算这些通道(默认全通道)。
    """
    import numpy as np  # noqa: PLC0415

    labels = _normalize_event_labels(params.get("condition"))
    if not labels:
        raise ValueError("TFR.condition is required.")

    event_id_map = _normalized_event_id_map(epochs)
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

    # 频率轴刻度:linear=等距(默认),log=对数等距(宽频带时低频密高频疏更合理)。
    freq_scale = str(params.get("freq_scale", "linear") or "linear").strip().lower()
    if freq_scale == "log":
        if fmin <= 0:
            raise ValueError("TFR.freq_scale=log requires fmin > 0.")
        freqs = np.logspace(np.log10(fmin), np.log10(fmax), n_freqs)
    else:
        freqs = np.linspace(fmin, fmax, n_freqs)

    # 小波周期数:factor=随频率成比例(经典启发式),fixed=固定周期数(低频 delta 定位更好)。
    n_cycles_mode = str(params.get("n_cycles_mode", "factor") or "factor").strip().lower()
    if n_cycles_mode == "fixed":
        n_cycles_fixed = float(params.get("n_cycles_fixed", 7.0) or 7.0)
        if n_cycles_fixed < 1.0:
            n_cycles_fixed = 1.0
        n_cycles = np.full(freqs.shape, n_cycles_fixed, dtype=float)
    else:
        factor = float(params.get("n_cycles_factor", 0.5) or 0.5)
        n_cycles = np.maximum(freqs * factor, 1.0)

    # 地板回显:np.maximum(...,1.0) 会在低频静默把 n_cycles 抬到 1.0(1 周期 Morlet 频率定位极差)。
    # 这些诊断数值需要在 io.summarize_tfr 里展示——本引擎返回的是 power 对象(非 dict)无法直接带 meta,
    # 故此处只算出真值,经 io_surfacing_needed 报告字段,由编排者串行接线进 result/summarize。
    n_cycles_arr = np.asarray(n_cycles, dtype=float)
    n_cycles_effective_min = float(np.min(n_cycles_arr))
    n_cycles_effective_max = float(np.max(n_cycles_arr))
    n_cycles_floored_count = int(np.count_nonzero(np.isclose(n_cycles_arr, 1.0)))

    decim = max(1, int(params.get("decim", 4) or 4))

    try:
        power = selected.compute_tfr(
            method="morlet",
            freqs=freqs,
            n_cycles=n_cycles,
            average=True,
            return_itc=False,
            decim=decim,
            verbose="ERROR",
        )
    except ValueError as exc:
        # 最常见:小波比信号长(低频 + 高 n_cycles,尤其固定 n_cycles 模式)。翻成可操作中文提示。
        if "longer than the signal" in str(exc):
            raise ValueError(
                f"小波比 epoch 信号还长,无法计算时频:最低频 {freqs[0]:.3g}Hz 配当前 n_cycles 需要的"
                "时长超过了 epoch 长度。解法任一:把 Epoch 切得更长(给低频留缓冲)、调高 fmin、"
                "减小 n_cycles(factor 模式调小系数 / fixed 模式调小固定周期数)。"
            ) from exc
        raise

    mode = str(params.get("baseline_mode", "logratio") or "logratio").strip().lower()
    if mode and mode != "none":
        baseline_tmin = params.get("baseline_tmin", None)
        baseline_tmax = params.get("baseline_tmax", 0.0)
        epoch_start = float(power.times[0])
        epoch_end = float(power.times[-1])
        # baseline_tmin 缺省 = epoch 起点;显式解析,别把 None 甩给 MNE 后再报看不懂的错。
        bmin = float(baseline_tmin) if baseline_tmin not in (None, "") else epoch_start
        bmax = float(baseline_tmax) if baseline_tmax not in (None, "") else 0.0
        # 在交给 MNE 前自检,把「基线窗落在 epoch 之外 / 区间反了」翻译成可操作的提示。
        if bmax <= bmin:
            raise ValueError(
                f"TFR 基线窗非法:[{bmin:.3g}, {bmax:.3g}] 起点必须 < 终点。"
                f"baseline_tmax({bmax:.3g}) 落在 epoch 起点({epoch_start:.3g}) 之前/之上 —— "
                f"基线必须在 epoch 之内。把 Epoch 的 Tmin 调到比 baseline_tmax({bmax:.3g}) 更早,"
                f"或把 baseline_tmax 调大。"
            )
        if bmin < epoch_start - 1e-6 or bmax > epoch_end + 1e-6:
            raise ValueError(
                f"TFR 基线窗 [{bmin:.3g}, {bmax:.3g}] 超出 epoch 范围 [{epoch_start:.3g}, {epoch_end:.3g}];"
                "请把基线窗收进 epoch 内,或相应调整 Epoch 的 Tmin/Tmax。"
            )
        try:
            power.apply_baseline((bmin, bmax), mode=mode, verbose="ERROR")
        except Exception as exc:  # noqa: BLE001 — 兜底:其它基线异常也给清楚的报错
            raise ValueError(f"TFR baseline correction failed (mode={mode}): {exc}") from exc

    # comment 携带 condition,供下游 / 预览标注(与 evoked.comment 同口径)
    power.comment = labels[0] if len(labels) == 1 else ",".join(labels)

    # n_cycles 地板诊断:挂为轻量属性(不改 power.comment、不改返回类型),
    # 编排者可在 io.summarize_tfr 里读取这三个值并显式回显(见 io_surfacing_needed)。
    # MNE 的 power 对象允许附加自定义属性,dispatcher/io 现状不读取故零副作用。
    try:
        power._elys_n_cycles_diag = {
            "n_cycles_effective_min": n_cycles_effective_min,
            "n_cycles_effective_max": n_cycles_effective_max,
            "n_cycles_floored_count": n_cycles_floored_count,
        }
    except Exception:  # noqa: BLE001 — 附加属性失败不影响主结果
        pass
    return power
