"""
Purpose: Pipeline 拓扑分析工具 —— 判断每个节点是否为"叶子节点"（无下游连接），
         用于自动决定 retention 策略（叶子节点默认保留，中间节点默认不保留）。

Related: app/pipeline/dispatcher.py, app/pipeline/nodes/*.json (save.* 配置)。
背景: 见 Save 节点废弃方案 (P0-P5)。
"""

from __future__ import annotations

from typing import Any


# 节点拓扑角色
ROLE_LEAF = "leaf"               # 叶子节点：输出无人连接 → 默认 retention=current（保留）
ROLE_INTERMEDIATE = "intermediate"  # 中间节点：输出有下游 → 默认 retention=none（不保留）
ROLE_SOURCE_ONLY = "source"      # 仅源节点（如 LoadData）：通常不参与 save 决策

# LoadData 等 source 节点的 type 前缀
SOURCE_NODE_TYPES = {"eeg/data/load"}


def analyze_pipeline_topology(
    graph: dict[str, Any] | None,
) -> dict[str, str]:
    """根据 pipeline 图分析每个节点的拓扑角色。

    Args:
        graph: pipeline 定义中的 graph 字段，结构为
               { "nodes": [{"id": "n1", "type": "eeg/...", ...}, ...],
                 "links": [{"from": {"node": "n1", "port": "output"},
                            "to": {"node": "n2", "port": "input"}}, ...] }

    Returns:
        映射 {node_id: "leaf" | "intermediate" | "source"}。
        - source: type 是 LoadData 等已知源节点
        - leaf: 该节点的任何输出端口都没有出现在 links.from 中
        - intermediate: 否则

    特殊情况:
        - 图为空或缺失字段 → 返回空 dict
        - 节点没有 id 字段 → 跳过该节点
    """
    if not graph or not isinstance(graph, dict):
        return {}

    nodes = graph.get("nodes") or []
    links = graph.get("links") or []
    if not isinstance(nodes, list):
        return {}

    # 收集所有 "被连接出去" 的 (node_id, port) 对
    # 一个节点有下游 ⟺ 它的某个输出端口出现在 link.from.node 上
    consumed_nodes: set[str] = set()
    for link in links:
        if not isinstance(link, dict):
            continue
        from_spec = link.get("from") if isinstance(link.get("from"), dict) else {}
        from_node = from_spec.get("node") if isinstance(from_spec, dict) else None
        if isinstance(from_node, str) and from_node:
            consumed_nodes.add(from_node)

    result: dict[str, str] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = node.get("id")
        node_type = node.get("type") or ""
        if not isinstance(node_id, str) or not node_id:
            continue

        if node_type in SOURCE_NODE_TYPES:
            result[node_id] = ROLE_SOURCE_ONLY
        elif node_id in consumed_nodes:
            result[node_id] = ROLE_INTERMEDIATE
        else:
            result[node_id] = ROLE_LEAF

    return result


def is_leaf(topology: dict[str, str], node_id: str) -> bool:
    """便捷查询：节点是否为叶子节点。"""
    return topology.get(node_id) == ROLE_LEAF


def is_source(topology: dict[str, str], node_id: str) -> bool:
    """便捷查询：节点是否为源节点（如 LoadData）。"""
    return topology.get(node_id) == ROLE_SOURCE_ONLY


def leaf_node_ids(topology: dict[str, str]) -> list[str]:
    """返回所有叶子节点的 ID 列表（按字典序排序，便于稳定输出）。"""
    return sorted(node_id for node_id, role in topology.items() if role == ROLE_LEAF)


def intermediate_node_ids(topology: dict[str, str]) -> list[str]:
    """返回所有中间节点的 ID 列表。"""
    return sorted(node_id for node_id, role in topology.items() if role == ROLE_INTERMEDIATE)


def summarize_topology(topology: dict[str, str]) -> dict[str, int]:
    """返回拓扑统计摘要，用于日志/manifest。

    示例: {"leaf": 2, "intermediate": 3, "source": 1, "total": 6}
    """
    counts: dict[str, int] = {ROLE_LEAF: 0, ROLE_INTERMEDIATE: 0, ROLE_SOURCE_ONLY: 0}
    for role in topology.values():
        if role in counts:
            counts[role] += 1
    counts["total"] = len(topology)
    return counts


__all__ = [
    "ROLE_LEAF",
    "ROLE_INTERMEDIATE",
    "ROLE_SOURCE_ONLY",
    "SOURCE_NODE_TYPES",
    "analyze_pipeline_topology",
    "is_leaf",
    "is_source",
    "leaf_node_ids",
    "intermediate_node_ids",
    "summarize_topology",
]
