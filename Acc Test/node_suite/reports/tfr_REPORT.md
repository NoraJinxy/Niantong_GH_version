# TFR 节点 MNE 对比报告

- 节点: `eeg/analysis/tfr`
- 流水线: `Acc Test - node TFR morlet`
- 结论: **PASS**
- 说明: 按条件选择 Epochs 后调用 MNE Morlet TFR，并应用同一基线校正。

## 指标

| 指标 | 通过 | shape | max_abs | relative_rmse | 备注 |
| --- | --- | --- | ---: | ---: | --- |
| TFR Morlet power | 是 | 63x8x376 | 9.77e-15 | 1.544e-18 |  |
| TFR Morlet times | 是 | 376 | 0 | 0 |  |
| TFR Morlet freqs | 是 | 8 | 0 | 0 |  |
| TFR Morlet channels | 是 |  | - | - | 63 |

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
    "tmin": -0.5,
    "tmax": 1.0,
    "split_by": "none"
  },
  "tfr": {
    "condition": [
      "S  3"
    ],
    "fmin": 4,
    "fmax": 20,
    "n_freqs": 8,
    "freq_scale": "linear",
    "n_cycles_mode": "factor",
    "n_cycles_factor": 0.5,
    "decim": 4,
    "baseline_mode": "logratio",
    "baseline_tmin": "",
    "baseline_tmax": 0
  }
}
```

## 原始指标

```json
{
  "case": "tfr",
  "title": "TFR",
  "node_types": [
    "eeg/analysis/tfr"
  ],
  "pipeline_name": "Acc Test - node TFR morlet",
  "status": "PASS",
  "summary": "按条件选择 Epochs 后调用 MNE Morlet TFR，并应用同一基线校正。",
  "metrics": [
    {
      "label": "TFR Morlet power",
      "passed": true,
      "shape": [
        63,
        8,
        376
      ],
      "max_abs": 9.769962616701378e-15,
      "rmse": 5.356840662510376e-16,
      "relative_rmse": 1.544091449707466e-18,
      "reference_std": 0.7155937477210198,
      "diff_std": 5.354614029511132e-16,
      "diff_std_over_reference_std": 7.482756866677758e-16,
      "atol": 1e-12,
      "rtol": 1e-08
    },
    {
      "label": "TFR Morlet times",
      "passed": true,
      "shape": [
        376
      ],
      "max_abs": 0.0,
      "rmse": 0.0,
      "relative_rmse": 0.0,
      "reference_std": 0.4341658669218482,
      "diff_std": 0.0,
      "diff_std_over_reference_std": 0.0,
      "atol": 1e-10,
      "rtol": 1e-08
    },
    {
      "label": "TFR Morlet freqs",
      "passed": true,
      "shape": [
        8
      ],
      "max_abs": 0.0,
      "rmse": 0.0,
      "relative_rmse": 0.0,
      "reference_std": 5.237229365663818,
      "diff_std": 0.0,
      "diff_std_over_reference_std": 0.0,
      "atol": 1e-10,
      "rtol": 1e-08
    },
    {
      "label": "TFR Morlet channels",
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
      "tmin": -0.5,
      "tmax": 1.0,
      "split_by": "none"
    },
    "tfr": {
      "condition": [
        "S  3"
      ],
      "fmin": 4,
      "fmax": 20,
      "n_freqs": 8,
      "freq_scale": "linear",
      "n_cycles_mode": "factor",
      "n_cycles_factor": 0.5,
      "decim": 4,
      "baseline_mode": "logratio",
      "baseline_tmin": "",
      "baseline_tmax": 0
    }
  }
}
```
