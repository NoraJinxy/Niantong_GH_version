"""
Purpose: 对 Epochs 做基线校正(减基线窗均值)。独立节点,可接在 Epoch 之后、ERP/TFR/PSD 之前。
Related: app/pipeline/dispatcher.py, app/pipeline/nodes/eeg_epoch_baseline.json。

基线校正(baseline correction):用刺激前一段(基线窗)的均值做参照,把每个 epoch 减去该均值,
消除试次间的直流漂移/慢漂,让刺激引起的变化更干净——是 ERP 的标准前置步骤。
按节点粒度判据,基线是跨分析类型复用的独立决策,故单列成节点而非塞进 Epoch/ERP。
`apply_baseline` 是 MNE 的老牌稳定 API,跨版本不变。
"""

from __future__ import annotations

from typing import Any


def run_baseline(epochs: Any, params: dict[str, Any]) -> Any:
    """对 Epochs 应用基线校正,返回校正后的 Epochs(不改原对象)。

    params:
      baseline_tmin: 基线窗起点(秒);留空 = epoch 起点。
      baseline_tmax: 基线窗终点(秒);默认 0(刺激前)。
    """
    tmin_raw = params.get("baseline_tmin", None)
    tmax_raw = params.get("baseline_tmax", 0.0)
    bmin = None if tmin_raw in (None, "") else float(tmin_raw)
    bmax = None if tmax_raw in (None, "") else float(tmax_raw)
    # MNE 约定:(None, 0) = 从 epoch 起点到 0;(None, None) = 整段。区间合法性交给 MNE 校验。
    return epochs.copy().apply_baseline((bmin, bmax), verbose="ERROR")
