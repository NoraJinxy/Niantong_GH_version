# 念析错位发展与 AI 服务规划

> 整理日期: 2026-05-14  
> 目标: 讨论念析如何与 OpenNeuro 等公共数据平台错位发展, 并加入 AI 能力  
> 核心判断: 不要做另一个 OpenNeuro, 而要做 AI-ready 的 EEG 数据管理与分析服务平台。

## 1. 为什么只做 EEG 数据库会显小

如果定位为:

> EEG 数据库

会遇到几个问题:

- 公共数据本身可以免费获得。
- OpenNeuro、PhysioNet、TUH、BNCI 已经存在。
- 单纯存数据的商业价值弱。
- 数据越公开, 越难卖独占权。
- 国内私有 EEG 数据又受伦理和合规限制, 开放速度慢。

更好的定位是:

> 神经生理数据管理与分析服务平台, EEG-first。

也就是以 EEG 为切入口, 逐步扩展到:

- EEG / ERP。
- 睡眠 PSG。
- iEEG / ECoG。
- MEG。
- fNIRS。
- 眼动、行为数据、量表。
- MRI/fMRI 作为 EEG 溯源和多模态扩展。

## 2. 与 OpenNeuro 的错位发展

OpenNeuro 的强项:

- 公开数据归档。
- BIDS 标准。
- DOI。
- 版本和开放共享。
- 长期保存。

念析不要和它比「谁存得多」。更好的错位点是:

### 2.1 私有数据管理

OpenNeuro 偏公开归档。  
念析可以服务:

- 实验室私有 EEG 数据库。
- 医院科研项目数据。
- 企业 BCI/康复/睡眠项目。
- 多项目、多成员、多权限的数据资产管理。

关键能力:

- 项目权限。
- 被试和会话管理。
- 数据版本。
- 审计日志。
- 私有部署。
- 内网部署。
- 备份和恢复。

### 2.2 BIDS 转换和数据整理服务

国内大量 EEG 数据不是 BIDS。念析可以提供:

- BrainVision 到 BIDS/FIF。
- EDF 到 BIDS/FIF。
- Neuroscan 到 BIDS/FIF。
- EGI 到 BIDS/FIF。
- EEGLAB set 到 BIDS/FIF。
- MATLAB 私有结构整理。
- 事件码映射。
- participants / events / channels metadata 补全。

这是真实痛点, 也比单纯托管更容易收费。

### 2.3 自动质控 QC

上传后自动生成:

- 文件完整性检查。
- BIDS 合规检查。
- 采样率检查。
- 通道名和电极位置检查。
- 坏道检测。
- 工频噪声检测。
- 平坦通道检测。
- 高幅值伪迹检测。
- 事件码检查。
- trial 数统计。
- 可分析性评分。
- 修复建议。

OpenNeuro 主要是归档, 念析可以做「能不能分析、怎么修」。

### 2.4 标准分析模板

面向心理/认知科研, 提供:

- ERP 模板。
- P300 / N400 / MMN / P600 模板。
- PSD 频段功率模板。
- TFR 时频模板。
- ICA 去伪迹模板。
- 微状态模板。
- 连接分析模板。
- 统计和多重比较模板。
- 论文图表模板。

用户需要的不只是数据, 而是从数据到结果的稳定路径。

### 2.5 中文科研工作流

OpenNeuro 不覆盖中文科研场景。念析可以提供:

- 中文界面。
- 中文报告。
- 中文论文图表模板。
- 中文实验设计说明。
- 导师/学生协作。
- 项目归档。
- 国内伦理材料和数据管理清单。

### 2.6 私有部署和合规

医院、康复机构、临床研究数据不能随便上传公开平台。念析可以提供:

- 本地化部署。
- 内网版。
- 私有云版。
- 等保支持。
- 数据脱敏。
- 访问审计。
- 角色权限。
- 数据不出院/不出校。

### 2.7 精选数据集和教学

不做全量镜像, 做高质量精选:

- ERP 教学数据。
- BCI 教学数据。
- 睡眠数据。
- 情绪/面孔数据。
- 语言/听觉数据。
- 静息态数据。
- 认知任务数据。

卖点不是数据本身, 而是:

- 数据筛选。
- 中文注释。
- 可运行 pipeline。
- 教程。
- 结果复现。
- 示例报告。

### 2.8 模型和 benchmark 服务

对以下场景提供 benchmark:

- BCI 分类。
- 睡眠分期。
- 异常检测。
- 认知状态分类。
- 情绪识别。
- 跨数据集泛化。

可接入:

- MOABB。
- BNCI。
- OpenNeuro 精选 EEG。
- 自有私有数据。

## 3. AI 加入的必要性

现在就应该把 AI 加入念析, 但定位要准确:

> 不是做一个会聊天的 EEG 工具, 而是做 AI-ready EEG 数据与分析服务平台。

AI 负责:

- 理解研究目标。
- 帮助制定分析流程。
- 生成 pipeline。
- 解释 QC。
- 推荐统计方法。
- 生成报告。
- 检索数据集。
- 调用平台工具。

真正计算仍由:

- MNE。
- NumPy / SciPy。
- statsmodels。
- scikit-learn。
- 念析 pipeline engine。

AI 不应直接凭空给科研结论。

## 4. 推荐 AI 功能

| 功能 | 说明 | 优先级 |
|---|---|---:|
| AI 辅助制定分析流程 | 用户输入研究问题, 系统给出预处理、分析、统计、出图方案 | P0 |
| AI 生成 pipeline JSON | 将自然语言转成可执行节点流程 | P0 |
| AI 质控解释 | 解释坏道、噪声、事件码、采样率等问题并建议修复 | P0 |
| AI 统计顾问 | 推荐 t 检验、ANOVA、LMM、cluster permutation、多重比较 | P0 |
| AI 报告生成 | 自动生成 Methods、Results、图注、参数表 | P1 |
| AI 数据集检索 | 找适合 P300、睡眠、情绪、BCI 等任务的数据 | P1 |
| AI 接口 / MCP-style tools | 给外部大模型提供标准化 EEG 工具接口 | P1 |
| EEG foundation model | 自训练大模型或信号大模型 | P3, 不建议早期做 |

## 5. 正确的 AI 架构

推荐流程:

```text
用户自然语言
  -> AI 理解研究目标
  -> 生成分析计划 / pipeline spec
  -> 规则校验 + 参数检查 + 用户确认
  -> MNE / SciPy / statsmodels 确定性执行
  -> AI 解释结果、生成报告
  -> 保留完整 provenance
```

核心原则:

- AI 规划, 工具执行。
- AI 解释, 证据可追溯。
- 用户确认关键参数。
- 所有结果保留 provenance。
- 不允许 AI 绕过权限直接读取敏感原始数据。
- 不把大段 EEG 原始数组塞给大模型。

## 6. 给大模型的标准化工具接口

念析可以为外部 AI / Agent 提供一层 EEG 工具 API。

推荐工具:

```text
search_datasets(query, task, modality, license)
get_dataset_card(dataset_id)
get_subjects(dataset_id)
get_qc_summary(dataset_id)
get_channel_info(dataset_id)
get_event_summary(dataset_id)
propose_pipeline(research_question)
validate_pipeline(pipeline_json)
run_pipeline(pipeline_json)
get_task_status(task_id)
get_result_summary(result_id)
get_feature_table(result_id)
get_statistical_result(result_id)
export_figure(result_id)
get_provenance(result_id)
```

大模型优先读取:

- dataset card。
- metadata。
- QC summary。
- event summary。
- feature table。
- ERP peak table。
- PSD band power。
- TFR summary。
- 统计结果。
- 图表链接。

不应默认读取:

- 全量原始 EEG 数组。
- 可识别被试信息。
- 未授权私有项目。

## 7. AI 分析助手示例

用户输入:

```text
我想比较两组被试在 P300 时间窗的 ERP 差异, 并做多重比较校正。
```

系统输出:

1. 数据要求:
   - 至少两个组。
   - 有明确 target / standard 或条件标签。
   - 有通道位置和 events。
   - 每个被试 trial 数达到最低阈值。

2. 推荐预处理:
   - FIR bandpass 0.1-30Hz。
   - notch 50Hz。
   - 坏道检测与插值。
   - ICA 眼动/肌电成分处理。
   - epoch: -200ms 到 800ms。
   - baseline: -200ms 到 0ms。

3. ERP 分析:
   - 按 condition 平均。
   - 提取 P300: 250-450ms。
   - 推荐通道: Pz、CPz、Cz 或用户指定 ROI。

4. 统计:
   - 两组独立样本: independent t test 或 LMM。
   - 被试内条件: paired t test / repeated measures ANOVA。
   - 多通道多时间点: cluster permutation。
   - 多 ROI/多窗口: FDR 或 Bonferroni。

5. 图表:
   - ERP 波形图。
   - P300 时间窗阴影。
   - 地形图。
   - 组间差异图。
   - 统计显著性标记。

6. 生成 pipeline JSON:
   - load_data。
   - filter。
   - notch。
   - bad_channel_qc。
   - ica。
   - epoch。
   - baseline。
   - erp。
   - peak_extract。
   - statistics。
   - figure_export。

7. 输出报告:
   - Methods 草稿。
   - Results 草稿。
   - 参数表。
   - QC 附录。

## 8. 商业包装

### 8.1 AI 分析助手

面向:

- 心理学研究生。
- 认知神经实验室。
- 康复/临床科研团队。
- BCI 初创团队。

收费点:

- 分析流程设计。
- 一键 pipeline。
- 报告生成。
- 高级统计建议。

### 8.2 AI-ready EEG 数据库

提供:

- 精选公开 EEG 数据。
- 结构化索引。
- 质量标签。
- 数据集卡片。
- 可运行模板。
- 结果复现。

收费点:

- 快速访问。
- 高质量标注。
- 预处理缓存。
- 教学数据包。
- 企业 API。

### 8.3 EEG Analysis API

提供给:

- 大模型应用。
- 科研平台。
- 医疗软件。
- 企业算法团队。

能力:

- 数据集检索。
- QC。
- Pipeline。
- 特征提取。
- 统计。
- 图表。
- 报告。

### 8.4 私有部署版

面向:

- 医院。
- 高校。
- 康复机构。
- 企业研发部门。

能力:

- 本地数据不出内网。
- 本地 AI 或私有模型接入。
- 权限、审计、等保。
- 自有数据分析。

## 9. AI 落地路线

### 阶段 1: AI 应用层, 不训练自有大模型

周期: 2-4个月。

要做:

- EEG 数据 schema。
- pipeline JSON 规范。
- 标准分析模板库。
- 数据集卡片。
- RAG 文档库: BIDS、MNE、念析 wiki、统计指南。
- 大模型 API 接入。
- 工具调用白名单。
- 用户确认机制。

成果:

- AI 分析计划生成。
- AI pipeline 生成。
- AI QC 解释。
- AI 报告草稿。

### 阶段 2: AI + 数据平台深度结合

周期: 4-8个月。

要做:

- AI 数据集检索。
- AI 统计顾问。
- AI 图表生成建议。
- 多项目上下文。
- 用户历史分析方案复用。
- 分析模板市场。

### 阶段 3: 模型和 benchmark

周期: 8个月以后。

要做:

- MOABB / BNCI / OpenNeuro benchmark。
- 睡眠、BCI、情绪、认知分类基线模型。
- 模型评估报告。
- 跨数据集泛化。
- 可能接入 EEG foundation model。

## 10. 风险和边界

### 10.1 科研可信度

风险:

- AI 过度解释。
- AI 编造统计结论。
- 用户过度依赖建议。

应对:

- 所有结论绑定真实计算结果。
- 报告标明模型生成内容需要人工审核。
- 关键参数需用户确认。
- 提供 provenance。

### 10.2 数据安全

风险:

- 私有 EEG 数据进入第三方模型。
- 被试信息泄露。
- 大模型越权访问项目。

应对:

- 默认只给 AI metadata 和 summary。
- 原始数据访问走工具权限。
- 私有部署支持本地模型。
- 审计所有 AI 工具调用。

### 10.3 产品焦点

风险:

- 过早训练大模型, 烧钱且无明确收益。
- AI 功能变成噱头。

应对:

- 先做 AI 应用层。
- 先服务 workflow、QC、统计、报告。
- 不早期自研 EEG 大模型。

### 10.4 医疗和合规边界

风险:

- 用户将 AI 生成报告用于临床诊断。
- 平台宣传被理解为医疗器械或辅助诊断系统。
- AI 对癫痫、睡眠异常、精神疾病、康复效果做未经验证的判断。
- 私有 EEG 数据通过 AI 接口传给第三方模型。

应对:

- 早期明确定位为科研分析和数据管理平台。
- 报告中加入「非医疗诊断用途」说明。
- 医院/临床项目默认走私有部署或受控环境。
- AI 不直接输出诊断结论, 只输出数据质量、分析建议和科研解释草稿。
- 对涉及临床标签的数据设置更高权限和审计级别。

### 10.5 AI 可信执行原则

为了避免 AI 变成不可靠噱头, 念析的 AI 功能应遵守:

1. AI 负责规划, pipeline 负责执行。
2. AI 可以建议统计方法, 但统计结果必须由确定性统计模块计算。
3. AI 生成的 Methods / Results 必须引用实际参数、结果表和图表。
4. AI 不能绕过用户权限读取私有数据。
5. AI 默认读取 summary, 不读取全量原始 EEG。
6. 所有 AI 工具调用记录到审计日志。
7. 关键分析参数需要用户确认。
8. 输出报告保留数据版本、软件版本、pipeline 参数和运行记录。

## 11. 一句话定位

OpenNeuro 是:

> 公开神经数据档案馆。

念析可以成为:

> 面向中国实验室、医院和企业的 AI-ready EEG 数据工作台。

核心价值不是存数据, 而是:

> 找数据、整理数据、管理数据、制定分析、执行分析、解释结果、生成报告。

## 12. 参考方向

- FAIR 数据原则: Findable、Accessible、Interoperable、Reusable。
- BIDS / EEG-BIDS。
- MNE-Python。
- OpenNeuro / NEMAR。
- MOABB / BNCI。
- MCP-style tool interface: 为大模型提供标准工具能力。
