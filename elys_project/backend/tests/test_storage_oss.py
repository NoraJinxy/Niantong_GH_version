"""
Purpose: Unit tests for the StorageService OSS byte-backend — key mapping + local round-trip.
Related: app/services/storage.py (OSS migration phase A), app/engine/io.py materialize_reference.

只测离线可测的部分：① OSS key 映射（含 legacy/新 study 不撞车的回归）；② local 后端字节读写往返
与幂等。OSS 后端的真实读写由 elys_scripts/oss_smoke 冒烟 + 未来端到端覆盖（需网络/凭证，不在单测）。
"""
from __future__ import annotations

from app.config import Settings
from app.services.storage import StorageService


def _svc(**overrides) -> StorageService:
    base = {"STORAGE_BACKEND": "local"}
    base.update(overrides)
    return StorageService(settings=Settings(**base))


def test_oss_key_disambiguates_legacy_and_new_studies():
    svc = _svc(
        STORAGE_BACKEND="oss", OSS_ENDPOINT="e", OSS_BUCKET="b",
        OSS_ACCESS_KEY_ID="x", OSS_ACCESS_KEY_SECRET="y",
    )
    dataset_key = svc.oss_key("elys://datasets/ds1/sub-01/eeg/x_raw.fif")
    new_study_key = svc.oss_key("elys://studies/202605000001/derivatives/x.fif")
    legacy_study_key = svc.oss_key("study://202605000001/derivatives/x.fif")
    assert dataset_key == "datasets/ds1/sub-01/eeg/x_raw.fif"
    assert new_study_key == "studies/202605000001/derivatives/x.fif"
    assert legacy_study_key == "legacy-studies/202605000001/derivatives/x.fif"
    # 关键回归：legacy study:// 与新 elys://studies/ 绝不能算出同一个 OSS key
    assert new_study_key != legacy_study_key


def test_oss_key_prefix_applied():
    svc = _svc(
        STORAGE_BACKEND="oss", OSS_ENDPOINT="e", OSS_BUCKET="b",
        OSS_ACCESS_KEY_ID="x", OSS_ACCESS_KEY_SECRET="y", OSS_PREFIX="env1/",
    )
    assert svc.oss_key("elys://datasets/ds1/x.fif") == "env1/datasets/ds1/x.fif"


def test_local_byte_roundtrip(tmp_path):
    svc = _svc(DATASETS_STORAGE_ROOT=str(tmp_path / "datasets"))
    uri = "elys://datasets/ds1/sub-01/eeg/probe.bin"
    assert svc.exists(uri) is False
    svc.write_bytes(uri, b"hello-oss")
    assert svc.exists(uri) is True
    assert svc.read_bytes(uri) == b"hello-oss"
    # local 后端 materialize 直接返回真实路径
    assert svc.materialize(uri).read_bytes() == b"hello-oss"
    svc.delete(uri)
    assert svc.exists(uri) is False


def test_local_persist_moves_file(tmp_path):
    svc = _svc(DATASETS_STORAGE_ROOT=str(tmp_path / "datasets"))
    src = tmp_path / "scratch_out.bin"
    src.write_bytes(b"persist-me")
    uri = "elys://datasets/ds1/derivatives/out.bin"
    svc.persist(src, uri)
    assert svc.read_bytes(uri) == b"persist-me"
    assert not src.exists()  # persist 是 move，不是 copy


def test_delete_and_exists_idempotent_on_bad_input(tmp_path):
    svc = _svc(DATASETS_STORAGE_ROOT=str(tmp_path / "datasets"))
    # 无法解析的输入：exists 返回 False、delete 静默不抛（local/oss 两后端语义须一致）
    assert svc.exists("") is False
    svc.delete("")
    assert svc.exists("not-a-uri-no-scheme") is False


def test_content_addressed_key_detection():
    """缓存复用只认 content-addressed key：study 产物(含 sha256 段)可缓存；dataset 可变 key 不缓存。
    回归：dataset BIDS 同四元组重传覆盖同 key 但内容变，若误判可缓存会读到 scratch 旧字节。"""
    from app.services.storage import _is_content_addressed_key

    sha = "a" * 64
    assert _is_content_addressed_key(f"studies/123/outputs/aa/{sha}/x-epo.fif") is True
    assert _is_content_addressed_key("datasets/ds1/BIDSdata/sub-01/eeg/sub-01_task-x_eeg.fif") is False
    assert _is_content_addressed_key("datasets/ds1/sourcedata/original_uploads/upload-001/files/a.edf") is False
    assert _is_content_addressed_key("legacy-studies/202605000001/derivatives/x.fif") is False
