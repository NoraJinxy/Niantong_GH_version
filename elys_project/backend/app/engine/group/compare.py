"""
Purpose: Group analysis – 通用统计比较。两组 unit_stack(A/B)沿 unit 轴做检验 → stat_map。
         通吃 evoked/psd/tfr:统计只对 unit 轴动手、与形态无关(同 merge/average 的统一抽象)。
Related: app/engine/group/stack.py, app/pipeline/dispatcher.py (_execute_group_compare), app/engine/io.py.

两类方法:
- pointwise: 每个 feature 点(通道×时间/频率)逐点 t——配对 ttest_rel / 独立 ttest_ind(Welch),
  none / FDR(BH)多重比较校正 → 完整 t 图 + 显著掩码。
- cluster: MNE cluster permutation。支持 ROI 平均、single-sensor、multi-sensor 三种模式;
  配对走差值 1-sample t,独立走 Welch t stat_fun,可按方向/tail 做成簇检验。
"""

from __future__ import annotations

from typing import Any

from app.engine.analysis.event_conditions import normalize_marker_label
from app.engine.group.stack import _assert_axis_match, align_and_stack, extract_block


_TAIL_ALT = {"two-sided": "two-sided", "greater": "greater", "less": "less"}
_TAIL_INT = {"two-sided": 0, "greater": 1, "less": -1}
_CLUSTER_MODES = {"roi", "single_sensor", "multi_sensor"}


_NO_CONDITION_KEY = "__all__"


def _condition_key(value: Any) -> str:
    text = " ".join(normalize_marker_label(value).split())
    return text.lower()


def _known_condition(value: Any) -> str:
    text = normalize_marker_label(value)
    return "" if not text or text.lower() == "unknown" else text


def _block_condition(block: dict[str, Any]) -> str:
    condition = _known_condition(block.get("condition"))
    if condition:
        return condition
    unit_conditions = [_known_condition(item) for item in list(block.get("unit_conditions") or [])]
    unit_conditions = [item for item in unit_conditions if item]
    if unit_conditions and len({_condition_key(item) for item in unit_conditions}) == 1:
        return unit_conditions[0]
    for key in ("label", "group_label"):
        value = _known_condition(block.get(key))
        if value:
            return value
    return ""


def _format_conditions(groups: dict[str, dict[str, Any]]) -> str:
    labels = [str(group.get("condition") or "未标注") for group in groups.values()]
    return ", ".join(labels) if labels else "无"


def _pool_blocks(
    blocks: list[dict[str, Any]],
    params: dict[str, Any],
    *,
    label_key: str,
    condition: str = "",
) -> dict[str, Any]:
    stack_params = dict(params)
    if condition:
        stack_params["condition"] = condition
    group = align_and_stack(blocks, stack_params)
    # align_and_stack 用 compare 节点的 params.label(通常空)→ 这里回填输入 unit_stack 自带的组标签。
    if condition and not _known_condition(group.get("condition")):
        group["condition"] = condition
    if not group.get("label"):
        for blk in blocks:
            if blk.get("label"):
                group["label"] = blk["label"]
                break
    if condition and group.get("label") in {"", "unknown", None}:
        group["label"] = condition
    group["_compare_side"] = label_key
    return group


def _pool_side_by_condition(
    data_infos: list[dict[str, Any]],
    params: dict[str, Any],
    label_key: str,
) -> dict[str, dict[str, Any]]:
    """把端口收到的 unit_stack 先按 condition 分桶，再在桶内沿 unit 轴合并。"""
    if not data_infos:
        raise ValueError(f"Group Compare: 端口 {label_key} 没有收到上游 unit_stack。")
    blocks = [extract_block(di) for di in data_infos]
    selected_key = _condition_key(params.get("condition"))

    buckets: dict[str, dict[str, Any]] = {}
    for block in blocks:
        condition = _block_condition(block)
        key = _condition_key(condition) or _NO_CONDITION_KEY
        if selected_key and key != selected_key:
            continue
        bucket = buckets.setdefault(key, {"condition": condition, "blocks": []})
        if not bucket.get("condition") and condition:
            bucket["condition"] = condition
        bucket["blocks"].append(block)

    if selected_key and not buckets:
        available = sorted({_block_condition(block) or "未标注" for block in blocks})
        raise ValueError(
            f"Group Compare: 端口 {label_key} 没有条件 {params.get('condition')!r}；"
            f"可用条件: {', '.join(available)}。"
        )

    return {
        key: _pool_blocks(
            list(bucket["blocks"]),
            params,
            label_key=label_key,
            condition=_known_condition(bucket.get("condition")),
        )
        for key, bucket in buckets.items()
    }


def _select_condition_keys(
    a_groups: dict[str, dict[str, Any]],
    b_groups: dict[str, dict[str, Any]],
    params: dict[str, Any],
) -> list[str]:
    selected = _condition_key(params.get("condition"))
    if selected:
        if selected not in a_groups or selected not in b_groups:
            raise ValueError(
                "Group Compare: 指定条件在 A/B 两侧未同时出现；"
                f"A={_format_conditions(a_groups)}，B={_format_conditions(b_groups)}。"
            )
        return [selected]

    a_keys = set(a_groups)
    b_keys = set(b_groups)
    if a_keys != b_keys:
        only_a = [str(a_groups[key].get("condition") or "未标注") for key in sorted(a_keys - b_keys)]
        only_b = [str(b_groups[key].get("condition") or "未标注") for key in sorted(b_keys - a_keys)]
        raise ValueError(
            "Group Compare: A/B 两侧条件集合不一致；"
            f"仅 A 有: {', '.join(only_a) or '无'}；仅 B 有: {', '.join(only_b) or '无'}。"
            "请在条件参数中指定一个共有条件，或让两侧 Group Merge 输出相同条件。"
        )
    return [key for key in a_groups.keys() if key in b_groups]


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


def _feature_mask_dims(base_type: str) -> list[str]:
    return {"evoked": ["times"], "psd": ["freqs"], "tfr": ["freqs", "times"]}.get(base_type, [])


def _full_mask_dims(base_type: str) -> list[str]:
    dims = _feature_mask_dims(base_type)
    return ["channels", *dims] if dims else ["channels"]


def _normalize_cluster_mode(params: dict[str, Any]) -> str:
    mode = str(params.get("cluster_mode") or "roi").strip().lower()
    aliases = {
        "roi_mean": "roi",
        "roi-average": "roi",
        "single": "single_sensor",
        "single-sensor": "single_sensor",
        "sensor": "single_sensor",
        "multi": "multi_sensor",
        "multi-sensor": "multi_sensor",
        "spatio_temporal": "multi_sensor",
    }
    mode = aliases.get(mode, mode)
    if mode not in _CLUSTER_MODES:
        raise ValueError("cluster_mode 必须是 roi、single_sensor 或 multi_sensor。")
    return mode


def _parse_cluster_channels(raw: Any, ch_names: list[str]) -> list[str]:
    """解析 ROI 通道:兼容前端字符串(Pz,POz)与数组。空值表示全通道。"""
    import re  # noqa: PLC0415

    if isinstance(raw, str):
        items = [part.strip() for part in re.split(r"[,，;；\s]+", raw) if part.strip()]
    elif isinstance(raw, (list, tuple, set)):
        items = [str(part).strip() for part in raw if str(part).strip()]
    else:
        items = []
    if not items:
        return list(ch_names)
    by_lower = {name.lower(): name for name in ch_names}
    resolved: list[str] = []
    missing: list[str] = []
    for item in items:
        name = by_lower.get(item.lower())
        if name and name not in resolved:
            resolved.append(name)
        else:
            missing.append(item)
    if missing:
        raise ValueError(f"cluster_channels 包含不存在的通道: {', '.join(missing[:8])}")
    return resolved or list(ch_names)


def _feature_window(mask: Any, base_type: str, times: Any, freqs: Any) -> dict[str, Any]:
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
        fi, ti = np.where(m)
        if fi.size:
            out["fmin"] = round(float(freqs[fi.min()]), 4)
            out["fmax"] = round(float(freqs[fi.max()]), 4)
            out["tmin"] = round(float(times[ti.min()]), 4)
            out["tmax"] = round(float(times[ti.max()]), 4)
    return out


def _describe_cluster(
    mask: Any,
    base_type: str,
    times: Any,
    freqs: Any,
    *,
    mask_dims: list[str] | None = None,
    ch_names: list[str] | None = None,
) -> dict[str, Any]:
    """把一个 cluster 的布尔掩码翻成可读窗口(时间/频率范围)。"""
    import numpy as np  # noqa: PLC0415

    m = np.asarray(mask, dtype=bool)
    dims = list(mask_dims or _feature_mask_dims(base_type))
    out: dict[str, Any] = {}
    feature_mask = m
    if dims and dims[0] == "channels" and m.ndim >= 2:
        channel_hits = m.reshape(m.shape[0], -1).any(axis=1)
        indices = np.where(channel_hits)[0]
        names = [str(ch_names[i]) for i in indices if ch_names and i < len(ch_names)]
        out["n_channels"] = int(indices.size)
        if names:
            out["channels"] = names
            out["channel"] = names[0] if len(names) == 1 else ""
        feature_mask = m.any(axis=0)
    out.update(_feature_window(feature_mask, base_type, times, freqs))
    out["n_points"] = int(m.sum())
    return out


def _validate_paired_identity(a_group: dict[str, Any], b_group: dict[str, Any]) -> None:
    """有 subject 元数据时校验配对顺序,避免 A/B 被试顺序错位后静默跑出假结果。"""
    a_subjects = [str(x).strip() for x in list(a_group.get("unit_subjects") or [])]
    b_subjects = [str(x).strip() for x in list(b_group.get("unit_subjects") or [])]
    if not a_subjects or not b_subjects:
        return
    if len(a_subjects) != len(b_subjects):
        return
    # 只有两边都能提供完整 subject 时才强校验;历史/合成 unit_stack 缺标签时仍按顺序配对。
    if any(not x or x == "unknown" for x in a_subjects + b_subjects):
        return
    mismatches = [
        f"{i + 1}:{a_subjects[i]}≠{b_subjects[i]}"
        for i in range(len(a_subjects))
        if a_subjects[i] != b_subjects[i]
    ]
    if mismatches:
        sample = ", ".join(mismatches[:8])
        raise ValueError(f"配对设计的 A/B unit_subjects 顺序不一致: {sample}。请先按同一被试顺序 Group Merge。")


def _welch_t_stat(a: Any, b: Any) -> Any:
    import numpy as np  # noqa: PLC0415
    from scipy import stats as _stats  # noqa: PLC0415

    res = _stats.ttest_ind(a, b, axis=0, equal_var=False)
    return np.nan_to_num(np.asarray(res.statistic, dtype=float), nan=0.0, posinf=0.0, neginf=0.0)


def _cluster_threshold(raw: Any, *, tail: str, alpha: float, df: int) -> float:
    from scipy import stats as _stats  # noqa: PLC0415

    tail_int = _TAIL_INT.get(tail, 0)
    if raw not in (None, ""):
        value = float(raw)
        if tail_int < 0 and value > 0:
            value = -value
        return value
    safe_df = max(1, int(df))
    p = float(alpha) / (2 if tail_int == 0 else 1)
    threshold = float(_stats.t.ppf(1.0 - p, safe_df))
    return -threshold if tail_int < 0 else threshold


def _run_mne_cluster(
    A: Any,
    B: Any,
    *,
    design: str,
    tail: str,
    alpha: float,
    n_perm: int,
    threshold_raw: Any,
    adjacency: Any = None,
) -> tuple[Any, Any, Any]:
    """统一调用 MNE cluster。独立组使用 Welch t,不再落到默认 F 检验。"""
    from mne.stats import permutation_cluster_1samp_test, permutation_cluster_test  # noqa: PLC0415

    tail_int = _TAIL_INT.get(tail, 0)
    if design == "paired":
        df = int(A.shape[0]) - 1
        threshold = _cluster_threshold(threshold_raw, tail=tail, alpha=alpha, df=df)
        return permutation_cluster_1samp_test(
            A - B,
            n_permutations=n_perm,
            threshold=threshold,
            tail=tail_int,
            adjacency=adjacency,
            out_type="indices",
            seed=42,
            verbose="ERROR",
        )[:3]

    df = int(A.shape[0]) + int(B.shape[0]) - 2
    threshold = _cluster_threshold(threshold_raw, tail=tail, alpha=alpha, df=df)
    return permutation_cluster_test(
        [A, B],
        n_permutations=n_perm,
        threshold=threshold,
        tail=tail_int,
        stat_fun=_welch_t_stat,
        adjacency=adjacency,
        out_type="indices",
        seed=42,
        verbose="ERROR",
    )[:3]


def _mask_from_cluster(cluster: Any, shape: tuple[int, ...]) -> Any:
    import numpy as np  # noqa: PLC0415

    mask = np.zeros(shape, dtype=bool)
    mask[cluster] = True
    return mask


def _sort_cluster_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(records, key=lambda item: float(item["p"]))


def run_group_compare(
    a_data_infos: list[dict[str, Any]],
    b_data_infos: list[dict[str, Any]],
    params: dict[str, Any],
) -> dict[str, Any] | list[dict[str, Any]]:
    """两组 unit_stack 做统计比较 → 一个或多个 stat_map。

    Group Merge 默认会按 condition 拆出多份 unit_stack。Compare 接到两侧多份 stack 时，
    先按 condition 配对；若有多个共有 condition，就逐条件输出多张 stat_map。
    """
    a_groups = _pool_side_by_condition(a_data_infos, params, "a")
    b_groups = _pool_side_by_condition(b_data_infos, params, "b")
    condition_keys = _select_condition_keys(a_groups, b_groups, params)

    results = [
        _run_group_compare_one(
            a_groups[key],
            b_groups[key],
            params,
            condition=_known_condition(a_groups[key].get("condition") or b_groups[key].get("condition")),
        )
        for key in condition_keys
    ]
    return results[0] if len(results) == 1 else results


def _run_group_compare_one(
    a_group: dict[str, Any],
    b_group: dict[str, Any],
    params: dict[str, Any],
    *,
    condition: str = "",
) -> dict[str, Any]:
    """两组已按 condition 对齐的 unit_stack 做统计比较。"""
    import numpy as np  # noqa: PLC0415

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
    if design == "paired":
        _validate_paired_identity(a_group, b_group)

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
        "condition": condition,
        "contrast_label": _contrast_label(a_group, b_group, params, condition=condition),
        "n_a": n_a,
        "n_b": n_b,
        "roi_channels": [],
        "roi_axis": "",
        "cluster_mode": "",
        "cluster_stat": "",
        "cluster_mask_dims": [],
        "cluster_adjacency": "",
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

    cluster_mode = _normalize_cluster_mode(params)
    n_perm = int(params.get("n_permutations", 1000) or 1000)
    threshold_raw = params.get("cluster_threshold")

    result["cluster_mode"] = cluster_mode
    result["cluster_stat"] = "welch_t" if design == "independent" else "paired_t"
    result["roi_axis"] = _roi_axis_name(base_type)

    if cluster_mode == "roi":
        records = _run_roi_cluster(A, B, ch_names, times, freqs, base_type, design, tail, alpha, params, n_perm, threshold_raw)
        result["roi_channels"] = records["roi_channels"]
        result["cluster_mask_dims"] = _feature_mask_dims(base_type)
        result["cluster_adjacency"] = "feature_lattice"
        masks = records["masks"]
        summary = records["summary"]
    elif cluster_mode == "single_sensor":
        records = _run_single_sensor_cluster(A, B, ch_names, times, freqs, base_type, design, tail, alpha, n_perm, threshold_raw)
        result["roi_channels"] = []
        result["cluster_mask_dims"] = _full_mask_dims(base_type)
        result["cluster_adjacency"] = "per_channel_feature_lattice"
        masks = records["masks"]
        summary = records["summary"]
    else:
        records = _run_multi_sensor_cluster(A, B, ch_names, times, freqs, base_type, design, tail, alpha, n_perm, threshold_raw, result.get("sfreq"))
        result["roi_channels"] = []
        result["cluster_mask_dims"] = _full_mask_dims(base_type)
        result["cluster_adjacency"] = "standard_1005_delaunay"
        masks = records["masks"]
        summary = records["summary"]

    result["cluster_masks"] = np.stack(masks, axis=0) if masks else None
    result["cluster_pvals"] = [float(item.pop("_p_raw", item["p"])) for item in summary]
    result["cluster_summary"] = summary


def _run_roi_cluster(
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
    n_perm: int,
    threshold_raw: Any,
) -> dict[str, Any]:
    import numpy as np  # noqa: PLC0415

    roi_names = _parse_cluster_channels(params.get("cluster_channels"), ch_names)
    roi_idx = [ch_names.index(c) for c in roi_names]
    roi_a = A[:, roi_idx, ...].mean(axis=1)
    roi_b = B[:, roi_idx, ...].mean(axis=1)
    t_obs, clusters, cluster_pv = _run_mne_cluster(
        roi_a,
        roi_b,
        design=design,
        tail=tail,
        alpha=alpha,
        n_perm=n_perm,
        threshold_raw=threshold_raw,
    )
    grid_shape = tuple(np.asarray(t_obs).shape)
    records: list[dict[str, Any]] = []
    for i, cl in enumerate(clusters):
        mask = _mask_from_cluster(cl, grid_shape)
        p = float(cluster_pv[i]) if i < len(cluster_pv) else 1.0
        desc = _describe_cluster(mask, base_type, times, freqs, mask_dims=_feature_mask_dims(base_type))
        desc.update({"p": round(p, 4), "_p_raw": p, "significant": bool(p < alpha), "mask": mask})
        records.append(desc)
    records = _sort_cluster_records(records)
    return {
        "roi_channels": roi_names,
        "masks": [item.pop("mask") for item in records],
        "summary": records,
    }


def _run_single_sensor_cluster(
    A: Any,
    B: Any,
    ch_names: list[str],
    times: Any,
    freqs: Any,
    base_type: str,
    design: str,
    tail: str,
    alpha: float,
    n_perm: int,
    threshold_raw: Any,
) -> dict[str, Any]:
    import numpy as np  # noqa: PLC0415

    full_shape = tuple(np.asarray(A).shape[1:])
    mask_dims = _full_mask_dims(base_type)
    records: list[dict[str, Any]] = []
    for ch_index, ch_name in enumerate(ch_names):
        t_obs, clusters, cluster_pv = _run_mne_cluster(
            A[:, ch_index, ...],
            B[:, ch_index, ...],
            design=design,
            tail=tail,
            alpha=alpha,
            n_perm=n_perm,
            threshold_raw=threshold_raw,
        )
        feature_shape = tuple(np.asarray(t_obs).shape)
        for i, cl in enumerate(clusters):
            feature_mask = _mask_from_cluster(cl, feature_shape)
            full_mask = np.zeros(full_shape, dtype=bool)
            full_mask[ch_index, ...] = feature_mask
            p = float(cluster_pv[i]) if i < len(cluster_pv) else 1.0
            desc = _describe_cluster(
                full_mask,
                base_type,
                times,
                freqs,
                mask_dims=mask_dims,
                ch_names=ch_names,
            )
            desc.update({"p": round(p, 4), "_p_raw": p, "significant": bool(p < alpha), "mask": full_mask})
            if "channels" not in desc:
                desc["channels"] = [ch_name]
                desc["channel"] = ch_name
                desc["n_channels"] = 1
            records.append(desc)
    records = _sort_cluster_records(records)
    return {"masks": [item.pop("mask") for item in records], "summary": records}


def _cluster_input_channels_last(data: Any) -> Any:
    import numpy as np  # noqa: PLC0415

    return np.moveaxis(np.asarray(data, dtype=float), 1, -1)


def _cluster_mask_channels_first(mask: Any) -> Any:
    import numpy as np  # noqa: PLC0415

    return np.moveaxis(np.asarray(mask, dtype=bool), -1, 0)


def _build_channel_adjacency(ch_names: list[str], sfreq: Any) -> Any:
    import numpy as np  # noqa: PLC0415
    import mne  # noqa: PLC0415

    if len(ch_names) < 2:
        raise ValueError("multi_sensor cluster 至少需要 2 个通道。")
    info = mne.create_info(ch_names=list(ch_names), sfreq=float(sfreq or 1.0), ch_types=["eeg"] * len(ch_names))
    montage = mne.channels.make_standard_montage("standard_1005")
    info.set_montage(montage, match_case=False, on_missing="ignore")
    locs = np.asarray([ch["loc"][:3] for ch in info["chs"]], dtype=float)
    missing = [
        ch_names[i]
        for i, loc in enumerate(locs)
        if (not np.isfinite(loc).all()) or float(np.linalg.norm(loc)) == 0.0
    ]
    if missing:
        raise ValueError(
            "multi_sensor cluster 需要可识别的标准 10-05/10-20 电极位置; "
            f"以下通道缺少坐标: {', '.join(missing[:10])}"
        )
    adjacency, adj_names = mne.channels.find_ch_adjacency(info, "eeg")
    if list(adj_names) != list(ch_names):
        order = [list(adj_names).index(name) for name in ch_names]
        adjacency = adjacency[order, :][:, order]
    return adjacency


def _build_multi_adjacency(base_type: str, A_mne: Any, ch_names: list[str], sfreq: Any) -> Any:
    from mne.stats import combine_adjacency  # noqa: PLC0415

    ch_adj = _build_channel_adjacency(ch_names, sfreq)
    shape = tuple(A_mne.shape[1:])
    if base_type in ("evoked", "psd"):
        return combine_adjacency(shape[0], ch_adj)
    if base_type == "tfr":
        return combine_adjacency(shape[0], shape[1], ch_adj)
    raise ValueError(f"Unsupported base_type for multi_sensor cluster: {base_type}")


def _run_multi_sensor_cluster(
    A: Any,
    B: Any,
    ch_names: list[str],
    times: Any,
    freqs: Any,
    base_type: str,
    design: str,
    tail: str,
    alpha: float,
    n_perm: int,
    threshold_raw: Any,
    sfreq: Any,
) -> dict[str, Any]:
    import numpy as np  # noqa: PLC0415

    A_mne = _cluster_input_channels_last(A)
    B_mne = _cluster_input_channels_last(B)
    adjacency = _build_multi_adjacency(base_type, A_mne, ch_names, sfreq)
    t_obs, clusters, cluster_pv = _run_mne_cluster(
        A_mne,
        B_mne,
        design=design,
        tail=tail,
        alpha=alpha,
        n_perm=n_perm,
        threshold_raw=threshold_raw,
        adjacency=adjacency,
    )
    mne_shape = tuple(np.asarray(t_obs).shape)
    mask_dims = _full_mask_dims(base_type)
    records: list[dict[str, Any]] = []
    for i, cl in enumerate(clusters):
        mne_mask = _mask_from_cluster(cl, mne_shape)
        full_mask = _cluster_mask_channels_first(mne_mask)
        p = float(cluster_pv[i]) if i < len(cluster_pv) else 1.0
        desc = _describe_cluster(
            full_mask,
            base_type,
            times,
            freqs,
            mask_dims=mask_dims,
            ch_names=ch_names,
        )
        desc.update({"p": round(p, 4), "_p_raw": p, "significant": bool(p < alpha), "mask": full_mask})
        records.append(desc)
    records = _sort_cluster_records(records)
    return {"masks": [item.pop("mask") for item in records], "summary": records}


def _contrast_label(
    a_group: dict[str, Any],
    b_group: dict[str, Any],
    params: dict[str, Any],
    *,
    condition: str = "",
) -> str:
    la = str(params.get("label_a") or a_group.get("group_label") or a_group.get("label") or "A")
    lb = str(params.get("label_b") or b_group.get("group_label") or b_group.get("label") or "B")
    if condition and _condition_key(la) == _condition_key(condition) and _condition_key(lb) == _condition_key(condition):
        la, lb = "A", "B"
    base = f"{la} − {lb}"
    if condition and _condition_key(condition) not in _condition_key(base):
        return f"{base} · {condition}"
    return base
