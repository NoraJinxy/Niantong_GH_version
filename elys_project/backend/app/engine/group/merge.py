"""
Purpose: Group analysis – N-to-1 PSD merge (stack per-subject PSDs into a group tensor).
Related: app/pipeline/dispatcher.py (_execute_group_merge_psd), app/engine/io.py.
"""

from __future__ import annotations

from typing import Any

from app.engine.io import load_psd_npz, resolve_path_reference


def run_group_merge_psd(input_data_infos: list[dict[str, Any]], params: dict[str, Any]) -> dict[str, Any]:
    """从 N 个单被试 PSD data_info 读出 .npz，**按共有通道对齐**后堆叠成 (n_subjects, n_channels, n_freqs)。

    被试间可能用不同 montage（如 Emotiv 不同型号 EEG 电极数 10/14/32 不等），各 PSD 形状不同无法直接
    堆叠。grand average 本就只能在所有被试都有的电极上做，故这里取通道名**交集**、按交集逐被试重排再堆叠。
    频率轴须一致（同采样率 + 同 PSD 参数应自然一致；否则报错，无法跨被试平均）。

    每个 data_info 须含 storage_uri / fif_abs_path / storage_path 之一（dispatcher 已写入）。
    返回 dict 可直接传给 io.save_group_psd_npz + io.summarize_group_psd。
    """
    import numpy as np  # noqa: PLC0415

    label = str(params.get("label") or "")

    # 1) 读出每个被试的 PSD（psds / ch_names / freqs / sfreq）
    entries: list[dict[str, Any]] = []
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
        subj = (
            data_info.get("subject")
            or data_info.get("bids_subject_id")
            or data_info.get("subject_id")
            or str(index)
        )
        entries.append(
            {
                "subject": str(subj),
                "psds": np.asarray(psd_data["psds"], dtype=float),  # (n_ch, n_freq)
                "ch_names": [str(c) for c in psd_data["ch_names"]],
                "freqs": np.asarray(psd_data["freqs"], dtype=float),
                "sfreq": float(psd_data["sfreq"]),
            }
        )

    if not entries:
        raise ValueError("run_group_merge_psd: input_data_infos is empty, nothing to merge.")

    # 2) 频率轴一致性：同采样率 + 同 PSD 参数应一致；不一致则无法跨被试平均
    ref_freqs = entries[0]["freqs"]
    for e in entries[1:]:
        if e["freqs"].shape != ref_freqs.shape or not np.allclose(e["freqs"], ref_freqs):
            raise ValueError(
                f"被试 {e['subject']} 的 PSD 频率轴与首个被试不一致"
                "（采样率或 PSD 参数不同），无法做 Grand Average。"
            )

    # 3) 通道取交集（保持首个被试的顺序，结果确定）
    common = [name for name in entries[0]["ch_names"] if all(name in e["ch_names"] for e in entries[1:])]
    if not common:
        raise ValueError(
            "各被试 PSD 没有共有通道，无法做 Grand Average："
            "被试 montage 不一致（如 Emotiv 不同型号电极数不同），请筛选同导联的被试再合并。"
        )

    # 4) 逐被试按交集重排 → 堆叠成 (n_subjects, n_common_channels, n_freqs)
    stacked: list[Any] = []
    subjects: list[str] = []
    for e in entries:
        idx = {name: i for i, name in enumerate(e["ch_names"])}
        stacked.append(np.stack([e["psds"][idx[name]] for name in common], axis=0))
        subjects.append(e["subject"])
    group_psds = np.stack(stacked, axis=0)

    return {
        "group_psds": group_psds,
        "freqs": ref_freqs,
        "ch_names": common,
        "sfreq": entries[0]["sfreq"],
        "n_subjects": len(entries),
        "subjects": subjects,
        "label": label,
    }
