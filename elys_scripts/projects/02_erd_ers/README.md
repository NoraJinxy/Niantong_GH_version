# 02_erd_ers —— 端到端 ERD/ERS pipeline 测试

目的：跑通 `建数据集 → 上传 econ 运动想象 .bdf → 建 pipeline → 跑 → 列产物` 这条
ERD/ERS 主线，**作为时频(TFR)/运动想象相关 bug 的最小可复现脚本。**

ERD/ERS（事件相关去同步/同步）= 运动想象时 mu(8-13Hz)/beta(13-30Hz) 节律的功率变化：
想象动作时功率下降(ERD)、结束后反弹(ERS)。与 01_erp_basic（ERP 时域叠加）互补——
**这条链末端是 TFR(Morlet 小波) + 基线归一化，不是 ERP。**

分两个脚本、两段跑：

| 脚本 | 干什么 | 何时跑 |
|---|---|---|
| `setup.py` | 建 Dataset+Study+挂载 → 上传单个 econ `.bdf` → 打印通道名/事件标签 | 数据没变时跑一次 |
| `run.py`   | 建 pipeline → validate → run → 打印每节点状态 → 列 TFR 产物 | 调 pipeline 参数时反复跑 |

仓库根的 `step3_test2_erders.cmd` 会**先跑 setup 再跑 run**，一键到底；
只调 pipeline 时直接 `python run.py`，不必每次重传数据。

## pipeline 链路

```
LoadData → Bandpass(1-40 IIR) → Notch(50Hz) → Epoch(MI 类切分) → TFR(ERD/ERS)
```

不做 Re-reference（运动想象 ERD/ERS 对参考不敏感，且省去待回填的通道列表，先求跑通；
要做共同平均参考就自己在 `run.py` 加 `eeg/preproc/rereference` 节点）。

## 数据

`data/` 里是 econ 运动想象 BDF（标准 BDF+/TAL，后端导入已支持）：
- `H01`~`H04`：健康者；`P02`/`P09`：患者（`D01`=day1, `B01`=block1, `train20_test60`=范式）
- 事件：`label/1`=握拳想象、`label/0`=放松休息（见 `data/readme.txt`）

默认传 `H01`（在 `config_local.py` 的 `BDF_FILE` 改被试）。

## 用前

1. 改 `common/config.py` 填好 `BASE_URL` / `USERNAME` / `PASSWORD`
2. 改本目录 `config_local.py`：`DATASET_*` / `STUDY_*` / `BDF_FILE` / `SUBJECT` / `TASK`

## 跑

```bash
cd elys_scripts/projects/02_erd_ers
python setup.py     # 建库 + 传数据；按它打印的事件标签回填 CONDITIONS / DATASET_IDS
python run.py       # 跑 ERD/ERS pipeline
```

幂等：dataset 同 code 复用；上传 `replace_existing=True`，重跑建新版本（recording id 不变）。

## 改 pipeline 参数（都在 `config_local.py`）

- **切分条件** `CONDITIONS`：锚 cue 指令 `clench_fist`(握拳)/`relax_arm`(放松)，`contains` 归并，各 40 trial。
  别用 `label/1`/`label/0`：它们在 `trial/start` 和 `trial/end` 各出现一次、可能撞同采样点 → MNE 报事件不唯一。
- **Epoch 窗** `EPOCH_TMIN/TMAX`：**关键坑** —— 这个范式里 cue 落在 MI 窗「内部」（实测单 trial：
  `trial_start(0)→mi/window_start(+2.0)→cue(+3.55)→mi/window_end(+7.0)`，cue 恒比 MI 晚 1.55s）。
  相对 cue：MI 段=`[-1.55,+3.45]`、MI 前干净基线≈`[-3.5,-1.9]`。故窗取 **`-3.5 ~ 4`**（旧值 `-1~5` 会把基线压进 MI 段、出鬼值）。
- **TFR / ERD-ERS** `TFR_*`：`TFR_CONDITION`（**给列表 `["fist","rest"]` 才有握拳-放松对比**，逐条各出一图）、
  `TFR_FMIN/FMAX`（频段）、`TFR_BASELINE_MODE`（`percent`=% 变化，负=ERD、正=ERS）、
  `TFR_BASELINE_TMAX`（基线窗结束，本范式用 **`-1.9`** 落在 MI 起点之前，**不能用 0**）。
- **本机真值参照**：`erders_reference.py`（独立 MNE 读 `data/H01.bdf` 直接出 ERD/ERS 图，
  不经后端）可用来对拍 pipeline 产物是否正确；它同时打印 cue-old / cue-fixed / mi-locked 三口径对照。
