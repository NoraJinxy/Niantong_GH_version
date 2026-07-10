"""Create/run remaining-node accuracy pipelines and download ELYS outputs.

The pipelines are created through the same public API used by the frontend, so
they are visible and editable in the workflow canvas.  Each pipeline is kept
small and deterministic: one target node per case unless a group-level node
requires a minimal upstream chain.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
COMMON = ROOT / "elys_scripts" / "common"
GROUP_PROJECT = ROOT / "elys_scripts" / "projects" / "04_group"
sys.path.insert(0, str(COMMON))
sys.path.insert(0, str(GROUP_PROJECT))

import config as gconfig  # noqa: E402
import config_local as lconfig  # noqa: E402
from elys_client import ElysAPIError, ElysClient  # noqa: E402


HERE = Path(__file__).resolve().parent
SERVER_DIR = HERE / "server_outputs"
META_DIR = HERE / "metadata"
MANIFEST_PATH = META_DIR / "remaining_nodes_manifest.json"

SUBJECTS = ["sub-007", "sub-008", "sub-009"]
PRIMARY_SUBJECT = "sub-009"
SESSION = "ses-a"
TASK = "task-sensory"
RUN_A = "run-04"
RUN_B = "run-11"

S3_RULE = {"name": "S  3", "pattern": r"S\s*0*3\b", "mode": "regex"}
S4_RULE = {"name": "S  4", "pattern": r"S\s*0*4\b", "mode": "regex"}
S5_RULE = {"name": "S  5", "pattern": r"S\s*0*5\b", "mode": "regex"}


def get_json(client: ElysClient, path: str) -> Any:
    client._ensure_login()
    response = client._session.get(f"{client.base_url}{path}", timeout=client.timeout)
    response.raise_for_status()
    return response.json()


def put_pipeline(client: ElysClient, pipeline_id: int, definition: dict[str, Any], expected_version: int) -> None:
    client._ensure_login()
    response = client._session.put(
        f"{client.base_url}/studies/{lconfig.STUDY_ID}/pipelines/{pipeline_id}",
        json={"definition_json": definition, "expected_version": expected_version},
        timeout=client.timeout,
    )
    response.raise_for_status()


def ensure_pipeline(client: ElysClient, name: str, definition: dict[str, Any]) -> int:
    for pipeline in client.list_pipelines(lconfig.STUDY_ID):
        if pipeline.get("name") == name:
            put_pipeline(client, int(pipeline["id"]), definition, int(pipeline.get("version") or 1))
            return int(pipeline["id"])
    created = client.create_pipeline(lconfig.STUDY_ID, name, definition)
    return int(created["id"])


def trigger_run_with_retry(client: ElysClient, pipeline_id: int) -> dict[str, Any]:
    deadline = time.time() + 1800
    while True:
        try:
            return client.trigger_run(lconfig.STUDY_ID, pipeline_id)
        except ElysAPIError as exc:
            if exc.status_code != 409 or time.time() > deadline:
                raise
            print("Another execution is active; waiting 10s before retrying ...", flush=True)
            time.sleep(10)


def resolve_recordings(
    client: ElysClient,
    *,
    subjects: list[str],
    run: str,
) -> list[dict[str, Any]]:
    resolved = client.resolve_load_data(
        lconfig.STUDY_ID,
        selection_mode="filter",
        dataset_filter={
            "subjects": subjects,
            "sessions": [SESSION],
            "tasks": [TASK],
            "runs": [run],
            "qa_status": "all",
            "require_fif": True,
        },
    )
    infos = resolved.get("data_infos") or []
    found = {str(info.get("subject") or info.get("bids_subject_id") or "") for info in infos}
    if len(infos) != len(subjects):
        raise RuntimeError(f"Expected {len(subjects)} {run} recordings, got {len(infos)}; found={sorted(found)}")
    return infos


def list_recording_files(client: ElysClient, recording_id: str) -> list[dict[str, Any]]:
    data = get_json(client, f"/studies/{lconfig.STUDY_ID}/recordings/{recording_id}/files")
    return data.get("files", [])


def download_dataset_file(client: ElysClient, file_id: str, out_path: Path) -> Path:
    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path
    client._ensure_login()
    response = client._session.get(
        f"{client.data_base_url}/dataset-files/{file_id}/download",
        stream=True,
        timeout=600,
    )
    response.raise_for_status()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as fh:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                fh.write(chunk)
    return out_path


def input_file_id(client: ElysClient, data_info: dict[str, Any]) -> str:
    dataset_file = data_info.get("dataset_file") or data_info.get("file_snapshot") or {}
    file_id = dataset_file.get("id") or dataset_file.get("dataset_file_id") or data_info.get("dataset_file_id")
    if file_id:
        return str(file_id)
    recording_id = str(data_info.get("dataset_id") or "")
    for item in list_recording_files(client, recording_id):
        logical_path = str(item.get("logical_path") or item.get("relative_path") or "")
        if item.get("file_role") == "fif" or logical_path.endswith("_eeg.fif"):
            return str(item["id"])
    raise RuntimeError(f"Cannot find FIF dataset file for input {recording_id}.")


def subject_from_info(info: dict[str, Any]) -> str:
    for key in ("subject", "bids_subject_id", "subject_id"):
        value = info.get(key)
        if value:
            text = str(value)
            return text if text.startswith("sub-") else f"sub-{text}"
    text = " ".join(str(info.get(key) or "") for key in ("display_name", "logical_path", "storage_uri"))
    match = re.search(r"sub-\d+", text)
    return match.group(0) if match else str(info.get("dataset_id") or "unknown")


def raw_filename(data_info: dict[str, Any], run: str) -> str:
    subject = subject_from_info(data_info)
    return f"{subject}_{SESSION}_{TASK}_{run}_eeg.fif"


def download_raw_inputs(
    client: ElysClient,
    data_infos: list[dict[str, Any]],
    *,
    run: str,
) -> dict[str, str]:
    paths: dict[str, str] = {}
    for info in data_infos:
        subject = subject_from_info(info)
        file_id = input_file_id(client, info)
        target = SERVER_DIR / "00_raw_inputs" / raw_filename(info, run)
        print(f"Downloading raw input {subject} {run}: {target.name}", flush=True)
        download_dataset_file(client, file_id, target)
        paths[f"{subject}:{run}"] = str(target)
    return paths


def node(nid: str, ntype: str, title: str, x: int, y: int, params: dict[str, Any]) -> dict[str, Any]:
    return {"id": nid, "type": ntype, "title": title, "position": [x, y], "params": params}


def link(src: str, dst: str, *, src_port: str = "output", dst_port: str = "input") -> dict[str, Any]:
    return {"id": f"{src}-{dst}-{src_port}-{dst_port}", "from": {"node": src, "port": src_port}, "to": {"node": dst, "port": dst_port}}


def load_node(nid: str, dataset_ids: list[str], title: str = "LoadData") -> dict[str, Any]:
    return node(
        nid,
        "eeg/data/load",
        title,
        80,
        80,
        {"selection_mode": "explicit", "dataset_ids": dataset_ids, "dataset_filter": {}},
    )


def single_raw_definition(recording_id: str, target_node: dict[str, Any]) -> dict[str, Any]:
    return {
        "graph": {
            "nodes": [load_node("ld", [recording_id]), target_node],
            "links": [link("ld", target_node["id"])],
        }
    }


def epoch_chain_nodes(prefix: str, conditions: list[dict[str, str]] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    conds = conditions or [S3_RULE]
    ep = node(
        f"{prefix}ep",
        "eeg/epoch/segment",
        f"Epoch {prefix}",
        400,
        80,
        {"conditions": conds, "tmin": -0.2, "tmax": 0.8, "split_by": "none"},
    )
    return [ep], [], ep["id"]


def run_case(client: ElysClient, case: dict[str, Any]) -> dict[str, Any]:
    definition = case["definition"]
    pipeline_id = ensure_pipeline(client, case["pipeline_name"], definition)
    validation = client.validate(lconfig.STUDY_ID, pipeline_id)
    if not validation.get("valid"):
        raise RuntimeError(json.dumps(validation, ensure_ascii=False, indent=2))
    run = trigger_run_with_retry(client, pipeline_id)
    run_id = str(run["id"])
    started = time.time()
    final = client.wait_run(lconfig.STUDY_ID, run_id, poll_sec=3, timeout_sec=2400)
    elapsed_sec = time.time() - started
    if final.get("status") != "completed":
        raise RuntimeError(json.dumps(final, ensure_ascii=False, indent=2))

    outputs = list(final.get("study_outputs") or [])
    if not outputs:
        outputs = client.list_run_derived(lconfig.STUDY_ID, run_id)
    downloaded: list[dict[str, Any]] = []
    for output in outputs:
        if case.get("output_node_types") and output.get("produced_by_node_type") not in set(case["output_node_types"]):
            continue
        if case.get("output_node_ids") and output.get("produced_by_node_id") not in set(case["output_node_ids"]):
            continue
        filename = output_name(output)
        target = SERVER_DIR / case["key"] / filename
        print(f"Downloading {case['key']}: {filename}", flush=True)
        client.download_derived(lconfig.STUDY_ID, output["id"], target)
        item = dict(output)
        item["local_path"] = str(target)
        downloaded.append(item)
    return {
        "key": case["key"],
        "pipeline_name": case["pipeline_name"],
        "pipeline_id": pipeline_id,
        "run_id": run_id,
        "elapsed_sec": elapsed_sec,
        "definition": definition,
        "validation": validation,
        "run": final,
        "outputs": outputs,
        "downloaded": downloaded,
    }


def output_name(output: dict[str, Any]) -> str:
    data_type = str(output.get("data_type") or "output")
    display = str(output.get("display_name") or output.get("id") or "output")
    subject = subject_from_info(output)
    condition = str(output.get("condition") or "")
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", display).strip("_")[:80] or "output"
    suffix = {
        "raw": "-raw.fif",
        "filtered_raw": "-raw.fif",
        "epochs": "-epo.fif",
        "evoked": "-ave.fif",
        "tfr": "-tfr.h5",
        "psd": "-psd.npz",
        "psd_grandavg": "-psd-grandavg.npz",
        "unit_stack": "-unit-stack.npz",
        "stat_map": "-stat-map.npz",
        "ica": "-ica.fif",
    }.get(data_type, ".bin")
    condition_part = re.sub(r"[^A-Za-z0-9_.-]+", "_", condition).strip("_")
    if condition_part:
        clean = f"{clean}_{condition_part}"
    return f"{subject}_{clean}{suffix}"


def build_cases(primary: dict[str, Any], group_a: list[dict[str, Any]], group_b: list[dict[str, Any]]) -> list[dict[str, Any]]:
    primary_id = str(primary["dataset_id"])
    group_a_ids = [str(info["dataset_id"]) for info in group_a]
    group_b_ids = [str(info["dataset_id"]) for info in group_b]

    cases: list[dict[str, Any]] = []

    cases.append({
        "key": "event_remap",
        "pipeline_name": "Acc Test - node event remap",
        "definition": single_raw_definition(
            primary_id,
            node(
                "evt_remap",
                "eeg/preproc/event_remap",
                "Event Remap S3",
                400,
                80,
                {
                    "rules": [
                        {"sources": ["S  3"], "target": "ACC_S3"},
                        {"sources": ["S  4"], "target": ""},
                    ]
                },
            ),
        ),
        "output_node_ids": ["evt_remap"],
    })

    cases.append({
        "key": "event_manager",
        "pipeline_name": "Acc Test - node event manager rules",
        "definition": single_raw_definition(
            primary_id,
            node(
                "evt_mgr",
                "eeg/preproc/event_manager",
                "Event Manager S4",
                400,
                80,
                {
                    "group_operations": [
                        {"op": "rename", "sources": ["S  4"], "target": "ACC_S4"},
                        {"op": "shift", "sources": ["S  5"], "delta_s": 0.01},
                    ],
                    "decision_version": 1,
                },
            ),
        ),
        "output_node_ids": ["evt_mgr"],
    })

    cases.append({
        "key": "artifact_mark",
        "pipeline_name": "Acc Test - node artifact mark",
        "definition": single_raw_definition(
            primary_id,
            node(
                "artifact",
                "eeg/preproc/artifact_mark",
                "Artifact Mark Fixed",
                400,
                80,
                {
                    "bad_segments": [{"onset": 1.0, "duration": 0.25, "source": "acc_test"}],
                    "bad_channels": ["Fp1"],
                    "channel_action": "mark",
                    "decision_version": 1,
                },
            ),
        ),
        "output_node_ids": ["artifact"],
    })

    cases.append({
        "key": "epoch_reject",
        "pipeline_name": "Acc Test - node epoch reject threshold",
        "definition": {
            "graph": {
                "nodes": [
                    load_node("ld", [primary_id]),
                    node("ep", "eeg/epoch/segment", "Epoch S3", 400, 80, {"conditions": [S3_RULE], "tmin": -0.2, "tmax": 0.8, "split_by": "none"}),
                    node("rej", "eeg/epoch/reject", "Reject Trials High Threshold", 720, 80, {"method": "threshold", "reject_peak_to_peak": 100000, "flat": ""}),
                ],
                "links": [link("ld", "ep"), link("ep", "rej")],
            }
        },
        "output_node_ids": ["ep", "rej"],
    })

    cases.append({
        "key": "epoch_merge",
        "pipeline_name": "Acc Test - node epoch merge source recording",
        "definition": {
            "graph": {
                "nodes": [
                    load_node("ld", [primary_id]),
                    node("ep", "eeg/epoch/segment", "Epoch S3 S4 split", 400, 80, {"conditions": [S3_RULE, S4_RULE], "tmin": -0.2, "tmax": 0.8, "split_by": "condition"}),
                    node("merge", "eeg/epoch/merge", "Epoch Merge source", 720, 80, {"merge_scope": "source_recording"}),
                ],
                "links": [link("ld", "ep"), link("ep", "merge")],
            }
        },
        "output_node_ids": ["ep", "merge"],
    })

    cases.append({
        "key": "psd",
        "pipeline_name": "Acc Test - node PSD epochs",
        "definition": {
            "graph": {
                "nodes": [
                    load_node("ld", [primary_id]),
                    node("ep", "eeg/epoch/segment", "Epoch S3", 400, 80, {"conditions": [S3_RULE], "tmin": -0.2, "tmax": 0.8, "split_by": "none"}),
                    node("psd", "eeg/analysis/psd", "PSD S3", 720, 80, {"condition": ["S  3"], "fmin": 1, "fmax": 40, "method": "welch", "window_seconds": "", "overlap": 0.5}),
                ],
                "links": [link("ld", "ep"), link("ep", "psd")],
            }
        },
        "output_node_ids": ["psd"],
    })

    cases.append({
        "key": "tfr",
        "pipeline_name": "Acc Test - node TFR morlet",
        "definition": {
            "graph": {
                "nodes": [
                    load_node("ld", [primary_id]),
                    node("ep", "eeg/epoch/segment", "Epoch S3 TFR", 400, 80, {"conditions": [S3_RULE], "tmin": -0.5, "tmax": 1.0, "split_by": "none"}),
                    node("tfr", "eeg/analysis/tfr", "TFR S3", 720, 80, {"condition": ["S  3"], "fmin": 4, "fmax": 20, "n_freqs": 8, "freq_scale": "linear", "n_cycles_mode": "factor", "n_cycles_factor": 0.5, "decim": 4, "baseline_mode": "logratio", "baseline_tmin": "", "baseline_tmax": 0}),
                ],
                "links": [link("ld", "ep"), link("ep", "tfr")],
            }
        },
        "output_node_ids": ["tfr"],
    })

    cases.append({
        "key": "iclabel",
        "pipeline_name": "Acc Test - node ICLabel mark",
        "definition": {
            "graph": {
                "nodes": [
                    load_node("ld", [primary_id]),
                    node("chloc", "eeg/preproc/channel_location", "Ch Loc Assign", 400, 80, {"montage": "auto", "rename": True, "on_missing": "ignore"}),
                    node("ica", "eeg/ica/compute", "Compute ICA 10", 720, 80, {"n_components": 10, "method": "picard", "decim": "auto", "fit_highpass": 1.0, "random_state": 42}),
                    node("iclabel", "eeg/ica/iclabel", "ICLabel Mark", 1040, 80, {"action": "mark", "prob_threshold": 0.8, "remove_eye": True, "remove_muscle": True, "remove_heart": True, "remove_line_noise": True, "remove_channel_noise": True}),
                ],
                "links": [
                    link("ld", "chloc"),
                    link("chloc", "ica"),
                    link("chloc", "iclabel", dst_port="input"),
                    link("ica", "iclabel", src_port="ica_matrix", dst_port="ica_matrix"),
                ],
            }
        },
        "output_node_ids": ["ica", "iclabel"],
    })

    cases.append({
        "key": "group_average",
        "pipeline_name": "Acc Test - node group merge average",
        "definition": {
            "graph": {
                "nodes": [
                    load_node("ld", group_a_ids, "LoadData group A"),
                    node("ep", "eeg/epoch/segment", "Epoch S3", 400, 80, {"conditions": [S3_RULE], "tmin": -0.2, "tmax": 0.8, "split_by": "none"}),
                    node("erp", "eeg/analysis/erp", "ERP S3", 720, 80, {"condition": ["S  3"]}),
                    node("gm", "eeg/group/merge", "Group Merge", 1040, 80, {"group_label": "A"}),
                    node("ga", "eeg/group/average", "Grand Average", 1360, 80, {"weighted": False}),
                ],
                "links": [link("ld", "ep"), link("ep", "erp"), link("erp", "gm"), link("gm", "ga")],
            }
        },
        "output_node_ids": ["erp", "gm", "ga"],
    })

    cases.append({
        "key": "group_compare",
        "pipeline_name": "Acc Test - node group compare paired",
        "definition": {
            "graph": {
                "nodes": [
                    load_node("ld_a", group_a_ids, "LoadData A"),
                    load_node("ld_b", group_b_ids, "LoadData B"),
                    node("ep_a", "eeg/epoch/segment", "Epoch A S3", 400, 40, {"conditions": [S3_RULE], "tmin": -0.2, "tmax": 0.8, "split_by": "none"}),
                    node("ep_b", "eeg/epoch/segment", "Epoch B S3", 400, 250, {"conditions": [S3_RULE], "tmin": -0.2, "tmax": 0.8, "split_by": "none"}),
                    node("erp_a", "eeg/analysis/erp", "ERP A S3", 720, 40, {"condition": ["S  3"]}),
                    node("erp_b", "eeg/analysis/erp", "ERP B S3", 720, 250, {"condition": ["S  3"]}),
                    node("gm_a", "eeg/group/merge", "Group Merge A", 1040, 40, {"group_label": "A"}),
                    node("gm_b", "eeg/group/merge", "Group Merge B", 1040, 250, {"group_label": "B"}),
                    node("cmp", "eeg/group/compare", "Group Compare", 1360, 145, {"design": "paired", "method": "pointwise", "correction": "none", "tail": "two-sided", "alpha": 0.05, "condition": "S  3", "label_a": "run04", "label_b": "run11"}),
                ],
                "links": [
                    link("ld_a", "ep_a"), link("ld_b", "ep_b"),
                    link("ep_a", "erp_a"), link("ep_b", "erp_b"),
                    link("erp_a", "gm_a"), link("erp_b", "gm_b"),
                    link("gm_a", "cmp", dst_port="a"), link("gm_b", "cmp", dst_port="b"),
                ],
            }
        },
        "output_node_ids": ["gm", "gm_a", "gm_b", "cmp"],
    })

    return cases


def main() -> None:
    SERVER_DIR.mkdir(parents=True, exist_ok=True)
    META_DIR.mkdir(parents=True, exist_ok=True)

    client = ElysClient(
        gconfig.BASE_URL,
        gconfig.USERNAME,
        gconfig.PASSWORD,
        data_base_url=gconfig.DATA_BASE_URL,
        timeout=90,
    )
    client.login()

    primary_list = resolve_recordings(client, subjects=[PRIMARY_SUBJECT], run=RUN_A)
    group_a = resolve_recordings(client, subjects=SUBJECTS, run=RUN_A)
    group_b = resolve_recordings(client, subjects=SUBJECTS, run=RUN_B)
    raw_paths = {}
    raw_paths.update(download_raw_inputs(client, primary_list, run=RUN_A))
    raw_paths.update(download_raw_inputs(client, group_a, run=RUN_A))
    raw_paths.update(download_raw_inputs(client, group_b, run=RUN_B))

    cases = build_cases(primary_list[0], group_a, group_b)
    results: dict[str, Any] = {}
    for case in cases:
        print(f"Running case {case['key']} ...", flush=True)
        results[case["key"]] = run_case(client, case)

    manifest = {
        "study_id": lconfig.STUDY_ID,
        "base_url": gconfig.BASE_URL,
        "data_base_url": gconfig.DATA_BASE_URL,
        "subjects": SUBJECTS,
        "primary_subject": PRIMARY_SUBJECT,
        "run_a": RUN_A,
        "run_b": RUN_B,
        "raw_paths": raw_paths,
        "recordings": {
            "primary": primary_list,
            "group_a": group_a,
            "group_b": group_b,
        },
        "cases": results,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"manifest_path": str(MANIFEST_PATH), "cases": list(results)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
