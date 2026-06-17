"""
Purpose: Group analysis – grand average PSD (mean ± SEM across subjects).
Related: app/pipeline/dispatcher.py (_execute_group_average_psd), app/engine/io.py.
"""

from __future__ import annotations

from typing import Any

from app.engine.io import load_group_psd_npz, resolve_path_reference


def run_group_average_psd(data_info: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """从一个 group_psd data_info 读出 .npz，计算 grand average ± SEM。

    输出 dict 可直接传给 io.save_psd_grandavg_npz + io.summarize_psd_grandavg。
    """
    import numpy as np  # noqa: PLC0415

    path = resolve_path_reference(
        data_info,
        (
            "storage_uri",
            "artifact_storage_uri",
            "fif_abs_path",
            "fif_path",
            "storage_path",
            "artifact_storage_path",
        ),
    )
    group = load_group_psd_npz(path)
    group_psds = group["group_psds"]  # (n_subjects, n_channels, n_freqs)
    n_subjects = group_psds.shape[0]

    mean_psds = np.mean(group_psds, axis=0)  # (n_channels, n_freqs)
    # ddof=1 无偏标准差，n=1 时 SEM 取 0 避免 NaN
    sem_psds = (
        np.std(group_psds, axis=0, ddof=1) / np.sqrt(n_subjects)
        if n_subjects > 1
        else np.zeros_like(mean_psds)
    )

    return {
        "psds": mean_psds,
        "psds_sem": sem_psds,
        "freqs": group["freqs"],
        "ch_names": group["ch_names"],
        "sfreq": group["sfreq"],
        "n_subjects": n_subjects,
        "label": group.get("label", ""),
        "subjects": group.get("subjects", []),
    }
