"""
03_resting_state / run —— 在 ELYS 上跑两条静息态 PSD pipeline（EO + EC）。

当前 pipeline 链路（两条，EO + EC 各一条）：
  LoadData(filter,tasks=["eo"/"ec"])
  → Bandpass(1-45 IIR) → Notch(50Hz)
  → Ch Loc → Bad Channels [→ Re-reference（REF_CHANNELS 非空时加）]
  → PSD(Welch, 1-45Hz)          # 30 被试 × 1 PSD，输出 30 个 .npz
  → Group Merge                  # N-to-1：堆叠成 (30, n_ch, n_freq) group 张量（节点未部署时自动跳过）
  → Grand Average                # mean ± SEM → 1 个 grand avg PSD（同上）

前置：先跑 setup.py 批量上传全部 EDF，STUDY_ID / DATASET_ID 会自动回填。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "common"))

from elys_client import ElysClient, ElysAPIError  # noqa: E402
import config as gconfig                           # noqa: E402
import config_local as lconfig                     # noqa: E402
import ui                                          # noqa: E402

TASKS = ["eo", "ec"]
TASK_LABEL = {"eo": "Eyes Open", "ec": "Eyes Closed"}

# 需要 Group 节点才能跑 Grand Average
GROUP_NODE_TYPES = {"eeg/group/merge", "eeg/group/average"}


def check_group_support(c: ElysClient) -> bool:
    """查询后端已注册节点类型；返回 True 表示 Group Merge/Average 均已部署。"""
    try:
        supported = c.list_node_types()
        missing = GROUP_NODE_TYPES - supported
        if missing:
            ui.warn(f"Group 节点尚未部署（{', '.join(sorted(missing))}）→ pipeline 只跑到 PSD，跳过 Grand Average")
            return False
        ui.ok(f"Group 节点已部署（{', '.join(sorted(GROUP_NODE_TYPES))}）→ 完整链路")
        return True
    except ElysAPIError as e:
        ui.warn(f"查询节点类型失败（{e}），保守跳过 Group 节点")
        return False


def build_definition(task: str, use_group: bool) -> dict:
    """为指定 task 建 pipeline 定义。

    use_group=True  → 完整链：PSD → Group Merge → Grand Average
    use_group=False → 截断链：只跑到 PSD（节点未部署时的安全降级）
    """
    use_reref = bool(lconfig.REF_CHANNELS)
    x = 80

    def node(nid, ntype, title, params, dx=320):
        nonlocal x
        n = {"id": nid, "type": ntype, "title": title, "position": [x, 80], "params": params}
        x += dx
        return n

    ld = node("ld", "eeg/data/load", f"LoadData ({task.upper()})", {
        "selection_mode": "filter",
        "dataset_filter": {
            "subjects": "all",
            "sessions": "all",
            "tasks": [f"task-{task}"],   # 须用规范 BIDS 形（存储即 task-eo），裸 eo 配不上前缀
            "runs": "all",
            "qa_status": "all",
            "require_fif": True,
        },
        "dataset_ids": [],
    })
    bw = node("bw", "eeg/filter/apply", "Bandpass (IIR)", {
        "filter_type": "bandpass", "method": "iir", "l_freq": 1.0, "h_freq": 45.0, "order": 4,
    })
    nf = node("nf", "eeg/filter/apply", "Notch 50Hz", {
        "filter_type": "notch", "notch_freq": 50.0, "notch_harmonics": 3,
    })
    cl = node("cl", "eeg/preproc/channel_location", "Ch Loc Assign", {
        "montage": lconfig.MONTAGE, "rename": True,
    })
    bc = node("bc", "eeg/preproc/bad_channels", "Bad Channels", {
        "method": lconfig.BAD_CHAN_METHOD, "action": lconfig.BAD_CHAN_ACTION,
    })

    nodes = [ld, bw, nf, cl, bc]
    links = [
        {"id": "l1", "from": {"node": "ld", "port": "output"}, "to": {"node": "bw", "port": "input"}},
        {"id": "l2", "from": {"node": "bw", "port": "output"}, "to": {"node": "nf", "port": "input"}},
        {"id": "l3", "from": {"node": "nf", "port": "output"}, "to": {"node": "cl", "port": "input"}},
        {"id": "l4", "from": {"node": "cl", "port": "output"}, "to": {"node": "bc", "port": "input"}},
    ]

    prev = "bc"
    if use_reref:
        rr = node("rr", "eeg/preproc/rereference", "Re-reference", {
            "ref_channels": lconfig.REF_CHANNELS,
        })
        nodes.append(rr)
        links.append({"id": f"l{len(links)+1}", "from": {"node": prev, "port": "output"}, "to": {"node": "rr", "port": "input"}})
        prev = "rr"

    psd = node("psd", "eeg/analysis/psd", f"PSD {task.upper()} (Welch)", {
        "condition": lconfig.PSD_CONDITION,
        "fmin": lconfig.PSD_FMIN,
        "fmax": lconfig.PSD_FMAX,
        "method": lconfig.PSD_METHOD,
    })
    nodes.append(psd)
    links.append({"id": f"l{len(links)+1}", "from": {"node": prev, "port": "output"}, "to": {"node": "psd", "port": "input"}})

    if use_group:
        # Group Merge：收集所有被试 PSD → 堆叠成 (n_subjects, n_channels, n_freqs) group 张量
        merge = node("gm", "eeg/group/merge", f"Group Merge {task.upper()}", {
            "label": task.upper(),
        })
        nodes.append(merge)
        links.append({"id": f"l{len(links)+1}", "from": {"node": "psd", "port": "output"}, "to": {"node": "gm", "port": "input"}})

        # Grand Average：沿被试轴求 mean ± SEM → 一条功率谱曲线
        grandavg = node("ga", "eeg/group/average", f"Grand Avg {task.upper()}", {})
        nodes.append(grandavg)
        links.append({"id": f"l{len(links)+1}", "from": {"node": "gm", "port": "output"}, "to": {"node": "ga", "port": "input"}})

    return {"graph": {"nodes": nodes, "links": links}}


def run_pipeline(c: ElysClient, task: str, use_group: bool) -> bool:
    """建→validate→run→等→打印状态。返回 True=成功。"""
    label = TASK_LABEL[task]
    suffix = " [+ Grand Avg]" if use_group else " [仅 PSD]"
    ui.section(f"Pipeline: {label} ({task}){suffix}")

    name = f"{lconfig.STUDY_NAME} — PSD {task.upper()}"
    p = c.create_pipeline(lconfig.STUDY_ID, name, build_definition(task, use_group))
    pid = p["id"]
    ui.ok(f"建 pipeline #{pid}")

    val = c.validate(lconfig.STUDY_ID, pid)
    for w in val["warnings"]:
        ui.warn(w["message"])
    if not val["valid"]:
        for e in val["errors"]:
            ui.info(f"{ui.RED}ERROR{ui.RESET} {e['message']}")
        ui.died(f"pipeline {task.upper()} 校验失败")
        return False
    ui.ok(f"校验通过  warnings={len(val['warnings'])}")

    run = c.trigger_run(lconfig.STUDY_ID, pid)
    rid = run["id"]
    ui.ok(f"触发 run {rid}")

    final = c.wait_run(lconfig.STUDY_ID, rid, poll_sec=3, timeout_sec=1800)
    if final.get("error_json"):
        ui.info(f"error_json: {final['error_json']}")

    ui.section("节点详情")
    for nr in c.list_run_nodes(lconfig.STUDY_ID, rid):
        err = nr.get("error_json") or {}
        err_msg = (err.get("errors") or [{}])[0].get("message", "") if err else ""
        st  = nr.get("status", "?")
        col = ui.GREEN if st == "completed" else (ui.RED if st == "failed" else ui.YELLOW)
        ui.kv(nr.get("node_id", "?"), f"{col}{st}{ui.RESET}  {ui.GRAY}{err_msg[:120]}{ui.RESET}")

    if final["status"] == "completed":
        derived = c.list_run_derived(lconfig.STUDY_ID, rid)
        out_dir = HERE / "output" / rid[:8]
        out_dir.mkdir(parents=True, exist_ok=True)
        ui.section(f"产物 {len(derived)} 个 → {out_dir}")
        for d in derived:
            dname = d.get("display_name") or d["id"]
            ui.info(f"  {dname}  type={d.get('data_type')}  {d.get('file_size_mb', 0):.1f} MB")
        label_str = "PSD + Grand Avg" if use_group else "PSD"
        ui.passed(f"{label_str} {task.upper()} pipeline 跑通 · run {rid[:8]}")
        return True
    else:
        ui.died(f"PSD {task.upper()} pipeline 未完成 · run {rid[:8]} · status={final['status']}")
        return False


def main():
    ui.section("静息态 PSD pipeline（ELYS 端）")

    reref_note = (
        f"Re-reference: {lconfig.REF_CHANNELS}" if lconfig.REF_CHANNELS
        else "Re-reference: 跳过（REF_CHANNELS 为空，跑完 setup 看通道名再填）"
    )
    ui.info(reref_note)
    ui.info(f"PSD: {lconfig.PSD_FMIN}-{lconfig.PSD_FMAX} Hz  method={lconfig.PSD_METHOD}")

    c = ElysClient(gconfig.BASE_URL, gconfig.USERNAME, gconfig.PASSWORD, data_base_url=gconfig.DATA_BASE_URL)
    c.login()
    ui.ok(f"登录成功 ({gconfig.USERNAME})")

    # 预检：Group 节点是否已部署
    use_group = check_group_support(c)

    results = {}
    for task in TASKS:
        results[task] = run_pipeline(c, task, use_group)

    ui.section("总结")
    for task, ok in results.items():
        col = ui.GREEN if ok else ui.RED
        ui.kv(TASK_LABEL[task], f"{col}{'通过' if ok else '失败'}{ui.RESET}")

    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
