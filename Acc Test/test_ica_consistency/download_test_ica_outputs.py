"""Download remote ELYS outputs for the existing "test ICA" pipeline."""

from __future__ import annotations

import json
import os
import re
import sys
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


HERE = Path(__file__).resolve().parent
SERVER_DIR = HERE / "server_outputs"
META_DIR = HERE / "metadata"

PIPELINE_NAME = os.environ.get("TEST_ICA_PIPELINE_NAME", "test ICA")
DEFAULT_RUN_ID = "822cca8b-3f07-45da-b956-289a5886f54c"
RUN_ID = os.environ.get("TEST_ICA_RUN_ID", DEFAULT_RUN_ID).strip()

NODE_KEYS = {
    "n_mr4bc24t_2": "01_resample_250",
    "n_mr4bc2t4_3": "02_notch_50",
    "n_mr4bc3xx_4": "03_bandpass_0p1_40",
    "n_mr4borp0_1": "04_compute_ica",
    "n_mr4boscg_2": "05_apply_ica_clean",
}


def get_json(client: ElysClient, path: str) -> Any:
    client._ensure_login()
    response = client._session.get(f"{client.base_url}{path}", timeout=client.timeout)
    response.raise_for_status()
    return response.json()


def find_pipeline(client: ElysClient) -> dict[str, Any]:
    for pipeline in client.list_pipelines(lconfig.STUDY_ID):
        if pipeline.get("name") == PIPELINE_NAME:
            return pipeline
    raise RuntimeError(f"Pipeline named {PIPELINE_NAME!r} was not found in study {lconfig.STUDY_ID}.")


def latest_completed_execution(client: ElysClient, pipeline_id: int | str) -> dict[str, Any]:
    data = get_json(client, f"/studies/{lconfig.STUDY_ID}/pipelines/{pipeline_id}/executions?status=completed")
    executions = [item for item in data.get("executions", []) if item.get("status") == "completed"]
    if not executions:
        raise RuntimeError(f"No completed executions found for pipeline {pipeline_id}.")
    return sorted(
        executions,
        key=lambda item: (int(item.get("execution_seq") or 0), str(item.get("finished_at") or "")),
        reverse=True,
    )[0]


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


def download_study_output(client: ElysClient, output_id: str, out_path: Path) -> Path:
    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path
    return client.download_derived(lconfig.STUDY_ID, output_id, out_path)


def subject_from_info(item: dict[str, Any]) -> str:
    for key in ("bids_subject_id", "subject", "subject_id"):
        value = item.get(key)
        if value and str(value).startswith("sub-"):
            return str(value)
    text = " ".join(str(item.get(key) or "") for key in ("display_name", "logical_path", "fif_path", "storage_uri"))
    match = re.search(r"sub-\d+", text)
    if match:
        return match.group(0)
    dataset_id = item.get("dataset_id") or item.get("source_dataset_id") or "unknown"
    return str(dataset_id)


def raw_filename(data_info: dict[str, Any]) -> str:
    dataset_file = data_info.get("dataset_file") or data_info.get("file_snapshot") or {}
    logical = str(dataset_file.get("logical_path") or data_info.get("logical_path") or "")
    name = Path(logical).name
    if name.endswith(".fif"):
        return name
    subject = subject_from_info(data_info)
    session = data_info.get("session") or "ses-a"
    task = data_info.get("task") or "task-sensory"
    run = data_info.get("run") or "run-04"
    return f"{subject}_{session}_{task}_{run}_eeg.fif"


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


def category_for_output(output: dict[str, Any]) -> str:
    node_id = str(output.get("produced_by_node_id") or output.get("node_id") or "")
    display_name = str(output.get("display_name") or "")
    data_type = str(output.get("data_type") or "")
    if node_id in NODE_KEYS:
        return NODE_KEYS[node_id]
    if data_type == "ica" or "Compute ICA" in display_name:
        return "04_compute_ica"
    if "Apply ICA" in display_name:
        return "05_apply_ica_clean"
    if "Resample" in display_name:
        return "01_resample_250"
    if "Filter (2)" in display_name:
        return "03_bandpass_0p1_40"
    if "Filter" in display_name:
        return "02_notch_50"
    return "unknown"


def output_filename(output: dict[str, Any], category: str) -> str:
    subject = subject_from_info(output)
    suffix = "-raw.fif"
    label = category
    if category == "04_compute_ica":
        suffix = "-ica.fif"
        label = "compute_ica"
    elif category == "05_apply_ica_clean":
        label = "apply_ica_clean"
    elif category == "01_resample_250":
        label = "resample_250"
    elif category == "02_notch_50":
        label = "notch_50"
    elif category == "03_bandpass_0p1_40":
        label = "bandpass_0p1_40"
    else:
        clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(output.get("display_name") or "output"))
        return f"{subject}_{clean}{suffix}"
    return f"{subject}_{label}{suffix}"


def node_params_by_id(run_detail: dict[str, Any], jobs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    params: dict[str, dict[str, Any]] = {}
    for job in jobs:
        if isinstance(job.get("params_json"), dict):
            params[str(job.get("node_id"))] = job["params_json"]
    graph = (run_detail.get("definition_snapshot") or {}).get("graph") or {}
    for node in graph.get("nodes", []):
        params.setdefault(str(node.get("id")), node.get("params") or {})
    return params


def ica_artifact_subject_map(jobs: list[dict[str, Any]], outputs: list[dict[str, Any]]) -> dict[str, str]:
    artifact_to_subject: dict[str, str] = {}
    for output in outputs:
        if str(output.get("data_type") or "") == "ica" or "Compute ICA" in str(output.get("display_name") or ""):
            artifact_to_subject[str(output.get("id"))] = subject_from_info(output)
    for job in jobs:
        if str(job.get("node_id")) != "n_mr4borp0_1":
            continue
        output_json = job.get("output_json") or {}
        data_infos = (output_json.get("outputs") or {}).get("ica_matrix") or output_json.get("data_infos") or []
        for data_info in data_infos:
            artifact_id = data_info.get("artifact_id")
            if artifact_id:
                artifact_to_subject[str(artifact_id)] = subject_from_info(data_info)
    return artifact_to_subject


def extract_apply_decisions(jobs: list[dict[str, Any]], outputs: list[dict[str, Any]]) -> dict[str, list[int]]:
    artifact_to_subject = ica_artifact_subject_map(jobs, outputs)
    decisions: dict[str, list[int]] = {}
    for job in jobs:
        if str(job.get("node_id")) != "n_mr4boscg_2":
            continue
        output_json = job.get("output_json") or {}
        metadata = output_json.get("metadata") or {}
        decision = metadata.get("decision") or {}
        global_excluded = [int(item) for item in (decision.get("excluded_components") or [])]
        by_dataset = decision.get("excluded_components_by_dataset") or {}
        for key, excluded in by_dataset.items():
            subject = artifact_to_subject.get(str(key), str(key) if str(key).startswith("sub-") else "")
            if subject:
                decisions[subject] = [int(item) for item in (excluded or [])]
        outputs = (output_json.get("outputs") or {}).get("output") or output_json.get("data_infos") or []
        for data_info in outputs:
            subject = subject_from_info(data_info)
            if subject in decisions:
                continue
            processing = data_info.get("processing") or {}
            params = processing.get("params") or {}
            excluded = params.get("excluded_components")
            if excluded is None:
                decision = (params.get("interaction_decision") or {})
                excluded = decision.get("excluded_components")
            if excluded is None:
                excluded = global_excluded
            decisions[subject] = [int(item) for item in (excluded or [])]
    return decisions


def download_raw_inputs(client: ElysClient, jobs: list[dict[str, Any]]) -> dict[str, str]:
    load_job = next((job for job in jobs if job.get("node_type") == "eeg/data/load"), None)
    if load_job is None:
        raise RuntimeError("LoadData job was not found.")
    data_infos = (load_job.get("output_json") or {}).get("data_infos") or []
    if not data_infos:
        data_infos = ((load_job.get("output_json") or {}).get("outputs") or {}).get("output") or []
    paths: dict[str, str] = {}
    for data_info in data_infos:
        subject = subject_from_info(data_info)
        file_id = input_file_id(client, data_info)
        target = SERVER_DIR / "00_raw_inputs" / raw_filename(data_info)
        print(f"Downloading raw input {subject}: {target.name}")
        download_dataset_file(client, file_id, target)
        paths[subject] = str(target)
    return paths


def download_outputs(client: ElysClient, outputs: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    paths: dict[str, dict[str, str]] = {}
    for output in outputs:
        category = category_for_output(output)
        subject = subject_from_info(output)
        filename = output_filename(output, category)
        target = SERVER_DIR / category / filename
        print(f"Downloading output {subject} {category}: {filename}")
        download_study_output(client, str(output["id"]), target)
        paths.setdefault(subject, {})[category] = str(target)
    return paths


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
    pipeline = find_pipeline(client)
    if RUN_ID:
        run_detail = client.get_run(lconfig.STUDY_ID, RUN_ID)
    else:
        latest = latest_completed_execution(client, pipeline["id"])
        run_detail = client.get_run(lconfig.STUDY_ID, str(latest["id"]))
    jobs = client.list_run_nodes(lconfig.STUDY_ID, str(run_detail["id"]))
    outputs = run_detail.get("study_outputs") or client.list_run_derived(lconfig.STUDY_ID, str(run_detail["id"]))

    raw_paths = download_raw_inputs(client, jobs)
    output_paths = download_outputs(client, outputs)

    manifest = {
        "pipeline_name": PIPELINE_NAME,
        "pipeline": pipeline,
        "study_id": lconfig.STUDY_ID,
        "base_url": gconfig.BASE_URL,
        "data_base_url": gconfig.DATA_BASE_URL,
        "run_id": str(run_detail["id"]),
        "run": run_detail,
        "jobs": jobs,
        "outputs": outputs,
        "node_params": node_params_by_id(run_detail, jobs),
        "apply_decisions_by_subject": extract_apply_decisions(jobs, outputs),
        "raw_input_paths": raw_paths,
        "output_paths": output_paths,
    }
    manifest_path = META_DIR / "test_ica_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "pipeline_id": pipeline.get("id"),
                "run_id": run_detail.get("id"),
                "raw_inputs": len(raw_paths),
                "outputs": len(outputs),
                "manifest_path": str(manifest_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
