"""
Purpose: Assign standard channel locations (montage) for Pipeline nodes in the MNE-based engine.
Related: app/pipeline/dispatcher.py, app/pipeline/nodes/eeg_preproc_channel_location.json,
         app/pipeline/timeseries.py（地形图读取 montage 坐标，与本节点写入的坐标对应），
         app/engine/preprocess/montage_autobind.py（导入期自动定位，与本节点同源的「命名重叠评分」，
           本模块只读复用其家族候选与帽键集，绝不改它）。
"""

from __future__ import annotations

from typing import Any

# 只读复用导入期自动定位的「命名重叠评分」族（候选帽列表 + 每顶帽的归一化键集 + 家族判定）。
# 这些都是无副作用的纯函数（带 lru_cache），跨模块复用不会动到 autobind 的导入流程。
from app.engine.preprocess.montage_autobind import (
    _candidate_names,
    _family_of,
    _montage_keys,
    _norm_ch_key,
)

# auto 走命名评分时，命中道数 / 匹配率低于此阈值即判「认不准家族」，退回按通道数选标准帽。
# 与 autobind 的 _MIN_MATCHED(=3) 同量级；这里要求略严一点（既要命中够多、又要占数据通道一定比例），
# 因为本节点是用户显式选了 auto、宁可退到通用 10-20/10-05 也不要套错厂家帽。
_AUTO_MIN_MATCHED = 3
_AUTO_MIN_RATIO = 0.5


def _mne():
    try:
        import mne
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("MNE is required for channel-location pipeline nodes.") from exc
    return mne


def _auto_by_channel_count(n_eeg: int) -> str:
    """通道数启发式：低密度（≤32 导）用 10-20；高密度用 10-05（10-05 是 10-20 命名的超集）。"""
    return "standard_1020" if n_eeg <= 32 else "standard_1005"


def _auto_by_family_scoring(eeg_names: list[str], n_eeg: int) -> tuple[str, dict[str, Any]]:
    """auto 选帽：先按「命名重叠评分」挑最匹配的厂家 / 标准帽，匹配太弱再退通道数启发式。

    评分逻辑复用 montage_autobind 同款：对每顶候选帽算 (命中道数, 精度=命中/帽电极数, -家族序)，
    取最大者——「命中多 > 帽不虚胖 > 家族更具体」。这样 BioSemi(A1..H32) / EGI(E1..E257) 这类
    私有命名能命中对应厂家帽，而不会被旧的「只看通道数」逻辑误判成 standard_1020/1005。

    返回 (montage_name, 选帽明细)；明细供溯源 / QA，不含 numpy 数组。
    """
    raw_keys = {_norm_ch_key(nm) for nm in eeg_names}

    best_score: tuple[int, float, int] | None = None
    best_name: str | None = None
    for idx, name in enumerate(_candidate_names()):
        try:
            m_keys = _montage_keys(name)
        except Exception:
            continue
        if len(m_keys) == 0:
            continue
        matched = len(raw_keys & m_keys)
        if matched == 0:
            continue
        precision = matched / len(m_keys)          # 帽子不虚胖（命中占帽电极的比例）
        score = (matched, precision, -idx)          # 命中多 > 精度高 > 家族更具体
        if best_score is None or score > best_score:
            best_score, best_name = score, name

    n_keys = len(raw_keys)
    ratio = (best_score[0] / n_keys) if (best_score is not None and n_keys > 0) else 0.0

    # 评分够强 → 用评分挑出的帽（覆盖厂家命名）
    if (
        best_name is not None
        and best_score is not None
        and best_score[0] >= _AUTO_MIN_MATCHED
        and ratio >= _AUTO_MIN_RATIO
    ):
        return best_name, {
            "auto_strategy": "family_scoring",
            "auto_family": _family_of(best_name),
            "auto_matched": best_score[0],
            "auto_match_ratio": round(ratio, 3),
        }

    # 评分太弱（命名无信息 / 命中太少）→ 退回通道数启发式，并在明细里说明为何降级
    fallback = _auto_by_channel_count(n_eeg)
    got = 0 if best_score is None else best_score[0]
    return fallback, {
        "auto_strategy": "channel_count_fallback",
        "auto_family": "standard",
        "auto_matched": got,
        "auto_match_ratio": round(ratio, 3),
        "auto_fallback_reason": (
            f"命名评分不足（最佳命中 {got}/{n_keys} 道，匹配率 {round(ratio, 3)}），"
            f"按通道数退回 {fallback}"
        ),
    }


def run_channel_location(raw: Any, params: dict[str, Any], custom_montage_path: str | None = None) -> Any:
    """给 raw 指派电极位置（montage）。raw→(raw, 选帽明细)，可选自动规范通道名。

    montage 三种来源：
    - auto → 先按「命名重叠评分」挑最匹配的厂家 / 标准帽（BioSemi A1.. / EGI E1.. 都能认对家族），
      评分太弱才退回「按 EEG 通道数选 standard_1020 / 1005」的通用启发式；
    - 标准帽（standard_1020/1005）/ 厂家预设（biosemi* / GSN-HydroCel-* / EGI_256 / easycap-*）
      → make_standard_montage（标准模板坐标，非个体真实数字化）；
    - custom → 读 custom_montage_path 指向的上传文件（由 dispatcher 按 custom_montage_file_id 解析出物理路径）。
    流程：先按归一化名把数据通道对到所选帽的标准命名（rename），再 set_montage 写入坐标。
    写入的坐标用于地形图 / ICA 成分图 / 坏导插值。

    返回 (located, extra_meta)：extra_meta 记 auto 选帽决策（选了哪顶帽、按什么策略、命中多少道），
    由 dispatcher 并入 mne_summary 溯源——不改 io.py，字段含义见 io_surfacing_needed 报告。
    """
    mne = _mne()
    requested = str(params.get("montage") or "auto")
    rename = bool(params.get("rename", True))
    on_missing = str(params.get("on_missing") or "ignore").strip().lower()
    if on_missing not in ("ignore", "warn", "raise"):
        on_missing = "ignore"

    located = raw.copy().load_data()

    extra_meta: dict[str, Any] = {}

    if requested.strip().lower() == "custom":
        if not custom_montage_path:
            raise ValueError(
                "选择了「自定义电极文件」，但没拿到有效文件。请在数据集详情页的「数据文件」里上传电极位置文件后，回到节点重新选择。"
            )
        montage = mne.channels.read_custom_montage(custom_montage_path)
        extra_meta["montage_resolved"] = "custom"
        extra_meta["montage_source"] = "custom_file"
    else:
        # 取真 EEG 通道（排除 EOG / 触发等），既给 auto 评分用、也给通道数启发式用
        try:
            eeg_picks = mne.pick_types(located.info, eeg=True, meg=False, exclude=[])
            eeg_names = [located.ch_names[i] for i in eeg_picks]
        except Exception:
            eeg_names = list(located.ch_names)
        n_eeg = len(eeg_names)

        if requested.strip().lower() == "auto":
            montage_name, auto_meta = _auto_by_family_scoring(eeg_names, n_eeg)
            extra_meta.update(auto_meta)
            extra_meta["montage_source"] = "auto"
        else:
            montage_name = requested.strip()
            extra_meta["montage_source"] = "explicit"

        extra_meta["montage_resolved"] = montage_name

        builtin = set(mne.channels.get_builtin_montages())
        if montage_name not in builtin:
            raise ValueError(
                f"未知的电极帽模板「{montage_name}」。可用内置模板：{', '.join(sorted(builtin))}。"
            )
        montage = mne.channels.make_standard_montage(montage_name)

    # rename：把数据通道名对到所选帽里的标准命名（仅当归一化能匹配且写法不同、不与现有名冲突）
    renamed: dict[str, str] = {}
    if rename:
        std_by_key = {_norm_ch_key(nm): nm for nm in montage.ch_names}
        existing = set(located.ch_names)
        used: set[str] = set()
        for nm in located.ch_names:
            std = std_by_key.get(_norm_ch_key(nm))
            if std and std != nm and std not in existing and std not in used:
                renamed[nm] = std
                used.add(std)
        if renamed:
            located.rename_channels(renamed)

    located.set_montage(montage, match_case=False, on_missing=on_missing, verbose="ERROR")

    extra_meta["renamed_channels"] = renamed
    extra_meta["on_missing"] = on_missing
    return located, extra_meta
