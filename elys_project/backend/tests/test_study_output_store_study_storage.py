"""
Purpose: Test Pipeline StudyOutputStore writes to Study storage and previews resolve storage_uri.
Related: app/pipeline/study_output_store.py, app/pipeline/previews.py, app/pipeline/cache.py.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import sys
import uuid


def clear_lightweight_app_stubs() -> None:
    for name in list(sys.modules):
        if not (
            name == "app.database"
            or name == "app.models"
            or name == "app.services"
            or name == "sqlalchemy"
            or name.startswith("app.database.")
            or name.startswith("app.models.")
            or name.startswith("app.services.")
            or name.startswith("sqlalchemy.")
        ):
            continue
        module = sys.modules.get(name)
        if module is not None and not getattr(module, "__file__", None):
            sys.modules.pop(name, None)


clear_lightweight_app_stubs()

from app.pipeline.study_output_store import StudyOutputStore  # noqa: E402
from app.pipeline.previews import build_study_output_preview, resolve_study_output_path  # noqa: E402


class _FakeColumn:
    """register 的 dedup 查询用到的最小列表达式桩：== / is_() / asc()。"""

    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other):  # type: ignore[override]
        return ("eq", self.name, other)

    def __hash__(self) -> int:
        return hash(self.name)

    def is_(self, other):
        return ("is", self.name, other)

    def asc(self):
        return ("asc", self.name)


class FakeStudyOutput:
    # 类属性 = 列桩（供 filter/order_by 表达式）；实例属性遮蔽为真实值
    study_id = _FakeColumn("study_id")
    sha256 = _FakeColumn("sha256")
    deleted_at = _FakeColumn("deleted_at")
    created_at = _FakeColumn("created_at")

    def __init__(self, **kwargs) -> None:
        self.id = uuid.uuid4()
        self.deleted_at = None
        self.purged_at = None
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeQuery:
    def __init__(self, rows) -> None:
        self._rows = list(rows)

    def filter(self, *conds) -> "FakeQuery":
        rows = self._rows
        for op, name, value in conds:
            if op == "eq":
                rows = [r for r in rows if getattr(r, name, None) == value]
            elif op == "is":
                rows = [r for r in rows if getattr(r, name, None) is value]
        return FakeQuery(rows)

    def order_by(self, *keys) -> "FakeQuery":
        return self

    def first(self):
        return self._rows[0] if self._rows else None


class FakeDb:
    def __init__(self) -> None:
        self.added = []

    def add(self, record) -> None:
        self.added.append(record)

    def flush(self) -> None:
        return None

    def query(self, model) -> FakeQuery:
        return FakeQuery(self.added)


def fake_settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        STUDIES_DIR=str(tmp_path / "studies"),
        DATASETS_STORAGE_ROOT=str(tmp_path / "storage" / "datasets"),
        STUDIES_STORAGE_ROOT=str(tmp_path / "storage" / "studies"),
    )


def patch_storage_settings(monkeypatch, tmp_path: Path) -> None:
    import app.pipeline.study_output_store as study_output_store_module
    import app.services.storage as storage_module

    settings = fake_settings(tmp_path)
    monkeypatch.setattr(study_output_store_module, "get_settings", lambda: settings)
    monkeypatch.setattr(storage_module, "get_settings", lambda: settings)


def make_context(tmp_path: Path):
    study = SimpleNamespace(id="202605000001", data_root=str(tmp_path / "studies" / "202605000001"))
    execution = SimpleNamespace(id=uuid.uuid4())
    job = SimpleNamespace(id=uuid.uuid4(), node_id="filter-1")
    Path(study.data_root).mkdir(parents=True, exist_ok=True)
    return study, execution, job


def test_study_output_store_writes_new_files_to_study_content_addressed_storage(tmp_path, monkeypatch) -> None:
    clear_lightweight_app_stubs()
    patch_storage_settings(monkeypatch, tmp_path)
    study, execution, job = make_context(tmp_path)
    db = FakeDb()

    summary = StudyOutputStore(db, study, execution, job, study_output_model=FakeStudyOutput).save_json(
        "metrics.json",
        {"ok": True},
        kind="metadata",
        data_type="json",
        preview={"ok": True},
    )

    assert summary["storage_uri"].startswith(f"elys://studies/{study.id}/outputs/")
    assert summary["storage_path"].startswith("outputs/")
    derived_path = resolve_study_output_path(study, db.added[0])
    assert derived_path.exists()
    assert derived_path.name == "metrics.json"
    assert derived_path.read_text(encoding="utf-8").strip().startswith("{")
    assert summary["sha256"] in derived_path.as_posix()
    assert not (Path(study.data_root) / "pipeline_runs").exists()


def test_study_output_preview_resolves_study_storage_uri(tmp_path, monkeypatch) -> None:
    clear_lightweight_app_stubs()
    patch_storage_settings(monkeypatch, tmp_path)
    study, execution, job = make_context(tmp_path)
    db = FakeDb()
    summary = StudyOutputStore(db, study, execution, job, study_output_model=FakeStudyOutput).save_json(
        "summary.json",
        {"rows": 3},
        kind="metadata",
        data_type="json",
        preview={"rows": 3},
    )
    derived = db.added[0]

    preview = build_study_output_preview(study, derived)

    assert preview["study_output_id"] == str(derived.id)
    assert preview["storage_path"] == summary["storage_path"]
    assert preview["storage_uri"] == summary["storage_uri"]
    assert preview["preview_json"]["preview_source"] == "study_output.preview_json"
    assert preview["preview_json"]["summary"] == {"rows": 3}


def test_register_dedup_reuses_active_row_for_same_content(tmp_path, monkeypatch) -> None:
    clear_lightweight_app_stubs()
    patch_storage_settings(monkeypatch, tmp_path)
    study, execution, job = make_context(tmp_path)
    db = FakeDb()
    store = StudyOutputStore(db, study, execution, job, study_output_model=FakeStudyOutput)

    first = store.save_json("metrics.json", {"ok": True}, kind="metadata", data_type="json")
    second = store.save_json("metrics.json", {"ok": True}, kind="metadata", data_type="json")

    assert len(db.added) == 1
    assert second["study_output_id"] == first["study_output_id"]
    assert second["sha256"] == first["sha256"]


def test_register_revives_recycled_row_for_same_content(tmp_path, monkeypatch) -> None:
    """回收站行占 (study_id, sha256) 唯一索引；重跑产出同内容时应复活该行而不是 INSERT 撞索引。"""
    clear_lightweight_app_stubs()
    patch_storage_settings(monkeypatch, tmp_path)
    study, execution, job = make_context(tmp_path)
    db = FakeDb()
    store = StudyOutputStore(db, study, execution, job, study_output_model=FakeStudyOutput)

    first = store.save_json(
        "metrics.json",
        {"ok": True},
        kind="metadata",
        data_type="json",
        metadata={"keep": False, "cache_eligible": False, "retention_expires_at": datetime.utcnow()},
    )
    row = db.added[0]
    row.deleted_at = datetime.utcnow()

    second = store.save_json(
        "metrics.json",
        {"ok": True},
        kind="metadata",
        data_type="json",
        metadata={"keep": True},
    )

    assert len(db.added) == 1
    assert second["study_output_id"] == first["study_output_id"]
    assert row.deleted_at is None
    assert row.purged_at is None
    # 生命周期重置为本次 save_settings 决策：keep=true 行 TTL 恒为 NULL
    assert row.keep is True
    assert row.cache_eligible is False
    assert row.retention_expires_at is None


def test_register_revives_purged_row_and_rewrites_file(tmp_path, monkeypatch) -> None:
    """已清盘行复活：register 前同 sha 文件已被重新写回 content-addressed 路径，磁盘文件回来了。"""
    clear_lightweight_app_stubs()
    patch_storage_settings(monkeypatch, tmp_path)
    study, execution, job = make_context(tmp_path)
    db = FakeDb()
    store = StudyOutputStore(db, study, execution, job, study_output_model=FakeStudyOutput)

    first = store.save_json("metrics.json", {"ok": True}, kind="metadata", data_type="json")
    row = db.added[0]
    row.deleted_at = datetime.utcnow() - timedelta(days=31)
    row.purged_at = datetime.utcnow()
    derived_path = resolve_study_output_path(study, row)
    derived_path.unlink()  # 模拟 GC 物理清盘
    assert not derived_path.exists()

    future_ttl = datetime.utcnow() + timedelta(days=7)
    second = store.save_json(
        "metrics.json",
        {"ok": True},
        kind="metadata",
        data_type="json",
        metadata={"keep": False, "cache_eligible": True, "retention_expires_at": future_ttl},
    )

    assert len(db.added) == 1
    assert second["study_output_id"] == first["study_output_id"]
    assert derived_path.exists()  # 文件随重跑重新落盘
    assert row.deleted_at is None
    assert row.purged_at is None
    assert row.keep is False
    assert row.cache_eligible is True
    assert row.retention_expires_at == future_ttl
