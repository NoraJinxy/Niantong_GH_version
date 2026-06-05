"""
Purpose: Provide shared EEG engine helpers used by Pipeline node executors.
Related: app/pipeline/dispatcher.py, app/engine/preprocess/*, app/engine/analysis/*.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np


def make_synthetic_raw(
    *,
    n_channels: int = 4,
    sfreq: float = 100.0,
    duration_seconds: float = 2.0,
    ch_names: Sequence[str] | None = None,
    ch_types: Sequence[str] | str = "eeg",
    seed: int = 13,
    add_annotations: bool = True,
):
    mne = _mne()
    n_times = max(1, int(round(float(sfreq) * float(duration_seconds))))
    names = list(ch_names) if ch_names is not None else [f"EEG{i + 1:03d}" for i in range(n_channels)]
    if len(names) != n_channels:
        raise ValueError("ch_names length must match n_channels")

    types: Sequence[str] | str
    if isinstance(ch_types, str):
        types = [ch_types] * n_channels
    else:
        types = list(ch_types)
        if len(types) != n_channels:
            raise ValueError("ch_types length must match n_channels")

    rng = np.random.default_rng(seed)
    times = np.arange(n_times, dtype=float) / float(sfreq)
    data = []
    for index in range(n_channels):
        frequency = 8.0 + index
        signal = 20e-6 * np.sin(2 * np.pi * frequency * times)
        noise = 2e-6 * rng.standard_normal(n_times)
        data.append(signal + noise)

    info = mne.create_info(ch_names=names, sfreq=float(sfreq), ch_types=types)
    raw = mne.io.RawArray(np.asarray(data), info, verbose="ERROR")
    if add_annotations and duration_seconds > 0.5:
        raw.set_annotations(mne.Annotations(onset=[0.25], duration=[0.1], description=["Synthetic/Event"]))
    return raw


def _mne():
    try:
        import mne
    except ImportError as exc:
        raise RuntimeError("MNE is required for synthetic engine test data.") from exc
    return mne
