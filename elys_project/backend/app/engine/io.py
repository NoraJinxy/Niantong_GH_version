"""
Purpose: Provide shared EEG engine helpers used by Pipeline node executors.
Related: app/pipeline/dispatcher.py, app/engine/preprocess/*, app/engine/analysis/*.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from app.services.storage import StorageService, StorageUriError


MneFifKind = Literal["raw", "epochs", "evoked", "ica"]

MNE_SUFFIXES: dict[MneFifKind, tuple[str, ...]] = {
    "raw": ("-raw.fif", "-raw.fif.gz", "_raw.fif", "_raw.fif.gz"),
    "epochs": ("-epo.fif", "-epo.fif.gz"),
    "evoked": ("-ave.fif", "-ave.fif.gz"),
    "ica": ("-ica.fif", "-ica.fif.gz"),
}

DEFAULT_SUFFIX: dict[MneFifKind, str] = {
    "raw": "-raw.fif",
    "epochs": "-epo.fif",
    "evoked": "-ave.fif",
    "ica": "-ica.fif",
}


def read_raw_from_data_info(data_info: Any, preload: bool = True):
    path = resolve_path_reference(data_info, ("storage_uri", "fif_abs_path", "fif_path"))
    mne = _mne()
    return mne.io.read_raw_fif(path, preload=preload, verbose="ERROR")


def read_epochs_from_data_info(data_info: Any, preload: bool = True):
    path = resolve_path_reference(
        data_info,
        ("storage_uri", "artifact_storage_uri", "fif_abs_path", "fif_path", "storage_path", "artifact_storage_path"),
    )
    mne = _mne()
    return mne.read_epochs(path, preload=preload, verbose="ERROR")


def read_ica_from_data_info(data_info: Any):
    path = resolve_path_reference(
        data_info,
        (
            "storage_uri",
            "artifact_storage_uri",
            "ica_abs_path",
            "ica_path",
            "fif_abs_path",
            "fif_path",
            "storage_path",
            "artifact_storage_path",
        ),
    )
    mne = _mne()
    return mne.preprocessing.read_ica(path, verbose="ERROR")


def save_raw_fif(raw: Any, path: str | Path, *, overwrite: bool = True) -> Path:
    target = ensure_mne_fif_path(path, "raw")
    target.parent.mkdir(parents=True, exist_ok=True)
    raw.save(target, overwrite=overwrite, verbose="ERROR")
    return target


def save_epochs_fif(epochs: Any, path: str | Path, *, overwrite: bool = True) -> Path:
    target = ensure_mne_fif_path(path, "epochs")
    target.parent.mkdir(parents=True, exist_ok=True)
    epochs.save(target, overwrite=overwrite, verbose="ERROR")
    return target


def save_evoked_fif(evoked: Any, path: str | Path, *, overwrite: bool = True) -> Path:
    target = ensure_mne_fif_path(path, "evoked")
    target.parent.mkdir(parents=True, exist_ok=True)
    evoked.save(target, overwrite=overwrite, verbose="ERROR")
    return target


def save_ica_fif(ica: Any, path: str | Path, *, overwrite: bool = True) -> Path:
    target = ensure_mne_fif_path(path, "ica")
    target.parent.mkdir(parents=True, exist_ok=True)
    ica.save(target, overwrite=overwrite, verbose="ERROR")
    return target


def save_tfr_h5(tfr: Any, path: str | Path, *, overwrite: bool = True) -> Path:
    """把 AverageTFR 存成 MNE 的 HDF5(-tfr.h5)。TFR 不用 FIF(FIF 不支持时频立方)。"""
    target = ensure_tfr_h5_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tfr.save(target, overwrite=overwrite, verbose="ERROR")
    return target


def summarize_raw(raw: Any) -> dict[str, Any]:
    sfreq = float(raw.info["sfreq"])
    return {
        "data_type": "raw",
        "n_channels": len(raw.ch_names),
        "ch_names": list(raw.ch_names),
        "channel_types": list(raw.get_channel_types()),
        "sfreq": sfreq,
        "n_times": int(raw.n_times),
        "duration_seconds": _duration_seconds(raw.n_times, sfreq),
        "first_samp": int(raw.first_samp),
        "last_samp": int(raw.last_samp),
        "highpass": float(raw.info.get("highpass", 0.0)),
        "lowpass": float(raw.info.get("lowpass", sfreq / 2.0)),
        "annotation_count": len(getattr(raw, "annotations", [])),
    }


def summarize_epochs(epochs: Any) -> dict[str, Any]:
    sfreq = float(epochs.info["sfreq"])
    n_times = int(len(epochs.times))
    return {
        "data_type": "epochs",
        "n_epochs": len(epochs),
        "n_channels": len(epochs.ch_names),
        "ch_names": list(epochs.ch_names),
        "channel_types": list(epochs.get_channel_types()),
        "sfreq": sfreq,
        "n_times": n_times,
        "duration_seconds": _duration_seconds(n_times, sfreq),
        "tmin": float(epochs.tmin),
        "tmax": float(epochs.tmax),
        "event_id": dict(epochs.event_id),
        "metadata_columns": list(epochs.metadata.columns) if epochs.metadata is not None else [],
    }


def summarize_evoked(evoked: Any) -> dict[str, Any]:
    sfreq = float(evoked.info["sfreq"])
    n_times = int(len(evoked.times))
    return {
        "data_type": "evoked",
        "n_channels": len(evoked.ch_names),
        "ch_names": list(evoked.ch_names),
        "channel_types": list(evoked.get_channel_types()),
        "sfreq": sfreq,
        "n_times": n_times,
        "duration_seconds": _duration_seconds(n_times, sfreq),
        "tmin": float(evoked.times[0]) if n_times else None,
        "tmax": float(evoked.times[-1]) if n_times else None,
        "nave": int(evoked.nave),
        "comment": evoked.comment,
    }


def summarize_tfr(tfr: Any) -> dict[str, Any]:
    """AverageTFR 的轻量摘要(不含功率立方,热图走 tfr_view 端点按需取)。"""
    sfreq = float(tfr.info["sfreq"])
    # 注意:tfr.freqs / tfr.times 是 numpy 数组,绝不能写 `arr or []`(会触发
    # 「truth value of an array is ambiguous」)—— 显式判 None。
    freqs_attr = getattr(tfr, "freqs", None)
    times_attr = getattr(tfr, "times", None)
    freqs = list(freqs_attr) if freqs_attr is not None else []
    times = list(times_attr) if times_attr is not None else []
    return {
        "data_type": "tfr",
        "n_channels": len(tfr.ch_names),
        "ch_names": list(tfr.ch_names),
        "channel_types": list(tfr.info.get_channel_types()),
        "sfreq": sfreq,
        "n_freqs": len(freqs),
        "fmin": float(freqs[0]) if freqs else None,
        "fmax": float(freqs[-1]) if freqs else None,
        "n_times": len(times),
        "tmin": float(times[0]) if times else None,
        "tmax": float(times[-1]) if times else None,
        "nave": int(getattr(tfr, "nave", 0) or 0),
        "comment": getattr(tfr, "comment", None),
        "method": str(getattr(tfr, "method", "") or ""),
    }


def resolve_path_reference(reference: Any, keys: tuple[str, ...]) -> Path:
    missing_paths: list[Path] = []
    for key in keys:
        value = _get_reference_value(reference, key)
        if value:
            path = _resolve_reference_path(value, reference)
            if path.exists():
                return path
            missing_paths.append(path)
    if missing_paths:
        raise FileNotFoundError(f"Referenced FIF path does not exist: {missing_paths[0]}")
    raise ValueError(f"Reference does not contain any usable path key: {', '.join(keys)}")


def _resolve_reference_path(value: Any, reference: Any) -> Path:
    text = str(value)
    study_id = _get_reference_value(reference, "study_id")
    study_root = _get_reference_value(reference, "study_root")
    try:
        return StorageService().resolve_path(text, study_id=study_id, study_root=study_root)
    except (StorageUriError, ValueError):
        return Path(text).expanduser()


def ensure_mne_fif_path(path: str | Path, kind: MneFifKind) -> Path:
    target = Path(path).expanduser()
    filename = target.name.lower()
    if filename.endswith(MNE_SUFFIXES[kind]):
        return target
    if filename.endswith(".fif") or filename.endswith(".fif.gz"):
        raise ValueError(f"{kind} FIF path should use an MNE-style suffix: {MNE_SUFFIXES[kind][0]}")
    return target.with_name(f"{target.name}{DEFAULT_SUFFIX[kind]}")


def ensure_tfr_h5_path(path: str | Path) -> Path:
    """保证 TFR 落盘文件名以 -tfr.h5 结尾(MNE read/write 的硬约束)。"""
    target = Path(path).expanduser()
    name = target.name.lower()
    if name.endswith(("-tfr.h5", "-tfr.hdf5")):
        return target
    if name.endswith((".h5", ".hdf5")):
        raise ValueError("TFR path should use an MNE-style suffix: -tfr.h5")
    return target.with_name(f"{target.name}-tfr.h5")


def _get_reference_value(reference: Any, key: str) -> Any:
    if isinstance(reference, dict):
        return reference.get(key)
    return getattr(reference, key, None)


def _duration_seconds(n_times: int, sfreq: float) -> float:
    if sfreq <= 0:
        return 0.0
    return float(n_times) / sfreq


def _mne():
    try:
        import mne
    except ImportError as exc:
        raise RuntimeError("MNE is required for engine IO operations.") from exc
    return mne
