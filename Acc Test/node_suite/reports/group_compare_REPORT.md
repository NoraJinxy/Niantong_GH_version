# Group Compare 节点 MNE 对比报告

- 节点: `eeg/group/compare`
- 流水线: `Acc Test - node group compare paired`
- 结论: **PASS**
- 说明: A/B 两个 run 的 subject-level ERP unit_stack 进行配对逐点 t 检验。

## 指标

| 指标 | 通过 | shape | max_abs | relative_rmse | 备注 |
| --- | --- | --- | ---: | ---: | --- |
| Group Compare tmap | 是 | 63x1001 | 0.001116 | 6.827e-09 |  |
| Group Compare pmap | 是 | 63x1001 | 7.847e-07 | 3.288e-10 |  |
| Group Compare mean A | 是 | 63x1001 | 8.446e-12 | 1.101e-10 |  |
| Group Compare mean B | 是 | 63x1001 | 3.075e-12 | 6.36e-11 |  |
| Group Compare sig mask | 是 | 63x1001 | - | - |  |

## 节点参数

```json
{
  "compare": {
    "design": "paired",
    "method": "pointwise",
    "correction": "none",
    "tail": "two-sided",
    "alpha": 0.05,
    "condition": "S  3",
    "label_a": "run04",
    "label_b": "run11"
  }
}
```

## 原始指标

```json
{
  "case": "group_compare",
  "title": "Group Compare",
  "node_types": [
    "eeg/group/compare"
  ],
  "pipeline_name": "Acc Test - node group compare paired",
  "status": "PASS",
  "summary": "A/B 两个 run 的 subject-level ERP unit_stack 进行配对逐点 t 检验。",
  "metrics": [
    {
      "label": "Group Compare tmap",
      "passed": true,
      "shape": [
        63,
        1001
      ],
      "max_abs": 0.001116461757135312,
      "rmse": 8.193691130048961e-06,
      "relative_rmse": 6.82715912865651e-09,
      "reference_std": 4.341271959871676,
      "diff_std": 8.19369092624976e-06,
      "diff_std_over_reference_std": 1.8873940637646572e-06,
      "atol": 0.002,
      "rtol": 1e-05
    },
    {
      "label": "Group Compare pmap",
      "passed": true,
      "shape": [
        63,
        1001
      ],
      "max_abs": 7.846553643497955e-07,
      "rmse": 3.692937984413577e-08,
      "relative_rmse": 3.288415529799126e-10,
      "reference_std": 0.2605785585323094,
      "diff_std": 3.692906767571506e-08,
      "diff_std_over_reference_std": 1.4171951784412143e-07,
      "atol": 1e-06,
      "rtol": 1e-06
    },
    {
      "label": "Group Compare mean A",
      "passed": true,
      "shape": [
        63,
        1001
      ],
      "max_abs": 8.446174261291656e-12,
      "rmse": 8.588747412561257e-13,
      "relative_rmse": 1.1005630416088035e-10,
      "reference_std": 3.107511168164203e-05,
      "diff_std": 8.588746467766661e-13,
      "diff_std_over_reference_std": 2.7638666453580465e-08,
      "atol": 1e-10,
      "rtol": 1e-08
    },
    {
      "label": "Group Compare mean B",
      "passed": true,
      "shape": [
        63,
        1001
      ],
      "max_abs": 3.0751026928294532e-12,
      "rmse": 4.348925956542108e-13,
      "relative_rmse": 6.360041027951115e-11,
      "reference_std": 1.7991909394458152e-05,
      "diff_std": 4.3488434075398605e-13,
      "diff_std_over_reference_std": 2.417110553524345e-08,
      "atol": 1e-10,
      "rtol": 1e-08
    },
    {
      "label": "Group Compare sig mask",
      "passed": true,
      "shape": [
        63,
        1001
      ],
      "n_sig_reference": 5946,
      "n_sig_server": 5946
    }
  ],
  "params": {
    "compare": {
      "design": "paired",
      "method": "pointwise",
      "correction": "none",
      "tail": "two-sided",
      "alpha": 0.05,
      "condition": "S  3",
      "label_a": "run04",
      "label_b": "run11"
    }
  }
}
```
