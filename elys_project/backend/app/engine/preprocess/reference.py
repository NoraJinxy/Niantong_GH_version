"""
Purpose: Run EEG preprocessing operations for Pipeline nodes in the MNE-based engine.
Related: app/pipeline/dispatcher.py, app/pipeline/nodes/*.json, docs_v2/5-00.
"""

from __future__ import annotations

from typing import Any


def run_rereference(raw: Any, params: dict[str, Any]) -> Any:
    """Re-reference EEG using selected channels as the reference.

    语义（与节点 spec 描述一致）：
      - 用户在 ref_channels 里勾选 1 个通道 → 该通道作为参考
      - 勾选多个通道 → 这些通道的平均作为参考
      - 勾选所有通道 → 共同平均参考 (common average reference)，等价于 MNE 的 ref_channels="average"

    旧版有 mode='average' / mode='channels' 双分支，本次统一为只看 ref_channels（删除 mode 参数）。
    """
    ref_channels_raw = params.get("ref_channels")
    if not isinstance(ref_channels_raw, list) or not ref_channels_raw:
        raise ValueError(
            "Re-reference requires at least one channel in ref_channels. "
            "勾选 1 个 = 单通道参考；多个 = 平均参考；全选 = 共同平均参考。"
        )

    normalized = [str(channel).strip() for channel in ref_channels_raw if str(channel).strip()]
    if not normalized:
        raise ValueError("Re-reference ref_channels are all empty strings.")

    rereferenced = raw.copy().load_data()
    missing = [channel for channel in normalized if channel not in rereferenced.ch_names]
    if missing:
        raise ValueError(f"Reference channels not found: {', '.join(missing)}")

    # 全选时也走 ref_channels=list（MNE 内部减去平均），与"average"模式等价。
    # 用 list 形式让回归 / cache 行为可预测：哈希值取决于 ref_channels 内容，重选会触发重跑。
    rereferenced.set_eeg_reference(ref_channels=normalized, projection=False, verbose="ERROR")
    return rereferenced
