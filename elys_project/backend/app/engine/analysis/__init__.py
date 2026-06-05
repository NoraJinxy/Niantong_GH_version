"""
Purpose: Run EEG analysis operations such as epoching or ERP generation for Pipeline nodes.
Related: app/pipeline/dispatcher.py, app/pipeline/nodes/*.json, docs_v2/5-00.
"""

from .epoching import run_epoch_segment
from .erp import run_erp_average

__all__ = [
    "run_epoch_segment",
    "run_erp_average",
]
