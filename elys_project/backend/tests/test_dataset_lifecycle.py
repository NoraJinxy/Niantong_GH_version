"""
Purpose: Test dataset lifecycle state machine (publish / withdraw / emergency takedown).
Related: app/services/dataset_lifecycle.py, app/services/semver.py, docs_v2/3-25.
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType, SimpleNamespace
from uuid import uuid4
import sys


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def install_fastapi_stub() -> None:
    fastapi = ModuleType("fastapi")
    fastapi.HTTPException = type("HTTPException", (Exception,), {})
    fastapi.APIRouter = type("APIRouter", (), {"__init__": lambda self, *a, **k: None})
    fastapi.Body = lambda default=None, **kwargs: default
    fastapi.Depends = lambda *a, **k: None
    fastapi.Query = lambda default=None, **kwargs: default
    fastapi.status = SimpleNamespace(
        HTTP_200_OK=200,
        HTTP_201_CREATED=201,
        HTTP_403_FORBIDDEN=403,
        HTTP_404_NOT_FOUND=404,
        HTTP_409_CONFLICT=409,
        HTTP_422_UNPROCESSABLE_ENTITY=422,
        HTTP_500_INTERNAL_SERVER_ERROR=500,
    )
    sys.modules["fastapi"] = fastapi


install_fastapi_stub()

from app.models import AuditEvent, DatasetAsset, DatasetVersion, DatasetWithdrawalRequest
from app.services import dataset_lifecycle
from app.services.dataset_lifecycle import (
    DatasetLifecyclePermissionError,
    DatasetLifecycleStateError,
    DatasetLifecycleValidationError,
)
from app.services.semver import (
    SemVerError,
    compare_semver,
    ensure_strictly_newer,
    is_valid_semver,
    parse_semver,
)


# ============================================
# Test doubles
# ============================================


class FakeQuery:
    """支持 filter()+first()+all() 的简化 query。

    具体过滤逻辑由测试在 added 里手动准备数据，filter() 不真做条件匹配 ——
    测试每个用例时往 db.added 里只放期望返回的对象即可。
    """

    def __init__(self, db, model) -> None:
        self.db = db
        self.model = model

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        for item in self.db.added:
            if isinstance(item, self.model):
                return item
        return None

    def all(self):
        return [item for item in self.db.added if isinstance(item, self.model)]


class FakeDb:
    def __init__(self) -> None:
        self.added = []
        self.committed = False
        self.refreshed = []

    def add(self, item) -> None:
        self.added.append(item)

    def query(self, model):
        return FakeQuery(self, model)

    def flush(self) -> None:
        for item in self.added:
            if getattr(item, "id", None) is None:
                item.id = uuid4()

    def commit(self) -> None:
        self.committed = True

    def refresh(self, item) -> None:
        self.refreshed.append(item)

    def rollback(self) -> None:
        pass


class FakeUser:
    def __init__(self, *, roles=("pi",), uid=None) -> None:
        self.id = uid or uuid4()
        self._roles = set(roles)

    def has_role(self, role: str) -> bool:
        return role in self._roles


def make_draft_asset_and_version(*, owner: FakeUser, primary_study_id="study-001"):
    asset = DatasetAsset(
        id=uuid4(),
        name="Demo",
        code="demo",
        owner_id=owner.id,
        status="working",
        visibility="private",
        metadata_json={},
        primary_study_id=primary_study_id,
        created_by=owner.id,
    )
    version = DatasetVersion(
        id=uuid4(),
        dataset_asset_id=asset.id,
        version_label="working",
        state="unpublished",
        qa_status="not_run",
        storage_uri=f"elys://datasets/{asset.id}/versions/working",
        metadata_json={},
        created_by=owner.id,
    )
    version.dataset_asset = asset
    return asset, version


# ============================================
# SemVer
# ============================================


def test_semver_valid_and_invalid():
    for v in ["1.0.0", "0.0.1", "0.1.0", "99.99.99", "10.20.30"]:
        assert is_valid_semver(v)
    for v in ["1.0", "1", "v1.0.0", "1.0.0-alpha", "1.0.0+build", "01.0.0", "1.00.0", "", "  ", "foo"]:
        assert not is_valid_semver(v)


def test_semver_compare_and_bump():
    assert compare_semver("1.0.0", "1.0.1") == -1
    assert compare_semver("1.1.0", "1.0.99") == 1
    assert compare_semver("2.0.0", "1.99.99") == 1
    assert compare_semver("1.0.0", "1.0.0") == 0
    v = parse_semver("1.2.3")
    assert str(v.bump_major()) == "2.0.0"
    assert str(v.bump_minor()) == "1.3.0"
    assert str(v.bump_patch()) == "1.2.4"


def test_ensure_strictly_newer():
    ensure_strictly_newer(previous_label="1.0.0", new_label="1.0.1")
    ensure_strictly_newer(previous_label="0.9.9", new_label="1.0.0")
    for prev, new in [("1.0.0", "1.0.0"), ("2.0.0", "1.99.99"), ("1.0.0", "0.99.99")]:
        try:
            ensure_strictly_newer(previous_label=prev, new_label=new)
            raise AssertionError(f"should reject {prev} -> {new}")
        except SemVerError:
            pass


# ============================================
# Publish
# ============================================


def _patch_publish_queries(monkeypatch, *, latest_published=None, conflicting=None):
    """绕过 _latest_published_version_label + 冲突检查 中的复杂 query。"""
    monkeypatch.setattr(
        dataset_lifecycle,
        "_latest_published_version_label",
        lambda db, *, asset: latest_published,
    )
    # 冲突检查用 db.query().filter().first(),把 query 替换为返回固定结果
    class _StubQuery:
        def filter(self, *a, **k):
            return self

        def first(self):
            return conflicting

        def all(self):
            return []

    orig_query = FakeDb.query

    def stub_query(self, model):
        if model is DatasetVersion:
            # publish 内部对 DatasetVersion 只有冲突检查这一处 query, 用 stub 返回固定值
            return _StubQuery()
        return orig_query(self, model)

    monkeypatch.setattr(FakeDb, "query", stub_query)


def test_publish_draft_to_published_succeeds(monkeypatch):
    owner = FakeUser()
    asset, version = make_draft_asset_and_version(owner=owner)
    db = FakeDb()
    db.added.extend([asset, version])
    _patch_publish_queries(monkeypatch, latest_published=None, conflicting=None)

    result = dataset_lifecycle.publish_dataset_version(
        db,
        version=version,
        new_version_label="1.0.0",
        actor=owner,
        deidentified_confirmed=True,
        ethics_statement="已通过伦理审查",
        license_statement="CC-BY-4.0",
        commit=True,
    )

    assert result.dataset_version.state == "published"
    assert result.dataset_version.version_label == "1.0.0"
    assert result.dataset_version.published_by == owner.id
    assert result.dataset_version.published_at is not None
    assert result.dataset_version.version_doi == f"elys:dataset/{asset.id}/v1.0.0"
    assert asset.current_version_id == version.id
    assert asset.concept_doi == f"elys:dataset/{asset.id}"
    assert result.is_first_published_version is True
    assert result.previous_version_label == "working"
    assert db.committed is True
    audit_events = [a for a in db.added if isinstance(a, AuditEvent)]
    assert any(e.action == "dataset_version.published" for e in audit_events)


def test_publish_rejects_non_increasing_version(monkeypatch):
    """已有 published 1.5.0 时, 新发 1.4.9 应被拒绝。"""
    owner = FakeUser()
    asset, version = make_draft_asset_and_version(owner=owner)
    db = FakeDb()
    db.added.extend([asset, version])
    _patch_publish_queries(monkeypatch, latest_published="1.5.0", conflicting=None)

    try:
        dataset_lifecycle.publish_dataset_version(
            db,
            version=version,
            new_version_label="1.4.9",
            actor=owner,
            deidentified_confirmed=True,
            ethics_statement="已通过伦理审查",
            license_statement="CC-BY-4.0",
            commit=False,
        )
        raise AssertionError("should reject non-increasing version")
    except DatasetLifecycleValidationError as exc:
        assert "1.5.0" in str(exc)


def test_publish_rejects_duplicate_version_label(monkeypatch):
    """同 Asset 下版本号必须唯一。"""
    owner = FakeUser()
    asset, version = make_draft_asset_and_version(owner=owner)
    db = FakeDb()
    db.added.extend([asset, version])
    # 模拟"已存在 1.0.0 版本" — stub 让 conflict query 返回非空
    conflict = DatasetVersion(id=uuid4(), dataset_asset_id=asset.id, version_label="1.0.0", state="published")
    _patch_publish_queries(monkeypatch, latest_published=None, conflicting=conflict)

    try:
        dataset_lifecycle.publish_dataset_version(
            db,
            version=version,
            new_version_label="1.0.0",
            actor=owner,
            deidentified_confirmed=True,
            ethics_statement="已通过伦理审查",
            license_statement="CC-BY-4.0",
            commit=False,
        )
        raise AssertionError("should reject duplicate")
    except DatasetLifecycleValidationError as exc:
        assert "1.0.0" in str(exc)


def test_publish_rejects_non_draft():
    owner = FakeUser()
    asset, version = make_draft_asset_and_version(owner=owner)
    version.state = "published"
    db = FakeDb()
    db.added.extend([asset, version])

    try:
        dataset_lifecycle.publish_dataset_version(
            db,
            version=version,
            new_version_label="1.0.0",
            actor=owner,
            deidentified_confirmed=True,
            ethics_statement="已通过伦理审查",
            license_statement="CC-BY-4.0",
            commit=False,
        )
        raise AssertionError("should reject")
    except DatasetLifecycleStateError as exc:
        assert "未发布" in str(exc)


def test_publish_rejects_invalid_semver():
    owner = FakeUser()
    asset, version = make_draft_asset_and_version(owner=owner)
    db = FakeDb()
    db.added.extend([asset, version])

    for bad in ["1.0", "v1.0.0", "1.0.0-alpha", "01.0.0", "foo", ""]:
        try:
            dataset_lifecycle.publish_dataset_version(
                db,
                version=version,
                new_version_label=bad,
                actor=owner,
                deidentified_confirmed=True,
                ethics_statement="已通过伦理审查",
                license_statement="CC-BY-4.0",
                commit=False,
            )
            raise AssertionError(f"should reject {bad!r}")
        except DatasetLifecycleValidationError:
            pass


def test_publish_rejects_non_owner():
    owner = FakeUser()
    other = FakeUser()
    asset, version = make_draft_asset_and_version(owner=owner)
    db = FakeDb()
    db.added.extend([asset, version])

    try:
        dataset_lifecycle.publish_dataset_version(
            db,
            version=version,
            new_version_label="1.0.0",
            actor=other,
            deidentified_confirmed=True,
            ethics_statement="已通过伦理审查",
            license_statement="CC-BY-4.0",
            commit=False,
        )
        raise AssertionError("should reject")
    except DatasetLifecyclePermissionError:
        pass


def test_publish_rejects_admin_non_owner(monkeypatch):
    """发布权限收紧为仅负责人：管理员（非 owner）发布他人资产应被拒。"""
    owner = FakeUser()
    admin = FakeUser(roles=("admin",))
    asset, version = make_draft_asset_and_version(owner=owner)
    db = FakeDb()
    db.added.extend([asset, version])
    _patch_publish_queries(monkeypatch, latest_published=None, conflicting=None)

    try:
        dataset_lifecycle.publish_dataset_version(
            db,
            version=version,
            new_version_label="1.0.0",
            actor=admin,
            deidentified_confirmed=True,
            ethics_statement="已通过伦理审查",
            license_statement="CC-BY-4.0",
            commit=False,
        )
        raise AssertionError("admin (non-owner) should be rejected, only owner can publish")
    except DatasetLifecyclePermissionError:
        pass


# ============================================
# Withdraw request
# ============================================


def test_withdraw_request_published_succeeds():
    owner = FakeUser()
    asset, version = make_draft_asset_and_version(owner=owner)
    version.state = "published"
    version.version_label = "1.0.0"
    db = FakeDb()
    db.added.extend([asset, version])

    req = dataset_lifecycle.request_version_withdrawal(
        db, version=version, reason="数据泄露,需撤回", actor=owner, commit=True
    )
    assert version.state == "withdraw_requested"
    assert version.withdraw_reason == "数据泄露,需撤回"
    assert version.withdraw_requested_by == owner.id
    assert req.reason == "数据泄露,需撤回"
    assert req.requested_by == owner.id
    assert req.decision is None
    audit = [a for a in db.added if isinstance(a, AuditEvent)]
    assert any(e.action == "dataset_version.withdraw_requested" for e in audit)


def test_withdraw_request_rejects_non_published():
    owner = FakeUser()
    asset, version = make_draft_asset_and_version(owner=owner)
    # state 还是 unpublished
    db = FakeDb()
    db.added.extend([asset, version])

    try:
        dataset_lifecycle.request_version_withdrawal(
            db, version=version, reason="x", actor=owner, commit=False
        )
        raise AssertionError("should reject")
    except DatasetLifecycleStateError:
        pass


def test_withdraw_request_rejects_empty_reason():
    owner = FakeUser()
    asset, version = make_draft_asset_and_version(owner=owner)
    version.state = "published"
    db = FakeDb()
    db.added.extend([asset, version])

    for bad in ["", "   ", None]:
        try:
            dataset_lifecycle.request_version_withdrawal(
                db, version=version, reason=bad, actor=owner, commit=False
            )
            raise AssertionError(f"should reject {bad!r}")
        except DatasetLifecycleValidationError:
            pass


# ============================================
# Emergency takedown
# ============================================


def test_emergency_takedown_admin_can_takedown():
    owner = FakeUser()
    admin = FakeUser(roles=("admin",))
    asset, version = make_draft_asset_and_version(owner=owner)
    version.state = "published"
    version.version_label = "1.0.0"
    db = FakeDb()
    db.added.extend([asset, version])

    req = dataset_lifecycle.emergency_takedown_version(
        db, version=version, reason="PII 泄露", actor=admin, commit=True
    )
    assert version.state == "withdrawn"
    assert version.withdrawn_by == admin.id
    assert req.decision == "emergency"
    assert req.reviewed_by == admin.id
    audit = [a for a in db.added if isinstance(a, AuditEvent)]
    assert any(e.action == "dataset_version.emergency_takedown" for e in audit)


def test_emergency_takedown_rejects_non_admin():
    # superadmin 另作平台治理，不参与数据集生命周期（3-25 §6.4），同样应被拒
    owner = FakeUser()
    super_admin = FakeUser(roles=("superadmin",))
    asset, version = make_draft_asset_and_version(owner=owner)
    version.state = "published"
    db = FakeDb()
    db.added.extend([asset, version])

    for actor in (owner, super_admin):
        try:
            dataset_lifecycle.emergency_takedown_version(
                db, version=version, reason="x", actor=actor, commit=False
            )
            raise AssertionError("only admin can emergency-takedown")
        except DatasetLifecyclePermissionError:
            pass


def test_emergency_takedown_requires_reason():
    admin = FakeUser(roles=("admin",))
    asset, version = make_draft_asset_and_version(owner=admin)
    version.state = "published"
    db = FakeDb()
    db.added.extend([asset, version])

    try:
        dataset_lifecycle.emergency_takedown_version(
            db, version=version, reason="", actor=admin, commit=False
        )
        raise AssertionError("should reject empty reason")
    except DatasetLifecycleValidationError:
        pass
