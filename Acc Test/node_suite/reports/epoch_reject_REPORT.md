# Reject Trials 节点 MNE 对比报告

- 节点: `eeg/epoch/reject`
- 流水线: `Acc Test - node epoch reject threshold`
- 结论: **PASS**
- 说明: Raw→Epoch 后按 MNE drop_bad 阈值法剔除；高阈值用来验证不误剔。

## 指标

| 指标 | 通过 | shape | max_abs | relative_rmse | 备注 |
| --- | --- | --- | ---: | ---: | --- |
| Reject Trials epochs | 是 | 30x64x1001 | 0 | 0 |  |
| Reject Trials epochs event_id | 是 |  | - | - |  |
| Reject Trials epochs channels | 是 |  | - | - | 64 |

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
  "reject": {
    "method": "threshold",
    "reject_peak_to_peak": 100000,
    "flat": ""
  }
}
```

## 原始指标

```json
{
  "case": "epoch_reject",
  "title": "Reject Trials",
  "node_types": [
    "eeg/epoch/reject"
  ],
  "pipeline_name": "Acc Test - node epoch reject threshold",
  "status": "PASS",
  "summary": "Raw→Epoch 后按 MNE drop_bad 阈值法剔除；高阈值用来验证不误剔。",
  "metrics": [
    {
      "label": "Reject Trials epochs",
      "passed": true,
      "shape": [
        30,
        64,
        1001
      ],
      "max_abs": 0.0,
      "rmse": 0.0,
      "relative_rmse": 0.0,
      "reference_std": 0.00035758549694216336,
      "diff_std": 0.0,
      "diff_std_over_reference_std": 0.0,
      "atol": 1e-10,
      "rtol": 1e-08
    },
    {
      "label": "Reject Trials epochs event_id",
      "passed": true,
      "reference": [
        "S  3"
      ],
      "server": [
        "S  3"
      ]
    },
    {
      "label": "Reject Trials epochs channels",
      "passed": true,
      "common_channels": 64
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
    "reject": {
      "method": "threshold",
      "reject_peak_to_peak": 100000,
      "flat": ""
    }
  }
}
```
