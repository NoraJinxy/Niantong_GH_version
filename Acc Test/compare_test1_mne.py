from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import mne
import numpy as np


ROOT = Path(__file__).resolve().parent
SERVER = ROOT / "server_outputs"
REPORT = ROOT / "TEST_RESULT.md"

CONDITIONS = ["Stimulus/S  3", "Stimulus/S  4", "Stimulus/S  5"]


def read_raw(path: Path, *, preload: bool = True) -> mne.io.BaseRaw:
    ext = path.suffix.lower()
    if ext == ".fif":
        return mne.io.read_raw_fif(path, preload=preload, verbose="ERROR")
    if ext == ".vhdr":
        return mne.io.read_raw_brainvision(path, preload=preload, verbose="ERROR")
    if ext == ".edf":
        return mne.io.read_raw_edf(path, preload=preload, verbose="ERROR")
    if ext == ".bdf":
        return mne.io.read_raw_bdf(path, preload=preload, verbose="ERROR")
    raise ValueError(f"Unsupported raw file extension: {path}")


def compare_data(
    label: str,
    reference: np.ndarray,
    server: np.ndarray,
    *,
    ref_ch_names: list[str] | None = None,
    server_ch_names: list[str] | None = None,
    channel_axis: int | None = None,
) -> dict[str, Any]:
    missing_ref: list[str] = []
    missing_server: list[str] = []

    if ref_ch_names is not None and server_ch_names is not None and channel_axis is not None:
        common = [ch for ch in ref_ch_names if ch in set(server_ch_names)]
        missing_ref = [ch for ch in server_ch_names if ch not in set(ref_ch_names)]
        missing_server = [ch for ch in ref_ch_names if ch not in set(server_ch_names)]
        ref_idx = [ref_ch_names.index(ch) for ch in common]
        server_idx = [server_ch_names.index(ch) for ch in common]
        reference = np.take(reference, ref_idx, axis=channel_axis)
        server = np.take(server, server_idx, axis=channel_axis)

    if reference.shape != server.shape:
        raise ValueError(f"{label}: shape mismatch {reference.shape} vs {server.shape}")

    reference = np.asarray(reference, dtype=np.float64)
    server = np.asarray(server, dtype=np.float64)
    error = server - reference

    ref_mean = float(np.mean(reference))
    server_mean = float(np.mean(server))
    error_mean = float(np.mean(error))
    ref_std = float(np.std(reference))
    server_std = float(np.std(server))
    error_std = float(np.std(error))
    rmse = float(np.sqrt(np.mean(error * error)))
    ref_rms = float(np.sqrt(np.mean(reference * reference)))
    rel_rmse = rmse / ref_rms if ref_rms else (0.0 if rmse == 0.0 else math.inf)
    std_ratio = error_std / ref_std if ref_std else (0.0 if error_std == 0.0 else math.inf)

    if error_std == 0.0:
        corr = 1.0
    elif ref_std > 0.0 and server_std > 0.0:
        corr = (float(np.mean(reference * server)) - ref_mean * server_mean) / (ref_std * server_std)
        corr = max(-1.0, min(1.0, corr))
    else:
        corr = math.nan

    if error_std == 0.0 and ref_std > 0.0:
        snr_db = math.inf
    elif error_std > 0.0 and ref_std > 0.0:
        snr_db = 20.0 * math.log10(ref_std / error_std)
    else:
        snr_db = math.nan

    return {
        "label": label,
        "shape": list(server.shape),
        "reference_mean": ref_mean,
        "server_mean": server_mean,
        "error_mean": error_mean,
        "reference_std": ref_std,
        "server_std": server_std,
        "error_std": error_std,
        "error_std_over_reference_std": std_ratio,
        "max_abs_error": float(np.max(np.abs(error))),
        "mean_abs_error": float(np.mean(np.abs(error))),
        "rmse": rmse,
        "relative_rmse": rel_rmse,
        "correlation": corr,
        "snr_db": snr_db,
        # Backward-compatible aliases kept for quick comparison with the first report.
        "max_abs": float(np.max(np.abs(error))),
        "mean_abs": float(np.mean(np.abs(error))),
        "rms": rmse,
        "relative_rms": rel_rmse,
        "missing_in_reference": missing_ref,
        "missing_in_server": missing_server,
    }


def build_events(raw: mne.io.BaseRaw) -> tuple[np.ndarray, dict[str, int]]:
    events, desc_to_code = mne.events_from_annotations(raw, regexp=None, verbose="ERROR")
    code_to_desc = {int(code): str(desc) for desc, code in desc_to_code.items()}
    event_id = {condition: index + 1 for index, condition in enumerate(CONDITIONS)}
    rows: list[list[int]] = []
    for sample, _zero, code in events:
        desc = code_to_desc.get(int(code), "")
        if desc in event_id:
            rows.append([int(sample), 0, event_id[desc]])
    if not rows:
        raise RuntimeError(f"No requested events found: {CONDITIONS}")
    return np.array(rows, dtype=int), event_id


def run(raw_path: Path, report_path: Path) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []

    source = read_raw(raw_path, preload=True)
    server_load = mne.io.read_raw_fif(SERVER / "00_load_raw.fif", preload=True, verbose="ERROR")
    metrics.append(
        compare_data(
            "00 LoadData raw",
            source.get_data(),
            server_load.get_data(),
            ref_ch_names=source.ch_names,
            server_ch_names=server_load.ch_names,
            channel_axis=0,
        )
    )

    nyquist = float(source.info["sfreq"]) / 2.0
    freqs = [50.0 * order for order in range(1, 4) if 50.0 * order < nyquist]
    ref_notch = source.copy().load_data()
    ref_notch.notch_filter(freqs=freqs, method="spectrum_fit", verbose="ERROR")
    server_notch = mne.io.read_raw_fif(SERVER / "01_notch_raw.fif", preload=True, verbose="ERROR")
    metrics.append(
        compare_data(
            "01 Filter notch",
            ref_notch.get_data(),
            server_notch.get_data(),
            ref_ch_names=ref_notch.ch_names,
            server_ch_names=server_notch.ch_names,
            channel_axis=0,
        )
    )

    ref_bandpass = ref_notch.copy().load_data()
    ref_bandpass.filter(l_freq=0.1, h_freq=40.0, phase="zero", fir_design="firwin", verbose="ERROR")
    server_bandpass = mne.io.read_raw_fif(SERVER / "02_bandpass_raw.fif", preload=True, verbose="ERROR")
    metrics.append(
        compare_data(
            "02 Filter bandpass 0.1-40 Hz",
            ref_bandpass.get_data(),
            server_bandpass.get_data(),
            ref_ch_names=ref_bandpass.ch_names,
            server_ch_names=server_bandpass.ch_names,
            channel_axis=0,
        )
    )

    events, event_id = build_events(ref_bandpass)
    ref_epochs = mne.Epochs(
        ref_bandpass,
        events,
        event_id=event_id,
        tmin=-1.0,
        tmax=3.0,
        baseline=None,
        preload=True,
        reject_by_annotation=True,
        verbose="ERROR",
    )
    server_epochs = mne.read_epochs(SERVER / "03_epoch_epo.fif", preload=True, verbose="ERROR")
    metrics.append(
        compare_data(
            "03 Epoch -1..3 s",
            ref_epochs.get_data(copy=False),
            server_epochs.get_data(copy=False),
            ref_ch_names=ref_epochs.ch_names,
            server_ch_names=server_epochs.ch_names,
            channel_axis=1,
        )
    )

    ref_baseline = ref_epochs.copy().apply_baseline((None, 0.0), verbose="ERROR")
    server_baseline = mne.read_epochs(SERVER / "04_baseline_epo.fif", preload=True, verbose="ERROR")
    metrics.append(
        compare_data(
            "04 Baseline start..0 s",
            ref_baseline.get_data(copy=False),
            server_baseline.get_data(copy=False),
            ref_ch_names=ref_baseline.ch_names,
            server_ch_names=server_baseline.ch_names,
            channel_axis=1,
        )
    )

    erp_files = {
        "Stimulus/S  3": SERVER / "05_erp_S3-ave.fif",
        "Stimulus/S  4": SERVER / "06_erp_S4-ave.fif",
        "Stimulus/S  5": SERVER / "07_erp_S5-ave.fif",
    }
    for condition, server_path in erp_files.items():
        target_id = ref_baseline.event_id[condition]
        indices = [i for i, ev in enumerate(ref_baseline.events) if int(ev[2]) == target_id]
        ref_evoked = ref_baseline[indices].average()
        server_evoked = mne.read_evokeds(server_path, verbose="ERROR")[0]
        metrics.append(
            compare_data(
                f"05 ERP Average {condition}",
                ref_evoked.data,
                server_evoked.data,
                ref_ch_names=ref_evoked.ch_names,
                server_ch_names=server_evoked.ch_names,
                channel_axis=0,
            )
        )

    write_report(metrics, raw_path, report_path)
    return metrics


def _uv(value: float) -> float:
    return value * 1_000_000.0


def _fmt(value: float, digits: int = 6) -> str:
    if math.isnan(value):
        return "nan"
    if math.isinf(value):
        return "inf" if value > 0 else "-inf"
    return f"{value:.{digits}e}"


def _verdict(item: dict[str, Any]) -> str:
    ratio = float(item["error_std_over_reference_std"])
    if ratio == 0.0:
        return "完全一致"
    if ratio < 1e-6:
        return "浮点级一致"
    if ratio < 1e-4:
        return "高度一致"
    if ratio < 1e-3:
        return "可接受, 建议抽查边界"
    return "需排查"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
    return value


def write_report(metrics: list[dict[str, Any]], raw_path: Path, report_path: Path) -> None:
    lines = [
        "# test1 MNE 一致性测试报告",
        "",
        f"- 标准答案: MNE 复算结果",
        f"- 原始输入: `{raw_path}`",
        "- 对照产物: `server_outputs/`",
        "- 流水线: LoadData -> Notch 50 Hz -> Bandpass 0.1-40 Hz -> Epoch(-1, 3) -> Baseline(None, 0) -> ERP Average",
        "- 误差定义: `error = web_result - mne_reference`",
        "",
        "## 标准差与准确性指标",
        "",
        "| 节点 | shape | MNE std(uV) | error std(uV) | error/MNE std | max abs err(uV) | mean abs err(uV) | corr | SNR(dB) | 结论 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in metrics:
        lines.append(
            "| {label} | {shape} | {ref_std} | {err_std} | {ratio} | {max_abs} | {mean_abs} | {corr} | {snr} | {verdict} |".format(
                label=item["label"],
                shape="x".join(str(x) for x in item["shape"]),
                ref_std=_fmt(_uv(float(item["reference_std"]))),
                err_std=_fmt(_uv(float(item["error_std"]))),
                ratio=_fmt(float(item["error_std_over_reference_std"])),
                max_abs=_fmt(_uv(float(item["max_abs_error"]))),
                mean_abs=_fmt(_uv(float(item["mean_abs_error"]))),
                corr=_fmt(float(item["correlation"])),
                snr=_fmt(float(item["snr_db"])),
                verdict=_verdict(item),
            )
        )

    lines.extend(
        [
            "",
            "## 旧版误差指标",
            "",
            "| 节点 | max_abs(V) | mean_abs(V) | RMSE(V) | relative_RMSE | bias(web-MNE, uV) | 通道差异 |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for item in metrics:
        missing_server = item["missing_in_server"]
        missing_ref = item["missing_in_reference"]
        if missing_server or missing_ref:
            channel_note = f"server缺{missing_server or '-'}; reference缺{missing_ref or '-'}"
        else:
            channel_note = "-"
        lines.append(
            "| {label} | {max_abs} | {mean_abs} | {rmse} | {rel_rmse} | {bias} | {channel_note} |".format(
                label=item["label"],
                max_abs=_fmt(float(item["max_abs_error"])),
                mean_abs=_fmt(float(item["mean_abs_error"])),
                rmse=_fmt(float(item["rmse"])),
                rel_rmse=_fmt(float(item["relative_rmse"])),
                bias=_fmt(_uv(float(item["error_mean"]))),
                channel_note=channel_note,
            )
        )

    lines.extend(
        [
            "",
            "## 说明",
            "",
            "- `MNE std` 是标准答案自身标准差，用来表示该节点结果的信号量级。",
            "- `error std` 是网页结果相对 MNE 的误差标准差，是本次新增的核心绝对误差指标。",
            "- `error/MNE std` 是标准化误差，适合跨节点比较；本报告用它给出结论。",
            "- `corr` 是按对齐后的全部样本计算的 Pearson 相关系数；越接近 1，波形形状越一致。",
            "- `SNR(dB)=20*log10(MNE std/error std)`；越大说明误差相对信号越小。",
            "- ERP Average 的服务器产物少 `IO` 通道；该通道在 Epoch 中是 `misc`，MNE 平均后不会进入 Evoked。脚本按共同通道对齐后比较。",
            "- 本次使用 execution #2，因为它已完成且只包含本次点名的 sub-007；execution #3 后来也已完成，但 v4 同时选中了 sub-008，范围不同。",
            "",
            "## 原始指标 JSON",
            "",
            "```json",
            json.dumps(_json_safe(metrics), ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--raw",
        type=Path,
        default=SERVER / "00_load_raw.fif",
        help="Local original raw file. Defaults to the downloaded server LoadData FIF.",
    )
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    run(args.raw, args.report)


if __name__ == "__main__":
    main()
