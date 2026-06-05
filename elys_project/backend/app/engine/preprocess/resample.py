"""
Purpose: Run EEG preprocessing operations for Pipeline nodes in the MNE-based engine.
Related: app/pipeline/dispatcher.py, app/pipeline/nodes/*.json, docs_v2/5-00.
"""

from __future__ import annotations

from typing import Any


def run_resample(raw: Any, params: dict[str, Any]) -> Any:
    sfreq = float(params.get("sfreq") or 0)
    if sfreq <= 0:
        raise ValueError("Resample.sfreq must be greater than 0.")

    resampled = raw.copy().load_data()
    resampled.resample(sfreq=sfreq, npad="auto", verbose="ERROR")
    return resampled
