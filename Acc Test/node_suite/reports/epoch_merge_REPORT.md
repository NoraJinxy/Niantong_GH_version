# Epoch Merge 节点 MNE 对比报告

- 节点: `eeg/epoch/merge`
- 流水线: `Acc Test - node epoch merge source recording`
- 结论: **PASS**
- 说明: 按原始记录合并 S3/S4 条件切出的 Epochs；样本数据、事件类型和顺序应与本地 concatenate_epochs 一致。

## 指标

| 指标 | 通过 | shape | max_abs | relative_rmse | 备注 |
| --- | --- | --- | ---: | ---: | --- |
| Epoch Merge source_recording | 是 | 60x64x1001 | 0 | 0 |  |
| Epoch Merge source_recording event_id | 是 |  | - | - |  |
| Epoch Merge source_recording channels | 是 |  | - | - | 64 |

## 节点参数

```json
{
  "epoch": {
    "conditions": [
      {
        "name": "S  3",
        "pattern": "S\\s*0*3\\b",
        "mode": "regex"
      },
      {
        "name": "S  4",
        "pattern": "S\\s*0*4\\b",
        "mode": "regex"
      }
    ],
    "tmin": -0.2,
    "tmax": 0.8,
    "split_by": "condition"
  },
  "merge": {
    "merge_scope": "source_recording"
  }
}
```

## 原始指标

```json
{
  "case": "epoch_merge",
  "title": "Epoch Merge",
  "node_types": [
    "eeg/epoch/merge"
  ],
  "pipeline_name": "Acc Test - node epoch merge source recording",
  "status": "PASS",
  "summary": "按原始记录合并 S3/S4 条件切出的 Epochs；样本数据、事件类型和顺序应与本地 concatenate_epochs 一致。",
  "metrics": [
    {
      "label": "Epoch Merge source_recording",
      "passed": true,
      "shape": [
        60,
        64,
        1001
      ],
      "max_abs": 0.0,
      "rmse": 0.0,
      "relative_rmse": 0.0,
      "reference_std": 0.0002618254280108787,
      "diff_std": 0.0,
      "diff_std_over_reference_std": 0.0,
      "atol": 1e-10,
      "rtol": 1e-08
    },
    {
      "label": "Epoch Merge source_recording event_id",
      "passed": true,
      "reference": [
        "S  3",
        "S  4"
      ],
      "server": [
        "S  3",
        "S  4"
      ]
    },
    {
      "label": "Epoch Merge source_recording channels",
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
        },
        {
          "name": "S  4",
          "pattern": "S\\s*0*4\\b",
          "mode": "regex"
        }
      ],
      "tmin": -0.2,
      "tmax": 0.8,
      "split_by": "condition"
    },
    "merge": {
      "merge_scope": "source_recording"
    }
  }
}
```
