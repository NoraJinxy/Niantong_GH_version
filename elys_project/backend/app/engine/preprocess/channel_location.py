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
    """把 montage 参数解析成 MNE 标准帽名。

    auto 按通道数选 10-20 / 10-05；其余原样透传——厂家预设（biosemi64 / GSN-HydroCel-128 /
    EGI_256 / easycap-M1 等）大小写敏感，绝不能 lower，否则 make_standard_montage 认不出。
    """
    req = (requested or "auto").strip()
    if req.lower() == "auto":
        # 低密度（≤32 导）用 10-20；高密度用 10-05（10-05 是 10-20 命名的超集，向下兼容）
        return "standard_1020" if n_eeg <= 32 else "standard_1005"
    return req


def run_channel_location(raw: Any, params: dict[str, Any], custom_montage_path: str | None = None) -> Any:
    """给 raw 指派电极位置（montage）。raw→raw，可选自动规范通道名。

    montage 三种来源：
    - auto / 标准帽（standard_1020/1005）/ 厂家预设（biosemi* / GSN-HydroCel-* / EGI_256 / easycap-*）
      → make_standard_montage（标准模板坐标，非个体真实数字化）；
    - custom → 读 custom_montage_path 指向的上传文件（由 dispatcher 按 custom_montage_file_id 解析出物理路径）。
    流程：先按归一化名把数据通道对到所选帽的标准命名（rename），再 set_montage 写入坐标。
    写入的坐标用于地形图 / ICA 成分图 / 坏导插值。
    """
    mne = _mne()
    requested = str(params.get("montage") or "auto")
    rename = bool(params.get("rename", True))
    on_missing = str(params.get("on_missing") or "ignore").strip().lower()
    if on_missing not in ("ignore", "warn", "raise"):
        on_missing = "ignore"

    located = raw.copy().load_data()

    if requested.strip().lower() == "custom":
        if not custom_montage_path:
            raise ValueError(
                "选择了「自定义电极文件」，但没拿到有效文件。请在数据集详情页的「数据文件」里上传电极位置文件后，回到节点重新选择。"
            )
        montage = mne.channels.read_custom_montage(custom_montage_path)
    else:
        # 统计 EEG 通道数以决定 auto 帽
        try:
            n_eeg = len(mne.pick_types(located.info, eeg=True, meg=False, exclude=[]))
        except Exception:
            n_eeg = len(located.ch_names)
        montage_name = _resolve_montage_name(requested, n_eeg)
        builtin = set(mne.channels.get_builtin_montages())
        if montage_name not in builtin:
            raise ValueError(
                f"未知的电极帽模板「{montage_name}」。可用内置模板：{', '.join(sorted(builtin))}。"
            )
        montage = mne.channels.make_standard_montage(montage_name)

    # rename：把数据通道名对到所选帽里的标准命名（仅当归一化能匹配且写法不同、不与现有名冲突）
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
