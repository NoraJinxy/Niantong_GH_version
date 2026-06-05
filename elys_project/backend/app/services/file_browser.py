"""
Purpose: Resolve, describe, preview, and tree-index Dataset files without exposing server paths.
Related: app/routers/datasets.py, app/services/storage.py, docs_v2/4-40.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

from app.services.storage import StorageService, StorageUriError


DATASET_FILE_PREVIEW_VERSION = "dataset-file-preview-v1"
TEXT_PREVIEW_EXTENSIONS = {".txt", ".md", ".json", ".tsv", ".csv", ".log"}
FIF_EXTENSIONS = {".fif", ".fif.gz"}


class FileAccessError(Exception):
    def __init__(self, code: str, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def resolve_dataset_file_path(file_record: Any, *, study: Any | None = None) -> Path:
    storage_uri = str(getattr(file_record, "storage_uri", "") or "").strip()
    study_id = str(getattr(file_record, "study_id", "") or getattr(study, "id", "") or "")
    study_root = getattr(study, "data_root", None) if study is not None else None

    if storage_uri:
        try:
            return StorageService().resolve_path(storage_uri, study_id=study_id, study_root=study_root)
        except (StorageUriError, ValueError):
            pass

    relative_path = str(getattr(file_record, "relative_path", "") or "").strip()
    if relative_path:
        try:
            return StorageService().resolve_path(relative_path, study_id=study_id, study_root=study_root)
        except (StorageUriError, ValueError):
            pass

    raise FileAccessError(
        "DATASET_FILE_PATH_UNRESOLVED",
        "Dataset file has no resolvable storage_uri or relative_path.",
        status_code=422,
    )


def dataset_file_metadata(file_record: Any, *, study: Any | None = None) -> dict[str, Any]:
    path = _try_resolve_path(file_record, study=study)
    exists = bool(path and path.exists())
    logical_path = _logical_path(file_record)
    extension = _extension_for_path(logical_path)
    return {
        "id": _string_or_none(getattr(file_record, "id", None)) or "",
        "study_id": str(getattr(file_record, "study_id", "") or ""),
        "dataset_id": _string_or_none(getattr(file_record, "recording_id", None)) or "",
        "dataset_upload_id": _string_or_none(getattr(file_record, "recording_version_id", None)) or "",
        "dataset_version_id": _string_or_none(getattr(file_record, "dataset_version_id", None)),
        "file_role": str(getattr(file_record, "file_role", "") or ""),
        "storage_uri": str(getattr(file_record, "storage_uri", "") or ""),
        "relative_path": str(getattr(file_record, "relative_path", "") or ""),
        "logical_path": getattr(file_record, "logical_path", None),
        "file_name": PurePosixPath(logical_path).name if logical_path else download_filename(file_record),
        "extension": extension,
        "file_size": getattr(file_record, "file_size", None),
        "sha256": getattr(file_record, "sha256", None),
        "mime_type": getattr(file_record, "mime_type", None),
        "metadata_json": _jsonable(getattr(file_record, "metadata_json", None) or {}),
        "exists": exists,
        "preview_supported": _preview_supported(file_record, extension),
        "download_name": download_filename(file_record),
        "created_by": _string_or_none(getattr(file_record, "created_by", None)),
        "created_at": _iso_or_none(getattr(file_record, "created_at", None)),
    }


def dataset_file_preview(file_record: Any, *, study: Any | None = None, max_bytes: int = 8192) -> dict[str, Any]:
    path = resolve_dataset_file_path(file_record, study=study)
    if not path.exists():
        raise FileAccessError("DATASET_FILE_MISSING", "Dataset file does not exist.", status_code=404)
    if not path.is_file():
        raise FileAccessError("DATASET_FILE_PREVIEW_DIRECTORY_UNSUPPORTED", "Directory preview is not supported.", status_code=409)

    metadata = dataset_file_metadata(file_record, study=study)
    extension = str(metadata.get("extension") or "").lower()
    preview_json: dict[str, Any]

    if extension == ".json":
        preview_json = _preview_json(path, max_bytes=max_bytes)
    elif extension in {".tsv", ".csv"}:
        preview_json = _preview_table(path, max_bytes=max_bytes, delimiter="\t" if extension == ".tsv" else ",")
    elif extension in {".txt", ".md", ".log"}:
        preview_json = _preview_text(path, max_bytes=max_bytes)
    elif extension in FIF_EXTENSIONS or str(getattr(file_record, "file_role", "") or "") == "canonical_fif":
        preview_json = _preview_fif(path)
    elif isinstance(getattr(file_record, "metadata_json", None), dict) and getattr(file_record, "metadata_json"):
        preview_json = {
            "_preview_version": DATASET_FILE_PREVIEW_VERSION,
            "preview_kind": "metadata",
            "preview_source": "dataset_file.metadata_json",
            "summary": _jsonable(getattr(file_record, "metadata_json")),
        }
    else:
        raise FileAccessError(
            "DATASET_FILE_PREVIEW_UNSUPPORTED",
            f"Preview is not supported for file extension {extension or 'unknown'}.",
            status_code=400,
        )

    return {
        "file": metadata,
        "preview_json": preview_json,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def build_dataset_file_tree(files: list[Any], *, prefix: str | None = "raw_bids") -> dict[str, Any]:
    root = {"name": prefix or "", "path": prefix or "", "kind": "directory", "children": []}
    prefix_text = _normalize_logical_path(prefix or "")
    for file_record in files:
        logical_path = _normalize_logical_path(_logical_path(file_record))
        if prefix_text:
            if logical_path == prefix_text:
                relative = PurePosixPath(logical_path).name
            elif logical_path.startswith(prefix_text.rstrip("/") + "/"):
                relative = logical_path[len(prefix_text.rstrip("/") + "/") :]
            else:
                continue
        else:
            relative = logical_path
        if not relative:
            continue
        _insert_tree_file(root, relative, file_record, full_path=logical_path)
    _sort_tree(root)
    return root


def download_filename(file_record: Any) -> str:
    for value in (
        getattr(file_record, "logical_path", None),
        getattr(file_record, "relative_path", None),
        _path_from_storage_uri(getattr(file_record, "storage_uri", None)),
    ):
        if value:
            name = PurePosixPath(str(value).replace("\\", "/")).name
            if name:
                return name
    return f"dataset-file-{getattr(file_record, 'id', 'download')}"


def _insert_tree_file(root: dict[str, Any], relative_path: str, file_record: Any, *, full_path: str) -> None:
    parts = [part for part in PurePosixPath(relative_path).parts if part not in {"", "."}]
    if not parts:
        return
    current = root
    current_path = str(root.get("path") or "")
    for part in parts[:-1]:
        current_path = f"{current_path.rstrip('/')}/{part}" if current_path else part
        child = next(
            (
                item
                for item in current["children"]
                if item.get("kind") == "directory" and item.get("name") == part
            ),
            None,
        )
        if child is None:
            child = {"name": part, "path": current_path, "kind": "directory", "children": []}
            current["children"].append(child)
        current = child
    leaf_name = parts[-1]
    current["children"].append(
        {
            "name": leaf_name,
            "path": full_path,
            "kind": "file",
            "file_id": _string_or_none(getattr(file_record, "id", None)),
            "file_role": getattr(file_record, "file_role", None),
            "storage_uri": getattr(file_record, "storage_uri", None),
            "relative_path": getattr(file_record, "relative_path", None),
            "logical_path": getattr(file_record, "logical_path", None),
            "file_size": getattr(file_record, "file_size", None),
            "sha256": getattr(file_record, "sha256", None),
        }
    )


def _sort_tree(node: dict[str, Any]) -> None:
    children = node.get("children")
    if not isinstance(children, list):
        return
    children.sort(key=lambda item: (0 if item.get("kind") == "directory" else 1, str(item.get("name") or "")))
    for child in children:
        _sort_tree(child)


def _try_resolve_path(file_record: Any, *, study: Any | None) -> Path | None:
    try:
        return resolve_dataset_file_path(file_record, study=study)
    except FileAccessError:
        return None


def _logical_path(file_record: Any) -> str:
    return str(
        getattr(file_record, "logical_path", None)
        or getattr(file_record, "relative_path", None)
        or _path_from_storage_uri(getattr(file_record, "storage_uri", None))
        or ""
    ).replace("\\", "/")


def _path_from_storage_uri(uri: str | None) -> str:
    if not uri:
        return ""
    parsed = urlparse(str(uri))
    return parsed.path.lstrip("/")


def _normalize_logical_path(value: str) -> str:
    return str(value or "").replace("\\", "/").strip("/")


def _extension_for_path(path: str) -> str:
    lower = str(path or "").lower()
    if lower.endswith(".fif.gz"):
        return ".fif.gz"
    return PurePosixPath(lower).suffix


def _preview_supported(file_record: Any, extension: str) -> bool:
    return (
        extension in TEXT_PREVIEW_EXTENSIONS
        or extension in FIF_EXTENSIONS
        or str(getattr(file_record, "file_role", "") or "") == "canonical_fif"
        or bool(getattr(file_record, "metadata_json", None))
    )


def _preview_json(path: Path, *, max_bytes: int) -> dict[str, Any]:
    text = _read_text(path, max_bytes=max_bytes)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FileAccessError("DATASET_FILE_JSON_INVALID", f"JSON preview failed: {exc}", status_code=422) from exc
    return {
        "_preview_version": DATASET_FILE_PREVIEW_VERSION,
        "preview_kind": "json",
        "summary": _jsonable(parsed),
        "truncated": path.stat().st_size > max_bytes,
    }


def _preview_table(path: Path, *, max_bytes: int, delimiter: str) -> dict[str, Any]:
    text = _read_text(path, max_bytes=max_bytes)
    rows = [line.split(delimiter) for line in text.splitlines()[:20]]
    header = rows[0] if rows else []
    return {
        "_preview_version": DATASET_FILE_PREVIEW_VERSION,
        "preview_kind": "table",
        "delimiter": delimiter,
        "header": header,
        "rows": rows[1:],
        "row_count_preview": max(0, len(rows) - 1),
        "truncated": path.stat().st_size > max_bytes,
    }


def _preview_text(path: Path, *, max_bytes: int) -> dict[str, Any]:
    text = _read_text(path, max_bytes=max_bytes)
    return {
        "_preview_version": DATASET_FILE_PREVIEW_VERSION,
        "preview_kind": "text",
        "text": text,
        "truncated": path.stat().st_size > max_bytes,
    }


def _preview_fif(path: Path) -> dict[str, Any]:
    try:
        import mne
    except Exception as exc:
        raise FileAccessError("DATASET_FILE_PREVIEW_ENGINE_UNAVAILABLE", f"MNE is required for FIF preview: {exc}", status_code=503) from exc

    try:
        info = mne.io.read_info(path, verbose="ERROR")
    except Exception as exc:
        raise FileAccessError("DATASET_FILE_FIF_PREVIEW_FAILED", str(exc), status_code=422) from exc

    channel_names = list(info.get("ch_names", []))
    return {
        "_preview_version": DATASET_FILE_PREVIEW_VERSION,
        "preview_kind": "fif_info",
        "summary": {
            "sfreq": float(info.get("sfreq") or 0),
            "n_channels": len(channel_names),
            "channel_names_preview": channel_names[:20],
            "bads": list(info.get("bads", [])),
        },
    }


def _read_text(path: Path, *, max_bytes: int) -> str:
    with path.open("rb") as handle:
        payload = handle.read(max_bytes)
    return payload.decode("utf-8", errors="replace")


def _jsonable(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value


def _iso_or_none(value: Any) -> str | None:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value) if value else None


def _string_or_none(value: Any) -> str | None:
    return str(value) if value is not None else None
