"""
Purpose: Group analysis – 通用 grand average(沿 unit 轴 mean ± SEM)。压扁 unit_stack 后**回吐原形态**
         (evoked/psd/tfr),以便直接复用现有观察页渲染。
Related: app/engine/group/stack.py, app/pipeline/dispatcher.py (_execute_group_average), app/engine/io.py.
"""

from __future__ import annotations

from typing import Any, Callable

from app.engine.io import resolve_path_reference, load_unit_stack_npz


_PATH_KEYS = (
    "storage_uri",
    "artifact_storage_uri",
    "fif_abs_path",
    "fif_path",
    "storage_path",
    "artifact_storage_path",
)


def run_group_average(data_info: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """从 unit_stack 读出 → 沿 unit 轴求均值与 SEM(grand average)。

    weighted=True 时按每个 unit 的试次数(unit_n)加权——ERP 跨被试常用(各被试 trial 数不等)。
    返回带 base_type 的结果,dispatcher 据此把 mean 回吐成原形态(evoked/psd/tfr)产物。
    """
    import numpy as np  # noqa: PLC0415

    path = resolve_path_reference(data_info, _PATH_KEYS)
    stk = load_unit_stack_npz(path)
    data = np.asarray(stk["data"], dtype=float)  # (n_units, n_ch, *feature)
    n_units = int(data.shape[0])
    if n_units == 0:
        raise ValueError("Grand Average: unit_stack 为空(0 个 unit)。")

    unit_n = np.asarray(stk.get("unit_n") or [], dtype=float)
    weighted = bool(params.get("weighted", False))
    if weighted and unit_n.size == n_units and float(unit_n.sum()) > 0:
        weights = unit_n / float(unit_n.sum())
        mean = np.tensordot(weights, data, axes=([0], [0]))  # 沿 unit 轴加权平均
    else:
        mean = data.mean(axis=0)
    # ddof=1 无偏标准差,n=1 时 SEM 取 0 避免 NaN
    sem = (
        np.std(data, axis=0, ddof=1) / np.sqrt(n_units)
        if n_units > 1
        else np.zeros_like(mean)
    )

    return {
        "base_type": str(stk["base_type"]),
        "mean": mean,
        "sem": sem,
        "ch_names": list(stk["ch_names"]),
        "ch_types": list(stk.get("ch_types") or (["eeg"] * len(stk["ch_names"]))),
        "times": stk.get("times"),
        "freqs": stk.get("freqs"),
        "sfreq": float(stk.get("sfreq") or 0.0),
        "n_units": n_units,
        "nave_total": int(unit_n.sum()) if unit_n.size else n_units,
        "label": str(stk.get("label") or ""),
        "subjects": list(stk.get("unit_subjects") or []),
    }


def build_grandavg_payload(
    result: dict[str, Any],
) -> tuple[str, Callable[[Any], Any], dict[str, Any]]:
    """据 base_type 把 grand average 结果组装成 (data_type, writer(path), summary)。

    回吐原形态以复用观察页:psd→psd_grandavg(.npz,带 ±SEM 带);evoked→-ave.fif;tfr→-tfr.h5。
    SEM 目前仅 PSD 观察页渲染;evoked/tfr 的 SEM 进 summary,观察页带状显示后置。
    """
    base = str(result.get("base_type") or "")
    if base == "psd":
        from app.engine.io import save_psd_grandavg_npz, summarize_psd_grandavg  # noqa: PLC0415

        payload = {
            "psds": result["mean"],
            "psds_sem": result["sem"],
            "freqs": result["freqs"],
            "ch_names": result["ch_names"],
            "sfreq": result["sfreq"],
            "n_subjects": result["n_units"],
            "label": result["label"],
            "subjects": result["subjects"],
        }
        summary = summarize_psd_grandavg(payload)
        summary["n_units"] = result["n_units"]
        return "psd_grandavg", (lambda p: save_psd_grandavg_npz(payload, p)), summary

    if base == "evoked":
        from app.engine.io import save_evoked_fif, summarize_evoked  # noqa: PLC0415

        evoked = _build_evoked(result)
        summary = summarize_evoked(evoked)
        summary["n_units"] = result["n_units"]
        return "evoked", (lambda p: save_evoked_fif(evoked, p)), summary

    if base == "tfr":
        from app.engine.io import save_tfr_h5, summarize_tfr  # noqa: PLC0415

        tfr = _build_tfr(result)
        summary = summarize_tfr(tfr)
        summary["n_units"] = result["n_units"]
        return "tfr", (lambda p: save_tfr_h5(tfr, p)), summary

    raise ValueError(f"Grand Average 不支持的 base_type: '{base}'(可处理 evoked/psd/tfr)。")


def _build_evoked(result: dict[str, Any]) -> Any:
    """用均值重建 mne.EvokedArray(grand-average ERP 仍是一条 ERP,可进波形观察页)。"""
    import mne  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    sfreq = float(result.get("sfreq") or 0.0) or 1.0
    info = mne.create_info(list(result["ch_names"]), sfreq, ch_types=list(result["ch_types"]))
    times = result.get("times")
    tmin = float(times[0]) if times is not None and len(times) > 0 else 0.0
    return mne.EvokedArray(
        np.asarray(result["mean"], dtype=float),
        info,
        tmin=tmin,
        nave=int(result.get("nave_total") or result["n_units"]),
        comment=str(result.get("label") or "grandavg"),
    )


def _build_tfr(result: dict[str, Any]) -> Any:
    """用均值重建 AverageTFR(grand-average 时频仍是时频立方,可进时频观察页)。"""
    import mne  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    sfreq = float(result.get("sfreq") or 0.0) or 1.0
    info = mne.create_info(list(result["ch_names"]), sfreq, ch_types=list(result["ch_types"]))
    data = np.asarray(result["mean"], dtype=float)  # (n_ch, n_freq, n_times)
    times = np.asarray(result["times"], dtype=float)
    freqs = np.asarray(result["freqs"], dtype=float)
    nave = int(result.get("nave_total") or result["n_units"])
    comment = str(result.get("label") or "grandavg")
    # MNE 1.7+ 用 AverageTFRArray(从数组构造);老签名退回 AverageTFR 位置参数。
    array_cls = getattr(mne.time_frequency, "AverageTFRArray", None)
    if array_cls is not None:
        return array_cls(info=info, data=data, times=times, freqs=freqs, nave=nave, comment=comment)
    return mne.time_frequency.AverageTFR(info, data, times, freqs, nave, comment=comment)
