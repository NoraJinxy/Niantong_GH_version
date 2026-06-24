"""本机 ERD/ERS 参照脚本(独立于 ELYS 后端,直接用 MNE 读 H01.bdf 出图)。

目的:给 s3_test2_erders.cmd 的产物做一个"地面真值"对照——
  - 严格复刻测试管线参数(带通 1-40 IIR / 陷波 50 / Epoch[-1,5] / Morlet 4-40Hz, n_cycles=f/2 / % 基线[-1,0]),
  - 但**握拳 + 放松两个条件都算**(测试只算了握拳 TFR_CONDITION="fist"),
  - 并量一下 cue→MI 执行窗的延迟(解释为什么 cue-locked 的 ERD 会推后)。

只读不写后端,产物是一张 PNG + 一段文字统计。本机 mne 1.12.1(云端是 1.7.1,出图对照足够)。
"""
from __future__ import annotations
import re
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")  # 无显示后端,直接存 PNG
import matplotlib.pyplot as plt
import mne

HERE = Path(__file__).parent
BDF = HERE / "data" / "H01_D01_B01_train20_test60.bdf"
OUT_PNG = HERE / "local_erders_H01.png"

FMIN, FMAX, NFREQS = 4.0, 40.0, 30
PLOT_CHANNELS = ["C3", "C4"]     # 手运动关键通道(对侧 ERD)
MU = (8, 13); BETA = (13, 30)

# 单 trial 结构(实测):trial/start(0) → mi/window_start(+2) → cue_sent(+3.55,在MI窗内) → mi/window_end(+7)
# cue 恒在 mi_start 后 1.55s(std 0.01)。三种口径对照:
#   cue-old   = 测试旧口径(锚 cue,窗 -1~5,基线 cue 前 1s —— 那 1s 已在 MI 窗内 → 基线污染,出鬼值)
#   cue-fixed = 修复后口径(仍锚 cue,但窗 -3.5~4、基线 [-3.5,-1.9] 落在 MI 前准备期 —— 等价 MI-locked)
#   mi-locked = 直接锚 mi/window_start(真值参照)
CUE_OLD = dict(anchor="cue", tmin=-1.0, tmax=5.0, base=(None, 0.0), post=(0.5, 4.5), tag="cue-old(测试旧口径)")
CUE_FIX = dict(anchor="cue", tmin=-3.5, tmax=4.0, base=(None, -1.9), post=(0.0, 3.0), tag="cue-fixed(新config)")
MIW = dict(anchor="mi", tmin=-2.0, tmax=6.0, base=(-1.5, -0.3), post=(0.5, 4.5), tag="mi-locked(真值参照)")


def sample_of(onset, sfreq, first_samp):
    return int(round(onset * sfreq)) + first_samp


def _trial_label_map(descs):
    """index N -> 1(fist)/2(rest)，从 cue_sent 的 clench_fist/relax_arm 解析。"""
    m = {}
    for d in descs:
        g = re.search(r"cue_sent/index/(\d+)/(clench_fist|relax_arm)", d)
        if g:
            m[g.group(1)] = 1 if g.group(2) == "clench_fist" else 2
    return m


def build_events(raw, anchor):
    """anchor='cue' 用 cue_sent 时刻；anchor='mi' 用 mi/window_start 时刻。类别都来自 cue 的 fist/rest。"""
    sfreq = raw.info["sfreq"]; fs = raw.first_samp
    onsets = raw.annotations.onset; descs = [str(d) for d in raw.annotations.description]
    label_of = _trial_label_map(descs)
    rows = []
    for onset, d in zip(onsets, descs):
        if anchor == "cue":
            g = re.search(r"cue_sent/index/(\d+)/(clench_fist|relax_arm)", d)
            if g:
                rows.append([sample_of(onset, sfreq, fs), 0, 1 if g.group(2) == "clench_fist" else 2])
        else:  # mi
            g = re.search(r"mi/window_start/index/(\d+)", d)
            if g and g.group(1) in label_of:
                rows.append([sample_of(onset, sfreq, fs), 0, label_of[g.group(1)]])
    ev = np.array(sorted(rows), dtype=int)
    return ev, {"fist": 1, "rest": 2}


def compute_powers(raw, cfg):
    events, event_id = build_events(raw, cfg["anchor"])
    epochs = mne.Epochs(raw, events, event_id, tmin=cfg["tmin"], tmax=cfg["tmax"],
                        baseline=None, preload=True, verbose="ERROR")
    freqs = np.linspace(FMIN, FMAX, NFREQS)
    n_cycles = np.maximum(freqs / 2.0, 1.0)
    powers = {}
    for label in event_id:
        p = epochs[label].compute_tfr("morlet", freqs=freqs, n_cycles=n_cycles,
                                      average=True, return_itc=False, decim=4, verbose="ERROR")
        p.apply_baseline(cfg["base"], mode="percent", verbose="ERROR")
        powers[label] = p
    return powers, dict(fist=int(sum(events[:, 2] == 1)), rest=int(sum(events[:, 2] == 2)))


def band_pct(p, ch, band, post):
    ci = p.ch_names.index(ch); fr = p.freqs; t = p.times
    tmask = (t >= post[0]) & (t <= post[1])
    return p.data[ci][(fr >= band[0]) & (fr < band[1])][:, tmask].mean() * 100


def report(powers, cfg):
    print(f"\n[ERD%] {cfg['tag']}  anchor后{cfg['post'][0]}-{cfg['post'][1]}s  基线={cfg['base']}(负=ERD)")
    print(f"  {'cond':6s}{'ch':5s}{'mu(8-13)':>11s}{'beta(13-30)':>13s}")
    for label, p in powers.items():
        for ch in PLOT_CHANNELS:
            if ch in p.ch_names:
                print(f"  {label:6s}{ch:5s}{band_pct(p,ch,MU,cfg['post']):>10.1f}%{band_pct(p,ch,BETA,cfg['post']):>12.1f}%")


def main():
    print(f"[load] {BDF.name}")
    raw = mne.io.read_raw_bdf(BDF, preload=True, verbose="ERROR")
    print(f"  sfreq={raw.info['sfreq']}  ch={raw.ch_names}")
    raw.filter(1.0, 40.0, method="iir", iir_params=dict(order=4, ftype="butter"), verbose="ERROR")
    raw.notch_filter([50, 100, 150], verbose="ERROR")

    # 三种口径都算,直接对照
    old_pow, n = compute_powers(raw, CUE_OLD)
    fix_pow, _ = compute_powers(raw, CUE_FIX)
    mi_pow, _ = compute_powers(raw, MIW)
    print(f"[epoch] fist={n['fist']} rest={n['rest']}")
    report(old_pow, CUE_OLD)
    report(fix_pow, CUE_FIX)
    report(mi_pow, MIW)

    # 出图:画修复后口径(cue-fixed,= 上云后测试将产出的结果),2 条件 × 2 通道
    fig, axes = plt.subplots(2, len(PLOT_CHANNELS),
                             figsize=(5 * len(PLOT_CHANNELS), 8), squeeze=False)
    for r, (label, p) in enumerate(fix_pow.items()):
        for col, ch in enumerate(PLOT_CHANNELS):
            ax = axes[r][col]
            ci = p.ch_names.index(ch)
            im = ax.imshow(p.data[ci] * 100, origin="lower", aspect="auto", cmap="RdBu_r",
                           vmin=-100, vmax=100,
                           extent=[p.times[0], p.times[-1], p.freqs[0], p.freqs[-1]])
            ax.axvline(-1.55, color="k", ls="--", lw=1)   # MI onset (cue 前 1.55s)
            ax.axvline(3.45, color="gray", ls=":", lw=1)   # MI end (cue 后 3.45s)
            ax.set_title(f"{label} - {ch}")
            ax.set_xlabel("time from cue (s)"); ax.set_ylabel("freq (Hz)")
            fig.colorbar(im, ax=ax, label="% change")
    fig.suptitle("H01 ERD/ERS  cue-fixed (new config)  black=MI onset, gray=MI end")
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=110)
    print(f"\n[saved] {OUT_PNG}")


if __name__ == "__main__":
    main()
