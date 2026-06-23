"""
Purpose: 对 Epochs 做自动试次剔除(峰峰值/平坦阈值 或 AutoReject),返回干净 Epochs + 溯源元数据。
Related: app/pipeline/dispatcher.py(_execute_reject_trials), app/pipeline/nodes/eeg_epoch_reject.json,
         app/engine/io.py(summarize_epochs / save_epochs_fif)。

试次剔除(trial / epoch rejection):把含眼动、肌电、漂移等大伪迹的整段 epoch 扔掉,留干净试次再去做
ERP / 时频 / 频域平均——脏 epoch 不剔会污染平均结果。两种方法(一个节点、method 下拉切换):
  - threshold(阈值法,MNE 内置,无额外依赖):任一通道在某 epoch 内峰峰值(max-min)超过阈值、或
    低于平坦阈值,就剔掉整个 epoch。经典 ERP 做法(Luck 2014)。
  - autoreject(Jas et al. 2017,需 autoreject 库):交叉验证给每个通道自动学阈值,还能先插值少量
    坏通道再决定剔不剔。更省心但慢、需电极坐标做插值。

两条路都返回 (cleaned_epochs, meta);meta 进结果 preview 作溯源(剔了几个 / 剔除率 / 判据),非黑箱。
"""

from __future__ import annotations

from typing import Any


def run_reject_trials(epochs: Any, params: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """按 method 分流:threshold(默认,MNE 内置)或 autoreject(需库)。返回 (cleaned_epochs, meta)。"""
    method = str(params.get("method", "threshold") or "threshold").strip().lower()
    if method == "autoreject":
        return _run_autoreject(epochs, params)
    return _run_threshold_reject(epochs, params)


def _run_threshold_reject(epochs: Any, params: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """峰峰值 / 平坦阈值剔除(MNE epochs.drop_bad)。阈值前端以 µV 给,这里换算成 V。"""
    n_before = len(epochs)

    reject: dict[str, float] = {}
    flat: dict[str, float] = {}
    ptp = params.get("reject_peak_to_peak")
    if ptp not in (None, "") and float(ptp) > 0:
        reject["eeg"] = float(ptp) * 1e-6  # µV → V
    # EOG 阈值:眼动范式用 EOG 导抓伪迹最直接;仅当数据含 EOG 通道时生效,否则忽略。
    eog_uv = params.get("reject_eog_uv")
    eog_applied = False
    if eog_uv not in (None, "") and float(eog_uv) > 0:
        try:
            ch_types = set(epochs.get_channel_types())
        except Exception:  # noqa: BLE001 — 读不到通道类型则当作无 EOG,安全忽略
            ch_types = set()
        if "eog" in ch_types:
            reject["eog"] = float(eog_uv) * 1e-6  # µV → V
            eog_applied = True
    flat_value = params.get("flat")
    if flat_value not in (None, "") and float(flat_value) > 0:
        flat["eeg"] = float(flat_value) * 1e-6  # µV → V
    if not reject and not flat:
        raise ValueError("Reject Trials(阈值法)至少要设峰峰值阈值或平坦阈值之一。")

    # 判据时间窗:宽 epoch + 强滤波时,限定判据窗可避开 epoch 边缘的滤波瞬态误剔。
    # 留空 = None = 用整段 epoch。区间合法性交给 MNE 校验。
    rmin_raw = params.get("reject_tmin")
    rmax_raw = params.get("reject_tmax")
    reject_tmin = None if rmin_raw in (None, "") else float(rmin_raw)
    reject_tmax = None if rmax_raw in (None, "") else float(rmax_raw)

    cleaned = epochs.copy()
    # 判据时间窗经 Epochs 属性设置:MNE 的 drop_bad 签名只有 (reject, flat, verbose),
    # reject_tmin/reject_tmax 是 Epochs 的属性而非 drop_bad 入参。仅在非空时设置——
    # 留空(默认)不动属性,保持旧的"整段判据"行为,无回归。
    if reject_tmin is not None:
        cleaned.reject_tmin = reject_tmin
    if reject_tmax is not None:
        cleaned.reject_tmax = reject_tmax
    cleaned.drop_bad(reject=reject or None, flat=flat or None, verbose="ERROR")
    n_after = len(cleaned)
    if n_after == 0:
        raise ValueError(
            f"试次剔除后一个 epoch 都不剩(剔掉了全部 {n_before} 个)。阈值过严——"
            "把峰峰值阈值调大,或确认单位是 µV(常用 100–200µV)。"
        )

    n_dropped = n_before - n_after
    return cleaned, {
        "reject_method": "threshold",
        "n_epochs_before": int(n_before),
        "n_epochs_after": int(n_after),
        "n_dropped": int(n_dropped),
        "drop_fraction": round(n_dropped / n_before, 4) if n_before else 0.0,
        "reject_peak_to_peak_uv": float(ptp) if (ptp not in (None, "") and float(ptp) > 0) else None,
        "flat_uv": float(flat_value) if (flat_value not in (None, "") and float(flat_value) > 0) else None,
        "reject_eog_uv": float(eog_uv) if eog_applied else None,
        "reject_tmin": reject_tmin,
        "reject_tmax": reject_tmax,
    }


def _run_autoreject(epochs: Any, params: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """AutoReject(交叉验证自动学阈值)。懒加载:未装库时只此方法失败,阈值法不受影响。"""
    try:
        from autoreject import AutoReject  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "AutoReject 方法需要 autoreject 库(云端重部署即 pip install);"
            "或改用「峰峰值 / 平坦阈值」方法(MNE 内置,无需额外依赖)。"
        ) from exc

    import numpy as np  # noqa: PLC0415

    n_before = len(epochs)
    n_ch = len(epochs.ch_names)
    raw_ni = params.get("n_interpolate")
    if raw_ni in (None, "", "auto"):
        # 留空=AutoReject 标准用法:在候选插值数上交叉验证自动选最优 κ(Jas 2017 的关键增量;
        # 不同被试/montage 最优 κ 差别大,固定单值会在干净数据上过插、脏数据上插不够)。
        cand = [c for c in (1, 4, 8, 16) if c < n_ch] or [max(0, min(1, n_ch - 1))]
        n_interp_grid = np.array(sorted(set(cand)))
    else:
        # 显式填值=固定该插值数、跳过 κ 搜索(更快但略糙,作为快速档)。
        n_interp_grid = np.array([max(0, min(int(raw_ni), max(0, n_ch - 1)))])
    # random_state 固定保证可复现。
    ar = AutoReject(
        n_interpolate=n_interp_grid,
        random_state=42,
        verbose=False,
    )
    try:
        cleaned = ar.fit_transform(epochs.copy())
    except Exception as exc:  # noqa: BLE001 — 把 autoreject 内部异常翻成可操作提示
        raise ValueError(
            f"AutoReject 运行失败:{exc}。常见原因:epoch 数太少(交叉验证需足够试次)、"
            "或缺电极坐标(插值需先接 Ch Loc Assign)。可改用阈值法。"
        ) from exc

    n_after = len(cleaned)
    if n_after == 0:
        raise ValueError(f"AutoReject 后一个 epoch 都不剩(原 {n_before} 个),数据可能整体过脏。")

    # 交叉验证实际选出的 κ(每通道类型一个,取其一)记进溯源,让"自动选了几"可见、可审计。
    chosen_kappa: int | None = None
    try:
        ni_ = getattr(ar, "n_interpolate_", None)
        if isinstance(ni_, dict) and ni_:
            chosen_kappa = int(next(iter(ni_.values())))
    except Exception:  # noqa: BLE001 — 读不到选值不影响结果,只是少一条溯源
        chosen_kappa = None

    n_dropped = n_before - n_after
    return cleaned, {
        "reject_method": "autoreject",
        "n_epochs_before": int(n_before),
        "n_epochs_after": int(n_after),
        "n_dropped": int(n_dropped),
        "drop_fraction": round(n_dropped / n_before, 4) if n_before else 0.0,
        "n_interpolate_grid": [int(x) for x in n_interp_grid.tolist()],
        "n_interpolate": chosen_kappa if chosen_kappa is not None else int(n_interp_grid[0]),
    }
