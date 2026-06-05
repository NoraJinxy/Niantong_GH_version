"""
Purpose: Run EEG preprocessing operations for Pipeline nodes in the MNE-based engine.
Related: app/pipeline/dispatcher.py, app/pipeline/nodes/*.json, docs_v2/5-00.
"""

from .filters import run_fir_filter
from .reference import run_rereference
from .resample import run_resample

__all__ = [
    "run_fir_filter",
    "run_rereference",
    "run_resample",
]
