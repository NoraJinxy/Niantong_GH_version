"""MNE reference comparison for the ELYS ICLabel node."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from node_mne_common import run_one  # noqa: E402


if __name__ == "__main__":
    run_one("iclabel")
