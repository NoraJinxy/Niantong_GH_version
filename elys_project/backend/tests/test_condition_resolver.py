"""
沿链路解析「节点输入端可用 condition」的单元测试（方案 B 核心）。
覆盖：透传链继承 LoadData、Epoch 只下传实际切出的 condition、多分支不串台。
LoadData 解析被 monkeypatch 掉（不碰 DB）。
"""

import app.pipeline.condition_resolver as cr


class _Info:
    def __init__(self, groups):
        self.condition_groups = groups


class _Resolved:
    def __init__(self, infos):
        self.data_infos = infos


def _fake_resolve(groups_by_node):
    """返回一个按 node_id 给 condition_groups 的假 resolve_load_data_selection。"""

    def _inner(*, db, study, params, node_id):
        return _Resolved([_Info(groups_by_node.get(node_id, []))])

    return _inner


def test_epoch_input_inherits_loaddata_through_passthrough(monkeypatch):
    """LoadData → Filter(透传) → Epoch：Epoch 候选 = LoadData 的 condition_groups。"""
    monkeypatch.setattr(
        cr,
        "resolve_load_data_selection",
        _fake_resolve({"ld1": [{"name": "go", "count": 10}, {"name": "nogo", "count": 8}]}),
    )
    graph = {
        "nodes": [
            {"id": "ld1", "type": "eeg/data/load", "params": {}},
            {"id": "flt", "type": "eeg/filter/apply", "params": {}},
            {"id": "ep1", "type": "eeg/epoch/segment", "params": {}},
        ],
        "links": [
            {"from": {"node": "ld1"}, "to": {"node": "flt"}},
            {"from": {"node": "flt"}, "to": {"node": "ep1"}},
        ],
    }
    res = cr.resolve_node_conditions(db=None, study=None, graph=graph, node_id="ep1")
    assert [c.name for c in res.conditions] == ["go", "nogo"]
    counts = {c.name: c.count for c in res.conditions}
    assert counts == {"go": 10, "nogo": 8}


def test_erp_inherits_epoch_realized_conditions(monkeypatch):
    """ERP 候选 = 上游 Epoch 实际切出的 condition（已勾 ∩ 输入），ghost 名不下传。"""
    monkeypatch.setattr(
        cr,
        "resolve_load_data_selection",
        _fake_resolve({"ld1": [{"name": "go", "count": 10}, {"name": "nogo", "count": 8}]}),
    )
    graph = {
        "nodes": [
            {"id": "ld1", "type": "eeg/data/load", "params": {}},
            # 勾了 go + 一个数据里不存在的 ghost → ghost 不应出现在 ERP 候选
            {"id": "ep1", "type": "eeg/epoch/segment", "params": {"conditions": ["go", "ghost"]}},
            {"id": "erp", "type": "eeg/analysis/erp", "params": {}},
        ],
        "links": [
            {"from": {"node": "ld1"}, "to": {"node": "ep1"}},
            {"from": {"node": "ep1"}, "to": {"node": "erp"}},
        ],
    }
    res = cr.resolve_node_conditions(db=None, study=None, graph=graph, node_id="erp")
    assert [c.name for c in res.conditions] == ["go"]
    assert res.conditions[0].count == 10


def test_epoch_after_epoch_uses_annotation_vocab_not_parent_epoch_labels(monkeypatch):
    """Epoch → Epoch：第二个 Epoch 的候选看父 Epochs 内 annotations，而不是第一个 Epoch 的 event_id。"""
    monkeypatch.setattr(
        cr,
        "resolve_load_data_selection",
        _fake_resolve(
            {
                "ld1": [
                    {"name": "block", "count": 2},
                    {"name": "Stimulus/S 3", "count": 20},
                    {"name": "Stimulus/S 4", "count": 20},
                ]
            }
        ),
    )
    graph = {
        "nodes": [
            {"id": "ld1", "type": "eeg/data/load", "params": {}},
            {"id": "block_ep", "type": "eeg/epoch/segment", "params": {"conditions": ["block"]}},
            {"id": "stim_ep", "type": "eeg/epoch/segment", "params": {}},
            {"id": "erp", "type": "eeg/analysis/erp", "params": {}},
        ],
        "links": [
            {"from": {"node": "ld1"}, "to": {"node": "block_ep"}},
            {"from": {"node": "block_ep"}, "to": {"node": "stim_ep"}},
            {"from": {"node": "block_ep"}, "to": {"node": "erp"}},
        ],
    }
    nested = cr.resolve_node_conditions(db=None, study=None, graph=graph, node_id="stim_ep")
    assert {c.name for c in nested.conditions} == {"block", "Stimulus/S 3", "Stimulus/S 4"}

    erp = cr.resolve_node_conditions(db=None, study=None, graph=graph, node_id="erp")
    assert [c.name for c in erp.conditions] == ["block"]


def test_analysis_after_plain_nested_epoch_keeps_leaf_conditions(monkeypatch):
    """Plain Epoch -> Epoch keeps leaf child event labels for downstream analysis."""
    monkeypatch.setattr(
        cr,
        "resolve_load_data_selection",
        _fake_resolve(
            {
                "ld1": [
                    {"name": "block/A", "count": 2},
                    {"name": "block/B", "count": 2},
                    {"name": "sound/low", "count": 20},
                    {"name": "sound/high", "count": 20},
                ]
            }
        ),
    )
    graph = {
        "nodes": [
            {"id": "ld1", "type": "eeg/data/load", "params": {}},
            {"id": "block_ep", "type": "eeg/epoch/segment", "params": {"conditions": ["block/A", "block/B"]}},
            {
                "id": "sound_ep",
                "type": "eeg/epoch/segment",
                "params": {"conditions": ["sound/low", "sound/high"], "split_by": "condition"},
            },
            {"id": "erp", "type": "eeg/analysis/erp", "params": {}},
        ],
        "links": [
            {"from": {"node": "ld1"}, "to": {"node": "block_ep"}},
            {"from": {"node": "block_ep"}, "to": {"node": "sound_ep"}},
            {"from": {"node": "sound_ep"}, "to": {"node": "erp"}},
        ],
    }
    res = cr.resolve_node_conditions(db=None, study=None, graph=graph, node_id="erp")
    assert {c.name for c in res.conditions} == {"sound/low", "sound/high"}


def test_analysis_after_epoch_merge_sees_condition_paths(monkeypatch):
    """Epoch Merge -> Epoch expands leaf child selections into parent / child condition paths."""
    monkeypatch.setattr(
        cr,
        "resolve_load_data_selection",
        _fake_resolve(
            {
                "ld1": [
                    {"name": "block/A", "count": 2},
                    {"name": "block/B", "count": 2},
                    {"name": "sound/low", "count": 20},
                    {"name": "sound/high", "count": 20},
                ]
            }
        ),
    )
    graph = {
        "nodes": [
            {"id": "ld1", "type": "eeg/data/load", "params": {}},
            {"id": "block_ep", "type": "eeg/epoch/segment", "params": {"conditions": ["block/A", "block/B"]}},
            {"id": "merge", "type": "eeg/epoch/merge", "params": {"merge_scope": "source_recording"}},
            {
                "id": "sound_ep",
                "type": "eeg/epoch/segment",
                "params": {"conditions": ["sound/low", "sound/high"], "split_by": "condition"},
            },
            {"id": "erp", "type": "eeg/analysis/erp", "params": {}},
        ],
        "links": [
            {"from": {"node": "ld1"}, "to": {"node": "block_ep"}},
            {"from": {"node": "block_ep"}, "to": {"node": "merge"}},
            {"from": {"node": "merge"}, "to": {"node": "sound_ep"}},
            {"from": {"node": "sound_ep"}, "to": {"node": "erp"}},
        ],
    }
    res = cr.resolve_node_conditions(db=None, study=None, graph=graph, node_id="erp")
    assert {c.name for c in res.conditions} == {
        "block/A / sound/low",
        "block/A / sound/high",
        "block/B / sound/low",
        "block/B / sound/high",
    }


def test_epoch_merge_preserves_parent_annotation_vocab(monkeypatch):
    """LoadData → Epoch(block) → Epoch Merge → Epoch(sound)：Merge 不吞掉子事件候选。"""
    monkeypatch.setattr(
        cr,
        "resolve_load_data_selection",
        _fake_resolve(
            {
                "ld1": [
                    {"name": "block/A", "count": 2},
                    {"name": "block/B", "count": 2},
                    {"name": "sound/low", "count": 20},
                    {"name": "sound/high", "count": 20},
                ]
            }
        ),
    )
    graph = {
        "nodes": [
            {"id": "ld1", "type": "eeg/data/load", "params": {}},
            {"id": "block_ep", "type": "eeg/epoch/segment", "params": {"conditions": ["block/A", "block/B"]}},
            {"id": "merge", "type": "eeg/epoch/merge", "params": {"merge_scope": "source_recording"}},
            {"id": "sound_ep", "type": "eeg/epoch/segment", "params": {}},
            {"id": "erp", "type": "eeg/analysis/erp", "params": {}},
        ],
        "links": [
            {"from": {"node": "ld1"}, "to": {"node": "block_ep"}},
            {"from": {"node": "block_ep"}, "to": {"node": "merge"}},
            {"from": {"node": "merge"}, "to": {"node": "sound_ep"}},
            {"from": {"node": "merge"}, "to": {"node": "erp"}},
        ],
    }
    nested = cr.resolve_node_conditions(db=None, study=None, graph=graph, node_id="sound_ep")
    assert {c.name for c in nested.conditions} == {"block/A", "block/B", "sound/low", "sound/high"}

    erp = cr.resolve_node_conditions(db=None, study=None, graph=graph, node_id="erp")
    assert {c.name for c in erp.conditions} == {"block/A", "block/B"}


def test_multi_branch_no_crosstalk(monkeypatch):
    """两条独立分支：各 Epoch 只看到自己上游 LoadData 的事件，不串台。"""
    monkeypatch.setattr(
        cr,
        "resolve_load_data_selection",
        _fake_resolve({"ldA": [{"name": "A1", "count": 5}], "ldB": [{"name": "B1", "count": 7}]}),
    )
    graph = {
        "nodes": [
            {"id": "ldA", "type": "eeg/data/load", "params": {}},
            {"id": "ldB", "type": "eeg/data/load", "params": {}},
            {"id": "epA", "type": "eeg/epoch/segment", "params": {}},
            {"id": "epB", "type": "eeg/epoch/segment", "params": {}},
        ],
        "links": [
            {"from": {"node": "ldA"}, "to": {"node": "epA"}},
            {"from": {"node": "ldB"}, "to": {"node": "epB"}},
        ],
    }
    res_a = cr.resolve_node_conditions(db=None, study=None, graph=graph, node_id="epA")
    res_b = cr.resolve_node_conditions(db=None, study=None, graph=graph, node_id="epB")
    assert [c.name for c in res_a.conditions] == ["A1"]
    assert [c.name for c in res_b.conditions] == ["B1"]


def test_two_loaddata_into_one_epoch_union(monkeypatch):
    """两个 LoadData 汇入同一 Epoch：候选 = 并集，重名计数累加、datasets 累加。"""
    monkeypatch.setattr(
        cr,
        "resolve_load_data_selection",
        _fake_resolve(
            {
                "ldA": [{"name": "go", "count": 5}, {"name": "x", "count": 1}],
                "ldB": [{"name": "go", "count": 3}],
            }
        ),
    )
    graph = {
        "nodes": [
            {"id": "ldA", "type": "eeg/data/load", "params": {}},
            {"id": "ldB", "type": "eeg/data/load", "params": {}},
            {"id": "ep1", "type": "eeg/epoch/segment", "params": {}},
        ],
        "links": [
            {"from": {"node": "ldA"}, "to": {"node": "ep1"}},
            {"from": {"node": "ldB"}, "to": {"node": "ep1"}},
        ],
    }
    res = cr.resolve_node_conditions(db=None, study=None, graph=graph, node_id="ep1")
    by_name = {c.name: c for c in res.conditions}
    assert set(by_name) == {"go", "x"}
    assert by_name["go"].count == 8 and by_name["go"].datasets == 2
    assert by_name["x"].count == 1 and by_name["x"].datasets == 1


def test_event_remap_transforms_downstream_vocab(monkeypatch):
    """LoadData → EventRemap(merge left+right→move, drop rest) → Epoch：方案 C 变换链路。
    Epoch 候选 = remap 后词表；remap 节点自己的源候选 = 上游原始词表。"""
    monkeypatch.setattr(
        cr,
        "resolve_load_data_selection",
        _fake_resolve(
            {"ld1": [{"name": "left", "count": 5}, {"name": "right", "count": 4}, {"name": "rest", "count": 9}]}
        ),
    )
    graph = {
        "nodes": [
            {"id": "ld1", "type": "eeg/data/load", "params": {}},
            {
                "id": "rm1",
                "type": "eeg/preproc/event_remap",
                "params": {"rules": [{"sources": ["left", "right"], "target": "move"}, {"sources": ["rest"], "target": ""}]},
            },
            {"id": "ep1", "type": "eeg/epoch/segment", "params": {}},
        ],
        "links": [
            {"from": {"node": "ld1"}, "to": {"node": "rm1"}},
            {"from": {"node": "rm1"}, "to": {"node": "ep1"}},
        ],
    }
    res = cr.resolve_node_conditions(db=None, study=None, graph=graph, node_id="ep1")
    by = {c.name: c for c in res.conditions}
    assert set(by) == {"move"}  # left+right→move, rest 被丢弃
    assert by["move"].count == 9  # 5 + 4
    # remap 节点自身的源候选 = 上游原始词表（供前端规则编辑器选源）
    res_rm = cr.resolve_node_conditions(db=None, study=None, graph=graph, node_id="rm1")
    assert {c.name for c in res_rm.conditions} == {"left", "right", "rest"}


def test_loaddata_forced_explicit_for_task61(monkeypatch):
    """LoadData 解析强制 explicit + dataset_ids（task#61）：即使节点残留 filter 模式也不回退，避免候选泄漏。"""
    captured: dict = {}

    def _capture(*, db, study, params, node_id):
        captured[node_id] = params
        return _Resolved([_Info([{"name": "go", "count": 1}])])

    monkeypatch.setattr(cr, "resolve_load_data_selection", _capture)
    graph = {
        "nodes": [
            {"id": "ld1", "type": "eeg/data/load", "params": {"selection_mode": "filter", "dataset_ids": ["d1"]}},
            {"id": "ep1", "type": "eeg/epoch/segment", "params": {}},
        ],
        "links": [{"from": {"node": "ld1"}, "to": {"node": "ep1"}}],
    }
    cr.resolve_node_conditions(db=None, study=None, graph=graph, node_id="ep1")
    assert captured["ld1"]["selection_mode"] == "explicit"
    assert captured["ld1"]["dataset_ids"] == ["d1"]


def test_unconnected_node_has_no_candidates(monkeypatch):
    """未连上游的 Epoch → 无候选（符合「只按上游导出的数据来」）。"""
    monkeypatch.setattr(cr, "resolve_load_data_selection", _fake_resolve({}))
    graph = {"nodes": [{"id": "ep1", "type": "eeg/epoch/segment", "params": {}}], "links": []}
    res = cr.resolve_node_conditions(db=None, study=None, graph=graph, node_id="ep1")
    assert res.conditions == []
