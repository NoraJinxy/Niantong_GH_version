"""Compare the ELYS Filter node output with direct MNE filtering."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import mne  # noqa: E402
import numpy as np  # noqa: E402


HERE = Path(__file__).resolve().parent
SERVER_DIR = HERE / "server_outputs"
FIG_DIR = HERE / "figures"
META_DIR = HERE / "metadata"
RAW_PATH = SERVER_DIR / "sub-009_ses-a_task-sensory_run-04_eeg.fif"
SERVER_FILTERED_PATH = SERVER_DIR / "sub-009_ses-a_task-sensory_run-04_Filter_0p5_40Hz-raw.fif"
METRICS_PATH = META_DIR / "comparison_metrics.json"
REPORT_PATH = HERE / "TEST_REPORT.md"


def _pick_channels(common: list[str]) -> list[str]:
    preferred = ["Fp1", "Cz", "Oz"]
    picked = [ch for ch in preferred if ch in common]
    for ch in common:
        if len(picked) >= 3:
            break
        if ch not in picked:
            picked.append(ch)
    return picked


def _load_pair() -> tuple[mne.io.BaseRaw, mne.io.BaseRaw]:
    if not RAW_PATH.exists():
        raise FileNotFoundError(f"Missing raw FIF: {RAW_PATH}")
    if not SERVER_FILTERED_PATH.exists():
        raise FileNotFoundError(f"Missing server filtered FIF: {SERVER_FILTERED_PATH}")

    raw = mne.io.read_raw_fif(RAW_PATH, preload=True, verbose="ERROR")
    mne_filtered = raw.copy().load_data()
    mne_filtered.filter(
        l_freq=0.5,
        h_freq=40.0,
        method="fir",
        phase="zero",
        fir_design="firwin",
        verbose="ERROR",
    )
    server_filtered = mne.io.read_raw_fif(SERVER_FILTERED_PATH, preload=True, verbose="ERROR")
    return mne_filtered, server_filtered


def _align_data(mne_filtered: mne.io.BaseRaw, server_filtered: mne.io.BaseRaw):
    common = [ch for ch in mne_filtered.ch_names if ch in server_filtered.ch_names]
    if not common:
        raise RuntimeError("No common channels between MNE and server output.")

    mne_aligned = mne_filtered.copy().pick(common)
    server_aligned = server_filtered.copy().pick(common)
    n_times = min(mne_aligned.n_times, server_aligned.n_times)
    sfreq = float(mne_aligned.info["sfreq"])
    if abs(float(server_aligned.info["sfreq"]) - sfreq) > 1e-9:
        raise RuntimeError(
            f"Sampling rate mismatch: MNE={sfreq}, server={float(server_aligned.info['sfreq'])}"
        )
    mne_data = mne_aligned.get_data()[:, :n_times]
    server_data = server_aligned.get_data()[:, :n_times]
    return common, sfreq, mne_data, server_data


def _metric_dict(common: list[str], sfreq: float, mne_data: np.ndarray, server_data: np.ndarray) -> dict:
    diff = server_data - mne_data
    mne_std_by_channel = mne_data.std(axis=1, ddof=0)
    diff_std_by_channel = diff.std(axis=1, ddof=0)
    rms_by_channel = np.sqrt(np.mean(diff**2, axis=1))
    denom = np.linalg.norm(mne_data)
    rel_l2 = float(np.linalg.norm(diff) / denom) if denom else float("nan")
    rows = []
    for idx, channel in enumerate(common):
        x = mne_data[idx]
        y = server_data[idx]
        if np.std(x) == 0 or np.std(y) == 0:
            corr = float("nan")
        else:
            corr = float(np.corrcoef(x, y)[0, 1])
        rows.append(
            {
                "channel": channel,
                "mne_std_v": float(mne_std_by_channel[idx]),
                "diff_mean_v": float(diff[idx].mean()),
                "diff_std_v": float(diff_std_by_channel[idx]),
                "diff_rmse_v": float(rms_by_channel[idx]),
                "diff_max_abs_v": float(np.max(np.abs(diff[idx]))),
                "diff_std_over_mne_std": float(diff_std_by_channel[idx] / mne_std_by_channel[idx])
                if mne_std_by_channel[idx]
                else float("nan"),
                "corr": corr,
            }
        )
    return {
        "raw_path": str(RAW_PATH),
        "server_filtered_path": str(SERVER_FILTERED_PATH),
        "mne_filter_params": {
            "l_freq": 0.5,
            "h_freq": 40.0,
            "method": "fir",
            "phase": "zero",
            "fir_design": "firwin",
        },
        "sfreq": sfreq,
        "n_channels": len(common),
        "n_times": int(mne_data.shape[1]),
        "duration_sec": float(mne_data.shape[1] / sfreq),
        "global": {
            "mne_std_v": float(np.std(mne_data, ddof=0)),
            "diff_mean_v": float(np.mean(diff)),
            "diff_std_v": float(np.std(diff, ddof=0)),
            "diff_rmse_v": float(np.sqrt(np.mean(diff**2))),
            "diff_max_abs_v": float(np.max(np.abs(diff))),
            "diff_std_over_mne_std": float(np.std(diff, ddof=0) / np.std(mne_data, ddof=0)),
            "relative_l2": rel_l2,
        },
        "channels": rows,
    }


def _plot_overlay(channels: list[str], sfreq: float, mne_data: np.ndarray, server_data: np.ndarray, common: list[str]) -> Path:
    start_sec = 10.0
    duration_sec = 5.0
    start = int(start_sec * sfreq)
    stop = min(mne_data.shape[1], int((start_sec + duration_sec) * sfreq))
    if stop <= start:
        start = 0
        stop = min(mne_data.shape[1], int(duration_sec * sfreq))
    times = np.arange(start, stop) / sfreq

    fig, axes = plt.subplots(len(channels), 1, figsize=(12, 2.6 * len(channels)), sharex=True)
    axes = np.atleast_1d(axes)
    for ax, channel in zip(axes, channels):
        idx = common.index(channel)
        ax.plot(times, mne_data[idx, start:stop] * 1e6, label="MNE", linewidth=1.0)
        ax.plot(times, server_data[idx, start:stop] * 1e6, label="ELYS Filter", linewidth=0.9, alpha=0.75)
        ax.set_ylabel(f"{channel}\n(uV)")
        ax.grid(True, alpha=0.25)
    axes[0].legend(loc="upper right")
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle("MNE vs ELYS Filter Output")
    fig.tight_layout()
    out = FIG_DIR / "mne_vs_elys_overlay.png"
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def _plot_difference(channels: list[str], sfreq: float, mne_data: np.ndarray, server_data: np.ndarray, common: list[str]) -> Path:
    diff = server_data - mne_data
    start_sec = 10.0
    duration_sec = 5.0
    start = int(start_sec * sfreq)
    stop = min(diff.shape[1], int((start_sec + duration_sec) * sfreq))
    if stop <= start:
        start = 0
        stop = min(diff.shape[1], int(duration_sec * sfreq))
    times = np.arange(start, stop) / sfreq

    fig, axes = plt.subplots(len(channels), 1, figsize=(12, 2.4 * len(channels)), sharex=True)
    axes = np.atleast_1d(axes)
    for ax, channel in zip(axes, channels):
        idx = common.index(channel)
        ax.plot(times, diff[idx, start:stop] * 1e6, color="#b42318", linewidth=0.9)
        ax.axhline(0, color="#333333", linewidth=0.7, alpha=0.5)
        ax.set_ylabel(f"{channel}\n(uV)")
        ax.grid(True, alpha=0.25)
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle("Difference Signal: ELYS - MNE")
    fig.tight_layout()
    out = FIG_DIR / "elys_minus_mne_difference.png"
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def _fmt_uv(value_v: float) -> str:
    return f"{value_v * 1e6:.6g}"


def _write_report(metrics: dict, overlay: Path, difference: Path) -> None:
    rows = sorted(metrics["channels"], key=lambda row: row["diff_rmse_v"], reverse=True)
    top_rows = rows[:10]
    global_metrics = metrics["global"]
    lines = [
        "# sub-009 0.5-40Hz Filter 节点一致性测试",
        "",
        "## 测试设置",
        "",
        f"- 原始输入: `{RAW_PATH.name}`",
        f"- 服务器 Filter 输出: `{SERVER_FILTERED_PATH.name}`",
        "- 服务器节点: ELYS `eeg/filter/apply`, `filter_type=bandpass`, `method=fir`, `phase=zero`",
        "- 本地 MNE 标准: `mne.io.read_raw_fif(...).filter(l_freq=0.5, h_freq=40.0, method='fir', phase='zero', fir_design='firwin')`",
        f"- 对比范围: {metrics['n_channels']} 通道 x {metrics['n_times']} 采样点, {metrics['duration_sec']:.2f} s @ {metrics['sfreq']:.1f} Hz",
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
        f"| 差值标准差 / MNE 标准差 | {global_metrics['diff_std_over_mne_std']:.6g} | ratio |",
        f"| 相对 L2 误差 | {global_metrics['relative_l2']:.6g} | ratio |",
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
            "| {channel} | {mne_std} | {diff_std} | {rmse} | {max_abs} | {ratio:.6g} | {corr:.9f} |".format(
                channel=row["channel"],
                mne_std=_fmt_uv(row["mne_std_v"]),
                diff_std=_fmt_uv(row["diff_std_v"]),
                rmse=_fmt_uv(row["diff_rmse_v"]),
                max_abs=_fmt_uv(row["diff_max_abs_v"]),
                ratio=row["diff_std_over_mne_std"],
                corr=row["corr"],
            )
        )
    lines.extend(
        [
            "",
            "## 图",
            "",
            f"![MNE 与 ELYS 叠加对比]({overlay.relative_to(HERE).as_posix()})",
            "",
            f"![差值信号 ELYS - MNE]({difference.relative_to(HERE).as_posix()})",
            "",
            "## 说明",
            "",
            "- 所有指标都基于完整对齐后的信号计算。",
            "- 为了便于观察，图中只显示从 10 s 开始的 5 s 片段。",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    META_DIR.mkdir(parents=True, exist_ok=True)
    mne_filtered, server_filtered = _load_pair()
    common, sfreq, mne_data, server_data = _align_data(mne_filtered, server_filtered)
    metrics = _metric_dict(common, sfreq, mne_data, server_data)
    channels = _pick_channels(common)
    overlay = _plot_overlay(channels, sfreq, mne_data, server_data, common)
    difference = _plot_difference(channels, sfreq, mne_data, server_data, common)
    METRICS_PATH.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(metrics, overlay, difference)
    print(json.dumps({"metrics_path": str(METRICS_PATH), "report_path": str(REPORT_PATH)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
