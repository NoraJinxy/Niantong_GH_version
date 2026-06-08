# 数据集页面与生命周期设计（可入库 wiki 设计稿草案）

> **性质：设计稿 / 目标态**。本稿是 `日志/2_meeting260607/文件管理目标方案.md`（28 节）+ UI 基准 `design/mockups/datasets-workbench-demo.html` 收敛而成，供回改 wiki 与各轨道落地引用的**单一口径来源**。
> 生成 2026-06-08 +08:00。**判断"是否已实现"以代码为准（P0）**；本稿凡未标 ✅ 的能力均为**尚未落地的目标态 / 规划**。
>
> 搬运指引（每节末「→ 落点」给出该节内容将切进哪个 wiki 页）：本稿不直接发布，而是拆分回改到 `4-20 / 4-70 / 4-60 / 4-00 / 3-25 / 3-50 / 6-05 / 6-20`，并（建议）新建 `6-25 数据集工作台与生命周期页面设计`。

---

## 0. 阅读前的大白话铺垫（黑话钉死）

第一次出现的术语先用大白话说清（遵 `0-20 文档编写规范` §8）：

- **数据资产 / 数据集（DatasetAsset）**：用户视角的"一份数据集"，有独立物理身份，不属于某个研究项。下文"数据集"= 它。
- **研究项（Study）**：拿数据集跑分析的工作空间；研究项**不拥有**数据集，靠"挂载"引用它。
- **采集记录（Recording）**：一个人做一次某任务采的一段脑电（subject/session/task/run 四件套唯一）。
- **记录版本（RecordingVersion）**：这段脑电上传了第几回（重传 = 加版本不覆盖）。
- **canonical FIF / 标准 FIF**：平台把原始数据转成的 MNE-ready 工作副本（MNE 是常用脑电分析库）。**不是权威源**，权威是原件，可清理可重建。
- **sidecar**：BIDS 元数据小文件——`_channels.tsv`(通道)、`_events.tsv`(事件)、`_eeg.json`(采集参数)。
- **provenance**：来源记录（这份 FIF 从哪个原件、什么参数、什么转换器版本转来）。
- **append-only**：只追加不改——新内容写新文件，旧文件永不动。
- **派生数据（DerivedDataset）**：Pipeline 跑出来的清洗 / epochs / ERP / 图 / 报告，**属研究项**，不进数据集文件管理器。

---

## 1. 现状对账：为什么要重构（三大债）

> **性质：现状**（事实源 `backend/app/routers/datasets.py` + `services/studies.py` + 服务器实拍）。

| # | 债 | 危害 | 目标 |
|---|---|---|---|
| **债 1 · 三根存储** | `studies.py` 同时建 `storage/studies/`(新) + legacy `studies/{id}/` data_root，datasets 又是第三根 | 数据散三处、指针乱 | **两根**（§2） |
| **债 2 · FIF 双写** | `generate_canonical_fif` 把 canonical 落 derivatives 后**再 `copy2` 一套**到 legacy fifdata（`legacy_mirror=True`），一条记录 10 文件、5 个是镜像；`recordings.fif_path` 指旧镜像、`dataset_files.canonical_fif` 指新副本 → **指针分裂** | 删一处另一处变野指针 | **单写 + 单指针**（§4） |
| **债 3 · raw_bids 幽灵 + 一文件多行** | working/ 下无 `raw_bids/` 目录，但 `create_dataset_file_records` 给每原件写 `raw_source`+`original_upload`+`raw_bids_data` 三行（含幽灵 `raw_bids_*`）；sub-093 三件套 → 9 行 | 用户看到不存在的"文件"、计数虚胖 | **一物理文件 = 一行 = 一角色**，raw_bids 纯逻辑视图（§3 §5） |

> 三债的代码证据见 `文件管理目标方案.md` §2 表（含行号）。文档回改时**须显式点名这三债为现状债**，不可继续把"双写 / 幽灵行 / 三根"当成果陈述。

→ 落点：`4-20`（新增「现状债」小节，仿 4-60 顶部 warning）、`4-00 §6 落地快照`。

---

## 2. 两根存储与目标磁盘布局

> **性质：目标态**（现状仍三根，删 legacy data_root 属规划，调试期 DROP 重建、不写迁移）。

**设计原则**：① 数据归资产、产物归研究项；② 磁盘只存真实字节（只有原件 + derivatives 真实 sidecar，raw_bids 永不落盘）；③ 状态是 DB 标志不是目录。

```text
mnt/elys_data/storage/
├── datasets/{asset_id}/                         ← 数据本体（资产；状态在 DB）
│   ├── sourcedata/original_uploads/sub-XXX/upload-{seq}/   📥 原件 append-only 只读
│   │     ├── manifest.json
│   │     └── sub093.vhdr / .eeg / .vmrk                    （原名保留）
│   ├── derivatives/canonical-fif/sub-XXX/[ses-XX/]eeg/     ✨ FIF 唯一副本 append-only
│   │     └── sub-XXX_task-YYY_eeg.fif · _eeg.json · _channels.tsv · _events.tsv · _provenance.json
│   ├── qc/                                                 🔧 质检（归数据集，F-3）
│   └── releases/v{semver}.json                             📌 发布冻结清单（零复制）
└── studies/{study_id}/                          ← 分析产物（研究项）
    └── executions/ derived/ exports/ previews/ temp/ pipeline_snapshots/
```

**两点关键变化**：① **取消 `versions/{label}/`（旧 working）层**——数据直接挂 asset 根、发布进 `releases/`；② **删 legacy `studies/{id}/` data_root 整支**（`source_uploads`/`fifdata`/`upload_staging`/`validation`/`bids_exports`/`pipeline*` 等，调试期 DROP）。

决策（已拍板，设计源 §17）：upload 目录**按被试归组**（F-1）；sidecar **与 FIF 旁放**（F-2）；qc **归数据集**（F-3）；旧调试数据 **DROP 重建**（F-5）；发布快照 **清单零复制**（F-6，靠 append-only 天然不可变）。

→ 落点：`4-00 §3 目标目录`、`4-20 §1 标准目录`、`4-20 §8 落地状态`。

---

## 3. 三条数据线

> **性质：目标态**（A 已实现落盘，B 现状双写、目标单写，raw_bids 投影现状已有端点）。

| 线 | 内容 | 归属 | 永久性 | 前端呈现 |
|---|---|---|---|---|
| **A 原始** | 上传原貌（.vhdr/.eeg/.vmrk、EDF…） | 资产 | **永久只读**（保险柜底片） | 📥 桶，可下载，标"永久保留" |
| **B 标准 FIF** | MNE-ready 工作副本 + sidecar | 资产 | 可清理可重建 | ✨ 桶，可下载，标"可重建" |
| **C 派生** | 清洗/epochs/ERP/图/报告 | **研究项** | 按 retention 清理 | 「派生数据/结果」页，**不在数据集文件管理器** |

**数据集文件管理器只管 A + B 两桶**；C 属研究项产物归 `studies/`。

**线 A 四规则**（append-only 的命运线）：① 新人/新任务 = 新建采集记录；② 同段脑电重传 = 加版本不覆盖（旧版转 `replaced`）；③ 原始文件只增不改（永写新 `upload-{seq}`）；④ 完全相同上传被 SHA-256 指纹拦截（409 不重复入库）。

**线 B 目标（修双写债）**：砍 `legacy_fif_base`/镜像 `copy2` 段、`ensure_fifdata_dataset_files` 下线；只写 `derivatives/canonical-fif/`；`recordings.fif_path` 与 `dataset_files.canonical_fif.storage_uri` **同指唯一副本**。

→ 落点：`4-20 §2/§4`、`4-00 §4 三层`、`6-20 §四（两桶呈现）`。

---

## 4. raw_bids 逻辑视图 + 文件角色精简

> **性质：目标态**（bids-tree 端点 ✅ 已存在，但当前仍建 `raw_bids_*` 幽灵行喂它；目标是删行、纯投影）。

**raw_bids（按 BIDS 规范命名的标准目录树）= 纯逻辑视图**：不落盘、不写 `dataset_files` 行（连逻辑行都不建，比"逻辑行 storage_uri 指回原件"更进一步——彻底消灭幽灵）。要按 BIDS 浏览 → `GET /dataset-assets/{id}/bids-tree` 从 `original_upload` + `sidecar` 行**实时投影**；要 BIDS 包带走 → 按需导出到 `studies/{study}/exports/`，导完可清（F-4）。

**目标角色表**（`dataset_files` 一物理文件一行，设计源 §10）：

| 角色 | 留/删 | 物理 | 说明 |
|---|---|---|---|
| `original_upload` | ✅ 留 | ✓ | 原件，**一文件一行** |
| `canonical_fif` | ✅ 留 | ✓ | 唯一 FIF，`recordings.fif_path` 同指 |
| `canonical_fif_provenance` | ✅ 留 | ✓ | provenance.json |
| `sidecar`（channels/events/eeg_json） | ✅ 留 | ✓ | 真实生成的 BIDS 元数据 |
| `qc_report` / `*_summary` | ✅ 留 | ✓ | 质检摘要 |
| `raw_source` | ❌ 删 | — | 与 `original_upload` 重复 |
| `raw_bids_data` | ❌ 删 | — | 幽灵，改 bids-tree 现算 |
| `raw_bids_channels/events/eeg_json/electrodes/coordsystem` | ❌ 删 | — | 幽灵，同上 |

**效果**：sub-093 三件套 **9 行 → 3 行**；"原始上传"计数 = 真实物理原件数（不再是 6=3 文件×2 角色）。

→ 落点：`4-70 §2 角色表`（替换为精简表）、`4-60`（强化"不建 raw_bids 行 + 实时投影"、纠偏 §6 旧 MVP 建议）、`4-20 §5 登记角色`。

---

## 5. 状态模型：两条正交轴 + 一个粒度

> **性质：目标态 / 规划**。`dataset_versions.state`(draft/published/withdrawn) ✅ schema 已有、`dataset_assets.visibility`(private/shared/public) ✅ schema 已有且发布自动 private→shared 部分逻辑已落；**`disclosure_level` 字段 ❌ 未加**；**两轴解耦 + 两道访问闸的业务流转 🚧 未接通**。

核心：状态不是单轴，而是 **两条正交轴 + 一个粒度**。**"发布"管不可变性、"可见性"管谁能看，两者解耦——发布 ≠ 公开**。取消 working/草稿 叫法，发布前统称"未发布"。

### 5.1 轴 A · 发布状态（管不可变性 / 生命周期）

| 状态 | 可变? | 含义 |
|---|---|---|
| **未发布 unpublished**（=schema `draft`） | ✅ 可增删改 | 还在整理；**强制私有** |
| **已发布 published** | ❌ 不可变 | 冻结快照、可引用、可注册 DOI；可见性转为**可自由配置** |
| **已撤回 withdrawn** | ❌ 终态 | 需管理员审核；保留墓碑（F-9，见 3-25） |

### 5.2 轴 B · 可见性范围（管谁能看）

| 范围 | 谁能看 | 何时可设 |
|---|---|---|
| **🔒 私有 private** | 仅 owner + 本研究项团队 | 任何时候（未发布时**锁定为此**） |
| **👥 共享 shared** | owner + 被授权协作者 / 研究项 | **仅已发布后** |
| **🌐 公共 public** | 所有人（可检索） | **仅已发布后** |

### 5.3 粒度 C · 可见程度（管能看多深；共享/公共才有意义）

| 粒度 | 别人能看到 | 别人不能 |
|---|---|---|
| **仅描述 metadata**（默认，F-10 保守） | 名称/描述/被试数/任务/引用信息/存在性 | **下载或使用数据本身**（可"申请访问"） |
| **数据本身 data** | 描述 + 下载/使用原始数据与 FIF | — |

### 5.4 组合与四条铁律

```text
未发布  →  必然 私有 · 数据仅本研究项可用            （可变，建设期）
已发布  →  私有 / 共享+仅描述 / 共享+数据本身 / 公共+仅描述 / 公共+数据本身
```

1. **发布前只能私有**（`state=draft ⟹ visibility=private`，service 强制，DB 可加 CHECK）。
2. **发布 ≠ 公开**：发布只"冻结 + 可引用"，默认仍私有；之后 owner 再单独开可见性。
3. **可见性与发布解耦**：发布后可在 私有/共享/公共 间切换，也能收回。
4. **两道访问闸**：能看到"它存在/它的描述"（元数据闸）≠ 能"拿到数据"（数据闸，需粒度=数据本身）。

### 5.5 对各层影响（落地分工）

- 🗄️ **DB**：沿用 `dataset_versions.state` + `dataset_assets.visibility`；**新增 `dataset_assets.disclosure_level ∈ {metadata,data}`（默认 metadata）**；新增约束 `state=draft ⟹ visibility=private`。极致按人授权 → `dataset_members`（范围+粒度，F-7 下一阶段；MVP 用 asset 级 visibility+disclosure）。
- ⚙️ **后端**：发布只冻结、不动 visibility；`PATCH /dataset-assets/{id}` {visibility, disclosure_level} **仅已发布后允许**（未发布设 shared/public → 403）；**数据闸**（`/dataset-files/{id}/download`、bids-tree 数据节点、打包下载）额外校验 `disclosure_level=data` 且在授权范围。
- 🖥️ **前端**：徽章拆两层 + 粒度小标（见 §7）；未发布可见性置灰锁"私有"；发布后出现「分享设置」面板。
- 📁 **文件存储**：**几乎零影响**——可见性/粒度是 DB+API 访问控制，不改物理布局，文件不因 private/shared/public 或 metadata/data 搬动（反证设计原则"状态是 DB 标志不是目录"）。

→ 落点：`3-25`（新增两轴+粒度节，标规划）、`3-50 §2 枚举表`（加 `disclosure_level` 行）、`6-05 §4.1`（粒度分级）、`6-25`（UI 映射）。

---

## 6. 描述结构化与可编辑性

> **性质：目标态 / 规划**。描述结构化字段、addenda 表、审核流 **均未落地**。

| 内容 | 未发布 | 已发布 |
|---|---|---|
| **描述信息** | ✅ 自由编辑 | 🔒 **只读**（冻结，保引用稳定） |
| **补充信息 addenda** | — | ✅ 可**追加**，但**需管理员审核**后才公开 |
| **负责人/出身/主研究项/使用许可** | ⛔ 不展示（私有草稿） | ✅ 展示 |
| **如何引用 / DOI** | ⛔ 不展示 | ✅ 展示（多格式 + 复制） |
| **文件数 / 标准 FIF 数** | ✅ 概览只读 | ✅ 概览只读 |

规则要点（设计源 §4.6 + F-12/F-13/F-14）：

1. **描述发布前可改、发布后只读**（类比论文已发表元数据冻结）。
2. **发布后仅可追加补充信息**（勘误/补充/新被试说明），**走管理员审核**（复用撤回审核 admin 流，写 `audit_events`），通过才对外可见。
3. **发表元数据（出身/引用/许可）只在发布后出现**。
4. **文件数 + 标准 FIF 数在概览只读可见**（借鉴 OpenNeuro 在 metadata 展示文件数），属"一览概要"，**不可在概览编辑**——注意区分于 L3 折叠区的全套文件统计。
5. **描述结构化**——拆「**摘要 / 采集方法 / 使用说明 / 伦理**」四段（借鉴 PhysioNet Abstract/Methods/Usage Notes/Ethics），DB 用 `dataset_versions.metadata_json.description{abstract,methods,usage,ethics}`。

**各层增量**：DB 加 `dataset_addenda`(或 `metadata_json.addenda[]`，含 `content/submitted_by/status(pending|approved|rejected)/reviewed_by/reviewed_at`)；后端 `PATCH 描述`仅未发布允许、`POST …/addenda`(pending)+管理员 review；前端描述卡 未发布=「✎编辑」/已发布=「🔒只读 + ＋添加补充信息(需审核)」；**文件存储零影响**。

→ 落点：`3-25`（新增描述可编辑性节，标规划）、`6-05`（描述结构化分级）、`6-25`（描述卡 UI）。

---

## 7. 前端呈现映射 + 双层徽章

> **性质：目标态**（两桶/双层徽章/分享设置面板均规划；上一轮已落"单轴可见范围徽章"为过渡态）。

| 后端存储 | 前端桶 | 呈现 |
|---|---|---|
| `original_upload` | 📥 你上传的原始数据 | 按被试/记录归组，可下载，标"永久保留" |
| `canonical_fif` | ✨ 平台标准格式 | 可直接分析，可下载，标"可重建" |
| provenance/sidecar/qc | 🔧 技术与元数据（折叠） | 默认隐藏（L3） |
| bids-tree | 「按 BIDS 浏览/导出」 | 可选，**非文件桶** |

- **状态徽章（双层 + 粒度小标）**：**发布状态**(未发布/已发布) + **可见性**(🔒私有/👥共享/🌐公共) + **粒度小标**(仅描述/含数据)；未发布时可见性锁定"私有"置灰。
  > 演进说明：上一轮（2026-06-07）落地的是**单轴可见范围徽章**（B 方案）作为过渡；本稿目标态升级为**双层 + 粒度**。保留上一轮两条铁律——可见范围是发表级严肃决策、**徽章只读不提供随意下拉**（改可见性一律走发布/撤回流程，与"发布≠随意"一致）。
- **计数**：用聚合字段（`subject_count`/`recording_count`/`task_codes`/`total_duration_seconds`）或去重物理文件数，**禁用 `countFilesByRole` 多角色计数**（否则虚胖）。
- **下一步指引**：未发布显示「继续导入 / 发布」；已发布显示「分享设置 / 开新版本 / 申请撤回」。
- **他人视角**：metadata-only 显示描述卡 +「申请访问数据」；data 级直接可下载。
- **铁律**：前端只拿 `dataset_file_id`，**绝不接触** `file://`/`s3://`/服务器绝对路径。

→ 落点：`6-05 §4.1+§6.2`（升级徽章口径）、`6-25`（完整 UI）、`6-20 §四`。

---

## 8. 页面信息架构：状态自适应 tab

> **性质：目标态 / 规划**。tab 随发布状态自适应、发布/管理分享按钮、数据详情合并视图 **均未实现**。UI 基准 `design/mockups/datasets-workbench-demo.html`。

设计：tab 结构随**版本发布状态 + 角色**自适应——发布前=建设工具集，发布后=只读消费视图。

### 8.1 状态 × 角色矩阵

| 视角 | 发布前（未发布·私有锁定） | 发布后（已发布） |
|---|---|---|
| **owner** | 概览 · 采集记录 · 导入 · 质控 + 概览「**发布**」按钮 | 概览 · 数据详情 + 概览「**管理/分享**」按钮（数据详情含质控报告段） |
| **协作者 editor** | 同 owner（可编辑），无发布按钮 | 概览 · 数据详情（只读） |
| **他人 · 公共+含数据** | 不可见 | 概览 · 数据详情（只读·可下载） |
| **他人 · 公共+仅描述** | 不可见 | 概览 +「**申请访问**」 |

### 8.2 关键规则

1. **tab 跟版本状态**：发布后「开新版本」→ 新草稿 → 该版本回到"发布前"四 tab（导航随版本生命周期循环）。
2. **发布 = 概览里的按钮**（非 tab）：点击弹"发布前检查清单"modal（SemVer / 会冻结什么 / 发布≠公开 / 联动质控状态，不阻塞）。
3. **管理/分享 = 概览里的按钮**（发布后 owner-only）：设可见性 + 粒度、申请撤回、开新版本、加补充信息。**位置与"发布"按钮一致**（概览右上）——"治理动作永远在概览右上"。
4. **导航不蒸发**：发布后 采集记录/导入/质控 收纳进"数据详情"（子段/按钮），给过渡提示。
5. **质控双向可达**：每条记录有质控徽章，点徽章跳质控详情。
6. **命名一致性（F-15 待定）**：发布前"采集记录" vs 发布后"数据详情"是同一份数据两个名——建议统一，或明确"数据详情 = 采集记录 + 文件 + 质控报告 的只读超集"。

### 8.3 各 tab / 区职责

- **概览**：科学名片（结构化描述 + 一览概要 + 文件数/FIF 只读 + 发布后:出身/引用/许可）+ 状态相关按钮。
- **采集记录（发布前）**：按被试浏览 + 管理，文件 2 桶展开，质控徽章。
- **导入（发布前）**：加数据；发布后消失（开新版本才回来）。
- **质控（发布前=tab / 发布后=数据详情内段或按钮）**：质量总览（N 条·M 通过·K 待审）+ 按记录详情。
- **数据详情（发布后）**：采集记录 + 文件 + 质控报告 的只读合并视图。

→ 落点：建议**新建 `6-25 数据集工作台与生命周期页面设计`**（承载整套 IA）；`6-20 §四` 加目标态小节并链 6-25；`3-25` 链 6-25。

---

## 9. 文件元数据 schema（目标）

> **性质：目标态**（manifest/provenance 现已产出但含 `legacy*` 字段；release 清单 🚧 骨架）。

- **manifest.json**（每 upload-{seq} 一份）：`importJobId/datasetAssetId/subject/task/session/run/uploadSeq/sourceFormat/files[]/checksum(合并 sha256)/status/createdAt/updatedAt`。
- **provenance.json**（每条 FIF 一份）：`sourceFormat`、`SourceOriginalUpload`、`SourceEvents/Channels`、`SourceSHA256`、`canonicalFifPath`、`validation(nChannels/sfreq/duration/nEvents)`、`GeneratedBy/At`、`ConversionParams`。**目标删除 `legacy*` 字段**（legacyFifDir/legacySidecars/legacy_mirror）。
- **releases/v{semver}.json**（发布冻结清单，新增）：`versionLabel/state/publishedAt/publishedBy/contentHash/versionDoi/files[{datasetFileId,role,logicalPath,sha256}]`。靠 append-only：清单指向的文件版本永不被后续编辑改动 → 天然不可变、无需拷贝。

→ 落点：`4-70 §5 provenance`、`4-20`（schema 附录）、`3-25`（release 清单）。

---

## 10. 端到端示例（sub093-erp）

> **性质：目标态去重后**（对比旧实现 18 行 → 8 行）。

```text
datasets/54e92097/                                （未发布 · 🔒私有锁定 · 粒度 metadata）
  sourcedata/original_uploads/sub-093/upload-001/  manifest.json · sub093.vhdr/.eeg/.vmrk
  derivatives/canonical-fif/sub-093/eeg/           sub-093_task-erp_eeg.fif · _eeg.json · _channels.tsv · _events.tsv · _provenance.json
  qc/ import_qc.json
  （releases/ 为空——还没发布）
```

DB（目标去重）：`subjects` 1 行 · `recordings` 1 行 · `recording_versions` 1 行 · `dataset_files` = 原件 3(original_upload) + FIF 1 + provenance 1 + sidecar 3 = **8 行**（旧实现 18 行）。

前端：📥 原始数据(下载) · ✨ 标准 FIF(下载) · 🔧 技术与元数据(5,折叠) · 徽章「未发布·🔒私有(锁定)」· 下一步「继续导入/发布」。

**发布后**：写 `releases/v1.0.0.json` 冻结清单，`state=published`、可见性解锁可单独设（私有/共享/公共 + 粒度）；**磁盘文件一个不动**。

---

## 11. 对外接口 / 依赖契约

> **性质：转录目标方案 §13/§20**——文档须如实登记**状态**，不得把规划写成已实现。前端永远只拿 `dataset_file_id`。

### 11.1 访问与下载（设计源 §13）

| 能力 | 端点 | 状态 |
|---|---|---|
| 资产文件索引（可按 role 筛） | `GET /dataset-assets/{id}/files` | ✅ |
| BIDS 树视图（逻辑投影） | `GET /dataset-assets/{id}/bids-tree` | ✅（目标：从 original_upload+sidecar 投影，不喂幽灵行） |
| 单文件 元数据/预览/下载 | `GET /dataset-files/{id}/metadata\|preview\|download` | ✅（download 目标加数据闸校验 `disclosure_level=data`） |
| 派生下载 | `GET /studies/{id}/derived-datasets/{id}/download` | ✅ |
| 按被试/全部/BIDS 打包下载 | `GET /dataset-assets/{id}/archive?scope=subject\|all\|bids` | ❌ **规划** |

### 11.2 发布状态轴（设计源 §20）

| 转换 | 端点 | 状态 |
|---|---|---|
| 创建 → 未发布 | `POST /dataset-assets/bootstrap` | ✅ |
| 未发布 → 已发布 | `POST /dataset-assets/{id}/publish` {semver} | 🚧 骨架（`publish_dataset_version`） |
| 开新内容轮 | `POST /dataset-assets/{id}/versions` | ✅ |
| 申请撤回 / 审核 / 紧急下架 | `…/withdraw` · `…/withdraw/review` · `…/emergency-takedown` | ✅ |

### 11.3 可见性 / 粒度 / 描述轴（设计源 §20，**仅已发布后**）

| 转换 | 端点 | 状态 |
|---|---|---|
| 设可见性 / 粒度 | `PATCH /dataset-assets/{id}` {visibility, disclosure_level} | 🚧（`disclosure_level` 字段需加；未发布调用 → 403） |
| 授权/收回协作者 | `POST/DELETE …/members`（F-7） | 🚧 |
| 提交 / 审核 补充信息 | `POST …/addenda` · `POST …/addenda/{id}/review` | 🚧 |

### 11.4 数据契约（DB 字段，文档须标"已有/需加"）

- ✅ 已有：`dataset_versions.state`、`dataset_assets.visibility`、`recordings.fif_path`/`current_version_id`、`recording_versions.status`、`dataset_files.{file_role,logical_path,storage_uri,sha256}`。
- 🆕 需加（规划）：`dataset_assets.disclosure_level`、`dataset_versions.metadata_json.description{abstract,methods,usage,ethics}`、`dataset_addenda`(或 `metadata_json.addenda[]`)、约束 `state=draft ⟹ visibility=private`。

---

## 12. 决策记录速查（F-1…F-15，已拍板 / 待定）

| 编号 | 决策 | 状态 |
|---|---|---|
| F-1 | upload 按被试归组 | 拍板 |
| F-2 | sidecar 与 FIF 旁放 | 拍板 |
| F-3 | qc 归数据集 | 拍板 |
| F-4 | raw_bids 纯逻辑视图（硬链接留未来） | 拍板 |
| F-5 | 旧调试数据 DROP 重建 | 拍板 |
| F-6 | 发布快照清单零复制 | 拍板 |
| F-7 | 按人共享分两步（MVP 发布+挂载 / 真授权 `dataset_members` 下一阶段） | 拍板 |
| F-8 | 可变性绑发布状态（未发布可变、已发布不可变） | 拍板 |
| F-9 | 撤回保留为第 4 终态 | 拍板（建议待确认） |
| F-10 | 可见粒度默认 metadata | 拍板 |
| F-11 | metadata-only 申请访问 | 建议做（二期） |
| F-12 | 发布后描述只读 + 可追加（需管理员审核） | 拍板 |
| F-13 | 概览展示文件数/FIF 数（只读） | 拍板 |
| F-14 | 描述结构化（摘要/方法/使用/伦理） | 拍板 |
| F-15 | 发布前"采集记录" vs 发布后"数据详情"命名一致性 | **待定** |

---

## 13. 验收清单（落地后据此核对）

- [ ] 一条 BrainVision 记录导入后，FIF **只在 derivatives 一处**，fifdata 不再产生。
- [ ] `dataset_files` 无 `raw_source`/`raw_bids_*` 行；原件按物理文件 1:1。
- [ ] `recordings.fif_path` 与 `dataset_files.canonical_fif` 指向同一 URI。
- [ ] working/ 与 legacy `studies/{id}/` 不再被写入。
- [ ] "原始上传"计数 = 真实物理原件数（示例 3，不是 6）。
- [ ] 徽章出现两轴 + 粒度小标；未发布时可见性锁"私有"置灰；无 working/草稿字样。
- [ ] 未发布想设 shared/public → 403；私有↔共享切换零文件变动。
- [ ] 发布产生 `releases/v{semver}.json`，磁盘数据文件零搬动；发布后描述只读、addenda 走审核。
- [ ] `bids-tree` 在无物理 raw_bids 目录下正常返回 BIDS 视图。
- [ ] metadata-only 数据集：描述可见、download 返回 403 +「可申请访问」。
- [ ] 前端不出现任何服务器绝对路径 / `file://` / `s3://`。

---

## 14. 搬运到 wiki 的总落点表

| 本稿节 | 切进的 wiki 页 | 动作 |
|---|---|---|
| §1 三大债 | `4-20`（新增现状债小节）、`4-00 §6` | 🚧 改 |
| §2 两根存储 | `4-00 §3`、`4-20 §1/§8` | 🚧 改 |
| §3 三条数据线 | `4-20 §2/§4`、`4-00 §4` | 🚧 改 |
| §4 raw_bids 逻辑视图 + 角色精简 | `4-70 §2`、`4-60`、`4-20 §5` | 🚧 改 |
| §5 两轴 + 粒度 | `3-25`(新增节)、`3-50 §2`、`6-05 §4.1` | 🚧 改 |
| §6 描述结构化/可编辑性 | `3-25`(新增节)、`6-05` | 🚧 改 |
| §7 前端呈现 + 双层徽章 | `6-05 §4.1/§6.2`、`6-20 §四` | 🚧 改 |
| §8 状态自适应 tab | **`6-25`（建议新建）**、`6-20`、`3-25` | 🆕 新建 + 🚧 改 |
| §9 元数据 schema | `4-70 §5`、`4-20`、`3-25` | 🚧 改 |
| §11 接口契约 | `4-20 §13`、`3-25`、`6-25` | 🚧 改 |
| 全稿落档 | `9-00`(周概览) + `9-02`(明细) | 🆕 新增条目 |
