"""
Purpose: Group analysis – N-to-1 PSD merge (stack per-subject PSDs into a group tensor).
Related: app/pipeline/dispatcher.py (_execute_group_merge_psd), app/engine/io.py.
"""

from __future__ import annotations

from typing import Any

from app.engine.io import load_psd_npz, resolve_path_reference


def run_group_merge_psd(input_data_infos: list[dict[str, Any]], params: dict[str, Any]) -> dict[str, Any]:
    """从 N 个单被试 PSD data_info 读出 .npz，堆叠成 (n_subjects, n_channels, n_freqs)。

    每个 data_info 须含 storage_uri / fif_abs_path / storage_path 之一（dispatcher 已写入）。
    返回 dict 可直接传给 io.save_group_psd_npz + io.summarize_group_psd。
    """
    import numpy as np  # noqa: PLC0415

    label = str(params.get("label") or "")
    psd_list: list[Any] = []
    subjects: list[str] = []
    ch_names: list[str] | None = None
    freqs: Any = None
    sfreq: float = 0.0

    for index, data_info in enumerate(input_data_infos):
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
        psd_data = load_psd_npz(path)

        if ch_names is None:
            ch_names = psd_data["ch_names"]
            freqs = psd_data["freqs"]
            sfreq = psd_data["sfreq"]

        psd_list.append(psd_data["psds"])
        subj = (
            data_info.get("subject")
            or data_info.get("bids_subject_id")
            or data_info.get("subject_id")
            or str(index)
        )
        subjects.append(str(subj))

    if not psd_list:
        raise ValueError("run_group_merge_psd: input_data_infos is empty, nothing to merge.")

    group_psds = np.stack(psd_list, axis=0)  # (n_subjects, n_channels, n_freqs)
    return {
        "group_psds": group_psds,
        "freqs": freqs,
        "ch_names": ch_names or [],
        "sfreq": sfreq,
        "n_subjects": len(psd_list),
        "subjects": subjects,
        "label": label,
    }
