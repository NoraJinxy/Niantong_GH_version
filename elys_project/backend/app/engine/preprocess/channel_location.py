"""
Purpose: Assign standard channel locations (montage) for Pipeline nodes in the MNE-based engine.
Related: app/pipeline/dispatcher.py, app/pipeline/nodes/eeg_preproc_channel_location.json,
         app/pipeline/timeseries.py（地形图读取 montage 坐标，与本节点写入的坐标对应）。
"""

from __future__ import annotations

from typing import Any


def _mne():
    try:
        import mne
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("MNE is required for channel-location pipeline nodes.") from exc
    return mne


def _norm_ch_key(name: str) -> str:
    """通道名归一化：大写、只留字母数字（FP1 / 'EEG Fp1-Ref' → FP1），供跨命名匹配电极帽。"""
    return "".join(ch for ch in str(name or "").upper() if ch.isalnum())


def _resolve_montage_name(requested: str, n_eeg: int) -> str:
    requested = (requested or "auto").strip().lower()
    if requested in ("standard_1005", "standard_1020"):
        return requested
    # auto：低密度（≤32 导）用 10-20；高密度用 10-05（10-05 是 10-20 命名的超集，向下兼容）
    return "standard_1020" if n_eeg <= 32 else "standard_1005"


def run_channel_location(raw: Any, params: dict[str, Any]) -> Any:
    """给 raw 指派标准电极位置（montage）。raw→raw，可选自动规范通道名。

    流程：先按归一化名把数据通道对到所选标准帽的标准命名（rename），再 set_montage 写入坐标。
    写入的坐标用于地形图 / ICA 成分图 / 坏导插值；为标准模板坐标，非个体真实数字化坐标。
    """
    mne = _mne()
    requested = str(params.get("montage") or "auto")
    rename = bool(params.get("rename", True))
    on_missing = str(params.get("on_missing") or "ignore").strip().lower()
    if on_missing not in ("ignore", "warn", "raise"):
        on_missing = "ignore"

    located = raw.copy().load_data()

    # 统计 EEG 通道数以决定 auto 帽
    try:
        n_eeg = len(mne.pick_types(located.info, eeg=True, meg=False, exclude=[]))
    except Exception:
        n_eeg = len(located.ch_names)
    montage_name = _resolve_montage_name(requested, n_eeg)
    montage = mne.channels.make_standard_montage(montage_name)

    # rename：把数据通道名对到标准帽里的标准命名（仅当归一化能匹配且写法不同、不与现有名冲突）
    if rename:
        std_by_key = {_norm_ch_key(nm): nm for nm in montage.ch_names}
        existing = set(located.ch_names)
        mapping: dict[str, str] = {}
        used: set[str] = set()
        for nm in located.ch_names:
            std = std_by_key.get(_norm_ch_key(nm))
            if std and std != nm and std not in existing and std not in used:
                mapping[nm] = std
                used.add(std)
        if mapping:
            located.rename_channels(mapping)

    located.set_montage(montage, match_case=False, on_missing=on_missing, verbose="ERROR")
    return located
