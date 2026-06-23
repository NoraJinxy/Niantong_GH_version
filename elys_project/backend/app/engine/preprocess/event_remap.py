"""
Purpose: 事件重映射执行器——按规则改写 Raw annotations 的 description（重命名 / 合并 / 丢弃），
得到干净的 condition 供下游 Epoch 切分。不改原始数据，返回改写后的 Raw 副本。
源名按「上游识别出的事件分组名」匹配（与选择器 / 运行时同一套 propose_condition_groups 分桶），
故「界面里勾的」与「运行时改的」是同一组事件。
Related: app/engine/analysis/event_conditions.py, app/pipeline/condition_resolver.py.
"""

from __future__ import annotations

from typing import Any

from app.engine.analysis.event_conditions import (
    build_remap_source_target,
    classify_descriptions,
)


def run_event_remap(raw: Any, params: dict[str, Any]) -> Any:
    """按 params["rules"] 改写 Raw annotations。

    rules: [{"sources": [上游事件分组名...], "target": "新名字"}]。多个 source = 合并到一个 target；
    target 留空 = 丢弃这些事件。未被任何规则命中的事件**原样保留**（不动你没指定的）。
    """
    mne = _mne()

    annotations = getattr(raw, "annotations", None)
    mapping = build_remap_source_target(params.get("rules"))
    if not mapping or annotations is None or len(annotations) == 0:
        return raw.copy()  # 没规则 / 没事件 = 透传（拷贝以不改输入）

    descriptions = [str(d) for d in annotations.description]
    group_names = classify_descriptions(descriptions)

    new_onset: list[float] = []
    new_duration: list[float] = []
    new_description: list[str] = []
    for onset, duration, desc, gname in zip(
        annotations.onset, annotations.duration, descriptions, group_names
    ):
        if desc.upper().startswith("BAD_"):
            new_description.append(desc)  # 坏段注解 → 不参与重映射，原样保留
        elif gname in mapping:
            target = mapping[gname]
            if not target:
                continue  # 目标留空 = 丢弃
            new_description.append(target)
        else:
            new_description.append(desc)  # 未命中 → 原样保留
        new_onset.append(float(onset))
        new_duration.append(float(duration))

    out = raw.copy()
    out.set_annotations(
        mne.Annotations(
            onset=new_onset,
            duration=new_duration,
            description=new_description,
            orig_time=annotations.orig_time,
        )
    )
    return out


def _mne():
    try:
        import mne
    except ImportError as exc:
        raise RuntimeError("MNE is required for event remap.") from exc
    return mne
