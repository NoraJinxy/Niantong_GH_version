"""
Purpose: 单元测试 app/pipeline/hash.py 的 node_hash 算法稳定性。

核心断言：
- spec metadata 字段（schema_version / save / ui / cache / backend 装饰字段）变化 → node_hash 不变
- 算法相关字段（node_type / backend.module / backend.function）变化 → node_hash 改变
- params / input 变化 → node_hash 改变

这能保证 spec 升级（schema_version 升、加 save 子对象、改 ui.color 等）
不会破坏 cache，让相同 input + 相同算法的节点保持 cache hit。

Related: app/pipeline/hash.py
"""

from __future__ import annotations

from pathlib import Path
import sys


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.pipeline.hash import input_hash, node_hash  # noqa: E402


# === 基线 spec ===

def base_spec():
    return {
        "schema_version": "1.0",
        "type": "eeg/filter/apply",
        "title": "Filter",
        "category": "preprocess",
        "phase": "phase1",
        "backend": {
            "module": "app.engine.preprocess.filters",
            "function": "run_filter",
            "save_descriptor": "filt",
            "output_kind": "fif",
            "supports_batch": True,
            "interactive": False,
        },
        "cache": {"enabled": True, "strategy": "content_hash"},
    }


PARAMS_DIGEST = "params-abc"
INPUT_DIGEST = "input-xyz"


def hash_of(spec):
    return node_hash(
        node_type=spec["type"],
        params_digest=PARAMS_DIGEST,
        input_digest=INPUT_DIGEST,
        node_spec=spec,
    )


# === Group 1: cosmetic / metadata 字段变化 → hash 不变 ===

def test_schema_version_change_does_not_break_hash():
    """spec.schema_version 从 1.0 升到 2.0 → hash 应该一致。"""
    spec_v1 = base_spec()
    spec_v2 = base_spec()
    spec_v2["schema_version"] = "2.0"
    assert hash_of(spec_v1) == hash_of(spec_v2)


def test_save_subobject_does_not_affect_hash():
    """P0 给 spec 加 save 子对象 → 不该让 cache 失效。"""
    spec_old = base_spec()
    spec_new = base_spec()
    spec_new["save"] = {
        "step_label": "butter",
        "auto_tags": ["step:butter", "type:raw"],
        "name_template_default": "{subject}_{task}_{node_title}",
        "data_type": "raw",
    }
    assert hash_of(spec_old) == hash_of(spec_new)


def test_ui_color_change_does_not_affect_hash():
    """spec.ui.color 改色 → 不影响算法 → hash 一致。"""
    spec_a = base_spec()
    spec_b = base_spec()
    spec_a["ui"] = {"color": "#2F766F"}
    spec_b["ui"] = {"color": "#9A6A28"}
    assert hash_of(spec_a) == hash_of(spec_b)


def test_backend_save_descriptor_change_does_not_affect_hash():
    """backend.save_descriptor 是文件命名后缀，不影响算法字节输出 → hash 一致。"""
    spec_a = base_spec()
    spec_b = base_spec()
    spec_a["backend"]["save_descriptor"] = "filt"
    spec_b["backend"]["save_descriptor"] = "butterworth"
    assert hash_of(spec_a) == hash_of(spec_b)


def test_backend_output_kind_change_does_not_affect_hash():
    """backend.output_kind / supports_batch / interactive 都是装饰字段，不影响算法 → hash 一致。"""
    spec_a = base_spec()
    spec_b = base_spec()
    spec_a["backend"]["output_kind"] = "fif"
    spec_b["backend"]["output_kind"] = "json"
    spec_a["backend"]["supports_batch"] = True
    spec_b["backend"]["supports_batch"] = False
    spec_a["backend"]["interactive"] = False
    spec_b["backend"]["interactive"] = True
    assert hash_of(spec_a) == hash_of(spec_b)


def test_properties_change_does_not_affect_node_hash_directly():
    """node_hash 不读 spec.properties（properties 通过 params_digest 间接体现）→ properties 数组改了 hash 不变。"""
    spec_a = base_spec()
    spec_b = base_spec()
    spec_a["properties"] = [{"name": "p1", "type": "number", "default": 1}]
    spec_b["properties"] = [
        {"name": "p1", "type": "number", "default": 1},
        {"name": "p2", "type": "boolean", "default": True},
    ]
    assert hash_of(spec_a) == hash_of(spec_b)


def test_cache_config_change_does_not_affect_hash():
    """spec.cache 是缓存"策略"字段，不参与 node_hash —— node_hash 本身就是缓存 key，
    改"怎么缓存"（enabled / strategy）不该改"算什么的指纹"，否则换缓存策略会平白冲掉已缓存结果。
    hash.py.node_hash 显式排除 cache（见其 docstring），故改 cache.* → hash 必须一致。"""
    spec_a = base_spec()
    spec_b = base_spec()
    spec_a["cache"] = {"enabled": True, "strategy": "content_hash"}
    spec_b["cache"] = {"enabled": False, "strategy": "node_hash_v2"}
    assert hash_of(spec_a) == hash_of(spec_b)


# === Group 2: 算法关键字段变化 → hash 改变 ===

def test_node_type_change_changes_hash():
    spec_a = base_spec()
    spec_b = base_spec()
    spec_b["type"] = "eeg/preproc/resample"
    a = node_hash(
        node_type=spec_a["type"], params_digest=PARAMS_DIGEST,
        input_digest=INPUT_DIGEST, node_spec=spec_a,
    )
    b = node_hash(
        node_type=spec_b["type"], params_digest=PARAMS_DIGEST,
        input_digest=INPUT_DIGEST, node_spec=spec_b,
    )
    assert a != b


def test_backend_module_change_changes_hash():
    """改 backend.module 意味着算法换了实现文件 → hash 应该变。"""
    spec_a = base_spec()
    spec_b = base_spec()
    spec_b["backend"]["module"] = "app.engine.preprocess.filters_v2"
    assert hash_of(spec_a) != hash_of(spec_b)


def test_backend_function_change_changes_hash():
    """改 backend.function 意味着调用不同函数 → hash 应该变。"""
    spec_a = base_spec()
    spec_b = base_spec()
    spec_b["backend"]["function"] = "run_filter_v2"
    assert hash_of(spec_a) != hash_of(spec_b)


def test_params_digest_change_changes_hash():
    """params 变 → params_digest 变 → hash 必须变。"""
    a = node_hash(
        node_type="x", params_digest="p1", input_digest="i", node_spec=base_spec(),
    )
    b = node_hash(
        node_type="x", params_digest="p2", input_digest="i", node_spec=base_spec(),
    )
    assert a != b


def test_input_digest_change_changes_hash():
    """input 变 → input_digest 变 → hash 必须变。"""
    a = node_hash(
        node_type="x", params_digest="p", input_digest="i1", node_spec=base_spec(),
    )
    b = node_hash(
        node_type="x", params_digest="p", input_digest="i2", node_spec=base_spec(),
    )
    assert a != b


# === Group 2.5: input_hash 对"上游缓存命中"的稳定性（回归） ===
# 缓存恢复时 cache.py 会往上游产物的 processing 注入 cached=True。若该标记进入
# input_hash，则"上游命中缓存"的下游节点 input_hash 会和"上游新鲜计算"时不一致，
# 导致紧邻下游必然 cache miss 一次（实测：Epoch 命中缓存后 TFR 仍重跑 22s）。

def _data_info(content_hash="sha-aaa", cached=False):
    processing = {"node_id": "n1", "node_type": "eeg/epoch/segment", "params": {"tmin": -0.2}}
    if cached:
        processing["cached"] = True
    return {
        "content_hash": content_hash,
        "sha256": content_hash,
        "artifact_id": "art-1",
        "storage_path": "pipeline/epoch/sub-01.fif",
        "file_role": "pipeline_artifact",
        "data_type": "epochs",
        "processing": processing,
    }


def _inputs(data_info):
    return {"Epochs": {"data_infos": [data_info], "artifacts": [], "value": None}}


def test_input_hash_ignores_cached_marker_in_processing():
    """上游 fresh（无 cached）与 cached（processing.cached=True）→ input_hash 必须一致。"""
    fresh = input_hash(_inputs(_data_info(cached=False)))
    cached = input_hash(_inputs(_data_info(cached=True)))
    assert fresh == cached


def test_input_hash_still_changes_on_real_content_change():
    """真实内容变化（content_hash 不同）仍必须改变 input_hash —— 剔除 cached 标记不引入误命中。"""
    a = input_hash(_inputs(_data_info(content_hash="sha-aaa")))
    b = input_hash(_inputs(_data_info(content_hash="sha-bbb")))
    assert a != b


# === Group 3: 边界 ===

def test_empty_spec_does_not_crash():
    """spec 为空 → 应该用空字典默认值，不抛错。"""
    h = node_hash(node_type="x", params_digest="p", input_digest="i", node_spec={})
    assert isinstance(h, str) and len(h) == 64  # sha256 hex


def test_none_spec_does_not_crash():
    h = node_hash(node_type="x", params_digest="p", input_digest="i", node_spec=None)
    assert isinstance(h, str) and len(h) == 64


def test_hash_is_deterministic():
    """同样输入 → 同样 hash。"""
    spec = base_spec()
    h1 = hash_of(spec)
    h2 = hash_of(spec)
    h3 = hash_of(spec)
    assert h1 == h2 == h3


if __name__ == "__main__":
    import traceback

    tests = [
        (name, fn) for name, fn in dict(globals()).items()
        if name.startswith("test_") and callable(fn)
    ]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"[PASS] {name}")
            passed += 1
        except Exception as e:  # noqa: BLE001
            print(f"[FAIL] {name}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed (of {len(tests)})")
    sys.exit(0 if failed == 0 else 1)
