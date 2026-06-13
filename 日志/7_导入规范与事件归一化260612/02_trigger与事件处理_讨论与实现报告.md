# ELYS · EEG 事件 / Trigger 处理 —— 讨论、决策与实现报告

> 把"从 Letswave 的 econ 特殊处理问起,一路到 TFR 热图"这整段讨论收敛成一份报告。叙事 + 决策 + 落地 + 踩坑 + 待办,配套 `00_数据导入原则.md`(规范)/ `01_事件归一化_修改计划.md`(计划)。

| 项 | 内容 |
|---|---|
| 文档性质 | **过程报告**(放 `日志/`,非 wiki 现状规范) |
| 日期 | 2026-06-13 |
| 数据 | `elys_scripts/projects/02_erd_ers/data/`(econ/iRecorder `.bdf`,readme: label1=握拳 label0=放松) |
| 关联 | 本目录 00/01;memory `econ_bdf_import`、`mne_tfr_numpy_truthiness`;云端锁 mne==1.7.1 |

---

## 0. TL;DR

- **econ 的 BDF 早就支持**(标准 BDF+/TAL,MNE 原生读;876 事件已入 FIF)。真问题不是格式,是**事件多到没法切分**:econ 把 trial 序号烧进注释字符串 → 876 个"唯一事件",Epoch 选不出"类",且前端有 64 条硬上限。
- **解法**:Epoch 事件选择从"逐个挑字符串"改成"**自动识别分组 + 勾选**";分组名**忠实原始模板**(抹掉序号写成 `*`,如 `trial/cue_sent/index/*/clench_fist`),前缀不同的窗(mi/csp/rest)天然分开。
- **顺带定的产品方向**:Epoch **原子化**(只切分,baseline 交独立节点);终端用户只接触 condition、不碰正则/facet;长期对接 **BIDS + HED**。
- **TFR 节点**(并行会话新建)连踩三坑,已修:numpy 真值崩溃、缺 `h5io` 依赖、预览误路由到波形页。
- **待确认**:TFR 热图路由真机未验(用户反馈"没调用 TFR 视图");HED/QC/badge 冻结待做。

---

## 1. 缘起与定性:不是 BDF 的锅

起点是 Letswave `FLW_import_data.m` 对 iRecorder/econ `.bdf` 的特殊处理(嗅头部 115:123 字节 `iRecorder` → 换 reader)。核查结论:

- 手头 econ 样本是**标准 BDF+C**,事件在标准 **BDF Annotations(TAL)** 通道(不是 BioSemi Status 触发通道),头部已匿名(无 `iRecorder` 串)。MNE `read_raw_bdf` 原生解析进 `raw.annotations`,现有导入流程**全支持**(本机装 mne 实测:10 通道 @500Hz、876 事件入 canonical FIF)。
- 所以 **不需要照搬 Letswave 的设备特判**。详见 memory `econ_bdf_import`。

## 2. 真问题:事件太多 + UI 上限

- econ 注释把 trial 序号烧进字符串(`trial/cue_sent/index/7/clench_fist`)→ **876 条全唯一**;抹掉序号坍缩成 **15 类模板**、真正只有 **2 个任务类别**(clench_fist/relax_arm,各 40,共 80 trial = 20 train + 60 predict)。
- 前端"共 64 种事件"是**硬上限**(`pipeline/load_data.py` `EVENT_LABEL_MAX_PER_DATASET=64`,读到第 64 个不同标签就 break),既不是 2 也不是 876,纯计数假象。

## 3. Trigger 编码三种哲学 + 谁设计的 + 哪些格式中招

- **三种哲学**:① 整数码本(硬件触发 / GDF,需外部码表)② 扁平字符串标签(BrainVision `S1`)③ 结构化字符串(econ / LSL JSON / MNE `/` 标签)。econ = 第三种**被玩坏**的版本——把计数器塞进标识符。
- **谁设计的**:不是任何标准。EDF+/BDF+ 只规定注释是自由文本,内容随便写;econ 这套 `域/阶段/键/值` 是其 **BCI 软件作者 ad-hoc 自定义**(文件无框架签名;铁证:同一个 trial 序号键名居然三种 —— `idx`/`index`/`trial`,手搓 f-string 才会这样)。
- **哪些格式会中招**:自由文本事件 + 把实例数据塞进去的都会 ——

  | 格式 | 事件存法 | 中招? |
  |---|---|---|
  | EDF+/BDF+ 注释(TAL) | 自由文本 | 会(econ) |
  | LSL / XDF 标记流 | 自由文本(常塞 JSON) | 很容易 |
  | EEGLAB `.set` `event.type` | 字符串/数字 | 会 |
  | FIF / MNE annotations | 自由文本 | 会 |
  | BrainVision `.vmrk` | 类型+短码 | 一般不会 |
  | 硬件触发(BioSemi Status / CNT)、GDF | 整数码本 | 不会(反而太少) |

- **行业标准答案**:BIDS `events.tsv`(onset/duration/trial_type + sidecar)+ **HED**(Hierarchical Event Descriptors,受控分层词表,可校验、跨研究可比;SCORE 库给临床脑电)。TAL 还有个硬限制:注释有效长度约 40 字符。

## 4. 别人怎么解(软件横评,同一个 H01 显示几种)

| 工具 | 怎么挑/合并 | 形态 | 同一文件显示 |
|---|---|---|---|
| FieldTrip | 写 `trialfun` | 纯代码 | 不列表(写函数) |
| MNE-Python | `event_id` + `/` 标签 + 正则 | 代码 | **876**(实跑 `events_from_annotations`;且顺序乱:1,10,11…2) |
| EEGLAB | `pop_epoch` 选类型 / STUDY | 半 GUI+脚本 | ≈876(列表拖不完) |
| Brainstorm | GUI 手动 Merge / Group-by-name | 全 GUI·手动 | 876 组 |
| **ELYS(本项目)** | **自动识别分组 + 勾选** | **全 GUI·自动** | **15 → 勾 2 个完事** |

共同智慧:**没有工具敢盲目自动合并到底**——"什么算同一个 condition"是语义判断(如 mi/csp/rest 的 window 不能合)。ELYS 的做法 = 自动收成忠实分组、但全摆出让你勾,不替你过度合并。

## 5. 设计决策(用户拍板)

- **condition 统一模型**:一个参数 = 一组 `{name, pattern, mode}`;选已有事件=exact、填模式=contains/regex/template,一套引擎(`event_conditions.py`)。
- **忠实模板命名**:`propose_condition_groups` 把"只差数字"的合并,name 忠实显示模板、序号位写 `*`;前缀不同的窗天然不同组,不堆 `-2/-3`、不瞎编名。
- **Epoch 原子化**:移除节点内 baseline 校正(只切分),baseline 留给**独立节点**(MNE 把切分+基线合在一步,我们拆开)。
- **前端极简(persona=非工程师)**:自动分组 chips + 竖排成列 + Tmin/Tmax 一行两列;终端用户不碰正则/facet/876 串。
- **暂不做**:导入 QC 五项、litmus 导入警告、HED/badge、导入侧 condition 派生、TFR 时频节点(后发现已存在)。

## 6. 实现(已落地)

- 后端:
  - `engine/analysis/event_conditions.py`(新):`ConditionRule`(exact/contains/regex/template)、`parse_condition_rules`、`match_conditions`、`propose_condition_groups`(忠实模板+前缀消歧)、`summarize_event_vocabulary`(litmus,备用)、`rules_for_selection`(按勾选名运行时还原)。
  - `engine/analysis/epoching.py`:`run_epoch_segment` 改用 `rules_for_selection` + `baseline=None`(原子化)。
  - 节点 spec `eeg_epoch_segment.json`:`event_id`(event_select)→ `conditions`;删 `baseline_start/end`。
- 前端 `PipelinePage.vue`:event_select chips 喂"自动分组"、chip 池竖排、property-list 两列(数字参数 `field--half`);`types/index.ts` 不再需要 textarea(中途试过又撤)。
- 验证:本机 mne 实测(勾 clench_fist/relax_arm → 2 condition × 40 epoch)、`py_compile`、`vue-tsc` 全过。

## 7. TFR 踩坑链(并行会话新建的 TFR 节点带来的)

| # | 症状 | 真因 | 修法 | 验证 |
|---|---|---|---|---|
| 1 | truth value of an array ambiguous | `engine/io.py` `summarize_tfr` 的 `数组 or []`(tfr.freqs 是 ndarray)—— 存盘阶段触发,任何 TFR 运行都中 | 显式判 None | ✅ 已提交 922642f;**云端 mne 1.7.1 复现并验证** |
| 2 | h5io could not be imported | `AverageTFR.save` 走 HDF5,`requirements` 缺 h5io | 加 `h5io==0.2.5` + `h5py==3.11.0`(h5py 选 numpy-1.26 ABI 版) | ✅ h5io 在 1.7.1 venv 实测存读通;h5py 版本待云端 |
| 3 | 暂不支持 data_type=tfr 的时域曲线 | 双击节点一律开 `/observe/waveform`(波形),tfr 也被送去 | `PipelinePage.openNodeWaveform` 按 data_type 分流:tfr → `/observe/tfr`(参数名 `studyId`+`study_output_id`) | 🔶 vue-tsc 过,**真机未确认**(用户反馈"没调用 TFR 视图") |

- **mne 版本坑**:云端锁 `mne==1.7.1 / scipy==1.14.1 / numpy==1.26.4`,本机 1.12.1 会**掩盖版本差异 bug**;测 1.7.1 要建 venv + `scipy==1.14.1`(scipy≥1.15 删了 `sph_harm`,mne1.7.1 import 直接崩,正是 `get_mne_module` 在 guard 的)。详见 memory `mne_tfr_numpy_truthiness`。

## 8. 现状与待办

- **已落地待云端真机验**:condition 自动分组、Epoch 原子化、TFR 三修。
- **未决**:
  - **TFR 热图路由真机确认**(#3)—— 可能未重部署前端 / 入口不是"双击节点"。**当前头号待办**。
  - `split_by=按condition` 时 dispatcher 用 `epochs[name]` 字符串索引(`/`/`*` 有 MNE 层级标签隐患;`_derived_fif_filename` 对文件名已 sanitize,故存盘安全)。
  - `event_select` 机制在 Epoch/ERP 都换走后成**死代码**(`useEventSelectEditor` 等),待 PipelinePage 重构落定后清理。
- **冻结(future)**:HED + BIDS trial_type 衔接、公开数据 QC badge(三态/钉 schema 版本)、导入 QC 五项、导入侧 condition 派生。

## 9. 该更新的 wiki(详见报告末与对话)

- `9-00` / `9-02`:补本会话变更(condition 分组 / Epoch 原子化 / TFR 三修 / mne 版本坑)。
- `5-25 工作流节点路线图`:`tfr` 从「规划(M5)」→「已接」;Epoch 参数 `event_id`→`conditions`、删 baseline;批次 B 的"待做"措辞过期。
- `6-00 前端页面总览`:`/observe/tfr` 从「仅前端」→「接真数据(双模式)」。
- `8-00 功能模块总览` / `1-30 功能需求矩阵` / `1-50 阶段路线图`:M5 时频从「规划」→「部分接入」。

## 附:关键文件 / 常量 / 参考

- 文件:`engine/analysis/event_conditions.py`、`epoching.py`、`tfr.py`、`io.py`(`summarize_tfr`)、`pipeline/load_data.py`(`EVENT_LABEL_MAX_PER_DATASET=64`)、节点 `eeg_epoch_segment.json`/`eeg_analysis_tfr.json`、`requirements.txt`(h5io/h5py)、前端 `PipelinePage.vue`/`TfrPage.vue`/`WaveformDetailPage.vue`。
- 参考:BioSemi BDF 规范(biosemi.com/faq/file_format.htm、trigger_signals.htm);BioSemi 论坛 Status/触发偏移帖;EDF+ 规范(edfplus.info);HED(frontiersin 2016 奠基论文、hedtags.org、BIDS HED 附录、HED-SCORE Nature 2025);BIDS events 规范;FieldTrip trialfun、MNE events/merge_events、EEGLAB epochs/STUDY、Brainstorm EventMarkers 文档。
