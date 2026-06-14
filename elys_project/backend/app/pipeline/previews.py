"""
Purpose: StudyOutput 预览构建 —— 把 raw/epochs/evoked 等 FIF 解析成轻量 JSON preview。
Related: app/routers/pipelines.py, app/pipeline/study_output_store.py, app/pipeline/cache.py, wiki/docs/5-00 and wiki/docs/7-40.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.storage import StorageService, StorageUriError

from .study_output_store import StudyOutputStore


PREVIEW_VERSION = "derived-dataset-preview-v1"
MAX_COUNTER_ITEMS = 20
MAX_EVOKED_CONDITIONS = 8
MAX_EVOKED_CHANNELS = 6
MAX_EVOKED_POINTS = 80


class StudyOutputPreviewError(Exception):
    def __init__(self, code: str, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def build_study_output_preview(
    study: Any,
    derived: Any,
    *,
    sample_channels: int = MAX_EVOKED_CHANNELS,
    sample_points: int = MAX_EVOKED_POINTS,
) -> dict[str, Any]:
    """Build a preview payload from a StudyOutput-like object."""
    data_type = str(getattr(derived, "data_type", "") or "").strip().lower()
    derived_path = resolve_study_output_path(study, derived)
    validate_study_output_file(derived_path, derived)

    if data_type in ("raw", "filtered_raw", "ica_cleaned"):
        preview_json = _preview_raw(derived_path)
    elif data_type == "epochs":
        preview_json = _preview_epochs(derived_path)
    elif data_type == "evoked":
        preview_json = _preview_evoked(derived_path, sample_channels=sample_channels, sample_points=sample_points)
    else:
        cached_preview = getattr(derived, "preview_json", None)
        if isinstance(cached_preview, dict) and cached_preview:
            preview_json = {
                "_preview_version": PREVIEW_VERSION,
                "data_type": data_type or "unknown",
                "summary": cached_preview,
                "preview_source": "study_output.preview_json",
            }
        else:
            raise StudyOutputPreviewError(
                "DERIVED_DATASET_PREVIEW_UNSUPPORTED",
                f"Preview is not supported for data_type={data_type or 'unknown'}",
                status_code=400,
            )

    execution_id = _stringify(getattr(derived, "produced_by_execution_id", None))
    job_id = _stringify(getattr(derived, "produced_by_job_id", None))
    storage_path = (
        getattr(derived, "logical_path", None)
        or getattr(derived, "storage_path", None)
        or ""
    )
    sha256 = getattr(derived, "sha256", None) or getattr(derived, "checksum", None)
    return {
        "study_output_id": _stringify(getattr(derived, "id", None)) or "",
        "study_id": str(getattr(derived, "study_id", getattr(study, "id", ""))),
        "execution_id": execution_id,
        "job_id": job_id,
        "data_type": data_type,
        "storage_path": str(storage_path),
        "storage_uri": getattr(derived, "storage_uri", None),
        "sha256": sha256,
        "keep": bool(getattr(derived, "keep", False)),
        "preview_json": preview_json,
        "observe_route": observe_route_for_data_type(data_type),
        "observe_query": observe_query(study, derived, execution_id=execution_id),
        "generated_at": datetime.utcnow(),
    }


def resolve_study_output_path(study: Any, derived: Any) -> Path:
    storage_uri = str(getattr(derived, "storage_uri", "") or "").strip()
    if storage_uri:
        try:
            return StorageService().resolve_path(
                storage_uri,
                study_id=str(getattr(study, "id", getattr(derived, "study_id", "")) or ""),
                study_root=_study_root_or_none(study),
            )
        except (StorageUriError, ValueError):
            pass

    storage_path = str(
        getattr(derived, "logical_path", None) or getattr(derived, "storage_path", "") or ""
    ).strip()
    if not storage_path:
        raise StudyOutputPreviewError(
            "DERIVED_DATASET_STORAGE_PATH_EMPTY",
            "结果没有可解析的 storage_uri 或 logical_path。",
            status_code=422,
        )
    path = Path(storage_path).expanduser()
    if path.is_absolute():
        return path

    study_root = _study_root(study)
    return study_root / storage_path


def validate_study_output_file(path: Path, derived: Any) -> None:
    if not path.exists():
        raise StudyOutputPreviewError(
            "DERIVED_DATASET_FILE_MISSING",
            f"结果文件不存在: {path}",
            status_code=404,
        )

    expected_checksum = str(
        getattr(derived, "sha256", None)
        or getattr(derived, "checksum", "")
        or ""
    ).strip().lower()
    if not expected_checksum:
        return

    actual_checksum = StudyOutputStore.sha256_directory(path) if path.is_dir() else StudyOutputStore.sha256_file(path)
    if actual_checksum.lower() != expected_checksum:
        raise StudyOutputPreviewError(
            "DERIVED_DATASET_CHECKSUM_MISMATCH",
            "StudyOutput checksum does not match the stored checksum.",
            status_code=409,
        )


def observe_route_for_data_type(data_type: str) -> str:
    normalized = str(data_type or "").lower()
    if normalized == "evoked":
        return "/observe/erp"
    if normalized == "tfr":
        return "/observe/tfr"
    if normalized == "psd":
        return "/observe/psd"
    return "/observe"


def observe_query(study: Any, derived: Any, *, execution_id: str | None = None) -> dict[str, str]:
    query = {
        "studyId": str(getattr(study, "id", getattr(derived, "study_id", ""))),
        "study_output_id": _stringify(getattr(derived, "id", None)) or "",
    }
    if execution_id:
        query["execution_id"] = execution_id
    job_id = _stringify(getattr(derived, "produced_by_job_id", None))
    if job_id:
        query["job_id"] = job_id
    return {key: value for key, value in query.items() if value}


def _preview_raw(path: Path) -> dict[str, Any]:
    mne = _mne()
    raw = mne.io.read_raw_fif(path, preload=False, verbose="ERROR")
    sfreq = float(raw.info["sfreq"])
    n_times = int(raw.n_times)
    annotation_descriptions = [str(item) for item in getattr(raw.annotations, "description", [])]
    return {
        "_preview_version": PREVIEW_VERSION,
        "data_type": "raw",
        "summary": {
            "sfreq": sfreq,
            "n_channels": len(raw.ch_names),
            "duration_seconds": _duration_seconds(n_times, sfreq),
            "n_times": n_times,
            "first_samp": int(raw.first_samp),
            "last_samp": int(raw.last_samp),
            "highpass": float(raw.info.get("highpass", 0.0)),
            "lowpass": float(raw.info.get("lowpass", sfreq / 2.0)),
            "channel_summary": _channel_summary(raw),
            "event_summary": {
                "annotation_count": len(annotation_descriptions),
                "annotation_counts": _counter_items(Counter(annotation_descriptions)),
            },
        },
    }


def _preview_epochs(path: Path) -> dict[str, Any]:
    mne = _mne()
    epochs = mne.read_epochs(path, preload=False, verbose="ERROR")
    inverse_event_id = {int(code): str(name) for name, code in epochs.event_id.items()}
    event_codes = [int(item) for item in epochs.events[:, 2].tolist()] if len(epochs.events) else []
    event_counts = Counter(inverse_event_id.get(code, str(code)) for code in event_codes)
    return {
        "_preview_version": PREVIEW_VERSION,
        "data_type": "epochs",
        "summary": {
            "n_epochs": len(epochs),
            "sfreq": float(epochs.info["sfreq"]),
            "n_channels": len(epochs.ch_names),
            "tmin": float(epochs.tmin),
            "tmax": float(epochs.tmax),
            "event_id": dict(epochs.event_id),
            "event_counts": _counter_items(event_counts),
            "channel_summary": _channel_summary(epochs),
        },
    }


def _preview_evoked(path: Path, *, sample_channels: int, sample_points: int) -> dict[str, Any]:
    mne = _mne()
    evokeds = mne.read_evokeds(path, condition=None, verbose="ERROR")
    if not isinstance(evokeds, list):
        evokeds = [evokeds]
    if not evokeds:
        raise StudyOutputPreviewError(
            "DERIVED_DATASET_PREVIEW_EMPTY",
            "Evoked derived dataset does not contain any evoked data.",
            status_code=422,
        )

    primary = evokeds[0]
    event_names = [str(item.comment or f"evoked_{index}") for index, item in enumerate(evokeds)]
    n_times = int(len(primary.times))
    return {
        "_preview_version": PREVIEW_VERSION,
        "data_type": "evoked",
        "summary": {
            "event_names": event_names,
            "conditions": [_evoked_condition_summary(item) for item in evokeds[:MAX_EVOKED_CONDITIONS]],
            "sfreq": float(primary.info["sfreq"]),
            "time_range": {
                "tmin": float(primary.times[0]) if n_times else None,
                "tmax": float(primary.times[-1]) if n_times else None,
            },
            "n_times": n_times,
            "channel_summary": _channel_summary(primary),
            "sampled_curves": _sample_evoked_curves(primary, sample_channels=sample_channels, sample_points=sample_points),
        },
    }


def _evoked_condition_summary(evoked: Any) -> dict[str, Any]:
    n_times = int(len(evoked.times))
    return {
        "name": str(evoked.comment or ""),
        "nave": int(evoked.nave),
        "time_range": {
            "tmin": float(evoked.times[0]) if n_times else None,
            "tmax": float(evoked.times[-1]) if n_times else None,
        },
    }


def _sample_evoked_curves(evoked: Any, *, sample_channels: int, sample_points: int) -> dict[str, Any]:
    np = _numpy()
    n_channels = min(max(0, sample_channels), len(evoked.ch_names))
    n_times = int(len(evoked.times))
    if n_channels == 0 or n_times == 0:
        return {"times": [], "channels": []}

    point_count = min(max(1, sample_points), n_times)
    indexes = np.unique(np.linspace(0, n_times - 1, point_count, dtype=int))
    times = [round(float(evoked.times[int(index)]), 6) for index in indexes]
    channels = []
    for channel_index, channel_name in enumerate(evoked.ch_names[:n_channels]):
        values = [float(evoked.data[channel_index, int(index)]) for index in indexes]
        channels.append({"name": channel_name, "values": values})
    return {"times": times, "channels": channels}


def _channel_summary(inst: Any) -> dict[str, Any]:
    ch_names = list(getattr(inst, "ch_names", []) or [])
    get_channel_types = getattr(inst, "get_channel_types", None)
    channel_types = list(get_channel_types()) if callable(get_channel_types) else []
    return {
        "n_channels": len(ch_names),
        "ch_names_sample": ch_names[:24],
        "channel_type_counts": dict(Counter(channel_types)),
    }


def _counter_items(counter: Counter[str]) -> list[dict[str, Any]]:
    return [
        {"name": str(name), "count": int(count)}
        for name, count in counter.most_common(MAX_COUNTER_ITEMS)
        if str(name)
    ]


def _study_root(study: Any) -> Path:
    root = _study_root_or_none(study)
    if root is not None:
        return root
    raise StudyOutputPreviewError(
        "DERIVED_DATASET_STUDY_ROOT_MISSING",
        "Study has no usable root path for resolving derived dataset storage_path.",
        status_code=422,
    )


def _study_root_or_none(study: Any) -> Path | None:
    for attr in ("data_root", "study_root", "root_dir", "storage_path"):
        value = getattr(study, attr, None)
        if value:
            return Path(str(value)).expanduser().resolve()
    return None


def _duration_seconds(n_times: int, sfreq: float) -> float:
    return float(n_times) / sfreq if sfreq > 0 else 0.0


def _stringify(value: Any | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _mne():
    try:
        import mne
    except ImportError as exc:
        raise RuntimeError("MNE is required for derived dataset previews.") from exc
    return mne


def _numpy():
    try:
        import numpy
    except ImportError as exc:
        raise RuntimeError("NumPy is required for derived dataset previews.") from exc
    return numpy
