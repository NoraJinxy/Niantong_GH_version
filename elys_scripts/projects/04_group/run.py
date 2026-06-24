"""
04_group / run —— 两组 Grand Average 工作流：sensory 的 ERP，rest 的 PSD。

产出 2 条 group-analysis 工作流（idempotent：按名字找到就更新、没有才新建，重跑不堆重复）：
  · "Group ERP — combined"     —— sensory（run 04/11），S3/S4/S5 同一张图：共享预处理 + 三条分支，
       一条 pipeline 出 3 个 grand average evoked（产物名 S3/S4/S5）。
  · "Group PSD — rest S1/S2"   —— rest（run 01/02/14/15），按 S1/S2 把录制分组（每条 rest 录制只带一个
       条件），各条件一条独立链，一条 pipeline 出 2 个 grand average PSD（频域 mean ± SEM）。
（曾有的 3 条单条件 ERP 工作流 "Group ERP — S3/S4/S5" 已砍掉——被 combined 覆盖；脚本启动时若库里还留着会自动删。）

为什么一个 condition 一条分支、不在一条分支里切多类：Group Merge 无脑沿 unit 轴堆叠、不按 condition
分组（engine/group/stack.align_and_stack），多类一起喂会被混成一锅。所以合并工作流也是各 condition 独立分支。

链路（每条分支）：
  ERP：LoadData(explicit, 12 条 sensory) [→ Resample 250Hz] → Bandpass(0.1-30) → Notch → Bad Channels
       [→ Re-reference] → Epoch(只切该 condition) → Baseline → ERP Average → Group Merge → Grand Average
  PSD：LoadData(explicit, rest) [→ Resample 250Hz] → Bandpass(1-45) → Notch → Bad Channels [→ Re-reference]
       → Epoch(只切该标签, 0-60s) → PSD(Welch) → Group Merge → Grand Average
  （Resample 为可选降采样，由 config_local.RESAMPLE_SFREQ 控制，置 None 关闭——见该配置项说明。）

LoadData 为什么用 explicit 而非 filter：前端 LoadData 面板是「explicit-by-design」（task #61，
Selected File = dataset_ids = 真正输入），filter 模式后端能跑但卡片显示「未选择数据」。所以这里先
resolve 把 sensory 的 12 个 recording id 取出来，按 explicit 喂给 LoadData，卡片就正常显示 12 个文件。

前置：先跑 setup.py 上传（STUDY_ID / DATASET_ID 已自动回填）。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]  # elys_scripts/
sys.path.insert(0, str(ROOT / "common"))

from elys_client import ElysClient, ElysAPIError  # noqa: E402
import config as gconfig                           # noqa: E402
import config_local as lconfig                     # noqa: E402
import ui                                          # noqa: E402

# 跑 Grand Average 需要这两个 Group 节点都已部署
GROUP_NODE_TYPES = {"eeg/group/merge", "eeg/group/average"}


def _resample_sfreq():
    """降采样目标采样率。读 config_local.RESAMPLE_SFREQ（该文件被 .gitignore 忽略、每台机各自维护），
    缺省 = 250Hz（默认开降采样）；本地 config 置 None / 0 即关闭。getattr 兜底：干净环境的
    config_local 没这行也不会 AttributeError，只是回落到默认 250。"""
    return getattr(lconfig, "RESAMPLE_SFREQ", 250)


def _sensory_filter() -> dict:
    """LoadData filter：选 task-sensory 的全部记录（run 04/11，跨被试/session）。"""
    return {
        "subjects": "all",
        "sessions": "all",
        "tasks": [lconfig.SENSORY_TASK],
        "runs": "all",
        "qa_status": "all",
        "require_fif": True,
    }


def resolve_sensory(c: ElysClient) -> tuple[list[str], list[str]]:
    """resolve sensory（filter 模式）→ (recording_ids, event_labels)。打印命中数 + 真实标签供核对。"""
    res = c.resolve_load_data(lconfig.STUDY_ID, selection_mode="filter", dataset_filter=_sensory_filter())
    infos = res.get("data_infos") or []
    ids = [str(di.get("dataset_id")) for di in infos if di.get("dataset_id")]
    labels = sorted({lbl for di in infos for lbl in (di.get("event_labels") or [])})
    ui.info(f"sensory（{lconfig.SENSORY_TASK}）命中 {len(infos)} 条 recording → {len(ids)} 个 id（explicit 喂 LoadData）")
    ui.info(f"真实事件标签（{len(labels)} 种）：{labels}")
    ui.info(f"将按 codes={lconfig.ERP_EVENT_CODES} 做 regex 容错匹配（免数空格）")
    return ids, labels


def _rest_filter() -> dict:
    """LoadData filter：选 task-rest 的全部记录（run 01/02/14/15，跨被试/session）。"""
    return {
        "subjects": "all",
        "sessions": "all",
        "tasks": [lconfig.REST_TASK],
        "runs": "all",
        "qa_status": "all",
        "require_fif": True,
    }


def resolve_rest(c: ElysClient) -> list[dict]:
    """resolve rest（filter 模式）→ 每条 recording 的 {id, labels}。
    打印命中数 + 全部标签 + **每条录制各自带哪些刺激标签**（看清 S1/S2 是每条都有、还是各带一个）。"""
    res = c.resolve_load_data(lconfig.STUDY_ID, selection_mode="filter", dataset_filter=_rest_filter())
    infos = res.get("data_infos") or []
    recs = [{"id": str(di.get("dataset_id")), "labels": list(di.get("event_labels") or [])}
            for di in infos if di.get("dataset_id")]
    union = sorted({lbl for r in recs for lbl in r["labels"]})
    ui.info(f"rest（{lconfig.REST_TASK}）命中 {len(recs)} 条 recording")
    ui.info(f"全部事件标签（{len(union)} 种）：{union}")
    for r in recs:
        stim = [lbl for lbl in r["labels"] if "New Segment" not in lbl]  # 去掉录制起始标记，只看刺激
        ui.info(f"  {r['id'][:8]}…  刺激标签={stim}")
    return recs


def _partition_rest_by_code(recs: list[dict], codes: list[str]) -> dict[str, list[str]]:
    """按条件把 rest 录制分组：每个 code 收「事件标签里含 S<code>」的录制 id（regex 容空格）。
    每条 rest 录制只带一个条件 → 各组天然 disjoint；某 code 命中 0 条则该分支跳过。"""
    out: dict[str, list[str]] = {}
    for code in codes:
        pat = re.compile(rf"S\s*0*{code}\b")
        out[code] = [r["id"] for r in recs if any(pat.search(lbl) for lbl in r["labels"])]
        ui.info(f"  条件 S{code}：{len(out[code])} 条录制")
    return out


def check_group_support(c: ElysClient) -> bool:
    """查后端已注册节点；True = Group Merge/Average 均已部署（可跑 Grand Average）。"""
    try:
        missing = GROUP_NODE_TYPES - c.list_node_types()
        if missing:
            ui.warn(f"Group 节点未部署（{', '.join(sorted(missing))}）→ 只跑到 ERP，跳过 Grand Average")
            return False
        ui.ok("Group 节点已部署 → 完整链（ERP → Merge → Grand Average）")
        return True
    except ElysAPIError as e:
        ui.warn(f"查询节点类型失败（{e}），保守跳过 Group 节点")
        return False


def _condition_rule(code: str) -> dict:
    """一个刺激 code → 一条 regex condition。容空格：'Stimulus/S  3' / 'S 3' / 'S3' 都命中。"""
    return {"name": f"S{code}", "pattern": rf"S\s*0*{code}\b", "mode": "regex"}


def _ref_desc(ref: list) -> str:
    """重参考的简短描述：空=跳过；多于 4 导=CAR N 导；否则列出通道。"""
    if not ref:
        return "跳过"
    return f"CAR {len(ref)} 导" if len(ref) > 4 else str(list(ref))


def build_definition(codes: list[str], dataset_ids: list[str], use_group: bool, label_prefix: str = "") -> dict:
    """codes 单个 → 一条分支；多个 → 共享预处理 + 每个 code 一条分支（纵向错开）。
    LoadData 用 explicit（dataset_ids），对齐前端 explicit-by-design、卡片正常显示文件。
    label_prefix：给 Group Merge 的 label 加前缀，让合并工作流的 grand avg 文件名与单独工作流区分。
    """
    use_reref = bool(lconfig.REF_SENSORY)
    nodes: list[dict] = []
    links: list[dict] = []

    def add_link(src: str, dst: str) -> None:
        # link id 用 src-dst（每条边天然唯一），不数 links 长度。
        links.append({"id": f"{src}-{dst}", "from": {"node": src, "port": "output"}, "to": {"node": dst, "port": "input"}})

    # ── 共享预处理段（一行；节点用 list 顺排，位置/连线按下标自动算，插 Resample 不用挪坐标）──
    shared: list[tuple[str, str, str, dict]] = [
        ("ld", "eeg/data/load", "LoadData (sensory)",
         {"selection_mode": "explicit", "dataset_ids": dataset_ids, "dataset_filter": {}}),
    ]
    rs_sfreq = _resample_sfreq()
    if rs_sfreq:   # 可选降采样：紧跟 LoadData，砍掉下游所有重节点的 1000Hz 线性放大
        shared.append(("rs", "eeg/preproc/resample", f"Resample ({int(rs_sfreq)}Hz)",
                       {"sfreq": rs_sfreq}))
    shared += [
        ("bw", "eeg/filter/apply", "Bandpass (IIR)",
         {"filter_type": "bandpass", "method": "iir",
          "l_freq": lconfig.BANDPASS_L, "h_freq": lconfig.BANDPASS_H, "order": 4}),
        ("nf", "eeg/filter/apply", "Notch",
         {"filter_type": "notch", "notch_freq": lconfig.NOTCH_FREQ, "notch_harmonics": 3}),
        ("bc", "eeg/preproc/bad_channels", "Bad Channels",
         {"method": lconfig.BAD_CHAN_METHOD, "action": lconfig.BAD_CHAN_ACTION}),
    ]
    if use_reref:
        shared.append(("rr", "eeg/preproc/rereference", "Re-reference",
                       {"ref_channels": lconfig.REF_SENSORY}))
    for si, (nid, ntype, title, params) in enumerate(shared):
        nodes.append({"id": nid, "type": ntype, "title": title, "position": [80 + si * 320, 80], "params": params})
        if si > 0:
            add_link(shared[si - 1][0], nid)

    prev = shared[-1][0]
    branch_x = 80 + len(shared) * 320

    # ── 每个 condition 一条分支（纵向错开 240px）─────────────────────────
    for bi, code in enumerate(codes):
        cname = f"S{code}"
        y = 80 + bi * 240
        chain = [
            (f"ep-{cname}", "eeg/epoch/segment", f"Epoch {cname}",
             {"conditions": [_condition_rule(code)], "tmin": lconfig.EPOCH_TMIN, "tmax": lconfig.EPOCH_TMAX, "split_by": "none"}),
            (f"bl-{cname}", "eeg/epoch/baseline", f"Baseline {cname}",
             {"baseline_tmax": lconfig.BASELINE_TMAX}),
            (f"erp-{cname}", "eeg/analysis/erp", f"ERP {cname}",
             {"condition": [cname]}),
        ]
        if use_group:
            chain += [
                (f"gm-{cname}", "eeg/group/merge", f"Group Merge {cname}",
                 {"unit_label": lconfig.GA_UNIT, "label": f"{label_prefix}{cname}"}),
                (f"ga-{cname}", "eeg/group/average", f"Grand Avg {cname}",
                 {"weighted": lconfig.GA_WEIGHTED}),
            ]
        src = prev
        for ci, (nid, ntype, title, params) in enumerate(chain):
            nodes.append({"id": nid, "type": ntype, "title": title, "position": [branch_x + ci * 320, y], "params": params})
            add_link(src, nid)
            src = nid

    return {"graph": {"nodes": nodes, "links": links}}


def build_rest_psd_definition(codes: list[str], ids_by_code: dict[str, list[str]], use_group: bool) -> dict:
    """静息态 PSD grand average：每个静息标签一条 **独立** 链（各自的 LoadData 只喂「带该标签」的录制）。
    每条链：LoadData(该条件录制) → Bandpass(rest 频段 1-45) → Notch → Bad Channels [→ Re-reference]
            → Epoch(只切该标签, 0-60s) → PSD(Welch) → Group Merge → Grand Average。

    为什么不像 ERP 那样共享预处理：每条 rest 录制只带一个条件（S1 *或* S2），各条件的录制是不同子集，
    输入不同 → 预处理无法共享 → 每条件一条独立子图（一条 pipeline 里多条互不相连的完整链）。
    PSD 是频域、无基线步；LoadData 走 explicit（对齐前端 explicit-by-design、卡片正常显示文件）。
    """
    use_reref = bool(lconfig.REF_REST)
    nodes: list[dict] = []
    links: list[dict] = []

    def add_link(src: str, dst: str) -> None:
        links.append({"id": f"{src}-{dst}", "from": {"node": src, "port": "output"}, "to": {"node": dst, "port": "input"}})

    for bi, code in enumerate(codes):
        cname = f"S{code}"
        y = 80 + bi * 260
        ids = ids_by_code.get(code, [])
        chain: list[tuple[str, str, str, dict]] = [
            (f"ld-{cname}", "eeg/data/load", f"LoadData {cname} ({len(ids)})",
             {"selection_mode": "explicit", "dataset_ids": ids, "dataset_filter": {}}),
            (f"bw-{cname}", "eeg/filter/apply", f"Bandpass {cname}",
             {"filter_type": "bandpass", "method": "iir",
              "l_freq": lconfig.REST_BANDPASS_L, "h_freq": lconfig.REST_BANDPASS_H, "order": 4}),
            (f"nf-{cname}", "eeg/filter/apply", f"Notch {cname}",
             {"filter_type": "notch", "notch_freq": lconfig.NOTCH_FREQ, "notch_harmonics": 3}),
            (f"bc-{cname}", "eeg/preproc/bad_channels", f"Bad Channels {cname}",
             {"method": lconfig.BAD_CHAN_METHOD, "action": lconfig.BAD_CHAN_ACTION}),
        ]
        rs_sfreq = _resample_sfreq()
        if rs_sfreq:   # 可选降采样：插在 LoadData 后、Bandpass 前（位置/连线按下标自动算）
            chain.insert(1, (f"rs-{cname}", "eeg/preproc/resample", f"Resample {cname} ({int(rs_sfreq)}Hz)",
                             {"sfreq": rs_sfreq}))
        if use_reref:
            chain.append((f"rr-{cname}", "eeg/preproc/rereference", f"Re-reference {cname}",
                          {"ref_channels": lconfig.REF_REST}))
        chain += [
            (f"ep-{cname}", "eeg/epoch/segment", f"Epoch {cname} (0-60s)",
             {"conditions": [_condition_rule(code)], "tmin": lconfig.REST_EPOCH_TMIN,
              "tmax": lconfig.REST_EPOCH_TMAX, "split_by": "none"}),
            (f"psd-{cname}", "eeg/analysis/psd", f"PSD {cname} (Welch)",
             {"condition": [cname], "fmin": lconfig.PSD_FMIN, "fmax": lconfig.PSD_FMAX, "method": lconfig.PSD_METHOD}),
        ]
        if use_group:
            chain += [
                (f"gm-{cname}", "eeg/group/merge", f"Group Merge {cname}",
                 {"unit_label": lconfig.GA_UNIT, "label": cname}),
                (f"ga-{cname}", "eeg/group/average", f"Grand Avg {cname}",
                 {"weighted": lconfig.GA_WEIGHTED}),
            ]
        for ci, (nid, ntype, title, params) in enumerate(chain):
            nodes.append({"id": nid, "type": ntype, "title": title, "position": [80 + ci * 320, y], "params": params})
            if ci > 0:
                add_link(chain[ci - 1][0], nid)

    return {"graph": {"nodes": nodes, "links": links}}


def ensure_pipeline(c: ElysClient, name: str, definition: dict) -> int:
    """按名字找到就更新、没有才新建——重跑保留同一条 pipeline（不堆重复）。返回 pipeline id。"""
    for p in c.list_pipelines(lconfig.STUDY_ID):
        if p.get("name") == name:
            c.update_pipeline(lconfig.STUDY_ID, p["id"], definition=definition)
            ui.ok(f"更新 pipeline #{p['id']}  {name}")
            return p["id"]
    p = c.create_pipeline(lconfig.STUDY_ID, name, definition)
    ui.ok(f"新建 pipeline #{p['id']}  {name}")
    return p["id"]


def run_pipeline(c: ElysClient, name: str, definition: dict) -> bool:
    """ensure → validate → trigger → 等 → 打印每节点状态 + 产物。返回 True=成功。"""
    ui.section(f"Pipeline: {name}")
    pid = ensure_pipeline(c, name, definition)

    val = c.validate(lconfig.STUDY_ID, pid)
    for w in val["warnings"]:
        ui.warn(w["message"])
    if not val["valid"]:
        for e in val["errors"]:
            ui.info(f"{ui.RED}ERROR{ui.RESET} {e['message']}")
        ui.died(f"pipeline 校验失败：{name}")
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
        emsg = (err.get("errors") or [{}])[0].get("message", "") if err else ""
        st = nr.get("status", "?")
        col = ui.GREEN if st == "completed" else (ui.RED if st == "failed" else ui.YELLOW)
        ui.kv(nr.get("node_id", "?"), f"{col}{st}{ui.RESET}  {ui.GRAY}{emsg[:120]}{ui.RESET}")

    if final["status"] == "completed":
        derived = c.list_run_derived(lconfig.STUDY_ID, rid)
        ui.section(f"产物 {len(derived)} 个")
        for d in derived:
            dn = d.get("display_name") or d["id"]
            ui.info(f"  {dn}  type={d.get('data_type')}  {d.get('file_size_mb', 0):.1f} MB")
        ui.passed(f"{name} 跑通 · run {rid[:8]}")
        return True

    ui.died(f"{name} 未完成 · run {rid[:8]} · status={final['status']}")
    return False


def _delete_retired_pipelines(c: ElysClient) -> None:
    """删掉已从脚本里砍掉的旧工作流（3 条单条件 ERP，已被 combined 覆盖）→ 库里最终只剩 2 条。"""
    retired = {f"{lconfig.ERP_PIPELINE_PREFIX} — S{code}" for code in lconfig.ERP_EVENT_CODES}
    for p in c.list_pipelines(lconfig.STUDY_ID):
        if p.get("name") in retired:
            try:
                c.delete_pipeline(lconfig.STUDY_ID, p["id"])
                ui.info(f"删除已废弃工作流 #{p['id']}  {p.get('name')}")
            except Exception as e:
                ui.warn(f"删除 {p.get('name')} 失败（忽略）：{e}")


def main():
    ui.section("Group ERP + Grand Average（sensory：S 3/4/5）")
    if not lconfig.STUDY_ID:
        ui.fail("STUDY_ID 为空，先跑 setup.py 建库 + 上传")
        return

    reref = f"Re-reference: rest={_ref_desc(lconfig.REF_REST)}  sensory={_ref_desc(lconfig.REF_SENSORY)}"
    ui.info(reref)
    ui.info(f"Epoch: [{lconfig.EPOCH_TMIN}, {lconfig.EPOCH_TMAX}]s  baseline=[段首, {lconfig.BASELINE_TMAX}]s")

    c = ElysClient(gconfig.BASE_URL, gconfig.USERNAME, gconfig.PASSWORD, data_base_url=gconfig.DATA_BASE_URL)
    c.login()
    ui.ok(f"登录成功 ({gconfig.USERNAME})")

    ids, _ = resolve_sensory(c)
    if not ids:
        ui.died("resolve 没拿到任何 sensory recording id，无法用 explicit 模式（先确认 setup 上传成功）")
        return
    use_group = check_group_support(c)

    codes = list(lconfig.ERP_EVENT_CODES)
    results: dict[str, bool] = {}

    # 先删掉已从脚本砍掉的旧工作流（3 条单条件 ERP，已被 combined 覆盖）→ 库里最终只剩 2 条
    _delete_retired_pipelines(c)

    # 1) ERP 合并工作流（sensory：S3/S4/S5 同图，共享预处理 + 三条分支 → 3 个 grand average evoked）
    combined_name = f"{lconfig.ERP_PIPELINE_PREFIX} — combined"
    results[combined_name] = run_pipeline(
        c, combined_name, build_definition(codes, ids, use_group, label_prefix="")
    )

    # 2) 静息态 PSD 工作流（rest：S1/S2）。每条 rest 录制只带一个条件 → 按条件分组，
    #    各分支只喂「带该标签」的录制（disjoint），各自独立一条链 LoadData→…→PSD→Merge→Avg。
    rest_recs = resolve_rest(c)
    psd_name = lconfig.PSD_PIPELINE_NAME
    ids_by_code = _partition_rest_by_code(rest_recs, list(lconfig.REST_EVENT_CODES))
    active_codes = [code for code in lconfig.REST_EVENT_CODES if ids_by_code.get(code)]
    if active_codes:
        results[psd_name] = run_pipeline(c, psd_name, build_rest_psd_definition(active_codes, ids_by_code, use_group))
    else:
        ui.warn(f"没有任何 rest 录制带 S{' / S'.join(lconfig.REST_EVENT_CODES)} 标签 → 跳过「{psd_name}」"
                f"（看上面每条录制的刺激标签，照实际改 REST_EVENT_CODES）")
        results[psd_name] = False

    ui.section("总结")
    for name, ok in results.items():
        col = ui.GREEN if ok else ui.RED
        ui.kv(name, f"{col}{'通过' if ok else '失败'}{ui.RESET}")
    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
