"""
Purpose: 单元测试 app/pipeline/save_settings.py 的纯函数与组合函数：
         render_template / merge_tags / default_retention_for_role /
         resolve_display_name_conflict / apply_save_settings。

不依赖真实 DB —— 用 _FakeDb 模拟 SQLAlchemy session 的 query 链。

Related: app/pipeline/save_settings.py, app/pipeline/topology.py
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sys


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# ---- minimal stubs：避免 app.models 拉起完整 SQLAlchemy 模型加载 -------------

class _FakeQuery:
    """模拟 db.query(...).filter(...).filter(...).all() 返回固定结果。"""

    def __init__(self, rows: list):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return list(self._rows)


class _FakeDb:
    def __init__(self, rows: list | None = None):
        self.rows = rows or []

    def query(self, *args, **kwargs):
        return _FakeQuery(self.rows)


# 让 save_settings 导入 DerivedDataset 时拿到一个能被 query() 接受的 Mock 类
import types  # noqa: E402


class _FakeColumn:
    """SQLAlchemy Column 的最小 stub —— 支持 .is_() / .like() / == / != 调用。"""

    def __init__(self, name):
        self.name = name

    def is_(self, *args, **kwargs):
        return self

    def like(self, *args, **kwargs):
        return self

    def __eq__(self, other):
        return self

    def __ne__(self, other):
        return self

    def __hash__(self):  # 让 __eq__ 不破坏可哈希性（虽然测试里不需要）
        return id(self)


_fake_models = types.ModuleType("app.models")


class _DerivedDataset:  # placeholder with column-like attrs
    display_name = _FakeColumn("display_name")
    study_id = _FakeColumn("study_id")
    deleted_at = _FakeColumn("deleted_at")
    retention_status = _FakeColumn("retention_status")


_fake_models.DerivedDataset = _DerivedDataset
sys.modules.setdefault("app.models", _fake_models)

# sqlalchemy.or_ stub（resolve_display_name_conflict 内 from sqlalchemy import or_）
if "sqlalchemy" not in sys.modules:
    _fake_sa = types.ModuleType("sqlalchemy")
    _fake_sa.or_ = lambda *args, **kwargs: None
    sys.modules["sqlalchemy"] = _fake_sa


from app.pipeline.save_settings import (  # noqa: E402
    apply_save_settings,
    default_retention_for_role,
    merge_tags,
    render_template,
    resolve_display_name_conflict,
)
from app.pipeline.topology import (  # noqa: E402
    ROLE_INTERMEDIATE,
    ROLE_LEAF,
    ROLE_SOURCE_ONLY,
)


# cache_retention_for_role 单独导入，避免拉起 PipelineCache 类需要的 storage 依赖
def _import_cache_retention():
    """从 cache.py 提取 cache_retention_for_role —— 用源码 exec 避免 import 拉 storage_service。"""
    import importlib.util
    spec_path = BACKEND_DIR / "app" / "pipeline" / "cache.py"
    source = spec_path.read_text(encoding="utf-8")
    # 只取 cache_retention_for_role 函数（独立、无外部依赖）
    namespace: dict = {}
    # 提取 def cache_retention_for_role 开始到下一个空行后的 def/class
    lines = source.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("def cache_retention_for_role"))
    end = start + 1
    while end < len(lines) and (lines[end].startswith((" ", "\t")) or not lines[end].strip()):
        end += 1
    exec("\n".join(lines[start:end]), namespace)
    return namespace["cache_retention_for_role"]


cache_retention_for_role = _import_cache_retention()


# ---- render_template -------------------------------------------------------

def test_render_template_basic_placeholders():
    out = render_template(
        "{subject}_{task}_{node_title}",
        {"subject": "sub-01", "task": "rest", "node_title": "Butter"},
    )
    assert out == "sub-01_rest_Butter"


def test_render_template_subject_falls_back_to_bids_subject_id():
    out = render_template("{subject}", {"bids_subject_id": "sub-02"})
    assert out == "sub-02"


def test_render_template_missing_value_returns_marker():
    out = render_template("{subject}_{task}", {"subject": "sub-01"})
    assert out == "sub-01_{task?}"


def test_render_template_empty_template_returns_empty():
    assert render_template("", {"subject": "sub-01"}) == ""


def test_render_template_index_substitutes():
    out = render_template("trial-{index}", {"index": 3})
    assert out == "trial-3"


# ---- merge_tags ------------------------------------------------------------

def test_merge_tags_dedupes_and_preserves_order():
    out = merge_tags(["a", "b"], ["b", "c"], ["a", "d"])
    assert out == ["a", "b", "c", "d"]


def test_merge_tags_renders_templates_via_ctx():
    out = merge_tags(["cond:{condition}"], ctx={"condition": "go"})
    assert out == ["cond:go"]


def test_merge_tags_filters_empty_strings():
    out = merge_tags(["", "  ", "real-tag"])
    assert out == ["real-tag"]


def test_merge_tags_splits_comma_separated_strings():
    out = merge_tags("a, b, c")
    assert out == ["a", "b", "c"]


def test_merge_tags_handles_none_sources():
    out = merge_tags(None, ["a"], None, ["b"])
    assert out == ["a", "b"]


# ---- default_retention_for_role -------------------------------------------

def test_retention_leaf_is_current_no_expiry():
    status, expires = default_retention_for_role(ROLE_LEAF)
    assert status == "current"
    assert expires is None


def test_retention_intermediate_is_cached_with_expiry():
    status, expires = default_retention_for_role(ROLE_INTERMEDIATE)
    assert status == "cached"
    assert expires is not None
    # 默认 7 天，允许 +/- 5 秒抖动
    delta = expires - datetime.utcnow()
    assert timedelta(days=6, hours=23) < delta <= timedelta(days=7, seconds=5)


def test_retention_source_role_defaults_to_current():
    status, expires = default_retention_for_role(ROLE_SOURCE_ONLY)
    assert status == "current"
    assert expires is None


def test_retention_none_role_defaults_to_current():
    status, expires = default_retention_for_role(None)
    assert status == "current"
    assert expires is None


# ---- resolve_display_name_conflict ----------------------------------------

def test_conflict_no_existing_returns_base():
    out = resolve_display_name_conflict(_FakeDb(rows=[]), "study-1", "sub-01_rest_Butter")
    assert out == "sub-01_rest_Butter"


def test_conflict_base_exists_appends_2():
    db = _FakeDb(rows=[("sub-01_rest_Butter",)])
    out = resolve_display_name_conflict(db, "study-1", "sub-01_rest_Butter")
    assert out == "sub-01_rest_Butter (2)"


def test_conflict_multiple_suffixes_picks_next_available():
    db = _FakeDb(rows=[
        ("sub-01_rest_Butter",),
        ("sub-01_rest_Butter (2)",),
        ("sub-01_rest_Butter (3)",),
    ])
    out = resolve_display_name_conflict(db, "study-1", "sub-01_rest_Butter")
    assert out == "sub-01_rest_Butter (4)"


def test_conflict_holes_filled():
    # 已有 (3) 但没 (2)，应填 (2)
    db = _FakeDb(rows=[
        ("sub-01_rest_Butter",),
        ("sub-01_rest_Butter (3)",),
    ])
    out = resolve_display_name_conflict(db, "study-1", "sub-01_rest_Butter")
    assert out == "sub-01_rest_Butter (2)"


def test_conflict_empty_base_returns_input():
    out = resolve_display_name_conflict(_FakeDb(rows=[]), "study-1", "")
    assert out == ""


# ---- apply_save_settings (end-to-end with FakeDb) -------------------------

def _node(node_id="butter-1", node_type="eeg/filter/apply", title="Butter"):
    return {"id": node_id, "type": node_type, "title": title}


def _spec_butter():
    return {
        "save": {
            "step_label": "butter",
            "auto_tags": ["step:butter", "type:raw"],
            "name_template_default": "{subject}_{task}_{node_title}",
            "split_supported": False,
            "data_type": "raw",
        }
    }


def _spec_erp():
    return {
        "save": {
            "step_label": "erp-average",
            "auto_tags": ["step:erp-average", "type:evoked"],
            "dynamic_tags_always": ["cond:{condition}"],
            "name_template_default": "{subject}_{task}_{condition}_{node_title}",
            "always_per_condition": True,
            "data_type": "evoked",
        }
    }


def _spec_epoch():
    return {
        "save": {
            "step_label": "epoch",
            "auto_tags": ["step:epoch", "type:epochs"],
            "dynamic_tags_when_split": ["cond:{condition}"],
            "name_template_default": "{subject}_{task}_{node_title}",
            "name_template_default_split": "{subject}_{task}_{condition}_{node_title}",
            "split_supported": True,
            "data_type": "epochs",
        }
    }


def test_apply_save_settings_butter_leaf():
    """中间节点 Butter (leaf=False) → cached + 7d；display_name = 模板渲染。"""
    out = apply_save_settings(
        db=_FakeDb(rows=[]),
        study_id="study-1",
        node=_node(),
        node_spec=_spec_butter(),
        params={},
        topology={"butter-1": ROLE_INTERMEDIATE},
        bids_entities={"bids_subject_id": "sub-01", "task": "rest"},
        index=0,
    )
    assert out["display_name"] == "sub-01_rest_Butter"
    assert out["tags"] == ["step:butter", "type:raw"]
    assert out["retention_status"] == "cached"
    assert out["retention_expires_at"] is not None
    assert out["data_type"] == "raw"
    assert out["step_label"] == "butter"


def test_apply_save_settings_leaf_node_is_current():
    """同样是 Butter 但拓扑是 leaf → retention=current。"""
    out = apply_save_settings(
        db=_FakeDb(rows=[]),
        study_id="study-1",
        node=_node(),
        node_spec=_spec_butter(),
        params={},
        topology={"butter-1": ROLE_LEAF},
        bids_entities={"bids_subject_id": "sub-01", "task": "rest"},
        index=0,
    )
    assert out["retention_status"] == "current"
    assert out["retention_expires_at"] is None


def test_apply_save_settings_user_retention_override():
    """用户在 params.retention 显式 pinned，覆盖拓扑默认。"""
    out = apply_save_settings(
        db=_FakeDb(rows=[]),
        study_id="study-1",
        node=_node(),
        node_spec=_spec_butter(),
        params={"retention": "pinned"},
        topology={"butter-1": ROLE_INTERMEDIATE},
        bids_entities={"bids_subject_id": "sub-01", "task": "rest"},
        index=0,
    )
    assert out["retention_status"] == "pinned"
    assert out["retention_expires_at"] is None


def test_apply_save_settings_user_tags_merge():
    """用户自定义 tag 与 auto_tags 合并去重。"""
    out = apply_save_settings(
        db=_FakeDb(rows=[]),
        study_id="study-1",
        node=_node(),
        node_spec=_spec_butter(),
        params={"tags": ["step:butter", "lab-internal", "v2"]},
        topology={"butter-1": ROLE_LEAF},
        bids_entities={"bids_subject_id": "sub-01", "task": "rest"},
        index=0,
    )
    # auto 顺序在前；用户 tag 中重复的 'step:butter' 不再追加；其余追加
    assert out["tags"] == ["step:butter", "type:raw", "lab-internal", "v2"]


def test_apply_save_settings_user_display_name_template_overrides_spec():
    """用户给 display_name_template 覆盖 spec 的默认模板。"""
    out = apply_save_settings(
        db=_FakeDb(rows=[]),
        study_id="study-1",
        node=_node(),
        node_spec=_spec_butter(),
        params={"display_name_template": "custom_{subject}"},
        topology={"butter-1": ROLE_LEAF},
        bids_entities={"bids_subject_id": "sub-99", "task": "rest"},
        index=0,
    )
    assert out["display_name"] == "custom_sub-99"


def test_apply_save_settings_epoch_split_uses_split_template_and_tag():
    """Epoch split_by=condition → 使用 _split 模板，自动加 cond:{condition} tag。"""
    out = apply_save_settings(
        db=_FakeDb(rows=[]),
        study_id="study-1",
        node={"id": "epoch-1", "type": "eeg/epoch/segment", "title": "Epoch"},
        node_spec=_spec_epoch(),
        params={},
        topology={"epoch-1": ROLE_LEAF},
        bids_entities={"bids_subject_id": "sub-01", "task": "rest"},
        split_value="go",
        index=0,
    )
    assert out["display_name"] == "sub-01_rest_go_Epoch"
    assert "cond:go" in out["tags"]
    assert "step:epoch" in out["tags"]
    assert "type:epochs" in out["tags"]


def test_apply_save_settings_epoch_no_split_uses_default_template():
    """Epoch split_by=none → 使用 name_template_default，不加 cond tag。"""
    out = apply_save_settings(
        db=_FakeDb(rows=[]),
        study_id="study-1",
        node={"id": "epoch-1", "type": "eeg/epoch/segment", "title": "Epoch"},
        node_spec=_spec_epoch(),
        params={},
        topology={"epoch-1": ROLE_LEAF},
        bids_entities={"bids_subject_id": "sub-01", "task": "rest"},
        split_value=None,
        index=0,
    )
    assert out["display_name"] == "sub-01_rest_Epoch"
    assert all(not t.startswith("cond:") for t in out["tags"])


def test_apply_save_settings_erp_always_per_condition_adds_cond_tag():
    """ERP always_per_condition=True → 即使 split_value=None，dynamic_tags_always 仍生效。

    （condition 在 ctx 中从 bids_entities.condition 或 params.condition 来；
    这里测试 split_value 传入的情形。）
    """
    out = apply_save_settings(
        db=_FakeDb(rows=[]),
        study_id="study-1",
        node={"id": "erp-1", "type": "eeg/analysis/erp", "title": "ERP"},
        node_spec=_spec_erp(),
        params={},
        topology={"erp-1": ROLE_LEAF},
        bids_entities={"bids_subject_id": "sub-01", "task": "rest"},
        split_value="go",
        index=0,
    )
    assert out["display_name"] == "sub-01_rest_go_ERP"
    assert "cond:go" in out["tags"]


def test_apply_save_settings_conflict_appends_suffix():
    """同 study_id + 同 display_name 已存在 → 自动加 (2)。"""
    db = _FakeDb(rows=[("sub-01_rest_Butter",)])
    out = apply_save_settings(
        db=db,
        study_id="study-1",
        node=_node(),
        node_spec=_spec_butter(),
        params={},
        topology={"butter-1": ROLE_LEAF},
        bids_entities={"bids_subject_id": "sub-01", "task": "rest"},
        index=0,
    )
    assert out["display_name"] == "sub-01_rest_Butter (2)"


def test_apply_save_settings_missing_subject_uses_marker():
    """BIDS subject 缺失 → 模板里渲染成 {subject?}，不抛错。"""
    out = apply_save_settings(
        db=_FakeDb(rows=[]),
        study_id="study-1",
        node=_node(),
        node_spec=_spec_butter(),
        params={},
        topology={"butter-1": ROLE_LEAF},
        bids_entities={"task": "rest"},  # 没 subject
        index=0,
    )
    assert "{subject?}" in out["display_name"]
    assert "rest" in out["display_name"]
    assert "Butter" in out["display_name"]


def test_apply_save_settings_no_spec_uses_fallback_template():
    """node_spec.save 为空 → 仍能渲染基础模板。"""
    out = apply_save_settings(
        db=_FakeDb(rows=[]),
        study_id="study-1",
        node=_node(),
        node_spec={},
        params={},
        topology={"butter-1": ROLE_LEAF},
        bids_entities={"bids_subject_id": "sub-01", "task": "rest"},
        index=0,
    )
    # fallback "{subject}_{task}_{node_title}"
    assert out["display_name"] == "sub-01_rest_Butter"
    assert out["tags"] == []


# ---- cache_retention_for_role (P2) ----------------------------------------

def test_cache_retention_leaf_is_current():
    assert cache_retention_for_role("leaf") == "current"


def test_cache_retention_intermediate_is_cached():
    assert cache_retention_for_role("intermediate") == "cached"


def test_cache_retention_source_falls_back_to_cached():
    """source 节点（LoadData）即使被 cache 也不应是 current —— LoadData 没有 derived_dataset，不会真发生。"""
    assert cache_retention_for_role("source") == "cached"


def test_cache_retention_none_role_defaults_to_cached():
    assert cache_retention_for_role(None) == "cached"


if __name__ == "__main__":
    # 简易自跑模式：可不依赖 pytest 直接 python -m tests.test_save_settings
    import traceback

    tests = [
        v for k, v in dict(globals()).items() if k.startswith("test_") and callable(v)
    ]
    passed = 0
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"[PASS] {fn.__name__}")
            passed += 1
        except Exception as e:  # noqa: BLE001
            print(f"[FAIL] {fn.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed (of {len(tests)})")
    sys.exit(0 if failed == 0 else 1)
