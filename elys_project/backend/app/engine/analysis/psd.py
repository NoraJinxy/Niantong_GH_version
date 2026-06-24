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
    sfreq = float(selected.info["sfreq"])
    psd_kwargs, reported_method = _psd_kwargs(params, fmin, fmax, int(len(selected.times)), sfreq)

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

    result: dict[str, Any] = {
        "freqs": freqs,
        "psds": mean_psds,
        # compute_psd 只对数据通道估谱(丢 stim/EOG);ch_names/types 对齐 spectrum 才与 psds 行一一对应
        "ch_names": list(spectrum.ch_names),
        "channel_types": list(selected.get_channel_types(picks=list(spectrum.ch_names))),
        "sfreq": sfreq,
        "n_epochs": n_epochs,
        "method": reported_method,
        "band_powers": _band_powers(np, freqs, mean_psds),
        # 相对功率分母口径透明化:分母=分析频段(fmin..fmax)总功率(常规做法)。显式标注让分母可审计,
        # 用户改 fmax 时知道所有 rel_power 都随之变化(分母变了),非数据本身波动。
        "rel_power_basis": {"kind": "analysis_range", "fmin": round(fmin, 6), "fmax": round(fmax, 6)},
        "condition": labels[0] if len(labels) == 1 else ",".join(labels),
    }
    aperiodic = _aperiodic_fit(np, freqs, mean_psds, fmin, fmax)
    if aperiodic is not None:
        result["aperiodic"] = aperiodic
    return result


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
    sfreq = float(selected.info["sfreq"])
    psd_kwargs, reported_method = _psd_kwargs(params, fmin, fmax, int(selected.n_times), sfreq)

    # RawSpectrum.get_data() → (n_channels, n_freqs);连续数据无需跨 epoch 平均。
    spectrum = selected.compute_psd(**psd_kwargs)
    psds = np.asarray(spectrum.get_data(), dtype=float)
    freqs = np.asarray(spectrum.freqs, dtype=float)

    result: dict[str, Any] = {
        "freqs": freqs,
        "psds": psds,
        # compute_psd 只对数据通道估谱(丢 stim/EOG);ch_names/types 对齐 spectrum 才与 psds 行一一对应
        "ch_names": list(spectrum.ch_names),
        "channel_types": list(selected.get_channel_types(picks=list(spectrum.ch_names))),
        "sfreq": sfreq,
        "n_epochs": 0,
        "method": reported_method,
        "band_powers": _band_powers(np, freqs, psds),
        # 相对功率分母口径透明化:分母=分析频段(fmin..fmax)总功率(常规做法),显式标注让分母可审计。
        "rel_power_basis": {"kind": "analysis_range", "fmin": round(fmin, 6), "fmax": round(fmax, 6)},
        "condition": None,
    }
    aperiodic = _aperiodic_fit(np, freqs, psds, fmin, fmax)
    if aperiodic is not None:
        result["aperiodic"] = aperiodic
    return result


def _psd_kwargs(
    params: dict[str, Any], fmin: float, fmax: float, n_times: int, sfreq: float
) -> tuple[dict[str, Any], str]:
    """构造 compute_psd kwargs,返回 (kwargs, 上报 method 名)。

    method:
      welch(默认)/ multitaper —— 常规宽带谱。
      fft —— 单段整段周期图:底层走 Welch 但 n_per_seg=整段、不重叠,频率分辨率拉满(=1/时长),
             用于 SSVEP / 窄带稳态等"盯单个刺激频率点"的分析(Welch 分段会牺牲频率分辨率)。

    welch 段长/重叠:window_seconds 给了就按它换算每段采样点数 n_per_seg=int(window_seconds*sfreq),
    n_overlap=int(n_per_seg*overlap)(overlap 夹到 [0,0.95));留空=MNE 默认(现状)。段越长频率分辨率越高、
    平滑越少,反之越短。专业旋钮,默认留空走安全默认。
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
        # 段长(秒)→ 每段采样点数;留空=MNE 默认。给了就同时定 n_per_seg + n_overlap。
        window_seconds = params.get("window_seconds")
        if window_seconds not in (None, "") and float(sfreq) > 0:
            n_per_seg = int(float(window_seconds) * float(sfreq))
            # 段长不能超过数据总采样点数:超长(窗比记录还长)会让 MNE 报错。夹到 n_times,
            # 即把过大的 window_seconds 退化成"整段一窗"而非整链失败。
            n_per_seg = min(n_per_seg, int(n_times))
            if n_per_seg >= 1:
                kwargs["n_per_seg"] = n_per_seg
                try:
                    overlap = float(params.get("overlap", 0.5))
                except (TypeError, ValueError):
                    overlap = 0.5
                overlap = min(max(overlap, 0.0), 0.95)  # 夹到 [0,0.95) 区间(0.95 上界刻意排他)
                kwargs["n_overlap"] = int(n_per_seg * overlap)
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

    频带部分覆盖:当频带上界 hi 超过本次实际可达的最高频率(freqs 最大值)时,该频带只积分到
    部分区间(默认 fmax=40 时 "gamma 30-80" 其实只测到 30-40),给该频带 dict 加 "partial": true 与
    "covered_fmax"=实际积分到的上界,避免按完整频带名误导。完全在 freqs 最大值之上的频带(mask 全空)维持现状跳过。
    """
    freqs = np.asarray(freqs, dtype=float)
    psds = np.asarray(psds, dtype=float)
    if psds.ndim == 1:
        psds = psds[None, :]
    if freqs.size < 2:
        return []
    freq_max = float(freqs.max())  # 本次分析实际可达的最高频率
    total = np.trapz(psds, freqs, axis=1)  # (n_channels,) 全谱总功率
    out: list[dict[str, Any]] = []
    for name, lo, hi in _PSD_BANDS:
        mask = (freqs >= lo) & (freqs < hi)
        if not bool(mask.any()):
            continue
        abs_power = np.trapz(psds[:, mask], freqs[mask], axis=1)  # (n_channels,) V²
        with np.errstate(divide="ignore", invalid="ignore"):
            rel = np.where(total > 0, abs_power / total, 0.0)
        entry: dict[str, Any] = {
            "name": name,
            "fmin": lo,
            "fmax": hi,
            "abs_power_uv2": float(np.mean(abs_power) * 1e12),  # 跨通道均值, µV²
            "rel_power": float(np.mean(rel)),                    # 跨通道均值, 0-1
        }
        # 部分覆盖:频带上界 hi 落在分析最高频率之外,只积分到了 freq_max。标注真相,别按完整频带名误导。
        if hi > freq_max:
            entry["partial"] = True
            entry["covered_fmax"] = round(freq_max, 6)
        out.append(entry)
    return out


def _aperiodic_fit(np: Any, freqs: Any, psds: Any, fmin: float, fmax: float) -> dict[str, Any] | None:
    """1/f 非周期成分(aperiodic):跨通道平均 PSD 在分析频段内做 log-log 一次线性拟合。

    对 log10(freqs) vs log10(psd_mean) 拟合直线,得 exponent=-slope(谱越陡 exponent 越大)与 offset。
    这是质量/解释辅助(不改频带功率)——非周期斜率随觉醒水平/年龄/麻醉变化,可粗判信号陡峭程度。
    严格防御:freqs/psd 必须 >0 才取 log(过滤 ≤0);有效点 <3 不算(返回 None)。不引新依赖,只用 numpy。
    """
    freqs = np.asarray(freqs, dtype=float)
    psds = np.asarray(psds, dtype=float)
    if psds.ndim == 1:
        psds = psds[None, :]
    if freqs.size < 3:
        return None
    psd_mean = psds.mean(axis=0)  # (n_freqs,) 跨通道平均 PSD
    valid = (freqs > 0) & (psd_mean > 0) & np.isfinite(freqs) & np.isfinite(psd_mean)
    if int(np.count_nonzero(valid)) < 3:
        return None
    log_f = np.log10(freqs[valid])
    log_p = np.log10(psd_mean[valid])
    try:
        slope, intercept = np.polyfit(log_f, log_p, 1)
    except Exception:  # noqa: BLE001 — 拟合数值异常时不报错,只是不给该辅助键
        return None
    if not (np.isfinite(slope) and np.isfinite(intercept)):
        return None
    return {
        "exponent": float(-slope),
        "offset": float(intercept),
        "fmin": round(float(fmin), 6),
        "fmax": round(float(fmax), 6),
    }
