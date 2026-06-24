"""
Purpose: Run EEG preprocessing operations for Pipeline nodes in the MNE-based engine.
Related: app/pipeline/dispatcher.py, app/pipeline/nodes/*.json, docs_v2/5-00.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def run_resample(raw: Any, params: dict[str, Any]) -> Any:
    sfreq = float(params.get("sfreq") or 0)
    if sfreq <= 0:
        raise ValueError("Resample.sfreq must be greater than 0.")

    # 上采样防呆：目标采样率高于原始采样率 = 上采样。FFT 插值只会得到
    # 看似平滑、实则不含新信息的波形，几乎总是手误。厚层放行（不 block），记一条 warning。
    original_sfreq = float(raw.info["sfreq"])
    upsampled = sfreq > original_sfreq
    if upsampled:
        logger.warning(
            "Resample target %.4g Hz is higher than the original sampling rate "
            "%.4g Hz; this is upsampling (FFT interpolation), which adds no new "
            "information and is usually unintended. Proceeding anyway.",
            sfreq,
            original_sfreq,
        )

    resampled = raw.copy().load_data()
    resampled.resample(sfreq=sfreq, npad="auto", verbose="ERROR")
    return resampled
