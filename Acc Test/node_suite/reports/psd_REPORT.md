# PSD 节点 MNE 对比报告

- 节点: `eeg/analysis/psd`
- 流水线: `Acc Test - node PSD epochs`
- 结论: **PASS**
- 说明: 按条件选择 Epochs 后调用 MNE compute_psd，并跨 epoch 求均值。

## 指标

| 指标 | 通过 | shape | max_abs | relative_rmse | 备注 |
| --- | --- | --- | ---: | ---: | --- |
| PSD Welch psds | 是 | 63x39 | 6.204e-25 | 1.809e-18 |  |
| PSD Welch freqs | 是 | 39 | 0 | 0 |  |
| PSD Welch channels | 是 |  | - | - | 63 |

## 节点参数

```json
{
  "epoch": {
    "conditions": [
      {
        "name": "S  3",
        "pattern": "S\\s*0*3\\b",
        "mode": "regex"
      }
    ],
    "tmin": -0.2,
    "tmax": 0.8,
    "split_by": "none"
  },
  "psd": {
    "condition": [
      "S  3"
    ],
    "fmin": 1,
    "fmax": 40,
    "method": "welch",
    "window_seconds": "",
    "overlap": 0.5
  }
}
```

## 原始指标

```json
{
  "case": "psd",
  "title": "PSD",
  "node_types": [
    "eeg/analysis/psd"
  ],
  "pipeline_name": "Acc Test - node PSD epochs",
  "status": "PASS",
  "summary": "按条件选择 Epochs 后调用 MNE compute_psd，并跨 epoch 求均值。",
  "metrics": [
    {
      "label": "PSD Welch psds",
      "passed": true,
      "shape": [
        63,
        39
      ],
      "max_abs": 6.203854594147708e-25,
      "rmse": 1.861581482483458e-26,
      "relative_rmse": 1.80878802641549e-18,
      "reference_std": 2.0647763496104412e-10,
      "diff_std": 1.8613396629645482e-26,
      "diff_std_over_reference_std": 9.014727737053579e-17,
      "atol": 1e-18,
      "rtol": 1e-08
    },
    {
      "label": "PSD Welch freqs",
      "passed": true,
      "shape": [
        39
      ],
      "max_abs": 0.0,
      "rmse": 0.0,
      "relative_rmse": 0.0,
      "reference_std": 11.243385292130622,
      "diff_std": 0.0,
      "diff_std_over_reference_std": 0.0,
      "atol": 1e-10,
      "rtol": 1e-08
    },
    {
      "label": "PSD Welch channels",
      "passed": true,
      "common_channels": 63
    }
  ],
  "params": {
    "epoch": {
      "conditions": [
        {
          "name": "S  3",
          "pattern": "S\\s*0*3\\b",
          "mode": "regex"
        }
      ],
      "tmin": -0.2,
      "tmax": 0.8,
      "split_by": "none"
    },
    "psd": {
      "condition": [
        "S  3"
      ],
      "fmin": 1,
      "fmax": 40,
      "method": "welch",
      "window_seconds": "",
      "overlap": 0.5
    }
  }
}
```
