# 公共 EEG 数据平台与商业使用分析

> 整理日期: 2026-05-14  
> 关注对象: OpenNeuro、NEMAR、MOABB、PhysioNet、TUH EEG 等公共 EEG 数据生态  
> 核心判断: 公共 EEG 数据本身不是最好的商业化对象, 数据整理、标准化索引、质控、分析流程、算力和报告才是更稳的商业价值。

## 1. 主要公共 EEG 数据平台

| 平台 | 主要数据 | 特点 | 对念析的价值 |
|---|---|---|---|
| OpenNeuro | BIDS 格式的人类神经影像, 含 EEG/MEG/iEEG | 开放、BIDS、DOI、可复现 | 最适合作为 BIDS/MNE 兼容和公开样例库 |
| NEMAR | OpenNeuro 上 EEG/MEG/iEEG/ECoG 的网关 | 更聚焦电生理数据检索和浏览 | 适合 EEG 数据检索和质量评估参考 |
| PhysioNet | 生理信号和临床数据, 含 EEG/睡眠/癫痫 | 临床、生理信号、算法训练 | 补充临床 EEG、睡眠、癫痫数据 |
| TUH EEG Corpus | Temple University 大规模临床 EEG | 大规模 EDF, 临床异常/癫痫 | 临床 EEG 和深度学习方向有价值 |
| BNCI Horizon | BCI 数据集, 运动想象/P300/SSVEP 等 | BCI benchmark 经典来源 | 补充脑机接口和分类任务 |
| MOABB | BCI benchmark 工具箱, 统一接入多个公开数据集 | 不是数据仓库, 是评测工具 | ML 工作台和 benchmark 参考 |
| DANDI | 神经生理数据, 偏 NWB/electrophysiology | 动物/侵入式电生理更多 | 中长期多模态/神经生理扩展 |
| IEEG.org | 癫痫相关 iEEG/ECoG/EEG | 临床癫痫和侵入式电生理 | 后续临床/癫痫方向可关注 |

## 2. OpenNeuro EEG 数据规模

按 2026-05-14 对 OpenNeuro 官方 GraphQL API 的 `modality: "eeg"` 查询估算:

| 口径 | 数量 |
|---|---:|
| EEG 数据集 | 约 414 个 |
| 被试数 | 约 23,468 人 |
| 数据容量 | 约 29.2 TB |
| TiB 口径 | 约 26.6 TiB |

这里的 EEG 包括纯 EEG 数据集, 也包括 EEG + MRI/行为/其他模态的多模态数据集。

### 2.1 容量结构

| 容量段 | 数据集数 | 数量占比 | 容量 | 容量占比 |
|---|---:|---:|---:|---:|
| <1GB | 43 | 10.4% | 0.02TB | 0.1% |
| 1-10GB | 112 | 27.1% | 0.57TB | 2.0% |
| 10-100GB | 211 | 51.0% | 7.11TB | 24.4% |
| 100GB-1TB | 45 | 10.9% | 9.40TB | 32.2% |
| >1TB | 3 | 0.7% | 12.11TB | 41.4% |

结论:

- 数据非常「头重」。
- 只有 48 个 100GB 以上数据集, 数量约 11.6%, 但占容量约 73.6%。
- 做产品不需要全量镜像, 应先精选高价值数据集。

### 2.2 数据类型大致构成

以下分类基于标题、metadata、任务字段做启发式归类, 不是 OpenNeuro 官方分类。

| 类型 | 数据集占比 | 容量占比 | 说明 |
|---|---:|---:|---|
| 认知/视觉/注意任务 | 17.1% | 5.9% | oddball、attention、视觉认知等 |
| BCI/运动/SSVEP/P300 | 12.8% | 5.9% | 可用于分类、BCI benchmark |
| 记忆/学习 | 12.6% | 46.5% | 被 PEERS 等超大数据集拉高 |
| 听觉/语言 | 11.6% | 4.8% | speech、music、MMN、语义等 |
| 静息态 | 7.7% | 11.1% | resting-state、基线 EEG |
| 睡眠 | 5.1% | 5.1% | REM/NREM、ear-EEG、睡眠监测 |
| 情绪/面孔/压力 | 4.6% | 3.2% | emotion、face、affect |
| 临床/疾病 | 3.1% | 0.9% | OpenNeuro 中相对少, PhysioNet/TUH 更强 |
| TMS/刺激 | 1.0% | 4.3% | 少但单集较大 |
| 其他/metadata 不明确 | 24.4% | 12.5% | 需要人工再筛 |

### 2.3 纯 EEG 与多模态

| 类型 | 数据集占比 | 容量占比 |
|---|---:|---:|
| 纯 EEG | 85.5% | 85.2% |
| EEG + 其他模态 | 14.5% | 14.8% |

多模态数据通常包括 EEG + MRI/fMRI/行为数据。对溯源、跨模态验证和高级科研更有价值, 但处理成本也更高。

## 3. 什么 EEG 数据更有价值

### 3.1 高价值数据特征

高价值公共 EEG 数据通常具备:

1. 原始数据完整: 有 raw EEG、events、channels、electrodes、participants、任务说明。
2. BIDS 规范好: 能被 MNE-BIDS / MNE 稳定读取。
3. 被试数足够: 30 人以上有统计分析价值, 100 人以上适合 benchmark。
4. 任务范式清楚: ERP、P300、视觉注意、语言、记忆、睡眠、静息态、BCI。
5. 有 DOI / 论文 / README: 便于理解实验设计和复现实验。
6. 有行为/临床/量表标签: 有利于统计建模和机器学习。
7. 有良好 license: CC0 或明确允许商业复用。
8. 可运行标准 pipeline: 上传后能自动完成 QC、预处理、分析和出图。

### 3.2 价值层估算

按容量、被试量、任务清晰度、是否有 DOI/论文、是否为原始数据等做产品视角粗分:

| 价值层 | 数据集占比 | 容量占比 | 用途 |
|---|---:|---:|---|
| 高价值 | 约 42.5% | 约 87.8% | benchmark、算法验证、产品示例、论文复现 |
| 中价值 | 约 41.8% | 约 11.1% | 教学、兼容性测试、普通分析流程验证 |
| 低价值/小众 | 约 15.7% | 约 1.1% | 小样本、metadata 弱、任务小众、需人工清洗 |

更保守地看, 真正适合念析早期重点适配的数据集大约是 15%-25%。其余可以作为普通示例、兼容测试或长尾数据。

## 4. OpenNeuro 数据的商业使用

### 4.1 基本判断

OpenNeuro 当前公开数据主要按 CC0 / Public Domain 发布。CC0 通常允许:

- 复制。
- 下载。
- 再分发。
- 改编。
- 商业使用。
- 收费提供访问、存储、整理、分析等服务。

但要注意:

- 不能声称这些公共数据是自己的独占资产。
- 不能暗示 OpenNeuro 官方授权或背书, 除非有正式授权。
- 不能去掉来源信息, 尤其历史数据可能不是 CC0。
- 不能忽视隐私、伦理撤回、数据更新和错误修正。

### 4.2 你可以做的事

对念析而言, 可以:

- 下载部分有价值的 OpenNeuro EEG 数据。
- 导入自己的后台数据库。
- 调整数据组织形式。
- 建立索引、标签、任务分类、质量评分。
- 生成 FIF、QC 报告、预处理缓存、特征表、图表和报告。
- 对软件服务、算力服务、数据整理服务、API 服务收费。

更准确的商业表达应是:

> 念析提供基于公开 EEG 数据的结构化索引、快速访问、预处理、分析和报告服务。

而不是:

> 念析出售 OpenNeuro 数据。

### 4.3 必须保留的元数据

每个导入数据集建议保留:

| 字段 | 用途 |
|---|---|
| OpenNeuro dataset id | 源数据集唯一标识 |
| OpenNeuro URL | 原始页面 |
| Snapshot / version tag | 版本追踪 |
| Dataset DOI | 引用和论文复现 |
| 原作者 / contributor | 来源说明 |
| License | 商业使用判断 |
| README / CHANGES | 原始说明 |
| HowToAcknowledge | 致谢和引用 |
| 导入日期 | 内部追踪 |
| 处理记录 | 是否转换、清洗、重采样、生成派生数据 |

### 4.4 衍生数据标记

如果只是改变数据库组织形式, 可以标记为 indexed/cache。

如果做了以下处理, 应明确标记为 derivative:

- 格式转换。
- 滤波。
- 重采样。
- 通道重命名。
- 事件清洗。
- 坏道标记。
- ICA。
- Epoch 切分。
- 统计特征提取。
- 图表和报告生成。

建议数据层分三层:

1. 原始 OpenNeuro snapshot: 只读保存。
2. 念析结构化索引: dataset card、搜索、标签、质量评分。
3. 念析派生结果: FIF、QC、features、figures、reports。

## 5. MOABB 背景和价值

MOABB 全称 Mother of All BCI Benchmarks, 本质是开源 BCI/EEG benchmark 工具箱, 不是大型数据托管平台。

### 5.1 性质

- 开源项目。
- 许可证 BSD-3-Clause。
- 挂在 NeuroTechX 生态下。
- NeuroTechX 是 non-profit 组织。
- 没有明显企业版/订阅式商业模式。

### 5.2 影响力

MOABB 在 EEG-BCI 算法评测领域影响力较大:

- 支持大量开放 EEG 数据集。
- 覆盖 Motor Imagery、P300/ERP、SSVEP、c-VEP、Resting State 等。
- 提供 within-session、cross-session、cross-subject 评估。
- 基于 MNE + scikit-learn。
- 常用于 BCI 算法横向比较。

### 5.3 对念析的启发

MOABB 不适合作为数据管理主线, 但适合作为:

- ML 工作台 benchmark 入口。
- BCI 示例数据来源。
- 统一数据集接口参考。
- 跨数据集模型评估参考。

念析主线仍应是:

> BIDS / MNE / OpenNeuro / NEMAR / 本地私有数据管理

MOABB 放在机器学习 benchmark 和公开样例数据模块更合适。

## 6. MNE-Python 商业使用与许可声明

MNE-Python 是软件库, 不是数据平台。其许可证是 BSD-3-Clause, 通常允许:

- 商业软件使用。
- 云服务中调用。
- 闭源产品集成。
- 修改后再分发。
- 基于 MNE 输出分析结果并收费。

需要做到:

- 保留 MNE 的 copyright 和 license notice。
- 不暗示 MNE 官方背书念析。
- 如果发布本地部署版或安装包, 提供 THIRD_PARTY_NOTICES。
- MNE 自带或下载的示例数据集要单独查看数据 license。

### 6.1 网站服务中的声明方式

网站页脚增加:

```text
开源许可 / Open Source Licenses
```

链接到:

```text
/legal/open-source-licenses
```

页面中列出:

```text
MNE-Python

念析的部分脑电数据处理功能使用 MNE-Python。

Copyright © MNE-Python contributors.
License: BSD 3-Clause License
Project: https://mne.tools/
Source: https://github.com/mne-tools/mne-python
License text: https://github.com/mne-tools/mne-python/blob/main/LICENSE.txt
```

并附完整 BSD-3-Clause 原文。

用户协议或关于页增加:

```text
念析不是 MNE-Python、OpenNeuro 或其维护机构的官方产品, 也不代表其官方认可或背书。
```

## 7. 对念析的数据策略建议

不要做全量 OpenNeuro 镜像。建议:

1. 第一阶段精选 20-50 个高价值 EEG 数据集。
2. 准备 1-3TB 本地缓存。
3. 建立 dataset card、license、DOI、snapshot、任务、被试量、质量评分。
4. 生成标准 pipeline: QC、预处理、ERP/PSD/TFR、统计、出图。
5. 保留原始 snapshot, 派生结果单独标记。
6. 对外卖服务、分析、算力、报告和接口, 不卖公共数据独占权。

## 8. 商业使用的风险边界

公共 EEG 数据可以为念析提供样例、benchmark 和分析模板, 但商业使用时需要避免以下风险:

| 风险 | 表现 | 建议 |
|---|---|---|
| 许可风险 | 未逐个检查 license, 忽略 CC-BY/NC/ND 等条款 | 每个 dataset 建立 license 字段和导入检查 |
| 来源风险 | 只写「来自 OpenNeuro」, 未保留 DOI、版本、作者 | 保留 OpenNeuro id、URL、snapshot、DOI、README、HowToAcknowledge |
| 独占表述风险 | 把公开数据包装成念析独占资产 | 对外卖服务和分析能力, 不卖数据独占权 |
| 派生混淆风险 | 处理后数据仍被展示为原始数据 | 原始 snapshot 和念析 derivative 分层管理 |
| 撤回风险 | 原平台下架或修正后, 念析继续分发旧数据 | 建立同步、下架和版本更新机制 |
| 隐私风险 | 数据中残留身份信息或用户尝试重识别 | 用户协议禁止重识别, 数据导入做脱敏检查 |
| 医疗使用风险 | 用户把公开 EEG 分析当作临床诊断依据 | 明确科研/教学/算法验证用途, 不宣传诊断能力 |

更稳的产品表述:

```text
念析提供公开 EEG 数据的结构化索引、质量评估、快速访问、预处理缓存、分析模板和可复现报告服务。原始数据版权和许可遵循各来源数据集页面所列条款。
```

不建议的表述:

```text
念析出售 OpenNeuro EEG 数据。
念析拥有这些公开 EEG 数据。
念析是 OpenNeuro 官方授权平台。
```

## 9. 参考链接

- OpenNeuro: https://openneuro.org/
- OpenNeuro API: https://docs.openneuro.org/api.html
- OpenNeuro FAQ: https://docs.openneuro.org/faq
- AWS OpenNeuro Registry: https://registry.opendata.aws/openneuro/
- NEMAR: https://www.nemar.org/
- PhysioNet: https://physionet.org/
- TUH EEG Corpus: https://isip.piconepress.com/projects/tuh_eeg/
- BNCI Horizon: https://bnci-horizon-2020.eu/database/data-sets
- MOABB: https://moabb.neurotechx.com/
- MOABB GitHub: https://github.com/NeuroTechX/moabb
- MNE-Python: https://mne.tools/
- MNE-Python License: https://github.com/mne-tools/mne-python/blob/main/LICENSE.txt
