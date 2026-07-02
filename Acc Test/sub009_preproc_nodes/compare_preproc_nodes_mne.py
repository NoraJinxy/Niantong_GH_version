"""Build local MNE references for preprocessing-node outputs and write reports."""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import mne  # noqa: E402
import numpy as np  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "elys_project" / "backend"
sys.path.insert(0, str(BACKEND))

from app.engine.preprocess.channel_location import run_channel_location  # noqa: E402


HERE = Path(__file__).resolve().parent
SERVER_DIR = HERE / "server_outputs"
FIG_DIR = HERE / "figures"
META_DIR = HERE / "metadata"
REPORT_DIR = HERE / "reports"
RAW_PATH = SERVER_DIR / "sub-009_ses-a_task-sensory_run-04_eeg.fif"


CASES: dict[str, dict[str, Any]] = {
    "resample_500": {
        "title": "Resample 500Hz",
        "server_path": SERVER_DIR / "sub-009_ses-a_task-sensory_run-04_resample_500Hz-raw.fif",
        "report": REPORT_DIR / "resample_500_REPORT.md",
        "params_text": "`raw.resample(sfreq=500, npad='auto')`",
    },
    "notch_50": {
        "title": "Filter Notch 50Hz",
        "server_path": SERVER_DIR / "sub-009_ses-a_task-sensory_run-04_notch_50Hz-raw.fif",
        "report": REPORT_DIR / "notch_50_REPORT.md",
        "params_text": "`raw.notch_filter(freqs=[50, 100, 150], method='spectrum_fit')`",
    },
    "reref_tp9_tp10": {
        "title": "Re-reference TP9/TP10",
        "server_path": SERVER_DIR / "sub-009_ses-a_task-sensory_run-04_reref_TP9_TP10-raw.fif",
        "report": REPORT_DIR / "reref_tp9_tp10_REPORT.md",
        "params_text": "`raw.set_eeg_reference(ref_channels=['TP9', 'TP10'], projection=False)`",
    },
    "channel_location": {
        "title": "Ch Loc Assign Default",
        "server_path": SERVER_DIR / "sub-009_ses-a_task-sensory_run-04_chloc_default-raw.fif",
        "report": REPORT_DIR / "channel_location_REPORT.md",
        "params_text": "`mne.channels.make_standard_montage(...)` + `raw.set_montage(...)`, using the same auto selection as the node",
    },
    "bad_channels": {
        "title": "Bad Channels Default",
        "server_path": SERVER_DIR / "sub-009_ses-a_task-sensory_run-04_bad_channels_default-raw.fif",
        "report": REPORT_DIR / "bad_channels_REPORT.md",
        "params_text": "`mne.preprocessing.find_bad_channels_lof(..., threshold=1.5, n_neighbors=20)` + `raw.interpolate_bads(reset_bads=True)`",
    },
}


def _load_raw() -> mne.io.BaseRaw:
    if not RAW_PATH.exists():
        raise FileNotFoundError(f"Missing raw FIF: {RAW_PATH}")
    return mne.io.read_raw_fif(RAW_PATH, preload=True, verbose="ERROR")


def _reference_raw(case_key: str, raw: mne.io.BaseRaw) -> tuple[mne.io.BaseRaw, dict[str, Any]]:
    if case_key == "resample_500":
        ref = raw.copy().load_data()
        ref.resample(sfreq=500, npad="auto", verbose="ERROR")
        return ref, {"sfreq": 500, "npad": "auto"}

    if case_key == "notch_50":
        ref = raw.copy().load_data()
        sfreq = float(ref.info["sfreq"])
        freqs = [50.0 * order for order in range(1, 4) if 50.0 * order < sfreq / 2.0]
        ref.notch_filter(freqs=freqs, method="spectrum_fit", verbose="ERROR")
        return ref, {"notch_freq": 50.0, "notch_harmonics": 3, "freqs": freqs, "method": "spectrum_fit"}

    if case_key == "reref_tp9_tp10":
        ref = raw.copy().load_data()
        requested = ["TP9", "TP10"]
        bads = set(ref.info.get("bads") or [])
        used = [channel for channel in requested if channel not in bads]
        ref.set_eeg_reference(ref_channels=used, projection=False, verbose="ERROR")
        return ref, {"ref_channels": requested, "ref_used": used}

    if case_key == "channel_location":
        ref, meta = run_channel_location(raw, {})
        return ref, meta

    if case_key == "bad_channels":
        ref = raw.copy().load_data()
        n_eeg = len(mne.pick_types(ref.info, eeg=True, meg=False, exclude=[]))
        n_neighbors = min(20, n_eeg - 1)
        detected = list(
            mne.preprocessing.find_bad_channels_lof(
                ref,
                n_neighbors=n_neighbors,
                picks="eeg",
                threshold=1.5,
                verbose="ERROR",
            )
        )
        preexisting = list(ref.info.get("bads", []) or [])
        all_bads = list(dict.fromkeys(preexisting + detected))
        ref.info["bads"] = all_bads
        interpolated = False
        if all_bads:
            ref.interpolate_bads(reset_bads=True, verbose="ERROR")
            interpolated = True
        return ref, {
            "method": "lof",
            "threshold": 1.5,
            "n_neighbors": n_neighbors,
            "preexisting_bads": preexisting,
            "detected_bads": detected,
            "bads": all_bads,
            "action": "interpolate",
            "interpolated": interpolated,
            "reset_bads": True,
        }

    raise KeyError(case_key)


def _align(ref: mne.io.BaseRaw, server: mne.io.BaseRaw):
    common = [ch for ch in ref.ch_names if ch in server.ch_names]
    if not common:
        raise RuntimeError("No common channels between MNE and server output.")
    ref_aligned = ref.copy().pick(common)
    server_aligned = server.copy().pick(common)
    n_times = min(ref_aligned.n_times, server_aligned.n_times)
    ref_data = ref_aligned.get_data()[:, :n_times]
    server_data = server_aligned.get_data()[:, :n_times]
    sfreq_ref = float(ref_aligned.info["sfreq"])
    sfreq_server = float(server_aligned.info["sfreq"])
    return common, sfreq_ref, sfreq_server, ref_data, server_data


def _position_map(raw: mne.io.BaseRaw) -> dict[str, np.ndarray]:
    try:
        montage = raw.get_montage()
    except Exception:
        montage = None
    if montage is None:
        return {}
    positions = montage.get_positions().get("ch_pos", {})
    return {str(name): np.asarray(pos, dtype=float) for name, pos in positions.items()}


def _montage_metrics(ref: mne.io.BaseRaw, server: mne.io.BaseRaw, common: list[str]) -> dict[str, Any]:
    ref_pos = _position_map(ref)
    server_pos = _position_map(server)
    shared = [ch for ch in common if ch in ref_pos and ch in server_pos]
    if not shared:
        return {
            "ref_dig_count": 0 if ref.info.get("dig") is None else len(ref.info["dig"]),
            "server_dig_count": 0 if server.info.get("dig") is None else len(server.info["dig"]),
            "channels_with_positions": 0,
            "max_position_diff_m": math.nan,
            "rmse_position_diff_m": math.nan,
        }
    diffs = np.array([server_pos[ch] - ref_pos[ch] for ch in shared])
    norms = np.linalg.norm(diffs, axis=1)
    return {
        "ref_dig_count": 0 if ref.info.get("dig") is None else len(ref.info["dig"]),
        "server_dig_count": 0 if server.info.get("dig") is None else len(server.info["dig"]),
        "channels_with_positions": len(shared),
        "max_position_diff_m": float(np.max(norms)),
        "rmse_position_diff_m": float(np.sqrt(np.mean(norms**2))),
    }


def _metrics(case_key: str, ref: mne.io.BaseRaw, server: mne.io.BaseRaw, meta: dict[str, Any]) -> dict[str, Any]:
    common, sfreq_ref, sfreq_server, ref_data, server_data = _align(ref, server)
    diff = server_data - ref_data
    ref_std = np.std(ref_data, ddof=0)
    diff_std = np.std(diff, ddof=0)
    channel_rows = []
    for idx, ch in enumerate(common):
        x = ref_data[idx]
        y = server_data[idx]
        corr = float(np.corrcoef(x, y)[0, 1]) if np.std(x) and np.std(y) else math.nan
        channel_rows.append(
            {
                "channel": ch,
                "mne_std_v": float(np.std(x, ddof=0)),
                "diff_mean_v": float(np.mean(y - x)),
                "diff_std_v": float(np.std(y - x, ddof=0)),
                "diff_rmse_v": float(np.sqrt(np.mean((y - x) ** 2))),
                "diff_max_abs_v": float(np.max(np.abs(y - x))),
                "diff_std_over_mne_std": float(np.std(y - x, ddof=0) / np.std(x, ddof=0)) if np.std(x) else math.nan,
                "corr": corr,
            }
        )
    global_metrics = {
        "mne_std_v": float(ref_std),
        "diff_mean_v": float(np.mean(diff)),
        "diff_std_v": float(diff_std),
        "diff_rmse_v": float(np.sqrt(np.mean(diff**2))),
        "diff_max_abs_v": float(np.max(np.abs(diff))),
        "diff_std_over_mne_std": float(diff_std / ref_std) if ref_std else math.nan,
        "relative_l2": float(np.linalg.norm(diff) / np.linalg.norm(ref_data)) if np.linalg.norm(ref_data) else math.nan,
    }
    return {
        "case": case_key,
        "title": CASES[case_key]["title"],
        "raw_path": str(RAW_PATH),
        "server_path": str(CASES[case_key]["server_path"]),
        "reference_meta": meta,
        "sfreq_mne": sfreq_ref,
        "sfreq_server": sfreq_server,
        "n_channels": len(common),
        "n_times": int(ref_data.shape[1]),
        "duration_sec": float(ref_data.shape[1] / sfreq_ref),
        "global": global_metrics,
        "channels": channel_rows,
        "montage": _montage_metrics(ref, server, common),
    }


def _pick_channels(common: list[str]) -> list[str]:
    preferred = ["Fp1", "Cz", "Oz"]
    picked = [ch for ch in preferred if ch in common]
    for ch in common:
        if len(picked) >= 3:
            break
        if ch not in picked:
            picked.append(ch)
    return picked


def _plot(case_key: str, metrics: dict, ref: mne.io.BaseRaw, server: mne.io.BaseRaw) -> tuple[Path, Path]:
    common, sfreq_ref, _sfreq_server, ref_data, server_data = _align(ref, server)
    channels = _pick_channels(common)
    case_fig_dir = FIG_DIR / case_key
    case_fig_dir.mkdir(parents=True, exist_ok=True)
    duration_sec = min(5.0, metrics["duration_sec"])
    start_sec = 10.0 if metrics["duration_sec"] > 15.0 else 0.0
    start = int(start_sec * sfreq_ref)
    stop = min(ref_data.shape[1], int((start_sec + duration_sec) * sfreq_ref))
    times = np.arange(start, stop) / sfreq_ref

    fig, axes = plt.subplots(len(channels), 1, figsize=(12, 2.6 * len(channels)), sharex=True)
    axes = np.atleast_1d(axes)
    for ax, ch in zip(axes, channels):
        idx = common.index(ch)
        ax.plot(times, ref_data[idx, start:stop] * 1e6, label="MNE", linewidth=1.0)
        ax.plot(times, server_data[idx, start:stop] * 1e6, label="ELYS", linewidth=0.9, alpha=0.75)
        ax.set_ylabel(f"{ch}\n(uV)")
        ax.grid(True, alpha=0.25)
    axes[0].legend(loc="upper right")
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle(f"{metrics['title']}: MNE vs ELYS")
    fig.tight_layout()
    overlay = case_fig_dir / "overlay.png"
    fig.savefig(overlay, dpi=160)
    plt.close(fig)

    diff = server_data - ref_data
    fig, axes = plt.subplots(len(channels), 1, figsize=(12, 2.4 * len(channels)), sharex=True)
    axes = np.atleast_1d(axes)
    for ax, ch in zip(axes, channels):
        idx = common.index(ch)
        ax.plot(times, diff[idx, start:stop] * 1e6, color="#b42318", linewidth=0.9)
        ax.axhline(0, color="#333333", linewidth=0.7, alpha=0.5)
        ax.set_ylabel(f"{ch}\n(uV)")
        ax.grid(True, alpha=0.25)
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle(f"{metrics['title']}: ELYS - MNE")
    fig.tight_layout()
    difference = case_fig_dir / "difference.png"
    fig.savefig(difference, dpi=160)
    plt.close(fig)
    return overlay, difference


def _fmt_uv(value_v: float) -> str:
    return "nan" if math.isnan(value_v) else f"{value_v * 1e6:.6g}"


def _fmt_ratio(value: float) -> str:
    return "nan" if math.isnan(value) else f"{value:.6g}"


def _write_report(metrics: dict, overlay: Path, difference: Path) -> None:
    case = metrics["case"]
    report = CASES[case]["report"]
    report.parent.mkdir(parents=True, exist_ok=True)
    global_metrics = metrics["global"]
    top_rows = sorted(metrics["channels"], key=lambda row: row["diff_rmse_v"], reverse=True)[:10]
    montage = metrics["montage"]
    lines = [
        f"# {metrics['title']} 节点一致性测试",
        "",
        "## 测试设置",
        "",
        f"- 原始输入: `{RAW_PATH.name}`",
        f"- 服务器输出: `{Path(metrics['server_path']).name}`",
        f"- 本地 MNE 标准: {CASES[case]['params_text']}",
        f"- 对比范围: {metrics['n_channels']} 通道 x {metrics['n_times']} 采样点, {metrics['duration_sec']:.2f} s",
        f"- 采样率: MNE {metrics['sfreq_mne']:.3f} Hz, ELYS {metrics['sfreq_server']:.3f} Hz",
        "",
        "## 差异汇总",
        "",
        "| 指标 | 数值 | 单位 |",
        "| --- | ---: | --- |",
        f"| MNE 信号标准差 | {_fmt_uv(global_metrics['mne_std_v'])} | uV |",
        f"| 差值均值 | {_fmt_uv(global_metrics['diff_mean_v'])} | uV |",
        f"| 差值标准差 | {_fmt_uv(global_metrics['diff_std_v'])} | uV |",
        f"| 差值 RMSE | {_fmt_uv(global_metrics['diff_rmse_v'])} | uV |",
        f"| 差值最大绝对值 | {_fmt_uv(global_metrics['diff_max_abs_v'])} | uV |",
        f"| 差值标准差 / MNE 标准差 | {_fmt_ratio(global_metrics['diff_std_over_mne_std'])} | ratio |",
        f"| 相对 L2 误差 | {_fmt_ratio(global_metrics['relative_l2'])} | ratio |",
        "",
        "## 通道指标",
        "",
        "按 RMSE 从大到小列出前 10 个通道。",
        "",
        "| 通道 | MNE 标准差 (uV) | 差值标准差 (uV) | RMSE (uV) | 最大绝对差值 (uV) | 差值标准差 / MNE 标准差 | 相关系数 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in top_rows:
        lines.append(
            "| {channel} | {mne_std} | {diff_std} | {rmse} | {max_abs} | {ratio} | {corr:.9f} |".format(
                channel=row["channel"],
                mne_std=_fmt_uv(row["mne_std_v"]),
                diff_std=_fmt_uv(row["diff_std_v"]),
                rmse=_fmt_uv(row["diff_rmse_v"]),
                max_abs=_fmt_uv(row["diff_max_abs_v"]),
                ratio=_fmt_ratio(row["diff_std_over_mne_std"]),
                corr=row["corr"],
            )
        )
    lines.extend(
        [
            "",
            "## 坐标/元信息",
            "",
            "| 指标 | 数值 | 单位 |",
            "| --- | ---: | --- |",
            f"| MNE dig 点数 | {montage['ref_dig_count']} | count |",
            f"| ELYS dig 点数 | {montage['server_dig_count']} | count |",
            f"| 可比较坐标通道数 | {montage['channels_with_positions']} | count |",
            f"| 坐标最大差异 | {montage['max_position_diff_m']:.6g} | m |",
            f"| 坐标 RMSE | {montage['rmse_position_diff_m']:.6g} | m |",
            "",
            "## 节点参数/默认值",
            "",
            "```json",
            json.dumps(metrics["reference_meta"], ensure_ascii=False, indent=2),
            "```",
            "",
            "## 图",
            "",
            f"![MNE 与 ELYS 叠加对比]({Path(os.path.relpath(overlay, report.parent)).as_posix()})",
            "",
            f"![差值信号 ELYS - MNE]({Path(os.path.relpath(difference, report.parent)).as_posix()})",
            "",
            "## 说明",
            "",
            "- 所有指标都基于完整对齐后的信号计算。",
            "- 为了便于观察，图中只显示从 10 s 开始的 5 s 片段；采样不足 15 s 时从 0 s 开始。",
        ]
    )
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    META_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    raw = _load_raw()
    all_metrics: dict[str, Any] = {}
    for case_key, case in CASES.items():
        if not case["server_path"].exists():
            raise FileNotFoundError(f"Missing server output for {case_key}: {case['server_path']}")
        print(f"Comparing {case_key} ...", flush=True)
        ref, meta = _reference_raw(case_key, raw)
        server = mne.io.read_raw_fif(case["server_path"], preload=True, verbose="ERROR")
        metrics = _metrics(case_key, ref, server, meta)
        overlay, difference = _plot(case_key, metrics, ref, server)
        _write_report(metrics, overlay, difference)
        all_metrics[case_key] = metrics

    metrics_path = META_DIR / "comparison_metrics.json"
    metrics_path.write_text(json.dumps(all_metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"metrics_path": str(metrics_path), "report_dir": str(REPORT_DIR)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
