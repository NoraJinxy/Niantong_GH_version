"""
Purpose: 用 ICLabel 自动分类 ICA 成分并剔除伪迹成分（全自动，无需人工逐个审阅）。
Related: app/pipeline/dispatcher.py (_execute_ica_iclabel),
         app/pipeline/nodes/eeg_ica_iclabel.json, app/engine/ica/apply.py。
"""

from __future__ import annotations

from typing import Any


# ICLabel 七分类标签（mne_icalabel.label_components 返回的字符串） → 内部类别键。
# 七类：brain / muscle artifact / eye blink / heart beat / line noise / channel noise / other。
_LABEL_TO_CATEGORY: dict[str, str] = {
    "brain": "brain",
    "muscle artifact": "muscle",
    "eye blink": "eye",
    "heart beat": "heart",
    "line noise": "line_noise",
    "channel noise": "channel_noise",
    "other": "other",
}

# 类别键 → (剔除开关参数名, 中文名)。仅这五类伪迹可被剔除；brain（脑信号）与 other（难判）永不自动剔除。
_REMOVABLE: dict[str, tuple[str, str]] = {
    "eye": ("remove_eye", "眼动/眨眼"),
    "muscle": ("remove_muscle", "肌电"),
    "heart": ("remove_heart", "心电"),
    "line_noise": ("remove_line_noise", "工频噪声"),
    "channel_noise": ("remove_channel_noise", "单通道噪声"),
}


def run_iclabel(raw: Any, ica: Any, params: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """ICLabel 自动给每个 ICA 成分分类，按所选类别 + 置信度阈值自动剔除伪迹成分。

    返回 (输出 raw, {"iclabel": 明细})。明细由 dispatcher 并入 preview / mne_summary 作溯源——
    把「每个成分判成了什么类、置信度多少、删了哪些」摊在结果里。

    - action="apply"：输出为剔除伪迹后重建的 raw（默认）。
    - action="mark" ：输出为原始 raw 副本（数据不动，只出一份分类报告）。
    """
    label_components = _label_components()

    action = str(params.get("action") or "apply").strip().lower()
    if action not in {"apply", "mark"}:
        raise ValueError(f"Unknown ICLabel action: {action!r}")
    threshold = _resolve_threshold(params.get("prob_threshold"), 0.8)

    # 选中的可剔除类别（默认五类伪迹全开；保留 brain/other）
    remove_categories = {
        category
        for category, (param_name, _label) in _REMOVABLE.items()
        if bool(params.get(param_name, True))
    }

    notes: list[str] = []
    # ICLabel 训练于 extended-infomax 分解；其它方法（如 fastica）仍可跑但准确度下降——给提示不拦（厚层放行）。
    # 例外：Picard 配 ortho=False+extended=True 在数学上等价于 extended-infomax，ICLabel 吃得饱，不该误报。
    ica_method = str(getattr(ica, "method", "") or "")
    fit_params = dict(getattr(ica, "fit_params", {}) or {})
    picard_as_infomax = (
        ica_method.lower() == "picard"
        and fit_params.get("ortho") is False
        and bool(fit_params.get("extended"))
    )
    if "infomax" not in ica_method.lower() and not picard_as_infomax:
        notes.append(
            f"当前 ICA 用 {ica_method or '未知方法'} 分解；ICLabel 训练于 extended-infomax，"
            "建议上游 Compute ICA 选 Infomax（或 Picard）以获得最佳分类准确度。"
        )

    # ICLabel 训练域:1–100Hz 带通 + 平均参考。偏离会让七分类置信度系统性偏移(伪迹误判成 brain 漏删,
    # 或 brain 误判成伪迹)。给提示不拦(厚层放行)——让用户看见这层"出域",而非默默拿偏移的分类去删数据。
    lowpass = float(raw.info.get("lowpass") or 0.0)
    if 0 < lowpass < 90.0:
        notes.append(
            f"当前低通约 {lowpass:g}Hz，低于 ICLabel 训练域上限 100Hz；肌电 / 工频类成分的高频特征被截断，"
            "分类置信度可能偏移。如需最佳准确度，可对送入 ICA / ICLabel 的数据用 1–100Hz 带通。"
        )
    if not bool(raw.info.get("custom_ref_applied", False)):
        notes.append(
            "未检测到平均参考；ICLabel 训练于平均参考数据，建议上游先做平均参考（Re-reference 全选）以提升分类准确度。"
        )

    try:
        result = label_components(raw, ica, method="iclabel")
    except Exception as exc:  # 缺电极坐标 / 无 EEG 通道 / 模型加载失败等，给清晰报错
        raise RuntimeError(
            f"ICLabel 分类失败：{exc}。请确认数据已绑定电极坐标（montage）且包含 EEG 通道；"
            "建议上游先做平均参考 + 1–100Hz 带通。"
        ) from exc

    labels = list(result.get("labels") or [])
    proba_attr = result.get("y_pred_proba")
    probabilities = _per_component_probabilities(proba_attr)

    components: list[dict[str, Any]] = []
    excluded: list[int] = []
    label_counts: dict[str, int] = {}
    for index, raw_label in enumerate(labels):
        category = _LABEL_TO_CATEGORY.get(str(raw_label).strip().lower(), "other")
        probability = probabilities[index] if index < len(probabilities) else None
        will_remove = (
            category in remove_categories
            and probability is not None
            and probability >= threshold
        )
        if will_remove:
            excluded.append(index)
        label_counts[category] = label_counts.get(category, 0) + 1
        components.append(
            {
                "index": index,
                "label": str(raw_label),
                "category": category,
                "probability": round(probability, 4) if probability is not None else None,
                "excluded": will_remove,
            }
        )

    excluded = sorted(set(excluded))

    detail: dict[str, Any] = {
        "iclabel": {
            "method": "iclabel",
            "action": action,
            "prob_threshold": threshold,
            "remove_categories": sorted(remove_categories),
            "ica_method": ica_method,
            "n_components": len(labels),
            "n_excluded": len(excluded),
            "excluded_components": excluded,
            "label_counts": label_counts,
            "components": components,
            "notes": notes,
        }
    }

    if action == "mark" or not excluded:
        return raw.copy(), detail

    cleaned = raw.copy()
    # 用 exclude 关键字应用，避免副作用地写回 ica.exclude（与官方 ICLabel 示例一致）。
    ica.apply(cleaned, exclude=excluded, verbose="ERROR")
    return cleaned, detail


def _per_component_probabilities(proba_attr: Any) -> list[float]:
    """把 ICLabel 的 y_pred_proba 归一成「每个成分取其预测类别的置信度」一维列表。

    mne-icalabel 不同版本里 y_pred_proba 可能是一维 (n_components,) 直接给预测类置信度，
    也可能是二维 (n_components, n_classes) 给全类别概率——后者按行取 argmax 类（与 labels 的
    选类一致）即每行最大值。
    """
    if proba_attr is None:
        return []
    probabilities: list[float] = []
    for row in proba_attr:
        try:
            probabilities.append(float(row))
        except (TypeError, ValueError):
            probabilities.append(float(max(row)))
    return probabilities


def _resolve_threshold(value: Any, default: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if not (0.0 <= result <= 1.0):
        return default
    return result


def _label_components():
    try:
        from mne_icalabel import label_components
    except ImportError as exc:
        raise RuntimeError(
            "ICLabel 自动选成分需要 mne-icalabel 库（及 onnxruntime 推理后端）。"
            "请确认 requirements 已安装 mne-icalabel 与 onnxruntime。"
        ) from exc
    return label_components
