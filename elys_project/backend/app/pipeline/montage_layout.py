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

    坐标来源：内嵌 montage 优先，缺失时按通道名兜底匹配 MNE 标准帽（见 collect_positions）。
    投影用方位等距（azimuthal equidistant）：顶点落圆心、耳缘落边界。纯 numpy，不依赖 MNE 私有 API，
    全程 try/except 兜底——拿不到坐标只是没有地形图，绝不影响调用方主数据。
    """
    try:
        np = _numpy()
        pts = collect_positions(np, info, names)
        if len(pts) < 3:
            return None
        names_list = list(pts.keys())
        arr = np.asarray([pts[nm] for nm in names_list], dtype="float64")
        center = arr.mean(axis=0)
        # 退化点云（电极近共面、z 无展开）→ 方位投影无意义，宁可不画（返回 None 走诚实空态）
        z_span = float(np.ptp(arr[:, 2]))
        xy_span = float(max(float(np.ptp(arr[:, 0])), float(np.ptp(arr[:, 1]))) or 1.0)
        if z_span <= 1e-6 * xy_span:
            return None
        # 相对中心的极角 theta（0=顶点）+ 方位角 phi
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
        theta_max = max(thetas) or 1.0
        # 按最大极角归一保留径向次序（避免下半球电极全堆圆周），再留余量 HEAD_MARGIN：
        # 最外电极落 ~0.9 头半径而非贴死圆边——对标 EEGLAB/MNE（头罩圆比电极分布大一圈；
        # MNE plot_topomap 实测标准帽最外电极在 ~0.906 head_radius、不顶到圈上）。
        HEAD_MARGIN = 0.9
        out: dict[str, list[float]] = {}
        for nm, th, ph in zip(names_list, thetas, phis):
            r = th / theta_max * HEAD_MARGIN
            out[nm] = [round(r * float(np.cos(ph)), 4), round(r * float(np.sin(ph)), 4)]
        return out or None
    except Exception:
        return None
