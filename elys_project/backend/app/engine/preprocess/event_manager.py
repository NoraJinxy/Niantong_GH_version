"""
Purpose: 事件管理器执行器（交互节点 eeg/preproc/event_manager）——人工对 Raw 的事件标记
         做全局梳理：新增 / 删除 / 改名 / 合并 / 改时 / 改时长。raw -> (raw, detail)。
Related: app/pipeline/dispatcher.py (_execute_event_manager / _event_manager_*),
         app/pipeline/nodes/eeg_preproc_event_manager.json,
         app/pipeline/condition_resolver.py（同套 group_operations 变换词表，选择器与切分一致）,
         app/engine/preprocess/event_remap.py（声明式批量改名的孪生；本节点是其交互版）。

两种作用模式（由 dispatcher 按输入数据集数量决定，见 _execute_event_manager）：
  - literal（单数据集）：params['events'] = 编辑器算出的「最终非 BAD 事件清单」，直接落盘——
    用户拖动/新增/删除的每一处都已反映在清单里，最精确。
  - rules（多数据集 / 声明式）：params['group_operations'] = 分组级规则（改名/合并/丢弃/平移），
    按事件分组名套用到每个数据集——可复现、可批量，等价于 Event Remap 的能力内化进本节点。

设计原则（对标 MNE Annotations / Letswave 事件表 / EEGLAB pop_editeventvals）：
  - 统一事件模型：一条记录 = (description 标签, onset 起始秒, duration 时长秒)；点事件 = 时长 0。
    底层只动 raw.annotations，与 artifact_mark 同存储。
  - BAD_ 注解归伪迹标记管，本节点全程**原样保留**、不增不删（事件梳理与数据质量正交）。
  - 非破坏、可重跑：始终在 raw.copy() 上 set_annotations，原始数据不改。
"""

from __future__ import annotations

import json
from typing import Any

from app.engine.analysis.event_conditions import classify_descriptions

# 与 artifact_mark.BAD_ANNOTATION_PREFIX 对齐：本节点不碰任何以此开头的注解。
BAD_ANNOTATION_PREFIX = "BAD_"


def _mne():
    try:
        import mne
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("MNE is required for event-manager pipeline nodes.") from exc
    return mne


def _coerce_list(value: Any) -> list[Any]:
    """node property 既可能是 JSON 字符串（前端存）也可能是已解析的 list（decision 写回）。"""
    if value in (None, ""):
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (ValueError, TypeError):
            return []
        return parsed if isinstance(parsed, list) else []
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def parse_event_list(value: Any) -> list[dict[str, Any]]:
    """归一「最终事件清单」为 [{onset, duration, description}]，按 onset 排序。

    丢弃：非 dict / 无法转 float 的 onset / 负 onset / 负时长 / 空标签 / BAD_ 开头的标签
    （后者归伪迹标记管，不让用户从事件管理器写进来造成与保留的 BAD_ 注解重复）。
    """
    out: list[dict[str, Any]] = []
    for item in _coerce_list(value):
        if not isinstance(item, dict):
            continue
        try:
            onset = float(item.get("onset"))
        except (TypeError, ValueError):
            continue
        try:
            duration = float(item.get("duration") or 0.0)
        except (TypeError, ValueError):
            duration = 0.0
        if onset < 0 or duration < 0:
            continue
        desc = str(item.get("description") or "").strip()
        if not desc or desc.startswith(BAD_ANNOTATION_PREFIX):
            continue
        out.append({"onset": onset, "duration": duration, "description": desc})
    out.sort(key=lambda e: e["onset"])
    return out


def apply_group_operations(
    managed: list[dict[str, Any]], group_ops: Any
) -> list[dict[str, Any]]:
    """按分组级规则把「非 BAD 事件清单」变换成新清单（改名/合并/丢弃/平移；未命中原样保留）。

    group_ops: [{op, sources:[分组名...], target?, delta_s?}]
      - op=rename/merge/relabel：sources 这些分组 → target（多 source = 合并）。
      - op=delete：sources 这些分组丢弃（等价 target 留空）。
      - op=shift ：sources 这些分组的 onset 平移 delta_s 秒（+ 后移 / - 前移）。
    分组名口径与 classify_descriptions / propose_condition_groups 一致——故「界面里勾的分组」
    与「运行时改的事件」是同一套桶。改名/合并「首条规则优先」，与 build_remap_source_target 同。
    """
    rename: dict[str, str] = {}   # 分组名 → 目标名（'' = 丢弃）
    shift: dict[str, float] = {}  # 分组名 → 累计平移秒
    for op in _coerce_list(group_ops):
        if not isinstance(op, dict):
            continue
        kind = str(op.get("op") or "").strip().lower()
        sources = op.get("sources")
        if not isinstance(sources, (list, tuple)):
            continue
        if not kind:
            # 无 op 字段 = 检查器 event_remap_rules 编辑器产出的 {sources,target} 形态 → 视作改名/丢弃；
            # 仅带 delta_s 而无 target 的视作平移。group_operations 即 event_remap_rules 的超集。
            kind = "shift" if ("delta_s" in op and "target" not in op) else "rename"
        if kind in ("rename", "merge", "relabel", "delete"):
            target = "" if kind == "delete" else str(op.get("target") or "").strip()
            for s in sources:
                nm = str(s).strip()
                if nm and nm not in rename:  # 首条规则优先
                    rename[nm] = target
        elif kind == "shift":
            try:
                delta = float(op.get("delta_s"))
            except (TypeError, ValueError):
                delta = 0.0
            for s in sources:
                nm = str(s).strip()
                if nm:
                    shift[nm] = shift.get(nm, 0.0) + delta

    if not rename and not shift:
        return [dict(e) for e in managed]

    group_names = classify_descriptions([e["description"] for e in managed])
    out: list[dict[str, Any]] = []
    for event, gname in zip(managed, group_names):
        desc = event["description"]
        onset = event["onset"]
        if gname in rename:
            target = rename[gname]
            if not target:
                continue  # 丢弃
            desc = target
        if gname in shift:
            onset = max(0.0, onset + shift[gname])
        out.append({"onset": onset, "duration": event["duration"], "description": desc})
    out.sort(key=lambda e: e["onset"])
    return out


def _split_annotations(annotations: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """把现有注解拆成（managed=非 BAD 事件, preserved=BAD_ 注解）。BAD_ 原样保留不动。"""
    managed: list[dict[str, Any]] = []
    preserved: list[dict[str, Any]] = []
    if annotations is None or len(annotations) == 0:
        return managed, preserved
    for onset, duration, desc in zip(
        annotations.onset, annotations.duration, annotations.description
    ):
        rec = {"onset": float(onset), "duration": float(duration), "description": str(desc)}
        if rec["description"].startswith(BAD_ANNOTATION_PREFIX):
            preserved.append(rec)
        else:
            managed.append(rec)
    return managed, preserved


def run_event_manager(raw: Any, params: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """应用人工事件梳理。raw→(raw, {"event_manager": 明细})。

    params（由 dispatcher 把 decision 合进来）：
      events           : 最终非 BAD 事件清单 [{onset,duration,description}]（literal 模式，单数据集）。
      group_operations : 分组级规则（rules 模式，多数据集 / 声明式持久化）。
      operations       : 人类可读的操作摘要（仅作溯源透传，喂 Methods 自动生成）。
    无任何编辑信号 → 透传（拷贝以不改输入）。
    """
    mne = _mne()
    annotations = getattr(raw, "annotations", None)
    orig_time = getattr(annotations, "orig_time", None) if annotations is not None else None
    managed, preserved = _split_annotations(annotations)

    events = params.get("events")
    group_ops = params.get("group_operations")

    if isinstance(events, list) and len(events) > 0:
        new_managed = parse_event_list(events)
        mode = "literal"
    elif _coerce_list(group_ops):
        new_managed = apply_group_operations(managed, group_ops)
        mode = "rules"
    else:
        return raw.copy()  # 没有编辑信号 = 透传

    out = raw.copy()
    out.set_annotations(
        mne.Annotations(
            onset=[e["onset"] for e in new_managed] + [b["onset"] for b in preserved],
            duration=[e["duration"] for e in new_managed] + [b["duration"] for b in preserved],
            description=[e["description"] for e in new_managed] + [b["description"] for b in preserved],
            orig_time=orig_time,
        )
    )

    label_counts: dict[str, int] = {}
    for e in new_managed:
        label_counts[e["description"]] = label_counts.get(e["description"], 0) + 1

    detail = {
        "mode": mode,
        "original_count": len(managed),
        "final_count": len(new_managed),
        "n_added": max(0, len(new_managed) - len(managed)),
        "n_removed": max(0, len(managed) - len(new_managed)),
        "n_labels": len(label_counts),
        "labels": sorted(label_counts),
        "label_counts": label_counts,
        "n_bad_preserved": len(preserved),
        "operations": params.get("operations") or [],
    }
    return out, {"event_manager": detail}
