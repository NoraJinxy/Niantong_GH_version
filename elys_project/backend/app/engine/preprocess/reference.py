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

    # 平均参考的分母必须排除坏道：MNE 仅对 ref_channels="average"/"REST" 字符串路径自动排除
    # info['bads']，显式通道 list 不排除。若上游已标坏道(bad_channels / artifact_mark)却未插值，
    # 坏道的大幅噪声会被平均进参考、再减回每根通道，全通道不可逆污染(PREP 铁律)。这里手动剔除。
    bads = set(rereferenced.info.get("bads") or [])
    ref_used = [channel for channel in normalized if channel not in bads]
    if not ref_used:
        raise ValueError(
            "选作参考的通道全部是已标记的坏道，无法作参考。"
            "请先插值/取消坏道标记，或改选其它参考通道。"
        )

    # 全选时走 ref_channels=好通道 list（MNE 内部减去这些通道的平均），等价于排坏道的共同平均参考。
    # 用 list 形式让回归 / cache 行为可预测：哈希值取决于 ref_channels 内容，重选会触发重跑。
    rereferenced.set_eeg_reference(ref_channels=ref_used, projection=False, verbose="ERROR")
    return rereferenced
