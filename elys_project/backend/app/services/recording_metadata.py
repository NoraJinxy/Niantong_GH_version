"""
Purpose: Lightweight readers for recording-level EEG metadata used by dataset management.
Related: app/routers/dataset_recordings.py, app/pipeline/load_data.py, docs_v2/4-00.
"""

from __future__ import annotations

from collections import Counter
from csv import DictReader
from io import StringIO
from pathlib import Path
from typing import Any

from app.engine.analysis.event_conditions import normalize_marker_label
from app.models import Recording, Study
from app.services.storage import StorageService, StorageUriError


EVENT_LABEL_COLUMNS = ("trial_type", "value", "type", "marker", "label")
EVENT_LABEL_MAX_PER_RECORDING = 128
EVENT_LABEL_MAX_LENGTH = 120


def read_recording_channel_names(study: Study, recording: Recording) -> list[str]:
    """Return channel names from current channels.tsv, falling back to FIF header."""

    sidecar_paths = _current_sidecar_paths(recording)
    names = _read_channel_names_from_tsv(study, sidecar_paths.get("channels"))
    if names:
        return names
    return _read_channel_names_from_fif(study, _current_fif_reference(recording))


def read_recording_event_counts(study: Study, recording: Recording) -> tuple[list[str], dict[str, int]]:
    """Return sorted event labels and per-label counts from current events.tsv."""

    sidecar_paths = _current_sidecar_paths(recording)
    rows = _read_tsv_rows(study, sidecar_paths.get("events"))
    if not rows:
        return [], {}
    counts: Counter[str] = Counter()
    for row in rows:
        label = _row_label(row)
        if not label:
            continue
        counts[label[:EVENT_LABEL_MAX_LENGTH]] += 1
        if len(counts) >= EVENT_LABEL_MAX_PER_RECORDING:
            break
    labels = sorted(counts.keys(), key=_naturalish_key)
    return labels, {label: int(counts[label]) for label in labels}


def _current_sidecar_paths(recording: Recording) -> dict[str, str]:
    current_version = getattr(recording, "current_version", None)
    sidecar_paths = getattr(current_version, "sidecar_paths", None) if current_version is not None else None
    if not isinstance(sidecar_paths, dict):
        return {}
    return {str(key): str(value) for key, value in sidecar_paths.items() if value}


def _current_fif_reference(recording: Recording) -> str | None:
    current_version = getattr(recording, "current_version", None)
    fif_path = getattr(current_version, "fif_path", None) if current_version is not None else None
    return str(fif_path or getattr(recording, "fif_path", "") or "") or None


def _read_channel_names_from_tsv(study: Study, path_value: str | None) -> list[str]:
    rows = _read_tsv_rows(study, path_value)
    names: list[str] = []
    for row in rows:
        raw = row.get("name")
        text = str(raw or "").strip()
        if text:
            names.append(text)
    return names


def _read_channel_names_from_fif(study: Study, path_value: str | None) -> list[str]:
    if not path_value:
        return []
    try:
        import mne  # noqa: PLC0415
    except ImportError:
        return []
    try:
        fif_path = StorageService().materialize(path_value, study_id=study.id, study_root=study.data_root)
        if not Path(fif_path).exists():
            return []
        info = mne.io.read_info(str(fif_path), verbose="ERROR")
    except Exception:
        return []
    return _clean_channel_names(_extract_info_channel_names(info))


def _extract_info_channel_names(info: Any) -> list[Any]:
    try:
        chs = info["chs"]
    except Exception:
        chs = getattr(info, "chs", None)
    if chs and isinstance(chs, (list, tuple)):
        names: list[str] = []
        for channel in chs:
            if isinstance(channel, dict):
                names.append(str(channel.get("ch_name") or "").strip())
            else:
                names.append(str(getattr(channel, "ch_name", "") or "").strip())
        if any(names):
            return names
    try:
        return list(getattr(info, "ch_names", []) or [])
    except Exception:
        return []


def _clean_channel_names(values: list[Any]) -> list[str]:
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text:
            out.append(text)
    return out


def _read_tsv_rows(study: Study, path_value: str | None) -> list[dict[str, str]]:
    if not path_value:
        return []
    try:
        content = StorageService().read_bytes(path_value, study_id=study.id, study_root=study.data_root).decode("utf-8-sig")
    except (OSError, UnicodeDecodeError, StorageUriError, ValueError):
        return []
    try:
        return list(DictReader(StringIO(content), delimiter="\t"))
    except Exception:
        return []


def _row_label(row: dict[str, Any]) -> str:
    for column in EVENT_LABEL_COLUMNS:
        raw = row.get(column)
        text = str(raw or "").strip()
        if not text or text in {"n/a", "N/A"}:
            continue
        return normalize_marker_label(text)
    return ""


def _naturalish_key(value: str) -> tuple[str, int, str]:
    prefix, _, tail = value.rpartition(" ")
    if tail.isdigit():
        return (prefix, int(tail), value)
    return (value, -1, value)
