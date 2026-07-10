"""
Purpose: 从 stat_map 结果(.npz)读取统计比较图供统计观察页(StatsPage)绘制——
         1D(ERP/PSD)返回选定通道的 t 曲线 + 显著掩码 + A/B 均值曲线;
         2D(TFR)返回选定通道的 t 时频网格 + 显著网格;附 cluster 显著窗口。
Related: app/routers/study_outputs.py, app/pipeline/previews.py, app/engine/group/compare.py,
         app/engine/io.py(save_stat_map_npz), frontend StatsPage.vue。
"""

from __future__ import annotations

from typing import Any

from app.engine.analysis.event_conditions import normalize_marker_label
from app.engine.io import load_stat_map_npz

from .montage_layout import channel_positions_2d
from .previews import (
    StudyOutputPreviewError,
    resolve_study_output_path,
    validate_study_output_file,
)

DEFAULT_MAX_POINTS = 600
MAX_TFR_FREQS = 80
MAX_TFR_TIMES = 200


def _numpy():
    try:
        import numpy
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("NumPy is required for stat view.") from exc
    return numpy


def _downsample_indices(np, n: int, max_count: int):
    if n <= 0:
        return np.array([], dtype=int)
    count = min(max(2, int(max_count)), int(n))
    return np.unique(np.linspace(0, n - 1, count).astype(int))


def _fdr_q_values(np, pmap: Any) -> Any:
    p = np.nan_to_num(np.asarray(pmap, dtype=float), nan=1.0, posinf=1.0, neginf=1.0)
    p = np.clip(p, 0.0, 1.0)
    flat = p.reshape(-1)
    n = int(flat.size)
    if n == 0:
        return p
    order = np.argsort(flat)
    ranked = flat[order] * n / np.arange(1, n + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    q = np.empty_like(flat)
    q[order] = np.clip(ranked, 0.0, 1.0)
    return q.reshape(p.shape)


def _feature_window(np, m: Any, base: str, times: Any, freqs: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if base == "evoked" and times is not None:
        idx = np.where(m)[0]
        if idx.size:
            out["tmin"] = round(float(times[idx.min()]), 4)
            out["tmax"] = round(float(times[idx.max()]), 4)
    elif base == "psd" and freqs is not None:
        idx = np.where(m)[0]
        if idx.size:
            out["fmin"] = round(float(freqs[idx.min()]), 4)
            out["fmax"] = round(float(freqs[idx.max()]), 4)
    elif base == "tfr" and freqs is not None and times is not None:
        fi, ti = np.where(m)
        if fi.size:
            out["fmin"] = round(float(freqs[fi.min()]), 4)
            out["fmax"] = round(float(freqs[fi.max()]), 4)
            out["tmin"] = round(float(times[ti.min()]), 4)
            out["tmax"] = round(float(times[ti.max()]), 4)
    return out


def _cluster_mask_for_channel(np, mask: Any, dims: list[str], ci: int) -> tuple[Any, bool, list[int]]:
    """返回当前通道对应的 feature mask。ROI mask 无通道维,视作所有通道可见。"""
    m = np.asarray(mask, dtype=bool)
    if dims and dims[0] == "channels" and m.ndim >= 2:
        channel_hits = m.reshape(m.shape[0], -1).any(axis=1)
        if ci >= m.shape[0] or not bool(channel_hits[ci]):
            return m.any(axis=0), False, [int(x) for x in np.where(channel_hits)[0]]
        return m[ci], True, [int(x) for x in np.where(channel_hits)[0]]
    return m, True, []


def _cluster_sig_for_channel(np, sm: dict[str, Any], base: str, ci: int) -> Any | None:
    masks = sm.get("cluster_masks")
    if masks is None:
        return None
    masks = np.asarray(masks, dtype=bool)
    if masks.size == 0:
        return None
    dims = list(sm.get("cluster_mask_dims") or [])
    pvals = list(sm.get("cluster_pvals") or [])
    alpha = float(sm.get("alpha") or 0.05)
    template = None
    out = None
    for i in range(masks.shape[0]):
        feature_mask, contains, _ = _cluster_mask_for_channel(np, masks[i], dims, ci)
        if template is None:
            template = np.zeros_like(feature_mask, dtype=bool)
        if i >= len(pvals) or float(pvals[i]) >= alpha:
            continue
        if not contains:
            continue
        if out is None:
            out = np.zeros_like(feature_mask, dtype=bool)
        if out is not None and feature_mask.shape == out.shape:
            out |= feature_mask
    return out if out is not None else template


def _cluster_windows(np, sm: dict[str, Any], base: str, ci: int) -> list[dict[str, Any]]:
    """从 cluster_masks + cluster_pvals 还原显著窗口;含通道维时只返回当前通道参与的簇。"""
    masks = sm.get("cluster_masks")
    if masks is None:
        return []
    masks = np.asarray(masks, dtype=bool)
    pvals = list(sm.get("cluster_pvals") or [])
    times = sm.get("times")
    freqs = sm.get("freqs")
    alpha = float(sm.get("alpha") or 0.05)
    dims = list(sm.get("cluster_mask_dims") or [])
    ch_names = list(sm.get("ch_names") or [])
    out: list[dict[str, Any]] = []
    for i in range(masks.shape[0]):
        m, contains, channel_indices = _cluster_mask_for_channel(np, masks[i], dims, ci)
        if not contains:
            continue
        p = float(pvals[i]) if i < len(pvals) else 1.0
        d: dict[str, Any] = {"p": round(p, 4), "significant": bool(p < alpha)}
        d.update(_feature_window(np, m, base, times, freqs))
        if channel_indices:
            names = [ch_names[j] for j in channel_indices if j < len(ch_names)]
            d["channels"] = names
            d["n_channels"] = len(names)
        d["n_points"] = int(m.sum())
        out.append(d)
    out.sort(key=lambda x: x["p"])
    return out


def _axis_coord(np, base: str, times: Any, freqs: Any, feature_index: tuple[int, ...]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if base == "evoked" and times is not None and feature_index:
        ti = int(feature_index[0])
        if 0 <= ti < len(times):
            value = round(float(times[ti]), 4)
            out.update({"axis_kind": "time", "axis_value": value, "axis_label": f"{value:g} s"})
    elif base == "psd" and freqs is not None and feature_index:
        fi = int(feature_index[0])
        if 0 <= fi < len(freqs):
            value = round(float(freqs[fi]), 4)
            out.update({"axis_kind": "frequency", "axis_value": value, "axis_label": f"{value:g} Hz"})
    elif base == "tfr" and freqs is not None and times is not None and len(feature_index) >= 2:
        fi = int(feature_index[0])
        ti = int(feature_index[1])
        if 0 <= fi < len(freqs) and 0 <= ti < len(times):
            f_value = round(float(freqs[fi]), 4)
            t_value = round(float(times[ti]), 4)
            out.update(
                {
                    "axis_kind": "freq_time",
                    "freq": f_value,
                    "time": t_value,
                    "axis_label": f"{f_value:g} Hz · {t_value:g} s",
                }
            )
    return out


def _contrast_parts(label: str) -> tuple[str, str]:
    core = str(label or "").split("·", 1)[0]
    if "−" in core:
        left, right = core.split("−", 1)
    elif "-" in core:
        left, right = core.split("-", 1)
    else:
        return "A", "B"
    return left.strip() or "A", right.strip() or "B"


def _stat_overview(np, sm: dict[str, Any], base: str, ch_names: list[str], tmap: Any, sig: Any) -> dict[str, Any]:
    """面向结果页的轻量结论摘要：先回答是否显著，再给最强差异位置。"""
    times = sm.get("times")
    freqs = sm.get("freqs")
    alpha = float(sm.get("alpha") or 0.05)
    method = str(sm.get("method") or "")
    correction = str(sm.get("correction") or "none")
    label_a, label_b = _contrast_parts(str(sm.get("contrast_label") or ""))

    t_arr = np.asarray(tmap, dtype=float)
    sig_arr = np.asarray(sig, dtype=bool)
    n_total = int(sig_arr.size)
    n_significant = int(sig_arr.sum()) if n_total else 0
    sig_by_channel = sig_arr.reshape(len(ch_names), -1).any(axis=1) if n_total and ch_names else np.zeros((0,), dtype=bool)
    significant_channels = [ch_names[i] for i, yes in enumerate(sig_by_channel) if bool(yes)]

    cluster_pvals = [float(x) for x in sm.get("cluster_pvals") or []]
    n_clusters = len(cluster_pvals)
    n_significant_clusters = sum(1 for p in cluster_pvals if p < alpha)

    abs_t = np.nan_to_num(np.abs(t_arr), nan=0.0)
    if abs_t.size:
        max_index = tuple(int(i) for i in np.unravel_index(int(np.argmax(abs_t)), abs_t.shape))
        strongest_t = round(float(t_arr[max_index]), 4)
        strongest_abs_t = round(float(abs_t[max_index]), 4)
        ch_index = int(max_index[0]) if max_index else 0
    else:
        max_index = (0,)
        strongest_t = 0.0
        strongest_abs_t = 0.0
        ch_index = 0
    strongest_channel = ch_names[ch_index] if 0 <= ch_index < len(ch_names) else ""

    mean_a = np.asarray(sm.get("mean_a"), dtype=float)
    mean_b = np.asarray(sm.get("mean_b"), dtype=float)
    if mean_a.size and mean_b.size and len(max_index) == mean_a.ndim == mean_b.ndim:
        raw_mean_a = float(mean_a[max_index])
        raw_mean_b = float(mean_b[max_index])
        mean_a_value = round(raw_mean_a, 5)
        mean_b_value = round(raw_mean_b, 5)
        delta = raw_mean_a - raw_mean_b
        if abs(delta) < 1e-12:
            delta = float(strongest_t)
    else:
        mean_a_value = None
        mean_b_value = None
        delta = float(strongest_t)
    direction = "a_gt_b" if delta > 0 else "b_gt_a" if delta < 0 else "flat"
    direction_label = f"{label_a} > {label_b}" if direction == "a_gt_b" else f"{label_b} > {label_a}" if direction == "b_gt_a" else "A ≈ B"

    has_significant = bool(n_significant_clusters > 0 if method == "cluster" else n_significant > 0)
    if method == "cluster":
        conclusion = (
            f"校正后发现 {n_significant_clusters} 个显著簇。"
            if has_significant
            else "校正后未发现显著簇。"
        )
    else:
        correction_label = "FDR 校正" if correction == "fdr" else "未校正"
        conclusion = (
            f"{correction_label}后发现 {n_significant} 个显著点，涉及 {len(significant_channels)} 个通道。"
            if has_significant
            else f"{correction_label}后未发现显著差异。"
        )

    strongest: dict[str, Any] = {
        "channel": strongest_channel,
        "t": strongest_t,
        "abs_t": strongest_abs_t,
        "direction": direction,
        "direction_label": direction_label,
        "mean_a": mean_a_value,
        "mean_b": mean_b_value,
    }
    strongest.update(_axis_coord(np, base, times, freqs, max_index[1:]))

    return {
        "has_significant": has_significant,
        "conclusion": conclusion,
        "n_significant": n_significant,
        "n_total": n_total,
        "n_significant_channels": len(significant_channels),
        "significant_channels": significant_channels[:12],
        "significant_channels_total": len(significant_channels),
        "n_clusters": n_clusters,
        "n_significant_clusters": n_significant_clusters,
        "strongest": strongest,
    }


def build_stat_view(
    study: Any,
    dataset: Any,
    *,
    channel: str | None = None,
    max_points: int = DEFAULT_MAX_POINTS,
) -> dict[str, Any]:
    """读 stat_map .npz → 统计观察页绘图数据(选定通道的 t 图 + 显著掩码 + A/B 均值 + cluster 窗口)。"""
    np = _numpy()
    path = resolve_study_output_path(study, dataset)
    validate_study_output_file(path, dataset)

    try:
        sm = load_stat_map_npz(path)
    except StudyOutputPreviewError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise StudyOutputPreviewError(
            "DERIVED_DATASET_STAT_UNREADABLE", f"统计结果无法读取: {exc}", status_code=422
        ) from exc

    base = str(sm.get("base_type") or "")
    ch_names = list(sm.get("ch_names") or [])
    tmap = np.asarray(sm["tmap"], dtype=float)
    pmap = np.asarray(sm.get("pmap"), dtype=float)
    sig = np.asarray(sm["sig"], dtype=bool)
    mean_a = np.asarray(sm["mean_a"], dtype=float)
    mean_b = np.asarray(sm["mean_b"], dtype=float)
    times = sm.get("times")
    freqs = sm.get("freqs")
    n_ch = len(ch_names)

    if tmap.ndim < 2 or n_ch == 0:
        raise StudyOutputPreviewError(
            "DERIVED_DATASET_STAT_EMPTY", "统计图为空或形状异常。", status_code=422
        )
    if pmap.shape != tmap.shape:
        pmap = np.ones_like(tmap, dtype=float)
    qmap = _fdr_q_values(np, pmap) if str(sm.get("correction") or "").lower() == "fdr" else pmap

    # 每通道 max|t| → 默认聚焦最强通道
    flat = np.abs(tmap).reshape(n_ch, -1)
    absmax_per_ch = np.nan_to_num(np.nanmax(flat, axis=1), nan=0.0)
    default_idx = int(np.argmax(absmax_per_ch))
    ci = ch_names.index(channel) if (channel and channel in ch_names) else default_idx
    tmax_abs = float(np.nanmax(np.abs(tmap))) if tmap.size else 0.0

    out: dict[str, Any] = {
        "data_type": "stat_map",
        "base_type": base,
        "study_output_id": str(getattr(dataset, "id", "") or ""),
        "display_name": getattr(dataset, "display_name", None),
        "condition": normalize_marker_label(sm.get("condition")),
        "contrast_label": str(sm.get("contrast_label") or ""),
        "design": str(sm.get("design") or ""),
        "method": str(sm.get("method") or ""),
        "tail": str(sm.get("tail") or ""),
        "correction": str(sm.get("correction") or ""),
        "alpha": float(sm.get("alpha") or 0.05),
        "n_a": int(sm.get("n_a") or 0),
        "n_b": int(sm.get("n_b") or 0),
        "n_significant": int(sig.sum()) if sig.size else 0,
        "n_total": int(sig.size),
        "ch_names": ch_names,
        "default_channel": ch_names[ci],
        "channel": ch_names[ci],
        "tmax_abs": round(tmax_abs, 4),
        "roi_channels": list(sm.get("roi_channels") or []),
        "cluster_mode": str(sm.get("cluster_mode") or ""),
        "cluster_stat": str(sm.get("cluster_stat") or ""),
        "cluster_mask_dims": list(sm.get("cluster_mask_dims") or []),
        "cluster_adjacency": str(sm.get("cluster_adjacency") or ""),
        "probability_kind": "fdr_q" if str(sm.get("correction") or "").lower() == "fdr" else "raw_p",
        "clusters": _cluster_windows(np, sm, base, ci),
        "ch_pos": channel_positions_2d(None, ch_names),
        "overview": _stat_overview(np, sm, base, ch_names, tmap, sig),
    }

    cluster_sig = _cluster_sig_for_channel(np, sm, base, ci) if out["method"] == "cluster" else None
    if cluster_sig is not None:
        out["n_significant"] = int(np.asarray(cluster_sig, dtype=bool).sum())
        out["n_total"] = int(np.asarray(cluster_sig).size)

    if base == "tfr" and freqs is not None and times is not None:
        f_idx = _downsample_indices(np, len(freqs), MAX_TFR_FREQS)
        t_idx = _downsample_indices(np, len(times), MAX_TFR_TIMES)
        grid = tmap[ci][np.ix_(f_idx, t_idx)]
        pgrid = pmap[ci][np.ix_(f_idx, t_idx)]
        qgrid = qmap[ci][np.ix_(f_idx, t_idx)]
        dgrid = (mean_a - mean_b)[ci][np.ix_(f_idx, t_idx)]
        sig_source = cluster_sig if cluster_sig is not None else sig[ci]
        sgrid = sig_source[np.ix_(f_idx, t_idx)]
        out["axis"] = {
            "kind": "freq_time",
            "freqs": [round(float(freqs[i]), 3) for i in f_idx],
            "times": [round(float(times[i]), 4) for i in t_idx],
        }
        out["t_grid"] = [[round(float(v), 3) for v in row] for row in grid]
        out["p_grid"] = [[round(float(v), 8) for v in row] for row in pgrid]
        out["q_grid"] = [[round(float(v), 8) for v in row] for row in qgrid]
        out["delta_grid"] = [[round(float(v), 8) for v in row] for row in dgrid]
        out["sig_grid"] = [[bool(v) for v in row] for row in sgrid]
    else:
        axis_vals = times if base == "evoked" else freqs
        kind = "times" if base == "evoked" else "freqs"
        if axis_vals is None:
            raise StudyOutputPreviewError(
                "DERIVED_DATASET_STAT_EMPTY", "统计图缺少坐标轴。", status_code=422
            )
        n = len(axis_vals)
        idx = _downsample_indices(np, n, max_points)
        sig_source = cluster_sig if cluster_sig is not None else sig[ci]
        out["axis"] = {"kind": kind, "values": [round(float(axis_vals[i]), 4) for i in idx]}
        out["t"] = [round(float(tmap[ci][i]), 4) for i in idx]
        out["sig"] = [bool(sig_source[i]) for i in idx]
        out["mean_a"] = [round(float(mean_a[ci][i]), 5) for i in idx]
        out["mean_b"] = [round(float(mean_b[ci][i]), 5) for i in idx]

    return out
