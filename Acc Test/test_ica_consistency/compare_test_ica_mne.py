"""Reproduce the remote "test ICA" pipeline with MNE and compare outputs."""

from __future__ import annotations

import gc
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import mne  # noqa: E402
import numpy as np  # noqa: E402
from scipy.optimize import linear_sum_assignment  # noqa: E402


HERE = Path(__file__).resolve().parent
SERVER_DIR = HERE / "server_outputs"
META_DIR = HERE / "metadata"
FIG_DIR = HERE / "figures"
LOCAL_DIR = HERE / "local_outputs"
REPORT_PATH = HERE / "TEST_ICA_REPORT.md"
METRICS_PATH = META_DIR / "ica_consistency_metrics.json"
MANIFEST_PATH = META_DIR / "test_ica_manifest.json"

COMPONENTS_PER_SHEET = 8
PREFERRED_CHANNELS = ["Fp1", "Cz", "Oz"]


def read_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"Missing manifest: {MANIFEST_PATH}. Run download_test_ica_outputs.py first.")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def parse_components(value: Any, default: int | float | None = None) -> int | float | None:
    if value in (None, "", "null"):
        return default
    if isinstance(value, float) and 0 < value < 1:
        return value
    return int(value)


def resolve_decim(value: Any, raw: mne.io.BaseRaw, n_channels: int) -> int | None:
    sfreq = float(raw.info["sfreq"])
    n_times = int(raw.n_times)
    if value in (None, "", "auto", "null"):
        decim = max(1, round(sfreq / 125.0))
    else:
        decim = max(1, int(value))
    if decim <= 1:
        return None
    min_samples = 25 * n_channels * n_channels
    while decim > 1 and (n_times // decim) < min_samples:
        decim -= 1
    return decim if decim > 1 else None


def apply_fit_highpass(raw: mne.io.BaseRaw, value: Any) -> mne.io.BaseRaw:
    if value in (None, ""):
        fit_hp = 1.0
    else:
        try:
            fit_hp = float(value)
        except (TypeError, ValueError):
            fit_hp = 1.0
    if fit_hp <= 0:
        return raw
    current_hp = float(raw.info.get("highpass") or 0.0)
    if current_hp >= fit_hp:
        return raw
    return raw.copy().load_data().filter(l_freq=fit_hp, h_freq=None, verbose="ERROR")


def build_local_preprocessed(raw: mne.io.BaseRaw, params: dict[str, Any]) -> mne.io.BaseRaw:
    resample_params = params.get("n_mr4bc24t_2") or {}
    notch_params = params.get("n_mr4bc2t4_3") or {}
    bandpass_params = params.get("n_mr4bc3xx_4") or {}

    sfreq = float(resample_params.get("sfreq") or 250.0)
    notch_freq = float(notch_params.get("notch_freq") or 50.0)
    harmonics = int(notch_params.get("notch_harmonics") or 3)
    notch_method = str(notch_params.get("notch_method") or "spectrum_fit")
    l_freq = float(bandpass_params.get("l_freq") or 0.1)
    h_freq = float(bandpass_params.get("h_freq") or 40.0)
    method = str(bandpass_params.get("method") or "fir")
    phase = str(bandpass_params.get("phase") or "zero")

    local = raw.copy().load_data()
    local.resample(sfreq=sfreq, npad="auto", verbose="ERROR")
    nyquist = float(local.info["sfreq"]) / 2.0
    notch_freqs = [notch_freq * order for order in range(1, harmonics + 1) if notch_freq * order < nyquist]
    local.notch_filter(freqs=notch_freqs, method=notch_method, verbose="ERROR")
    local.filter(
        l_freq=l_freq,
        h_freq=h_freq,
        method=method,
        phase=phase,
        fir_design="firwin",
        verbose="ERROR",
    )
    return local


def compute_local_ica(raw: mne.io.BaseRaw, params: dict[str, Any]) -> tuple[mne.preprocessing.ICA, dict[str, Any]]:
    ica_params = params.get("n_mr4borp0_1") or {}
    n_components = parse_components(ica_params.get("n_components"), default=None)
    method = str(ica_params.get("method") or "picard")
    random_state = ica_params.get("random_state", 42)
    if isinstance(random_state, str) and random_state.strip():
        random_state = int(random_state)
    picks = mne.pick_types(raw.info, meg=True, eeg=True, eog=False, ecg=False, stim=False, exclude="bads")
    decim = resolve_decim(ica_params.get("decim"), raw, len(picks))
    fit_params = {"ortho": False, "extended": True} if method == "picard" else None
    fit_raw = apply_fit_highpass(raw, ica_params.get("fit_highpass"))
    ica = mne.preprocessing.ICA(
        n_components=n_components,
        method=method,
        random_state=random_state,
        max_iter="auto",
        fit_params=fit_params,
    )
    ica.fit(fit_raw, picks=picks, decim=decim, verbose="ERROR")
    fit_info = {
        "n_components": n_components,
        "method": method,
        "random_state": random_state,
        "decim": decim,
        "fit_highpass": ica_params.get("fit_highpass", 1.0),
        "picked_channels": int(len(picks)),
    }
    return ica, fit_info


def pick_common_raw(mne_raw: mne.io.BaseRaw, server_raw: mne.io.BaseRaw) -> tuple[list[str], np.ndarray, np.ndarray, float]:
    common = [ch for ch in mne_raw.ch_names if ch in server_raw.ch_names]
    if not common:
        raise RuntimeError("No common channels found.")
    local = mne_raw.copy().pick(common)
    server = server_raw.copy().pick(common)
    sfreq = float(local.info["sfreq"])
    if abs(float(server.info["sfreq"]) - sfreq) > 1e-9:
        raise RuntimeError(f"Sampling rate mismatch: local={sfreq}, server={float(server.info['sfreq'])}.")
    n_times = min(local.n_times, server.n_times)
    return common, local.get_data()[:, :n_times], server.get_data()[:, :n_times], sfreq


def raw_metrics(local_raw: mne.io.BaseRaw, server_raw: mne.io.BaseRaw, label: str) -> dict[str, Any]:
    common, local_data, server_data, sfreq = pick_common_raw(local_raw, server_raw)
    diff = server_data - local_data
    local_std = float(np.std(local_data, ddof=0))
    diff_std = float(np.std(diff, ddof=0))
    denom = float(np.linalg.norm(local_data))
    channel_rows = []
    for idx, channel in enumerate(common):
        x = local_data[idx]
        y = server_data[idx]
        x_std = float(np.std(x, ddof=0))
        y_std = float(np.std(y, ddof=0))
        corr = float(np.corrcoef(x, y)[0, 1]) if x_std > 0 and y_std > 0 else float("nan")
        channel_diff = diff[idx]
        channel_rows.append(
            {
                "channel": channel,
                "local_std_v": x_std,
                "diff_mean_v": float(np.mean(channel_diff)),
                "diff_std_v": float(np.std(channel_diff, ddof=0)),
                "diff_rmse_v": float(np.sqrt(np.mean(channel_diff**2))),
                "diff_max_abs_v": float(np.max(np.abs(channel_diff))),
                "diff_std_over_local_std": float(np.std(channel_diff, ddof=0) / x_std) if x_std else float("nan"),
                "corr": corr,
            }
        )
    return {
        "label": label,
        "n_channels": len(common),
        "n_times": int(local_data.shape[1]),
        "sfreq": sfreq,
        "duration_sec": float(local_data.shape[1] / sfreq),
        "global": {
            "local_std_v": local_std,
            "server_std_v": float(np.std(server_data, ddof=0)),
            "diff_mean_v": float(np.mean(diff)),
            "diff_std_v": diff_std,
            "diff_rmse_v": float(np.sqrt(np.mean(diff**2))),
            "diff_max_abs_v": float(np.max(np.abs(diff))),
            "diff_std_over_local_std": float(diff_std / local_std) if local_std else float("nan"),
            "relative_l2": float(np.linalg.norm(diff) / denom) if denom else float("nan"),
        },
        "channels": sorted(channel_rows, key=lambda row: row["diff_rmse_v"], reverse=True),
    }


def channel_indices(names: list[str], common: list[str]) -> list[int]:
    lookup = {name: idx for idx, name in enumerate(names)}
    return [lookup[name] for name in common]


def pearson(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    x_std = float(np.std(x))
    y_std = float(np.std(y))
    if x_std == 0.0 or y_std == 0.0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def ica_component_metrics(
    server_ica: mne.preprocessing.ICA,
    local_ica: mne.preprocessing.ICA,
) -> tuple[dict[str, Any], dict[str, Any]]:
    server_names = list(server_ica.info["ch_names"])
    local_names = list(local_ica.info["ch_names"])
    common = [ch for ch in server_names if ch in local_names]
    if not common:
        raise RuntimeError("No common ICA channels found.")

    server_components = np.asarray(server_ica.get_components())
    local_components = np.asarray(local_ica.get_components())
    server_matrix = server_components[channel_indices(server_names, common), :]
    local_matrix = local_components[channel_indices(local_names, common), :]
    n_server = int(server_matrix.shape[1])
    n_local = int(local_matrix.shape[1])
    n_compare = min(n_server, n_local)

    corr_abs = np.zeros((n_server, n_local), dtype=float)
    corr_signed = np.zeros((n_server, n_local), dtype=float)
    for i in range(n_server):
        for j in range(n_local):
            corr = pearson(server_matrix[:, i], local_matrix[:, j])
            corr_signed[i, j] = corr
            corr_abs[i, j] = abs(corr) if not math.isnan(corr) else 0.0

    rows_idx, cols_idx = linear_sum_assignment(-corr_abs)
    best_map = {int(row): int(col) for row, col in zip(rows_idx, cols_idx)}

    rows = []
    signs = []
    same_abs_values = []
    best_abs_values = []
    aligned_local = np.zeros_like(server_matrix[:, :n_compare])
    diff_matrix = np.zeros_like(server_matrix[:, :n_compare])
    for index in range(n_compare):
        same_corr = corr_signed[index, index]
        sign = -1 if same_corr < 0 else 1
        signs.append(sign)
        aligned = local_matrix[:, index] * sign
        diff = server_matrix[:, index] - aligned
        aligned_local[:, index] = aligned
        diff_matrix[:, index] = diff
        same_abs = abs(same_corr) if not math.isnan(same_corr) else float("nan")
        best_j = best_map.get(index)
        best_corr = corr_signed[index, best_j] if best_j is not None else float("nan")
        best_abs = abs(best_corr) if not math.isnan(best_corr) else float("nan")
        same_abs_values.append(same_abs)
        best_abs_values.append(best_abs)
        denom = float(np.std(server_matrix[:, index], ddof=0))
        diff_std = float(np.std(diff, ddof=0))
        rows.append(
            {
                "component": index,
                "same_index_corr": float(same_corr),
                "same_index_abs_corr": float(same_abs),
                "same_index_sign": int(sign),
                "best_local_component": int(best_j) if best_j is not None else None,
                "best_match_corr": float(best_corr),
                "best_match_abs_corr": float(best_abs),
                "topomap_diff_mean": float(np.mean(diff)),
                "topomap_diff_std": diff_std,
                "topomap_diff_rmse": float(np.sqrt(np.mean(diff**2))),
                "topomap_diff_std_over_server_std": float(diff_std / denom) if denom else float("nan"),
            }
        )

    same_arr = np.asarray(same_abs_values, dtype=float)
    best_arr = np.asarray(best_abs_values, dtype=float)
    metrics = {
        "n_server_components": n_server,
        "n_local_components": n_local,
        "n_compared": n_compare,
        "n_common_channels": len(common),
        "common_channels": common,
        "summary": {
            "same_index_abs_corr_mean": float(np.nanmean(same_arr)),
            "same_index_abs_corr_min": float(np.nanmin(same_arr)),
            "same_index_abs_corr_median": float(np.nanmedian(same_arr)),
            "best_match_abs_corr_mean": float(np.nanmean(best_arr)),
            "best_match_abs_corr_min": float(np.nanmin(best_arr)),
            "best_match_abs_corr_median": float(np.nanmedian(best_arr)),
            "same_index_sign_flips": int(sum(1 for sign in signs if sign < 0)),
        },
        "components": rows,
    }
    matrices = {
        "server": server_matrix[:, :n_compare],
        "local_aligned": aligned_local,
        "diff": diff_matrix,
        "common_channels": common,
        "server_info": mne.pick_info(
            server_ica.info.copy(),
            channel_indices(server_names, common),
            copy=True,
        ),
    }
    return metrics, matrices


def plot_topomap_sheet(
    subject: str,
    start_component: int,
    component_metrics: list[dict[str, Any]],
    matrices: dict[str, Any],
) -> Path:
    stop_component = min(start_component + COMPONENTS_PER_SHEET, len(component_metrics))
    components = list(range(start_component, stop_component))
    fig, axes = plt.subplots(len(components), 3, figsize=(10.0, 2.25 * len(components)))
    axes = np.atleast_2d(axes)
    info = matrices["server_info"]
    for row_idx, component in enumerate(components):
        server_values = matrices["server"][:, component]
        local_values = matrices["local_aligned"][:, component]
        diff_values = matrices["diff"][:, component]
        row = component_metrics[component]
        scale = max(float(np.max(np.abs(server_values))), float(np.max(np.abs(local_values))), 1e-12)
        diff_scale = max(float(np.max(np.abs(diff_values))), 1e-12)
        for col_idx, (values, title, vlim) in enumerate(
            [
                (server_values, f"Page IC{component:03d}", (-scale, scale)),
                (local_values, "MNE code aligned", (-scale, scale)),
                (diff_values, "Page - MNE", (-diff_scale, diff_scale)),
            ]
        ):
            ax = axes[row_idx, col_idx]
            mne.viz.plot_topomap(
                values,
                info,
                axes=ax,
                show=False,
                contours=0,
                sensors=False,
                cmap="RdBu_r",
                vlim=vlim,
            )
            if row_idx == 0:
                ax.set_title(title, fontsize=10)
        axes[row_idx, 0].set_ylabel(
            f"IC{component:03d}\nr={row['same_index_corr']:.4f}",
            rotation=0,
            labelpad=36,
            va="center",
            fontsize=8,
        )
    fig.suptitle(f"{subject} ICA topomaps: page vs MNE code", fontsize=12)
    fig.tight_layout()
    out = FIG_DIR / subject / f"{subject}_ica_topomaps_{start_component:02d}_{stop_component - 1:02d}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=170)
    plt.close(fig)
    return out


def choose_channels(common: list[str]) -> list[str]:
    picked = [channel for channel in PREFERRED_CHANNELS if channel in common]
    for channel in common:
        if len(picked) >= 3:
            break
        if channel not in picked:
            picked.append(channel)
    return picked


def plot_cleaned_signals(subject: str, local_clean: mne.io.BaseRaw, server_clean: mne.io.BaseRaw) -> dict[str, str]:
    common, local_data, server_data, sfreq = pick_common_raw(local_clean, server_clean)
    channels = choose_channels(common)
    start_sec = 10.0
    duration_sec = 5.0
    start = int(start_sec * sfreq)
    stop = min(local_data.shape[1], int((start_sec + duration_sec) * sfreq))
    if stop <= start:
        start = 0
        stop = min(local_data.shape[1], int(duration_sec * sfreq))
    times = np.arange(start, stop) / sfreq

    subject_dir = FIG_DIR / subject
    subject_dir.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(len(channels), 1, figsize=(12, 2.7 * len(channels)), sharex=True)
    axes = np.atleast_1d(axes)
    for ax, channel in zip(axes, channels):
        idx = common.index(channel)
        ax.plot(times, server_data[idx, start:stop] * 1e6, label="Page cleaned", linewidth=1.0)
        ax.plot(times, local_data[idx, start:stop] * 1e6, label="MNE code cleaned", linewidth=0.9, alpha=0.75)
        ax.set_ylabel(f"{channel}\n(uV)")
        ax.grid(True, alpha=0.25)
    axes[0].legend(loc="upper right")
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle(f"{subject} cleaned signal overlay")
    fig.tight_layout()
    overlay = subject_dir / f"{subject}_cleaned_overlay.png"
    fig.savefig(overlay, dpi=170)
    plt.close(fig)

    diff = server_data - local_data
    fig, axes = plt.subplots(len(channels), 1, figsize=(12, 2.5 * len(channels)), sharex=True)
    axes = np.atleast_1d(axes)
    for ax, channel in zip(axes, channels):
        idx = common.index(channel)
        ax.plot(times, diff[idx, start:stop] * 1e6, color="#b42318", linewidth=0.9)
        ax.axhline(0, color="#333333", linewidth=0.7, alpha=0.5)
        ax.set_ylabel(f"{channel}\n(uV)")
        ax.grid(True, alpha=0.25)
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle(f"{subject} cleaned difference: page - MNE code")
    fig.tight_layout()
    difference = subject_dir / f"{subject}_cleaned_difference.png"
    fig.savefig(difference, dpi=170)
    plt.close(fig)
    return {"overlay": str(overlay), "difference": str(difference)}


def fmt_uv(value_v: float) -> str:
    return f"{value_v * 1e6:.6g}"


def fmt_ratio(value: float) -> str:
    if value is None or math.isnan(float(value)):
        return "nan"
    return f"{float(value):.6g}"


def rel(path: str | Path) -> str:
    return Path(path).relative_to(HERE).as_posix()


def consistency_label(subject_result: dict[str, Any]) -> str:
    topo = subject_result["ica_components"]["summary"]
    cleaned = subject_result["signal_metrics"]["local_clean_vs_page"]["global"]
    same_mean = topo["same_index_abs_corr_mean"]
    clean_ratio = cleaned["diff_std_over_local_std"]
    if same_mean >= 0.999 and clean_ratio <= 1e-5:
        return "一致"
    if topo["best_match_abs_corr_mean"] >= 0.99 and same_mean < 0.99:
        return "成分可能重排"
    return "不一致/需排查"


def write_report(manifest: dict[str, Any], results: dict[str, Any]) -> None:
    params = manifest.get("node_params") or {}
    ica_params = params.get("n_mr4borp0_1") or {}
    notch_params = params.get("n_mr4bc2t4_3") or {}
    bandpass_params = params.get("n_mr4bc3xx_4") or {}
    resample_params = params.get("n_mr4bc24t_2") or {}
    decisions = manifest.get("apply_decisions_by_subject") or {}
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# test ICA 流水线一致性测试报告",
        "",
        "## 测试对象",
        "",
        f"- 远端流水线: `{manifest.get('pipeline_name')}`",
        f"- Pipeline ID: `{manifest.get('pipeline', {}).get('id')}`",
        f"- Execution ID: `{manifest.get('run_id')}`",
        f"- Pipeline version: `{manifest.get('run', {}).get('pipeline_version')}`",
        f"- 生成时间: `{generated}`",
        "",
        "## 本地 MNE 复现流程",
        "",
        f"- Resample: `sfreq={resample_params.get('sfreq', 250)}`",
        f"- Notch: `notch_freq={notch_params.get('notch_freq', 50)}`, `harmonics={notch_params.get('notch_harmonics', 3)}`, `method={notch_params.get('notch_method', 'spectrum_fit')}`；250 Hz 数据实际去除 50 Hz 与 100 Hz。",
        f"- Bandpass: `l_freq={bandpass_params.get('l_freq', 0.1)}`, `h_freq={bandpass_params.get('h_freq', 40)}`, `method={bandpass_params.get('method', 'fir')}`, `phase={bandpass_params.get('phase', 'zero')}`。",
        f"- Compute ICA: `method={ica_params.get('method')}`, `n_components={ica_params.get('n_components')}`, `random_state={ica_params.get('random_state')}`, `fit_highpass={ica_params.get('fit_highpass')}`, `max_iter='auto'`。",
        f"- Apply ICA: 按远端交互决策剔除成分，当前记录为 `{decisions}`。",
        "",
        "说明: ICA 地形图比较时对本地成分做了符号对齐，因为 ICA 成分整体正负号翻转不改变分解含义；清洗信号比较使用未人为改动符号的 MNE ICA 对象直接 apply。",
        "",
        "## 总览指标",
        "",
        "| Subject | 预处理差异SD (uV) | 预处理相对L2 | 同编号topomap平均|r| | 同编号最小|r| | 最佳匹配平均|r| | Apply重放差异SD (uV) | 完整本地清洗差异SD (uV) | 清洗差异/信号SD | 结论 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for subject, result in sorted(results.items()):
        pre = result["signal_metrics"]["preprocessed_vs_page"]["global"]
        replay = result["signal_metrics"]["server_ica_replay_vs_page"]["global"]
        clean = result["signal_metrics"]["local_clean_vs_page"]["global"]
        topo = result["ica_components"]["summary"]
        lines.append(
            "| {subject} | {pre_std} | {pre_l2} | {same_mean:.6f} | {same_min:.6f} | {best_mean:.6f} | {replay_std} | {clean_std} | {clean_ratio} | {label} |".format(
                subject=subject,
                pre_std=fmt_uv(pre["diff_std_v"]),
                pre_l2=fmt_ratio(pre["relative_l2"]),
                same_mean=topo["same_index_abs_corr_mean"],
                same_min=topo["same_index_abs_corr_min"],
                best_mean=topo["best_match_abs_corr_mean"],
                replay_std=fmt_uv(replay["diff_std_v"]),
                clean_std=fmt_uv(clean["diff_std_v"]),
                clean_ratio=fmt_ratio(clean["diff_std_over_local_std"]),
                label=consistency_label(result),
            )
        )

    lines.extend(
        [
            "",
            "## 各被试成分与图",
            "",
        ]
    )
    for subject, result in sorted(results.items()):
        excluded = decisions.get(subject, result.get("excluded_components", []))
        topo = result["ica_components"]["summary"]
        lines.extend(
            [
                f"### {subject}",
                "",
                f"- 剔除成分: `{excluded}`",
                f"- 同编号成分平均 |r|: `{topo['same_index_abs_corr_mean']:.6f}`；最小 |r|: `{topo['same_index_abs_corr_min']:.6f}`；符号翻转数: `{topo['same_index_sign_flips']}`。",
                f"- 最佳匹配平均 |r|: `{topo['best_match_abs_corr_mean']:.6f}`；如果它明显高于同编号结果，说明主要差异可能是 ICA 成分顺序变化。",
                "",
                "| IC | 同编号 r | 同编号 |r| | 符号 | 最佳本地IC | 最佳 |r| | 地形图RMSE |",
                "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in result["ica_components"]["components"]:
            lines.append(
                f"| IC{row['component']:03d} | {row['same_index_corr']:.6f} | {row['same_index_abs_corr']:.6f} | {row['same_index_sign']} | IC{row['best_local_component']:03d} | {row['best_match_abs_corr']:.6f} | {row['topomap_diff_rmse']:.6g} |"
            )
        lines.extend(["", "#### Topomap 对比", ""])
        for path in result["figures"]["topomap_sheets"]:
            lines.extend([f"![{subject} topomap sheet]({rel(path)})", ""])
        lines.extend(
            [
                "#### 去除成分后的信号对比",
                "",
                f"![{subject} cleaned overlay]({rel(result['figures']['cleaned']['overlay'])})",
                "",
                f"![{subject} cleaned difference]({rel(result['figures']['cleaned']['difference'])})",
                "",
            ]
        )

    lines.extend(
        [
            "## 判读口径",
            "",
            "- `预处理差异` 比较本地 MNE 从原始 FIF 复现到 bandpass 后的结果与页面 bandpass 输出。",
            "- `Apply重放差异` 使用页面保存的 ICA 矩阵在本地重新 apply，验证 Apply ICA 节点本身是否可复现。",
            "- `完整本地清洗差异` 使用本地 MNE 重新计算 ICA 后剔除同样成分，再与页面清洗输出比较，是本次 ICA 一致性的核心指标。",
            "- ICA 符号翻转属于等价解；同编号相关很低但最佳匹配相关很高时，通常表示成分顺序变化。",
            "",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def required_paths_for_subject(manifest: dict[str, Any], subject: str) -> dict[str, Path]:
    raw_path = Path(manifest["raw_input_paths"][subject])
    outputs = manifest["output_paths"][subject]
    paths = {
        "raw": raw_path,
        "bandpass": Path(outputs["03_bandpass_0p1_40"]),
        "ica": Path(outputs["04_compute_ica"]),
        "clean": Path(outputs["05_apply_ica_clean"]),
    }
    for label, path in paths.items():
        if not path.exists():
            raise FileNotFoundError(f"Missing {label} path for {subject}: {path}")
    return paths


def process_subject(subject: str, manifest: dict[str, Any]) -> dict[str, Any]:
    print(f"[{subject}] loading server and raw files", flush=True)
    paths = required_paths_for_subject(manifest, subject)
    params = manifest.get("node_params") or {}
    excluded = (manifest.get("apply_decisions_by_subject") or {}).get(subject, [0, 1])

    raw = mne.io.read_raw_fif(paths["raw"], preload=True, verbose="ERROR")
    server_bandpass = mne.io.read_raw_fif(paths["bandpass"], preload=True, verbose="ERROR")
    server_ica = mne.preprocessing.read_ica(paths["ica"], verbose="ERROR")
    server_clean = mne.io.read_raw_fif(paths["clean"], preload=True, verbose="ERROR")

    print(f"[{subject}] reproducing preprocessing", flush=True)
    local_preprocessed = build_local_preprocessed(raw, params)
    pre_metrics = raw_metrics(local_preprocessed, server_bandpass, "preprocessed_vs_page")

    print(f"[{subject}] fitting local ICA", flush=True)
    local_ica, fit_info = compute_local_ica(local_preprocessed, params)
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    local_ica_path = LOCAL_DIR / f"{subject}_mne_ica-ica.fif"
    local_ica.save(local_ica_path, overwrite=True, verbose="ERROR")

    print(f"[{subject}] applying local ICA with excluded={excluded}", flush=True)
    local_clean = local_preprocessed.copy()
    local_ica.apply(local_clean, exclude=[int(item) for item in excluded], verbose="ERROR")
    local_clean_path = LOCAL_DIR / f"{subject}_mne_clean-raw.fif"
    local_clean.save(local_clean_path, overwrite=True, verbose="ERROR")
    clean_metrics = raw_metrics(local_clean, server_clean, "local_clean_vs_page")

    print(f"[{subject}] replaying page ICA apply locally", flush=True)
    replay_clean = server_bandpass.copy()
    server_ica.apply(replay_clean, exclude=[int(item) for item in excluded], verbose="ERROR")
    replay_metrics = raw_metrics(replay_clean, server_clean, "server_ica_replay_vs_page")

    print(f"[{subject}] comparing ICA topomaps", flush=True)
    component_metrics, matrices = ica_component_metrics(server_ica, local_ica)
    topomap_sheets = []
    for start in range(0, component_metrics["n_compared"], COMPONENTS_PER_SHEET):
        topomap_sheets.append(str(plot_topomap_sheet(subject, start, component_metrics["components"], matrices)))

    cleaned_figures = plot_cleaned_signals(subject, local_clean, server_clean)
    result = {
        "subject": subject,
        "paths": {key: str(value) for key, value in paths.items()},
        "local_outputs": {
            "ica": str(local_ica_path),
            "clean": str(local_clean_path),
        },
        "excluded_components": [int(item) for item in excluded],
        "local_ica_fit": fit_info,
        "signal_metrics": {
            "preprocessed_vs_page": pre_metrics,
            "server_ica_replay_vs_page": replay_metrics,
            "local_clean_vs_page": clean_metrics,
        },
        "ica_components": component_metrics,
        "figures": {
            "topomap_sheets": topomap_sheets,
            "cleaned": cleaned_figures,
        },
    }

    del raw, server_bandpass, server_ica, server_clean, local_preprocessed, local_ica, local_clean, replay_clean
    gc.collect()
    return result


def main() -> None:
    mne.set_log_level("ERROR")
    META_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    manifest = read_manifest()
    subjects = sorted(manifest.get("raw_input_paths", {}).keys())
    if not subjects:
        raise RuntimeError("No raw input paths found in manifest.")
    results: dict[str, Any] = {}
    for subject in subjects:
        results[subject] = process_subject(subject, manifest)
        METRICS_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(manifest, results)
    METRICS_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"metrics_path": str(METRICS_PATH), "report_path": str(REPORT_PATH)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
