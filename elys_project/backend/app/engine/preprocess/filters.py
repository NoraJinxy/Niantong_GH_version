"""
Purpose: Run EEG preprocessing operations for Pipeline nodes in the MNE-based engine.
Related: app/pipeline/dispatcher.py, app/pipeline/nodes/*.json, docs_v2/5-00.
"""

from __future__ import annotations

from typing import Any


def run_fir_filter(raw: Any, params: dict[str, Any]) -> Any:
    filter_mode = str(params.get("filter_mode") or "bandpass")
    phase = str(params.get("phase") or "zero")
    if phase not in {"zero", "minimum"}:
        raise ValueError("FIR phase must be zero or minimum.")

    l_freq, h_freq = _resolve_freqs(filter_mode, params, "FIR")

    filtered = raw.copy().load_data()
    filtered.filter(l_freq=l_freq, h_freq=h_freq, phase=phase, fir_design="firwin", verbose="ERROR")
    return filtered


def run_butterworth_filter(raw: Any, params: dict[str, Any]) -> Any:
    """IIR Butterworth filter via MNE.

    MNE 的 `method="iir"` 配 `iir_params={"order": N, "ftype": "butter"}` 走 scipy 的 sosfiltfilt（零相位双向），
    跟 FIR 用法风格统一；order 范围 1-12 与节点 spec 一致。
    """
    order_raw = params.get("order")
    try:
        order = int(order_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("Butterworth order must be an integer (1-12).") from exc
    if order < 1 or order > 12:
        raise ValueError("Butterworth order must be between 1 and 12.")

    filter_mode = str(params.get("filter_mode") or "bandpass")
    l_freq, h_freq = _resolve_freqs(filter_mode, params, "Butterworth")

    filtered = raw.copy().load_data()
    filtered.filter(
        l_freq=l_freq,
        h_freq=h_freq,
        method="iir",
        iir_params={"order": order, "ftype": "butter"},
        verbose="ERROR",
    )
    return filtered


def run_notch_filter(raw: Any, params: dict[str, Any]) -> Any:
    """工频陷波（notch）——剔除 50/60Hz 工频及其谐波。

    用法与 FIR / Butterworth 保持一致：raw.copy().load_data() 后调 MNE 的 notch_filter。
    频点优先级：
      - 给了 freqs（逗号分隔字符串 / 列表）→ 直接用这些频点，忽略 freq + harmonics；
      - 否则用 freq（基频）× 1..harmonics 自动展开成 [50, 100, 150 …]。
    """
    explicit = params.get("freqs")
    if explicit not in (None, ""):
        freqs = _parse_freq_list(explicit)
        if not freqs:
            raise ValueError("Notch freqs must contain at least one positive frequency.")
    else:
        freq = _positive_float_or_none(params.get("freq"))
        if freq is None:
            raise ValueError("Notch filter requires a positive freq (line frequency).")
        harmonics_raw = params.get("harmonics")
        try:
            harmonics = int(harmonics_raw) if harmonics_raw not in (None, "") else 1
        except (TypeError, ValueError) as exc:
            raise ValueError("Notch harmonics must be an integer between 1 and 20.") from exc
        if harmonics < 1 or harmonics > 20:
            raise ValueError("Notch harmonics must be between 1 and 20.")
        freqs = [freq * order for order in range(1, harmonics + 1)]

    filtered = raw.copy().load_data()
    filtered.notch_filter(freqs=freqs, verbose="ERROR")
    return filtered


def _parse_freq_list(value: Any) -> list[float]:
    """把 "50, 100; 150" 或 [50, 100] 这样的输入解析成正频点列表，跳过非法 / 非正值。"""
    if isinstance(value, (list, tuple)):
        items: list[Any] = list(value)
    else:
        items = str(value).replace(";", ",").split(",")
    freqs: list[float] = []
    for item in items:
        number = _positive_float_or_none(item.strip() if isinstance(item, str) else item)
        if number is not None:
            freqs.append(number)
    return freqs


def _resolve_freqs(filter_mode: str, params: dict[str, Any], label: str) -> tuple[float | None, float | None]:
    """共享的 bandpass/lowpass/highpass cutoff 校验。返回 (l_freq, h_freq) 给 MNE filter() 用。"""
    l_freq = _positive_float_or_none(params.get("l_freq"))
    h_freq = _positive_float_or_none(params.get("h_freq"))
    if filter_mode == "bandpass":
        if l_freq is None or h_freq is None:
            raise ValueError(f"Bandpass {label} filter requires l_freq and h_freq.")
        if l_freq >= h_freq:
            raise ValueError(f"Bandpass {label} filter requires l_freq < h_freq.")
        return l_freq, h_freq
    if filter_mode == "lowpass":
        if h_freq is None:
            raise ValueError(f"Lowpass {label} filter requires h_freq.")
        return None, h_freq
    if filter_mode == "highpass":
        if l_freq is None:
            raise ValueError(f"Highpass {label} filter requires l_freq.")
        return l_freq, None
    raise ValueError(f"{label} filter_mode must be bandpass, lowpass, or highpass.")


def _positive_float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    number = float(value)
    if number <= 0:
        return None
    return number
