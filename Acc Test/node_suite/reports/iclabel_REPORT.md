# ICLabel 节点 MNE 对比报告

- 节点: `eeg/ica/iclabel`
- 流水线: `Acc Test - node ICLabel mark`
- 结论: **PASS**
- 说明: mark 模式校验 ICLabel 分类 metadata；该模式不改信号，后端可能复用上游 raw 文件而不产生新 FIF。

## 指标

| 指标 | 通过 | shape | max_abs | relative_rmse | 备注 |
| --- | --- | --- | ---: | ---: | --- |
| ICLabel node completed | 是 |  | - | - |  |
| ICLabel mode | 是 |  | - | - |  |
| ICLabel component count | 是 |  | - | - |  |
| ICLabel excluded count | 是 |  | - | - |  |

## 节点参数

```json
{
  "params": {
    "action": "mark",
    "prob_threshold": 0.8,
    "remove_eye": true,
    "remove_muscle": true,
    "remove_heart": true,
    "remove_line_noise": true,
    "remove_channel_noise": true
  },
  "iclabel_metadata": {
    "notes": [
      "未检测到平均参考；ICLabel 训练于平均参考数据，建议上游先做平均参考（Re-reference 全选）以提升分类准确度。"
    ],
    "action": "mark",
    "method": "iclabel",
    "components": [
      {
        "index": 0,
        "label": "other",
        "category": "other",
        "excluded": false,
        "probability": 0.9783
      },
      {
        "index": 1,
        "label": "eye blink",
        "category": "eye",
        "excluded": true,
        "probability": 0.8984
      },
      {
        "index": 2,
        "label": "eye blink",
        "category": "eye",
        "excluded": true,
        "probability": 0.9834
      },
      {
        "index": 3,
        "label": "other",
        "category": "other",
        "excluded": false,
        "probability": 0.5934
      },
      {
        "index": 4,
        "label": "eye blink",
        "category": "eye",
        "excluded": false,
        "probability": 0.547
      },
      {
        "index": 5,
        "label": "eye blink",
        "category": "eye",
        "excluded": false,
        "probability": 0.693
      },
      {
        "index": 6,
        "label": "other",
        "category": "other",
        "excluded": false,
        "probability": 0.9565
      },
      {
        "index": 7,
        "label": "eye blink",
        "category": "eye",
        "excluded": true,
        "probability": 0.997
      },
      {
        "index": 8,
        "label": "other",
        "category": "other",
        "excluded": false,
        "probability": 0.5257
      },
      {
        "index": 9,
        "label": "channel noise",
        "category": "channel_noise",
        "excluded": false,
        "probability": 0.4322
      }
    ],
    "ica_method": "picard",
    "n_excluded": 3,
    "label_counts": {
      "eye": 5,
      "other": 4,
      "channel_noise": 1
    },
    "n_components": 10,
    "prob_threshold": 0.8,
    "remove_categories": [
      "channel_noise",
      "eye",
      "heart",
      "line_noise",
      "muscle"
    ],
    "excluded_components": [
      1,
      2,
      7
    ]
  }
}
```

## 原始指标

```json
{
  "case": "iclabel",
  "title": "ICLabel",
  "node_types": [
    "eeg/ica/iclabel"
  ],
  "pipeline_name": "Acc Test - node ICLabel mark",
  "status": "PASS",
  "summary": "mark 模式校验 ICLabel 分类 metadata；该模式不改信号，后端可能复用上游 raw 文件而不产生新 FIF。",
  "metrics": [
    {
      "label": "ICLabel node completed",
      "passed": true,
      "status": "completed",
      "dataset_count": 1
    },
    {
      "label": "ICLabel mode",
      "passed": true,
      "params_action": "mark",
      "metadata_action": "mark"
    },
    {
      "label": "ICLabel component count",
      "passed": true,
      "n_components": 10,
      "components": 10
    },
    {
      "label": "ICLabel excluded count",
      "passed": true,
      "n_excluded": 3,
      "excluded": [
        1,
        2,
        7
      ]
    }
  ],
  "params": {
    "params": {
      "action": "mark",
      "prob_threshold": 0.8,
      "remove_eye": true,
      "remove_muscle": true,
      "remove_heart": true,
      "remove_line_noise": true,
      "remove_channel_noise": true
    },
    "iclabel_metadata": {
      "notes": [
        "未检测到平均参考；ICLabel 训练于平均参考数据，建议上游先做平均参考（Re-reference 全选）以提升分类准确度。"
      ],
      "action": "mark",
      "method": "iclabel",
      "components": [
        {
          "index": 0,
          "label": "other",
          "category": "other",
          "excluded": false,
          "probability": 0.9783
        },
        {
          "index": 1,
          "label": "eye blink",
          "category": "eye",
          "excluded": true,
          "probability": 0.8984
        },
        {
          "index": 2,
          "label": "eye blink",
          "category": "eye",
          "excluded": true,
          "probability": 0.9834
        },
        {
          "index": 3,
          "label": "other",
          "category": "other",
          "excluded": false,
          "probability": 0.5934
        },
        {
          "index": 4,
          "label": "eye blink",
          "category": "eye",
          "excluded": false,
          "probability": 0.547
        },
        {
          "index": 5,
          "label": "eye blink",
          "category": "eye",
          "excluded": false,
          "probability": 0.693
        },
        {
          "index": 6,
          "label": "other",
          "category": "other",
          "excluded": false,
          "probability": 0.9565
        },
        {
          "index": 7,
          "label": "eye blink",
          "category": "eye",
          "excluded": true,
          "probability": 0.997
        },
        {
          "index": 8,
          "label": "other",
          "category": "other",
          "excluded": false,
          "probability": 0.5257
        },
        {
          "index": 9,
          "label": "channel noise",
          "category": "channel_noise",
          "excluded": false,
          "probability": 0.4322
        }
      ],
      "ica_method": "picard",
      "n_excluded": 3,
      "label_counts": {
        "eye": 5,
        "other": 4,
        "channel_noise": 1
      },
      "n_components": 10,
      "prob_threshold": 0.8,
      "remove_categories": [
        "channel_noise",
        "eye",
        "heart",
        "line_noise",
        "muscle"
      ],
      "excluded_components": [
        1,
        2,
        7
      ]
    }
  }
}
```
