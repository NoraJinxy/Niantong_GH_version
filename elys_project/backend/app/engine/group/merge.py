"""
Purpose: Group analysis – 通用 N→1 合并(把多个分析产物沿 unit 轴堆叠成 unit_stack)。
         通吃 evoked / psd / tfr / unit_stack(由 stack.extract_block 分形态抽块)。
Related: app/engine/group/stack.py, app/pipeline/dispatcher.py (_execute_group_merge), app/engine/io.py.
"""

from __future__ import annotations

from typing import Any

from app.engine.group.stack import align_and_stack, extract_block


def run_group_merge(input_data_infos: list[dict[str, Any]], params: dict[str, Any]) -> dict[str, Any]:
    """从 N 个上游产物读出 → 沿 unit 轴对齐堆叠成 unit_stack。

    每个输入贡献 ≥1 个 unit(单产物=1;已堆叠 unit_stack=其 m 个)。要求:同形态、feature 轴可对齐
    (通道交集、时间/频率轴逐点一致)。返回 dict 可直接传给 io.save_unit_stack_npz / io.summarize_unit_stack。
    """
    if not input_data_infos:
        raise ValueError("run_group_merge: input_data_infos 为空,无可合并的产物。")
    blocks = [extract_block(di) for di in input_data_infos]
    return align_and_stack(blocks, params)
