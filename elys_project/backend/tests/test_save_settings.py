"""
Purpose: 单元测试 app/pipeline/save_settings.py 的纯函数与组合函数：
         render_template / merge_tags / default_keep_for_role /
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


# 让 save_settings 导入 StudyOutput 时拿到一个能被 query() 接受的 Mock 类
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


class _StudyOutput:  # placeholder with column-like attrs
    display_name = _FakeColumn("display_name")
    study_id = _FakeColumn("study_id")
    deleted_at = _FakeColumn("deleted_at")


_fake_models.StudyOutput = _StudyOutput
sys.modules.setdefault("app.models", _fake_models)

# sqlalchemy.or_ stub（resolve_display_name_conflict 内 from sqlalchemy import or_）
if "sqlalchemy" not in sys.modules:
    _fake_sa = types.ModuleType("sqlalchemy")
    _fake_sa.or_ = lambda *args, **kwargs: None
    sys.modules["sqlalchemy"] = _fake_sa


from app.pipeline.save_settings import (  # noqa: E402
    DEFAULT_INTERMEDIATE_RETENTION_DAYS,
    USER_ACTION_GRACE_DAYS,
    apply_save_settings,
    default_keep_for_role,
    merge_tags,
    render_template,
    resolve_display_name_conflict,
    retention_expiry_after_user_action,
)
from app.pipeline.topology import (  # noqa: E402
    ROLE_INTERMEDIATE,
    ROLE_LEAF,
    ROLE_SOURCE_ONLY,
)


# (P3：cache_retention_for_role 已删除，按拓扑分级缓存改由 cache_eligible/keep 承担，无对应测试)


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


# ---- default_keep_for_role ------------------------------------------------

def test_keep_leaf_is_true():
    assert default_keep_for_role(ROLE_LEAF) is True


def test_keep_intermediate_is_false():
    assert default_keep_for_role(ROLE_INTERMEDIATE) is False


def test_keep_source_role_is_true():
    assert default_keep_for_role(ROLE_SOURCE_ONLY) is True


def test_keep_none_role_is_true():
    assert default_keep_for_role(None) is True


# ---- retention_expiry_after_user_action ------------------------------------
# 用户动作（PATCH keep=false / 回收站恢复）后的 TTL 重算口径——缺陷修复锚点：
# 不补 TTL 的话，NULL / 已过期的 retention_expires_at 会让下一轮每日 cleanup
# 立即再次软删，用户的「恢复 / 不保留」操作形同无效。


def test_user_action_keep_true_clears_ttl():
    assert retention_expiry_after_user_action(keep=True, cache_eligible=True) is None
    assert retention_expiry_after_user_action(keep=True, cache_eligible=False) is None


def test_user_action_unkeep_cache_eligible_gets_cache_ttl():
    before = datetime.utcnow()
    expires = retention_expiry_after_user_action(keep=False, cache_eligible=True)
    assert expires is not None
    assert (
        timedelta(days=DEFAULT_INTERMEDIATE_RETENTION_DAYS)
        <= expires - before
        <= timedelta(days=DEFAULT_INTERMEDIATE_RETENTION_DAYS, minutes=1)
    )


def test_user_action_unkeep_non_cache_gets_grace_not_immediate():
    before = datetime.utcnow()
    expires = retention_expiry_after_user_action(keep=False, cache_eligible=False)
    assert expires is not None
    assert expires > before  # 关键：必须在未来，不能沿用产出时"登记即过期"的口径
    assert (
        timedelta(days=USER_ACTION_GRACE_DAYS)
        <= expires - before
        <= timedelta(days=USER_ACTION_GRACE_DAYS, minutes=1)
    )


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
    assert out["keep"] is False
    assert out["cache_eligible"] is False  # _spec_butter 无 compute_cost/output_footprint 标签
    assert out["retention_expires_at"] is not None  # keep=False → 有 TTL（不缓存即立即过期）
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
    assert out["keep"] is True
    assert out["retention_expires_at"] is None


def test_apply_save_settings_user_keep_override():
    """用户在 params.keep 显式 True，覆盖拓扑默认（intermediate 本应 False）。"""
    out = apply_save_settings(
        db=_FakeDb(rows=[]),
        study_id="study-1",
        node=_node(),
        node_spec=_spec_butter(),
        params={"keep": True},
        topology={"butter-1": ROLE_INTERMEDIATE},
        bids_entities={"bids_subject_id": "sub-01", "task": "rest"},
        index=0,
    )
    assert out["keep"] is True
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


# ---- 四元组命名（P1 修重名：run/session 进名字） --------------------------

def test_render_template_optional_segment_included_when_present():
    out = render_template(
        "{subject}[_{session}]_{task}[_{run}]_{node_title}",
        {"subject": "sub-01", "session": "ses-b", "task": "task-rest", "run": "run-14", "node_title": "Filter"},
    )
    assert out == "sub-01_ses-b_task-rest_run-14_Filter"


def test_render_template_optional_segment_omitted_when_missing():
    # 无 session / 无 run → 两可选段连同下划线一起消失，不留 __ 空洞
    out = render_template(
        "{subject}[_{session}]_{task}[_{run}]_{node_title}",
        {"subject": "sub-01", "task": "task-rest", "node_title": "Filter"},
    )
    assert out == "sub-01_task-rest_Filter"


def test_apply_save_settings_includes_session_and_run():
    """逐数据集产物名带上 BIDS 四元组（session/run），不再只 subject_task。"""
    out = apply_save_settings(
        db=_FakeDb(rows=[]),
        study_id="study-1",
        node=_node(),
        node_spec=_spec_butter(),
        params={},
        topology={"butter-1": ROLE_LEAF},
        bids_entities={"bids_subject_id": "sub-09", "session": "ses-b", "task": "task-rest", "run": "run-14"},
        index=0,
    )
    assert out["display_name"] == "sub-09_ses-b_task-rest_run-14_Butter"


def test_apply_save_settings_runs_get_distinct_names_without_suffix():
    """同被试/任务的不同 run → 名字天然不同，不靠 (N) 退化区分（P1 核心修复）。"""
    # 库里已有 run-01 的产物，现在落 run-14：base 不同 → 不触发 (N)
    db = _FakeDb(rows=[("sub-09_ses-b_task-rest_run-01_Butter",)])
    out = apply_save_settings(
        db=db,
        study_id="study-1",
        node=_node(),
        node_spec=_spec_butter(),
        params={},
        topology={"butter-1": ROLE_LEAF},
        bids_entities={"bids_subject_id": "sub-09", "session": "ses-b", "task": "task-rest", "run": "run-14"},
        index=0,
    )
    assert out["display_name"] == "sub-09_ses-b_task-rest_run-14_Butter"
    assert "(2)" not in out["display_name"]


def test_apply_save_settings_group_template_not_upgraded():
    """组级模板（不含 {subject}，如 Grand Average）保持 spec 原样，不被四元组策略污染。"""
    spec = {"save": {"step_label": "grandavg", "name_template_default": "Grand Average", "data_type": "evoked"}}
    out = apply_save_settings(
        db=_FakeDb(rows=[]),
        study_id="study-1",
        node={"id": "ga-1", "type": "eeg/group/average", "title": "Grand Average"},
        node_spec=spec,
        params={},
        topology={"ga-1": ROLE_LEAF},
        bids_entities={"bids_subject_id": "sub-01", "task": "task-rest"},
        index=0,
    )
    assert out["display_name"] == "Grand Average"


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
