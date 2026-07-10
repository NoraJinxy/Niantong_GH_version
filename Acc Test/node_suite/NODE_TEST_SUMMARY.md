# ELYS 节点输出 vs MNE 本地复算一致性总表

本表汇总 `Acc Test` 中已有节点测试与本次补充的 `node_suite` 测试。`已有` 表示对应独立报告/产物已在仓库中；`PASS/FAIL/SKIP` 来自本次自动复算结果。

| 节点类型 | 节点 | 测试入口 | 结果 |
| --- | --- | --- | --- |
| `eeg/data/load` | LoadData | 已有 test1 | PASS（已有报告） |
| `eeg/filter/apply` | Filter(notch/bandpass) | 已有 test1 + sub009_bandpass | PASS（已有报告） |
| `eeg/preproc/resample` | Resample | 已有 sub009_preproc_nodes | PASS（已有报告） |
| `eeg/preproc/rereference` | Re-reference | 已有 sub009_preproc_nodes | PASS（已有报告） |
| `eeg/preproc/channel_location` | Ch Loc Assign | 已有 sub009_preproc_nodes | PASS（已有报告） |
| `eeg/preproc/bad_channels` | Bad Channels | 已有 sub009_preproc_nodes | PASS（已有报告） |
| `eeg/preproc/artifact_mark` | Artifact Mark | node_suite/artifact_mark | PASS |
| `eeg/preproc/event_manager` | Event Manager | node_suite/event_manager | PASS |
| `eeg/preproc/event_remap` | Event Remap | node_suite/event_remap | PASS |
| `eeg/ica/compute` | Compute ICA | 已有 test_ica_consistency | PASS（已有报告） |
| `eeg/ica/apply` | Apply ICA | 已有 test_ica_consistency | PASS（已有报告） |
| `eeg/ica/iclabel` | ICLabel | node_suite/iclabel | PASS |
| `eeg/epoch/segment` | Epoch | 已有 test1 + node_suite/epoch_reject | PASS |
| `eeg/epoch/merge` | Epoch Merge | node_suite/epoch_merge | PASS |
| `eeg/epoch/baseline` | Baseline | 已有 test1 | PASS（已有报告） |
| `eeg/epoch/reject` | Reject Trials | node_suite/epoch_reject | PASS |
| `eeg/analysis/erp` | ERP Average | 已有 test1 + node_suite/group_average | PASS |
| `eeg/analysis/tfr` | TFR | node_suite/tfr | PASS |
| `eeg/analysis/psd` | PSD | node_suite/psd | PASS |
| `eeg/group/merge` | Group Merge | node_suite/group_average/group_compare | PASS |
| `eeg/group/average` | Grand Average | node_suite/group_average | PASS |
| `eeg/group/compare` | Group Compare | node_suite/group_compare | PASS |

## 本次补充测试明细

- `event_remap`: **PASS** - 按规则重命名 S3、删除 S4；数据本体应不变，annotations 应完全一致。
- `event_manager`: **PASS** - 按规则重命名 S4 并平移 S5；数据本体应不变，annotations 应完全一致。
- `artifact_mark`: **PASS** - 坏段只写 BAD_ annotation，坏道只写 info['bads']，信号样本不应改变。
- `epoch_reject`: **PASS** - Raw→Epoch 后按 MNE drop_bad 阈值法剔除；高阈值用来验证不误剔。
- `epoch_merge`: **PASS** - 按原始记录合并 S3/S4 条件切出的 Epochs；样本数据、事件类型和顺序应与本地 concatenate_epochs 一致。
- `psd`: **PASS** - 按条件选择 Epochs 后调用 MNE compute_psd，并跨 epoch 求均值。
- `tfr`: **PASS** - 按条件选择 Epochs 后调用 MNE Morlet TFR，并应用同一基线校正。
- `iclabel`: **PASS** - mark 模式校验 ICLabel 分类 metadata；该模式不改信号，后端可能复用上游 raw 文件而不产生新 FIF。
- `group_average`: **PASS** - 三名被试各自 Epoch→ERP 后按 subject 堆叠，再沿 unit 轴求均值。
- `group_compare`: **PASS** - A/B 两个 run 的 subject-level ERP unit_stack 进行配对逐点 t 检验。
