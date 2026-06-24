"""
Purpose: 节点级缓存策略 —— 按「计算成本 × 落盘体积」自动判定产物留存，并单独控制执行前是否查缓存跳过。

两个关注点分离：
  - should_lookup_cache：执行节点前是否查历史命中、跳过重跑。跳过不产生新文件，
    与存储成本无关；只要不是 interactive / source / explosive 节点就应该查。
  - is_cache_eligible：产物是否值得长期保留供跨 execution 复用（存储成本权衡）。
    评分（见 日志/2_meeting260609/Save保留策略-重构方案.md §4.2）：
        cache_score = compute_cost − STORAGE_WEIGHT × output_footprint，> 0 才保留。

三条硬规则优先于评分（两个函数共享）：
    1) interactive 节点强制不缓存 —— 恢复会短路 waiting_user_input 的人工确认；
    2) output_footprint=explosive 永不物化全量（如单试次 TFR）；
    3) 缺 compute_cost / output_footprint 标签 → 视为 source 节点，保守不缓存。

当前 is_cache_eligible 只有 ica/compute（expensive=3 − 2×small=1 = +1）命中，
其余产物不做长期留存；但 should_lookup_cache 对所有非 interactive / non-source 节点
均返回 True，保证「无变化重跑」时能跳过计算。

Related:
- app/pipeline/nodes/*.json (compute_cost / output_footprint 标签)
- app/pipeline/executor.py (should_lookup_cache 门控缓存查找)
- app/pipeline/save_settings.py (is_cache_eligible 设 artifact.cache_eligible 标志)
- app/pipeline/cache.py (实际缓存恢复)
"""

from __future__ import annotations

from typing import Any

# 全局旋钮：存储比计算重要几倍。越大越省空间（越少长期保留）。见 §4.2。
STORAGE_WEIGHT = 2

_COMPUTE_RANK = {"cheap": 1, "moderate": 2, "expensive": 3}
_FOOTPRINT_RANK = {"small": 1, "medium": 2, "large": 3}


def cache_score(node_spec: dict[str, Any] | None) -> int | None:
    """缓存评分 = compute_cost − STORAGE_WEIGHT × footprint。

    返回 None 表示「不参与评分、保守不缓存产物」：
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
    """产物是否值得长期保留供跨 execution 复用（存储成本权衡）。
    供 save_settings 设 StudyOutput.cache_eligible 标志使用。
    不控制执行前是否查缓存——那由 should_lookup_cache 决定。
    """
    spec = node_spec or {}
    backend = spec.get("backend") if isinstance(spec.get("backend"), dict) else {}
    # 硬规则①：交互节点强制不缓存——缓存恢复会跳过 waiting_user_input 的人工选择。
    if (backend or {}).get("interactive") is True:
        return False
    score = cache_score(spec)
    if score is None:
        return False  # explosive / 缺标签 / source 节点 → 保守不留存
    return score > 0


def should_lookup_cache(node_spec: dict[str, Any] | None) -> bool:
    """执行节点前是否查历史缓存尝试跳过重跑。

    仅以下情况不查：
    ① interactive 节点 —— 缓存恢复会跳过 waiting_user_input 的人工确认；
    ② 没有 compute_cost + output_footprint 标签的节点（source 节点如 LoadData，无可复用产物）；
    ③ output_footprint=explosive —— 无法物化全量，历史不会有完整产物可恢复。

    与 is_cache_eligible 的区别：跳过重跑不产生新文件，与存储成本无关；
    即使产物评分为负（不值得长期留存），只要 hash 命中就应该跳过计算。
    """
    spec = node_spec or {}
    backend = spec.get("backend") if isinstance(spec.get("backend"), dict) else {}
    if (backend or {}).get("interactive") is True:
        return False
    compute = str(spec.get("compute_cost") or "")
    footprint = str(spec.get("output_footprint") or "")
    if not compute or not footprint:
        return False
    if footprint == "explosive":
        return False
    return True


__all__ = ["STORAGE_WEIGHT", "cache_score", "is_cache_eligible", "should_lookup_cache"]
