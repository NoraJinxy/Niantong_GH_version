"""
01_erp_basic：建 ERP pipeline 跑通（含自动去坏道）。

pipeline：LoadData → Bandpass(0.5-30 IIR) → Notch(50Hz) → Bad Channels(坏道检测+插值)
          → Re-reference → Epoch → ERP Average。
  · 电极坐标由「导入转 FIF 时自动绑定 montage」提供（见 montage_autobind），无需流水线手接 Ch Loc 节点；
    坏道球面样条插值因此天生有坐标可用。
  · Bad Channels 的算法 / 处理方式在 config_local.py 调（BAD_CHAN_METHOD / BAD_CHAN_ACTION）。
流程：login → 建 pipeline → validate → trigger run → wait → 打印每节点状态 → 下载 evoked。
前置：先跑 setup.py 建库 + 上传，并按它打印把 STUDY_ID / DATASET_IDS / REF_CHANNELS / EVENT_LABELS 回填到 config_local.py。
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
    # 节点横向间隔 320px：前端画布节点卡片宽 264px（NODE_CARD_WIDTH），间隔小于它会重叠；
    # 前端自身自动布局用 304（NODE_GAP_X），这里取 320 留点余量。
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
                    "params": {"filter_type": "bandpass", "method": "iir", "l_freq": 0.5, "h_freq": 30.0, "order": 4},
                },
                {
                    "id": "nf", "type": "eeg/filter/apply", "title": "Notch 50Hz",
                    "position": [720, 80],
                    # 工频陷波：50Hz 基频 + 前 3 次谐波（50/100/150）。中国市电 50Hz；北美改 60。
                    "params": {"filter_type": "notch", "notch_freq": 50.0, "notch_harmonics": 3},
                },
                {
                    "id": "bc", "type": "eeg/preproc/bad_channels", "title": "Bad Channels",
                    "position": [1040, 80],
                    # 自动找坏电极 → 球面样条插值修复（坐标由导入自动绑定的 montage 提供）。放在重参考前，免得坏道污染参考。
                    # 算法 / 处理方式在 config 调：BAD_CHAN_METHOD(lof/ransac) / BAD_CHAN_ACTION(interpolate/mark)。
                    "params": {"method": lconfig.BAD_CHAN_METHOD, "action": lconfig.BAD_CHAN_ACTION},
                },
                {
                    "id": "rr", "type": "eeg/preproc/rereference", "title": "Re-reference",
                    "position": [1360, 80],
                    "params": {"ref_channels": lconfig.REF_CHANNELS},
                },
                {
                    "id": "ep", "type": "eeg/epoch/segment", "title": "Epoch",
                    "position": [1680, 80],
                    "params": {
                        # conditions 统一模型：每个勾选项 = 一个 condition。这里把每个事件标签
                        # 当作一条 exact 规则（name=pattern=原始标签），下游 ERP 按这些 name 求平均。
                        "conditions": [
                            {"name": lbl, "pattern": lbl, "mode": "exact"}
                            for lbl in lconfig.EVENT_LABELS
                        ],
                        "tmin": -0.2, "tmax": 1.0,
                    },
                },
                {
                    "id": "erp", "type": "eeg/analysis/erp", "title": "ERP Average",
                    "position": [2000, 80],
                    "params": {"condition": lconfig.EVENT_LABELS},
                },
            ],
            "links": [
                {"id": "l1", "from": {"node": "ld", "port": "output"}, "to": {"node": "bw",  "port": "input"}},
                {"id": "l2", "from": {"node": "bw", "port": "output"}, "to": {"node": "nf",  "port": "input"}},
                {"id": "l3", "from": {"node": "nf", "port": "output"}, "to": {"node": "bc",  "port": "input"}},
                {"id": "l4", "from": {"node": "bc", "port": "output"}, "to": {"node": "rr",  "port": "input"}},
                {"id": "l5", "from": {"node": "rr", "port": "output"}, "to": {"node": "ep",  "port": "input"}},
                {"id": "l6", "from": {"node": "ep", "port": "output"}, "to": {"node": "erp", "port": "input"}},
            ],
        },
    }


def main():
    ui.section("跑 ERP pipeline")
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

    # 6) 下载 evoked 产物
    if final["status"] == "completed":
        derived = c.list_run_derived(lconfig.STUDY_ID, rid)
        out_dir = HERE / "output" / rid[:8]
        out_dir.mkdir(parents=True, exist_ok=True)
        ui.section(f"产物 {len(derived)} 个 → {out_dir}")
        for d in derived:
            name = d.get("display_name") or d["id"]
            ui.info(f"{name}  type={d.get('data_type')}  size={d.get('file_size_mb',0):.1f} MB")
            # 真要下载就取消下行注释
            # c.download_derived(lconfig.STUDY_ID, d["id"], out_dir / f"{name}.fif")

    # 7) 终态横幅
    if final["status"] == "completed":
        ui.passed(f"ERP pipeline 跑通 · run {rid[:8]} · status={final['status']}")
    else:
        ui.died(f"ERP pipeline 未完成 · run {rid[:8]} · status={final['status']}")


if __name__ == "__main__":
    main()
