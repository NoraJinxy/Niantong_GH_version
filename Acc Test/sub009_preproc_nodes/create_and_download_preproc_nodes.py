"""Create/run minimal ELYS LoadData -> node pipelines for preprocessing nodes.

Targets:
- Resample to 500 Hz
- Notch filter at 50 Hz, with other filter parameters left at node defaults
- Re-reference to TP9/TP10
- Channel-location assignment with node defaults
- Bad-channel processing with node defaults
"""

from __future__ import annotations

import json
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


SUBJECT = "sub-009"
SESSION = "ses-a"
TASK = "task-sensory"
RUN = "run-04"
RAW_FILENAME = "sub-009_ses-a_task-sensory_run-04_eeg.fif"

HERE = Path(__file__).resolve().parent
SERVER_DIR = HERE / "server_outputs"
META_DIR = HERE / "metadata"


NODE_CASES: list[dict[str, Any]] = [
    {
        "key": "resample_500",
        "pipeline_name": "Acc Test - sub-009 resample 500Hz",
        "node_type": "eeg/preproc/resample",
        "node_title": "Resample 500Hz",
        "params": {"sfreq": 500},
        "output_filename": "sub-009_ses-a_task-sensory_run-04_resample_500Hz-raw.fif",
    },
    {
        "key": "notch_50",
        "pipeline_name": "Acc Test - sub-009 notch 50Hz",
        "node_type": "eeg/filter/apply",
        "node_title": "Filter Notch 50Hz",
        "params": {"filter_type": "notch", "notch_freq": 50.0},
        "output_filename": "sub-009_ses-a_task-sensory_run-04_notch_50Hz-raw.fif",
    },
    {
        "key": "reref_tp9_tp10",
        "pipeline_name": "Acc Test - sub-009 reref TP9 TP10",
        "node_type": "eeg/preproc/rereference",
        "node_title": "Re-reference TP9 TP10",
        "params": {"ref_channels": ["TP9", "TP10"]},
        "output_filename": "sub-009_ses-a_task-sensory_run-04_reref_TP9_TP10-raw.fif",
    },
    {
        "key": "channel_location",
        "pipeline_name": "Acc Test - sub-009 channel location default",
        "node_type": "eeg/preproc/channel_location",
        "node_title": "Ch Loc Assign Default",
        "params": {"montage": "auto", "rename": True, "on_missing": "ignore"},
        "output_filename": "sub-009_ses-a_task-sensory_run-04_chloc_default-raw.fif",
    },
    {
        "key": "bad_channels",
        "pipeline_name": "Acc Test - sub-009 bad channels default",
        "node_type": "eeg/preproc/bad_channels",
        "node_title": "Bad Channels Default",
        "params": {
            "action": "interpolate",
            "method": "lof",
            "threshold": 1.5,
            "n_neighbors": 20,
            "corr_thresh": 0.75,
            "reset_bads": True,
        },
        "output_filename": "sub-009_ses-a_task-sensory_run-04_bad_channels_default-raw.fif",
    },
]


def resolve_recording(client: ElysClient) -> dict[str, Any]:
    resolved = client.resolve_load_data(
        lconfig.STUDY_ID,
        selection_mode="filter",
        dataset_filter={
            "subjects": [SUBJECT],
            "sessions": [SESSION],
            "tasks": [TASK],
            "runs": [RUN],
            "qa_status": "all",
            "require_fif": True,
        },
    )
    infos = resolved.get("data_infos") or []
    if len(infos) != 1:
        raise RuntimeError(f"Expected exactly one recording for {RAW_FILENAME}, got {len(infos)}")
    return infos[0]


def build_definition(recording_id: str, case: dict[str, Any]) -> dict[str, Any]:
    node_params = {
        **case["params"],
        "keep": True,
        "display_name_template": case["output_filename"].replace("-raw.fif", ""),
    }
    return {
        "graph": {
            "nodes": [
                {
                    "id": "ld",
                    "type": "eeg/data/load",
                    "title": "LoadData",
                    "position": [80, 80],
                    "params": {
                        "selection_mode": "explicit",
                        "dataset_ids": [recording_id],
                        "dataset_filter": {},
                    },
                },
                {
                    "id": "node",
                    "type": case["node_type"],
                    "title": case["node_title"],
                    "position": [400, 80],
                    "params": node_params,
                },
            ],
            "links": [
                {
                    "id": "ld-node",
                    "from": {"node": "ld", "port": "output"},
                    "to": {"node": "node", "port": "input"},
                }
            ],
        }
    }


def ensure_pipeline(client: ElysClient, name: str, definition: dict[str, Any]) -> int:
    for pipeline in client.list_pipelines(lconfig.STUDY_ID):
        if pipeline.get("name") == name:
            # Newer server builds require optimistic locking on update.
            client._ensure_login()
            response = client._session.put(
                f"{client.base_url}/studies/{lconfig.STUDY_ID}/pipelines/{pipeline['id']}",
                json={
                    "definition_json": definition,
                    "expected_version": pipeline.get("version", 1),
                },
                timeout=client.timeout,
            )
            response.raise_for_status()
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


def list_recording_files(client: ElysClient, recording_id: str) -> list[dict[str, Any]]:
    client._ensure_login()
    response = client._session.get(
        f"{client.base_url}/studies/{lconfig.STUDY_ID}/recordings/{recording_id}/files",
        timeout=client.timeout,
    )
    response.raise_for_status()
    return response.json().get("files", [])


def download_dataset_file(client: ElysClient, file_id: str, out_path: Path) -> Path:
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


def download_raw_fif(client: ElysClient, recording_id: str) -> Path:
    files = list_recording_files(client, recording_id)
    fif_files = [
        item
        for item in files
        if item.get("file_role") == "fif" or str(item.get("logical_path") or "").endswith("_eeg.fif")
    ]
    if not fif_files:
        raise RuntimeError(f"No FIF dataset file found for recording {recording_id}")
    target = SERVER_DIR / RAW_FILENAME
    if not target.exists():
        download_dataset_file(client, str(fif_files[0]["id"]), target)
    return target


def pick_case_output(outputs: list[dict[str, Any]], case: dict[str, Any]) -> dict[str, Any]:
    expected_name = case["output_filename"].replace("-raw.fif", "")
    candidates = [item for item in outputs if str(item.get("display_name") or "").startswith(expected_name)]
    if not candidates:
        candidates = [item for item in outputs if item.get("data_type") in {"raw", "filtered_raw"}]
    if not candidates:
        raise RuntimeError(f"No output found for {case['key']}: {json.dumps(outputs, ensure_ascii=False)}")
    return candidates[0]


def run_case(client: ElysClient, recording_id: str, case: dict[str, Any]) -> dict[str, Any]:
    definition = build_definition(recording_id, case)
    pipeline_id = ensure_pipeline(client, case["pipeline_name"], definition)
    validation = client.validate(lconfig.STUDY_ID, pipeline_id)
    if not validation.get("valid"):
        raise RuntimeError(json.dumps(validation, ensure_ascii=False, indent=2))

    run = trigger_run_with_retry(client, pipeline_id)
    run_id = str(run["id"])
    started = time.time()
    final = client.wait_run(lconfig.STUDY_ID, run_id, poll_sec=3, timeout_sec=1800)
    elapsed_sec = time.time() - started
    if final.get("status") != "completed":
        raise RuntimeError(json.dumps(final, ensure_ascii=False, indent=2))

    outputs = client.list_run_derived(lconfig.STUDY_ID, run_id)
    selected_output = pick_case_output(outputs, case)
    output_path = SERVER_DIR / case["output_filename"]
    client.download_derived(lconfig.STUDY_ID, selected_output["id"], output_path)
    return {
        "case": case,
        "pipeline_id": pipeline_id,
        "run_id": run_id,
        "elapsed_sec": elapsed_sec,
        "definition": definition,
        "validation": validation,
        "run": final,
        "outputs": outputs,
        "selected_output": selected_output,
        "output_path": str(output_path),
    }


def main() -> None:
    SERVER_DIR.mkdir(parents=True, exist_ok=True)
    META_DIR.mkdir(parents=True, exist_ok=True)

    client = ElysClient(
        gconfig.BASE_URL,
        gconfig.USERNAME,
        gconfig.PASSWORD,
        data_base_url=gconfig.DATA_BASE_URL,
    )
    client.login()
    recording = resolve_recording(client)
    recording_id = str(recording["dataset_id"])
    raw_path = download_raw_fif(client, recording_id)

    results: dict[str, Any] = {}
    for case in NODE_CASES:
        print(f"Running {case['key']} ...", flush=True)
        results[case["key"]] = run_case(client, recording_id, case)

    manifest = {
        "study_id": lconfig.STUDY_ID,
        "base_url": gconfig.BASE_URL,
        "data_base_url": gconfig.DATA_BASE_URL,
        "recording": recording,
        "raw_path": str(raw_path),
        "cases": results,
    }
    manifest_path = META_DIR / "pipeline_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"manifest_path": str(manifest_path), "raw_path": str(raw_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
