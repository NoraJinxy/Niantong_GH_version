"""
01_erp_basic：建 ERP pipeline 跑通。

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


def build_definition() -> dict:
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
                    "position": [320, 80],
                    "params": {"filter_type": "bandpass", "method": "iir", "l_freq": 0.5, "h_freq": 30.0, "order": 4},
                },
                {
                    "id": "nf", "type": "eeg/filter/apply", "title": "Notch 50Hz",
                    "position": [560, 80],
                    # 工频陷波：50Hz 基频 + 前 3 次谐波（50/100/150）。中国市电 50Hz；北美改 60。
                    "params": {"filter_type": "notch", "notch_freq": 50.0, "notch_harmonics": 3},
                },
                {
                    "id": "rr", "type": "eeg/preproc/rereference", "title": "Re-reference",
                    "position": [800, 80],
                    "params": {"ref_channels": lconfig.REF_CHANNELS},
                },
                {
                    "id": "ep", "type": "eeg/epoch/segment", "title": "Epoch",
                    "position": [1040, 80],
                    "params": {
                        "event_id": lconfig.EVENT_LABELS,
                        "tmin": -0.2, "tmax": 1.0,
                        "baseline_start": -0.2, "baseline_end": 0.0,
                    },
                },
                {
                    "id": "erp", "type": "eeg/analysis/erp", "title": "ERP Average",
                    "position": [1280, 80],
                    "params": {"condition": lconfig.EVENT_LABELS},
                },
            ],
            "links": [
                {"id": "l1", "from": {"node": "ld",  "port": "output"}, "to": {"node": "bw",  "port": "input"}},
                {"id": "l2", "from": {"node": "bw",  "port": "output"}, "to": {"node": "nf",  "port": "input"}},
                {"id": "l3", "from": {"node": "nf",  "port": "output"}, "to": {"node": "rr",  "port": "input"}},
                {"id": "l4", "from": {"node": "rr",  "port": "output"}, "to": {"node": "ep",  "port": "input"}},
                {"id": "l5", "from": {"node": "ep",  "port": "output"}, "to": {"node": "erp", "port": "input"}},
            ],
        },
    }


def main():
    if not lconfig.DATASET_IDS:
        print("× 先在 config_local.py 里填 DATASET_IDS（跑 setup.py 后看它打印的 recording id）")
        return

    c = ElysClient(gconfig.BASE_URL, gconfig.USERNAME, gconfig.PASSWORD)
    c.login()
    print(f"✓ 登录成功 ({gconfig.USERNAME})")

    # 1) 建 pipeline
    p = c.create_pipeline(lconfig.STUDY_ID, lconfig.PIPELINE_NAME, build_definition())
    pid = p["id"]
    print(f"✓ 建 pipeline #{pid}  name={p.get('name')}")

    # 2) validate
    val = c.validate(lconfig.STUDY_ID, pid)
    print(f"validate: valid={val['valid']}, errors={len(val['errors'])}, warnings={len(val['warnings'])}")
    for w in val["warnings"]:
        print(f"  warn: {w['message']}")
    if not val["valid"]:
        for e in val["errors"]:
            print(f"  ERROR: {e['message']}")
        return

    # 3) 触发
    run = c.trigger_run(lconfig.STUDY_ID, pid)
    rid = run["id"]
    print(f"✓ 触发 run {rid}")

    # 4) 等
    final = c.wait_run(lconfig.STUDY_ID, rid, poll_sec=2, timeout_sec=900)
    print(f"\n=== 最终 status: {final['status']} ===")
    if final.get("error_json"):
        print(f"error_json: {final['error_json']}")

    # 5) 每节点状态
    print("\n节点详情：")
    for nr in c.list_run_nodes(lconfig.STUDY_ID, rid):
        err = nr.get("error_json") or {}
        err_msg = (err.get("errors") or [{}])[0].get("message", "") if err else ""
        print(f"  {nr.get('node_id','?'):20} {nr.get('status','?'):10} {err_msg[:120]}")

    # 6) 下载 evoked 产物
    if final["status"] == "completed":
        derived = c.list_run_derived(lconfig.STUDY_ID, rid)
        out_dir = HERE / "output" / rid[:8]
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n产物 {len(derived)} 个 → {out_dir}")
        for d in derived:
            name = d.get("display_name") or d["id"]
            print(f"  - {name}  type={d.get('data_type')}  size={d.get('file_size_mb',0):.1f} MB")
            # 真要下载就取消下行注释
            # c.download_derived(lconfig.STUDY_ID, d["id"], out_dir / f"{name}.fif")


if __name__ == "__main__":
    main()
