"""
Purpose: Provide shared EEG engine helpers used by Pipeline node executors.
Related: app/pipeline/dispatcher.py, app/engine/preprocess/*, app/engine/analysis/*.
"""

from .io import (
    read_epochs_from_data_info,
    read_raw_from_data_info,
    save_epochs_fif,
    save_evoked_fif,
    save_raw_fif,
    summarize_epochs,
    summarize_evoked,
    summarize_mne_object,
    summarize_raw,
)
from .testing import make_synthetic_raw

__all__ = [
    "make_synthetic_raw",
    "read_epochs_from_data_info",
    "read_raw_from_data_info",
    "save_epochs_fif",
    "save_evoked_fif",
    "save_raw_fif",
    "summarize_epochs",
    "summarize_evoked",
    "summarize_mne_object",
    "summarize_raw",
]
