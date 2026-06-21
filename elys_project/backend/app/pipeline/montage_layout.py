"""
Purpose: 通道 2D 头皮投影坐标的共享助手——把电极 3D 坐标投到单位圆内供地形图 / ICA 成分图用。
         内嵌 montage 优先；缺失时按通道名兜底匹配 MNE 标准帽（standard_1005 / 1020）。
Related: app/pipeline/timeseries.py（时域看图地形图条）, app/pipeline/ica_inspect.py（ICA 成分地形图）。
         无重依赖（只 lazy import mne / numpy），故 ica_inspect 可自由复用，不会被 previews 链拖进 DB/config。
"""

from __future__ import annotations

from typing import Any


def _mne():
    try:
        import mne
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("MNE is required for montage layout.") from exc
    return mne


def _numpy():
    try:
        import numpy
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("NumPy is required for montage layout.") from exc
    return numpy


def valid_xyz(np, xyz):
    """把任意坐标输入校验为有限、非全零的 3D 向量；不合法 → None。"""
    if xyz is None:
        return None
    a = np.asarray(xyz, dtype="float64").ravel()
    if a.shape[0] < 3 or not np.all(np.isfinite(a[:3])) or np.allclose(a[:3], 0.0):
        return None
    return a[:3]


def norm_ch_key(name) -> str:
    """通道名归一化：大写、只留字母数字（Fp1 / FP1 / 'EEG Fp1' → FP1），供跨命名匹配标准帽。"""
    return "".join(ch for ch in str(name or "").upper() if ch.isalnum())


_STD_MONTAGE_NAMES = ("standard_1005", "standard_1020")
_STD_POS_CACHE: dict[str, Any] = {}


def standard_montage_lookup(np) -> dict[str, Any]:
    """归一化通道名 → MNE 标准帽 3D 坐标（standard_1005 优先、1020 补充），进程内缓存。

    供"未带 montage 的数据"兜底定位：拿标准 10-05/10-20 模板坐标而非真实数字化坐标，
    用于观察用地形图足够（同 EEGLAB 的 look-up standard locations 思路）。
    """
    if _STD_POS_CACHE:
        return _STD_POS_CACHE
    mne = _mne()
    for mname in _STD_MONTAGE_NAMES:
        try:
            montage = mne.channels.make_standard_montage(mname)
            ch_pos = (montage.get_positions() or {}).get("ch_pos") or {}
        except Exception:
            continue
        for std_name, pos in ch_pos.items():
            key = norm_ch_key(std_name)
            if not key or key in _STD_POS_CACHE:
                continue
            a = valid_xyz(np, pos)
            if a is not None:
                _STD_POS_CACHE[key] = a
    return _STD_POS_CACHE


def collect_positions(np, info, names) -> dict[str, Any]:
    """收集通道 3D 坐标：优先用内嵌 montage；取不到（<3）再按通道名匹配标准帽兜底。

    两路坐标不混用——内嵌够数就全用内嵌（用户真实数字化坐标），否则整组退回标准帽模板，
    避免不同 montage 尺度混叠。
    """
    try:
        montage = info.get_montage()
        embedded = (montage.get_positions() or {}).get("ch_pos") if montage is not None else {}
        embedded = embedded or {}
    except Exception:
        embedded = {}
    pts: dict[str, Any] = {}
    for nm in names:
        a = valid_xyz(np, embedded.get(nm))
        if a is not None:
            pts[nm] = a
    if len(pts) >= 3:
        return pts
    # 兜底：内嵌 montage 不可用，按归一化名匹配标准帽
    lookup = standard_montage_lookup(np)
    fallback: dict[str, Any] = {}
    for nm in names:
        a = lookup.get(norm_ch_key(nm))
        if a is not None:
            fallback[nm] = a
    return fallback if len(fallback) >= 3 else pts


def channel_positions_2d(info, names) -> dict[str, list[float]] | None:
    """提取通道 2D 头皮投影坐标（单位圆内，+x=右、+y=前）供地形图用；取不到 → None。

    优先用 **MNE plot_topomap 同款投影**（`_find_topomap_coords`）——主流外圈电极（Fpz/Oz/T7…）
    落在接近头罩圆边，不会被耳后/下方个别极端电极（P9/P10/Iz）把整组压缩到圆心（旧手写「按最大极角
    归一」就栽在这：极端电极撑大 theta_max，主流电极只到 ~0.75 圆半径、看着缩了一圈）。
    MNE 投影不可用（缺 montage、别名电极重叠等）时回退手写方位等距。全程 try/except，拿不到只是
    没有地形图、绝不影响主数据。坐标来源：内嵌 montage 优先，缺失时按名兜底标准帽（见 collect_positions）。
    """
    try:
        np = _numpy()
        xy = _mne_topomap_xy(np, info, names)
        if xy is not None:
            return xy
        return _azimuthal_fallback_xy(np, info, names)
    except Exception:
        return None


def _mne_topomap_xy(np, info, names) -> dict[str, list[float]] | None:
    """MNE `plot_topomap` 同款投影：把 info 里 picks 的传感器位置投到 2D，主流外圈电极
    （Fpz/Oz/T7…）顶到头罩圆边（~1.0 半径）。失败 → None。

    归一化基准用半径的 **95 分位**而非绝对最大值：biosemi64 实测里只有 Iz/P9/P10 这三颗
    枕下/耳后极端电极独占最大半径，主流外圈（含 Oz）只到它们的 ~0.904——若按 max 归一，
    主流圈就被压到 ~0.81 圆内「缩一圈」。改按 95 分位（≈主流外圈那一环）归一后，Oz 等直接
    顶到 ~1.0（贴圆边）；放大后那几颗枕下/耳后极端电极**自然落到圆外一点（~1.11，用户接受、同 MNE：
    低位电极落在 head outline 外）**，仅对离谱坐标钳到 1.15 防越出 viewBox。无极端电极的
    稀疏帽（10-20）下 95 分位≈max，行为不变。"""
    try:
        from mne.channels.layout import _find_topomap_coords  # type: ignore
    except Exception:
        return None
    try:
        wanted = set(names)
        picks = [i for i, ch in enumerate(info["ch_names"]) if ch in wanted]
        if len(picks) < 3:
            return None
        coords = np.asarray(_find_topomap_coords(info, picks=picks), dtype="float64")
        if coords.ndim != 2 or coords.shape[0] != len(picks):
            return None
        rr = np.hypot(coords[:, 0], coords[:, 1])
        r_ref = float(np.percentile(rr, 95.0))
        if not np.isfinite(r_ref) or r_ref <= 0:
            r_ref = float(rr.max())
        if not np.isfinite(r_ref) or r_ref <= 0:
            return None
        scale = 1.0 / r_ref
        out: dict[str, list[float]] = {}
        for k, idx in enumerate(picks):
            x = float(coords[k, 0]) * scale
            y = float(coords[k, 1]) * scale
            r = float(np.hypot(x, y))
            if r > 1.15:  # 只防离谱坐标越出 viewBox；主流圈到 0.95，个别枕下/耳后极端电极自然落圆外一点（用户可接受、同 MNE 低位电极落 head outline 外）
                f = 1.15 / r
                x *= f
                y *= f
            out[info["ch_names"][idx]] = [round(x, 4), round(y, 4)]
        return out or None
    except Exception:
        # 别名电极重叠 / 缺 montage / 跨版本 API 变动等 → 交回退处理
        return None


def _azimuthal_fallback_xy(np, info, names) -> dict[str, list[float]] | None:
    """回退：手写方位等距投影（电极质心为心、按极角 95 分位归一到顶圆边 ~1.0 + 极端电极自然落圆外一点、仅离谱坐标钳 1.15）。
    与 MNE 路同口径（避开极端电极独占 theta_max 把主流圈压缩「缩一圈」）。MNE 投影不可用时才用。"""
    pts = collect_positions(np, info, names)
    if len(pts) < 3:
        return None
    names_list = list(pts.keys())
    arr = np.asarray([pts[nm] for nm in names_list], dtype="float64")
    # 退化点云（电极近共面、z 无展开）→ 方位投影无意义，宁可不画
    z_span = float(np.ptp(arr[:, 2]))
    xy_span = float(max(float(np.ptp(arr[:, 0])), float(np.ptp(arr[:, 1]))) or 1.0)
    if z_span <= 1e-6 * xy_span:
        return None
    center = arr.mean(axis=0)
    thetas: list[float] = []
    phis: list[float] = []
    for xyz in arr:
        v = xyz - center
        norm = float(np.linalg.norm(v))
        if norm <= 0:
            thetas.append(0.0)
            phis.append(0.0)
            continue
        vz = max(-1.0, min(1.0, float(v[2]) / norm))
        thetas.append(float(np.arccos(vz)))
        phis.append(float(np.arctan2(float(v[1]), float(v[0]))))
    theta_ref = float(np.percentile(np.asarray(thetas, dtype="float64"), 95.0)) or (max(thetas) or 1.0)
    out: dict[str, list[float]] = {}
    for nm, th, ph in zip(names_list, thetas, phis):
        r = min(th / theta_ref * 1.0, 1.15)  # 主流圈→顶圆边(1.0)，个别极端电极自然落圆外一点（只防离谱越界）
        out[nm] = [round(r * float(np.cos(ph)), 4), round(r * float(np.sin(ph)), 4)]
    return out or None
