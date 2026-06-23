"""
Purpose: Run EEG preprocessing operations for Pipeline nodes in the MNE-based engine.
Related: app/pipeline/dispatcher.py, app/pipeline/nodes/*.json, docs_v2/5-00.
"""

from __future__ import annotations

from typing import Any


def run_filter(raw: Any, params: dict[str, Any]) -> Any:
    """统一滤波节点的执行入口：按 filter_type 分派到 MNE 的 filter() 或 notch_filter()。

    filter_type:
      - bandpass / highpass / lowpass → raw.filter()（频谱滤波家族，由 l_freq/h_freq 决定形状）
      - notch                          → raw.notch_filter()（工频陷波，由中心频率 + 谐波决定）
    method:
      - fir（默认，零相位窗函数）/ iir（Butterworth）/ spectrum_fit（仅 notch，正弦拟合减除）

    设计说明：MNE 本就用一个 filter() 管低通 / 高通 / 带通，notch 是独立函数。这里把这两套
    包成一个面向用户的节点，按 filter_type 在引擎内分派——参数形状的差异由 NodeSpec 的
    visible_when 在 UI 层切换，引擎只管按 type 读对应参数。
    """
    filter_type = str(params.get("filter_type") or "bandpass").strip().lower()
    if filter_type == "notch":
        # 陷波默认走谱拟合(spectrum_fit≈CleanLine):把工频当正弦回归减除,只扣窄带、保留邻近频谱,
        # 不像硬陷波那样在 50/100Hz 挖缺口、引入振铃污染 PSD/时频。独立 notch_method,与频谱滤波的
        # method(fir/iir)分开,避免"spectrum_fit 选给带通会报错"的混淆。
        notch_method = str(params.get("notch_method") or "spectrum_fit").strip().lower()
        return _run_notch(raw, params, notch_method)
    method = str(params.get("method") or "fir").strip().lower()
    if filter_type in {"bandpass", "highpass", "lowpass"}:
        return _run_spectral(raw, params, filter_type, method)
    raise ValueError(
        f"Unknown filter_type: {filter_type!r} (expected bandpass/highpass/lowpass/notch)."
    )


def _run_spectral(raw: Any, params: dict[str, Any], filter_type: str, method: str) -> Any:
    """带通 / 高通 / 低通：走 MNE raw.filter()。FIR（默认）或 IIR Butterworth。"""
    if method == "spectrum_fit":
        raise ValueError("spectrum_fit method is only valid for filter_type=notch.")
    if method not in {"fir", "iir"}:
        raise ValueError("Spectral filter method must be fir or iir.")

    l_freq, h_freq = _resolve_freqs(filter_type, params)
    trans = _positive_float_or_none(params.get("trans_bandwidth"))

    kwargs: dict[str, Any] = {"l_freq": l_freq, "h_freq": h_freq, "verbose": "ERROR"}
    if trans is not None:
        # 只给相关那一边设过渡带（高通只有低边、低通只有高边）；留空时 MNE 用 'auto'
        if l_freq is not None:
            kwargs["l_trans_bandwidth"] = trans
        if h_freq is not None:
            kwargs["h_trans_bandwidth"] = trans

    if method == "iir":
        kwargs["method"] = "iir"
        kwargs["iir_params"] = {"order": _resolve_order(params), "ftype": "butter"}
    else:  # fir
        phase = str(params.get("phase") or "zero").strip().lower()
        if phase not in {"zero", "minimum"}:
            raise ValueError("FIR phase must be zero or minimum.")
        kwargs["phase"] = phase
        kwargs["fir_design"] = "firwin"

    filtered = raw.copy().load_data()
    filtered.filter(**kwargs)
    return filtered


def _run_notch(raw: Any, params: dict[str, Any], method: str) -> Any:
    """工频陷波：走 MNE raw.notch_filter()。中心频率 × 谐波展开成 [50, 100, 150 …]。

    采样率定 Nyquist（= sfreq/2，可表示的最高频率）：高于 Nyquist 的谐波物理上根本测不到、
    更无从陷除——128Hz 数据（Nyquist 64）下的 100/150Hz 就是够不着。MNE 碰到这种频率会直接
    报错、连累整条链失败。所以这里先按 Nyquist 把够不着的谐波筛掉，只陷有效的那几个：专家照常
    填 3 次谐波，引擎做物理上做得到的部分，而不是因为一个够不着的谐波把整条链拖垮。
    """
    if method not in {"fir", "iir", "spectrum_fit"}:
        raise ValueError("Notch method must be fir, iir, or spectrum_fit.")
    freq = _positive_float_or_none(params.get("notch_freq"))
    if freq is None:
        raise ValueError("Notch filter requires a positive notch_freq (line frequency).")
    harmonics = _resolve_int(params.get("notch_harmonics"), default=3, lo=1, hi=20, name="notch_harmonics")
    nyquist = float(raw.info["sfreq"]) / 2.0
    freqs = [freq * order for order in range(1, harmonics + 1) if freq * order < nyquist]
    if not freqs:
        raise ValueError(
            f"Notch base frequency {freq:g}Hz is at or above the Nyquist frequency "
            f"{nyquist:g}Hz (sampling rate {nyquist * 2:g}Hz); cannot notch this recording."
        )

    filtered = raw.copy().load_data()
    filtered.notch_filter(freqs=freqs, method=method, verbose="ERROR")
    return filtered


def _resolve_freqs(filter_type: str, params: dict[str, Any]) -> tuple[float | None, float | None]:
    """按 filter_type 解析 (l_freq, h_freq) 给 MNE filter() 用，并做基本校验。"""
    l_freq = _positive_float_or_none(params.get("l_freq"))
    h_freq = _positive_float_or_none(params.get("h_freq"))
    if filter_type == "bandpass":
        if l_freq is None or h_freq is None:
            raise ValueError("Bandpass filter requires both l_freq and h_freq.")
        if l_freq >= h_freq:
            raise ValueError("Bandpass filter requires l_freq < h_freq.")
        return l_freq, h_freq
    if filter_type == "lowpass":
        if h_freq is None:
            raise ValueError("Lowpass filter requires h_freq.")
        return None, h_freq
    if filter_type == "highpass":
        if l_freq is None:
            raise ValueError("Highpass filter requires l_freq.")
        return l_freq, None
    raise ValueError("Spectral filter_type must be bandpass, lowpass, or highpass.")


def _resolve_order(params: dict[str, Any]) -> int:
    raw_order = params.get("order")
    try:
        order = int(raw_order) if raw_order not in (None, "") else 4
    except (TypeError, ValueError) as exc:
        raise ValueError("Butterworth order must be an integer between 1 and 12.") from exc
    if order < 1 or order > 12:
        raise ValueError("Butterworth order must be between 1 and 12.")
    return order


def _resolve_int(value: Any, *, default: int, lo: int, hi: int, name: str) -> int:
    try:
        number = int(value) if value not in (None, "") else default
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer between {lo} and {hi}.") from exc
    if number < lo or number > hi:
        raise ValueError(f"{name} must be between {lo} and {hi}.")
    return number


def _positive_float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    number = float(value)
    if number <= 0:
        return None
    return number
