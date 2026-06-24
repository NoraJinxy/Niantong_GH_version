"""
Purpose: Run ICA compute/apply operations for Pipeline nodes in the EEG engine.
Related: app/pipeline/dispatcher.py, app/pipeline/nodes/eeg_ica_*.json, docs_v2/5-00.
"""

"""ICA helpers for pipeline node executors."""

from .apply import parse_excluded_components, run_apply_ica
from .compute import component_preview, run_compute_ica, summarize_ica

__all__ = [
    "component_preview",
    "parse_excluded_components",
    "run_apply_ica",
    "run_compute_ica",
    "summarize_ica",
]
