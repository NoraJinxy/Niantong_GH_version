# Artifact Mark 节点 MNE 对比报告

- 节点: `eeg/preproc/artifact_mark`
- 流水线: `Acc Test - node artifact mark`
- 结论: **PASS**
- 说明: 坏段只写 BAD_ annotation，坏道只写 info['bads']，信号样本不应改变。

## 指标

| 指标 | 通过 | shape | max_abs | relative_rmse | 备注 |
| --- | --- | --- | ---: | ---: | --- |
| Artifact Mark raw data | 是 | 64x310420 | 0 | 0 |  |
| Artifact Mark raw data channel_count | 是 |  | - | - | 64 |
| Artifact Mark annotations | 是 |  | - | - |  |
| Artifact Mark bad channels | 是 |  | - | - |  |

## 节点参数

```json
{
  "bad_segments": [
    {
      "onset": 1.0,
      "duration": 0.25,
      "source": "acc_test"
    }
  ],
  "bad_channels": [
    "Fp1"
  ],
  "channel_action": "mark",
  "decision_version": 1
}
```

## 原始指标

```json
{
  "case": "artifact_mark",
  "title": "Artifact Mark",
  "node_types": [
    "eeg/preproc/artifact_mark"
  ],
  "pipeline_name": "Acc Test - node artifact mark",
  "status": "PASS",
  "summary": "坏段只写 BAD_ annotation，坏道只写 info['bads']，信号样本不应改变。",
  "metrics": [
    {
      "label": "Artifact Mark raw data",
      "passed": true,
      "shape": [
        64,
        310420
      ],
      "max_abs": 0.0,
      "rmse": 0.0,
      "relative_rmse": 0.0,
      "reference_std": 0.0002472447475860969,
      "diff_std": 0.0,
      "diff_std_over_reference_std": 0.0,
      "atol": 1e-10,
      "rtol": 1e-08
    },
    {
      "label": "Artifact Mark raw data channel_count",
      "passed": true,
      "common_channels": 64
    },
    {
      "label": "Artifact Mark annotations",
      "passed": true,
      "reference_count": 92,
      "server_count": 92,
      "reference_label_counts": {
        "New Segment/": 1,
        "BAD_acc_test": 1,
        "S  5": 30,
        "S  4": 30,
        "S  3": 30
      },
      "server_label_counts": {
        "New Segment/": 1,
        "BAD_acc_test": 1,
        "S  5": 30,
        "S  4": 30,
        "S  3": 30
      },
      "max_onset_diff_sec": 0.0,
      "max_duration_diff_sec": 0.0,
      "onset_atol": 0.0001,
      "duration_atol": 1e-06
    },
    {
      "label": "Artifact Mark bad channels",
      "passed": true,
      "reference": [
        "Fp1"
      ],
      "server": [
        "Fp1"
      ]
    }
  ],
  "params": {
    "bad_segments": [
      {
        "onset": 1.0,
        "duration": 0.25,
        "source": "acc_test"
      }
    ],
    "bad_channels": [
      "Fp1"
    ],
    "channel_action": "mark",
    "decision_version": 1
  }
}
```
