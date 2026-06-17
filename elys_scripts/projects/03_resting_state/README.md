# 03_resting_state —— 端到端静息态 PSD pipeline 测试

目的：跑通 `建数据集 → 上传静息态 BrainVision 数据 → 建 pipeline → 跑 → 列 PSD 产物` 这条
静息态频谱主线，**作为 PSD / 频谱相关 bug 的最小可复现脚本。**

与 01/02 的核心区别：**没有 Epoch、没有 Reject Trials**。
静息态没有事件锚点，直接对连续 EEG 做 Welch PSD。PSD 节点 `condition` 留空，
接收 `eeg_data`（连续信号，即 `spectral_source` 输入的一种）整段算一条功率谱。

分两个脚本、两段跑：

| 脚本 | 干什么 | 何时跑 |
|---|---|---|
| `setup.py` | 建 Dataset+Study+挂载 → 上传 BrainVision 三件套 → 打印通道名 | 数据没变时跑一次 |
| `run.py`   | 建 pipeline → validate → run → 打印每节点状态 → 列 PSD 产物 | 调 pipeline 参数时反复跑 |

`start.cmd 03_resting_state`（仓库根 `elys_scripts/` 下）会**先跑 setup 再跑 run**，一键到底；
只调 pipeline 时直接 `python run.py`，不必每次重传数据。

## pipeline 链路

```
LoadData → Bandpass(1-45 IIR) → Notch(50Hz) → Ch Loc → Bad Channels(LOF+插值)
         → Re-reference → PSD(Welch, 1-45Hz)
```

- **Bandpass 1-45Hz**：高通 1Hz 去漂移，低通 45Hz 截高频（工频基频 50Hz 留给陷波处理）。
- **Ch Loc** 在坏道修复前：球面样条插值需要标准电极坐标，上游没它插值会失败。
- **Bad Channels** 在 Re-reference 前：坏道不修就参与参考计算会污染全局参考。
- **Re-reference（乳突 TP9/TP10）**：alpha 峰频和相对功率对参考敏感，静息态 PSD 通常要重参考。
- **PSD condition 留空**：连续数据无 condition，整段算一条谱。产物 `.npz` 含各频段绝对 + 相对功率
  （delta/theta/alpha/beta/gamma），观察页右栏可直读 IAF / TBR / DAR 等临床指标。

## 数据

把静息态 BrainVision 三件套（`.vhdr` / `.eeg` / `.vmrk`，**同文件名**）放进 `data/`，
文件名任意（setup 自动发现），改 `config_local.py` 的 `SUBJECT` / `TASK` 即可。

## 用前

1. 改 `common/config.py` 填好 `BASE_URL` / `USERNAME` / `PASSWORD`
2. 改本目录 `config_local.py`：`DATASET_*` / `STUDY_*` / `SUBJECT` / `TASK`
3. 把 BrainVision 三件套放进 `data/`

## 跑

```bash
cd elys_scripts/projects/03_resting_state
python setup.py     # 建库 + 传数据；按它打印的通道名回填 REF_CHANNELS / DATASET_IDS
python run.py       # 跑静息态 PSD pipeline
```

幂等：dataset 同 code 复用；上传 `replace_existing=True`，重跑建新版本（recording id 不变）。

## 改 pipeline 参数（都在 `config_local.py`）

- **参考电极** `REF_CHANNELS`：setup 打印通道名后改，乳突=`["TP9","TP10"]`，连接耳=`["A1","A2"]`。
- **PSD 频段** `PSD_FMIN/FMAX`：1-45Hz 覆盖全频段；只看 alpha 可缩到 `1-30`。
- **PSD 方法** `PSD_METHOD`：`welch`（分段平均，宽带，默认）/ `multitaper`（低方差）/ `fft`（单段，SSVEP）。
- **换成 Epoch 输入**：若想按事件切 Epoch 再做 PSD（如闭眼/开眼分段对比），在 `run.py`
  的 `build_definition()` 里在 `rr` 后插入 `eeg/epoch/segment` 节点，`psd` 的 `condition` 填对应标签即可。
