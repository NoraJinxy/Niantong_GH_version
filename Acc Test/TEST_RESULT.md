# test1 MNE 一致性测试报告

- 标准答案: MNE 复算结果
- 原始输入: `E:\JinXingyi\gitee\claude\Acc Test\server_outputs\00_load_raw.fif`
- 对照产物: `server_outputs/`
- 流水线: LoadData -> Notch 50 Hz -> Bandpass 0.1-40 Hz -> Epoch(-1, 3) -> Baseline(None, 0) -> ERP Average
- 误差定义: `error = web_result - mne_reference`

## 标准差与准确性指标

| 节点 | shape | MNE std(uV) | error std(uV) | error/MNE std | max abs err(uV) | mean abs err(uV) | corr | SNR(dB) | 结论 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 00 LoadData raw | 64x284200 | 3.820882e+01 | 0.000000e+00 | 0.000000e+00 | 0.000000e+00 | 0.000000e+00 | 1.000000e+00 | inf | 完全一致 |
| 01 Filter notch | 64x284200 | 3.744593e+01 | 1.094880e-06 | 2.923897e-08 | 2.322546e-05 | 7.062416e-07 | 1.000000e+00 | 1.506808e+02 | 浮点级一致 |
| 02 Filter bandpass 0.1-40 Hz | 64x284200 | 2.306818e+01 | 6.786986e-07 | 2.942142e-08 | 3.052258e-05 | 4.170114e-07 | 1.000000e+00 | 1.506267e+02 | 浮点级一致 |
| 03 Epoch -1..3 s | 90x64x4001 | 2.136817e+01 | 6.061961e-07 | 2.836911e-08 | 3.052258e-05 | 3.917391e-07 | 1.000000e+00 | 1.509431e+02 | 浮点级一致 |
| 04 Baseline start..0 s | 90x64x4001 | 2.116162e+01 | 7.961773e-07 | 3.762364e-08 | 4.609799e-05 | 5.089084e-07 | 1.000000e+00 | 1.484908e+02 | 浮点级一致 |
| 05 ERP Average Stimulus/S  3 | 63x4001 | 6.516855e+00 | 2.365671e-07 | 3.630081e-08 | 4.434283e-06 | 1.537742e-07 | 1.000000e+00 | 1.488017e+02 | 浮点级一致 |
| 05 ERP Average Stimulus/S  4 | 63x4001 | 2.887800e+00 | 1.532858e-07 | 5.308046e-08 | 1.534091e-06 | 1.136623e-07 | 1.000000e+00 | 1.455013e+02 | 浮点级一致 |
| 05 ERP Average Stimulus/S  5 | 63x4001 | 3.355362e+00 | 1.810454e-07 | 5.395704e-08 | 1.941111e-06 | 1.322951e-07 | 1.000000e+00 | 1.453590e+02 | 浮点级一致 |

## 旧版误差指标

| 节点 | max_abs(V) | mean_abs(V) | RMSE(V) | relative_RMSE | bias(web-MNE, uV) | 通道差异 |
|---|---:|---:|---:|---:|---:|---|
| 00 LoadData raw | 0.000000e+00 | 0.000000e+00 | 0.000000e+00 | 0.000000e+00 | 0.000000e+00 | - |
| 01 Filter notch | 2.322546e-11 | 7.062416e-13 | 1.094880e-12 | 2.509618e-08 | 1.201016e-10 | - |
| 02 Filter bandpass 0.1-40 Hz | 3.052258e-11 | 4.170114e-13 | 6.787015e-13 | 2.941851e-08 | -2.011355e-09 | - |
| 03 Epoch -1..3 s | 3.052258e-11 | 3.917391e-13 | 6.061961e-13 | 2.836099e-08 | -1.983749e-10 | - |
| 04 Baseline start..0 s | 4.609799e-11 | 5.089084e-13 | 7.961773e-13 | 3.761945e-08 | 7.171714e-11 | - |
| 05 ERP Average Stimulus/S  3 | 4.434283e-12 | 1.537742e-13 | 2.365793e-13 | 3.377550e-08 | 2.400012e-09 | - |
| 05 ERP Average Stimulus/S  4 | 1.534091e-12 | 1.136623e-13 | 1.533029e-13 | 5.078752e-08 | -2.294839e-09 | - |
| 05 ERP Average Stimulus/S  5 | 1.941111e-12 | 1.322951e-13 | 1.810461e-13 | 4.461342e-08 | 4.957371e-10 | - |

## 说明

- `MNE std` 是标准答案自身标准差，用来表示该节点结果的信号量级。
- `error std` 是网页结果相对 MNE 的误差标准差，是本次新增的核心绝对误差指标。
- `error/MNE std` 是标准化误差，适合跨节点比较；本报告用它给出结论。
- `corr` 是按对齐后的全部样本计算的 Pearson 相关系数；越接近 1，波形形状越一致。
- `SNR(dB)=20*log10(MNE std/error std)`；越大说明误差相对信号越小。
- ERP Average 的服务器产物少 `IO` 通道；该通道在 Epoch 中是 `misc`，MNE 平均后不会进入 Evoked。脚本按共同通道对齐后比较。
- 本次使用 execution #2，因为它已完成且只包含本次点名的 sub-007；execution #3 后来也已完成，但 v4 同时选中了 sub-008，范围不同。

## 原始指标 JSON

```json
[
  {
    "label": "00 LoadData raw",
    "shape": [
      64,
      284200
    ],
    "reference_mean": -2.2386380310971956e-05,
    "server_mean": -2.2386380310971956e-05,
    "error_mean": 0.0,
    "reference_std": 3.8208818219572944e-05,
    "server_std": 3.8208818219572944e-05,
    "error_std": 0.0,
    "error_std_over_reference_std": 0.0,
    "max_abs_error": 0.0,
    "mean_abs_error": 0.0,
    "rmse": 0.0,
    "relative_rmse": 0.0,
    "correlation": 1.0,
    "snr_db": "inf",
    "max_abs": 0.0,
    "mean_abs": 0.0,
    "rms": 0.0,
    "relative_rms": 0.0,
    "missing_in_reference": [],
    "missing_in_server": []
  },
  {
    "label": "01 Filter notch",
    "shape": [
      64,
      284200
    ],
    "reference_mean": -2.2386368593742732e-05,
    "server_mean": -2.2386368593622616e-05,
    "error_mean": 1.2010157115471323e-16,
    "reference_std": 3.7445933737100414e-05,
    "server_std": 3.744593373749142e-05,
    "error_std": 1.0948803519536939e-12,
    "error_std_over_reference_std": 2.9238965160826424e-08,
    "max_abs_error": 2.322546121353783e-11,
    "mean_abs_error": 7.062416128652794e-13,
    "rmse": 1.0948803585408935e-12,
    "relative_rmse": 2.509618038591549e-08,
    "correlation": 1.0,
    "snr_db": 150.68076004392498,
    "max_abs": 2.322546121353783e-11,
    "mean_abs": 7.062416128652794e-13,
    "rms": 1.0948803585408935e-12,
    "relative_rms": 2.509618038591549e-08,
    "missing_in_reference": [],
    "missing_in_server": []
  },
  {
    "label": "02 Filter bandpass 0.1-40 Hz",
    "shape": [
      64,
      284200
    ],
    "reference_mean": -3.315200088722106e-07,
    "server_mean": -3.315200108835655e-07,
    "error_mean": -2.011355403838058e-15,
    "reference_std": 2.3068176877882177e-05,
    "server_std": 2.3068176876564295e-05,
    "error_std": 6.786985678964406e-13,
    "error_std_over_reference_std": 2.9421422052090228e-08,
    "max_abs_error": 3.052258142413611e-11,
    "mean_abs_error": 4.170113524758036e-13,
    "rmse": 6.787015482634773e-13,
    "relative_rmse": 2.9418513435797185e-08,
    "correlation": 0.9999999999999988,
    "snr_db": 150.62672679909684,
    "max_abs": 3.052258142413611e-11,
    "mean_abs": 4.170113524758036e-13,
    "rms": 6.787015482634773e-13,
    "relative_rms": 2.9418513435797185e-08,
    "missing_in_reference": [],
    "missing_in_server": []
  },
  {
    "label": "03 Epoch -1..3 s",
    "shape": [
      90,
      64,
      4001
    ],
    "reference_mean": 5.114784899983282e-07,
    "server_mean": 5.114784897999549e-07,
    "error_mean": -1.983749493420059e-16,
    "reference_std": 2.1368170548300684e-05,
    "server_std": 2.1368170548566358e-05,
    "error_std": 6.061960531977592e-13,
    "error_std_over_reference_std": 2.8369113388884258e-08,
    "max_abs_error": 3.052258142413611e-11,
    "mean_abs_error": 3.917391476449705e-13,
    "rmse": 6.06196085656417e-13,
    "relative_rmse": 2.8360991293842362e-08,
    "correlation": 1.0,
    "snr_db": 150.94308473726028,
    "max_abs": 3.052258142413611e-11,
    "mean_abs": 3.917391476449705e-13,
    "rms": 6.06196085656417e-13,
    "relative_rms": 2.8360991293842362e-08,
    "missing_in_reference": [],
    "missing_in_server": []
  },
  {
    "label": "04 Baseline start..0 s",
    "shape": [
      90,
      64,
      4001
    ],
    "reference_mean": 3.160069305725446e-07,
    "server_mean": 3.160069306442613e-07,
    "error_mean": 7.171714029830535e-17,
    "reference_std": 2.1161621972646183e-05,
    "server_std": 2.1161621973470285e-05,
    "error_std": 7.961773186508778e-13,
    "error_std_over_reference_std": 3.762364338990782e-08,
    "max_abs_error": 4.609799250220731e-11,
    "mean_abs_error": 5.089083837824807e-13,
    "rmse": 7.961773218809058e-13,
    "relative_rmse": 3.761944930001232e-08,
    "correlation": 1.0,
    "snr_db": 148.49078301275878,
    "max_abs": 4.609799250220731e-11,
    "mean_abs": 5.089083837824807e-13,
    "rms": 7.961773218809058e-13,
    "relative_rms": 3.761944930001232e-08,
    "missing_in_reference": [],
    "missing_in_server": []
  },
  {
    "label": "05 ERP Average Stimulus/S  3",
    "shape": [
      63,
      4001
    ],
    "reference_mean": -2.567706353561829e-06,
    "server_mean": -2.5677063511618166e-06,
    "error_mean": 2.4000120190121787e-15,
    "reference_std": 6.516855464308087e-06,
    "server_std": 6.516855478324424e-06,
    "error_std": 2.365671082601789e-13,
    "error_std_over_reference_std": 3.630080635604459e-08,
    "max_abs_error": 4.434283391592086e-12,
    "mean_abs_error": 1.5377417491002409e-13,
    "rmse": 2.365792822042425e-13,
    "relative_rmse": 3.3775499428273834e-08,
    "correlation": 0.9999999999999996,
    "snr_db": 148.80167455597686,
    "max_abs": 4.434283391592086e-12,
    "mean_abs": 1.5377417491002409e-13,
    "rms": 2.365792822042425e-13,
    "relative_rms": 3.3775499428273834e-08,
    "missing_in_reference": [],
    "missing_in_server": []
  },
  {
    "label": "05 ERP Average Stimulus/S  4",
    "shape": [
      63,
      4001
    ],
    "reference_mean": 8.786626975052086e-07,
    "server_mean": 8.786626952103696e-07,
    "error_mean": -2.2948388108557676e-15,
    "reference_std": 2.8878000684677154e-06,
    "server_std": 2.8878000662678426e-06,
    "error_std": 1.5328576090541908e-13,
    "error_std_over_reference_std": 5.308046169094852e-08,
    "max_abs_error": 1.534091116875305e-12,
    "mean_abs_error": 1.1366232348359175e-13,
    "rmse": 1.5330293794158388e-13,
    "relative_rmse": 5.0787522847371235e-08,
    "correlation": 0.9999999999999987,
    "snr_db": 145.50130616643114,
    "max_abs": 1.534091116875305e-12,
    "mean_abs": 1.1366232348359175e-13,
    "rms": 1.5330293794158388e-13,
    "relative_rms": 5.0787522847371235e-08,
    "missing_in_reference": [],
    "missing_in_server": []
  },
  {
    "label": "05 ERP Average Stimulus/S  5",
    "shape": [
      63,
      4001
    ],
    "reference_mean": 2.2824949807955958e-06,
    "server_mean": 2.2824949812913324e-06,
    "error_mean": 4.9573705364783865e-16,
    "reference_std": 3.3553624138971515e-06,
    "server_std": 3.355362410079604e-06,
    "error_std": 1.8104541344174785e-13,
    "error_std_over_reference_std": 5.395703685893921e-08,
    "max_abs_error": 1.94111078529206e-12,
    "mean_abs_error": 1.3229512505762824e-13,
    "rmse": 1.8104609215202568e-13,
    "relative_rmse": 4.461342420078012e-08,
    "correlation": 0.9999999999999989,
    "snr_db": 145.35903816708444,
    "max_abs": 1.94111078529206e-12,
    "mean_abs": 1.3229512505762824e-13,
    "rms": 1.8104609215202568e-13,
    "relative_rms": 4.461342420078012e-08,
    "missing_in_reference": [],
    "missing_in_server": []
  }
]
```
