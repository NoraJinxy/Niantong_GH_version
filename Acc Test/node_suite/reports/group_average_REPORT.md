# Group Merge + Grand Average 节点 MNE 对比报告

- 节点: `eeg/group/merge, eeg/group/average`
- 流水线: `Acc Test - node group merge average`
- 结论: **PASS**
- 说明: 三名被试各自 Epoch→ERP 后按 subject 堆叠，再沿 unit 轴求均值。

## 指标

| 指标 | 通过 | shape | max_abs | relative_rmse | 备注 |
| --- | --- | --- | ---: | ---: | --- |
| Group Merge unit_stack | 是 | 3x63x1001 | 2.325e-11 | 6.138e-11 |  |
| Grand Average evoked mean | 是 | 63x1001 | 1.471e-11 | 1.497e-10 |  |
| Grand Average times | 是 | 1001 | 2.98e-09 | 2.261e-10 |  |
| Group Average unit count | 是 |  | - | - |  |

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
  "erp": {
    "condition": [
      "S  3"
    ]
  },
  "group_merge": {
    "group_label": "A"
  },
  "grand_average": {
    "weighted": false
  }
}
```

## 原始指标

```json
{
  "case": "group_average",
  "title": "Group Merge + Grand Average",
  "node_types": [
    "eeg/group/merge",
    "eeg/group/average"
  ],
  "pipeline_name": "Acc Test - node group merge average",
  "status": "PASS",
  "summary": "三名被试各自 Epoch→ERP 后按 subject 堆叠，再沿 unit 轴求均值。",
  "metrics": [
    {
      "label": "Group Merge unit_stack",
      "passed": true,
      "shape": [
        3,
        63,
        1001
      ],
      "max_abs": 2.324668495895521e-11,
      "rmse": 1.4859108124825956e-12,
      "relative_rmse": 6.137638339556105e-11,
      "reference_std": 5.565944419026039e-05,
      "diff_std": 1.485910757872313e-12,
      "diff_std_over_reference_std": 2.669647136239866e-08,
      "atol": 1e-10,
      "rtol": 1e-08
    },
    {
      "label": "Grand Average evoked mean",
      "passed": true,
      "shape": [
        63,
        1001
      ],
      "max_abs": 1.470735943513539e-11,
      "rmse": 1.1683175435731142e-12,
      "relative_rmse": 1.4970833901102127e-10,
      "reference_std": 3.107511168164203e-05,
      "diff_std": 1.168315293006526e-12,
      "diff_std_over_reference_std": 3.759649538755226e-08,
      "atol": 1e-10,
      "rtol": 1e-08
    },
    {
      "label": "Grand Average times",
      "passed": true,
      "shape": [
        1001
      ],
      "max_abs": 2.9802322831784522e-09,
      "rmse": 2.9802322398398266e-09,
      "relative_rmse": 2.2614309427848547e-10,
      "reference_std": 0.2889636655359978,
      "diff_std": 3.512464780970458e-17,
      "diff_std_over_reference_std": 1.215538560689005e-16,
      "atol": 1e-08,
      "rtol": 1e-08
    },
    {
      "label": "Group Average unit count",
      "passed": true,
      "server_units": 3
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
    "erp": {
      "condition": [
        "S  3"
      ]
    },
    "group_merge": {
      "group_label": "A"
    },
    "grand_average": {
      "weighted": false
    }
  }
}
```
