"""
03_resting_state / setup —— 批量上传所有 EDF 到同一个 Study。

data/ 下所有 sub-{ID}_task-{eo|ec}_eeg.edf 文件全部上传，每个文件一条 recording，
subject 和 task 从文件名自动解析，不需要手动填写。全部 recording 归到同一个 Dataset / Study，
之后 run.py 的 LoadData filter 模式可以按 tasks=eo / tasks=ec 分别选出 30 条。

幂等：dataset 同 code 复用；replace_existing=True，重跑会建新版本（recording id 不变）。
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


def main():
    ui.section("静息态 批量上传 EDF")
    c = ElysClient(gconfig.BASE_URL, gconfig.USERNAME, gconfig.PASSWORD, data_base_url=gconfig.DATA_BASE_URL)
    c.login()
    ui.ok(f"登录成功 ({gconfig.USERNAME}) @ {gconfig.BASE_URL}")

    ds_id, study_id, mount_id = _ensure_dataset(c)
    _writeback_config(ds_id=ds_id, study_id=study_id, mount_id=mount_id)

    edfs = _find_edfs(DATA_DIR)
    if not edfs:
        ui.fail(f"{DATA_DIR} 里没有 sub-*_task-*_eeg.edf 文件")
        sys.exit(1)
    ui.info(f"发现 {len(edfs)} 个 EDF（{sum(1 for _,_,t in edfs if t=='eo')} EO + "
            f"{sum(1 for _,_,t in edfs if t=='ec')} EC）")

    # ── Phase 1：一次请求提交全部 EDF（后端从文件名解析 BIDS）──────────────
    ui.info(f"  批量提交 {len(edfs)} 个 EDF（一次请求）…")
    all_paths = [p for p, _, _ in edfs]
    try:
        batch = c.import_recordings_batch_async(
            study_id,
            all_paths,
            dataset_asset_id=ds_id,
            session=lconfig.SESSION,
            run=lconfig.RUN,
            replace_existing=False,
            show_progress=True,
        )
    except ElysAPIError as e:
        ui.died(f"批量提交失败：{e}")
        sys.exit(1)

    submitted = [(r["task_id"], r["filename"]) for r in batch["results"] if r["status"] == "submitted"]
    skip_count = batch["n_skipped"]
    err_count  = batch["n_error"]
    for r in batch["results"]:
        if r["status"] == "error":
            ui.warn(f"  {r['filename']}：{r['message']}")
    ui.ok(f"Phase 1 完成：{batch['n_submitted']} 已入队 / {skip_count} 跳过 / {err_count} 解析错误 / {len(edfs)} 总计")

    # ── Phase 2：等所有 Celery 任务完成（Celery 并行跑，轮询串行无妨）────────
    ok_count = 0
    first_recording_id = ""

    for i, (task_id, fname) in enumerate(submitted, 1):
        ui.info(f"  [{i}/{len(submitted)}] 等待 {fname}")
        try:
            task_obj = c.wait_import_task(
                study_id, task_id,
                show_progress=True,
                poll_timeout=1800,
            )
        except TimeoutError as e:
            ui.warn(f"    超时跳过：{e}")
            continue
        except (ElysAPIError, requests.RequestException) as e:
            ui.warn(f"    等待失败：{e}")
            continue

        if task_obj.get("status") == "succeeded":
            rec = (task_obj.get("result_json") or {}).get("recording") or {}
            rec_id = rec.get("id", "")
            ok_count += 1
            if not first_recording_id:
                first_recording_id = rec_id
            ui.ok(f"    recording_id={rec_id}  通道={rec.get('n_channels')}  "
                  f"采样率={rec.get('sfreq')}Hz  时长={rec.get('duration_seconds')}s")
        else:
            errors = (task_obj.get("error_json") or {}).get("errors") or []
            detail = errors[0].get("message") if errors else task_obj.get("status")
            ui.warn(f"    转换失败：{detail}")

    ui.ok(f"Phase 2 完成：{ok_count} 成功 / {len(submitted) - ok_count} 失败 / {skip_count} 跳过")

    # 用第一条 recording 读一次元信息，打印通道名供 REF_CHANNELS 回填
    if first_recording_id:
        _print_meta(c, study_id=study_id, recording_id=first_recording_id)


def _ensure_dataset(c: ElysClient) -> tuple[str, str, str]:
    existing = c.find_dataset_by_code(lconfig.DATASET_CODE)
    if existing is not None:
        ds_id = existing.get("id", "")
        study_id = existing.get("primary_study_id", "") or ""
        ui.info(f"dataset 已存在  code={lconfig.DATASET_CODE}  id={ds_id}  study={study_id}")
        if not (ds_id and study_id):
            ui.fail(f"复用的 dataset 缺 id/study，完整记录：{existing}")
            sys.exit(1)
        return ds_id, study_id, ""

    own_study = c.find_study_by_code(lconfig.STUDY_CODE)
    if own_study is not None:
        study_id = own_study.get("id", "")
        ui.info(f"新建 dataset，挂到已有 study (code={lconfig.STUDY_CODE}, id={study_id})")
        kwargs = dict(study_mode="existing", study_id=study_id)
    else:
        ui.info(f"新建 dataset + study (code={lconfig.STUDY_CODE})")
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
        ui.fail(f"bootstrap 返回缺字段，完整响应：{result}")
        sys.exit(1)
    ui.ok(f"新建完成  dataset_id={ds_id}  study_id={study_id}  mount_id={mount_id}")
    return ds_id, study_id, mount_id


def _find_edfs(data_dir: Path) -> list[tuple[Path, str, str]]:
    """发现 data/ 下所有 sub-*_task-*_eeg.edf，返回 [(path, subject, task), ...]。"""
    results = []
    for f in sorted(data_dir.glob("sub-*_task-*_eeg.edf")):
        parts = f.stem.split("_")
        sub  = next((p.split("-", 1)[1] for p in parts if p.startswith("sub-")),  "")
        task = next((p.split("-", 1)[1] for p in parts if p.startswith("task-")), "")
        if sub and task:
            results.append((f, sub, task))
        else:
            ui.warn(f"  跳过 {f.name}：无法解析 sub / task")
    return results



def _writeback_config(*, ds_id: str, study_id: str, mount_id: str) -> None:
    """把 STUDY_ID / DATASET_ID / MOUNT_ID 写回 config_local.py。"""
    cfg  = HERE / "config_local.py"
    text = cfg.read_text(encoding="utf-8")
    updates = {"STUDY_ID": f'"{study_id}"', "DATASET_ID": f'"{ds_id}"'}
    if mount_id:
        updates["MOUNT_ID"] = f'"{mount_id}"'
    for key, value in updates.items():
        pattern = re.compile(rf"(?m)^(\s*{key}\s*=\s*)(.*?)(\s*#.*)?$")
        text, n = pattern.subn(lambda m: f"{m.group(1)}{value}{m.group(3) or ''}", text, count=1)
        if n == 0:
            ui.warn(f"config_local.py 里没找到 {key}=，跳过回填")
    cfg.write_text(text, encoding="utf-8")
    ui.ok("已回填 config_local.py：STUDY_ID / DATASET_ID / MOUNT_ID")


def _print_meta(c: ElysClient, *, study_id: str, recording_id: str) -> None:
    """读第一条 recording 的通道名，供 REF_CHANNELS 回填参考。"""
    try:
        res = c.resolve_load_data(study_id, [recording_id])
    except (ElysAPIError, requests.RequestException) as e:
        ui.warn(f"resolve 元信息失败（不影响上传）：{e}")
        return
    infos = res.get("data_infos") or []
    if not infos:
        return
    info     = infos[0]
    ch_names = info.get("ch_names") or []
    ui.section("第一条 recording 通道名（按需回填 config_local.py 的 REF_CHANNELS）")
    ui.info(f"通道数={info.get('n_channels')}  采样率={info.get('sfreq')}Hz")
    ui.info(f"通道名：{ch_names}")


if __name__ == "__main__":
    try:
        main()
    except ElysAPIError as e:
        ui.died(f"API 调用失败：{e}")
        sys.exit(1)
    except requests.RequestException as e:
        ui.died(f"网络或连接失败：{e}")
        ui.info(f"BASE_URL = {gconfig.BASE_URL}")
        sys.exit(1)
