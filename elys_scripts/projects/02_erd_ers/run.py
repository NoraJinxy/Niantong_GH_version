"""
02_erd_ers：建 ERD/ERS pipeline 跑通（含自动去坏道）。

流程：login → 建 pipeline → validate → trigger run → wait → 打印每节点状态 → 列出 TFR 产物。
前置：先跑 setup.py 建库 + 上传，并按它打印把 STUDY_ID / DATASET_IDS / CONDITIONS 回填到 config_local.py。

pipeline（跟 01 ERP 的区别在末端：不是 ERP 时域叠加，而是 TFR 时频 + 基线归一化看 ERD/ERS）：
  LoadData → Bandpass(1-40 IIR) → Notch(50Hz) → Bad Channels(坏道检测+插值)
  → Epoch(按 MI 类切分) → TFR(Morlet, ERD/ERS)
  · 电极坐标由「导入转 FIF 时自动绑定 montage」提供，无需流水线手接 Ch Loc 节点；坏道球面样条插值天生有坐标。
  · Bad Channels 的算法 / 处理方式在 config_local.py 调（BAD_CHAN_METHOD / BAD_CHAN_ACTION）。
不做 Re-reference（运动想象 ERD/ERS 对参考不敏感，少一个待回填的通道列表）。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]  # elys_scripts/
sys.path.insert(0, str(ROOT / "common"))

from elys_client import ElysClient  # noqa: E402
import config as gconfig              # noqa: E402
import config_local as lconfig        # noqa: E402
import ui                             # noqa: E402


def build_definition() -> dict:
    # 节点横向间隔 320px：前端画布节点卡片宽 264px，间隔小于它会重叠。
    return {
        "graph": {
            "nodes": [
                {
                    "id": "ld", "type": "eeg/data/load", "title": "LoadData",
                    "position": [80, 80],
                    "params": {
                        "selection_mode": "explicit",
                        "dataset_ids": lconfig.DATASET_IDS,
                        "dataset_filter": {},
                    },
                },
                {
                    "id": "bw", "type": "eeg/filter/apply", "title": "Bandpass (IIR)",
                    "position": [400, 80],
                    # ERD/ERS 看 mu(8-13)/beta(13-30)，带通 1-40 保留这些节律。
                    "params": {"filter_type": "bandpass", "method": "iir", "l_freq": 1.0, "h_freq": 40.0, "order": 4},
                },
                {
                    "id": "nf", "type": "eeg/filter/apply", "title": "Notch 50Hz",
                    "position": [720, 80],
                    "params": {"filter_type": "notch", "notch_freq": 50.0, "notch_harmonics": 3},
                },
                {
                    "id": "bc", "type": "eeg/preproc/bad_channels", "title": "Bad Channels",
                    "position": [1040, 80],
                    # 自动找坏电极 → 球面样条插值修复（坐标由导入自动绑定的 montage 提供）。
                    # 算法 / 处理方式在 config 调：BAD_CHAN_METHOD(lof/ransac) / BAD_CHAN_ACTION(interpolate/mark)。
                    "params": {"method": lconfig.BAD_CHAN_METHOD, "action": lconfig.BAD_CHAN_ACTION},
                },
                {
                    "id": "ep", "type": "eeg/epoch/segment", "title": "Epoch",
                    "position": [1360, 80],
                    # conditions 统一模型：从 config 取 fist/rest 规则（contains/regex 归并）。
                    "params": {
                        "conditions": lconfig.CONDITIONS,
                        "tmin": lconfig.EPOCH_TMIN,
                        "tmax": lconfig.EPOCH_TMAX,
                    },
                },
                {
                    "id": "tfr", "type": "eeg/analysis/tfr", "title": "TFR (ERD/ERS)",
                    "position": [1680, 80],
                    # 对所选 condition 做 Morlet 小波时频 + 基线归一化 = ERD/ERS。
                    "params": {
                        "condition": lconfig.TFR_CONDITION,
                        "fmin": lconfig.TFR_FMIN,
                        "fmax": lconfig.TFR_FMAX,
                        "baseline_mode": lconfig.TFR_BASELINE_MODE,
                        "baseline_tmax": lconfig.TFR_BASELINE_TMAX,
                    },
                },
            ],
            "links": [
                {"id": "l1", "from": {"node": "ld", "port": "output"}, "to": {"node": "bw",  "port": "input"}},
                {"id": "l2", "from": {"node": "bw", "port": "output"}, "to": {"node": "nf",  "port": "input"}},
                {"id": "l3", "from": {"node": "nf", "port": "output"}, "to": {"node": "bc",  "port": "input"}},
                {"id": "l4", "from": {"node": "bc", "port": "output"}, "to": {"node": "ep",  "port": "input"}},
                {"id": "l5", "from": {"node": "ep", "port": "output"}, "to": {"node": "tfr", "port": "input"}},
            ],
        },
    }


def main():
    ui.section("跑 ERD/ERS pipeline")
    if not lconfig.DATASET_IDS:
        ui.fail("先在 config_local.py 里填 DATASET_IDS（跑 setup.py 后看它打印的 recording id）")
        return

    c = ElysClient(gconfig.BASE_URL, gconfig.USERNAME, gconfig.PASSWORD, data_base_url=gconfig.DATA_BASE_URL)
    c.login()
    ui.ok(f"登录成功 ({gconfig.USERNAME})")

    # 1) 建 pipeline
    p = c.create_pipeline(lconfig.STUDY_ID, lconfig.PIPELINE_NAME, build_definition())
    pid = p["id"]
    ui.ok(f"建 pipeline #{pid}  name={p.get('name')}")

    # 2) validate
    val = c.validate(lconfig.STUDY_ID, pid)
    if val["valid"]:
        ui.ok(f"校验通过  warnings={len(val['warnings'])}")
    else:
        ui.fail(f"校验未通过  errors={len(val['errors'])}  warnings={len(val['warnings'])}")
    for w in val["warnings"]:
        ui.warn(w["message"])
    if not val["valid"]:
        for e in val["errors"]:
            ui.info(f"{ui.RED}ERROR{ui.RESET} {e['message']}")
        ui.died("pipeline 校验失败，已停止")
        return

    # 3) 触发
    run = c.trigger_run(lconfig.STUDY_ID, pid)
    rid = run["id"]
    ui.ok(f"触发 run {rid}")

    # 4) 等
    final = c.wait_run(lconfig.STUDY_ID, rid, poll_sec=2, timeout_sec=900)
    if final.get("error_json"):
        ui.info(f"error_json: {final['error_json']}")

    # 5) 每节点状态
    ui.section("节点详情")
    for nr in c.list_run_nodes(lconfig.STUDY_ID, rid):
        err = nr.get("error_json") or {}
        err_msg = (err.get("errors") or [{}])[0].get("message", "") if err else ""
        st = nr.get("status", "?")
        col = ui.GREEN if st == "completed" else (ui.RED if st == "failed" else ui.YELLOW)
        ui.kv(nr.get("node_id", "?"), f"{col}{st}{ui.RESET}  {ui.GRAY}{err_msg[:120]}{ui.RESET}")

    # 6) 列出 TFR 产物
    if final["status"] == "completed":
        derived = c.list_run_derived(lconfig.STUDY_ID, rid)
        out_dir = HERE / "output" / rid[:8]
        out_dir.mkdir(parents=True, exist_ok=True)
        ui.section(f"产物 {len(derived)} 个 → {out_dir}")
        for d in derived:
            name = d.get("display_name") or d["id"]
            ui.info(f"{name}  type={d.get('data_type')}  size={d.get('file_size_mb',0):.1f} MB")
            # 真要下载就取消下行注释（TFR 是 .h5）
            # c.download_derived(lconfig.STUDY_ID, d["id"], out_dir / f"{name}.h5")

    # 7) 终态横幅
    if final["status"] == "completed":
        ui.passed(f"ERD/ERS pipeline 跑通 · run {rid[:8]} · status={final['status']}")
    else:
        ui.died(f"ERD/ERS pipeline 未完成 · run {rid[:8]} · status={final['status']}")


if __name__ == "__main__":
    main()
