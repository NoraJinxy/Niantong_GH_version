"""
Purpose: 节点级缓存策略 —— 按「计算成本 × 落盘体积」自动判定一个节点的产物该不该缓存。
存储优先（STORAGE_WEIGHT > 计算权重）：默认倾向不缓存，只有「省得多、占得少」才破例缓存。

评分（见 日志/2_meeting260609/Save保留策略-重构方案.md §4.2）：
    cache_score = compute_cost − STORAGE_WEIGHT × output_footprint，> 0 才缓存。
三条硬规则优先于评分：
    1) interactive 节点强制不缓存 —— 缓存恢复会短路掉 waiting_user_input 的人工确认；
    2) output_footprint=explosive 永不物化全量（如单试次 TFR）；
    3) 缺标签默认不缓存（保守侧）——LoadData 这类 source 节点不打标签、天然落到此分支。

当前 8 节点里只有 ica/compute（expensive=3 − 2×small=1 = +1）命中缓存。

Related:
- app/pipeline/nodes/*.json (compute_cost / output_footprint 标签)
- app/pipeline/executor.py (_restore_cached_node_output 缓存门控)
- app/pipeline/cache.py (实际缓存恢复)
"""

from __future__ import annotations

from typing import Any

# 全局旋钮：存储比计算重要几倍。越大越省空间（越少缓存）。见 §4.2。
STORAGE_WEIGHT = 2

_COMPUTE_RANK = {"cheap": 1, "moderate": 2, "expensive": 3}
_FOOTPRINT_RANK = {"small": 1, "medium": 2, "large": 3}


def cache_score(node_spec: dict[str, Any] | None) -> int | None:
    """缓存评分 = compute_cost − STORAGE_WEIGHT × footprint。

    返回 None 表示「不参与评分、保守不缓存」：
      - 缺 compute_cost / output_footprint 标签（如 LoadData 等 source 节点）；
      - output_footprint=explosive（硬规则：永不物化全量）。
    """
    spec = node_spec or {}
    compute = _COMPUTE_RANK.get(str(spec.get("compute_cost") or ""))
    footprint_raw = str(spec.get("output_footprint") or "")
    if compute is None or not footprint_raw:
        return None
    if footprint_raw == "explosive":
        return None
    footprint = _FOOTPRINT_RANK.get(footprint_raw)
    if footprint is None:
        return None
    return compute - STORAGE_WEIGHT * footprint


def is_cache_eligible(node_spec: dict[str, Any] | None) -> bool:
    """这个节点的产物该不该缓存。存储优先 + 三条硬规则。"""
    spec = node_spec or {}
    backend = spec.get("backend") if isinstance(spec.get("backend"), dict) else {}
    # 硬规则①：交互节点强制不缓存——缓存恢复会跳过 waiting_user_input 的人工选择。
    if (backend or {}).get("interactive") is True:
        return False
    score = cache_score(spec)
    if score is None:
        return False  # explosive / 缺标签 / source 节点 → 保守不缓存
    return score > 0


__all__ = ["STORAGE_WEIGHT", "cache_score", "is_cache_eligible"]
