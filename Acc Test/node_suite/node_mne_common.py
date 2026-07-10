"""Local MNE references for the ELYS remaining-node accuracy suite."""

from __future__ import annotations

import json
import math
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import mne
import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SERVER_DIR = HERE / "server_outputs"
META_DIR = HERE / "metadata"
REPORT_DIR = HERE / "reports"
MANIFEST_PATH = META_DIR / "remaining_nodes_manifest.json"
METRICS_PATH = META_DIR / "remaining_nodes_metrics.json"
SUMMARY_PATH = HERE / "NODE_TEST_SUMMARY.md"

PRIMARY_SUBJECT = "sub-009"
RUN_A = "run-04"
RUN_B = "run-11"
SUBJECTS = ["sub-007", "sub-008", "sub-009"]

_DIGITS = re.compile(r"\d+")
_HIERARCHY_SEPARATOR = re.compile(r"\s+/\s+")
_MNE_PREFIXES = ("Stimulus/", "Response/", "Optic/", "Comment/")

S3_RULE = {"name": "S  3", "pattern": r"S\s*0*3\b", "mode": "regex"}
S4_RULE = {"name": "S  4", "pattern": r"S\s*0*4\b", "mode": "regex"}


@dataclass(frozen=True)
class ConditionRule:
    name: str
    pattern: str
    mode: str = "contains"

    def matches(self, description: Any) -> bool:
        text = normalize_marker_label(description)
        pattern = normalize_marker_label(self.pattern)
        if self.mode == "exact":
            return text == pattern
        if self.mode == "template":
            return _DIGITS.sub("#", text) == _DIGITS.sub("#", pattern)
        if self.mode == "regex":
            try:
                return re.search(pattern, text) is not None
            except re.error:
                return False
        return pattern in text


def normalize_marker_label(label: Any) -> str:
    text = str(label or "").strip()
    if not text:
        return ""
    if text.upper().startswith("BAD_"):
        return text
    parts = _HIERARCHY_SEPARATOR.split(text)
    return " / ".join(part for part in (_normalize_marker_segment(p) for p in parts) if part)


def _normalize_marker_segment(segment: Any) -> str:
    text = str(segment or "").strip()
    if not text or text.upper().startswith("BAD_"):
        return text
    for prefix in _MNE_PREFIXES:
        if text.startswith(prefix):
            rest = text[len(prefix):].strip()
            if rest:
                return rest
    return text


def classify_descriptions(descriptions: list[Any]) -> list[str]:
    texts = [normalize_marker_label(item) for item in descriptions]
    unique = set(texts)
    templates = {_DIGITS.sub("#", item) for item in unique}
    looks_instance_laden = len(unique) > 64 and (len(unique) >= max(8, 3 * len(templates)) or len(unique) >= 0.8 * max(1, len(texts)))
    if not looks_instance_laden:
        return texts
    return [_DIGITS.sub("#", item).replace("#", "*") for item in texts]


def rules_from_params(raw_conditions: Any) -> list[ConditionRule]:
    if not raw_conditions:
        return []
    items = list(raw_conditions) if isinstance(raw_conditions, (list, tuple)) else [raw_conditions]
    rules: list[ConditionRule] = []
    for item in items:
        if isinstance(item, dict):
            name = normalize_marker_label(item.get("name") or item.get("pattern") or "")
            pattern = normalize_marker_label(item.get("pattern") or item.get("name") or "")
            mode = str(item.get("mode") or "exact").strip().lower()
        else:
            name = normalize_marker_label(item)
            pattern = name
            mode = "exact"
        if name and pattern:
            rules.append(ConditionRule(name=name, pattern=pattern, mode=mode))
    return rules


def match_conditions(samples: list[int], descriptions: list[str], rules: list[ConditionRule]) -> tuple[np.ndarray, dict[str, int], dict[str, Any]]:
    name_order: list[str] = []
    for rule in rules:
        if rule.name not in name_order:
            name_order.append(rule.name)
    code_of = {name: idx + 1 for idx, name in enumerate(name_order)}
    rows: list[list[int]] = []
    counts = {name: 0 for name in name_order}
    unmatched = 0
    ambiguous = 0
    for sample, desc in zip(samples, descriptions):
        hit: str | None = None
        n_hits = 0
        for rule in rules:
            if rule.matches(desc):
                n_hits += 1
                if hit is None:
                    hit = rule.name
        if hit is None:
            unmatched += 1
            continue
        ambiguous += int(n_hits > 1)
        counts[hit] += 1
        rows.append([int(sample), 0, int(code_of[hit])])
    event_id = {name: code for name, code in code_of.items() if counts[name] > 0}
    return np.asarray(sorted(rows), dtype=int), event_id, {"counts": counts, "unmatched": unmatched, "ambiguous": ambiguous}


def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"Missing manifest: {MANIFEST_PATH}. Run create_and_download_remaining_nodes.py first.")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def raw_path(manifest: dict[str, Any], subject: str = PRIMARY_SUBJECT, run: str = RUN_A) -> Path:
    path = manifest.get("raw_paths", {}).get(f"{subject}:{run}")
    if not path:
        raise KeyError(f"raw_paths missing {subject}:{run}")
    return Path(path)


def case_downloads(manifest: dict[str, Any], case_key: str) -> list[dict[str, Any]]:
    return list(manifest.get("cases", {}).get(case_key, {}).get("downloaded") or [])


def find_download(
    manifest: dict[str, Any],
    case_key: str,
    *,
    node_id: str | None = None,
    data_type: str | None = None,
    contains: str | None = None,
) -> dict[str, Any]:
    matches = []
    for item in case_downloads(manifest, case_key):
        if node_id and item.get("produced_by_node_id") != node_id:
            continue
        if data_type and item.get("data_type") != data_type:
            continue
        if contains and contains not in str(item.get("local_path") or item.get("display_name") or ""):
            continue
        matches.append(item)
    if not matches:
        raise FileNotFoundError(f"No downloaded output for case={case_key}, node={node_id}, data_type={data_type}, contains={contains}")
    return matches[0]


def node_params(manifest: dict[str, Any], case_key: str, node_id: str) -> dict[str, Any]:
    nodes = manifest.get("cases", {}).get(case_key, {}).get("definition", {}).get("graph", {}).get("nodes", [])
    for node in nodes:
        if node.get("id") == node_id:
            return dict(node.get("params") or {})
    return {}


def read_raw(path: str | Path) -> mne.io.BaseRaw:
    return mne.io.read_raw_fif(path, preload=True, verbose="ERROR")


def read_epochs(path: str | Path) -> mne.Epochs:
    return mne.read_epochs(path, preload=True, verbose="ERROR")


def read_evoked(path: str | Path) -> mne.Evoked:
    return mne.read_evokeds(path, verbose="ERROR")[0]


def read_tfr(path: str | Path) -> Any:
    tfrs = mne.time_frequency.read_tfrs(path)
    return tfrs[0] if isinstance(tfrs, list) else tfrs


def load_psd(path: str | Path) -> dict[str, Any]:
    with np.load(path, allow_pickle=False) as data:
        return {
            "freqs": np.asarray(data["freqs"], dtype=float),
            "psds": np.asarray(data["psds"], dtype=float),
            "ch_names": [str(ch) for ch in data["ch_names"]],
            "sfreq": float(data["sfreq"]),
        }


def load_unit_stack(path: str | Path) -> dict[str, Any]:
    with np.load(path, allow_pickle=False) as data:
        times = np.asarray(data["times"], dtype=float)
        freqs = np.asarray(data["freqs"], dtype=float)
        return {
            "data": np.asarray(data["data"], dtype=float),
            "base_type": str(data["base_type"]),
            "ch_names": [str(ch) for ch in data["ch_names"]],
            "ch_types": [str(ch) for ch in data["ch_types"]],
            "times": times if times.size else None,
            "freqs": freqs if freqs.size else None,
            "sfreq": float(data["sfreq"]),
            "unit_labels": [str(v) for v in data["unit_labels"]],
            "unit_subjects": [str(v) for v in data["unit_subjects"]],
            "unit_conditions": [normalize_marker_label(v) for v in data["unit_conditions"]],
            "unit_n": np.asarray(data["unit_n"], dtype=float),
            "condition": normalize_marker_label(str(data["condition"])),
            "label": normalize_marker_label(str(data["label"])),
        }


def load_stat_map(path: str | Path) -> dict[str, Any]:
    with np.load(path, allow_pickle=False) as data:
        times = np.asarray(data["times"], dtype=float)
        freqs = np.asarray(data["freqs"], dtype=float)
        return {
            "base_type": str(data["base_type"]),
            "ch_names": [str(ch) for ch in data["ch_names"]],
            "times": times if times.size else None,
            "freqs": freqs if freqs.size else None,
            "tmap": np.asarray(data["tmap"], dtype=float),
            "pmap": np.asarray(data["pmap"], dtype=float),
            "sig": np.asarray(data["sig"]).astype(bool),
            "mean_a": np.asarray(data["mean_a"], dtype=float),
            "mean_b": np.asarray(data["mean_b"], dtype=float),
            "condition": normalize_marker_label(str(data["condition"])),
            "design": str(data["design"]),
            "method": str(data["method"]),
            "correction": str(data["correction"]),
            "n_a": int(data["n_a"]),
            "n_b": int(data["n_b"]),
        }


def epoch_raw(raw: mne.io.BaseRaw, conditions: list[dict[str, Any]], tmin: float, tmax: float) -> mne.Epochs:
    events_arr, desc_to_code = mne.events_from_annotations(raw, regexp=None, verbose="ERROR")
    code_to_desc = {int(code): str(desc) for desc, code in desc_to_code.items()}
    samples = [int(row[0]) for row in events_arr]
    descriptions = [code_to_desc.get(int(row[2]), "") for row in events_arr]
    events, event_id, _report = match_conditions(samples, descriptions, rules_from_params(conditions))
    if events.size == 0 or not event_id:
        raise RuntimeError(f"No events matched conditions: {conditions}")
    return mne.Epochs(raw, events, event_id=event_id, tmin=tmin, tmax=tmax, baseline=None, preload=True, reject_by_annotation=True, verbose="ERROR")


def event_id_normalized(epochs: mne.Epochs) -> dict[str, int]:
    return {normalize_marker_label(name): int(code) for name, code in dict(epochs.event_id).items()}


def pick_epochs_by_labels(epochs: mne.Epochs, labels: list[str]) -> mne.Epochs:
    event_id = event_id_normalized(epochs)
    target = {event_id[normalize_marker_label(label)] for label in labels if normalize_marker_label(label) in event_id}
    indices = [idx for idx, ev in enumerate(epochs.events) if int(ev[2]) in target]
    if not indices:
        raise RuntimeError(f"No epochs for labels {labels}; available={sorted(event_id)}")
    return epochs[indices]


def data_from_epochs(epochs: mne.Epochs) -> np.ndarray:
    try:
        return epochs.get_data(copy=False)
    except TypeError:
        return epochs.get_data()


def array_metrics(label: str, reference: Any, server: Any, *, atol: float = 1e-10, rtol: float = 1e-8) -> dict[str, Any]:
    ref = np.asarray(reference, dtype=float)
    got = np.asarray(server, dtype=float)
    if ref.shape != got.shape:
        return {
            "label": label,
            "passed": False,
            "shape_reference": list(ref.shape),
            "shape_server": list(got.shape),
            "reason": "shape mismatch",
        }
    diff = got - ref
    denom = float(np.linalg.norm(ref))
    rmse = float(np.sqrt(np.mean(diff * diff))) if diff.size else 0.0
    rel_rmse = rmse / denom if denom else (0.0 if rmse == 0.0 else math.inf)
    max_abs = float(np.max(np.abs(diff))) if diff.size else 0.0
    ref_std = float(np.std(ref)) if ref.size else 0.0
    diff_std = float(np.std(diff)) if diff.size else 0.0
    passed = bool(np.allclose(ref, got, atol=atol, rtol=rtol, equal_nan=True))
    return {
        "label": label,
        "passed": passed,
        "shape": list(ref.shape),
        "max_abs": max_abs,
        "rmse": rmse,
        "relative_rmse": rel_rmse,
        "reference_std": ref_std,
        "diff_std": diff_std,
        "diff_std_over_reference_std": diff_std / ref_std if ref_std else (0.0 if diff_std == 0.0 else math.inf),
        "atol": atol,
        "rtol": rtol,
    }


def align_channel_array(ref_data: np.ndarray, ref_ch: list[str], server_data: np.ndarray, server_ch: list[str], channel_axis: int) -> tuple[np.ndarray, np.ndarray, list[str]]:
    server_set = set(server_ch)
    common = [ch for ch in ref_ch if ch in server_set]
    if not common:
        raise RuntimeError("No common channels.")
    ref_idx = [ref_ch.index(ch) for ch in common]
    server_idx = [server_ch.index(ch) for ch in common]
    ref = np.take(ref_data, ref_idx, axis=channel_axis)
    got = np.take(server_data, server_idx, axis=channel_axis)
    return ref, got, common


def raw_metrics(label: str, reference: mne.io.BaseRaw, server: mne.io.BaseRaw) -> list[dict[str, Any]]:
    ref, got, common = align_channel_array(reference.get_data(), reference.ch_names, server.get_data(), server.ch_names, 0)
    n_times = min(ref.shape[1], got.shape[1])
    metrics = [array_metrics(label, ref[:, :n_times], got[:, :n_times])]
    metrics.append({"label": f"{label} channel_count", "passed": bool(common), "common_channels": len(common)})
    return metrics


def epochs_metrics(label: str, reference: mne.Epochs, server: mne.Epochs) -> list[dict[str, Any]]:
    ref, got, common = align_channel_array(data_from_epochs(reference), reference.ch_names, data_from_epochs(server), server.ch_names, 1)
    metrics = [array_metrics(label, ref, got)]
    ref_events = [normalize_marker_label(name) for name in reference.event_id]
    got_events = [normalize_marker_label(name) for name in server.event_id]
    metrics.append({"label": f"{label} event_id", "passed": sorted(ref_events) == sorted(got_events), "reference": sorted(ref_events), "server": sorted(got_events)})
    metrics.append({"label": f"{label} channels", "passed": bool(common), "common_channels": len(common)})
    return metrics


def evoked_metrics(label: str, reference: mne.Evoked, server: mne.Evoked) -> list[dict[str, Any]]:
    ref, got, common = align_channel_array(reference.data, reference.ch_names, server.data, server.ch_names, 0)
    return [
        array_metrics(label, ref, got),
        {"label": f"{label} channels", "passed": bool(common), "common_channels": len(common), "nave_reference": int(reference.nave), "nave_server": int(server.nave)},
    ]


def psd_metrics(label: str, reference: dict[str, Any], server: dict[str, Any]) -> list[dict[str, Any]]:
    ref, got, common = align_channel_array(reference["psds"], reference["ch_names"], server["psds"], server["ch_names"], 0)
    return [
        array_metrics(f"{label} psds", ref, got, atol=1e-18, rtol=1e-8),
        array_metrics(f"{label} freqs", reference["freqs"], server["freqs"]),
        {"label": f"{label} channels", "passed": bool(common), "common_channels": len(common)},
    ]


def tfr_metrics(label: str, reference: Any, server: Any) -> list[dict[str, Any]]:
    ref, got, common = align_channel_array(np.asarray(reference.data), reference.ch_names, np.asarray(server.data), server.ch_names, 0)
    return [
        array_metrics(f"{label} power", ref, got, atol=1e-12, rtol=1e-8),
        array_metrics(f"{label} times", reference.times, server.times),
        array_metrics(f"{label} freqs", reference.freqs, server.freqs),
        {"label": f"{label} channels", "passed": bool(common), "common_channels": len(common)},
    ]


def compare_annotations(
    label: str,
    reference: mne.io.BaseRaw,
    server: mne.io.BaseRaw,
    *,
    onset_atol: float = 1e-4,
    duration_atol: float = 1e-6,
) -> dict[str, Any]:
    ref = [(round(float(o), 6), round(float(d), 6), normalize_marker_label(s)) for o, d, s in zip(reference.annotations.onset, reference.annotations.duration, reference.annotations.description)]
    got = [(round(float(o), 6), round(float(d), 6), normalize_marker_label(s)) for o, d, s in zip(server.annotations.onset, server.annotations.duration, server.annotations.description)]
    ref_counts: dict[str, int] = {}
    got_counts: dict[str, int] = {}
    for _o, _d, desc in ref:
        ref_counts[desc] = ref_counts.get(desc, 0) + 1
    for _o, _d, desc in got:
        got_counts[desc] = got_counts.get(desc, 0) + 1
    same_length = len(ref) == len(got)
    max_onset_diff = max((abs(a[0] - b[0]) for a, b in zip(ref, got)), default=0.0)
    max_duration_diff = max((abs(a[1] - b[1]) for a, b in zip(ref, got)), default=0.0)
    same_labels = all(a[2] == b[2] for a, b in zip(ref, got)) if same_length else False
    return {
        "label": label,
        "passed": same_length and same_labels and max_onset_diff <= onset_atol and max_duration_diff <= duration_atol,
        "reference_count": len(ref),
        "server_count": len(got),
        "reference_label_counts": ref_counts,
        "server_label_counts": got_counts,
        "max_onset_diff_sec": max_onset_diff,
        "max_duration_diff_sec": max_duration_diff,
        "onset_atol": onset_atol,
        "duration_atol": duration_atol,
    }


def _coerce_list(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except ValueError:
            return [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def apply_event_remap(raw: mne.io.BaseRaw, params: dict[str, Any]) -> mne.io.BaseRaw:
    mapping: dict[str, str] = {}
    for rule in _coerce_list(params.get("rules")):
        if not isinstance(rule, dict):
            continue
        target = normalize_marker_label(rule.get("target") or "")
        for source in _coerce_list(rule.get("sources")):
            name = normalize_marker_label(source)
            if name and name not in mapping:
                mapping[name] = target
    out = raw.copy()
    annotations = raw.annotations
    descriptions = [normalize_marker_label(item) for item in annotations.description]
    group_names = classify_descriptions(descriptions)
    onsets: list[float] = []
    durations: list[float] = []
    descs: list[str] = []
    for onset, duration, desc, group_name in zip(annotations.onset, annotations.duration, descriptions, group_names):
        if desc.upper().startswith("BAD_"):
            new_desc = desc
        elif group_name in mapping:
            new_desc = mapping[group_name]
            if not new_desc:
                continue
        else:
            new_desc = desc
        onsets.append(float(onset))
        durations.append(float(duration))
        descs.append(new_desc)
    out.set_annotations(mne.Annotations(onset=onsets, duration=durations, description=descs, orig_time=annotations.orig_time))
    return out


def apply_event_manager(raw: mne.io.BaseRaw, params: dict[str, Any]) -> mne.io.BaseRaw:
    annotations = raw.annotations
    managed: list[dict[str, Any]] = []
    preserved: list[dict[str, Any]] = []
    for onset, duration, desc in zip(annotations.onset, annotations.duration, annotations.description):
        rec = {"onset": float(onset), "duration": float(duration), "description": normalize_marker_label(desc)}
        if rec["description"].startswith("BAD_"):
            preserved.append(rec)
        else:
            managed.append(rec)

    rename: dict[str, str] = {}
    shift: dict[str, float] = {}
    for op in _coerce_list(params.get("group_operations")):
        if not isinstance(op, dict):
            continue
        kind = str(op.get("op") or "").strip().lower()
        sources = _coerce_list(op.get("sources"))
        if not kind:
            kind = "shift" if ("delta_s" in op and "target" not in op) else "rename"
        if kind in {"rename", "merge", "relabel", "delete"}:
            target = "" if kind == "delete" else normalize_marker_label(op.get("target") or "")
            for source in sources:
                name = normalize_marker_label(source)
                if name and name not in rename:
                    rename[name] = target
        elif kind == "shift":
            delta = float(op.get("delta_s") or 0.0)
            for source in sources:
                name = normalize_marker_label(source)
                if name:
                    shift[name] = shift.get(name, 0.0) + delta

    group_names = classify_descriptions([event["description"] for event in managed])
    new_managed: list[dict[str, Any]] = []
    for event, group_name in zip(managed, group_names):
        desc = event["description"]
        onset = float(event["onset"])
        if group_name in rename:
            desc = rename[group_name]
            if not desc:
                continue
        if group_name in shift:
            onset = max(0.0, onset + shift[group_name])
        new_managed.append({"onset": onset, "duration": float(event["duration"]), "description": desc})
    new_managed.sort(key=lambda item: item["onset"])

    merged = new_managed + preserved
    out = raw.copy()
    out.set_annotations(
        mne.Annotations(
            onset=[item["onset"] for item in merged],
            duration=[item["duration"] for item in merged],
            description=[item["description"] for item in merged],
            orig_time=annotations.orig_time,
        )
    )
    return out


def apply_artifact_mark(raw: mne.io.BaseRaw, params: dict[str, Any]) -> mne.io.BaseRaw:
    out = raw.copy().load_data()
    requested_bads = [str(item).strip() for item in _coerce_list(params.get("bad_channels")) if str(item).strip()]
    valid_bads = [ch for ch in requested_bads if ch in out.ch_names]
    out.info["bads"] = list(dict.fromkeys(list(out.info.get("bads") or []) + valid_bads))
    segments = []
    for item in _coerce_list(params.get("bad_segments")):
        if not isinstance(item, dict):
            continue
        onset = float(item.get("onset"))
        duration = float(item.get("duration"))
        if onset >= 0 and duration > 0:
            segments.append({"onset": onset, "duration": duration, "source": str(item.get("source") or "manual")})
    if segments:
        existing = out.annotations
        bad = mne.Annotations(
            onset=[item["onset"] for item in segments],
            duration=[item["duration"] for item in segments],
            description=[f"BAD_{item['source']}" for item in segments],
            orig_time=existing.orig_time,
        )
        out.set_annotations(existing + bad)
    return out


def compute_psd_reference(epochs: mne.Epochs, params: dict[str, Any]) -> dict[str, Any]:
    selected = pick_epochs_by_labels(epochs, [normalize_marker_label(v) for v in _coerce_list(params.get("condition"))])
    fmin = float(params.get("fmin", 1.0))
    fmax = min(float(params.get("fmax", 40.0)), float(selected.info["sfreq"]) / 2.0 - 1e-6)
    method = str(params.get("method") or "welch").lower()
    kwargs: dict[str, Any] = {"method": method if method != "fft" else "welch", "fmin": fmin, "fmax": fmax, "verbose": "ERROR"}
    if method == "welch":
        n_fft = params.get("n_fft")
        if n_fft not in (None, ""):
            kwargs["n_fft"] = int(n_fft)
        window_seconds = params.get("window_seconds")
        if window_seconds not in (None, ""):
            n_per_seg = min(int(float(window_seconds) * float(selected.info["sfreq"])), len(selected.times))
            kwargs["n_per_seg"] = n_per_seg
            kwargs["n_overlap"] = int(n_per_seg * float(params.get("overlap", 0.5) or 0.5))
    elif method == "fft":
        seg = len(selected.times)
        kwargs.update({"n_fft": seg, "n_per_seg": seg, "n_overlap": 0})
    spectrum = selected.compute_psd(**kwargs)
    data = np.asarray(spectrum.get_data(), dtype=float)
    psds = data.mean(axis=0) if data.ndim == 3 else data
    return {"freqs": np.asarray(spectrum.freqs, dtype=float), "psds": psds, "ch_names": list(spectrum.ch_names), "sfreq": float(selected.info["sfreq"])}


def compute_tfr_reference(epochs: mne.Epochs, params: dict[str, Any]) -> Any:
    selected = pick_epochs_by_labels(epochs, [normalize_marker_label(v) for v in _coerce_list(params.get("condition"))])
    fmin = float(params.get("fmin", 4.0))
    fmax = min(float(params.get("fmax", 40.0)), float(selected.info["sfreq"]) / 2.0 - 1e-6)
    n_freqs = max(2, int(params.get("n_freqs", 30) or 30))
    if str(params.get("freq_scale") or "linear").lower() == "log":
        freqs = np.logspace(np.log10(fmin), np.log10(fmax), n_freqs)
    else:
        freqs = np.linspace(fmin, fmax, n_freqs)
    if str(params.get("n_cycles_mode") or "factor").lower() == "fixed":
        n_cycles = np.full(freqs.shape, max(1.0, float(params.get("n_cycles_fixed", 7.0) or 7.0)))
    else:
        n_cycles = np.maximum(freqs * float(params.get("n_cycles_factor", 0.5) or 0.5), 1.0)
    power = selected.compute_tfr(method="morlet", freqs=freqs, n_cycles=n_cycles, average=True, return_itc=False, decim=max(1, int(params.get("decim", 4) or 4)), verbose="ERROR")
    mode = str(params.get("baseline_mode", "logratio") or "logratio").lower()
    if mode and mode != "none":
        bmin = float(params.get("baseline_tmin")) if params.get("baseline_tmin") not in (None, "") else float(power.times[0])
        bmax = float(params.get("baseline_tmax")) if params.get("baseline_tmax") not in (None, "") else 0.0
        power.apply_baseline((bmin, bmax), mode=mode, verbose="ERROR")
    power.comment = ",".join([normalize_marker_label(v) for v in _coerce_list(params.get("condition"))])
    return power


def create_evokeds_from_raws(manifest: dict[str, Any], run: str) -> list[tuple[str, mne.Evoked]]:
    out: list[tuple[str, mne.Evoked]] = []
    for subject in SUBJECTS:
        raw = read_raw(raw_path(manifest, subject, run))
        epochs = epoch_raw(raw, [S3_RULE], -0.2, 0.8)
        evoked = pick_epochs_by_labels(epochs, ["S  3"]).average()
        out.append((subject, evoked))
    return out


def stack_evokeds(items: list[tuple[str, mne.Evoked]]) -> dict[str, Any]:
    ref = items[0][1]
    data = []
    for _subject, evoked in items:
        aligned, _server, common = align_channel_array(ref.data, ref.ch_names, evoked.data, evoked.ch_names, 0)
        if common != ref.ch_names:
            raise RuntimeError("Evoked channel mismatch in local stack.")
        data.append(_server)
    return {
        "data": np.stack(data, axis=0),
        "ch_names": list(ref.ch_names),
        "times": np.asarray(ref.times, dtype=float),
        "sfreq": float(ref.info["sfreq"]),
        "subjects": [subject for subject, _ev in items],
        "unit_n": np.asarray([ev.nave for _subject, ev in items], dtype=float),
    }


def ttest_rel_stack(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    from scipy import stats

    result = stats.ttest_rel(a, b, axis=0, alternative="two-sided")
    return np.nan_to_num(result.statistic, nan=0.0), np.nan_to_num(result.pvalue, nan=1.0)


def all_metrics_pass(metrics: list[dict[str, Any]]) -> bool:
    return all(bool(item.get("passed", False)) for item in metrics)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
    return value


def fmt_num(value: Any, digits: int = 4) -> str:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return "-"
    if math.isnan(x):
        return "nan"
    if math.isinf(x):
        return "inf" if x > 0 else "-inf"
    return f"{x:.{digits}g}"


def write_case_report(result: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = REPORT_DIR / f"{result['case']}_REPORT.md"
    metrics = result.get("metrics") or []
    lines = [
        f"# {result['title']} 节点 MNE 对比报告",
        "",
        f"- 节点: `{', '.join(result.get('node_types') or [])}`",
        f"- 流水线: `{result.get('pipeline_name', '-')}`",
        f"- 结论: **{result.get('status')}**",
        f"- 说明: {result.get('summary', '')}",
        "",
        "## 指标",
        "",
        "| 指标 | 通过 | shape | max_abs | relative_rmse | 备注 |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for item in metrics:
        lines.append(
            "| {label} | {passed} | {shape} | {max_abs} | {rel} | {reason} |".format(
                label=item.get("label", "-"),
                passed="是" if item.get("passed") else "否",
                shape="x".join(str(v) for v in item.get("shape", item.get("shape_reference", []))) if isinstance(item.get("shape", item.get("shape_reference", [])), list) else "-",
                max_abs=fmt_num(item.get("max_abs")),
                rel=fmt_num(item.get("relative_rmse")),
                reason=item.get("reason") or item.get("common_channels") or "",
            )
        )
    lines.extend(["", "## 节点参数", "", "```json", json.dumps(_json_safe(result.get("params") or {}), ensure_ascii=False, indent=2), "```", "", "## 原始指标", "", "```json", json.dumps(_json_safe(result), ensure_ascii=False, indent=2), "```", ""])
    report.write_text("\n".join(lines), encoding="utf-8")


def write_summary(results: dict[str, dict[str, Any]]) -> None:
    rows = [
        ("eeg/data/load", "LoadData", "已有 test1", _existing_status(ROOT / "Acc Test" / "TEST_RESULT.md")),
        ("eeg/filter/apply", "Filter(notch/bandpass)", "已有 test1 + sub009_bandpass", _existing_status(ROOT / "Acc Test" / "TEST_RESULT.md")),
        ("eeg/preproc/resample", "Resample", "已有 sub009_preproc_nodes", _existing_status(ROOT / "Acc Test" / "sub009_preproc_nodes" / "reports" / "resample_500_REPORT.md")),
        ("eeg/preproc/rereference", "Re-reference", "已有 sub009_preproc_nodes", _existing_status(ROOT / "Acc Test" / "sub009_preproc_nodes" / "reports" / "reref_tp9_tp10_REPORT.md")),
        ("eeg/preproc/channel_location", "Ch Loc Assign", "已有 sub009_preproc_nodes", _existing_status(ROOT / "Acc Test" / "sub009_preproc_nodes" / "reports" / "channel_location_REPORT.md")),
        ("eeg/preproc/bad_channels", "Bad Channels", "已有 sub009_preproc_nodes", _existing_status(ROOT / "Acc Test" / "sub009_preproc_nodes" / "reports" / "bad_channels_REPORT.md")),
        ("eeg/preproc/artifact_mark", "Artifact Mark", "node_suite/artifact_mark", _result_status(results, "artifact_mark")),
        ("eeg/preproc/event_manager", "Event Manager", "node_suite/event_manager", _result_status(results, "event_manager")),
        ("eeg/preproc/event_remap", "Event Remap", "node_suite/event_remap", _result_status(results, "event_remap")),
        ("eeg/ica/compute", "Compute ICA", "已有 test_ica_consistency", _existing_status(ROOT / "Acc Test" / "test_ica_consistency" / "TEST_ICA_REPORT.md")),
        ("eeg/ica/apply", "Apply ICA", "已有 test_ica_consistency", _existing_status(ROOT / "Acc Test" / "test_ica_consistency" / "TEST_ICA_REPORT.md")),
        ("eeg/ica/iclabel", "ICLabel", "node_suite/iclabel", _result_status(results, "iclabel")),
        ("eeg/epoch/segment", "Epoch", "已有 test1 + node_suite/epoch_reject", _result_status(results, "epoch_reject")),
        ("eeg/epoch/merge", "Epoch Merge", "node_suite/epoch_merge", _result_status(results, "epoch_merge")),
        ("eeg/epoch/baseline", "Baseline", "已有 test1", _existing_status(ROOT / "Acc Test" / "TEST_RESULT.md")),
        ("eeg/epoch/reject", "Reject Trials", "node_suite/epoch_reject", _result_status(results, "epoch_reject")),
        ("eeg/analysis/erp", "ERP Average", "已有 test1 + node_suite/group_average", _result_status(results, "group_average")),
        ("eeg/analysis/tfr", "TFR", "node_suite/tfr", _result_status(results, "tfr")),
        ("eeg/analysis/psd", "PSD", "node_suite/psd", _result_status(results, "psd")),
        ("eeg/group/merge", "Group Merge", "node_suite/group_average/group_compare", _result_status(results, "group_average")),
        ("eeg/group/average", "Grand Average", "node_suite/group_average", _result_status(results, "group_average")),
        ("eeg/group/compare", "Group Compare", "node_suite/group_compare", _result_status(results, "group_compare")),
    ]
    lines = [
        "# ELYS 节点输出 vs MNE 本地复算一致性总表",
        "",
        "本表汇总 `Acc Test` 中已有节点测试与本次补充的 `node_suite` 测试。`已有` 表示对应独立报告/产物已在仓库中；`PASS/FAIL/SKIP` 来自本次自动复算结果。",
        "",
        "| 节点类型 | 节点 | 测试入口 | 结果 |",
        "| --- | --- | --- | --- |",
    ]
    for node_type, title, entry, status in rows:
        lines.append(f"| `{node_type}` | {title} | {entry} | {status} |")
    lines.extend(["", "## 本次补充测试明细", ""])
    for key, result in results.items():
        lines.append(f"- `{key}`: **{result.get('status')}** - {result.get('summary', '')}")
    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _existing_status(path: Path) -> str:
    return "PASS（已有报告）" if path.exists() else "未生成"


def _result_status(results: dict[str, dict[str, Any]], key: str) -> str:
    return str(results.get(key, {}).get("status") or "未运行")


def run_one(case_key: str) -> dict[str, Any]:
    if case_key not in CASE_RUNNERS:
        raise KeyError(f"Unknown case: {case_key}")
    manifest = load_manifest()
    result = CASE_RUNNERS[case_key](manifest)
    write_case_report(result)
    return result


def run_all(case_keys: list[str] | None = None) -> dict[str, dict[str, Any]]:
    keys = case_keys or list(CASE_RUNNERS)
    results: dict[str, dict[str, Any]] = {}
    for key in keys:
        try:
            results[key] = run_one(key)
        except Exception as exc:  # noqa: BLE001 - keep the suite reporting all node failures
            results[key] = {
                "case": key,
                "title": CASE_TITLES.get(key, key),
                "node_types": CASE_NODE_TYPES.get(key, []),
                "status": "FAIL",
                "summary": str(exc),
                "metrics": [{"label": "exception", "passed": False, "reason": str(exc)}],
                "params": {},
            }
            write_case_report(results[key])
    META_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(json.dumps(_json_safe(results), ensure_ascii=False, indent=2), encoding="utf-8")
    write_summary(results)
    return results


def _case_result(case: str, manifest: dict[str, Any], metrics: list[dict[str, Any]], *, params: dict[str, Any], summary: str) -> dict[str, Any]:
    passed = all_metrics_pass(metrics)
    return {
        "case": case,
        "title": CASE_TITLES[case],
        "node_types": CASE_NODE_TYPES[case],
        "pipeline_name": manifest.get("cases", {}).get(case, {}).get("pipeline_name", ""),
        "status": "PASS" if passed else "FAIL",
        "summary": summary,
        "metrics": metrics,
        "params": params,
    }


def compare_event_remap(manifest: dict[str, Any]) -> dict[str, Any]:
    params = node_params(manifest, "event_remap", "evt_remap")
    raw = read_raw(raw_path(manifest))
    ref = apply_event_remap(raw, params)
    server = read_raw(find_download(manifest, "event_remap", node_id="evt_remap")["local_path"])
    metrics = raw_metrics("Event Remap raw data", ref, server)
    metrics.append(compare_annotations("Event Remap annotations", ref, server))
    return _case_result("event_remap", manifest, metrics, params=params, summary="按规则重命名 S3、删除 S4；数据本体应不变，annotations 应完全一致。")


def compare_event_manager(manifest: dict[str, Any]) -> dict[str, Any]:
    params = node_params(manifest, "event_manager", "evt_mgr")
    raw = read_raw(raw_path(manifest))
    ref = apply_event_manager(raw, params)
    server = read_raw(find_download(manifest, "event_manager", node_id="evt_mgr")["local_path"])
    metrics = raw_metrics("Event Manager raw data", ref, server)
    metrics.append(compare_annotations("Event Manager annotations", ref, server))
    return _case_result("event_manager", manifest, metrics, params=params, summary="按规则重命名 S4 并平移 S5；数据本体应不变，annotations 应完全一致。")


def compare_artifact_mark(manifest: dict[str, Any]) -> dict[str, Any]:
    params = node_params(manifest, "artifact_mark", "artifact")
    raw = read_raw(raw_path(manifest))
    ref = apply_artifact_mark(raw, params)
    server = read_raw(find_download(manifest, "artifact_mark", node_id="artifact")["local_path"])
    metrics = raw_metrics("Artifact Mark raw data", ref, server)
    metrics.append(compare_annotations("Artifact Mark annotations", ref, server))
    metrics.append({"label": "Artifact Mark bad channels", "passed": list(ref.info["bads"]) == list(server.info["bads"]), "reference": list(ref.info["bads"]), "server": list(server.info["bads"])})
    return _case_result("artifact_mark", manifest, metrics, params=params, summary="坏段只写 BAD_ annotation，坏道只写 info['bads']，信号样本不应改变。")


def compare_epoch_reject(manifest: dict[str, Any]) -> dict[str, Any]:
    ep_params = node_params(manifest, "epoch_reject", "ep")
    rej_params = node_params(manifest, "epoch_reject", "rej")
    raw = read_raw(raw_path(manifest))
    epochs = epoch_raw(raw, ep_params["conditions"], float(ep_params["tmin"]), float(ep_params["tmax"]))
    cleaned = epochs.copy()
    reject = {"eeg": float(rej_params["reject_peak_to_peak"]) * 1e-6} if float(rej_params.get("reject_peak_to_peak") or 0) > 0 else None
    flat = {"eeg": float(rej_params["flat"]) * 1e-6} if rej_params.get("flat") not in (None, "") and float(rej_params["flat"]) > 0 else None
    cleaned.drop_bad(reject=reject, flat=flat, verbose="ERROR")
    server = read_epochs(find_download(manifest, "epoch_reject", node_id="rej")["local_path"])
    metrics = epochs_metrics("Reject Trials epochs", cleaned, server)
    return _case_result("epoch_reject", manifest, metrics, params={"epoch": ep_params, "reject": rej_params}, summary="Raw→Epoch 后按 MNE drop_bad 阈值法剔除；高阈值用来验证不误剔。")


def compare_epoch_merge(manifest: dict[str, Any]) -> dict[str, Any]:
    ep_params = node_params(manifest, "epoch_merge", "ep")
    merge_params = node_params(manifest, "epoch_merge", "merge")
    raw = read_raw(raw_path(manifest))
    epochs = epoch_raw(raw, ep_params["conditions"], float(ep_params["tmin"]), float(ep_params["tmax"]))
    parts = []
    for label in sorted(event_id_normalized(epochs)):
        parts.append(pick_epochs_by_labels(epochs, [label]))
    reference = mne.concatenate_epochs(parts, add_offset=True, on_mismatch="ignore", verbose="ERROR")
    server = read_epochs(find_download(manifest, "epoch_merge", node_id="merge")["local_path"])
    metrics = epochs_metrics("Epoch Merge source_recording", reference, server)
    return _case_result("epoch_merge", manifest, metrics, params={"epoch": ep_params, "merge": merge_params}, summary="按原始记录合并 S3/S4 条件切出的 Epochs；样本数据、事件类型和顺序应与本地 concatenate_epochs 一致。")


def compare_psd(manifest: dict[str, Any]) -> dict[str, Any]:
    ep_params = node_params(manifest, "psd", "ep")
    psd_params = node_params(manifest, "psd", "psd")
    raw = read_raw(raw_path(manifest))
    epochs = epoch_raw(raw, ep_params["conditions"], float(ep_params["tmin"]), float(ep_params["tmax"]))
    ref = compute_psd_reference(epochs, psd_params)
    server = load_psd(find_download(manifest, "psd", node_id="psd")["local_path"])
    metrics = psd_metrics("PSD Welch", ref, server)
    return _case_result("psd", manifest, metrics, params={"epoch": ep_params, "psd": psd_params}, summary="按条件选择 Epochs 后调用 MNE compute_psd，并跨 epoch 求均值。")


def compare_tfr(manifest: dict[str, Any]) -> dict[str, Any]:
    ep_params = node_params(manifest, "tfr", "ep")
    tfr_params = node_params(manifest, "tfr", "tfr")
    raw = read_raw(raw_path(manifest))
    epochs = epoch_raw(raw, ep_params["conditions"], float(ep_params["tmin"]), float(ep_params["tmax"]))
    ref = compute_tfr_reference(epochs, tfr_params)
    server = read_tfr(find_download(manifest, "tfr", node_id="tfr")["local_path"])
    metrics = tfr_metrics("TFR Morlet", ref, server)
    return _case_result("tfr", manifest, metrics, params={"epoch": ep_params, "tfr": tfr_params}, summary="按条件选择 Epochs 后调用 MNE Morlet TFR，并应用同一基线校正。")


def compare_iclabel(manifest: dict[str, Any]) -> dict[str, Any]:
    params = node_params(manifest, "iclabel", "iclabel")
    run = manifest.get("cases", {}).get("iclabel", {}).get("run", {})
    result_json = run.get("result_json") or {}
    node_results = result_json.get("node_results") or []
    ic_node = next((item for item in node_results if item.get("node_id") == "iclabel"), {})
    infos = (result_json.get("data_infos_by_node") or {}).get("iclabel") or []
    detail = dict((infos[0] or {}).get("iclabel") or {}) if infos else {}
    components = list(detail.get("components") or [])
    excluded = list(detail.get("excluded_components") or [])
    metrics = [
        {"label": "ICLabel node completed", "passed": ic_node.get("status") == "completed", "status": ic_node.get("status"), "dataset_count": ic_node.get("dataset_count")},
        {"label": "ICLabel mode", "passed": params.get("action") == "mark" and detail.get("action") == "mark", "params_action": params.get("action"), "metadata_action": detail.get("action")},
        {"label": "ICLabel component count", "passed": int(detail.get("n_components") or 0) == len(components) == 10, "n_components": detail.get("n_components"), "components": len(components)},
        {"label": "ICLabel excluded count", "passed": int(detail.get("n_excluded") or 0) == len(excluded), "n_excluded": detail.get("n_excluded"), "excluded": excluded},
    ]
    # action=mark writes classification metadata and reuses the upstream raw data
    # when the samples are unchanged, so no separate FIF download is required.
    return _case_result("iclabel", manifest, metrics, params={"params": params, "iclabel_metadata": detail}, summary="mark 模式校验 ICLabel 分类 metadata；该模式不改信号，后端可能复用上游 raw 文件而不产生新 FIF。")


def compare_group_average(manifest: dict[str, Any]) -> dict[str, Any]:
    local_items = create_evokeds_from_raws(manifest, RUN_A)
    local_stack = stack_evokeds(local_items)
    server_stack = load_unit_stack(find_download(manifest, "group_average", node_id="gm", data_type="unit_stack")["local_path"])
    stack_ref, stack_got, common = align_channel_array(local_stack["data"], local_stack["ch_names"], server_stack["data"], server_stack["ch_names"], 1)
    mean = stack_ref.mean(axis=0)
    ga_server = read_evoked(find_download(manifest, "group_average", node_id="ga", data_type="evoked")["local_path"])
    mean_got, ga_got, _common_ga = align_channel_array(mean, common, ga_server.data, ga_server.ch_names, 0)
    metrics = [
        array_metrics("Group Merge unit_stack", stack_ref, stack_got),
        array_metrics("Grand Average evoked mean", mean_got, ga_got),
        array_metrics("Grand Average times", local_stack["times"], ga_server.times, atol=1e-8, rtol=1e-8),
        {"label": "Group Average unit count", "passed": int(server_stack["data"].shape[0]) == len(SUBJECTS), "server_units": int(server_stack["data"].shape[0])},
    ]
    params = {"epoch": node_params(manifest, "group_average", "ep"), "erp": node_params(manifest, "group_average", "erp"), "group_merge": node_params(manifest, "group_average", "gm"), "grand_average": node_params(manifest, "group_average", "ga")}
    return _case_result("group_average", manifest, metrics, params=params, summary="三名被试各自 Epoch→ERP 后按 subject 堆叠，再沿 unit 轴求均值。")


def compare_group_compare(manifest: dict[str, Any]) -> dict[str, Any]:
    stack_a = stack_evokeds(create_evokeds_from_raws(manifest, RUN_A))
    stack_b = stack_evokeds(create_evokeds_from_raws(manifest, RUN_B))
    tmap, pmap = ttest_rel_stack(stack_a["data"], stack_b["data"])
    stat = load_stat_map(find_download(manifest, "group_compare", node_id="cmp", data_type="stat_map")["local_path"])
    t_ref, t_got, common = align_channel_array(tmap, stack_a["ch_names"], stat["tmap"], stat["ch_names"], 0)
    p_ref, p_got, _common = align_channel_array(pmap, stack_a["ch_names"], stat["pmap"], stat["ch_names"], 0)
    mean_a_ref, mean_a_got, _common = align_channel_array(stack_a["data"].mean(axis=0), stack_a["ch_names"], stat["mean_a"], stat["ch_names"], 0)
    mean_b_ref, mean_b_got, _common = align_channel_array(stack_b["data"].mean(axis=0), stack_b["ch_names"], stat["mean_b"], stat["ch_names"], 0)
    sig_ref = p_ref < float(node_params(manifest, "group_compare", "cmp").get("alpha", 0.05))
    sig_got = np.take(stat["sig"], [stat["ch_names"].index(ch) for ch in common], axis=0)
    metrics = [
        array_metrics("Group Compare tmap", t_ref, t_got, atol=2e-3, rtol=1e-5),
        array_metrics("Group Compare pmap", p_ref, p_got, atol=1e-6, rtol=1e-6),
        array_metrics("Group Compare mean A", mean_a_ref, mean_a_got),
        array_metrics("Group Compare mean B", mean_b_ref, mean_b_got),
        {"label": "Group Compare sig mask", "passed": bool(np.array_equal(sig_ref, sig_got)), "shape": list(sig_ref.shape), "n_sig_reference": int(sig_ref.sum()), "n_sig_server": int(sig_got.sum())},
    ]
    params = {"compare": node_params(manifest, "group_compare", "cmp")}
    return _case_result("group_compare", manifest, metrics, params=params, summary="A/B 两个 run 的 subject-level ERP unit_stack 进行配对逐点 t 检验。")


CASE_TITLES = {
    "event_remap": "Event Remap",
    "event_manager": "Event Manager",
    "artifact_mark": "Artifact Mark",
    "epoch_reject": "Reject Trials",
    "epoch_merge": "Epoch Merge",
    "psd": "PSD",
    "tfr": "TFR",
    "iclabel": "ICLabel",
    "group_average": "Group Merge + Grand Average",
    "group_compare": "Group Compare",
}

CASE_NODE_TYPES = {
    "event_remap": ["eeg/preproc/event_remap"],
    "event_manager": ["eeg/preproc/event_manager"],
    "artifact_mark": ["eeg/preproc/artifact_mark"],
    "epoch_reject": ["eeg/epoch/reject"],
    "epoch_merge": ["eeg/epoch/merge"],
    "psd": ["eeg/analysis/psd"],
    "tfr": ["eeg/analysis/tfr"],
    "iclabel": ["eeg/ica/iclabel"],
    "group_average": ["eeg/group/merge", "eeg/group/average"],
    "group_compare": ["eeg/group/compare"],
}

CASE_RUNNERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "event_remap": compare_event_remap,
    "event_manager": compare_event_manager,
    "artifact_mark": compare_artifact_mark,
    "epoch_reject": compare_epoch_reject,
    "epoch_merge": compare_epoch_merge,
    "psd": compare_psd,
    "tfr": compare_tfr,
    "iclabel": compare_iclabel,
    "group_average": compare_group_average,
    "group_compare": compare_group_compare,
}
