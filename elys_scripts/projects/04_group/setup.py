"""
04_group / setup —— 建 Dataset 资产 + 配对 Study + 自动挂载，再批量上传 36 条 BrainVision。

组分析测试链的「准备数据」步（跑 pipeline 的 run.py 待后端 Group 节点定稿后再补）：
  1) ensure dataset：同 DATASET_CODE 已存在则复用，否则 bootstrap 一次建齐 dataset+study+mount
  2) discover：扫 data/ 下 sub<NNN><ses>_r<NN>.vhdr，解析 subject/session/run，按 run 号定 task
  3) upload：每条三件套(.vhdr/.eeg/.vmrk)作为一条 recording 导入到该 asset

数据：data/ 下 sub{被试}{session}_r{run}.{vhdr,eeg,vmrk}
  3 被试(007/008/009) × 2 session(a/b) × 6 run(01/02/04/11/14/15) = 36 条 recording
  task：rest(01/02/14/15) / sensory(04/11)，查 config_local.TASK_BY_RUN

上传方式：逐条**同步导入**（POST /recordings/import），跟浏览器批量上传走的是同一条路——
  每条三件套传上去后，服务端在「这次请求里」就地转成 FIF 再返回，一次只处理一条。
  不用异步端点(/import-async)：那条会给每个文件派一个 Celery 任务，36 个一次涌进去挤同一个
  worker 池会卡住（长期 queued）；同步端点在 web 进程里就地转、压根不碰 Celery，跟浏览器一样稳。

幂等 / 抗重置：dataset 同 code 复用；STUDY_CODE 认领自己的 study；replace_existing=True。
            重跑（未重置环境）传同样的文件 → 服务端按 checksum 去重直接回 409，脚本当「已存在」
            跳过、不算失败（标准流程是先重部署清库再跑，那时从零全新导入）。

用法：
  1. common/config.py 里 BASE_URL / USERNAME / PASSWORD 已填好（一般跟随部署 profile）
  2. data/ 里放好 36 套 BrainVision 三件套
  3. python setup.py   （跑完自动回填 STUDY_ID / DATASET_ID / MOUNT_ID）
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]  # elys_scripts/
sys.path.insert(0, str(ROOT / "common"))

import requests                                    # noqa: E402
from elys_client import ElysClient, ElysAPIError   # noqa: E402
import config as gconfig                            # noqa: E402
import config_local as lconfig                      # noqa: E402
import ui                                           # noqa: E402

DATA_DIR = HERE / "data"
_BV_EXTS = (".vhdr", ".eeg", ".vmrk")
# sub007a_r01 → subject=007  session=a  run=01
_NAME_RE = re.compile(r"^sub(?P<subject>\d+)(?P<session>[a-zA-Z]+)_r(?P<run>\d+)$")


def main():
    ui.section("Group 多任务 批量上传 BrainVision")
    c = ElysClient(gconfig.BASE_URL, gconfig.USERNAME, gconfig.PASSWORD, data_base_url=gconfig.DATA_BASE_URL)
    c.login()
    ui.ok(f"登录成功 ({gconfig.USERNAME}) @ {gconfig.BASE_URL}")

    ds_id, study_id, mount_id = _ensure_dataset(c)
    _writeback_config(ds_id=ds_id, study_id=study_id, mount_id=mount_id)

    recs = _discover_recordings(DATA_DIR)
    if not recs:
        ui.fail(f"{DATA_DIR} 里没有可识别的 BrainVision（sub<NNN><ses>_r<NN>.vhdr）")
        sys.exit(1)
    n_rest    = sum(1 for r in recs if r["task"] == "rest")
    n_sensory = sum(1 for r in recs if r["task"] == "sensory")
    subjects  = sorted({r["subject"] for r in recs})
    sessions  = sorted({r["session"] for r in recs})
    ui.info(f"发现 {len(recs)} 条 recording  被试={subjects}  session={sessions}  "
            f"（rest {n_rest} + sensory {n_sensory}）")

    _upload_all(c, study_id=study_id, ds_id=ds_id, recs=recs)
    _verify_uploaded_recordings(c, study_id=study_id, ds_id=ds_id, recs=recs)


def _ensure_dataset(c: ElysClient) -> tuple[str, str, str]:
    """确保目标 dataset 存在，返回 (dataset_id, study_id, mount_id)。同 code 已存在则复用。"""
    existing = c.find_dataset_by_code(lconfig.DATASET_CODE)
    if existing is not None:
        ds_id = existing.get("id", "")
        study_id = existing.get("primary_study_id", "") or ""
        ui.info(f"dataset 已存在  code={lconfig.DATASET_CODE}  id={ds_id}  study={study_id}")
        if not (ds_id and study_id):
            ui.fail(f"复用的 dataset 缺 id / study，完整记录：{existing}")
            sys.exit(1)
        return ds_id, study_id, ""

    own_study = c.find_study_by_code(lconfig.STUDY_CODE)
    if own_study is not None:
        study_id = own_study.get("id", "")
        ui.info(f"新建 dataset, 挂到本用例已有 study (code={lconfig.STUDY_CODE}, id={study_id})")
        kwargs = dict(study_mode="existing", study_id=study_id)
    else:
        ui.info(f"新建 dataset + 新建 study (code={lconfig.STUDY_CODE})")
        kwargs = dict(
            study_mode="create",
            study_code=lconfig.STUDY_CODE,
            study_name=lconfig.STUDY_NAME,
            study_description=lconfig.STUDY_DESCRIPTION,
        )
    kwargs.update(
        dataset_name=lconfig.DATASET_NAME,
        dataset_code=lconfig.DATASET_CODE,
        dataset_description=lconfig.DATASET_DESCRIPTION,
    )
    result = c.bootstrap_dataset(**kwargs)
    ds_id    = (result.get("dataset_asset") or {}).get("id", "")
    study_id = (result.get("study") or {}).get("id", "")
    mount_id = (result.get("mount") or {}).get("id", "")
    if not (ds_id and study_id):
        ui.fail(f"bootstrap 返回里缺关键字段，完整响应：{result}")
        sys.exit(1)
    ui.ok(f"新建完成  dataset_id={ds_id}  study_id={study_id}  mount_id={mount_id}")
    return ds_id, study_id, mount_id


def _discover_recordings(data_dir: Path) -> list[dict]:
    """扫 data/ 下所有 .vhdr，解析 subject/session/run，按 run 号查 task。
    返回按 (subject, session, run) 排序的 [{triplet, subject, session, run, task, label}, ...]。
    文件名不符规范、run 没配 task、或三件套不全的，逐条告警跳过、不中断整批。"""
    if not data_dir.is_dir():
        ui.fail(f"数据目录不存在：{data_dir}")
        sys.exit(1)
    recs: list[dict] = []
    for vhdr in sorted(data_dir.glob("*.vhdr")):
        m = _NAME_RE.match(vhdr.stem)
        if not m:
            ui.warn(f"  跳过 {vhdr.name}：文件名不符合 sub<NNN><ses>_r<NN>")
            continue
        subject, session, run = m.group("subject"), m.group("session"), m.group("run")
        task = lconfig.TASK_BY_RUN.get(run)
        if task is None:
            ui.warn(f"  跳过 {vhdr.name}：run={run} 不在 TASK_BY_RUN（未指定 task）")
            continue
        triplet = _build_triplet(vhdr)
        if triplet is None:
            continue
        recs.append({
            "triplet": triplet,
            "subject": subject,
            "session": session,
            "run": run,
            "task": task,
            "label": f"sub-{subject} ses-{session} run-{run} task-{task}",
        })
    recs.sort(key=lambda r: (r["subject"], r["session"], r["run"]))
    return recs


def _build_triplet(vhdr: Path) -> list[Path] | None:
    """同名 .vhdr/.eeg/.vmrk 凑齐返回三件套（vhdr 在前）；缺件告警返回 None（跳过该条）。"""
    triplet = [vhdr.with_suffix(ext) for ext in _BV_EXTS]
    missing = [p.name for p in triplet if not p.exists()]
    if missing:
        ui.warn(f"  跳过 {vhdr.name}：三件套不全，缺 {missing}")
        return None
    return triplet


def _upload_all(c: ElysClient, *, study_id: str, ds_id: str, recs: list[dict]) -> None:
    """逐条同步导入（仿浏览器：一次一条，服务端就地转 FIF），不走 Celery 异步、不会堆积卡住。"""
    total = len(recs)
    ui.section(f"逐条同步上传 {total} 条 recording 到 asset {ds_id}（一次一条，仿浏览器）")
    ok_count = skip_count = fail_count = 0
    first_recording_id = ""
    for i, r in enumerate(recs, 1):
        ui.info(f"  [{i}/{total}] {r['label']}  ({r['triplet'][0].stem} 三件套)")
        try:
            result = c.import_recording(
                study_id,
                r["triplet"],
                subject=r["subject"],
                task=r["task"],
                session=r["session"],
                run=r["run"],
                dataset_asset_id=ds_id,
                replace_existing=True,
                show_progress=True,
            )
        except ElysAPIError as e:
            if e.status_code == 409:        # checksum 去重：同文件已在库 → 当「已存在」跳过，不算失败
                skip_count += 1
                ui.warn("    已存在（409 去重），跳过")
                continue
            fail_count += 1
            ui.warn(f"    导入失败：{e}")
            continue
        except requests.RequestException as e:
            fail_count += 1
            ui.warn(f"    网络失败：{e}")
            continue
        rec = result.get("recording") or {}
        ok_count += 1
        if not first_recording_id:
            first_recording_id = rec.get("id", "")
        ui.ok(f"    recording_id={rec.get('id', '')}  通道={rec.get('n_channels')}  "
              f"采样率={rec.get('sfreq')}Hz  时长={rec.get('duration_seconds')}s  "
              f"事件={rec.get('n_events')}")

    if fail_count == 0 and (ok_count + skip_count) == total:
        ui.passed(f"完成：{ok_count} 新增 / {skip_count} 已存在跳过 / {total} 总计")
    else:
        ui.died(f"上传不完整：{ok_count} 新增 / {skip_count} 跳过 / {fail_count} 失败 / {total} 总计")
        sys.exit(1)

    # 用第一条成功的 recording 读一次元信息，打印通道名 / 事件标签供参考
    if first_recording_id:
        _print_meta(c, study_id=study_id, recording_id=first_recording_id)


def _verify_uploaded_recordings(c: ElysClient, *, study_id: str, ds_id: str, recs: list[dict]) -> None:
    """Fail fast if the remote study does not contain the full 04_group recording set."""
    expected_total = len(recs)
    expected_subjects = sorted({f"sub-{r['subject']}" for r in recs})
    expected_sessions = sorted({f"ses-{r['session']}" for r in recs})
    expected_tasks = sorted({f"task-{r['task']}" for r in recs})

    try:
        res = c._session.get(
            f"{c.base_url}/studies/{study_id}/recordings",
            params={"limit": max(500, expected_total * 2)},
            timeout=c.timeout,
        )
        res.raise_for_status()
        rows = res.json().get("recordings", [])
    except requests.RequestException as e:
        ui.died(f"上传后完整性复核失败：{e}")
        sys.exit(1)

    if any(r.get("dataset_asset_id") for r in rows):
        rows = [r for r in rows if r.get("dataset_asset_id") == ds_id]
    actual_subjects = sorted({r.get("bids_subject_id") or r.get("subject") or "" for r in rows if r})
    actual_sessions = sorted({r.get("session") or "" for r in rows if r.get("session")})
    actual_tasks = sorted({r.get("task") or "" for r in rows if r.get("task")})

    problems = []
    if len(rows) != expected_total:
        problems.append(f"recording 数 {len(rows)} != {expected_total}")
    if actual_subjects != expected_subjects:
        problems.append(f"被试 {actual_subjects} != {expected_subjects}")
    if actual_sessions != expected_sessions:
        problems.append(f"session {actual_sessions} != {expected_sessions}")
    if actual_tasks != expected_tasks:
        problems.append(f"task {actual_tasks} != {expected_tasks}")

    if problems:
        ui.died("上传后完整性复核未通过：" + "；".join(problems))
        sys.exit(1)

    ui.passed(
        f"完整性复核通过：{len(rows)} 条 recording / "
        f"{len(actual_subjects)} 被试 / {len(actual_sessions)} session / {len(actual_tasks)} task"
    )


def _writeback_config(*, ds_id: str, study_id: str, mount_id: str) -> None:
    """把 STUDY_ID / DATASET_ID / MOUNT_ID 写回 config_local.py，只改值、保留行尾注释。"""
    cfg  = HERE / "config_local.py"
    text = cfg.read_text(encoding="utf-8")
    updates = {"STUDY_ID": f'"{study_id}"', "DATASET_ID": f'"{ds_id}"'}
    if mount_id:                       # 复用已有 dataset 时拿不到 mount，就别把原值清掉
        updates["MOUNT_ID"] = f'"{mount_id}"'
    for key, value in updates.items():
        pattern = re.compile(rf"(?m)^(\s*{key}\s*=\s*)(.*?)(\s*#.*)?$")
        text, n = pattern.subn(lambda m: f"{m.group(1)}{value}{m.group(3) or ''}", text, count=1)
        if n == 0:
            ui.warn(f"config_local.py 里没找到 {key}= 这行，跳过回填")
    cfg.write_text(text, encoding="utf-8")
    ui.ok("已回填 config_local.py：STUDY_ID / DATASET_ID / MOUNT_ID")


def _print_meta(c: ElysClient, *, study_id: str, recording_id: str) -> None:
    """读第一条 recording 的通道名 / 事件标签，供需要时回填 pipeline 参数。"""
    try:
        res = c.resolve_load_data(study_id, [recording_id])
    except (ElysAPIError, requests.RequestException) as e:
        ui.warn(f"resolve 读元信息失败（不影响上传）：{e}")
        return
    infos = res.get("data_infos") or []
    if not infos:
        ui.warn(f"resolve 没返回 data_infos；errors={res.get('errors')}")
        return
    info = infos[0]
    ch_names     = info.get("ch_names") or []
    event_labels = info.get("event_labels") or []
    ui.section("第一条 recording 元信息（参考）")
    ui.info(f"通道数={info.get('n_channels')}  采样率={info.get('sfreq')}Hz")
    ui.info(f"通道名({len(ch_names)})：{ch_names}")
    ui.info(f"事件标签({len(event_labels)})：{event_labels}")


if __name__ == "__main__":
    try:
        main()
    except ElysAPIError as e:                  # 后端 4xx/5xx：打印响应体看真正原因
        ui.died(f"API 调用失败：{e}")
        sys.exit(1)
    except requests.RequestException as e:     # 连不上：网络 / 地址错 / 服务没起
        ui.died(f"网络或连接失败：{e}")
        ui.info(f"请确认服务已部署且地址可达：BASE_URL = {gconfig.BASE_URL}")
        sys.exit(1)
