"""03_resting_state / diag —— 临时诊断：为什么 LoadData filter 模式查不到 recording。

直连线上：列出 study 下全部 recording 的关键字段，再用 filter 模式 resolve 一次，
把 resolved_filter / dataset_count / errors / warnings 全打出来，定位过滤为空的根因。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "common"))

from elys_client import ElysClient, _raise_for_status  # noqa: E402
import config as gconfig                                 # noqa: E402
import config_local as lconfig                           # noqa: E402


def main():
    c = ElysClient(gconfig.BASE_URL, gconfig.USERNAME, gconfig.PASSWORD, data_base_url=gconfig.DATA_BASE_URL)
    c.login()
    sid = lconfig.STUDY_ID
    print(f"== STUDY_ID={sid} ==")

    # 1) 列 recordings
    r = c._session.get(f"{c.base_url}/studies/{sid}/recordings", timeout=c.timeout)
    _raise_for_status(r)
    recs = r.json().get("recordings", [])
    print(f"\n== recordings: {len(recs)} 条 ==")
    by_task: dict[str, int] = {}
    for rec in recs:
        subj = (rec.get("subject") or {}).get("bids_subject_id") or rec.get("subject_id")
        task = rec.get("task")
        by_task[str(task)] = by_task.get(str(task), 0) + 1
        # 只打前 6 条明细，避免刷屏
        if recs.index(rec) < 6:
            print(f"  id={rec.get('id')[:8]}  subject={subj}  task={task!r}  "
                  f"session={rec.get('session')!r}  qa={rec.get('qa_status')!r}  "
                  f"asset={str(rec.get('dataset_asset_id'))[:8]}  fif={bool(rec.get('fif_path'))}")
    print(f"\n  task 分布: {by_task}")
    asset_ids = {str(rec.get("dataset_asset_id")) for rec in recs}
    print(f"  recordings 落在的 dataset_asset_id: {asset_ids}")
    print(f"  config DATASET_ID = {lconfig.DATASET_ID}")

    # 2) filter 模式 resolve（tasks=["eo"]）
    for task in ("eo", "ec"):
        print(f"\n== filter resolve tasks=[{task!r}] ==")
        body = {
            "selection_mode": "filter",
            "dataset_ids": [],
            "dataset_filter": {
                "subjects": "all",
                "sessions": "all",
                "tasks": [task],
                "runs": "all",
                "qa_status": "all",
                "require_fif": True,
            },
        }
        rr = c._session.post(
            f"{c.base_url}/studies/{sid}/pipeline/load-data/resolve",
            json=body, timeout=c.timeout,
        )
        _raise_for_status(rr)
        data = rr.json()
        print(f"  valid={data.get('valid')}  dataset_count={data.get('dataset_count')}")
        print(f"  resolved_filter={json.dumps(data.get('resolved_filter'), ensure_ascii=False)}")
        print(f"  errors={json.dumps(data.get('errors'), ensure_ascii=False)[:400]}")
        print(f"  warnings={json.dumps(data.get('warnings'), ensure_ascii=False)[:400]}")


if __name__ == "__main__":
    main()
