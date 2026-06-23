"""
Purpose: Group analysis – 通用统计比较。两组 unit_stack(A/B)沿 unit 轴做检验 → stat_map。
         通吃 evoked/psd/tfr:统计只对 unit 轴动手、与形态无关(同 merge/average 的统一抽象)。
Related: app/engine/group/stack.py, app/pipeline/dispatcher.py (_execute_group_compare), app/engine/io.py.

两种方法:
- pointwise: 每个 feature 点(通道×时间/频率)逐点 t——配对 ttest_rel / 独立 ttest_ind(Welch),
  none / FDR(BH)多重比较校正 → 完整 t 图 + 显著掩码。
- cluster: ROI(选定通道平均)上沿连续轴(time/freq/freq×time)做 cluster permutation(MNE),
  montage-free、可复现(固定 seed)。配对走 1samp(t,差值),独立走 cluster_test(F)。
"""

from __future__ import annotations

from typing import Any

from app.engine.group.stack import _assert_axis_match, align_and_stack, extract_block


_TAIL_ALT = {"two-sided": "two-sided", "greater": "greater", "less": "less"}
_TAIL_INT = {"two-sided": 0, "greater": 1, "less": -1}


def _pool_side(data_infos: list[dict[str, Any]], params: dict[str, Any], label_key: str) -> dict[str, Any]:
    """把一个端口收到的(≥1 个)产物抽块后沿 unit 轴并成一个组块。单 unit_stack 即原样返回。"""
    if not data_infos:
        raise ValueError(f"Group Compare: 端口 {label_key} 没有收到上游 unit_stack。")
    blocks = [extract_block(di) for di in data_infos]
    group = align_and_stack(blocks, params)
    # align_and_stack 用 compare 节点的 params.label(通常空)→ 这里回填输入 unit_stack 自带的组标签。
    if not group.get("label"):
        for blk in blocks:
            if blk.get("label"):
                group["label"] = blk["label"]
                break
    return group


def _align_two(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """把 A/B 两组对齐到共有通道 + 校验 feature 轴一致,返回对齐后的数据与坐标。"""
    import numpy as np  # noqa: PLC0415

    if a["base_type"] != b["base_type"]:
        raise ValueError(
            f"不能比较不同形态:A={a['base_type']} vs B={b['base_type']}。两组须同为 ERP / PSD / TFR。"
        )
    base_type = a["base_type"]

    common = [c for c in a["ch_names"] if c in set(b["ch_names"])]
    if not common:
        raise ValueError("A/B 两组没有共有通道,无法比较(montage 不一致)。请筛选同导联的输入。")

    _assert_axis_match(a.get("times"), b.get("times"), "时间轴", base_type)
    _assert_axis_match(a.get("freqs"), b.get("freqs"), "频率轴", base_type)

    def _reorder(group: dict[str, Any]) -> Any:
        idx = {c: i for i, c in enumerate(group["ch_names"])}
        sel = [idx[c] for c in common]
        return np.asarray(group["data"], dtype=float)[:, sel, ...]  # 通道在 axis=1

    ch_types = _ch_types_for(a, common)
    return {
        "base_type": base_type,
        "a_data": _reorder(a),  # (n_a, n_ch, *feature)
        "b_data": _reorder(b),  # (n_b, n_ch, *feature)
        "ch_names": common,
        "ch_types": ch_types,
        "times": a.get("times"),
        "freqs": a.get("freqs"),
        "sfreq": float(a.get("sfreq") or 0.0),
    }


def _ch_types_for(group: dict[str, Any], common: list[str]) -> list[str]:
    names = list(group.get("ch_names") or [])
    types = list(group.get("ch_types") or [])
    tmap = {n: (types[i] if i < len(types) else "eeg") for i, n in enumerate(names)}
    return [str(tmap.get(c, "eeg")) for c in common]


def _roi_axis_name(base_type: str) -> str:
    return {"evoked": "times", "psd": "freqs", "tfr": "freq_time"}.get(base_type, "")


def _describe_cluster(mask: Any, base_type: str, times: Any, freqs: Any) -> dict[str, Any]:
    """把一个 cluster 的布尔掩码翻成可读窗口(时间/频率范围)。"""
    import numpy as np  # noqa: PLC0415

    m = np.asarray(mask, dtype=bool)
    out: dict[str, Any] = {}
    if base_type == "evoked" and times is not None:
        idx = np.where(m)[0]
        if idx.size:
            out["tmin"] = round(float(times[idx.min()]), 4)
            out["tmax"] = round(float(times[idx.max()]), 4)
    elif base_type == "psd" and freqs is not None:
        idx = np.where(m)[0]
        if idx.size:
            out["fmin"] = round(float(freqs[idx.min()]), 4)
            out["fmax"] = round(float(freqs[idx.max()]), 4)
    elif base_type == "tfr" and freqs is not None and times is not None:
        fi, ti = np.where(m)  # (n_freq, n_time) 掩码
        if fi.size:
            out["fmin"] = round(float(freqs[fi.min()]), 4)
            out["fmax"] = round(float(freqs[fi.max()]), 4)
            out["tmin"] = round(float(times[ti.min()]), 4)
            out["tmax"] = round(float(times[ti.max()]), 4)
    out["n_points"] = int(m.sum())
    return out


def run_group_compare(
    a_data_infos: list[dict[str, Any]],
    b_data_infos: list[dict[str, Any]],
    params: dict[str, Any],
) -> dict[str, Any]:
    """两组 unit_stack 做统计比较 → stat_map dict(可传给 io.save_stat_map_npz / summarize_stat_map)。"""
    import numpy as np  # noqa: PLC0415

    a_group = _pool_side(a_data_infos, params, "a")
    b_group = _pool_side(b_data_infos, params, "b")
    aligned = _align_two(a_group, b_group)

    base_type = aligned["base_type"]
    A = aligned["a_data"]  # (n_a, n_ch, *feature)
    B = aligned["b_data"]  # (n_b, n_ch, *feature)
    ch_names = aligned["ch_names"]
    times = aligned["times"]
    freqs = aligned["freqs"]

    design = str(params.get("design") or "independent").lower()
    if design not in ("paired", "independent"):
        raise ValueError("Group Compare.design 必须是 paired 或 independent。")
    method = str(params.get("method") or "pointwise").lower()
    tail = str(params.get("tail") or "two-sided").lower()
    if tail not in _TAIL_INT:
        tail = "two-sided"
    alpha = float(params.get("alpha", 0.05) or 0.05)
    correction = str(params.get("correction") or "fdr").lower()

    n_a = int(A.shape[0])
    n_b = int(B.shape[0])
    if n_a < 2 or n_b < 2:
        raise ValueError(f"统计需每组至少 2 个 unit(A={n_a}, B={n_b})。先 Group Merge 多个被试。")
    if design == "paired" and n_a != n_b:
        raise ValueError(
            f"配对设计要求两组 unit 数相等且一一对应(A={n_a}, B={n_b})。"
            "如两组被试不同,请改用 independent。"
        )

    # ---------- 逐点 t(全通道×feature),给完整 t 图 ----------
    from scipy import stats as _stats  # noqa: PLC0415

    alt = _TAIL_ALT[tail]
    if design == "paired":
        res = _stats.ttest_rel(A, B, axis=0, alternative=alt)
    else:
        res = _stats.ttest_ind(A, B, axis=0, equal_var=False, alternative=alt)
    tmap = np.nan_to_num(np.asarray(res.statistic, dtype=float), nan=0.0)
    pmap = np.nan_to_num(np.asarray(res.pvalue, dtype=float), nan=1.0)

    if correction == "fdr":
        from mne.stats import fdr_correction  # noqa: PLC0415

        reject, _ = fdr_correction(pmap, alpha=alpha)
        sig = np.asarray(reject, dtype=bool)
    else:
        correction = "none"
        sig = pmap < alpha

    mean_a = A.mean(axis=0)
    mean_b = B.mean(axis=0)

    result: dict[str, Any] = {
        "base_type": base_type,
        "ch_names": ch_names,
        "ch_types": aligned["ch_types"],
        "times": times,
        "freqs": freqs,
        "sfreq": aligned["sfreq"],
        "tmap": tmap,
        "pmap": pmap,
        "sig": sig,
        "mean_a": mean_a,
        "mean_b": mean_b,
        "design": design,
        "method": method,
        "tail": tail,
        "correction": correction,
        "alpha": alpha,
        "contrast_label": _contrast_label(a_group, b_group, params),
        "n_a": n_a,
        "n_b": n_b,
        "roi_channels": [],
        "roi_axis": "",
        "cluster_masks": None,
        "cluster_pvals": [],
        "cluster_summary": [],
    }

    # ---------- 可选:ROI cluster permutation(沿连续轴,montage-free) ----------
    if method == "cluster":
        _run_cluster(result, A, B, ch_names, times, freqs, base_type, design, tail, alpha, params)

    return result


def _run_cluster(
    result: dict[str, Any],
    A: Any,
    B: Any,
    ch_names: list[str],
    times: Any,
    freqs: Any,
    base_type: str,
    design: str,
    tail: str,
    alpha: float,
    params: dict[str, Any],
) -> None:
    import numpy as np  # noqa: PLC0415

    roi = params.get("cluster_channels")
    if isinstance(roi, list) and roi:
        roi_names = [c for c in (str(x) for x in roi) if c in set(ch_names)]
    else:
        roi_names = list(ch_names)
    if not roi_names:
        roi_names = list(ch_names)
    roi_idx = [ch_names.index(c) for c in roi_names]

    roi_a = A[:, roi_idx, ...].mean(axis=1)  # (n_a, *continuous)
    roi_b = B[:, roi_idx, ...].mean(axis=1)  # (n_b, *continuous)

    n_perm = int(params.get("n_permutations", 1000) or 1000)
    threshold = params.get("cluster_threshold")
    threshold = float(threshold) if threshold not in (None, "") else None

    from mne.stats import (  # noqa: PLC0415
        permutation_cluster_1samp_test,
        permutation_cluster_test,
    )

    if design == "paired":
        tail_int = _TAIL_INT[tail]
        t_obs, clusters, cluster_pv, _ = permutation_cluster_1samp_test(
            roi_a - roi_b,
            n_permutations=n_perm,
            threshold=threshold,
            tail=tail_int,
            out_type="indices",
            seed=42,
            verbose="ERROR",
        )
    else:
        # 独立两组用 F 统计(非负),tail 恒 1;F 本身已是"任意方向差异"的双侧含义。
        t_obs, clusters, cluster_pv, _ = permutation_cluster_test(
            [roi_a, roi_b],
            n_permutations=n_perm,
            threshold=threshold,
            tail=1,
            out_type="indices",
            seed=42,
            verbose="ERROR",
        )

    cluster_pv = np.asarray(cluster_pv, dtype=float)
    # clusters 是「索引/slice 元组」列表(out_type=indices,跨 MNE 版本最稳)。用 mask[cl]=True
    # 还原成连续网格上的布尔掩码——无论 cl 是 slice 元组还是 index 数组元组都通用(MNE 官方惯用法)。
    grid_shape = np.asarray(t_obs).shape
    masks: list[Any] = []
    for cl in clusters:
        m = np.zeros(grid_shape, dtype=bool)
        m[cl] = True
        masks.append(m)
    summary: list[dict[str, Any]] = []
    for i, m in enumerate(masks):
        pv = float(cluster_pv[i]) if i < cluster_pv.size else 1.0
        desc = _describe_cluster(m, base_type, times, freqs)
        desc["p"] = round(pv, 4)
        desc["significant"] = bool(pv < alpha)
        summary.append(desc)
    # 按 p 升序,显著者在前
    summary_sorted = sorted(range(len(summary)), key=lambda i: summary[i]["p"])

    masks_sorted = [masks[i] for i in summary_sorted]
    pvals_sorted = [
        float(cluster_pv[i]) if i < cluster_pv.size else 1.0 for i in summary_sorted
    ]

    result["roi_channels"] = roi_names
    result["roi_axis"] = _roi_axis_name(base_type)
    result["cluster_masks"] = np.stack(masks_sorted, axis=0) if masks_sorted else None
    result["cluster_pvals"] = pvals_sorted
    result["cluster_summary"] = [summary[i] for i in summary_sorted]


def _contrast_label(a_group: dict[str, Any], b_group: dict[str, Any], params: dict[str, Any]) -> str:
    la = str(params.get("label_a") or a_group.get("label") or "A")
    lb = str(params.get("label_b") or b_group.get("label") or "B")
    return f"{la} − {lb}"
