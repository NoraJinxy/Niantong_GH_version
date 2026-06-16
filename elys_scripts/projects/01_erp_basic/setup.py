"""
01_erp_basic / setup —— 准备数据：建 Dataset 资产 + 配对 Study + 自动挂载，再上传 BrainVision 数据。

这是 ERP 测试链的第 1~2 步（第 3 步「跑 pipeline」在 run.py）：
  1) ensure dataset：同 DATASET_CODE 已存在则复用，否则 bootstrap 一次建齐 dataset+study+mount
  2) upload：把 data/ 里的 BrainVision 三件套(.vhdr/.eeg/.vmrk)同步导入到该 asset
  3) writeback + resolve：把新 ID 自动写回 config_local.py，并打印通道名/事件标签

后端约定：
  - 建 dataset 唯一入口是 POST /dataset-assets/bootstrap（裸 POST /dataset-assets 已删）
  - 上传走 POST /studies/{id}/recordings/import（6 月 Dataset→Recording 改名后的新端点）

用法：
  1. 确认 common/config.py 里 BASE_URL / USERNAME / PASSWORD 已填好
  2. config_local.py 里填 DATASET_* / STUDY_* 和 SUBJECT / TASK
  3. 把 BrainVision 三件套放进 data/（同名，如 sub093.vhdr/.eeg/.vmrk）
  4. python setup.py  （跑完自动回填 STUDY_ID / DATASET_IDS 等，接着跑 run.py 即可）

幂等 / 抗重置：dataset 同 code 复用；STUDY_ID 若指向已不存在的 study（测试服常被重置）会自动改回 create；
            上传用 replace_existing=True，重跑建新版本(version_seq+1)、recording id 不变。
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

DATA_DIR = HERE / "data"            # BrainVision 三件套放这里
_BV_EXTS = (".vhdr", ".eeg", ".vmrk")


def main():
    ui.section("准备数据：建库 + 上传")
    c = ElysClient(gconfig.BASE_URL, gconfig.USERNAME, gconfig.PASSWORD, data_base_url=gconfig.DATA_BASE_URL)
    c.login()
    ui.ok(f"登录成功 ({gconfig.USERNAME}) @ {gconfig.BASE_URL}")

    ds_id, study_id, mount_id = _ensure_dataset(c)
    recording_id = _upload(c, study_id=study_id, ds_id=ds_id)
    _writeback_config(study_id=study_id, ds_id=ds_id, mount_id=mount_id, recording_id=recording_id)
    _resolve_meta(c, study_id=study_id, recording_id=recording_id)


def _ensure_dataset(c: ElysClient) -> tuple[str, str, str]:
    """确保目标 dataset 存在，返回 (dataset_id, study_id, mount_id)。同 code 已存在则复用。"""
    # 同 code 的 dataset 已存在 → 直接复用（bootstrap 后端会 409 冲突，本端先查重避坑）
    existing = c.find_dataset_by_code(lconfig.DATASET_CODE)
    if existing is not None:
        ds_id = existing.get("id", "")
        study_id = existing.get("primary_study_id", "") or ""
        ui.info(f"dataset 已存在  code={lconfig.DATASET_CODE}  id={ds_id}  study={study_id}")
        if not (ds_id and study_id):
            ui.fail(f"复用的 dataset 缺 id / study，完整记录：{existing}")
            sys.exit(1)
        return ds_id, study_id, ""

    # dataset 不存在 → 新建。认领「本用例自己的」study 用 STUDY_CODE（稳定标识），不用数字 STUDY_ID：
    # 测试服每次重部署清库、study id 从 2026..01 顺序重发，stale 的数字 id 会指到「别的测试用例」刚建的
    # 同号 study，把第二个同名 mount（primary）往人家身上挂 → 409。按 code 认领则各用例天然隔离、可反复重跑。
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
    ds_id = (result.get("dataset_asset") or {}).get("id", "")
    study_id = (result.get("study") or {}).get("id", "")
    mount_id = (result.get("mount") or {}).get("id", "")
    if not (ds_id and study_id):
        ui.fail(f"bootstrap 返回里缺关键字段，完整响应：{result}")
        sys.exit(1)
    ui.ok(f"新建完成  dataset_id={ds_id}  study_id={study_id}  mount_id={mount_id}")
    return ds_id, study_id, mount_id


def _find_brainvision_triplet(data_dir: Path) -> list[Path]:
    """在 data_dir 里定位一套 BrainVision 三件套（.vhdr/.eeg/.vmrk，同名同目录）。"""
    vhdrs = sorted(data_dir.glob("*.vhdr"))
    if not vhdrs:
        ui.fail(f"{data_dir} 里没有 .vhdr，放一套 BrainVision 三件套再跑。")
        sys.exit(1)
    if len(vhdrs) > 1:
        ui.fail(f"{data_dir} 里有多套 .vhdr：{[p.name for p in vhdrs]}，一次只导入一套。")
        sys.exit(1)
    stem = vhdrs[0].stem
    triplet = [data_dir / f"{stem}{ext}" for ext in _BV_EXTS]
    missing = [p.name for p in triplet if not p.exists()]
    if missing:
        ui.fail(f"BrainVision 三件套不全，缺：{missing}（需同名 .vhdr/.eeg/.vmrk）")
        sys.exit(1)
    return triplet


def _upload(c: ElysClient, *, study_id: str, ds_id: str) -> str:
    """把 data/ 里的 BrainVision 三件套同步导入到指定 asset，返回 recording id。"""
    triplet = _find_brainvision_triplet(DATA_DIR)
    ui.section(f"上传 BrainVision 三件套到 asset {ds_id}")
    ui.info(f"文件：{[p.name for p in triplet]}")
    ui.info(f"subject={lconfig.SUBJECT}  task={lconfig.TASK}")
    task = c.import_recording_async(
        study_id,
        triplet,
        subject=lconfig.SUBJECT,
        task=lconfig.TASK,
        session=lconfig.SESSION,
        run=lconfig.RUN,
        dataset_asset_id=ds_id,
        replace_existing=True,
        show_progress=True,
    )
    if task.get("status") != "succeeded":
        errors = (task.get("error_json") or {}).get("errors") or []
        detail = errors[0].get("message") if errors else task.get("status")
        ui.fail(f"导入任务未成功（{task.get('status')}）：{detail}")
        sys.exit(1)
    result = task.get("result_json") or {}
    rec = result.get("recording") or {}
    ui.ok(f"导入完成（async upload-{result.get('upload_seq')}）")
    ui.info(f"recording_id = {rec.get('id', '')}")
    ui.info(
        f"格式={rec.get('source_format')}  通道数={rec.get('n_channels')}  "
        f"采样率={rec.get('sfreq')}Hz  时长={rec.get('duration_seconds')}s  "
        f"事件数={rec.get('n_events')}"
    )
    return rec.get("id", "")


def _writeback_config(*, study_id: str, ds_id: str, mount_id: str, recording_id: str) -> None:
    """把这次的 ID 自动写回 config_local.py，省得手动复制；测试服重置后重跑会自动刷新。

    只改这几行的「值」，行尾注释和其它配置（REF_CHANNELS / EVENT_LABELS 等）原样保留。
    """
    cfg = HERE / "config_local.py"
    text = cfg.read_text(encoding="utf-8")
    updates = {
        "STUDY_ID": f'"{study_id}"',
        "DATASET_IDS": f'["{recording_id}"]' if recording_id else "[]",
        "DATASET_ID": f'"{ds_id}"',
        "RECORDING_ID": f'"{recording_id}"',
    }
    if mount_id:                       # 复用已有 dataset 时拿不到 mount，就别把原值清掉
        updates["MOUNT_ID"] = f'"{mount_id}"'

    for key, value in updates.items():
        # 匹配 “KEY = 旧值  # 注释”，只换中间的值。\s*=\s* 保证不会误伤 DATASET_IDS↔DATASET_ID
        pattern = re.compile(rf"(?m)^(\s*{key}\s*=\s*)(.*?)(\s*#.*)?$")
        text, n = pattern.subn(lambda m: f"{m.group(1)}{value}{m.group(3) or ''}", text, count=1)
        if n == 0:
            ui.warn(f"config_local.py 里没找到 {key}= 这行，跳过回填")
    cfg.write_text(text, encoding="utf-8")
    ui.ok("已自动回填 config_local.py：STUDY_ID / DATASET_IDS / DATASET_ID / MOUNT_ID / RECORDING_ID")


def _resolve_meta(c: ElysClient, *, study_id: str, recording_id: str) -> None:
    """resolve 一把，打印通道名 / 事件标签，供需要时手改 REF_CHANNELS / EVENT_LABELS。"""
    if not recording_id:
        ui.warn("没拿到 recording_id，跳过 resolve。")
        return
    try:
        res = c.resolve_load_data(study_id, [recording_id])
    except (ElysAPIError, requests.RequestException) as e:
        ui.warn(f"resolve 读元信息失败（不影响上传，跑 pipeline 时再看）：{e}")
        return

    infos = res.get("data_infos") or []
    if not infos:
        ui.warn(f"resolve 没返回 data_infos；errors={res.get('errors')}")
        return

    info = infos[0]
    ch_names = info.get("ch_names") or []
    event_labels = info.get("event_labels") or []
    event_counts = info.get("event_counts") or {}
    ui.section("该 recording 元信息（REF_CHANNELS / EVENT_LABELS 候选，需要时手改 config）")
    ui.info(f"fif_exists={info.get('fif_exists')}  通道数={info.get('n_channels')}  采样率={info.get('sfreq')}Hz")
    ui.info(f"通道名({len(ch_names)})：{ch_names}")
    ui.info(f"事件标签({len(event_labels)})：{event_labels}")
    if event_counts:
        ui.info(f"事件计数：{event_counts}")


if __name__ == "__main__":
    try:
        main()
    except ElysAPIError as e:                  # 后端返回 4xx/5xx：打印响应体看真正原因
        ui.died(f"API 调用失败：{e}")
        sys.exit(1)
    except requests.RequestException as e:     # 连不上：网络 / 地址错 / 服务没起
        ui.died(f"网络或连接失败：{e}")
        ui.info(f"请确认服务已部署且地址可达：BASE_URL = {gconfig.BASE_URL}")
        sys.exit(1)
