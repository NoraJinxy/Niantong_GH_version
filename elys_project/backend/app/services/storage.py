"""
Purpose: Resolve ELYS storage URIs to safe local filesystem paths.
Related: app/config.py, app/routers/datasets.py, app/pipeline/artifacts.py, docs_v2/4-00.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
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
