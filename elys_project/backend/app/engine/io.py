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


def read_evoked_from_data_info(data_info: Any):
    """读单条 ERP(-ave.fif)→ mne.Evoked。一个 artifact 存一个 condition,取首个。"""
    path = resolve_path_reference(
        data_info,
        ("storage_uri", "artifact_storage_uri", "fif_abs_path", "fif_path", "storage_path", "artifact_storage_path"),
    )
    mne = _mne()
    evokeds = mne.read_evokeds(path, verbose="ERROR")
    if not evokeds:
        raise ValueError(f"read_evoked_from_data_info: 文件无 evoked: {path}")
    return evokeds[0]


def read_tfr_from_data_info(data_info: Any):
    """读时频(-tfr.h5)→ mne.time_frequency.AverageTFR。read_tfrs 返回 list,取首个。"""
    path = resolve_path_reference(
        data_info,
        ("storage_uri", "artifact_storage_uri", "fif_abs_path", "fif_path", "storage_path", "artifact_storage_path"),
    )
    mne = _mne()
    tfrs = mne.time_frequency.read_tfrs(str(path))
    obj = tfrs[0] if isinstance(tfrs, list) else tfrs
    if obj is None:
        raise ValueError(f"read_tfr_from_data_info: 文件无 TFR: {path}")
    return obj


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


def save_psd_npz(result: dict[str, Any], path: str | Path, *, overwrite: bool = True) -> Path:
    """把 PSD 结果(freqs / psds / ch_names 的数组 dict)存成 numpy .npz。

    PSD 故意不走 MNE Spectrum.save —— Spectrum 的 HDF5 存取 API 跨 MNE 版本易变;这里只存纯
    numpy 数组,自给自足、版本无关。下游读回用 numpy.load(...)。
    """
    import numpy as np  # noqa: PLC0415

    target = ensure_psd_npz_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        str(target),
        freqs=np.asarray(result.get("freqs"), dtype=float),
        psds=np.asarray(result.get("psds"), dtype=float),
        ch_names=np.asarray(list(result.get("ch_names") or []), dtype="U64"),
        sfreq=np.asarray(float(result.get("sfreq") or 0.0), dtype=float),
    )
    return target


def summarize_psd(result: dict[str, Any]) -> dict[str, Any]:
    """PSD 结果的轻量摘要(不含完整功率矩阵,谱线后续走 psd 视图端点按需取)。"""
    freqs_attr = result.get("freqs")
    # freqs 是 numpy 数组,绝不能写 `arr or []`(会触发 array 真值歧义)—— 显式判 None 后转成 list。
    freqs = list(freqs_attr) if freqs_attr is not None else []
    ch_names = list(result.get("ch_names") or [])
    return {
        "data_type": "psd",
        "n_channels": len(ch_names),
        "ch_names": ch_names,
        "channel_types": list(result.get("channel_types") or []),
        "sfreq": float(result.get("sfreq") or 0.0),
        "n_freqs": len(freqs),
        "fmin": float(freqs[0]) if freqs else None,
        "fmax": float(freqs[-1]) if freqs else None,
        "n_epochs": int(result.get("n_epochs") or 0),
        "method": str(result.get("method", "welch") or "welch"),
        "band_powers": result.get("band_powers") or [],
        "comment": result.get("condition"),
    }


def ensure_psd_npz_path(path: str | Path) -> Path:
    """保证 PSD 落盘文件名以 .npz 结尾(numpy savez 约束)。"""
    target = Path(path).expanduser()
    if target.name.lower().endswith(".npz"):
        return target
    return target.with_name(f"{target.name}_psd.npz")


def load_psd_npz(path: str | Path) -> dict[str, Any]:
    """读单被试 PSD .npz → {freqs, psds, ch_names, sfreq}。"""
    import numpy as np  # noqa: PLC0415

    data = np.load(str(Path(path).expanduser()), allow_pickle=False)
    return {
        "freqs": data["freqs"],
        "psds": data["psds"],
        "ch_names": list(data["ch_names"]),
        "sfreq": float(data["sfreq"]),
    }


def save_psd_grandavg_npz(result: dict[str, Any], path: str | Path, *, overwrite: bool = True) -> Path:
    """保存 grand average PSD（mean ± SEM）为 .npz；格式类似单被试 PSD，额外含 psds_sem。"""
    import numpy as np  # noqa: PLC0415

    target = ensure_psd_npz_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        str(target),
        freqs=np.asarray(result.get("freqs"), dtype=float),
        psds=np.asarray(result.get("psds"), dtype=float),
        psds_sem=np.asarray(result.get("psds_sem"), dtype=float),
        ch_names=np.asarray(list(result.get("ch_names") or []), dtype="U64"),
        sfreq=np.asarray(float(result.get("sfreq") or 0.0), dtype=float),
        label=np.asarray(str(result.get("label") or ""), dtype="U256"),
        n_subjects=np.asarray(int(result.get("n_subjects") or 0), dtype=int),
    )
    return target


def summarize_psd_grandavg(result: dict[str, Any]) -> dict[str, Any]:
    """grand average PSD 的轻量摘要。"""
    freqs_attr = result.get("freqs")
    freqs = list(freqs_attr) if freqs_attr is not None else []
    ch_names = list(result.get("ch_names") or [])
    return {
        "data_type": "psd_grandavg",
        "n_subjects": int(result.get("n_subjects") or 0),
        "n_channels": len(ch_names),
        "ch_names": ch_names,
        "n_freqs": len(freqs),
        "fmin": float(freqs[0]) if freqs else None,
        "fmax": float(freqs[-1]) if freqs else None,
        "label": str(result.get("label") or ""),
    }


# ========== 通用 unit_stack(沿 unit 轴堆叠的块,通吃 evoked/psd/tfr) ==========
# 任何分析产物都能写成 (unit, *feature_axes):unit=trial/run/subject(语义),feature 轴随形态。
# group 的 merge/average/compare 全是对 unit 轴的操作,故三类共用本格式,一套 io 通吃。

def ensure_unit_stack_npz_path(path: str | Path) -> Path:
    """保证 unit_stack 落盘文件名以 .npz 结尾(numpy savez 约束)。"""
    target = Path(path).expanduser()
    if target.name.lower().endswith(".npz"):
        return target
    return target.with_name(f"{target.name}_unitstack.npz")


def save_unit_stack_npz(result: dict[str, Any], path: str | Path, *, overwrite: bool = True) -> Path:
    """保存 unit_stack:data (n_units × *feature) + base_type + 坐标轴 + 逐 unit 元数据。

    times / freqs 缺省轴存空数组(读回还原成 None);psd 无 time、evoked 无 freq。
    """
    import numpy as np  # noqa: PLC0415

    target = ensure_unit_stack_npz_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    times = result.get("times")
    freqs = result.get("freqs")
    np.savez(
        str(target),
        data=np.asarray(result["data"], dtype=float),
        base_type=np.asarray(str(result.get("base_type") or ""), dtype="U16"),
        ch_names=np.asarray(list(result.get("ch_names") or []), dtype="U64"),
        ch_types=np.asarray(list(result.get("ch_types") or []), dtype="U16"),
        times=np.asarray(list(times) if times is not None else [], dtype=float),
        freqs=np.asarray(list(freqs) if freqs is not None else [], dtype=float),
        sfreq=np.asarray(float(result.get("sfreq") or 0.0), dtype=float),
        unit_labels=np.asarray(list(result.get("unit_labels") or []), dtype="U256"),
        unit_subjects=np.asarray(list(result.get("unit_subjects") or []), dtype="U256"),
        unit_n=np.asarray(list(result.get("unit_n") or []), dtype=float),
        unit_kind=np.asarray(str(result.get("unit_kind") or "unit"), dtype="U32"),
        label=np.asarray(str(result.get("label") or ""), dtype="U256"),
    )
    return target


def load_unit_stack_npz(path: str | Path) -> dict[str, Any]:
    """读 unit_stack .npz → dict(data + 坐标轴 + 逐 unit 元数据);空 times/freqs 还原成 None。"""
    import numpy as np  # noqa: PLC0415

    data = np.load(str(Path(path).expanduser()), allow_pickle=False)
    times = data["times"]
    freqs = data["freqs"]
    stacked = data["data"]
    return {
        "data": stacked,  # (n_units, n_channels, *feature)
        "base_type": str(data["base_type"]),
        "ch_names": [str(c) for c in data["ch_names"]],
        "ch_types": [str(c) for c in data["ch_types"]],
        "times": times if times.size else None,
        "freqs": freqs if freqs.size else None,
        "sfreq": float(data["sfreq"]),
        "unit_labels": [str(c) for c in data["unit_labels"]],
        "unit_subjects": [str(c) for c in data["unit_subjects"]],
        "unit_n": [float(x) for x in data["unit_n"]],
        "unit_kind": str(data["unit_kind"]),
        "label": str(data["label"]),
        "n_units": int(stacked.shape[0]),
    }


def summarize_unit_stack(result: dict[str, Any]) -> dict[str, Any]:
    """unit_stack 的轻量摘要(不含大数组)。"""
    ch_names = list(result.get("ch_names") or [])
    times = result.get("times")
    freqs = result.get("freqs")
    data = result.get("data")
    n_units = int(result.get("n_units") or (data.shape[0] if data is not None else 0))
    summary: dict[str, Any] = {
        "data_type": "unit_stack",
        "base_type": str(result.get("base_type") or ""),
        "unit_kind": str(result.get("unit_kind") or "unit"),
        "n_units": n_units,
        "n_channels": len(ch_names),
        "ch_names": ch_names,
        "label": str(result.get("label") or ""),
        "unit_labels": list(result.get("unit_labels") or []),
        "subjects": list(result.get("unit_subjects") or []),
    }
    # times / freqs 是 numpy 数组或 None —— 显式判 None + len(),严禁 `if 数组`(真值歧义)。
    if times is not None and len(times) > 0:
        summary["n_times"] = int(len(times))
        summary["tmin"] = float(times[0])
        summary["tmax"] = float(times[-1])
    if freqs is not None and len(freqs) > 0:
        summary["n_freqs"] = int(len(freqs))
        summary["fmin"] = float(freqs[0])
        summary["fmax"] = float(freqs[-1])
    return summary


# ========== 通用 stat_map(两组 unit_stack 的统计比较结果,通吃 evoked/psd/tfr) ==========
# compare 保留 unit 轴在其上做检验:逐点 t(全通道×feature)+ none/FDR 校正,可选 ROI cluster permutation。
# 形状:tmap/pmap/sig/mean_a/mean_b 均 (n_ch, *feature);cluster_masks (n_clusters, *continuous)。

def ensure_stat_map_npz_path(path: str | Path) -> Path:
    target = Path(path).expanduser()
    if target.name.lower().endswith(".npz"):
        return target
    return target.with_name(f"{target.name}_statmap.npz")


def save_stat_map_npz(result: dict[str, Any], path: str | Path, *, overwrite: bool = True) -> Path:
    """保存 stat_map 为 .npz。sig / cluster_masks 用 int8 存(读回转 bool)。"""
    import numpy as np  # noqa: PLC0415

    target = ensure_stat_map_npz_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    times = result.get("times")
    freqs = result.get("freqs")
    cmasks = result.get("cluster_masks")
    cmasks_arr = (
        np.asarray(cmasks, dtype=np.int8)
        if cmasks is not None and len(cmasks) > 0
        else np.zeros((0,), dtype=np.int8)
    )
    np.savez(
        str(target),
        base_type=np.asarray(str(result.get("base_type") or ""), dtype="U16"),
        ch_names=np.asarray(list(result.get("ch_names") or []), dtype="U64"),
        ch_types=np.asarray(list(result.get("ch_types") or []), dtype="U16"),
        times=np.asarray(list(times) if times is not None else [], dtype=float),
        freqs=np.asarray(list(freqs) if freqs is not None else [], dtype=float),
        sfreq=np.asarray(float(result.get("sfreq") or 0.0), dtype=float),
        tmap=np.asarray(result["tmap"], dtype=float),
        pmap=np.asarray(result["pmap"], dtype=float),
        sig=np.asarray(result["sig"], dtype=np.int8),
        mean_a=np.asarray(result["mean_a"], dtype=float),
        mean_b=np.asarray(result["mean_b"], dtype=float),
        design=np.asarray(str(result.get("design") or ""), dtype="U16"),
        method=np.asarray(str(result.get("method") or ""), dtype="U16"),
        tail=np.asarray(str(result.get("tail") or "two-sided"), dtype="U16"),
        correction=np.asarray(str(result.get("correction") or "none"), dtype="U16"),
        alpha=np.asarray(float(result.get("alpha") or 0.05), dtype=float),
        contrast_label=np.asarray(str(result.get("contrast_label") or ""), dtype="U256"),
        n_a=np.asarray(int(result.get("n_a") or 0), dtype=int),
        n_b=np.asarray(int(result.get("n_b") or 0), dtype=int),
        roi_channels=np.asarray(list(result.get("roi_channels") or []), dtype="U64"),
        roi_axis=np.asarray(str(result.get("roi_axis") or ""), dtype="U16"),
        cluster_masks=cmasks_arr,
        cluster_pvals=np.asarray(list(result.get("cluster_pvals") or []), dtype=float),
    )
    return target


def load_stat_map_npz(path: str | Path) -> dict[str, Any]:
    """读 stat_map .npz → dict(sig / cluster_masks 还原 bool,空 times/freqs 还原 None)。"""
    import numpy as np  # noqa: PLC0415

    data = np.load(str(Path(path).expanduser()), allow_pickle=False)
    times = data["times"]
    freqs = data["freqs"]
    cmasks = data["cluster_masks"]
    return {
        "base_type": str(data["base_type"]),
        "ch_names": [str(c) for c in data["ch_names"]],
        "ch_types": [str(c) for c in data["ch_types"]],
        "times": times if times.size else None,
        "freqs": freqs if freqs.size else None,
        "sfreq": float(data["sfreq"]),
        "tmap": data["tmap"],
        "pmap": data["pmap"],
        "sig": data["sig"].astype(bool),
        "mean_a": data["mean_a"],
        "mean_b": data["mean_b"],
        "design": str(data["design"]),
        "method": str(data["method"]),
        "tail": str(data["tail"]),
        "correction": str(data["correction"]),
        "alpha": float(data["alpha"]),
        "contrast_label": str(data["contrast_label"]),
        "n_a": int(data["n_a"]),
        "n_b": int(data["n_b"]),
        "roi_channels": [str(c) for c in data["roi_channels"]],
        "roi_axis": str(data["roi_axis"]),
        "cluster_masks": cmasks.astype(bool) if cmasks.size else None,
        "cluster_pvals": [float(x) for x in data["cluster_pvals"]],
    }


def summarize_stat_map(result: dict[str, Any]) -> dict[str, Any]:
    """stat_map 的轻量摘要(不含完整 t 图;含显著点数 + 显著 cluster 窗口,供 preview)。"""
    import numpy as np  # noqa: PLC0415

    ch_names = list(result.get("ch_names") or [])
    times = result.get("times")
    freqs = result.get("freqs")
    sig = result.get("sig")
    sig_arr = np.asarray(sig, dtype=bool) if sig is not None else np.zeros((0,), dtype=bool)
    n_total = int(sig_arr.size)
    n_sig = int(sig_arr.sum()) if n_total else 0
    summary: dict[str, Any] = {
        "data_type": "stat_map",
        "base_type": str(result.get("base_type") or ""),
        "design": str(result.get("design") or ""),
        "method": str(result.get("method") or ""),
        "tail": str(result.get("tail") or "two-sided"),
        "correction": str(result.get("correction") or "none"),
        "alpha": float(result.get("alpha") or 0.05),
        "contrast_label": str(result.get("contrast_label") or ""),
        "n_channels": len(ch_names),
        "ch_names": ch_names,
        "n_a": int(result.get("n_a") or 0),
        "n_b": int(result.get("n_b") or 0),
        "n_significant": n_sig,
        "n_total": n_total,
        "sig_fraction": round(n_sig / n_total, 4) if n_total else 0.0,
        "roi_channels": list(result.get("roi_channels") or []),
        "roi_axis": str(result.get("roi_axis") or ""),
        "clusters": list(result.get("cluster_summary") or []),
    }
    if times is not None and len(times) > 0:
        summary["n_times"] = int(len(times))
        summary["tmin"] = float(times[0])
        summary["tmax"] = float(times[-1])
    if freqs is not None and len(freqs) > 0:
        summary["n_freqs"] = int(len(freqs))
        summary["fmin"] = float(freqs[0])
        summary["fmax"] = float(freqs[-1])
    return summary


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
