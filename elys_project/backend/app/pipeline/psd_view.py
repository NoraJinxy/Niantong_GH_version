"""
Purpose: 从 PSD 结果(.npz)读取「单通道功率谱」供前端功率谱观察页(PsdPage)绘制——
         返回某通道的 频率 → 功率(dB) 折线 + 各频带(δ/θ/α/β/γ)平均功率。
Related: app/routers/study_outputs.py, app/pipeline/previews.py(复用路径解析/校验),
         app/engine/analysis/psd.py, app/engine/io.py(save_psd_npz), frontend PsdPage.vue。
"""

from __future__ import annotations

from typing import Any

from .previews import (
    StudyOutputPreviewError,
    resolve_study_output_path,
    validate_study_output_file,
)

DEFAULT_MAX_FREQS = 300

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
) -> dict[str, Any]:
    """读 PSD 的 .npz(freqs / psds / ch_names)→ 单通道功率谱折线(dB)+ 频带统计。"""
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
        raise StudyOutputPreviewError("DERIVED_DATASET_PSD_EMPTY", "PSD 不含有效数据", status_code=422)

    channel_index = _resolve_channel_index(np, ch_names, psds, channel)
    chosen = ch_names[channel_index]

    # 转 dB（10·log10），让折线在可读量级（裸功率是 ~1e-11 V²/Hz、无法直接画）
    db_line = 10.0 * np.log10(np.maximum(psds[channel_index], 1e-30))

    f_idx = _downsample_indices(np, len(freqs), max_freqs)
    out_freqs = [round(float(freqs[i]), 3) for i in f_idx]
    out_power = [round(float(db_line[i]), 4) for i in f_idx]

    bands = _band_stats(np, freqs, db_line)
    finite = db_line[np.isfinite(db_line)]
    return {
        "data_type": "psd",
        "study_output_id": str(getattr(dataset, "id", "") or ""),
        "condition": getattr(dataset, "condition", None),
        "method": "welch",
        "unit": "dB",
        "sfreq": sfreq,
        "channel": chosen,
        "n_channels_total": len(ch_names),
        "ch_names_all": ch_names,
        "freqs": out_freqs,
        "power": out_power,
        "fmin": round(float(freqs[0]), 3) if freqs.size else None,
        "fmax": round(float(freqs[-1]), 3) if freqs.size else None,
        "pmax": round(float(np.nanmax(finite)), 4) if finite.size else None,
        "pmin": round(float(np.nanmin(finite)), 4) if finite.size else None,
        "bands": bands,
    }


def _resolve_channel_index(np, ch_names: list[str], psds, channel: str | None) -> int:
    if channel:
        wanted = str(channel).strip()
        for i, name in enumerate(ch_names):
            if name == wanted:
                return i
    # 默认:总功率最大的通道(更有信息量)
    try:
        return int(np.argmax(np.nansum(psds, axis=1)))
    except Exception:  # noqa: BLE001
        return 0


def _downsample_indices(np, n: int, max_count: int):
    if n <= 0:
        return np.array([], dtype=int)
    count = min(max(2, int(max_count)), int(n))
    return np.unique(np.linspace(0, n - 1, count).astype(int))


def _band_stats(np, freqs, db_line) -> list[dict[str, Any]]:
    """各频带的平均功率(dB)。"""
    out: list[dict[str, Any]] = []
    for name, lo, hi in EEG_BANDS:
        fmask = (freqs >= lo) & (freqs < hi)
        if not bool(fmask.any()):
            continue
        block = db_line[fmask]
        value = float(np.nanmean(block)) if block.size else 0.0
        out.append({"name": name, "fmin": lo, "fmax": hi, "value": round(value, 4)})
    return out
