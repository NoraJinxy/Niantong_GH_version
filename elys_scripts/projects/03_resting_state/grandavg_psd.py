"""
grandavg_psd.py —— Eyes-Open vs Eyes-Closed Welch PSD grand average 对比图。

读 data/ 下所有 EDF（命名格式 sub-XXX_task-{eo|ec}_eeg.edf），
每人每 condition 算全 EEG 通道均值 Welch PSD，
grand average ± SEM 画在同一张图，存到 output/grandavg_psd_eo_vs_ec.png。

用法：
    cd elys_scripts
    .venv\\Scripts\\activate          # 首次跑 start.cmd 会装好
    python projects\\03_resting_state\\grandavg_psd.py
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

try:
    import mne
    mne.set_log_level("WARNING")
except ImportError:
    sys.exit("缺少 MNE，请先运行 start.cmd（它会自动安装），或手动 pip install mne")

try:
    import matplotlib.pyplot as plt
except ImportError:
    sys.exit("缺少 matplotlib，请 pip install matplotlib")

# ── 路径 ──────────────────────────────────────────────────────────────────────
HERE     = Path(__file__).parent
DATA_DIR = HERE / "data"
OUT_DIR  = HERE / "output"

# ── 参数 ──────────────────────────────────────────────────────────────────────
FMIN, FMAX = 1.0, 45.0      # PSD 频率范围 Hz（与 pipeline 一致）
L_FREQ     = 1.0            # 带通高通截止
H_FREQ     = 45.0           # 带通低通截止

TASK_MAP = {"eo": "Eyes Open", "ec": "Eyes Closed"}
COLORS   = {"eo": "#E87040", "ec": "#4472C4"}   # 暖橙=睁眼 冷蓝=闭眼

# 频段划分（只用于标注）
BANDS = [("δ", 1, 4), ("θ", 4, 8), ("α", 8, 13), ("β", 13, 30), ("γ", 30, 45)]


# ── 文件发现 ──────────────────────────────────────────────────────────────────
def parse_files(data_dir: Path) -> dict[str, list[Path]]:
    """按 task(eo/ec) 分组，返回 {task: [Path, ...]}。"""
    groups: dict[str, list[Path]] = defaultdict(list)
    for f in sorted(data_dir.glob("sub-*_task-*_eeg.edf")):
        task_part = next((p for p in f.stem.split("_") if p.startswith("task-")), None)
        if task_part is None:
            continue
        task = task_part.removeprefix("task-")
        if task in TASK_MAP:
            groups[task].append(f)
    return dict(groups)


# ── 单被试 PSD ────────────────────────────────────────────────────────────────
def compute_subject_psd(edf_path: Path) -> tuple[np.ndarray, np.ndarray] | None:
    """读单个 EDF → 带通滤波 → Welch PSD → 全通道均值，返回 (freqs, psd_mean_uv2)。"""
    try:
        raw = mne.io.read_raw_edf(edf_path, preload=True, verbose=False)
    except Exception as e:
        print(f"    [skip] 读取失败：{e}")
        return None

    # 优先选 EEG 通道；有些 EDF 没标 type，则取全部
    picks = mne.pick_types(raw.info, eeg=True, exclude="bads")
    if len(picks) == 0:
        picks = list(range(len(raw.ch_names)))
    raw.pick(picks)

    # 带通 1-45 Hz（与 ELYS pipeline 一致）
    raw.filter(l_freq=L_FREQ, h_freq=H_FREQ, method="iir",
               iir_params={"order": 4, "ftype": "butter"}, verbose=False)

    # Welch PSD（MNE 1.x API）
    psd_obj  = raw.compute_psd(method="welch", fmin=FMIN, fmax=FMAX, verbose=False)
    freqs    = psd_obj.freqs                      # (n_freqs,)
    psd_data = psd_obj.get_data()                 # (n_ch, n_freqs)，µV²/Hz

    return freqs, psd_data.mean(axis=0)


# ── 组级收集 ──────────────────────────────────────────────────────────────────
def collect_group(
    groups: dict[str, list[Path]],
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """对每个 task 下所有被试算 PSD，返回 {task: (freqs, psds [n_subs × n_freqs])}。"""
    result: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for task, files in sorted(groups.items()):
        label = TASK_MAP[task]
        print(f"\n[{label}]  {len(files)} 个被试")
        psds: list[np.ndarray] = []
        ref_freqs: np.ndarray | None = None

        for f in files:
            sub = f.stem.split("_")[0]
            print(f"  {sub} …", end=" ", flush=True)
            out = compute_subject_psd(f)
            if out is None:
                print("跳过")
                continue
            freqs, psd_mean = out
            if ref_freqs is None:
                ref_freqs = freqs
            if len(psd_mean) != len(ref_freqs):
                print(f"跳过（频率轴不一致）")
                continue
            psds.append(psd_mean)
            print("OK")

        if psds and ref_freqs is not None:
            result[task] = (ref_freqs, np.array(psds))   # (n_subs, n_freqs)
            print(f"  → 有效 {len(psds)}/{len(files)} 人")

    return result


# ── 绘图 ──────────────────────────────────────────────────────────────────────
def plot_grandavg(
    collected: dict[str, tuple[np.ndarray, np.ndarray]],
    out_dir: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(11, 5))

    for task, (freqs, psds) in sorted(collected.items(), reverse=True):  # ec 先画（下层）
        label = TASK_MAP[task]
        color = COLORS[task]
        n           = psds.shape[0]
        grand_avg   = psds.mean(axis=0)          # µV²/Hz
        sem         = psds.std(axis=0, ddof=1) / np.sqrt(n)

        # 转 dB（以 µV²/Hz 为单位，log 后更线性、视觉友好）
        ga_db    = 10 * np.log10(np.maximum(grand_avg, 1e-30))
        upper_db = 10 * np.log10(np.maximum(grand_avg + sem, 1e-30))
        lower_db = 10 * np.log10(np.maximum(grand_avg - sem, 1e-30))

        ax.plot(freqs, ga_db, label=f"{label}  (n={n})", color=color, linewidth=2)
        ax.fill_between(freqs, lower_db, upper_db, color=color, alpha=0.15)

    # 频段背景 + 标注
    ymin, ymax = ax.get_ylim()
    for name, lo, hi in BANDS:
        ax.axvspan(lo, hi, alpha=0.06, color="gray", zorder=0)
        ax.text((lo + hi) / 2, ymax, name, ha="center", va="bottom",
                fontsize=9, color="#666666")

    ax.set_xlabel("Frequency (Hz)", fontsize=12)
    ax.set_ylabel("Power (dB  µV²/Hz)", fontsize=12)
    ax.set_title("Resting-State PSD — Grand Average ± SEM\n"
                 f"({', '.join(TASK_MAP[t] for t in sorted(collected))})",
                 fontsize=13)
    ax.set_xlim(FMIN, FMAX)
    ax.legend(fontsize=11, loc="upper right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "grandavg_psd_eo_vs_ec.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"\n图已存：{out_path}")


# ── 入口 ──────────────────────────────────────────────────────────────────────
def main() -> None:
    print("=== Resting-State PSD Grand Average ===")

    groups = parse_files(DATA_DIR)
    if not groups:
        sys.exit(f"data/ 里没找到 sub-*_task-{{eo,ec}}_eeg.edf")

    for task, files in sorted(groups.items()):
        print(f"  {TASK_MAP[task]:15s}: {len(files)} 个文件")

    collected = collect_group(groups)
    if not collected:
        sys.exit("没有成功解析的 PSD，退出。")

    print("\n绘图 …")
    plot_grandavg(collected, OUT_DIR)


if __name__ == "__main__":
    main()
