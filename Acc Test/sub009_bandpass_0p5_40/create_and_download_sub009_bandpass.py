"""Create/run a minimal ELYS LoadData -> Filter pipeline and download outputs.

This script uses the same REST client/config style as elys_scripts/projects/04_group.
It is intentionally narrow: one recording, one FIR bandpass filter, one downloaded
server result for local MNE comparison.
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
from elys_client import ElysClient  # noqa: E402


PIPELINE_NAME = "Acc Test - sub-009 bandpass 0.5-40"
SUBJECT = "sub-009"
SESSION = "ses-a"
TASK = "task-sensory"
RUN = "run-04"
RAW_FILENAME = "sub-009_ses-a_task-sensory_run-04_eeg.fif"
OUT_DIR = Path(__file__).resolve().parent
SERVER_DIR = OUT_DIR / "server_outputs"
META_DIR = OUT_DIR / "metadata"


def build_definition(recording_id: str) -> dict[str, Any]:
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
                    "id": "flt",
                    "type": "eeg/filter/apply",
                    "title": "Filter 0.5-40Hz",
                    "position": [400, 80],
                    "params": {
                        "filter_type": "bandpass",
                        "l_freq": 0.5,
                        "h_freq": 40.0,
                        "method": "fir",
                        "phase": "zero",
                        "trans_bandwidth": "",
                        "keep": True,
                        "display_name_template": "sub-009_ses-a_task-sensory_run-04_Filter_0p5_40Hz",
                    },
                },
            ],
            "links": [
                {
                    "id": "ld-flt",
                    "from": {"node": "ld", "port": "output"},
                    "to": {"node": "flt", "port": "input"},
                }
            ],
        }
    }


def ensure_pipeline(client: ElysClient, definition: dict[str, Any]) -> int:
    for pipeline in client.list_pipelines(lconfig.STUDY_ID):
        if pipeline.get("name") == PIPELINE_NAME:
            client.update_pipeline(lconfig.STUDY_ID, pipeline["id"], definition=definition)
            return int(pipeline["id"])
    created = client.create_pipeline(lconfig.STUDY_ID, PIPELINE_NAME, definition)
    return int(created["id"])


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
    download_dataset_file(client, str(fif_files[0]["id"]), target)
    return target


def pick_filter_output(outputs: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [item for item in outputs if item.get("data_type") == "filtered_raw"]
    if not candidates:
        candidates = [item for item in outputs if "Filter_0p5_40Hz" in str(item.get("display_name") or "")]
    if not candidates:
        raise RuntimeError(f"No filtered_raw output found. Outputs: {json.dumps(outputs, ensure_ascii=False)}")
    return candidates[0]


def download_filter_output(client: ElysClient, output: dict[str, Any]) -> Path:
    filename = "sub-009_ses-a_task-sensory_run-04_Filter_0p5_40Hz-raw.fif"
    target = SERVER_DIR / filename
    client.download_derived(lconfig.STUDY_ID, output["id"], target)
    return target


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

    definition = build_definition(recording_id)
    pipeline_id = ensure_pipeline(client, definition)
    validation = client.validate(lconfig.STUDY_ID, pipeline_id)
    if not validation.get("valid"):
        raise RuntimeError(json.dumps(validation, ensure_ascii=False, indent=2))

    run = client.trigger_run(lconfig.STUDY_ID, pipeline_id)
    run_id = str(run["id"])
    started = time.time()
    final = client.wait_run(lconfig.STUDY_ID, run_id, poll_sec=3, timeout_sec=1800)
    elapsed_sec = time.time() - started
    if final.get("status") != "completed":
        raise RuntimeError(json.dumps(final, ensure_ascii=False, indent=2))

    outputs = client.list_run_derived(lconfig.STUDY_ID, run_id)
    filter_output = pick_filter_output(outputs)
    raw_path = download_raw_fif(client, recording_id)
    filtered_path = download_filter_output(client, filter_output)

    manifest = {
        "pipeline_name": PIPELINE_NAME,
        "pipeline_id": pipeline_id,
        "run_id": run_id,
        "study_id": lconfig.STUDY_ID,
        "base_url": gconfig.BASE_URL,
        "data_base_url": gconfig.DATA_BASE_URL,
        "elapsed_sec": elapsed_sec,
        "recording": recording,
        "definition": definition,
        "validation": validation,
        "run": final,
        "outputs": outputs,
        "selected_filter_output": filter_output,
        "raw_path": str(raw_path),
        "filtered_path": str(filtered_path),
    }
    manifest_path = META_DIR / "pipeline_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "pipeline_id": pipeline_id,
        "run_id": run_id,
        "raw_path": str(raw_path),
        "filtered_path": str(filtered_path),
        "manifest_path": str(manifest_path),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
