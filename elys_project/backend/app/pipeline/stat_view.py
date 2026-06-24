"""
Purpose: 从 stat_map 结果(.npz)读取统计比较图供统计观察页(StatsPage)绘制——
         1D(ERP/PSD)返回选定通道的 t 曲线 + 显著掩码 + A/B 均值曲线;
         2D(TFR)返回选定通道的 t 时频网格 + 显著网格;附 cluster 显著窗口。
Related: app/routers/study_outputs.py, app/pipeline/previews.py, app/engine/group/compare.py,
         app/engine/io.py(save_stat_map_npz), frontend StatsPage.vue。
"""

from __future__ import annotations

from typing import Any

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


def _cluster_windows(np, sm: dict[str, Any], base: str) -> list[dict[str, Any]]:
    """从 cluster_masks + cluster_pvals 还原显著窗口(时间/频率范围),按 p 升序。"""
    masks = sm.get("cluster_masks")
    if masks is None:
        return []
    masks = np.asarray(masks, dtype=bool)
    pvals = list(sm.get("cluster_pvals") or [])
    times = sm.get("times")
    freqs = sm.get("freqs")
    alpha = float(sm.get("alpha") or 0.05)
    out: list[dict[str, Any]] = []
    for i in range(masks.shape[0]):
        m = masks[i]
        p = float(pvals[i]) if i < len(pvals) else 1.0
        d: dict[str, Any] = {"p": round(p, 4), "significant": bool(p < alpha)}
        if base == "evoked" and times is not None:
            idx = np.where(m)[0]
            if idx.size:
                d["tmin"] = round(float(times[idx.min()]), 4)
                d["tmax"] = round(float(times[idx.max()]), 4)
        elif base == "psd" and freqs is not None:
            idx = np.where(m)[0]
            if idx.size:
                d["fmin"] = round(float(freqs[idx.min()]), 4)
                d["fmax"] = round(float(freqs[idx.max()]), 4)
        elif base == "tfr" and freqs is not None and times is not None:
            fi, ti = np.where(m)
            if fi.size:
                d["fmin"] = round(float(freqs[fi.min()]), 4)
                d["fmax"] = round(float(freqs[fi.max()]), 4)
                d["tmin"] = round(float(times[ti.min()]), 4)
                d["tmax"] = round(float(times[ti.max()]), 4)
        d["n_points"] = int(m.sum())
        out.append(d)
    out.sort(key=lambda x: x["p"])
    return out


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
        "clusters": _cluster_windows(np, sm, base),
        "ch_pos": channel_positions_2d(None, ch_names),
    }

    if base == "tfr" and freqs is not None and times is not None:
        f_idx = _downsample_indices(np, len(freqs), MAX_TFR_FREQS)
        t_idx = _downsample_indices(np, len(times), MAX_TFR_TIMES)
        grid = tmap[ci][np.ix_(f_idx, t_idx)]
        sgrid = sig[ci][np.ix_(f_idx, t_idx)]
        out["axis"] = {
            "kind": "freq_time",
            "freqs": [round(float(freqs[i]), 3) for i in f_idx],
            "times": [round(float(times[i]), 4) for i in t_idx],
        }
        out["t_grid"] = [[round(float(v), 3) for v in row] for row in grid]
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
        out["axis"] = {"kind": kind, "values": [round(float(axis_vals[i]), 4) for i in idx]}
        out["t"] = [round(float(tmap[ci][i]), 4) for i in idx]
        out["sig"] = [bool(sig[ci][i]) for i in idx]
        out["mean_a"] = [round(float(mean_a[ci][i]), 5) for i in idx]
        out["mean_b"] = [round(float(mean_b[ci][i]), 5) for i in idx]

    return out
