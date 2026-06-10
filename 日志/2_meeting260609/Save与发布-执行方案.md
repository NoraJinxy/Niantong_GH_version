# Save 保留策略 + 发布权限 · 执行方案

> 日期：2026-06-09
> 状态：**待落地**（决策见 `Save保留策略-重构方案.md` Q1–Q10、`Study发布与权限模型.md` 7问+D1–D9）
> 调试期规则：**直接改 DDL → DROP + 重建，不写迁移、不留兼容层**（AGENTS.md）。每次部署清空环境跑 `elys_debug.cmd` 自建。

---

## 0. 与"大手术"的边界（前置，必读）

另有 session 在 `feat/dataset-lifecycle-v2` 上重构，复核结论：

| 项 | 手术已做 | 对本方案影响 |
|---|---|---|
| `lifecycle_state` 已对齐 `unpublished` | ✅ | **L12 / L15 已消**，无需再改（但 P6 最终要砍这字段）|
| 滤波节点统一 `eeg/filter/apply`（节点 8 个）| ✅ | P4 节点标签按 8 个填 |
| PipelinePage 巨石拆分（抽出 usePipelineEditor / useDraftPersistence / useExecutionTasks）| ✅ | P3 前端改动要落到拆分后的 composable，不是老巨石 |
| `retention_status` 6 态 / `save_policy` / 一刀切缓存 | ❌ 未动 | **本方案主体** |
| 手术工作树未提交 | ⚠️ | **P0：等手术 commit/merge 后再基线**，否则撞车 |

> **铁律**：动手前 `git pull` + 复核本方案涉及的文件是否又变；改名（P2）必须抢一个"无人动 derived 相关文件"的窗口。

---

## 1. 阶段总览

```
P0  对齐手术基线        ── 前置，不写代码
P1  死代码清理          ── 纯删，最安全，先行  ★独立可部署
P2  改名 derived→输出   ── 机械原子，抢窗口   ★独立可部署
P3  retention 三层解耦  ── DB + 后端 + 前端    ★独立可部署
P4  节点缓存评分        ── spec 标签 + 评分函数 ★独立可部署
P5  GC 清盘 + 回收站     ── 后端任务 + 前端列表  ★独立可部署
P6  发布权限（大）      ── Study 发布轴，单独迭代
P7  wiki 回写           ── 收尾
```

依赖：P1→P2→P3→P4→P5 线性；P6 依赖 P3（输出砍 publish 轴）但工作量最大，可单独排期；P7 随时跟进。

---

## 2. P1 · 死代码清理（先行，纯删）

**目标**：删掉确认无消费方的死配置，缩小后续改动面。

| 删什么 | 文件 | 实锤 |
|---|---|---|
| `save_policy` | `models/study.py`、`schemas/pipeline.py`、`schemas/dashboard.py`、`schemas/study_summary.py`、`services/dashboard_summary.py`、`services/study_summary.py`、`routers/pipelines.py`、`pipeline/execution_manifest.py`（8 文件 18 处）+ DDL `04_pipelines.sql` 的列 | 从不驱动 retention（L14）|
| Study `derived_dataset_retention_policy` | `schemas/study.py` + DDL | 空壳 dict、无消费方（L10）|
| `pinned` / `quarantined`（derived 侧）| `05_derived.sql` CHECK + 引用处 | pinned 无独有保护逻辑（L6）、quarantined derived 从没写（L5）。⚠️ **dataset_assets 的 quarantined 是活的，勿动** |

**校验**：`python -m py_compile`（后端全量）；`npm run typecheck`（前端，savePolicy 删后类型连带）；grep 确认零残留。
**部署验证**：起服务、创建一次 Execution、看 manifest 不再有 save_policy 字段、不报错。
**撞车风险**：低（纯删）。但 `save_policy` 在 dashboard/study_summary 露出，删后前端摘要卡要同步去字段。

---

## 3. P2 · 改名 derived_dataset → 输出 / StudyOutput（机械原子）

**目标**：全栈统一命名（决策：用户面"输出"，代码 `StudyOutput` 前缀避开节点 output slot）。

| 层 | 改 |
|---|---|
| DB 表 | `derived_datasets` → `study_outputs`（含所有索引名 `idx_derived_*` → `idx_study_output_*`、外键引用）|
| Model / 类型 | `DerivedDataset` → `StudyOutput`；`derived_dataset.py` → `study_output.py`；`schemas/derived_dataset.py` → `schemas/study_output.py` |
| Store | `derived_dataset_store.py` → `output_store.py`、`DerivedDatasetStore` → `StudyOutputStore` |
| API | `/derived-datasets` → `/outputs` |
| 前端 | 类型 `DerivedDataset`、api 文件、`ResultsPage` 等文案统一「输出」 |

**做法**：抢安静窗口，**一次性全局替换 + 立即提交**（约 572 代码处 / 39 文件）。分步：① DB/model/schema ② store/service/router ③ 前端 ④ grep 兜底残留。
**校验**：`py_compile` + `typecheck` + `mkdocs build`；全仓 grep `derived_dataset|DerivedDataset` 应归零（wiki 留到 P7）。
**撞车风险**：⚠️ 中高——572 处，与手术若同时动 derived 必冲突。**务必协调时间窗口**。

---

## 4. P3 · retention 三层解耦（核心）

**目标**：`retention_status` 6 态混一字段 → 拆三层正交。

### 4.1 DB（`05_derived.sql`，DROP 重建）

| 动作 | 字段 |
|---|---|
| **删** | `retention_status`（6 态枚举列）|
| **加** | `keep BOOLEAN NOT NULL DEFAULT false`（用户意图）|
| **加** | `cache_eligible BOOLEAN NOT NULL DEFAULT false`（系统缓存判定）|
| **留** | `retention_expires_at`（**仅 cache 行**有值；keep 行为 NULL）|
| **留** | `deleted_at`（回收站软删，P5）|

> 行的两种命运：`keep=true`（永久）/ `cache_eligible=true`（到期清）。`keep=false 且 不缓存` → 根本不产生行（不写盘）。不再需要枚举状态列。

### 4.2 后端 `save_settings.py` 重写

- 删 `_normalise_retention_param` 那套 `none/study/temporary` 字面值兼容
- 输出从 `{retention_status, retention_expires_at}` 改为 `{keep, cache_eligible, retention_expires_at}`
- `keep` 默认 = 拓扑角色（leaf=true / intermediate=false），用户参数可覆盖
- `cache_eligible` = 调 P4 的评分函数，**不接受用户参数**（系统自动、用户不可见）

### 4.3 API `schemas/study_output.py`（已改名）

- PATCH 从 `retention_status: Literal[...]` 改为 `keep: bool` + 动作「转为保留 / 不保留」

### 4.4 前端（拆分后的 composable + PipelinePage）

- 保留策略**下拉 5 选项** → **二元开关**（💾 保留 / ○ 不保留），收出参数面板主区
- 缓存中间步：工作流页**双击节点可见**、标「缓存」；结果页只列 keep 成品
- 去掉 39 处 retention 老逻辑

**校验**：`py_compile` + `typecheck`；起服务跑一条 pipeline，确认末端产物 `keep=true`、中间 `cache_eligible` 按评分。
**撞车风险**：中（前端落在手术拆分后的新结构，需先看清 composable 边界）。

---

## 5. P4 · 节点缓存评分

**目标**：一刀切缓存 → 按 ROI 自动判定（存储优先）。

- 8 个节点 spec（`nodes/*.json`）：删 `cache.enabled` 手动开关，加
  - `compute_cost`: cheap=1 / moderate=2 / expensive=3
  - `output_footprint`: small=1 / medium=2 / large=3 / explosive（硬规则不物化）
- 新增评分函数（建议 `pipeline/cache_policy.py`）：
  `cache_eligible = (compute_cost − STORAGE_WEIGHT × footprint) > 0`，`STORAGE_WEIGHT = 2`（全局可调）
  explosive → 强制不物化全量（流式 average）
- 标签初值（按决策表）：

| 节点 | compute | footprint | 结论 |
|---|---|---|---|
| data/load | n/a | — | — |
| filter/apply | moderate | large | 不缓存 |
| preproc/resample | cheap | medium | 不缓存 |
| preproc/rereference | cheap | large | 不缓存 |
| **ica/compute** | **expensive** | **small** | ✅ **缓存** |
| ica/apply | moderate | large | 不缓存 |
| epoch/segment | cheap | medium | 不缓存 |
| analysis/erp | cheap | small | 不缓存 |

> 当前 8 节点仅 ica/compute 命中缓存。TFR 节点（未实现）将来填 explosive → 流式。

**校验**：`py_compile`；单测评分函数；跑 pipeline 确认仅 ICA Compute job 标 cached。
**撞车风险**：低（节点 spec 独立）。

---

## 6. P5 · GC 清盘 + 回收站

**目标**：补上"真正释放磁盘"（L8）+ 删错可救（Q8）。

### 6.1 GC 物理清盘（`tasks/file_tasks.py` 扩展）

- 现 cleanup 只软删（改 deleted_at），**新增物理删盘步骤**
- 三层触发：① 定时 celery beat（基线）② 硬盘水位（>85% 触发、清到 70%，需新增磁盘监控）③ 管理员手动 + `dry_run` 预览
- **删前必查** `artifact_dependency_blockers`（有下游引用就跳过，现成）

### 6.2 删除两条线（状态机）

- **缓存到期**：`retention_expires_at` 过 → 直接 GC 清，不进回收站
- **用户删输出**：盖 `deleted_at` → 进回收站 → 宽限期（N 天）→ GC 清

### 6.3 回收站 UI（前端新增列表页）

- 「已删除」列表 + restore 按钮 + 「剩 N 天自动清除」倒计时
- restore = 清 `deleted_at`（端点已有）

**校验**：`py_compile` + `typecheck`；测：删输出→回收站可见→restore 回来；缓存到期→直接消失；GC dry_run 预览释放量。
**撞车风险**：低。

---

## 7. P6 · 发布权限（大，可单独迭代）

**目标**：发布上提 Study/Dataset，输出砍 publish 轴。**工作量最大，建议独立排期。**

| 子项 | 内容 | 决策 |
|---|---|---|
| 输出砍 publish 轴 | `study_outputs` 删 `lifecycle_state` + `visibility`，可见性继承 Study | 消解 L11 |
| Study 发布字段 | 加 `publish_state`（unpublished/published/withdrawn）+ `visibility`（**private/shared/public** 三档）| D1 |
| **Study 版本化** | 发布=冻结快照版本（新基础设施，最重）| D4 |
| 发布单位 | 只含 keep 成品 + active pipeline + 引用数据 | D5 |
| 撤回流程 | 复用 dataset `withdraw_requested→withdrawn` + 理由分级 + 通知 + 宽限期；**红线：不动已算结果** | D2 |
| 动态一致性 | dataset 撤 public → 依赖 study 自动降级 + 通知 | D3 |
| 跨 study 引用 | 纯引用（源撤回宽限期后失效）；改 `pipelines.py` 共享端点为 study 级 | D7 |
| 私有 dataset 露出 | 引用 + 非敏感元信息（名/被试数/任务/通道），不给文件 | D8 |
| 可复现性徽章 | ✅可复现（数据公开）/ 📊仅结果（数据私有）| D9 |
| 公开结果隐私 | 个体级 output（单试次/重建连续数据）发布前提示/拦截 | B6 |

> 脱敏发布（D6）暂不做、记 backlog。
> P6 自身建议再拆：① 输出砍轴 + Study 发布字段（小）② Study 版本化（大）③ 撤回 + 跨study引用 + 一致性（中）④ UI（徽章/审核/露出）。

**撞车风险**：⚠️ 高——直接动 `models/study.py`、dataset lifecycle，与手术同区。**必须等手术完全落定。**

---

## 8. P7 · wiki 回写

- `5-20 Pipeline 工作流管理`（缓存口径、二元保留）
- `3-45 DerivedDataset` → 改名「输出」，retention 三层
- `3-25 数据集生命周期`（Study 发布轴、输出继承）
- `3-50 协作权限`、`6-05 信息分级`（输出/Study 可见性）
- 重要改动记 `9-00` 周报 + `9-02` 月度明细
- `cd wiki && mkdocs build --clean` 自查

---

## 9. 风险汇总

| 风险 | 缓解 |
|---|---|
| 与手术撞车（同动 derived/study）| P0 等手术落定；每 P 前 `git pull` 复核 |
| 改名 572 处遗漏 | P2 抢窗口、一次做完、grep 兜底归零 |
| 本机无运行环境 | 每 P 静态校验（py_compile / typecheck / mkdocs）；真测在云端 `elys_debug.cmd` |
| DDL 改动 | 调试期 DROP 重建，**不写迁移**；确认 seed/bootstrap 能从零自建 |
| 行号已过时 | 本方案文件名为准、行号仅参考，落地按最新代码定位 |

---

## 10. 建议执行顺序（一句话）

**等手术落定 → P1 清死代码 → P2 抢窗口改名 → P3 解耦 → P4 评分 → P5 GC/回收站**（这 5 步是 Save 主线，可连续交付）；**P6 发布权限单独立项**（依赖 Study 版本化，最重）；**P7 wiki 随每步跟进**。
