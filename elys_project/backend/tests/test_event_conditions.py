"""
事件重映射共用纯逻辑测试（方案 C）：源→目标映射表 + 注释分组分类。
分类口径必须与 propose_condition_groups 一致——这是「选择器显示 / 运行时改写」一致的保证。
"""

from app.engine.analysis.event_conditions import (
    build_remap_source_target,
    classify_descriptions,
    propose_condition_groups,
)


def test_build_remap_source_target_first_rule_wins_and_drop():
    rules = [
        {"sources": ["left", "right"], "target": "move"},
        {"sources": ["rest"], "target": ""},  # 目标空 = 丢弃
        {"sources": ["left"], "target": "OTHER"},  # 重复源，首条优先
    ]
    assert build_remap_source_target(rules) == {"left": "move", "right": "move", "rest": ""}


def test_build_remap_source_target_ignores_malformed():
    assert build_remap_source_target(None) == {}
    assert build_remap_source_target([{"target": "x"}, "junk", {"sources": []}]) == {}


def test_classify_descriptions_exact_when_clean():
    assert classify_descriptions(["go", "nogo", "go"]) == ["go", "nogo", "go"]


def test_classify_descriptions_template_when_instance_laden():
    # 大量「只差数字」的标识符 → 抹数字模板归组，与 propose_condition_groups 同口径
    descs = [f"trial/{i}/fist" for i in range(70)] + [f"trial/{i}/rest" for i in range(70)]
    names = classify_descriptions(descs)
    assert set(names) == {"trial/*/fist", "trial/*/rest"}
    # 与 propose_condition_groups 的分组名严格一致（一致性保证）
    assert set(names) == {g["name"] for g in propose_condition_groups(descs)}
