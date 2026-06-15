"""
Purpose: 为"ICA 成分交互审阅"提供后端数据——每成分地形图 / 时域波形 / Welch 频谱 / 去除前后对比。
         纯计算函数（入参是已载入的 mne ICA + Raw 对象），便于本地单测；路由层负责解析 artifact、载入对象。
Related: app/routers/study_outputs.py（ica-components 端点）, app/pipeline/montage_layout.py（共用 2D 投影）,
         app/engine/ica/compute.py（component_preview 同源思路）, 参照 Niantong-eeg-analysis/ica_visualization_utils.py。

地形图：把 ICA 解混矩阵每一列（成分在各通道的权重）落到通道 2D 投影坐标上着色（电极散点，与时域看图地形图条同形态，
不做插值热力面——与 elys 既定"插值留出图二期"一致）。
"""

from __future__ import annotations

from typing import Any

from .montage_layout import channel_positions_2d


def _mne():
    try:
        import mne
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("MNE is required for ICA inspection.") from exc
    return mne


def _numpy():
    try:
        import numpy
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("NumPy is required for ICA inspection.") from exc
    return numpy


def _downsample_idx(np, n: int, max_points: int):
    if n <= 0:
        return np.array([], dtype=int)
    count = min(max(2, int(max_points)), int(n))
    return np.unique(np.linspace(0, n - 1, count).astype(int))


def _eeg_names(ica: Any) -> list[str]:
    return [str(name) for name in (getattr(getattr(ica, "info", None), "ch_names", []) or [])]


def _per_component_variance(ica: Any, raw: Any, index: int) -> float | None:
    try:
        evr = ica.get_explained_variance_ratio(raw, components=[index])
        return float(evr.get("eeg", 0.0)) * 100 if isinstance(evr, dict) else None
    except Exception:
        return None


def ica_overview(ica: Any, raw: Any | None = None) -> dict[str, Any]:
    """ICA 总览：成分数 / 方法 / 已排除 / 通道名 / 总解释方差。"""
    n_components = int(getattr(ica, "n_components_", 0) or 0)
    total_var: float | None = None
    if raw is not None:
        try:
            evr = ica.get_explained_variance_ratio(raw)
            total_var = float(evr.get("eeg", 0.0)) * 100 if isinstance(evr, dict) else None
        except Exception:
            total_var = None
    names = _eeg_names(ica)
    return {
        "n_components": n_components,
        "method": getattr(ica, "method", None),
        "exclude": [int(i) for i in (getattr(ica, "exclude", []) or [])],
        "ch_names": names,
        "n_channels": len(names),
        "total_variance_explained": total_var,
    }


def component_topographies(ica: Any, raw: Any | None = None) -> list[dict[str, Any]]:
    """所有成分的地形图数据（成分图网格用）：每成分 = 通道权重落到 2D 坐标 + 解释方差 + 主导通道。

    raw 为 None 时跳过解释方差（地形图本身只需 ICA 解混矩阵 + 通道坐标）。
    """
    np = _numpy()
    names = _eeg_names(ica)
    try:
        comps = np.asarray(ica.get_components())  # (n_channels, n_components)
    except Exception:
        comps = None
    positions = channel_positions_2d(getattr(ica, "info", None), names) or {}
    n_components = int(getattr(ica, "n_components_", 0) or 0)

    out: list[dict[str, Any]] = []
    for index in range(n_components):
        weights = comps[:, index] if (comps is not None and comps.ndim == 2 and index < comps.shape[1]) else None
        topo: list[dict[str, Any]] = []
        vmax = 0.0
        if weights is not None:
            for ci, name in enumerate(names):
                pos = positions.get(name)
                if pos is None or ci >= len(weights):
                    continue
                w = float(weights[ci])
                topo.append({"name": name, "x": pos[0], "y": pos[1], "weight": round(w, 6)})
                vmax = max(vmax, abs(w))
        top_channels: list[str] = []
        if weights is not None:
            order = np.argsort(np.abs(weights))[::-1][:5]
            top_channels = [names[i] for i in order if i < len(names)]
        out.append(
            {
                "index": index,
                "label": f"IC{index:03d}",
                "explained_variance": _per_component_variance(ica, raw, index) if raw is not None else None,
                "vmax": round(vmax, 6),
                "topography": topo,
                "top_channels": top_channels,
                "has_positions": bool(topo),
            }
        )
    return out


def component_detail(
    ica: Any,
    raw: Any,
    index: int,
    *,
    max_seconds: float = 10.0,
    fmax: float = 50.0,
    nperseg_seconds: float = 2.0,
    max_points: int = 2000,
) -> dict[str, Any]:
    """单成分详情：时域波形（下采样）+ Welch 频谱（dB），供详情面板。"""
    np = _numpy()
    from scipy import signal  # noqa: PLC0415

    sources = ica.get_sources(raw).get_data()  # (n_components, n_times)
    n_components = int(sources.shape[0])
    if index < 0 or index >= n_components:
        raise ValueError(f"component index {index} out of range [0, {n_components - 1}]")

    series = np.asarray(sources[index], dtype="float64")
    sfreq = float(raw.info["sfreq"])
    times = np.asarray(raw.times, dtype="float64")
    if max_seconds and max_seconds > 0:
        keep = int(max_seconds * sfreq)
        series = series[:keep]
        times = times[:keep]

    idx = _downsample_idx(np, series.shape[0], max_points)
    tc_times = np.round(times[idx], 5).tolist()
    tc_values = np.round(series[idx], 6).tolist()

    nperseg = min(int(sfreq * nperseg_seconds) or 256, max(1, series.shape[0]))
    freqs, psd = signal.welch(series, sfreq, nperseg=nperseg)
    band = freqs <= fmax
    freqs = freqs[band]
    psd = psd[band]
    power_db = 10.0 * np.log10(psd + 1e-12)

    return {
        "index": index,
        "label": f"IC{index:03d}",
        "explained_variance": _per_component_variance(ica, raw, index),
        "sfreq": sfreq,
        "timecourse": {"times": tc_times, "values": tc_values},
        "spectrum": {
            "frequencies": np.round(freqs, 4).tolist(),
            "power_db": np.round(power_db, 4).tolist(),
            "fmax": float(fmax),
        },
    }


def spatial_comparison(
    ica: Any,
    raw: Any,
    excluded: list[int],
    *,
    channel: str | None = None,
    seconds: float = 5.0,
    max_points: int = 2000,
) -> dict[str, Any]:
    """去除前后对比：在某通道上画"原始 vs 排除选定成分后"的波形，让用户确认清洗效果。"""
    np = _numpy()
    excluded = sorted({int(i) for i in (excluded or []) if int(i) >= 0})
    if not excluded:
        return {"has_comparison": False, "message": "未选择要去除的成分"}

    ch_names = list(raw.ch_names)
    if not ch_names:
        return {"has_comparison": False, "message": "数据无通道"}
    ch_idx = ch_names.index(channel) if (channel and channel in ch_names) else 0

    sfreq = float(raw.info["sfreq"])
    original = np.asarray(raw.get_data(picks=[ch_idx])[0], dtype="float64")

    ica_copy = ica.copy()
    ica_copy.exclude = excluded
    clean_raw = raw.copy()
    ica_copy.apply(clean_raw, verbose="ERROR")
    filtered = np.asarray(clean_raw.get_data(picks=[ch_idx])[0], dtype="float64")

    keep = min(int(seconds * sfreq), original.shape[0]) if seconds and seconds > 0 else original.shape[0]
    times = np.asarray(raw.times[:keep], dtype="float64")
    idx = _downsample_idx(np, keep, max_points)
    return {
        "has_comparison": True,
        "channel_name": ch_names[ch_idx],
        "channel_index": ch_idx,
        "components_removed": excluded,
        "times": np.round(times[idx], 5).tolist(),
        "original": np.round(original[:keep][idx], 6).tolist(),
        "filtered": np.round(filtered[:keep][idx], 6).tolist(),
    }


# ---- 端点包装层：解析 artifact 路径 + 载入对象，再调上面的纯函数 ------------------
# 这里才 import previews / io（带 storage/config 重依赖），用惰性 import 让本模块顶层保持轻、
# 上面的纯函数可被单测直接 exec。


def _load_source_raw(study: Any, artifact: Any):
    """从 ICA artifact 的 preview_json.source_ref 回溯并载入源 raw；取不到 → None。"""
    from app.engine.io import read_raw_from_data_info  # noqa: PLC0415

    preview = getattr(artifact, "preview_json", None)
    source_ref = preview.get("source_ref") if isinstance(preview, dict) else None
    if not isinstance(source_ref, dict):
        return None
    ref = dict(source_ref)
    ref.setdefault("study_id", getattr(study, "id", None))
    try:
        return read_raw_from_data_info(ref, preload=True)
    except Exception:
        return None


def build_ica_components(study: Any, artifact: Any) -> dict[str, Any]:
    """端点用：解析 ICA artifact 路径载入 ICA（+回溯源 raw），返回总览 + 每成分地形图网格。"""
    from .previews import resolve_study_output_path  # noqa: PLC0415

    mne = _mne()
    ica_path = resolve_study_output_path(study, artifact)
    ica = mne.preprocessing.read_ica(str(ica_path), verbose="ERROR")
    raw = _load_source_raw(study, artifact)
    overview = ica_overview(ica, raw)
    return {
        **overview,
        "study_output_id": str(getattr(artifact, "id", "") or ""),
        "has_source_raw": raw is not None,
        "components": component_topographies(ica, raw),
    }


def build_ica_component_detail(
    study: Any,
    artifact: Any,
    index: int,
    *,
    excluded: list[int] | None = None,
    max_seconds: float = 10.0,
    fmax: float = 50.0,
) -> dict[str, Any]:
    """端点用：单成分时域 + 频谱（+可选去除前后对比，需源 raw）。"""
    from .previews import StudyOutputPreviewError, resolve_study_output_path  # noqa: PLC0415

    mne = _mne()
    ica_path = resolve_study_output_path(study, artifact)
    ica = mne.preprocessing.read_ica(str(ica_path), verbose="ERROR")
    raw = _load_source_raw(study, artifact)
    if raw is None:
        raise StudyOutputPreviewError(
            "ICA_SOURCE_RAW_UNAVAILABLE",
            "源 raw 不可用，无法计算成分时序 / 频谱 / 去除前后对比。",
            status_code=409,
        )
    detail = component_detail(ica, raw, index, max_seconds=max_seconds, fmax=fmax)
    excluded = [int(i) for i in (excluded or [])]
    if excluded:
        detail["comparison"] = spatial_comparison(ica, raw, excluded)
    return detail
