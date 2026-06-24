"""
Event Remap 运行时改写测试（方案 C）：合并 / 重命名 / 丢弃 / 透传。
用真实 mne 构造带 annotations 的 Raw（云端 mne 可用；本机仅 py_compile）。
"""

import numpy as np
import mne

from app.engine.preprocess.event_remap import run_event_remap


def _raw_with_events(descriptions, sfreq=100.0):
    info = mne.create_info(["Cz"], sfreq, ch_types="eeg")
    raw = mne.io.RawArray(np.zeros((1, int(sfreq * 30))), info, verbose="ERROR")
    onsets = [0.5 * (i + 1) for i in range(len(descriptions))]
    raw.set_annotations(
        mne.Annotations(onset=onsets, duration=[0.0] * len(descriptions), description=list(descriptions))
    )
    return raw


def test_merge_renames_sources_to_target():
    raw = _raw_with_events(["left", "right", "rest", "left"])
    out = run_event_remap(raw, {"rules": [{"sources": ["left", "right"], "target": "move"}]})
    assert sorted(out.annotations.description) == sorted(["move", "move", "rest", "move"])


def test_drop_removes_events():
    raw = _raw_with_events(["left", "rest", "left"])
    out = run_event_remap(raw, {"rules": [{"sources": ["rest"], "target": ""}]})
    descs = list(out.annotations.description)
    assert "rest" not in descs
    assert len(descs) == 2


def test_unmatched_events_pass_through():
    raw = _raw_with_events(["left", "rest"])
    out = run_event_remap(raw, {"rules": [{"sources": ["left"], "target": "move"}]})
    assert sorted(out.annotations.description) == sorted(["move", "rest"])


def test_no_rules_is_passthrough():
    raw = _raw_with_events(["a", "b"])
    out = run_event_remap(raw, {"rules": []})
    assert sorted(out.annotations.description) == ["a", "b"]


def test_template_group_collapses_indexed_events():
    # 烧进序号的事件名 → 按模板分组「trial/*/fist」一键改名（econ BDF 那类数据）
    descs = [f"trial/{i}/fist" for i in range(70)] + [f"trial/{i}/rest" for i in range(70)]
    raw = _raw_with_events(descs, sfreq=1000.0)
    out = run_event_remap(raw, {"rules": [{"sources": ["trial/*/fist"], "target": "fist"}]})
    out_descs = list(out.annotations.description)
    assert out_descs.count("fist") == 70
    # rest 那组未被规则命中 → 原样保留（仍带序号）
    assert sum(1 for d in out_descs if d.endswith("/rest")) == 70
