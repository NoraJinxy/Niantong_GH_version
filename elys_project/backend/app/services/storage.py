"""
Purpose: Resolve ELYS storage URIs to safe local filesystem paths.
Related: app/config.py, app/routers/datasets.py, app/pipeline/artifacts.py, docs_v2/4-00.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
import shutil
from typing import Callable
from urllib.parse import unquote, urlparse

from app.config import Settings, get_settings


StudyRootResolver = Callable[[str], str | Path | None]


class StorageUriError(ValueError):
    """Raised when a storage URI cannot be safely resolved."""


@dataclass(frozen=True)
class StorageReference:
    uri: str
    scheme: str
    namespace: str
    root: Path
    path: Path
    relative_path: str
    study_id: str | None = None
    dataset_asset_id: str | None = None
    dataset_version: str | None = None


class StorageService:
    """Compatibility resolver for old study roots and new Dataset/Study roots."""

    def __init__(
        self,
        settings: Settings | None = None,
        study_root_resolver: StudyRootResolver | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.study_root_resolver = study_root_resolver

    def resolve_uri(
        self,
        uri: str,
        *,
        study_root: str | Path | None = None,
    ) -> StorageReference:
        parsed = urlparse((uri or "").strip())
        if not parsed.scheme:
            raise StorageUriError("Storage URI must include a scheme.")

        if parsed.scheme == "study":
            return self._resolve_legacy_study_uri(uri, parsed, study_root=study_root)
        if parsed.scheme == "elys" and parsed.netloc == "datasets":
            return self._resolve_dataset_uri(uri, parsed)
        if parsed.scheme == "elys" and parsed.netloc == "studies":
            return self._resolve_study_uri(uri, parsed)

        raise StorageUriError(f"Unsupported storage URI: {uri}")

    def resolve_path(
        self,
        value: str | Path,
        *,
        study_id: str | None = None,
        study_root: str | Path | None = None,
    ) -> Path:
        """Resolve a URI, absolute path, or legacy study-relative path for reads."""

        text = str(value or "").strip()
        if not text:
            raise StorageUriError("Path reference is empty.")

        parsed = urlparse(text)
        if parsed.scheme in {"study", "elys"}:
            return self.resolve_uri(text, study_root=study_root).path

        path = Path(text).expanduser()
        if path.is_absolute():
            return path.resolve(strict=False)

        if study_root is None and study_id:
            study_root = self.legacy_study_root(study_id)
        if study_root is None:
            raise StorageUriError("Relative paths require study_id or study_root.")

        parts = _safe_logical_parts(text)
        return _safe_join(Path(study_root), parts)

    def legacy_study_root(self, study_id: str) -> Path:
        """Resolve legacy study storage root under STUDIES_DIR (physical dir name kept)."""
        identifier = _safe_identifier(study_id, "study_id")
        if self.study_root_resolver is not None:
            resolved = self.study_root_resolver(identifier)
            if resolved:
                return Path(resolved).expanduser().resolve(strict=False)
        return _safe_join(Path(self.settings.STUDIES_DIR), [identifier])

    def dataset_asset_root(self, dataset_asset_id: str) -> Path:
        # 2026-06-10 两层目录重构：URI 不再含 versions/{label} 段。
        # asset 根下直接是 sourcedata/（asset 级共享）、BIDSdata/（working FIF）、ver{label}/（发布快照）。
        dataset_id = _safe_identifier(dataset_asset_id, "dataset_asset_id")
        return _safe_join(Path(self.settings.DATASETS_STORAGE_ROOT), [dataset_id])

    def study_root(self, study_id: str) -> Path:
        identifier = _safe_identifier(study_id, "study_id")
        return _safe_join(Path(self.settings.STUDIES_STORAGE_ROOT), [identifier])

    # ===== 字节读写后端（local / oss）—— OSS 迁移 A 阶段 (OSS-1) =====
    # 逻辑身份永远是 elys:// URI；物理后端由 settings.STORAGE_BACKEND 决定。
    #   local：直接读写 URI 解析出的本地 Path（与历史行为完全一致）。
    #   oss  ：URI → 对象 key，下载到 scratch 供 MNE 读 / 把产物上传回桶。
    # 这些方法为 OSS-5/6 接线预备；STORAGE_BACKEND=local 时全部走本地分支，零行为变化。

    @property
    def backend(self) -> str:
        return (self.settings.STORAGE_BACKEND or "local").strip().lower()

    def oss_key_for_reference(self, ref: "StorageReference") -> str:
        """elys:// URI → OSS 对象 key：{prefix}{namespace}/{id}/{relative_path}。
        legacy study:// 与新 elys://studies/ 同为 namespace='studies' 却映射到不同本地根
        (STUDIES_DIR vs STUDIES_STORAGE_ROOT)——key 也必须区分，否则 OSS 上两者会互相覆盖。"""
        ident = ref.dataset_asset_id or ref.study_id or ""
        namespace = "legacy-studies" if ref.scheme == "study" else ref.namespace
        key = "/".join(p for p in (namespace, ident, ref.relative_path) if p)
        prefix = (self.settings.OSS_PREFIX or "").strip().strip("/")
        return f"{prefix}/{key}" if prefix else key

    def oss_key(self, uri: str | Path, *, study_root: str | Path | None = None) -> str:
        return self.oss_key_for_reference(self.resolve_uri(str(uri), study_root=study_root))

    def _oss_bucket(self):
        bucket = getattr(self, "_oss_bucket_cache", None)
        if bucket is not None:
            return bucket
        endpoint = (self.settings.OSS_ENDPOINT or "").strip()
        name = (self.settings.OSS_BUCKET or "").strip()
        ak = (self.settings.OSS_ACCESS_KEY_ID or "").strip()
        sk = (self.settings.OSS_ACCESS_KEY_SECRET or "").strip()
        if not endpoint or not name:
            raise StorageUriError("OSS backend requires OSS_ENDPOINT and OSS_BUCKET.")
        if not ak or not sk:
            raise StorageUriError("OSS backend requires OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET (inject via env).")
        try:
            import oss2  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - 部署装了 oss2 才会走 oss 后端
            raise StorageUriError("oss2 is not installed; add oss2 to backend requirements.") from exc
        ep = endpoint if endpoint.startswith(("http://", "https://")) else f"https://{endpoint}"
        bucket = oss2.Bucket(oss2.Auth(ak, sk), ep, name)
        self._oss_bucket_cache = bucket
        return bucket

    def _scratch_path(self, key: str) -> Path:
        root = Path(self.settings.OSS_SCRATCH_ROOT).expanduser()
        return _safe_join(root, _safe_logical_parts(key))

    def materialize(
        self,
        uri: str | Path,
        *,
        study_id: str | None = None,
        study_root: str | Path | None = None,
        refresh: bool = False,
    ) -> Path:
        """返回一个本地可读文件路径（供 MNE 等需要真实路径的库使用）。local：直接解析；oss：下载对象到 scratch。
        缓存复用仅限 content-addressed key（study 产物 outputs/{sha}/…，内容变 key 就变 → 复用安全）；
        可变 key（dataset BIDS 同四元组覆盖，key 不变内容变）每次重下，否则会读到 scratch 里的旧字节。"""
        if self.backend != "oss":
            return self.resolve_path(uri, study_id=study_id, study_root=study_root)
        key = self.oss_key(uri, study_root=study_root)
        local = self._scratch_path(key)
        cacheable = _is_content_addressed_key(key)
        if refresh or not cacheable or not local.exists():
            local.parent.mkdir(parents=True, exist_ok=True)
            self._oss_bucket().get_object_to_file(key, str(local))
        return local

    def persist(
        self,
        local_path: str | Path,
        uri: str | Path,
        *,
        study_id: str | None = None,
        study_root: str | Path | None = None,
    ) -> None:
        """把本地产物写进存储。local：移动到解析路径；oss：上传到对象 key。"""
        local_path = Path(local_path)
        if self.backend != "oss":
            target = self.resolve_path(uri, study_id=study_id, study_root=study_root)
            if local_path.resolve() == target.resolve():
                return
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(local_path), str(target))
            return
        self._oss_bucket().put_object_from_file(self.oss_key(uri, study_root=study_root), str(local_path))

    def exists(self, uri: str | Path, *, study_id: str | None = None, study_root: str | Path | None = None) -> bool:
        if self.backend != "oss":
            try:
                return self.resolve_path(uri, study_id=study_id, study_root=study_root).exists()
            except (StorageUriError, ValueError):
                return False
        try:
            key = self.oss_key(uri, study_root=study_root)
        except (StorageUriError, ValueError):
            return False
        return self._oss_bucket().object_exists(key)

    def read_bytes(self, uri: str | Path, *, study_id: str | None = None, study_root: str | Path | None = None) -> bytes:
        if self.backend != "oss":
            return self.resolve_path(uri, study_id=study_id, study_root=study_root).read_bytes()
        return self._oss_bucket().get_object(self.oss_key(uri, study_root=study_root)).read()

    def write_bytes(
        self,
        uri: str | Path,
        data: bytes,
        *,
        study_id: str | None = None,
        study_root: str | Path | None = None,
    ) -> None:
        if self.backend != "oss":
            target = self.resolve_path(uri, study_id=study_id, study_root=study_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            return
        self._oss_bucket().put_object(self.oss_key(uri, study_root=study_root), data)

    def delete(self, uri: str | Path, *, study_id: str | None = None, study_root: str | Path | None = None) -> None:
        if self.backend != "oss":
            try:
                path = self.resolve_path(uri, study_id=study_id, study_root=study_root)
            except (StorageUriError, ValueError):
                return
            if path.exists():
                path.unlink()
            return
        try:
            key = self.oss_key(uri, study_root=study_root)
        except (StorageUriError, ValueError):
            return
        self._oss_bucket().delete_object(key)

    def _resolve_legacy_study_uri(
        self,
        uri: str,
        parsed,
        *,
        study_root: str | Path | None,
    ) -> StorageReference:
        """Resolve legacy study:// URI scheme (kept for backward compat with stored URIs)."""
        study_id = _safe_identifier(parsed.netloc, "study_id")
        root = Path(study_root).expanduser().resolve(strict=False) if study_root else self.legacy_study_root(study_id)
        relative_path = _uri_path_to_relative(parsed.path)
        parts = _safe_logical_parts(relative_path) if relative_path else []
        path = _safe_join(root, parts)
        return StorageReference(
            uri=uri,
            scheme="study",
            namespace="studies",
            root=root,
            path=path,
            relative_path=relative_path,
            study_id=study_id,
        )

    def _resolve_dataset_uri(self, uri: str, parsed) -> StorageReference:
        # 新方案：elys://datasets/{dataset_asset_id}/{logical_path}
        # logical_path 形如 sourcedata/original_uploads/... 或 BIDSdata/sub-/ses-/eeg/... 或 ver{label}/...
        parts = _safe_logical_parts(_uri_path_to_relative(parsed.path))
        if len(parts) < 1:
            raise StorageUriError("Dataset URI must be elys://datasets/{dataset_asset_id}/{path}.")

        dataset_asset_id = _safe_identifier(parts[0], "dataset_asset_id")
        logical_parts = parts[1:]
        root = self.dataset_asset_root(dataset_asset_id)
        path = _safe_join(root, logical_parts)
        return StorageReference(
            uri=uri,
            scheme="elys",
            namespace="datasets",
            root=root,
            path=path,
            relative_path="/".join(logical_parts),
            dataset_asset_id=dataset_asset_id,
            dataset_version=None,
        )

    def _resolve_study_uri(self, uri: str, parsed) -> StorageReference:
        parts = _safe_logical_parts(_uri_path_to_relative(parsed.path))
        if not parts:
            raise StorageUriError("Study URI must be elys://studies/{study_id}/{path}.")

        study_id = _safe_identifier(parts[0], "study_id")
        logical_parts = parts[1:]
        root = self.study_root(study_id)
        path = _safe_join(root, logical_parts)
        return StorageReference(
            uri=uri,
            scheme="elys",
            namespace="studies",
            root=root,
            path=path,
            relative_path="/".join(logical_parts),
            study_id=study_id,
        )


def _uri_path_to_relative(path: str) -> str:
    text = unquote(path or "").replace("\\", "/")
    return text.lstrip("/")


def _safe_identifier(value: str | None, field_name: str) -> str:
    text = unquote(str(value or "").strip())
    if not text:
        raise StorageUriError(f"{field_name} is required.")
    if text in {".", ".."} or "/" in text or "\\" in text:
        raise StorageUriError(f"{field_name} contains unsafe path characters.")
    if re.fullmatch(r"[A-Za-z]:.*", text):
        raise StorageUriError(f"{field_name} must not be a drive path.")
    return text


def _safe_logical_parts(relative_path: str) -> list[str]:
    normalized = _uri_path_to_relative(relative_path)
    if not normalized:
        return []
    parts = []
    for part in PurePosixPath(normalized).parts:
        if part in {"", "."}:
            continue
        if part == ".." or "\\" in part or re.fullmatch(r"[A-Za-z]:.*", part):
            raise StorageUriError("Storage path escapes its root.")
        parts.append(part)
    return parts


def _safe_join(root: Path, parts: list[str]) -> Path:
    resolved_root = root.expanduser().resolve(strict=False)
    target = resolved_root.joinpath(*parts).resolve(strict=False)
    try:
        target.relative_to(resolved_root)
    except ValueError as exc:
        raise StorageUriError("Resolved path escapes its storage root.") from exc
    return target


_SHA256_SEGMENT_RE = re.compile(r"^[0-9a-f]{64}$")


def _is_content_addressed_key(key: str) -> bool:
    """key 含 64 位 hex 段（=sha256 内容寻址，如 studies/{id}/outputs/ab/<sha>/…）即视为不可变、可缓存。
    dataset BIDS 文件（datasets/{asset}/BIDSdata/sub-…）无此段 → 可变 → 不缓存、每次重下。"""
    return any(_SHA256_SEGMENT_RE.match(seg) for seg in str(key).split("/"))
