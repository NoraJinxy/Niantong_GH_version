# Event Manager 节点 MNE 对比报告

- 节点: `eeg/preproc/event_manager`
- 流水线: `Acc Test - node event manager rules`
- 结论: **PASS**
- 说明: 按规则重命名 S4 并平移 S5；数据本体应不变，annotations 应完全一致。

## 指标

| 指标 | 通过 | shape | max_abs | relative_rmse | 备注 |
| --- | --- | --- | ---: | ---: | --- |
| Event Manager raw data | 是 | 64x310420 | 0 | 0 |  |
| Event Manager raw data channel_count | 是 |  | - | - | 64 |
| Event Manager annotations | 是 |  | - | - |  |

## 节点参数

```json
{
  "group_operations": [
    {
      "op": "rename",
      "sources": [
        "S  4"
      ],
      "target": "ACC_S4"
    },
    {
      "op": "shift",
      "sources": [
        "S  5"
      ],
      "delta_s": 0.01
    }
  ],
  "decision_version": 1
}
```

## 原始指标

```json
{
  "case": "event_manager",
  "title": "Event Manager",
  "node_types": [
    "eeg/preproc/event_manager"
  ],
  "pipeline_name": "Acc Test - node event manager rules",
  "status": "PASS",
  "summary": "按规则重命名 S4 并平移 S5；数据本体应不变，annotations 应完全一致。",
  "metrics": [
    {
      "label": "Event Manager raw data",
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
      "label": "Event Manager raw data channel_count",
      "passed": true,
      "common_channels": 64
    },
    {
      "label": "Event Manager annotations",
      "passed": true,
      "reference_count": 91,
      "server_count": 91,
      "reference_label_counts": {
        "New Segment/": 1,
        "S  5": 30,
        "ACC_S4": 30,
        "S  3": 30
      },
      "server_label_counts": {
        "New Segment/": 1,
        "S  5": 30,
        "ACC_S4": 30,
        "S  3": 30
      },
      "max_onset_diff_sec": 1.0000000031595846e-05,
      "max_duration_diff_sec": 0.0,
      "onset_atol": 0.0001,
      "duration_atol": 1e-06
    }
  ],
  "params": {
    "group_operations": [
      {
        "op": "rename",
        "sources": [
          "S  4"
        ],
        "target": "ACC_S4"
      },
      {
        "op": "shift",
        "sources": [
          "S  5"
        ],
        "delta_s": 0.01
      }
    ],
    "decision_version": 1
  }
}
```
