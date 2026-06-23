"""
Purpose: 导入转 FIF 时自动给 raw 绑定电极位置（montage）。已知放大器 / 电极帽（BioSemi / EGI 等）
         → 套对应厂家模板；认不出 → 退标准 10-20 / 10-05 通用模板；再认不出 → 不绑（留待手动上传）。
Related: app/routers/dataset_imports.py（generate_canonical_fif 在 raw.save 前调用本模块），
         app/engine/preprocess/channel_location.py（流水线手动指派节点，与本模块同源的坐标语义），
         app/engine/preprocess/bad_channels.py（坏道球面样条插值依赖这里绑好的坐标）。

为什么放在导入而不是流水线节点：电极位置是「采集时的设备元数据」，不是分析决策——对标 BIDS
把它放数据集级 sidecar（electrodes.tsv）、EEGLAB 开局就灌 chanlocs。绑在转 FIF 这一刻，
canonical FIF「出生即带坐标」，下游所有节点 / 观察页地形图都天生有坐标，医生 / 心理 persona
无需再认识「通道定位」这个步骤。

识别策略（数据驱动，不硬编码厂家判断）：拿「数据通道名 ↔ 每顶内置帽通道名」的实际重叠打分。
  · BioSemi 命名（A1..H32）只会和 biosemi* 帽高度重叠；
  · EGI 命名（E1..E256）只会和 GSN-HydroCel* / EGI* 帽重叠；
  · 标准 10-20 命名（Fp1/Cz..）只会和 standard_1020 / 1005 重叠。
得分 = (命中道数, 精度)，精度 = 命中 / 帽电极数，避免「64 导数据套上 256 帽」这种虚胖匹配。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

# 候选电极帽家族（靠前 = 更「具体」，仅用于得分并列时兜底排序；真正选谁靠实际名字重叠）。
_FAMILY_PRIORITY = (
    "biosemi",        # BioSemi ActiveTwo（BDF），A1..H32 字母分组命名
    "GSN-HydroCel",   # EGI 测地线传感器网（HydroCel），E1..E257
    "EGI",            # EGI_256
    "easycap",        # easycap-M1 / M10
    "mgh",            # mgh60 / mgh70
    "standard_1005",  # 通用兜底：10-05（10-20 命名的超集）
    "standard_1020",  # 通用兜底：10-20
)

# 命中道数低于此值不绑（多是 Ch1/Ch2 这类无信息命名，硬绑只会得到 1~2 个孤立坐标）。
_MIN_MATCHED = 3


def _norm_ch_key(name: str) -> str:
    """通道名归一化：大写、只留字母数字（'EEG Fp1-Ref' → 'FP1'，'A1' → 'A1'），供跨命名匹配电极帽。"""
    return "".join(ch for ch in str(name or "").upper() if ch.isalnum())


def _family_of(montage_name: str) -> str:
    n = montage_name.lower()
    if n.startswith("biosemi"):
        return "biosemi"
    if n.startswith("gsn-hydrocel") or n.startswith("egi"):
        return "egi"
    return "standard"


@lru_cache(maxsize=1)
def _candidate_names() -> tuple[str, ...]:
    """按家族优先级列出「内置且与 scalp EEG 相关」的候选帽名（剔除 fNIRS 等无关帽）。"""
    import mne  # noqa: PLC0415

    builtins = list(mne.channels.get_builtin_montages())
    out: list[str] = []
    seen: set[str] = set()
    for fam in _FAMILY_PRIORITY:
        for name in sorted(builtins):
            if name in seen:
                continue
            if name == fam or name.lower().startswith(fam.lower()):
                out.append(name)
                seen.add(name)
    return tuple(out)


@lru_cache(maxsize=32)
def _montage_for(name: str) -> Any:
    """构建并缓存内置帽对象（同进程跨多文件复用，省去每个文件重复 make_standard_montage 的开销）。"""
    import mne  # noqa: PLC0415

    return mne.channels.make_standard_montage(name)


@lru_cache(maxsize=None)
def _montage_keys(name: str) -> frozenset[str]:
    return frozenset(_norm_ch_key(x) for x in _montage_for(name).ch_names)


def _empty_detail(upload_kind: str) -> dict[str, Any]:
    return {
        "applied": False,        # 本模块是否套了模板帽
        "has_positions": False,  # 绑定后 FIF 是否带坐标（本模块套的 OR 文件自带）
        "montage": None,
        "family": "none",
        "n_eeg": 0,
        "n_matched": 0,
        "match_ratio": 0.0,
        "renamed": {},
        "vendor_hint": upload_kind or None,
        "note": "",
    }


def autobind_montage(raw: Any, *, upload_kind: str = "") -> dict[str, Any]:
    """就地给 raw 绑定最匹配的标准电极位置（montage）。返回绑定明细（供溯源 / QA）。

    流程：取真 EEG 通道名 → 与每顶内置帽算名字重叠 → 取「命中最多且帽不虚胖」者
    （得分 =(命中数, 精度)）→ 必要时把数据通道名对齐到帽的标准写法 → set_montage。
    文件自带坐标则保留不覆盖；认不出任何标准帽则不绑、留待手动上传。

    绝不因绑定失败而中断导入：任何异常都吞掉、记进 detail['error']，raw 原样返回（无坐标）。
    """
    detail = _empty_detail(upload_kind)
    try:
        import mne  # noqa: PLC0415

        eeg_picks = mne.pick_types(raw.info, eeg=True, meg=False, exclude=[])
        eeg_names = [raw.ch_names[i] for i in eeg_picks]
        detail["n_eeg"] = len(eeg_names)

        # 文件自带电极位置（如部分 BrainVision / 自带 dig）→ 真实坐标，绝不用模板覆盖
        if raw.get_montage() is not None:
            detail.update(has_positions=True, family="preexisting", montage="(file-provided)",
                          note="文件自带电极位置，保留不覆盖")
            return detail

        if len(eeg_names) < _MIN_MATCHED:
            detail["note"] = f"EEG 通道少于 {_MIN_MATCHED} 个，跳过自动定位"
            return detail

        raw_keys = {_norm_ch_key(nm) for nm in eeg_names}

        best_score: tuple[int, float, int] | None = None
        best_name: str | None = None
        for idx, name in enumerate(_candidate_names()):
            try:
                m_keys = _montage_keys(name)
            except Exception:
                continue
            if not m_keys:
                continue
            matched = len(raw_keys & m_keys)
            if matched == 0:
                continue
            precision = matched / len(m_keys)          # 帽子不虚胖（命中占帽电极的比例）
            score = (matched, precision, -idx)          # 命中多 > 精度高 > 家族更具体
            if best_score is None or score > best_score:
                best_score, best_name = score, name

        if best_name is None or best_score[0] < _MIN_MATCHED:
            got = 0 if best_score is None else best_score[0]
            detail["note"] = f"无内置电极帽与通道名足够匹配（最佳仅命中 {got} 道），留待手动上传"
            return detail

        montage = _montage_for(best_name)
        matched = best_score[0]

        # 对齐写法：把数据通道名改成帽里的标准命名（仅当归一化能配上、写法不同、不与现有名冲突）
        std_by_key = {_norm_ch_key(x): x for x in montage.ch_names}
        existing = set(raw.ch_names)
        mapping: dict[str, str] = {}
        used: set[str] = set()
        for nm in eeg_names:
            std = std_by_key.get(_norm_ch_key(nm))
            if std and std != nm and std not in existing and std not in used:
                mapping[nm] = std
                used.add(std)
        if mapping:
            raw.rename_channels(mapping)

        raw.set_montage(montage, match_case=False, on_missing="ignore", verbose="ERROR")

        detail.update(
            applied=True,
            has_positions=True,
            montage=best_name,
            family=_family_of(best_name),
            n_matched=matched,
            match_ratio=round(matched / len(raw_keys), 3),
            renamed=mapping,
            note=f"按通道名重叠自动绑定 {best_name}（命中 {matched}/{len(raw_keys)} 道）",
        )
        return detail
    except Exception as exc:  # 绝不阻断导入
        detail["error"] = str(exc)
        detail["note"] = "自动定位异常，已跳过（不影响导入）"
        return detail
