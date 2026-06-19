"""
Purpose: 把"原始事件注释(自由文本、常带实例序号)"归一化成"有界的分析用 condition"。
供 epoching(切分时按 condition 分组,而非逐字符串精确匹配)与导入 QC(事件可用性体检)共用。
设计依据见 日志/7_导入规范与事件归一化260612/。
Related: app/engine/analysis/epoching.py, app/pipeline/load_data.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

# 与 pipeline/load_data.py 的 EVENT_LABEL_MAX_PER_DATASET 对齐:
# 不同事件取值超过此数,基本可断定"标识符里烧进了实例序号",未归一化。
DEFAULT_MAX_CONDITIONS = 64

_DIGITS = re.compile(r"\d+")


@dataclass(frozen=True)
class ConditionRule:
    """一条"原始注释 → 干净 condition"的归并规则。"""

    name: str
    pattern: str
    mode: str = "contains"  # exact | contains | regex

    def matches(self, description: str) -> bool:
        if self.mode == "exact":
            return description == self.pattern
        if self.mode == "template":
            return _DIGITS.sub("#", description) == _DIGITS.sub("#", self.pattern)
        if self.mode == "regex":
            try:
                return re.search(self.pattern, description) is not None
            except re.error:
                return False
        return self.pattern in description  # contains(默认)


def match_conditions(
    onsets: Sequence[float],
    descriptions: Sequence[str],
    sfreq: float,
    rules: Sequence[ConditionRule],
) -> tuple[list[list[int]], dict[str, int], dict[str, Any]]:
    """按规则把注释归并成 condition,产出 mne events 所需结构。

    返回 (events, event_id_map, report):
      events       : [[sample, 0, code], ...](未排序;调用方排序后转 np.array)
      event_id_map : {condition_name: code};仅含至少命中 1 条的 condition
      report       : {"counts": {name: n}, "unmatched": n, "ambiguous": n, "total": n}
    一条注释命中多条规则时,归入"第一条命中"的规则(顺序即优先级),并计入 ambiguous。
    """
    name_order: list[str] = []
    for r in rules:
        if r.name not in name_order:
            name_order.append(r.name)
    code_of = {name: i + 1 for i, name in enumerate(name_order)}

    events: list[list[int]] = []
    counts: dict[str, int] = {name: 0 for name in name_order}
    unmatched = 0
    ambiguous = 0
    total = 0

    for onset, desc in zip(onsets, descriptions):
        text = str(desc)
        total += 1
        hit_name: str | None = None
        n_hits = 0
        for r in rules:
            if r.matches(text):
                n_hits += 1
                if hit_name is None:
                    hit_name = r.name
        if hit_name is None:
            unmatched += 1
            continue
        if n_hits > 1:
            ambiguous += 1
        sample = int(round(float(onset) * float(sfreq)))
        events.append([sample, 0, code_of[hit_name]])
        counts[hit_name] += 1

    event_id_map = {name: code_of[name] for name in name_order if counts[name] > 0}
    report = {"counts": counts, "unmatched": unmatched, "ambiguous": ambiguous, "total": total}
    return events, event_id_map, report


def summarize_event_vocabulary(
    descriptions: Sequence[str],
    *,
    n_trials_hint: int | None = None,
    max_conditions: int = DEFAULT_MAX_CONDITIONS,
) -> dict[str, Any]:
    """事件词表体检(导入 QC 的"那把尺子"):判定原始事件是否"未归一化、下游切不动"。

    判据:不同取值数超过 max_conditions,且(抹掉数字后模板数远小于唯一数 ——
    说明唯一性几乎全由内嵌序号制造;或唯一数 ≈ 事件总数)→ 疑似实例数据烧进标识符。
    """
    texts = [str(d) for d in descriptions]
    n_total = len(texts)
    uniques = set(texts)
    n_unique = len(uniques)
    n_templates = len({_DIGITS.sub("#", t) for t in uniques})

    over_cap = n_unique > max_conditions
    digit_driven = n_unique >= max(8, 3 * n_templates)  # 唯一性主要来自数字(序号)
    near_total = n_total > 0 and n_unique >= 0.8 * n_total
    looks_instance_laden = bool(over_cap and (digit_driven or near_total))

    if looks_instance_laden:
        verdict = "instance_laden"
        hint = (
            f"事件有 {n_unique} 种取值、抹掉数字后仅 {n_templates} 种模板:"
            "标识符里疑似烧进了序号,无法直接按 condition 切分,需先归一化(见导入原则)。"
        )
    elif over_cap:
        verdict = "too_many"
        hint = f"事件取值 {n_unique} 种,超过阈值 {max_conditions},建议归并成更少的 condition。"
    else:
        verdict = "ok"
        hint = f"事件取值 {n_unique} 种,处于可直接切分的健康范围。"

    return {
        "n_total": n_total,
        "n_unique": n_unique,
        "n_templates": n_templates,
        "looks_instance_laden": looks_instance_laden,
        "verdict": verdict,
        "hint": hint,
    }


def propose_condition_groups(
    descriptions: Sequence[str],
    *,
    max_conditions: int = DEFAULT_MAX_CONDITIONS,
) -> list[dict[str, Any]]:
    """把原始事件自动收成「可勾选的分组」:忠实原始 label,只把"仅差序号的重复"合并。

    返回 [{name,pattern,mode,count,sample}]。
    - 事件带序号/多到爆(instance_laden):把"只差数字"的合并成一组,mode="template";
      name **忠实显示原模板**、被合并的数字位写成 `*`(如 `trial/cue_sent/index/*/clench_fist`)。
    - 事件本就干净:每个原值一组,mode="exact",name=原值。
    前缀不同的(mi/csp/rest 的 window)天然就是不同组,不改名、不撞名、不堆 `-2/-3`。
    前端展示与运行时(epoching)调同一函数,分组一致。
    """
    texts = [str(d) for d in descriptions]
    use_template = summarize_event_vocabulary(texts, max_conditions=max_conditions)["looks_instance_laden"]

    buckets: dict[str, dict[str, Any]] = {}
    for t in texts:
        key = _DIGITS.sub("#", t) if use_template else t
        bucket = buckets.get(key)
        if bucket is None:
            buckets[key] = {"count": 1, "sample": t}
        else:
            bucket["count"] += 1

    groups: list[dict[str, Any]] = []
    for key, bucket in buckets.items():
        if use_template:
            name, pattern, mode = key.replace("#", "*"), key, "template"
        else:
            name, pattern, mode = key, key, "exact"
        groups.append(
            {"name": name, "pattern": pattern, "mode": mode, "count": bucket["count"], "sample": bucket["sample"]}
        )
    groups.sort(key=lambda g: g["name"])
    return groups


def rules_for_selection(selected: Any, descriptions: Sequence[str]) -> list[ConditionRule]:
    """把节点存的 conditions 还原成 ConditionRule。接受:
    - 勾选的分组名列表(前端 chips,字符串)→ 按当前数据重算分组、按名取回 pattern/mode;
    - [{"name","pattern","mode"?}, ...] 规则列表 → 直接用。
    """
    if not selected:
        return []
    items = list(selected) if isinstance(selected, (list, tuple)) else [selected]
    rules: list[ConditionRule] = []
    pending_names: list[str] = []
    for item in items:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("pattern") or "").strip()
            pattern = str(item.get("pattern") or item.get("name") or "").strip()
            mode = str(item.get("mode") or "exact").strip().lower()
            if mode not in ("exact", "contains", "regex", "template"):
                mode = "exact"
            if name and pattern:
                rules.append(ConditionRule(name=name, pattern=pattern, mode=mode))
        else:
            text = str(item).strip()
            if text:
                pending_names.append(text)
    if pending_names:
        groups = {g["name"]: g for g in propose_condition_groups(descriptions)}
        for nm in pending_names:
            g = groups.get(nm)
            if g is not None:
                rules.append(ConditionRule(name=g["name"], pattern=g["pattern"], mode=g["mode"]))
    return rules
