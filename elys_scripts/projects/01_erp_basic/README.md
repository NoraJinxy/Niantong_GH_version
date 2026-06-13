# 01_erp_basic —— 端到端 ERP pipeline 测试

目的：跑通 `建数据集 → 上传数据 → 建 pipeline → 跑 → 下载产物` 这条 ERP 主线，
**作为 ERP 相关 bug 的最小可复现脚本。**

分两个脚本、两段跑：

| 脚本 | 干什么 | 何时跑 |
|---|---|---|
| `setup.py` | 建 Dataset+Study+挂载 → 上传 BrainVision 数据 → 打印通道名/事件标签 | 数据没变时跑一次就够 |
| `run.py`   | 建 pipeline → validate → run → 打印每节点状态 → 下载 evoked | 调 pipeline 参数时反复跑 |

仓库根的 `step3_elys_debug.cmd` 会**先跑 setup 再跑 run**，一键到底；
只调 pipeline 时直接 `python run.py`，不必每次重传数据。

## 用前

1. 改 `common/config.py` 填好 `BASE_URL` / `USERNAME` / `PASSWORD`
2. 改本目录 `config_local.py`：
   - setup 用：`DATASET_*` / `STUDY_*` / `SUBJECT` / `TASK`
   - run 用：`PIPELINE_NAME` / `DATASET_IDS` / `REF_CHANNELS` / `EVENT_LABELS`
3. 把 BrainVision 三件套放进 `data/`（同名，如 `sub093.vhdr` / `sub093.eeg` / `sub093.vmrk`）

## 跑

```bash
cd elys_scripts/projects/01_erp_basic
python setup.py     # 建库 + 传数据；按它打印的把 STUDY_ID / DATASET_IDS / REF_CHANNELS / EVENT_LABELS 回填到 config_local.py
python run.py       # 跑 ERP pipeline
```

幂等：dataset 同 code 复用；上传 `replace_existing=True`，重跑建新版本（recording id 不变）而不是报 409。

## 改 pipeline 参数

- 换滤波类型 / 频段：改 `run.py` 里 `build_definition()` 的 `bw`（统一 `eeg/filter/apply`）节点——`filter_type`（bandpass/highpass/lowpass/notch）、`method`（fir/iir/spectrum_fit，仅陷波可用谱拟合）、`l_freq`/`h_freq`；陷波改用 `notch_freq`/`notch_harmonics`。
- 换参考电极 / 分析条件：改 `config_local.py` 的 `REF_CHANNELS` / `EVENT_LABELS`（候选见 setup 打印）。
- 要重跑不同参数对比：复制 `run.py` 成 `run_v2.py` 改参数，跑两次对比 `output/`。
