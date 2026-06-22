"""
Purpose: Run ICA compute/apply operations for Pipeline nodes in the EEG engine.
Related: app/pipeline/dispatcher.py, app/pipeline/nodes/eeg_ica_*.json, docs_v2/5-00.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def run_compute_ica(raw: Any, params: dict[str, Any]):
    mne = _mne()
    n_components = _parse_n_components(params.get("n_components"), len(raw.ch_names))
    method = str(params.get("method") or "picard")
    random_state = params.get("random_state", 42)
    picks = mne.pick_types(raw.info, meg=True, eeg=True, eog=False, ecg=False, stim=False, exclude="bads")
    if len(picks) < 2:
        raise ValueError("ICA requires at least two EEG/MEG channels.")
    if n_components is not None and n_components > len(picks):
        raise ValueError(f"n_components={n_components} exceeds picked channel count {len(picks)}.")

    decim = _resolve_decim(params.get("decim"), raw, len(picks))
    fit_params = _resolve_fit_params(method)

    ica = mne.preprocessing.ICA(
        n_components=n_components,
        method=method,
        random_state=random_state,
        max_iter="auto",
        fit_params=fit_params,
    )
    ica.fit(raw, picks=picks, decim=decim, verbose="ERROR")
    return ica


def _resolve_fit_params(method: str) -> dict[str, Any] | None:
    # Picard 默认是 FastICA 风格(ortho=True)；切到 extended-infomax 风格,既快又喂得饱下游 ICLabel
    # (ICLabel 训练于 extended-infomax)。其它方法走 MNE 默认。
    if method == "picard":
        return {"ortho": False, "extended": True}
    return None


def _resolve_decim(value: Any, raw: Any, n_channels: int) -> int | None:
    """把数据抽稀后再喂 ICA 以省算力。

    - 默认(value 为空)按「目标有效采样率 ~125Hz」自适应:本来就低采样率的数据基本不动。
    - 兜底「样本数地板」:抽完若总样本 < k×通道²(ICA 估稳定解混矩阵的经验下限),自动退回不抽,
      宁可慢也不喂不饱、解出垃圾成分。
    - 用户显式填 1 = 关闭抽取(复刻老行为);填具体因子则尊重,但仍受样本地板保护。
    """
    sfreq = float(getattr(getattr(raw, "info", None), "sfreq", 0.0) or 0.0)
    n_times = int(getattr(raw, "n_times", 0) or 0)
    if sfreq <= 0 or n_times <= 0:
        return None

    if value in (None, "", "auto", "null"):
        target_hz = 125.0
        decim = max(1, round(sfreq / target_hz))
    else:
        decim = max(1, int(value))

    if decim <= 1:
        return None

    # 样本地板:k=25 × 通道²(取 20–30 经验区间的中段)
    min_samples = 25 * n_channels * n_channels
    while decim > 1 and (n_times // decim) < min_samples:
        decim -= 1

    return decim if decim > 1 else None


def summarize_ica(ica: Any, raw: Any | None = None) -> dict[str, Any]:
    return {
        "data_type": "ica",
        "method": getattr(ica, "method", None),
        "n_components": int(getattr(ica, "n_components_", 0) or 0),
        "n_pca_components": _safe_int(getattr(ica, "n_pca_components", None)),
        "exclude": list(getattr(ica, "exclude", []) or []),
        "components": component_preview(ica, raw),
    }


def component_preview(ica: Any, raw: Any | None = None, *, limit: int | None = None) -> list[dict[str, Any]]:
    n_components = int(getattr(ica, "n_components_", 0) or 0)
    if limit is None:
        limit = n_components

    component_matrix = _component_matrix(ica)
    source_stats = _source_stats(ica, raw)
    previews: list[dict[str, Any]] = []
    for index in range(min(n_components, max(0, limit))):
        top_channels = _top_channels(component_matrix, ica, index)
        stats = source_stats.get(index, {})
        previews.append(
            {
                "index": index,
                "label": f"IC{index:03d}",
                "std": stats.get("std"),
                "max_abs": stats.get("max_abs"),
                "top_channels": top_channels,
            }
        )
    return previews


def _parse_n_components(value: Any, channel_count: int) -> int | float | None:
    if value in (None, "", "null"):
        return None
    if isinstance(value, float) and 0 < value < 1:
        return value
    parsed = int(value)
    if parsed < 1:
        raise ValueError("n_components must be positive.")
    if parsed > channel_count:
        raise ValueError(f"n_components={parsed} exceeds channel count {channel_count}.")
    return parsed


def _component_matrix(ica: Any) -> np.ndarray | None:
    try:
        return np.asarray(ica.get_components())
    except Exception:
        return None


def _source_stats(ica: Any, raw: Any | None) -> dict[int, dict[str, float]]:
    if raw is None:
        return {}
    try:
        data = np.asarray(ica.get_sources(raw).get_data())
    except Exception:
        return {}
    stats: dict[int, dict[str, float]] = {}
    for index, series in enumerate(data):
        stats[index] = {
            "std": float(np.std(series)),
            "max_abs": float(np.max(np.abs(series))) if series.size else 0.0,
        }
    return stats


def _top_channels(component_matrix: np.ndarray | None, ica: Any, component_index: int, *, limit: int = 5) -> list[str]:
    if component_matrix is None or component_matrix.ndim != 2 or component_index >= component_matrix.shape[1]:
        return []
    names = list(getattr(getattr(ica, "info", None), "ch_names", []) or [])
    if not names:
        names = [f"CH{index + 1:03d}" for index in range(component_matrix.shape[0])]
    weights = np.abs(component_matrix[:, component_index])
    ranked = np.argsort(weights)[::-1][:limit]
    return [str(names[index]) for index in ranked if index < len(names)]


def _safe_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def _mne():
    try:
        import mne
    except ImportError as exc:
        raise RuntimeError("MNE is required for ICA pipeline nodes.") from exc
    return mne
