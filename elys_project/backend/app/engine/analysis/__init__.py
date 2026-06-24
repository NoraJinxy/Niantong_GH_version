"""
Purpose: Run EEG analysis operations such as epoching or ERP generation for Pipeline nodes.
Related: app/pipeline/dispatcher.py, app/pipeline/nodes/*.json, docs_v2/5-00.
"""

from .baseline import run_baseline
from .epoching import run_epoch_segment
from .erp import run_erp_average
from .psd import run_psd
from .tfr import run_tfr

__all__ = [
    "run_baseline",
    "run_epoch_segment",
    "run_erp_average",
    "run_psd",
    "run_tfr",
]
