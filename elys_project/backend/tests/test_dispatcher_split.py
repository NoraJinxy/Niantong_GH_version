"""
Purpose: 单元测试 Epoch split_by="condition" 拆分与 ERP 自动 condition 推断逻辑。

测试范围:
- NodeDispatcher._derived_fif_filename 的 condition 参数（文件名带 condition 后缀）
- NodeDispatcher._save_epochs_dataset 在 condition / non-condition 模式下的行为
- _execute_epochs_output 的 split_mode 分支（用 fake Epochs 模拟）
- _execute_evoked_output 的 condition 推断优先级（input.condition > params.condition）

不依赖 MNE / DB —— 用 FakeEpochs / FakeStudyOutputStore / FakeDb 模拟。

Related: app/pipeline/dispatcher.py
"""

from __future__ import annotations

from pathlib import Path
import sys
import types

import numpy as np


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# ---- stubs（同 test_save_settings.py，避免拉真实 DB / SQLAlchemy） ---------

class _FakeColumn:
    def __init__(self, name): self.name = name
    def is_(self, *a, **kw): return self
    def like(self, *a, **kw): return self
    def in_(self, *a, **kw): return self
    def asc(self, *a, **kw): return self
    def __eq__(self, other): return self
    def __ne__(self, other): return self
    def __hash__(self): return id(self)


_fake_models = types.ModuleType("app.models")


class _StudyOutput:
    display_name = _FakeColumn("display_name")
    study_id = _FakeColumn("study_id")
    deleted_at = _FakeColumn("deleted_at")


class _PipelineExecutionInput:
    execution_id = _FakeColumn("execution_id")
    node_id = _FakeColumn("node_id")
    input_kind = _FakeColumn("input_kind")
    input_index = _FakeColumn("input_index")
    created_at = _FakeColumn("created_at")
    id = _FakeColumn("id")


_fake_models.StudyOutput = _StudyOutput
_fake_models.PipelineExecutionInput = _PipelineExecutionInput
for _name in ("DatasetFile", "Recording", "Study", "StudyDatasetMount", "StudySettings"):
    setattr(_fake_models, _name, type(_name, (), {}))
sys.modules.setdefault("app.models", _fake_models)

if "sqlalchemy" not in sys.modules:
    _fake_sa = types.ModuleType("sqlalchemy")
    _fake_sa.or_ = lambda *a, **kw: None
    _fake_sa.and_ = lambda *a, **kw: None
    _fake_sa.func = types.SimpleNamespace()
    sys.modules["sqlalchemy"] = _fake_sa
    _fake_sa_exc = types.ModuleType("sqlalchemy.exc")
    _fake_sa_exc.IntegrityError = type("IntegrityError", (Exception,), {})
    sys.modules["sqlalchemy.exc"] = _fake_sa_exc
    _fake_sa_orm = types.ModuleType("sqlalchemy.orm")
    _fake_sa_orm.Session = object
    _fake_sa_orm.joinedload = lambda *a, **kw: None
    sys.modules["sqlalchemy.orm"] = _fake_sa_orm


from app.pipeline.dispatcher import NodeDispatcher  # noqa: E402


# =============================================================================
# Group 1: _derived_fif_filename condition 参数
# =============================================================================

def test_filename_without_condition_unchanged():
    out = NodeDispatcher._derived_fif_filename(
        {"fif_path": "sub-01/task-rest/sub-01_task-rest_eeg.fif"},
        "epo",
        0,
        kind="epochs",
    )
    # base: sub-01_task-rest_eeg；后缀 _epo-epo.fif
    assert out == "sub-01_task-rest_eeg_epo-epo.fif"


def test_filename_with_condition_inserts_before_descriptor():
    out = NodeDispatcher._derived_fif_filename(
        {"fif_path": "sub-01_task-rest_eeg.fif"},
        "epo",
        0,
        kind="epochs",
        condition="go",
    )
    assert out == "sub-01_task-rest_eeg_go_epo-epo.fif"


def test_filename_with_condition_sanitizes_unsafe_chars():
    out = NodeDispatcher._derived_fif_filename(
        {"fif_path": "data.fif"},
        "epo",
        0,
        kind="epochs",
        condition="Stim/A.x",
    )
    # 斜杠和点应被替换为 _
    assert "Stim_A_x_epo" in out
    assert out.endswith("-epo.fif")


def test_filename_with_empty_condition_falls_back():
    """condition='' 或 None 都不插入。"""
    out_a = NodeDispatcher._derived_fif_filename(
        {"fif_path": "data.fif"}, "epo", 0, kind="epochs", condition=""
    )
    out_b = NodeDispatcher._derived_fif_filename(
        {"fif_path": "data.fif"}, "epo", 0, kind="epochs", condition=None
    )
    assert out_a == out_b == "data_epo-epo.fif"


def test_filename_evoked_with_condition():
    """ERP 的输出文件名也支持 condition 后缀。"""
    out = NodeDispatcher._derived_fif_filename(
        {"fif_path": "sub-01_task-rest_eeg.fif"},
        "erp",
        0,
        kind="evoked",
        condition="nogo",
    )
    assert out == "sub-01_task-rest_eeg_nogo_erp-ave.fif"


# =============================================================================
# Group 2: _save_epochs_dataset helper（用 fake study_output_store 抓调用）
# =============================================================================

class FakeStudyOutputStore:
    """记录所有 save_file_from_writer 调用的 fake study_output_store。"""

    def __init__(self):
        self.calls = []

    def save_file_from_writer(self, filename, writer, **kwargs):
        record = dict(filename=filename, **kwargs)
        self.calls.append(record)
        # 模拟成功写入的返回值（最小必要键）
        return {
            "artifact_id": f"ds-{len(self.calls)}",
            "storage_path": f"outputs/ab/cd/{filename}",
            "storage_uri": None,
            "file_size": 100,
            "checksum": "abcdef",
            "sha256": "abcdef",
        }


class FakeStudy:
    id = "study-1"
    data_root = "/tmp/study-1"


class FakeExecution:
    id = "run-1"


class FakeJob:
    id = "noderun-1"
    node_id = "epoch-1"


class FakeDb:
    def query(self, *a, **kw):
        return self

    def filter(self, *a, **kw):
        return self

    def all(self):
        return []  # 无冲突


def _make_context(*, params=None, node=None, topology=None, db=None):
    """构造一个最小 NodeExecutionContext（不依赖真实模型）。"""
    from app.pipeline.contracts import NodeExecutionContext

    return NodeExecutionContext(
        db=db or FakeDb(),
        study=FakeStudy(),
        pipeline=None,
        execution=FakeExecution(),
        job=FakeJob(),
        node=node or {"id": "epoch-1", "type": "eeg/epoch/segment", "title": "Epoch"},
        params=params or {},
        inputs={},
        study_output_store=None,
        node_spec={
            "save": {
                "step_label": "epoch",
                "auto_tags": ["step:epoch", "type:epochs"],
                "dynamic_tags_when_split": ["cond:{condition}"],
                "name_template_default": "{subject}_{task}_{node_title}",
                "name_template_default_split": "{subject}_{task}_{condition}_{node_title}",
                "split_supported": True,
                "data_type": "epochs",
            }
        },
        topology=topology or {"epoch-1": "leaf"},
    )


class FakeEpochs:
    """模拟 mne.Epochs 子集：支持 event_id / __getitem__ / __len__."""

    def __init__(self, event_id: dict, count: int = 10):
        self.event_id = dict(event_id)
        self._count = count

    def __getitem__(self, key: str):
        if key not in self.event_id:
            raise KeyError(key)
        # 每个 condition 子集自带单个 event_id；行数按比例缩减
        per_cond = max(1, self._count // max(1, len(self.event_id)))
        return FakeEpochs({key: self.event_id[key]}, count=per_cond)

    def __len__(self):
        return self._count


def test_save_epochs_dataset_writes_correct_filename(monkeypatch):
    """调 _save_epochs_dataset 时 condition='go' → 文件名带 go；no condition → 不带。"""
    import app.pipeline.dispatcher as disp_mod

    # 给 dispatcher 用的 summarize_epochs / save_epochs_fif 打桩
    monkeypatch.setattr(disp_mod, "summarize_epochs", lambda epochs: {"n_epochs": len(epochs)})
    monkeypatch.setattr(disp_mod, "save_epochs_fif", lambda epochs, path: None)

    store = FakeStudyOutputStore()
    artifacts = []
    ctx = _make_context(params={"event_id": ["go", "nogo"]})
    epochs = FakeEpochs({"go": 1, "nogo": 2}, count=20)

    dispatcher = NodeDispatcher()
    info = dispatcher._save_epochs_dataset(
        context=ctx,
        data_info={"fif_path": "sub-01_task-rest_eeg.fif", "bids_subject_id": "sub-01", "task": "rest"},
        epochs=epochs,
        study_output_store=store,
        artifacts=artifacts,
        save_descriptor="epo",
        index=0,
        condition="go",
        node_id="epoch-1",
        node_type="eeg/epoch/segment",
    )

    assert len(store.calls) == 1
    assert store.calls[0]["filename"] == "sub-01_task-rest_eeg_go_epo-epo.fif"
    assert store.calls[0]["metadata"]["condition"] == "go"
    assert "cond:go" in store.calls[0]["metadata"]["tags"]
    assert info["condition"] == "go"


def test_save_epochs_dataset_no_condition_no_suffix(monkeypatch):
    """condition=None → 文件名无 condition，metadata.condition=None。"""
    import app.pipeline.dispatcher as disp_mod

    monkeypatch.setattr(disp_mod, "summarize_epochs", lambda epochs: {"n_epochs": len(epochs)})
    monkeypatch.setattr(disp_mod, "save_epochs_fif", lambda epochs, path: None)

    store = FakeStudyOutputStore()
    ctx = _make_context()
    epochs = FakeEpochs({"go": 1, "nogo": 2}, count=20)

    dispatcher = NodeDispatcher()
    info = dispatcher._save_epochs_dataset(
        context=ctx,
        data_info={"fif_path": "data.fif", "bids_subject_id": "sub-01", "task": "rest"},
        epochs=epochs,
        study_output_store=store,
        artifacts=[],
        save_descriptor="epo",
        index=0,
        condition=None,
        node_id="epoch-1",
        node_type="eeg/epoch/segment",
    )

    assert store.calls[0]["filename"] == "data_epo-epo.fif"
    assert store.calls[0]["metadata"]["condition"] is None
    # split_value=None → 不带 cond: 前缀的标签
    assert all(not t.startswith("cond:") for t in store.calls[0]["metadata"]["tags"])
    assert "condition" not in info  # 未拆分时不写入 data_info.condition


# =============================================================================
# Group 3: _execute_epochs_output split_mode 集成
# =============================================================================

def test_execute_epochs_output_split_condition_iterates_event_ids(monkeypatch):
    """split_by='condition' + 上游 epochs 有 {go, nogo} → 输出 2 个 data_info。"""
    import app.pipeline.dispatcher as disp_mod
    from app.pipeline.contracts import NodeInput

    monkeypatch.setattr(disp_mod, "summarize_epochs", lambda epochs: {"n_epochs": len(epochs)})
    monkeypatch.setattr(disp_mod, "save_epochs_fif", lambda epochs, path: None)
    monkeypatch.setattr(disp_mod, "read_raw_from_data_info", lambda data_info, **kw: object())

    # processor 模拟 run_epoch_segment，返回带 2 个 conditions 的 FakeEpochs
    def fake_processor(raw, params):
        return FakeEpochs({"go": 1, "nogo": 2}, count=20), {"skipped_conditions": []}

    store = FakeStudyOutputStore()
    input_data_info = {"fif_path": "sub-01_task-rest_eeg.fif", "bids_subject_id": "sub-01", "task": "rest"}

    ctx = _make_context(params={"split_by": "condition", "event_id": ["go", "nogo"]})
    ctx.inputs = {"input": NodeInput(port="input", data_infos=[input_data_info])}
    ctx.study_output_store = store

    dispatcher = NodeDispatcher()
    result = dispatcher._execute_epochs_output(ctx, fake_processor, save_descriptor="epo")

    assert result.status == "success"
    assert result.dataset_count == 2
    # 验证生成 2 个文件，文件名各带 condition
    filenames = [c["filename"] for c in store.calls]
    assert "sub-01_task-rest_eeg_go_epo-epo.fif" in filenames
    assert "sub-01_task-rest_eeg_nogo_epo-epo.fif" in filenames
    # 验证 metadata 条件
    conditions = [c["metadata"]["condition"] for c in store.calls]
    assert sorted(conditions) == ["go", "nogo"]
    # 输出 data_info 也带 condition
    output_conditions = [info.get("condition") for info in result.output.data_infos]
    assert sorted(output_conditions) == ["go", "nogo"]
    # 拓扑 metadata 中暴露 split_mode
    assert result.output.metadata.get("split_mode") == "condition"


def test_execute_epochs_output_split_none_keeps_single_output(monkeypatch):
    """split_by='none' → 一进一出，输出无 condition 字段。"""
    import app.pipeline.dispatcher as disp_mod
    from app.pipeline.contracts import NodeInput

    monkeypatch.setattr(disp_mod, "summarize_epochs", lambda epochs: {"n_epochs": len(epochs)})
    monkeypatch.setattr(disp_mod, "save_epochs_fif", lambda epochs, path: None)
    monkeypatch.setattr(disp_mod, "read_raw_from_data_info", lambda data_info, **kw: object())

    def fake_processor(raw, params):
        return FakeEpochs({"go": 1, "nogo": 2}, count=20), {"skipped_conditions": []}

    store = FakeStudyOutputStore()
    input_data_info = {"fif_path": "sub-01_task-rest_eeg.fif", "bids_subject_id": "sub-01", "task": "rest"}

    ctx = _make_context(params={"split_by": "none", "event_id": ["go", "nogo"]})
    ctx.inputs = {"input": NodeInput(port="input", data_infos=[input_data_info])}
    ctx.study_output_store = store

    dispatcher = NodeDispatcher()
    result = dispatcher._execute_epochs_output(ctx, fake_processor, save_descriptor="epo")

    assert result.status == "success"
    assert result.dataset_count == 1
    assert store.calls[0]["filename"] == "sub-01_task-rest_eeg_epo-epo.fif"
    assert store.calls[0]["metadata"]["condition"] is None
    assert "condition" not in result.output.data_infos[0]


def test_execute_epochs_output_split_skips_empty_subepochs(monkeypatch):
    """某个 condition 子集为空 → 跳过，不写入 study_output。"""
    import app.pipeline.dispatcher as disp_mod
    from app.pipeline.contracts import NodeInput

    monkeypatch.setattr(disp_mod, "summarize_epochs", lambda epochs: {"n_epochs": len(epochs)})
    monkeypatch.setattr(disp_mod, "save_epochs_fif", lambda epochs, path: None)
    monkeypatch.setattr(disp_mod, "read_raw_from_data_info", lambda data_info, **kw: object())

    class FakeEpochsWithEmpty(FakeEpochs):
        def __getitem__(self, key):
            if key == "nogo":
                return FakeEpochs({key: 2}, count=0)  # 空集
            return super().__getitem__(key)

    def fake_processor(raw, params):
        return FakeEpochsWithEmpty({"go": 1, "nogo": 2}, count=10), {"skipped_conditions": []}

    store = FakeStudyOutputStore()
    ctx = _make_context(params={"split_by": "condition"})
    ctx.inputs = {"input": NodeInput(port="input", data_infos=[{"fif_path": "data.fif"}])}
    ctx.study_output_store = store

    dispatcher = NodeDispatcher()
    result = dispatcher._execute_epochs_output(ctx, fake_processor, save_descriptor="epo")

    # 只有 go 一个非空
    assert result.dataset_count == 1
    assert store.calls[0]["metadata"]["condition"] == "go"


def test_execute_epoch_merge_groups_parent_conditions_by_source(monkeypatch):
    """Epoch Merge：同一 recording 下拆开的父 condition epochs 合成一份多条件 epochs。"""
    import app.pipeline.dispatcher as disp_mod
    from app.pipeline.contracts import NodeInput

    monkeypatch.setattr(disp_mod, "summarize_epochs", lambda epochs: {"n_epochs": len(epochs)})
    monkeypatch.setattr(disp_mod, "save_epochs_fif", lambda epochs, path: None)
    monkeypatch.setattr(disp_mod, "read_epochs_from_data_info", lambda data_info, **kw: FakeEpochs({data_info["condition"]: 1}, count=5))
    monkeypatch.setattr(disp_mod, "_concatenate_epochs", lambda items: FakeEpochs({"block/A": 1, "block/B": 2}, count=sum(len(item) for item in items)))

    store = FakeStudyOutputStore()
    infos = [
        {
            "data_type": "epochs",
            "fif_path": "sub-01_blockA_epo-epo.fif",
            "source_dataset_id": "rec-01",
            "artifact_id": "block-a",
            "condition": "block/A",
        },
        {
            "data_type": "epochs",
            "fif_path": "sub-01_blockB_epo-epo.fif",
            "source_dataset_id": "rec-01",
            "artifact_id": "block-b",
            "condition": "block/B",
        },
    ]
    ctx = _make_context(
        params={"merge_scope": "source_recording"},
        node={"id": "merge-1", "type": "eeg/epoch/merge", "title": "Epoch Merge"},
    )
    ctx.inputs = {"input": NodeInput(port="input", data_infos=infos)}
    ctx.study_output_store = store

    dispatcher = NodeDispatcher()
    result = dispatcher._execute_epoch_merge(ctx)

    assert result.status == "success"
    assert result.dataset_count == 1
    assert len(store.calls) == 1
    call = store.calls[0]
    assert call["metadata"]["condition"] is None
    assert call["metadata"]["upstream_dataset_ids"] == ["block-a", "block-b"]
    assert call["metadata"]["mne_summary"]["merge_scope"] == "source_recording"
    assert call["metadata"]["mne_summary"]["merged_conditions"] == ["block/A", "block/B"]
    assert result.output.data_infos[0]["merged_conditions"] == ["block/A", "block/B"]


def test_execute_epoch_merge_all_inputs_uses_neutral_display_name(monkeypatch):
    """Epoch Merge 全部输入合并是跨数据集产物，展示名不能沿用第一个被试。"""
    import app.pipeline.dispatcher as disp_mod
    from app.pipeline.contracts import NodeInput

    monkeypatch.setattr(disp_mod, "summarize_epochs", lambda epochs: {"n_epochs": len(epochs)})
    monkeypatch.setattr(disp_mod, "save_epochs_fif", lambda epochs, path: None)
    monkeypatch.setattr(
        disp_mod,
        "read_epochs_from_data_info",
        lambda data_info, **kw: FakeEpochs({data_info["condition"]: 1}, count=5),
    )
    monkeypatch.setattr(
        disp_mod,
        "_concatenate_epochs",
        lambda items: FakeEpochs({"block/A": 1, "block/B": 2}, count=sum(len(item) for item in items)),
    )

    store = FakeStudyOutputStore()
    infos = [
        {
            "data_type": "epochs",
            "fif_path": "sub-05_blockA_epo-epo.fif",
            "source_dataset_id": "rec-05",
            "artifact_id": "block-a",
            "bids_subject_id": "sub-05",
            "task": "rest",
            "condition": "block/A",
        },
        {
            "data_type": "epochs",
            "fif_path": "sub-04_blockB_epo-epo.fif",
            "source_dataset_id": "rec-04",
            "artifact_id": "block-b",
            "bids_subject_id": "sub-04",
            "task": "rest",
            "condition": "block/B",
        },
    ]
    ctx = _make_context(
        params={"merge_scope": "all_inputs"},
        node={"id": "merge-1", "type": "eeg/epoch/merge", "title": "Epoch Merge"},
    )
    ctx.inputs = {"input": NodeInput(port="input", data_infos=infos)}
    ctx.study_output_store = store

    dispatcher = NodeDispatcher()
    result = dispatcher._execute_epoch_merge(ctx)

    assert result.status == "success"
    assert result.dataset_count == 1
    call = store.calls[0]
    assert call["metadata"]["display_name"] == "Epoch Merge · 全部输入合并"
    assert call["metadata"]["mne_summary"]["merge_scope"] == "all_inputs"
    assert call["metadata"]["upstream_dataset_ids"] == ["block-a", "block-b"]


def test_execute_epoch_merge_condition_scope_stays_within_subject(monkeypatch):
    """Epoch Merge condition mode groups matching conditions within each subject."""
    import app.pipeline.dispatcher as disp_mod
    from app.pipeline.contracts import NodeInput

    monkeypatch.setattr(disp_mod, "summarize_epochs", lambda epochs: {"n_epochs": len(epochs)})
    monkeypatch.setattr(disp_mod, "save_epochs_fif", lambda epochs, path: None)
    monkeypatch.setattr(
        disp_mod,
        "read_epochs_from_data_info",
        lambda data_info, **kw: FakeEpochs(dict(data_info["event_ids"]), count=data_info.get("count", 10)),
    )
    monkeypatch.setattr(
        disp_mod,
        "_concatenate_epochs",
        lambda items: FakeEpochs(items[0].event_id, count=sum(len(item) for item in items)),
    )

    store = FakeStudyOutputStore()
    infos = [
        {
            "data_type": "epochs",
            "fif_path": "sub-03_run-01_epo-epo.fif",
            "source_dataset_id": "rec-03-a",
            "artifact_id": "ep-03-a",
            "bids_subject_id": "sub-03",
            "event_ids": {"Stimulus/S 61": 1, "Stimulus/S 62": 2},
            "count": 8,
        },
        {
            "data_type": "epochs",
            "fif_path": "sub-03_run-02_epo-epo.fif",
            "source_dataset_id": "rec-03-b",
            "artifact_id": "ep-03-b",
            "bids_subject_id": "sub-03",
            "event_ids": {"Stimulus/S 61": 1, "Stimulus/S 62": 2},
            "count": 6,
        },
        {
            "data_type": "epochs",
            "fif_path": "sub-04_run-01_epo-epo.fif",
            "source_dataset_id": "rec-04-a",
            "artifact_id": "ep-04-a",
            "bids_subject_id": "sub-04",
            "event_ids": {"Stimulus/S 61": 1, "Stimulus/S 62": 2},
            "count": 4,
        },
    ]
    ctx = _make_context(
        params={"merge_scope": "condition"},
        node={"id": "merge-1", "type": "eeg/epoch/merge", "title": "Epoch Merge"},
    )
    ctx.inputs = {"input": NodeInput(port="input", data_infos=infos)}
    ctx.study_output_store = store

    dispatcher = NodeDispatcher()
    result = dispatcher._execute_epoch_merge(ctx)

    assert result.status == "success"
    assert result.dataset_count == 4
    pairs = {
        (call["metadata"]["mne_summary"]["merge_subject"], call["metadata"]["condition"])
        for call in store.calls
    }
    assert pairs == {
        ("sub-03", "S 61"),
        ("sub-03", "S 62"),
        ("sub-04", "S 61"),
        ("sub-04", "S 62"),
    }

    sub03_s61 = next(
        call
        for call in store.calls
        if call["metadata"]["mne_summary"]["merge_subject"] == "sub-03"
        and call["metadata"]["condition"] == "S 61"
    )
    assert sub03_s61["metadata"]["upstream_dataset_ids"] == ["ep-03-a", "ep-03-b"]
    assert sub03_s61["metadata"]["mne_summary"]["merged_input_count"] == 2

    sub04_s61 = next(
        call
        for call in store.calls
        if call["metadata"]["mne_summary"]["merge_subject"] == "sub-04"
        and call["metadata"]["condition"] == "S 61"
    )
    assert sub04_s61["metadata"]["upstream_dataset_ids"] == ["ep-04-a"]
    assert sub04_s61["metadata"]["mne_summary"]["merged_input_count"] == 1


def test_concatenate_epochs_preserves_annotations_for_nested_epoching(tmp_path):
    """合并父 condition Epochs 后，保存再读取也能继续按父/子路径切下一层 Epoch。"""
    import mne
    from app.engine.analysis.epoching import run_epoch_segment
    from app.engine.io import save_epochs_fif
    import app.pipeline.dispatcher as disp_mod

    sfreq = 100.0
    info = mne.create_info(["Cz"], sfreq, ["eeg"])
    raw = mne.io.RawArray(np.zeros((1, int(10 * sfreq))), info, verbose="ERROR")
    raw.set_annotations(
        mne.Annotations(
            onset=[1.0, 1.5, 5.0, 5.5],
            duration=[0, 0, 0, 0],
            description=["block/A", "sound/low", "block/B", "sound/low"],
        )
    )
    parent, _ = run_epoch_segment(raw, {"conditions": ["block/A", "block/B"], "tmin": 0.0, "tmax": 1.0})

    merged = disp_mod._concatenate_epochs([parent["block/A"], parent["block/B"]])
    merged, summary = NodeDispatcher()._rewrite_epoch_annotations_with_parent_context(merged, {})
    path = tmp_path / "merged-epo.fif"
    save_epochs_fif(merged, path)
    merged = mne.read_epochs(path, preload=True, verbose="ERROR")
    child, diag = run_epoch_segment(merged, {"conditions": ["sound/low"], "tmin": -0.1, "tmax": 0.2})

    assert summary["context_annotation_count"] == 2
    assert len(child) == 2
    assert child.event_id == {"block/A / sound/low": 1, "block/B / sound/low": 2}
    assert diag["skipped_conditions"] == []
    rows = getattr(child, "_elys_condition_metadata")
    assert [row["parent_condition"] for row in rows] == ["block/A", "block/B"]
    assert [row["child_condition"] for row in rows] == ["sound/low", "sound/low"]
    assert [row["condition_path"] for row in rows] == ["block/A / sound/low", "block/B / sound/low"]


def test_execute_epochs_output_child_condition_preserves_parent_paths(monkeypatch):
    """split_by='child_condition'：同一 recording 下不同父 condition 的同名子 condition 按完整路径分开。"""
    import app.pipeline.dispatcher as disp_mod
    from app.pipeline.contracts import NodeInput

    monkeypatch.setattr(disp_mod, "summarize_epochs", lambda epochs: {"n_epochs": len(epochs)})
    monkeypatch.setattr(disp_mod, "save_epochs_fif", lambda epochs, path: None)
    monkeypatch.setattr(disp_mod, "read_epochs_from_data_info", lambda data_info, **kw: object())
    monkeypatch.setattr(
        disp_mod,
        "_concatenate_epochs",
        lambda items: FakeEpochs(items[0].event_id, count=sum(len(item) for item in items)),
    )

    def fake_processor(source, params):
        return FakeEpochs({"sound/low": 1, "sound/high": 2}, count=20), {"skipped_conditions": []}

    store = FakeStudyOutputStore()
    infos = [
        {
            "data_type": "epochs",
            "fif_path": "sub-01_blockA_epo-epo.fif",
            "bids_subject_id": "sub-01",
            "task": "stim",
            "source_dataset_id": "rec-01",
            "artifact_id": "block-a",
            "condition": "block/A",
        },
        {
            "data_type": "epochs",
            "fif_path": "sub-01_blockB_epo-epo.fif",
            "bids_subject_id": "sub-01",
            "task": "stim",
            "source_dataset_id": "rec-01",
            "artifact_id": "block-b",
            "condition": "block/B",
        },
    ]
    ctx = _make_context(params={"split_by": "child_condition", "conditions": ["sound/low", "sound/high"]})
    ctx.inputs = {"input": NodeInput(port="input", data_infos=infos)}
    ctx.study_output_store = store

    dispatcher = NodeDispatcher()
    result = dispatcher._execute_epochs_output(ctx, fake_processor, save_descriptor="epo")

    assert result.status == "success"
    assert result.dataset_count == 4
    assert len(store.calls) == 4
    by_condition = {call["metadata"]["condition"]: call for call in store.calls}
    assert set(by_condition) == {
        "block/A / sound/low",
        "block/A / sound/high",
        "block/B / sound/low",
        "block/B / sound/high",
    }
    assert by_condition["block/A / sound/low"]["metadata"]["parent_conditions"] == ["block/A"]
    assert by_condition["block/A / sound/low"]["metadata"]["child_condition"] == "sound/low"
    assert by_condition["block/A / sound/low"]["metadata"]["condition_path"] == "block/A / sound/low"
    assert by_condition["block/A / sound/low"]["metadata"]["condition_model"] == "hierarchical"
    assert by_condition["block/A / sound/low"]["metadata"]["upstream_dataset_ids"] == ["block-a"]
    output_by_condition = {info["condition"]: info for info in result.output.data_infos}
    assert output_by_condition["block/B / sound/high"]["parent_conditions"] == ["block/B"]
    assert output_by_condition["block/B / sound/high"]["child_condition"] == "sound/high"
    assert result.output.metadata.get("split_mode") == "child_condition"


def test_condition_metadata_subset_fallback_without_pandas():
    """无 pandas 时，MNE metadata 的 ELYS 兜底行也能随 condition 子集转移。"""
    source = FakeEpochs({"sound/low": 1, "sound/high": 2}, count=20)
    source._elys_condition_metadata = [
        {"parent_condition": "block/A", "child_condition": "sound/low"},
        {"parent_condition": "block/B", "child_condition": "sound/low"},
        {"parent_condition": "block/C", "child_condition": "sound/high"},
    ]
    target = FakeEpochs({"sound/low": 1}, count=10)

    NodeDispatcher._attach_condition_metadata_subset(source, target, "sound/low")

    assert NodeDispatcher._parent_conditions_for_epochs(target, {}) == ["block/A", "block/B"]


def test_execute_epochs_output_emits_warning_for_skipped_conditions(monkeypatch):
    """processor 回吐 skipped_conditions → 结果带 severity=warning 的 issue，但仍 success。"""
    import app.pipeline.dispatcher as disp_mod
    from app.pipeline.contracts import NodeInput

    monkeypatch.setattr(disp_mod, "summarize_epochs", lambda epochs: {"n_epochs": len(epochs)})
    monkeypatch.setattr(disp_mod, "save_epochs_fif", lambda epochs, path: None)
    monkeypatch.setattr(disp_mod, "read_raw_from_data_info", lambda data_info, **kw: object())

    def fake_processor(raw, params):
        # 只切出 go；nogo 在该数据中无匹配 → 回吐为 skipped（不阻断）
        return FakeEpochs({"go": 1}, count=10), {"skipped_conditions": ["nogo"]}

    store = FakeStudyOutputStore()
    input_data_info = {"fif_path": "sub-01_task-rest_eeg.fif", "bids_subject_id": "sub-01", "task": "rest"}
    ctx = _make_context(params={"split_by": "none"})
    ctx.inputs = {"input": NodeInput(port="input", data_infos=[input_data_info])}
    ctx.study_output_store = store

    dispatcher = NodeDispatcher()
    result = dispatcher._execute_epochs_output(ctx, fake_processor, save_descriptor="epo")

    assert result.status == "success"        # 部分跳过不阻断
    assert result.dataset_count == 1         # go 仍正常切分输出
    assert len(result.warnings) == 1
    warning = result.warnings[0]
    assert warning["severity"] == "warning"
    assert warning["code"] == "PIPELINE_EPOCH_CONDITIONS_SKIPPED"
    assert "nogo" in warning["message"]


def test_execute_epochs_output_aggregates_skips_across_datasets(monkeypatch):
    """多个数据集都跳同一条件 → 聚合成「一个节点一条」警告（N/M 个数据集），不逐数据集刷屏。"""
    import app.pipeline.dispatcher as disp_mod
    from app.pipeline.contracts import NodeInput

    monkeypatch.setattr(disp_mod, "summarize_epochs", lambda epochs: {"n_epochs": len(epochs)})
    monkeypatch.setattr(disp_mod, "save_epochs_fif", lambda epochs, path: None)
    monkeypatch.setattr(disp_mod, "read_raw_from_data_info", lambda data_info, **kw: object())

    def fake_processor(raw, params):
        return FakeEpochs({"go": 1}, count=10), {"skipped_conditions": ["nogo"]}

    store = FakeStudyOutputStore()
    infos = [
        {"fif_path": "sub-01_task-rest_eeg.fif", "bids_subject_id": "sub-01", "task": "rest"},
        {"fif_path": "sub-02_task-rest_eeg.fif", "bids_subject_id": "sub-02", "task": "rest"},
    ]
    ctx = _make_context(params={"split_by": "none"})
    ctx.inputs = {"input": NodeInput(port="input", data_infos=infos)}
    ctx.study_output_store = store

    dispatcher = NodeDispatcher()
    result = dispatcher._execute_epochs_output(ctx, fake_processor, save_descriptor="epo")

    assert result.status == "success"
    assert result.dataset_count == 2
    assert len(result.warnings) == 1  # 两个数据集聚合成一条警告，而非两条
    assert "2/2" in result.warnings[0]["message"]
    assert "nogo" in result.warnings[0]["message"]


# =============================================================================
# Group 4: _execute_evoked_output ERP condition 推断
# =============================================================================

class FakeEvoked:
    def __init__(self):
        self.nave = 5
        self.ch_names = ["Cz", "Pz"]


def test_execute_evoked_uses_input_condition_when_params_empty(monkeypatch):
    """input.condition='go' + params.condition=空 → ERP 用 'go'，文件名带 _go_。"""
    import app.pipeline.dispatcher as disp_mod
    from app.pipeline.contracts import NodeInput

    monkeypatch.setattr(disp_mod, "summarize_evoked", lambda ev: {"nave": ev.nave})
    monkeypatch.setattr(disp_mod, "save_evoked_fif", lambda ev, path: None)
    monkeypatch.setattr(disp_mod, "read_epochs_from_data_info", lambda data_info, **kw: object())

    received_params = {}

    def fake_processor(epochs, params):
        received_params.update(params)
        return FakeEvoked()

    store = FakeStudyOutputStore()
    input_data_info = {
        "fif_path": "sub-01_task-rest_eeg.fif",
        "bids_subject_id": "sub-01",
        "task": "rest",
        "condition": "go",
    }
    ctx = _make_context(
        params={},
        node={"id": "erp-1", "type": "eeg/analysis/erp", "title": "ERP"},
        topology={"erp-1": "leaf"},
    )
    ctx.node_spec = {
        "save": {
            "step_label": "erp-average",
            "auto_tags": ["step:erp-average", "type:evoked"],
            "dynamic_tags_always": ["cond:{condition}"],
            "name_template_default": "{subject}_{task}_{condition}_{node_title}",
            "always_per_condition": True,
            "data_type": "evoked",
        }
    }
    ctx.inputs = {"input": NodeInput(port="input", data_infos=[input_data_info])}
    ctx.study_output_store = store

    dispatcher = NodeDispatcher()
    result = dispatcher._execute_evoked_output(ctx, fake_processor, save_descriptor="erp")

    assert result.status == "success"
    # processor 接收到的 params.condition 被自动注入
    assert received_params.get("condition") == "go"
    # 文件名带 _go_
    assert "_go_erp-ave.fif" in store.calls[0]["filename"]
    # metadata.condition 写入
    assert store.calls[0]["metadata"]["condition"] == "go"
    # display_name 走 split 模板
    assert "go" in store.calls[0]["metadata"]["display_name"]


def test_execute_evoked_hierarchical_condition_selects_child_and_saves_path(monkeypatch):
    """层级 Epoch 输出：ERP 实际选择 child_condition，但保存和下游分组使用完整 condition_path。"""
    import app.pipeline.dispatcher as disp_mod
    from app.pipeline.contracts import NodeInput

    monkeypatch.setattr(disp_mod, "summarize_evoked", lambda ev: {"nave": ev.nave})
    monkeypatch.setattr(disp_mod, "save_evoked_fif", lambda ev, path: None)
    monkeypatch.setattr(disp_mod, "read_epochs_from_data_info", lambda data_info, **kw: object())

    received_params = {}

    def fake_processor(epochs, params):
        received_params.update(params)
        return FakeEvoked()

    store = FakeStudyOutputStore()
    input_data_info = {
        "fif_path": "sub-01_blockA_sound_low_epo-epo.fif",
        "bids_subject_id": "sub-01",
        "task": "stim",
        "condition": "block/A / sound/low",
        "condition_model": "hierarchical",
        "parent_conditions": ["block/A"],
        "child_condition": "sound/low",
        "condition_path": "block/A / sound/low",
    }
    ctx = _make_context(
        params={},
        node={"id": "erp-1", "type": "eeg/analysis/erp", "title": "ERP"},
        topology={"erp-1": "leaf"},
    )
    ctx.node_spec = {
        "save": {
            "step_label": "erp-average",
            "auto_tags": ["step:erp-average", "type:evoked"],
            "dynamic_tags_always": ["cond:{condition}"],
            "name_template_default": "{subject}_{task}_{condition}_{node_title}",
            "always_per_condition": True,
            "data_type": "evoked",
        }
    }
    ctx.inputs = {"input": NodeInput(port="input", data_infos=[input_data_info])}
    ctx.study_output_store = store

    dispatcher = NodeDispatcher()
    result = dispatcher._execute_evoked_output(ctx, fake_processor, save_descriptor="erp")

    assert result.status == "success"
    assert received_params.get("condition") == "sound/low"
    assert store.calls[0]["metadata"]["condition"] == "block/A / sound/low"
    assert store.calls[0]["metadata"]["analysis_condition"] == "sound/low"
    assert store.calls[0]["metadata"]["condition_path"] == "block/A / sound/low"
    assert result.output.data_infos[0]["condition"] == "block/A / sound/low"
    assert result.output.data_infos[0]["analysis_condition"] == "sound/low"


def test_execute_evoked_input_condition_takes_priority_over_params(monkeypatch):
    """params.condition='nogo' + input.condition='go' → 上游 split 后仍以 input.condition 为准。"""
    import app.pipeline.dispatcher as disp_mod
    from app.pipeline.contracts import NodeInput

    monkeypatch.setattr(disp_mod, "summarize_evoked", lambda ev: {"nave": ev.nave})
    monkeypatch.setattr(disp_mod, "save_evoked_fif", lambda ev, path: None)
    monkeypatch.setattr(disp_mod, "read_epochs_from_data_info", lambda data_info, **kw: object())

    received_params = {}

    def fake_processor(epochs, params):
        received_params.update(params)
        return FakeEvoked()

    store = FakeStudyOutputStore()
    input_data_info = {
        "fif_path": "data.fif",
        "bids_subject_id": "sub-01",
        "task": "rest",
        "condition": "go",
    }
    ctx = _make_context(
        params={"condition": "nogo"},
        node={"id": "erp-1", "type": "eeg/analysis/erp", "title": "ERP"},
        topology={"erp-1": "leaf"},
    )
    ctx.node_spec = {
        "save": {
            "step_label": "erp-average",
            "auto_tags": ["step:erp-average", "type:evoked"],
            "dynamic_tags_always": ["cond:{condition}"],
            "name_template_default": "{subject}_{task}_{condition}_{node_title}",
            "always_per_condition": True,
            "data_type": "evoked",
        }
    }
    ctx.inputs = {"input": NodeInput(port="input", data_infos=[input_data_info])}
    ctx.study_output_store = store

    dispatcher = NodeDispatcher()
    result = dispatcher._execute_evoked_output(ctx, fake_processor, save_descriptor="erp")

    assert result.status == "success"
    # 上游已经是单 condition，静态 params 可能过期，必须以 input.condition 为准。
    assert received_params.get("condition") == "go"
    assert "_go_erp-ave.fif" in store.calls[0]["filename"]
    assert store.calls[0]["metadata"]["condition"] == "go"


if __name__ == "__main__":
    import traceback

    class _MonkeyPatch:
        """极简 monkeypatch context manager 模拟 pytest fixture。"""

        def __init__(self):
            self._restore = []

        def setattr(self, target, name, value):
            old = getattr(target, name)
            setattr(target, name, value)
            self._restore.append((target, name, old))

        def undo(self):
            for target, name, old in reversed(self._restore):
                setattr(target, name, old)

    tests = [
        (k, v) for k, v in dict(globals()).items() if k.startswith("test_") and callable(v)
    ]
    passed = failed = 0
    for name, fn in tests:
        mp = _MonkeyPatch()
        try:
            sig = fn.__code__.co_varnames[: fn.__code__.co_argcount]
            args = [mp] if "monkeypatch" in sig else []
            fn(*args)
            print(f"[PASS] {name}")
            passed += 1
        except Exception as e:  # noqa: BLE001
            print(f"[FAIL] {name}: {e}")
            traceback.print_exc()
            failed += 1
        finally:
            mp.undo()

    print(f"\n{passed} passed, {failed} failed (of {len(tests)})")
    sys.exit(0 if failed == 0 else 1)
