"""
Purpose: 沿 pipeline 图上游链路解析「某节点输入端的可用 condition（事件分组）」——
Epoch / ERP / TFR / PSD 条件选择器的**服务端单一事实源**，取代旧的「前端各自扫 LoadData」。
统一规则:节点 X 的候选 = 其全部直接上游「输出 condition 词表」的并集。
Related: app/pipeline/load_data.py, app/engine/analysis/event_conditions.py.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.engine.analysis.event_conditions import build_remap_source_target
from app.models import Study
from app.pipeline.load_data import resolve_load_data_selection
from app.schemas.pipeline import (
    ConditionOption,
    ConditionResolveResponse,
    PipelineValidationIssue,
)

LOAD_DATA_NODE_TYPE = "eeg/data/load"
EPOCH_NODE_TYPE = "eeg/epoch/segment"
EVENT_REMAP_NODE_TYPE = "eeg/preproc/event_remap"

# 这些节点不改事件描述 → condition 词表原样透传给下游：
# 预处理(滤波/重采样/重参考/通道定位/坏道/手动标记)、ICA 三件套、分析(ERP/TFR/PSD)。
# 注:artifact_mark 只加 BAD_ 注解、不改事件类型,故也透传;分析节点的输出 condition 继承自
# 上游 Epoch,供更下游(如 group)回溯。
PASSTHROUGH_NODE_TYPES = {
    "eeg/filter/apply",
    "eeg/preproc/resample",
    "eeg/preproc/rereference",
    "eeg/preproc/channel_location",
    "eeg/preproc/bad_channels",
    "eeg/preproc/artifact_mark",
    "eeg/ica/compute",
    "eeg/ica/apply",
    "eeg/ica/iclabel",
    "eeg/analysis/erp",
    "eeg/analysis/tfr",
    "eeg/analysis/psd",
}


def resolve_node_conditions(
    *, db: Session, study: Study, graph: dict[str, Any], node_id: str
) -> ConditionResolveResponse:
    """解析 node_id 输入端可用的 condition（沿 graph 上游链路）。

    候选 = 本节点全部直接上游「输出 condition 词表」的并集。各节点类型如何产出输出词表:
    - LoadData → 解析其数据集、并集 condition_groups;
    - Epoch    → 输入词表 ∩ 本节点已勾 conditions(= 它实际切出的 condition,喂给 ERP/TFR/PSD);
    - 透传类(预处理/ICA/分析) → = 输入词表;
    - 其余/未知类型 → = 输入词表。
    memo 防菱形图重复解析,visiting 防环(图本应无环)。
    """
    nodes: dict[str, dict[str, Any]] = {
        str(n.get("id")): n
        for n in (graph.get("nodes") or [])
        if isinstance(n, dict) and n.get("id")
    }
    incoming: dict[str, list[str]] = {}
    for link in graph.get("links") or []:
        if not isinstance(link, dict):
            continue
        frm = link.get("from") if isinstance(link.get("from"), dict) else {}
        to = link.get("to") if isinstance(link.get("to"), dict) else {}
        frm_node = frm.get("node")
        to_node = to.get("node")
        if isinstance(frm_node, str) and isinstance(to_node, str):
            incoming.setdefault(to_node, []).append(frm_node)

    warnings: list[PipelineValidationIssue] = []
    memo: dict[str, dict[str, dict[str, int]]] = {}
    visiting: set[str] = set()

    def input_vocab(nid: str) -> dict[str, dict[str, int]]:
        merged: dict[str, dict[str, int]] = {}
        for parent in incoming.get(nid, []):
            _merge(merged, output_vocab(parent))
        return merged

    def output_vocab(nid: str) -> dict[str, dict[str, int]]:
        if nid in memo:
            return memo[nid]
        if nid in visiting:
            return {}
        visiting.add(nid)
        node = nodes.get(nid) or {}
        ntype = str(node.get("type") or "")
        result: dict[str, dict[str, int]] = {}

        if ntype == LOAD_DATA_NODE_TYPE:
            node_params = node.get("params") if isinstance(node.get("params"), dict) else {}
            # 与前端 task#61 同口径:LoadData 永远 explicit,只认 Selected File 列表(dataset_ids);
            # 不回退 filter——否则未勾文件时后端会返回全库匹配 → 候选泄漏。
            ds_ids = node_params.get("dataset_ids")
            ds_filter = node_params.get("dataset_filter")
            params = {
                "selection_mode": "explicit",
                "dataset_ids": ds_ids if isinstance(ds_ids, list) else [],
                "dataset_filter": ds_filter if isinstance(ds_filter, dict) else {},
            }
            try:
                resolved = resolve_load_data_selection(
                    db=db, study=study, params=params, node_id=nid
                )
                for info in resolved.data_infos:
                    _aggregate(result, info.condition_groups)
            except Exception as exc:  # 单个 LoadData 解析失败不该炸整个 picker
                warnings.append(
                    PipelineValidationIssue(
                        code="CONDITION_RESOLVE_LOADDATA_FAILED",
                        message=f"上游 LoadData 解析失败: {exc}",
                        node_id=nid,
                        node_type=ntype,
                        severity="warning",
                    )
                )
        elif ntype == EPOCH_NODE_TYPE:
            inp = input_vocab(nid)
            params = node.get("params") if isinstance(node.get("params"), dict) else {}
            selected = _selected_condition_names(params.get("conditions"))
            # Epoch 实际切出的 = 已勾且在输入词表里真实存在的(ghost 名不下传给 ERP/TFR/PSD)
            result = {name: inp[name] for name in selected if name in inp}
        elif ntype == EVENT_REMAP_NODE_TYPE:
            # 事件重映射:按规则把输入词表重命名/合并/丢弃 → 输出词表(方案 C)
            node_params = node.get("params") if isinstance(node.get("params"), dict) else {}
            result = _remap_vocab(input_vocab(nid), node_params.get("rules"))
        else:
            # 透传类与未知类型:输出词表 = 输入词表
            result = input_vocab(nid)

        memo[nid] = result
        visiting.discard(nid)
        return result

    candidates = input_vocab(node_id)
    options = [
        ConditionOption(
            name=name,
            count=int(info.get("count", 0)),
            datasets=int(info.get("datasets", 0)),
        )
        for name, info in candidates.items()
    ]
    options.sort(key=_option_sort_key)
    return ConditionResolveResponse(node_id=node_id, conditions=options, warnings=warnings)


def _aggregate(into: dict[str, dict[str, int]], groups: list[dict[str, Any]]) -> None:
    """把一份 condition_groups 累加进 name→{count,datasets} 聚合表。"""
    for g in groups or []:
        name = str((g or {}).get("name") or "").strip()
        if not name:
            continue
        slot = into.setdefault(name, {"count": 0, "datasets": 0})
        try:
            slot["count"] += int((g or {}).get("count") or 0)
        except (TypeError, ValueError):
            pass
        slot["datasets"] += 1


def _merge(target: dict[str, dict[str, int]], other: dict[str, dict[str, int]]) -> None:
    for name, info in other.items():
        slot = target.setdefault(name, {"count": 0, "datasets": 0})
        slot["count"] += int(info.get("count") or 0)
        slot["datasets"] += int(info.get("datasets") or 0)


def _remap_vocab(
    input_vocab: dict[str, dict[str, int]], raw_rules: Any
) -> dict[str, dict[str, int]]:
    """按 Event Remap 规则把输入词表变换成输出词表（重命名 / 合并 / 丢弃；未命中原样保留）。
    与运行时 `run_event_remap` 共用 `build_remap_source_target`,故选择器显示与实际切分一致。"""
    mapping = build_remap_source_target(raw_rules)
    out: dict[str, dict[str, int]] = {}
    for name, info in input_vocab.items():
        if name in mapping:
            dest = mapping[name]
            if not dest:
                continue  # 目标空 = 丢弃
        else:
            dest = name  # 未命中 → 原样保留
        slot = out.setdefault(dest, {"count": 0, "datasets": 0})
        slot["count"] += int(info.get("count") or 0)
        slot["datasets"] = max(slot["datasets"], int(info.get("datasets") or 0))
    return out


def _selected_condition_names(raw: Any) -> list[str]:
    """从 Epoch.conditions 取已勾的 condition 名(字符串 chip 或 {name,...} 规则字典)。"""
    if not isinstance(raw, (list, tuple)):
        return []
    names: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("pattern") or "").strip()
        else:
            name = str(item).strip()
        if name:
            names.append(name)
    return names


def _option_sort_key(opt: ConditionOption) -> tuple[int, float, str]:
    # 数字名按数值排,其余按字典序(与前端 availableEventLabels 排序口径一致)
    try:
        return (0, float(opt.name), "")
    except (TypeError, ValueError):
        return (1, 0.0, opt.name)
