"""
Purpose: 从 TFR 结果(-tfr.h5)按需读取「单通道时频热图」供前端时频观察页(TfrPage)绘制。
         返回某个通道的 频率 × 时间 功率矩阵(按基线模式换算成 dB / % / z 等展示单位),
         外加各频带(δ/θ/α/β/γ)的刺激后平均功率统计。
Related: app/routers/study_outputs.py, app/pipeline/previews.py(复用路径解析/校验),
         app/engine/analysis/tfr.py, frontend TfrPage.vue。
"""

from __future__ import annotations

import functools
import os
from typing import Any

from .montage_layout import channel_positions_2d
from .previews import (
    StudyOutputPreviewError,
    resolve_study_output_path,
    validate_study_output_file,
)

DEFAULT_MAX_FREQS = 60
DEFAULT_MAX_TIMES = 120

# 标准频带(Hz),用于右栏频带功率统计
EEG_BANDS: tuple[tuple[str, float, float], ...] = (
    ("delta", 1.0, 4.0),
    ("theta", 4.0, 8.0),
    ("alpha", 8.0, 13.0),
    ("beta", 13.0, 30.0),
    ("gamma", 30.0, 80.0),
)


def _mne():
    try:
        import mne
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("MNE is required for TFR view.") from exc
    return mne


def _numpy():
    try:
        import numpy
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("NumPy is required for TFR view.") from exc
    return numpy


def _unit_and_scale(baseline_mode: str | None) -> tuple[str, float]:
    """基线模式 → (展示单位, 缩放系数)。

    注意 MNE 各模式返回值的量纲:
      - logratio = log10(功率/基线) → ×10 = 标准 ERSP 的 dB
      - percent  = (功率-基线)/基线，是「分数」(−0.21 = −21%)，**不是**已乘 100 的百分数 → ×100 才是真 %
      - ratio    = 功率/基线（倍数）；mean = 功率-基线；zscore/zlogratio 已是无量纲 z → 都 ×1
    """
    mode = str(baseline_mode or "").strip().lower()
    if mode == "logratio":
        return "dB", 10.0
    if mode == "percent":
        return "%", 100.0
    if mode in ("zscore", "zlogratio"):
        return "z", 1.0
    if mode == "ratio":
        return "×", 1.0
    if mode == "mean":
        return "Δ", 1.0
    return "power", 1.0


@functools.lru_cache(maxsize=6)
def _read_tfrs_cached(path_str: str, _mtime: float):
    """解析 -tfr.h5 → 首个 AverageTFR，按 (路径, mtime) LRU 缓存（默认 6 个）。

    关键：避免「选 N 个通道 = N 次 /tfr = N 次整读同一份 h5」，再叠 /tfr/cube、/tfr/topo 又各读一次的重复磁盘读。
    缓存对象在各视图里只读取（np.asarray 复制 data、info 只读）、绝不就地改 → 多请求共享安全。
    文件被重处理 → mtime 变 → 缓存键变 → 自动重读；旧条目按 LRU 淘汰。
    """
    mne = _mne()
    out = mne.time_frequency.read_tfrs(path_str)
    if isinstance(out, (list, tuple)):
        return out[0] if out else None
    return out


def _read_first_tfr(path) -> Any:
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = 0.0
    tfr = _read_tfrs_cached(str(path), mtime)
    if tfr is None:
        raise StudyOutputPreviewError(
            "DERIVED_DATASET_TFR_EMPTY", "TFR 文件不含任何时频数据", status_code=422
        )
    return tfr


def build_tfr_heatmap(
    study: Any,
    dataset: Any,
    *,
    channel: str | None = None,
    max_freqs: int = DEFAULT_MAX_FREQS,
    max_times: int = DEFAULT_MAX_TIMES,
) -> dict[str, Any]:
    np = _numpy()
    path = resolve_study_output_path(study, dataset)
    validate_study_output_file(path, dataset)
    tfr = _read_first_tfr(path)

    ch_names = [str(name) for name in tfr.ch_names]
    if not ch_names:
        raise StudyOutputPreviewError("DERIVED_DATASET_TFR_EMPTY", "TFR 不含任何通道", status_code=422)

    params = getattr(dataset, "produced_by_params", None)
    baseline_mode = params.get("baseline_mode") if isinstance(params, dict) else None
    unit, scale = _unit_and_scale(baseline_mode)

    freqs = np.asarray(tfr.freqs, dtype=float)
    times = np.asarray(tfr.times, dtype=float)
    data = np.asarray(tfr.data, dtype=float)  # (n_channels, n_freqs, n_times)

    # 选通道:显式指定优先;否则默认取刺激后能量变化最强的通道(更有信息量)
    channel_index = _resolve_channel_index(np, ch_names, data, times, channel)
    chosen = ch_names[channel_index]

    f_idx = _downsample_indices(np, len(freqs), max_freqs)
    t_idx = _downsample_indices(np, len(times), max_times)
    out_freqs = [round(float(freqs[i]), 3) for i in f_idx]
    out_times = [round(float(times[i]), 4) for i in t_idx]

    plane = data[channel_index][np.ix_(f_idx, t_idx)] * scale
    power = [[round(float(v), 4) for v in row] for row in plane.tolist()]

    bands = _band_stats(np, freqs, times, data[channel_index] * scale)
    zmax = _suggest_zmax(np, plane)

    return {
        "data_type": "tfr",
        "study_output_id": str(getattr(dataset, "id", "") or ""),
        "condition": getattr(dataset, "condition", None),
        "method": str(getattr(tfr, "method", "") or "morlet"),
        "baseline_mode": str(baseline_mode or "none"),
        "unit": unit,
        "sfreq": float(tfr.info["sfreq"]),
        "nave": int(getattr(tfr, "nave", 0) or 0),
        "channel": chosen,
        "n_channels_total": len(ch_names),
        "ch_names_all": ch_names,
        "freqs": out_freqs,
        "times": out_times,
        "fmin": round(float(freqs[0]), 3) if len(freqs) else None,
        "fmax": round(float(freqs[-1]), 3) if len(freqs) else None,
        "tmin": round(float(times[0]), 4) if len(times) else None,
        "tmax": round(float(times[-1]), 4) if len(times) else None,
        "zmax": zmax,
        "power": power,
        "bands": bands,
    }


def build_tfr_topomap(
    study: Any,
    dataset: Any,
    *,
    tmin: float | None = None,
    tmax: float | None = None,
    fmin: float | None = None,
    fmax: float | None = None,
) -> dict[str, Any]:
    """全通道在 (时窗 × 频窗) 内的平均功率 + 2D 电极坐标，供时频观察页画频段地形图。

    与单通道热图(build_tfr_heatmap)互补：热图看「一个通道的时频面」，地形图看「某时频窗里所有通道的空间分布」。
    时窗默认刺激后(t>=0)、频窗默认全频；越界 / 空窗回退到全幅，绝不返回空地形。功率值按基线模式换算成展示单位
    (dB/%/z…)，**有符号**(负=ERD、正=ERS) → 前端发散色直接绕 0 上色，不必去均值。
    """
    np = _numpy()
    path = resolve_study_output_path(study, dataset)
    validate_study_output_file(path, dataset)
    tfr = _read_first_tfr(path)

    ch_names = [str(name) for name in tfr.ch_names]
    if not ch_names:
        raise StudyOutputPreviewError("DERIVED_DATASET_TFR_EMPTY", "TFR 不含任何通道", status_code=422)

    params = getattr(dataset, "produced_by_params", None)
    baseline_mode = params.get("baseline_mode") if isinstance(params, dict) else None
    unit, scale = _unit_and_scale(baseline_mode)

    freqs = np.asarray(tfr.freqs, dtype=float)
    times = np.asarray(tfr.times, dtype=float)
    data = np.asarray(tfr.data, dtype=float) * scale  # (n_channels, n_freqs, n_times)

    t_lo = float(times[0]) if tmin is None else float(tmin)
    t_hi = float(times[-1]) if tmax is None else float(tmax)
    f_lo = float(freqs[0]) if fmin is None else float(fmin)
    f_hi = float(freqs[-1]) if fmax is None else float(fmax)
    tmask = (times >= min(t_lo, t_hi)) & (times <= max(t_lo, t_hi))
    fmask = (freqs >= min(f_lo, f_hi)) & (freqs <= max(f_lo, f_hi))
    if not bool(tmask.any()):
        tmask = np.ones_like(times, dtype=bool)
    if not bool(fmask.any()):
        fmask = np.ones_like(freqs, dtype=bool)

    block = data[:, fmask, :][:, :, tmask]  # (n_channels, nf, nt)
    if block.size:
        with np.errstate(invalid="ignore"):
            values = np.nanmean(block, axis=(1, 2))
    else:
        values = np.zeros(len(ch_names), dtype=float)

    # 真实 montage 优先（h5 带完整 info），缺失时按通道名兜底标准帽
    ch_pos = channel_positions_2d(tfr.info, ch_names) or {}

    channels: list[dict[str, Any]] = []
    vmax = 0.0
    for i, name in enumerate(ch_names):
        v = float(values[i]) if i < len(values) and np.isfinite(values[i]) else 0.0
        pos = ch_pos.get(name)
        channels.append(
            {
                "name": name,
                "value": round(v, 4),
                "x": round(float(pos[0]), 4) if pos else None,
                "y": round(float(pos[1]), 4) if pos else None,
            }
        )
        if pos is not None and abs(v) > vmax:
            vmax = abs(v)

    return {
        "data_type": "tfr_topo",
        "study_output_id": str(getattr(dataset, "id", "") or ""),
        "condition": getattr(dataset, "condition", None),
        "unit": unit,
        "tmin": round(min(t_lo, t_hi), 4),
        "tmax": round(max(t_lo, t_hi), 4),
        "fmin": round(min(f_lo, f_hi), 3),
        "fmax": round(max(f_lo, f_hi), 3),
        "n_channels": len(ch_names),
        "n_positioned": sum(1 for c in channels if c["x"] is not None),
        "vmax": round(vmax, 4) if vmax > 1e-9 else 1.0,
        "channels": channels,
    }


def build_tfr_cube(
    study: Any,
    dataset: Any,
    *,
    max_freqs: int = DEFAULT_MAX_FREQS,
    max_times: int = DEFAULT_MAX_TIMES,
) -> dict[str, Any]:
    """全通道降采样时频立方体（每通道一张 freq×time 面）+ 2D 电极坐标，供前端**本地**算地形图。

    一次性把所有通道取回前端 → 跟随游标 / 区间地形图全在前端本地算（最近 bin / 窗口均值），
    跟随期间**零后端往返**、即时响应（对标 PSD：多通道数据在前端、topo 本地算）。
    值已按基线模式换算成展示单位、有符号（负=ERD、正=ERS）。这一次读 h5 替代了原来每移一下游标读一次。
    """
    np = _numpy()
    path = resolve_study_output_path(study, dataset)
    validate_study_output_file(path, dataset)
    tfr = _read_first_tfr(path)

    ch_names = [str(name) for name in tfr.ch_names]
    if not ch_names:
        raise StudyOutputPreviewError("DERIVED_DATASET_TFR_EMPTY", "TFR 不含任何通道", status_code=422)

    params = getattr(dataset, "produced_by_params", None)
    baseline_mode = params.get("baseline_mode") if isinstance(params, dict) else None
    unit, scale = _unit_and_scale(baseline_mode)

    freqs = np.asarray(tfr.freqs, dtype=float)
    times = np.asarray(tfr.times, dtype=float)
    data = np.asarray(tfr.data, dtype=float)  # (n_channels, n_freqs, n_times)

    f_idx = _downsample_indices(np, len(freqs), max_freqs)
    t_idx = _downsample_indices(np, len(times), max_times)
    out_freqs = [round(float(freqs[i]), 3) for i in f_idx]
    out_times = [round(float(times[i]), 4) for i in t_idx]

    sub = data[:, f_idx, :][:, :, t_idx] * scale  # (n_channels, nf, nt)
    ch_pos = channel_positions_2d(tfr.info, ch_names) or {}

    channels: list[dict[str, Any]] = []
    for i, name in enumerate(ch_names):
        pos = ch_pos.get(name)
        channels.append(
            {
                "name": name,
                "x": round(float(pos[0]), 4) if pos else None,
                "y": round(float(pos[1]), 4) if pos else None,
                "data": [[round(float(v), 4) for v in row] for row in sub[i].tolist()],
            }
        )

    return {
        "data_type": "tfr_cube",
        "study_output_id": str(getattr(dataset, "id", "") or ""),
        "condition": getattr(dataset, "condition", None),
        "unit": unit,
        "freqs": out_freqs,
        "times": out_times,
        "n_channels": len(ch_names),
        "n_positioned": sum(1 for c in channels if c["x"] is not None),
        "channels": channels,
    }


def _resolve_channel_index(np, ch_names: list[str], data, times, channel: str | None) -> int:
    if channel:
        wanted = str(channel).strip()
        for i, name in enumerate(ch_names):
            if name == wanted:
                return i
    # 默认:刺激后(t>=0)平均功率绝对值最大的通道
    post = times >= 0
    if not bool(post.any()):
        post = np.ones_like(times, dtype=bool)
    try:
        strength = np.nanmean(np.abs(data[:, :, post]), axis=(1, 2))
        return int(np.argmax(strength))
    except Exception:
        return 0


def _downsample_indices(np, n: int, max_count: int):
    if n <= 0:
        return np.array([], dtype=int)
    count = min(max(2, int(max_count)), int(n))
    return np.unique(np.linspace(0, n - 1, count).astype(int))


def _band_stats(np, freqs, times, plane) -> list[dict[str, Any]]:
    """plane: 单通道 (n_freqs, n_times),已按展示单位缩放。统计刺激后窗口内各频带均值。"""
    post = times >= 0
    if not bool(post.any()):
        post = np.ones_like(times, dtype=bool)
    out: list[dict[str, Any]] = []
    for name, lo, hi in EEG_BANDS:
        fmask = (freqs >= lo) & (freqs < hi)
        if not bool(fmask.any()):
            continue
        block = plane[np.ix_(fmask, post)]
        value = float(np.nanmean(block)) if block.size else 0.0
        out.append({"name": name, "fmin": lo, "fmax": hi, "value": round(value, 4)})
    return out


def _suggest_zmax(np, plane) -> float:
    """给前端一个对称色阶上界:取 |值| 的 98 分位,避免极端值压扁配色。"""
    try:
        flat = np.abs(np.asarray(plane, dtype=float)).ravel()
        flat = flat[np.isfinite(flat)]
        if flat.size == 0:
            return 1.0
        z = float(np.percentile(flat, 98))
        return round(z, 4) if z > 1e-9 else 1.0
    except Exception:
        return 1.0
