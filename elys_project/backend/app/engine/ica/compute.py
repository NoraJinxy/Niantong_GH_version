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

    # n_components 未指定时按【有效秩】自动降维:平均参考(秩降1)与坏道插值(插值道≈邻道线性组合)
    # 会让数据秩亏,若仍按满通道数解 ICA,多出来的"虚秩"会被劈成镜像 ghost 成分,污染 ICLabel 与
    # 去伪迹(Makoto/Delorme 反复警告)。这里不增加任何用户旋钮,默认就把上限收到有效秩。
    if n_components is None:
        n_components = _effective_rank(mne, raw, picks)

    decim = _resolve_decim(params.get("decim"), raw, len(picks))
    fit_params = _resolve_fit_params(method)
    # ICA 在高通副本上训练(解混矩阵随后由 Apply 套回原数据),兼顾分解质量与慢波保真。
    fit_raw = _apply_fit_highpass(raw, params.get("fit_highpass"))

    ica = mne.preprocessing.ICA(
        n_components=n_components,
        method=method,
        random_state=random_state,
        max_iter="auto",
        fit_params=fit_params,
    )
    ica.fit(fit_raw, picks=picks, decim=decim, verbose="ERROR")
    return ica


def _apply_fit_highpass(raw: Any, value: Any) -> Any:
    """ICA 标准做法(Winkler 2015 / Makoto):在 ~1Hz 高通副本上拟合 ICA。

    慢漂移会拖垮 ICA 分解,但 ERP 又需要保留 0.1Hz 的慢成分——二者矛盾。解法是"训练/应用解耦":
    ICA 只在这个 1Hz 高通副本上学解混矩阵,而 Apply 节点把矩阵套回未额外高通的原数据,故最终数据
    的低频/慢成分不受影响。默认 1.0Hz;数据本就高通到 ≥该值则不重复滤(幂等);设 0 / 空 = 不额外
    高通、按原样训练(供专家覆盖)。这是默认行为,用户无需配置即得到高质量分解。
    """
    if value in (None, ""):
        fit_hp = 1.0
    else:
        try:
            fit_hp = float(value)
        except (TypeError, ValueError):
            fit_hp = 1.0
    if fit_hp <= 0:
        return raw
    current_hp = float(raw.info.get("highpass") or 0.0)
    if current_hp >= fit_hp:
        return raw
    return raw.copy().load_data().filter(l_freq=fit_hp, h_freq=None, verbose="ERROR")


def _effective_rank(mne: Any, raw: Any, picks: Any) -> int:
    """估算送入 ICA 的 EEG 数据有效秩(用作 n_components 上限),消除秩亏导致的 ghost 成分。

    两道防线取较小者:
      ① 数值秩 mne.compute_rank:从数据本身估,能反映坏道插值/平均参考造成的近似线性相关;
      ② 平均参考显式扣 1:CAR 用 projection=False 时数据严格秩降 1,但浮点噪声可能让数值秩漏判,
         故只要 info['custom_ref_applied'] 为真就再保险地把上限钳到 n_pick−1。
    """
    n_pick = int(len(picks))
    eff = n_pick
    try:
        sub = raw.copy().pick([raw.ch_names[i] for i in picks])
        ranks = mne.compute_rank(sub, rank=None, verbose="ERROR")
        if isinstance(ranks, dict) and ranks:
            eff = min(eff, int(min(ranks.values())))
    except Exception:  # noqa: BLE001 — 估秩失败不该挡住 ICA,退回满通道数(MNE.fit 内部还会再估一次)
        pass
    if bool(raw.info.get("custom_ref_applied", False)):
        eff = min(eff, n_pick - 1)
    return max(1, min(eff, n_pick))


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
