"""
Purpose: 从 PSD 结果(.npz)读取「多通道功率谱」供前端功率谱观察页(PsdPage)绘制——
         返回各通道的 频率 → 功率(dB) 折线 + 各频带(δ/θ/α/β/γ)平均功率,
         形状对齐 timeseries 的 channels[],让前端复用时域图的叠加/分面/频段地形图机制。
Related: app/routers/study_outputs.py, app/pipeline/previews.py(复用路径解析/校验),
         app/engine/analysis/psd.py, app/engine/io.py(save_psd_npz), frontend PsdPage.vue。
"""

from __future__ import annotations

from typing import Any

from app.engine.analysis.event_conditions import normalize_marker_label

from .montage_layout import channel_positions_2d
from .previews import (
    StudyOutputPreviewError,
    resolve_study_output_path,
    validate_study_output_file,
)

DEFAULT_MAX_FREQS = 300
DEFAULT_MAX_CHANNELS = 64

# 标准频带(Hz)
EEG_BANDS: tuple[tuple[str, float, float], ...] = (
    ("delta", 1.0, 4.0),
    ("theta", 4.0, 8.0),
    ("alpha", 8.0, 13.0),
    ("beta", 13.0, 30.0),
    ("gamma", 30.0, 80.0),
)


def _numpy():
    try:
        import numpy
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("NumPy is required for PSD view.") from exc
    return numpy


def build_psd_lines(
    study: Any,
    dataset: Any,
    *,
    channel: str | None = None,
    max_freqs: int = DEFAULT_MAX_FREQS,
    max_channels: int = DEFAULT_MAX_CHANNELS,
) -> dict[str, Any]:
    """读 PSD 的 .npz(freqs / psds / ch_names)→ 多通道功率谱折线(dB)+ 逐通道频带统计。

    返回形状对齐 timeseries 的 channels[]：每通道一条 power(dB) 折线 + bands,
    让前端 facet/叠加/频段地形图复用时域图那套机制。channel 仅用于指定默认聚焦通道。
    """
    np = _numpy()
    path = resolve_study_output_path(study, dataset)
    validate_study_output_file(path, dataset)

    try:
        with np.load(path, allow_pickle=False) as npz:
            freqs = np.asarray(npz["freqs"], dtype=float)
            psds = np.asarray(npz["psds"], dtype=float)  # (n_channels, n_freqs)
            ch_names = [str(x) for x in np.asarray(npz["ch_names"]).tolist()]
            sfreq = float(np.asarray(npz["sfreq"]).reshape(-1)[0])
    except StudyOutputPreviewError:
        raise
    except Exception as exc:  # noqa: BLE001 — 读不出给可操作报错
        raise StudyOutputPreviewError(
            "DERIVED_DATASET_PSD_UNREADABLE", f"PSD 文件无法读取: {exc}", status_code=422
        ) from exc

    if psds.ndim != 2 or freqs.size == 0 or not ch_names:
        shape = tuple(int(x) for x in psds.shape) if psds.ndim == 2 else f"ndim={psds.ndim}"
        raise StudyOutputPreviewError(
            "DERIVED_DATASET_PSD_EMPTY", f"PSD 数据为空或形状异常 (psds={shape}, freqs={int(freqs.size)}, ch={len(ch_names)})", status_code=422
        )

    # 以 psds 真实维度为准夹紧:psds 行数(=做了 PSD 的数据通道数)可能少于 ch_names(旧 artifact 把
    # 全部通道名都存了,含 stim/EOG 等非数据通道);freqs 也夹到 psds 列数。避免按 ch_names 长度越界 db。
    n_ch = min(int(psds.shape[0]), len(ch_names))
    if n_ch <= 0:
        raise StudyOutputPreviewError("DERIVED_DATASET_PSD_EMPTY", "PSD 无可用通道", status_code=422)
    n_freq = min(int(psds.shape[1]), int(freqs.size))
    ch_names = ch_names[:n_ch]
    freqs = freqs[:n_freq]
    psds = psds[:n_ch, :n_freq]

    keep = min(max(1, int(max_channels)), n_ch)
    kept = list(range(keep))  # 蒙太奇顺序前 keep 个通道(常规 ≤64 蒙太奇不会截断)

    # 频率横轴整体降采样一次,全通道共享同一根 x
    f_idx = _downsample_indices(np, n_freq, max_freqs)
    out_freqs = [round(float(freqs[i]), 3) for i in f_idx]

    # 全通道一次转 dB(10·log10):裸功率 ~1e-11 V²/Hz,无法直接画
    db = 10.0 * np.log10(np.maximum(psds, 1e-30))  # (n_ch, n_freq)

    # 默认聚焦通道:显式 channel 命中优先,否则取返回集中总功率最大者(更有信息量)
    default_index = _focus_index(np, ch_names, psds, channel, kept)

    channels_out: list[dict[str, Any]] = []
    for ci in kept:
        line = db[ci]
        finite = line[np.isfinite(line)]
        channels_out.append(
            {
                "name": ch_names[ci],
                "power": [round(float(line[i]), 4) for i in f_idx],
                "bands": _band_stats(np, freqs, line, psds[ci]),
                "pmax": round(float(np.nanmax(finite)), 4) if finite.size else None,
                "pmin": round(float(np.nanmin(finite)), 4) if finite.size else None,
            }
        )

    # 通道 2D 坐标:PSD 的 .npz 不存电极位置,传 info=None 让 montage_layout 走「按通道名兜底标准帽」分支,
    # 标准 10-20 名即可定位(观察用地形图足够);非标名/匹配不足 → None,前端走诚实空态不画。
    ch_pos = channel_positions_2d(None, ch_names)

    return {
        "data_type": "psd",
        "study_output_id": str(getattr(dataset, "id", "") or ""),
        "condition": normalize_marker_label(getattr(dataset, "condition", None)),
        "subject": getattr(dataset, "bids_subject_id", None),
        "display_name": getattr(dataset, "display_name", None),
        "method": "welch",
        "unit": "dB",
        "sfreq": sfreq,
        "n_channels_total": n_ch,
        "ch_names_all": ch_names,
        "ch_pos": ch_pos,
        "freqs": out_freqs,
        "fmin": round(float(freqs[0]), 3) if freqs.size else None,
        "fmax": round(float(freqs[-1]), 3) if freqs.size else None,
        "default_channel": ch_names[default_index],
        "channels": channels_out,
    }


def _focus_index(np, ch_names: list[str], psds, channel: str | None, kept: list[int]) -> int:
    """默认聚焦通道下标:显式 channel 命中优先,否则取 kept 集合中总功率最大者。"""
    if channel:
        wanted = str(channel).strip()
        for i in kept:
            if ch_names[i] == wanted:
                return i
    try:
        sub = psds[kept]  # (keep, n_freqs)
        return kept[int(np.argmax(np.nansum(sub, axis=1)))]
    except Exception:  # noqa: BLE001
        return kept[0] if kept else 0


def _downsample_indices(np, n: int, max_count: int):
    if n <= 0:
        return np.array([], dtype=int)
    count = min(max(2, int(max_count)), int(n))
    return np.unique(np.linspace(0, n - 1, count).astype(int))


def _band_stats(np, freqs, db_line, lin_row) -> list[dict[str, Any]]:
    """各频带统计:平均功率(dB, value) + 相对功率(占总功率 %, rel)。

    rel 从「线性」功率算(总功率=全频谱线性功率和):临床看相对功率——跨人/跨导联可比,
    不像绝对 dB 受电极/颅骨影响。比值(θ/β 等)由前端用 rel 相除即得(总功率约掉)。
    """
    lin = np.where(np.isfinite(lin_row), lin_row, 0.0)
    total = float(np.sum(lin))
    out: list[dict[str, Any]] = []
    for name, lo, hi in EEG_BANDS:
        fmask = (freqs >= lo) & (freqs < hi)
        if not bool(fmask.any()):
            continue
        block = db_line[fmask]
        value = float(np.nanmean(block)) if block.size else 0.0
        band_lin = float(np.sum(lin[fmask]))
        rel = round(band_lin / total * 100.0, 2) if total > 0 else 0.0
        out.append({"name": name, "fmin": lo, "fmax": hi, "value": round(value, 4), "rel": rel})
    return out
