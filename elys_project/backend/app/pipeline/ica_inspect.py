"""
Purpose: 为"ICA 成分交互审阅"提供后端数据——每成分地形图 / 时域波形 / Welch 频谱 / 去除前后对比。
         纯计算函数（入参是已载入的 mne ICA + Raw 对象），便于本地单测；路由层负责解析 artifact、载入对象。
Related: app/routers/study_outputs.py（ica-components 端点）, app/pipeline/montage_layout.py（共用 2D 投影）,
         app/engine/ica/compute.py（component_preview 同源思路）, 参照 Niantong-eeg-analysis/ica_visualization_utils.py。

地形图：把 ICA 解混矩阵每一列（成分在各通道的权重）落到通道 2D 投影坐标上着色（电极散点，与时域看图地形图条同形态，
不做插值热力面——与 elys 既定"插值留出图二期"一致）。
"""

from __future__ import annotations

import threading
import time
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


def _all_component_variances(ica: Any, raw: Any, n_components: int) -> dict[int, float]:
    """一次性批量获取所有成分的解释方差（%），替代逐成分调用。"""
    np = _numpy()
    try:
        evr = ica.get_explained_variance_ratio(raw, components=list(range(n_components)))
        if not isinstance(evr, dict):
            return {}
        arr = evr.get("eeg")
        if arr is None:
            return {}
        arr = np.asarray(arr).ravel()
        return {int(i): float(v) * 100 for i, v in enumerate(arr)}
    except Exception:
        return {}


def _per_component_variance(ica: Any, raw: Any, index: int) -> float | None:
    try:
        evr = ica.get_explained_variance_ratio(raw, components=[index])
        return float(evr.get("eeg", 0.0)) * 100 if isinstance(evr, dict) else None
    except Exception:
        return None


# ICLabel 七分类标签 → (类别键, 中文名)；与 engine/ica/iclabel.py 同源七分类（此处仅展示用）。
_ICLABEL_CATEGORY: dict[str, tuple[str, str]] = {
    "brain": ("brain", "脑"),
    "muscle artifact": ("muscle", "肌电"),
    "eye blink": ("eye", "眼动"),
    "heart beat": ("heart", "心电"),
    "line noise": ("line_noise", "工频"),
    "channel noise": ("channel_noise", "坏导"),
    "other": ("other", "其它"),
}
# 可剔除的五类伪迹（brain / other 永不建议剔除）
_ICLABEL_ARTIFACT = {"muscle", "eye", "heart", "line_noise", "channel_noise"}


def classify_iclabel(ica: Any, raw: Any, *, threshold: float = 0.8) -> dict[int, dict[str, Any]]:
    """best-effort ICLabel 分类：复用 mne-icalabel 的 label_components（仅分类、不清洗），
    返回 {成分序号: {category, label_cn, probability, suggested}}。

    suggested=该成分是伪迹类且置信度≥阈值（默认 0.8）→ 建议剔除（auto-flag 不 auto-delete）。
    任何失败（缺 mne-icalabel / 无 montage / 非 EEG / 模型加载失败）都吞掉返回 {}，
    页面照常出（只是没有自动标签），不因辅助功能拖垮主流程。
    """
    if raw is None:
        return {}
    try:
        from mne_icalabel import label_components  # noqa: PLC0415
    except Exception:
        return {}
    try:
        result = label_components(raw, ica, method="iclabel")
    except Exception:
        return {}
    labels = list(result.get("labels") or [])
    proba = result.get("y_pred_proba")
    probs = [float(p) for p in proba] if proba is not None else []
    out: dict[int, dict[str, Any]] = {}
    for i, raw_label in enumerate(labels):
        category, label_cn = _ICLABEL_CATEGORY.get(str(raw_label).strip().lower(), ("other", "其它"))
        p = probs[i] if i < len(probs) else None
        suggested = category in _ICLABEL_ARTIFACT and p is not None and p >= threshold
        out[i] = {
            "category": category,
            "label_cn": label_cn,
            "probability": round(p, 4) if p is not None else None,
            "suggested": suggested,
        }
    return out


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

    # 批量获取解释方差（一次调用取代 n_components 次，大幅降低响应时间）
    variances: dict[int, float] = _all_component_variances(ica, raw, n_components) if raw is not None else {}

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
                "explained_variance": variances.get(index),
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
    """去除前后对比：在某通道上画"原始 vs 排除选定成分后"的波形，让用户确认清洗效果。

    excluded 为空 → 去除后 = 原始（让初始 / 未勾选成分时也显示原始信号，蓝线与灰线重合），
    而不是返回空白——用户一进来就能看到该通道的原始波形作参照。
    """
    np = _numpy()
    excluded = sorted({int(i) for i in (excluded or []) if int(i) >= 0})

    ch_names = list(raw.ch_names)
    if not ch_names:
        return {"has_comparison": False, "message": "数据无通道"}
    ch_idx = ch_names.index(channel) if (channel and channel in ch_names) else 0

    sfreq = float(raw.info["sfreq"])
    original = np.asarray(raw.get_data(picks=[ch_idx])[0], dtype="float64")

    if excluded:
        ica_copy = ica.copy()
        ica_copy.exclude = excluded
        clean_raw = raw.copy()
        ica_copy.apply(clean_raw, verbose="ERROR")
        filtered = np.asarray(clean_raw.get_data(picks=[ch_idx])[0], dtype="float64")
    else:
        filtered = original.copy()

    keep = min(int(seconds * sfreq), original.shape[0]) if seconds and seconds > 0 else original.shape[0]
    times = np.asarray(raw.times[:keep], dtype="float64")
    idx = _downsample_idx(np, keep, max_points)
    # 方差降幅：该通道去除前后信号方差减少多少（%）——给一个"整体清掉了多少"的量化读数。
    orig_keep = original[:keep]
    filt_keep = filtered[:keep]
    var_o = float(np.var(orig_keep)) if orig_keep.size else 0.0
    var_f = float(np.var(filt_keep)) if filt_keep.size else 0.0
    var_reduction = ((var_o - var_f) / var_o * 100.0) if var_o > 0 else 0.0
    return {
        "has_comparison": True,
        "channel_name": ch_names[ch_idx],
        "channel_index": ch_idx,
        "components_removed": excluded,
        "variance_reduction": round(var_reduction, 1),
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


# ── ICA 加载缓存（进程内）：三个 ICA 端点共享 ───────────────────────────────────
# 痛点：成分网格 / 单成分详情 / 去除前后预览各自从磁盘重读整个源 raw（preload）+ 重跑 ICLabel，
# 又慢又重复。这里按 artifact 内容身份（sha256，缺则 id）缓存「已载入的 (ica, raw) 对象 + 网格结果」，
# 让首屏后的点选 / 勾选 / 重开都走内存。进程内、带 TTL + 容量上限（raw 对象大，只留几个）；
# mne 对象只读复用——detail/preview 的 apply/copy 都在副本上做，不污染缓存原件。
_ICA_CACHE: dict[str, dict[str, Any]] = {}
_ICA_CACHE_LOCK = threading.Lock()
_ICA_CACHE_TTL_SECONDS = 600.0  # 10 分钟未访问即失效
_ICA_CACHE_MAX_ENTRIES = 3  # raw 对象占内存，最多并存 3 个数据集


def _ica_cache_key(artifact: Any) -> str:
    sha = getattr(artifact, "sha256", None)
    return f"sha:{sha}" if sha else f"id:{getattr(artifact, 'id', '')}"


def _ica_cache_get(key: str) -> dict[str, Any] | None:
    with _ICA_CACHE_LOCK:
        entry = _ICA_CACHE.get(key)
        if entry is None:
            return None
        if time.time() - entry.get("ts", 0) > _ICA_CACHE_TTL_SECONDS:
            _ICA_CACHE.pop(key, None)
            return None
        entry["ts"] = time.time()  # 触碰续期
        return entry


def _ica_cache_set(key: str, entry: dict[str, Any]) -> None:
    with _ICA_CACHE_LOCK:
        entry["ts"] = time.time()
        _ICA_CACHE[key] = entry
        if len(_ICA_CACHE) > _ICA_CACHE_MAX_ENTRIES:
            stale = sorted(_ICA_CACHE.items(), key=lambda kv: kv[1].get("ts", 0))
            for old_key, _entry in stale[: len(_ICA_CACHE) - _ICA_CACHE_MAX_ENTRIES]:
                _ICA_CACHE.pop(old_key, None)


def _ensure_ica(study: Any, artifact: Any) -> tuple[str, Any, dict[str, Any]]:
    """载入 ICA 矩阵（轻，不碰源 raw），命中缓存复用。返回 (key, ica, entry)。"""
    from .previews import resolve_study_output_path  # noqa: PLC0415

    key = _ica_cache_key(artifact)
    entry = _ica_cache_get(key) or {}
    if entry.get("ica") is None:
        mne = _mne()
        entry["ica"] = mne.preprocessing.read_ica(str(resolve_study_output_path(study, artifact)), verbose="ERROR")
        _ica_cache_set(key, entry)
    return key, entry["ica"], entry


def _ensure_raw(study: Any, artifact: Any, key: str, entry: dict[str, Any]) -> Any:
    """惰性载入源 raw（preload 整份 FIF，重活），命中缓存复用。raw=None 也记 raw_loaded、不反复重试。"""
    if not entry.get("raw_loaded"):
        entry["raw"] = _load_source_raw(study, artifact)
        entry["raw_loaded"] = True
        _ica_cache_set(key, entry)
    return entry.get("raw")


def _has_source_ref(artifact: Any) -> bool:
    """不载入 raw、仅看 preview_json 是否带 source_ref（供快路径标注 has_source_raw）。"""
    preview = getattr(artifact, "preview_json", None)
    return isinstance(preview, dict) and isinstance(preview.get("source_ref"), dict)


def build_ica_components(study: Any, artifact: Any) -> dict[str, Any]:
    """端点用（**快路径**）：只载 ICA 矩阵 → 出成分地形图网格，**不碰源 raw、不跑 ICLabel**，让首屏秒出。

    地形图只需解混矩阵 + 电极坐标（与 raw 无关）；方差% / ICLabel 标签 / 自动建议由
    build_ica_labels（`/labels` 端点）在网格显示后异步补。结果按 artifact 内容身份缓存。
    """
    key, ica, entry = _ensure_ica(study, artifact)
    if entry.get("grid_result") is not None:
        return entry["grid_result"]

    overview = ica_overview(ica, None)  # 不传 raw → 跳过总方差（异步补）
    components = component_topographies(ica, None)  # 不传 raw → 地形图秒出、无方差
    result = {
        **overview,
        "study_output_id": str(getattr(artifact, "id", "") or ""),
        "has_source_raw": _has_source_ref(artifact),
        "iclabel_available": False,  # 占位：标签由 /labels 异步补
        "suggested_exclude": [],
        "labels_pending": _has_source_ref(artifact),  # 提示前端去拉 /labels
        "components": components,
    }
    entry["grid_result"] = result
    _ica_cache_set(key, entry)
    return result


def build_ica_labels(study: Any, artifact: Any) -> dict[str, Any]:
    """端点用（**慢路径，异步补**）：载入源 raw，算每成分解释方差% + ICLabel 自动分类 + 建议剔除。

    与快路径网格分离——网格秒出后前端再拉这个把方差 / 标签 / 默认勾选补上。结果按 artifact 内容身份缓存。
    """
    key, ica, entry = _ensure_ica(study, artifact)
    if entry.get("labels_result") is not None:
        return entry["labels_result"]
    raw = _ensure_raw(study, artifact, key, entry)

    n_components = int(getattr(ica, "n_components_", 0) or 0)
    variances = _all_component_variances(ica, raw, n_components) if raw is not None else {}
    iclabel = classify_iclabel(ica, raw)
    suggested = sorted(i for i, info in iclabel.items() if info.get("suggested"))

    total_var: float | None = None
    if raw is not None:
        try:
            evr = ica.get_explained_variance_ratio(raw)
            total_var = float(evr.get("eeg", 0.0)) * 100 if isinstance(evr, dict) else None
        except Exception:
            total_var = None

    result = {
        "has_source_raw": raw is not None,
        "iclabel_available": bool(iclabel),
        "total_variance_explained": total_var,
        "suggested_exclude": suggested,
        "variances": {str(i): round(v, 1) for i, v in variances.items()},
        "iclabel": {str(i): info for i, info in iclabel.items()},
    }
    entry["labels_result"] = result
    _ica_cache_set(key, entry)
    return result


def build_ica_component_detail(
    study: Any,
    artifact: Any,
    index: int,
    *,
    excluded: list[int] | None = None,
    max_seconds: float = 10.0,
    fmax: float = 50.0,
) -> dict[str, Any]:
    """端点用：单成分时域 + 频谱（+可选去除前后对比，需源 raw）。复用缓存的 ica+raw，不重读 FIF。"""
    from .previews import StudyOutputPreviewError  # noqa: PLC0415

    key, ica, entry = _ensure_ica(study, artifact)
    raw = _ensure_raw(study, artifact, key, entry)
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


def build_ica_preview(
    study: Any,
    artifact: Any,
    *,
    excluded: list[int] | None = None,
    channel: str | None = None,
    max_seconds: float = 10.0,
) -> dict[str, Any]:
    """端点用：给定要剔除的成分组合 + 通道，返回去除前后对比波形（成分审核页中心视图实时刷新用）。

    只算对比波形（不含时序 / 频谱），比单成分详情端点轻，便于成分组合频繁切换时实时预览。
    复用缓存的 ica+raw，不重读 FIF。excluded 为空 → 返回原始信号（去除后=原始）。
    """
    from .previews import StudyOutputPreviewError  # noqa: PLC0415

    key, ica, entry = _ensure_ica(study, artifact)
    raw = _ensure_raw(study, artifact, key, entry)
    if raw is None:
        raise StudyOutputPreviewError(
            "ICA_SOURCE_RAW_UNAVAILABLE",
            "源 raw 不可用，无法计算去除前后对比。",
            status_code=409,
        )
    excluded = [int(i) for i in (excluded or [])]
    return spatial_comparison(ica, raw, excluded, channel=channel, seconds=max_seconds)
