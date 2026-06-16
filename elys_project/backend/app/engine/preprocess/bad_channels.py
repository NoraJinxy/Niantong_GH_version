"""
Purpose: Automatic bad-channel detection + interpolation for Pipeline nodes (MNE-based engine).
Related: app/pipeline/dispatcher.py, app/pipeline/nodes/eeg_preproc_bad_channels.json,
         app/engine/preprocess/channel_location.py（插值依赖本节点之前指派的电极坐标）。
"""

from __future__ import annotations

from typing import Any


def _mne():
    try:
        import mne
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("MNE is required for bad-channel pipeline nodes.") from exc
    return mne


def _resolve_int(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        number = int(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        number = default
    return max(lo, min(number, hi))


def _resolve_float(value: Any, default: float, lo: float) -> float:
    try:
        number = float(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        number = default
    return max(lo, number)


def run_bad_channels(raw: Any, params: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """自动检测坏道（默认 MNE LOF 局部离群因子），可选球面样条插值修复。raw→raw。

    返回 (处理后的 raw, {"bad_channels": 明细})。明细由 dispatcher 并入 preview /
    mne_summary，作为该步溯源——把"自动判了哪些坏道 / 有没有插值"摊在结果里，
    而不是黑箱改数据。

    科学性对标 MNE / PREP：
      - 检测 lof（默认）：mne.preprocessing.find_bad_channels_lof —— LOF（Local Outlier
        Factor，局部离群因子）按每个电极相对邻近电极的"离群程度"打分，高于 threshold 判坏。
        MNE 1.7 为 EEG 内置，偏温和。文献：Kumaravel et al. 2022。
      - 检测 ransac（可选）：pyprep NoisyChannels.find_bad_by_ransac —— PREP 流程的 RANSAC
        法，随机抽样好电极、按电极位置互相预测，预测不合（相关 < corr_thresh）判坏；更激进，
        需要电极坐标 + pyprep 库。
      - 修复：raw.interpolate_bads —— 球面样条插值，用周围好电极重建坏电极；
        需要电极坐标，故本节点之前要先接 Ch Loc Assign。
    """
    mne = _mne()
    method = str(params.get("method") or "lof").strip().lower()
    action = str(params.get("action") or "interpolate").strip().lower()
    threshold = _resolve_float(params.get("threshold"), 1.5, 1.0)
    n_neighbors = _resolve_int(params.get("n_neighbors"), 20, 2, 100)
    corr_thresh = _resolve_float(params.get("corr_thresh"), 0.75, 0.0)
    reset_bads = bool(params.get("reset_bads", True))

    if method not in {"lof", "ransac"}:
        raise ValueError(f"Unknown bad-channel method: {method!r} (expected 'lof' or 'ransac').")
    if action not in {"interpolate", "mark"}:
        raise ValueError(f"Unknown bad-channel action: {action!r} (expected 'interpolate' or 'mark').")

    work = raw.copy().load_data()

    # 仅在 EEG 通道上检测；LOF 的近邻数不能超过可用 EEG 通道数
    eeg_picks = mne.pick_types(work.info, eeg=True, meg=False, exclude=[])
    n_eeg = len(eeg_picks)
    if n_eeg < 3:
        raise ValueError(f"LOF 坏道检测至少需要 3 个 EEG 通道，当前仅 {n_eeg} 个。")
    n_neighbors = min(n_neighbors, n_eeg - 1)

    preexisting = list(work.info.get("bads", []) or [])

    if method == "lof":
        detected = list(
            mne.preprocessing.find_bad_channels_lof(
                work,
                n_neighbors=n_neighbors,
                picks="eeg",
                threshold=threshold,
                verbose="ERROR",
            )
        )
        method_detail: dict[str, Any] = {"threshold": threshold, "n_neighbors": n_neighbors}
    else:  # ransac —— pyprep / PREP 流程
        try:
            from pyprep import NoisyChannels  # noqa: PLC0415 —— 懒加载：未装 pyprep 时只 ransac 失败、lof 不受影响
        except ImportError as exc:
            raise RuntimeError(
                "RANSAC 坏道检测需要 pyprep 库（已列入 requirements.txt，云端重新部署即 pip install）。"
            ) from exc
        # RANSAC 按电极位置互相预测，没坐标做不了
        if work.get_montage() is None:
            raise ValueError(
                "RANSAC 坏道检测需要电极坐标：请在本节点之前接 'Ch Loc Assign' 指派电极位置。"
            )
        nc = NoisyChannels(work, random_state=42)  # 固定随机种子 → 同输入同结果，可复现
        nc.find_bad_by_ransac(corr_thresh=corr_thresh)
        detected = list(nc.get_bads())
        method_detail = {"corr_thresh": corr_thresh}

    all_bads = list(dict.fromkeys(preexisting + detected))
    work.info["bads"] = all_bads

    detail: dict[str, Any] = {
        "method": method,
        "n_eeg_channels": n_eeg,
        "preexisting_bads": preexisting,
        "detected_bads": detected,
        "n_detected": len(detected),
        "bads": all_bads,
        "action": action,
        "interpolated": False,
        **method_detail,
    }

    # 仅标记，或没有任何坏道 → 不改数据，直接回
    if action == "mark" or not all_bads:
        return work, {"bad_channels": detail}

    # 插值修复：球面样条需要电极坐标
    if work.get_montage() is None:
        raise ValueError(
            "坏道插值需要电极坐标：请在本节点之前接 'Ch Loc Assign' 指派电极位置（10-20 / 10-05）。"
        )
    work.interpolate_bads(reset_bads=reset_bads, verbose="ERROR")
    detail["interpolated"] = True
    detail["interpolated_bads"] = all_bads
    detail["reset_bads"] = reset_bads
    return work, {"bad_channels": detail}
