# PipelinePage 巨石组件 · 拆分重构方案

> 整理日期：2026-06-10。本文档把 `PipelinePage.vue`（工作流编辑器主界面）的**体量问题、职责诊断、已落地的拆分进度**，以及面向「未来节点暴涨（统计 / 机器学习 / 行为分析全部融入 pipeline）」的**目标架构**，收敛成一份可执行方案。
>
> 事实源口径：**P0 = 当前代码**（分支 `feat/save-retention-fe`）。横切拆分已提交 `d6c0f83` / `45d012c` / `476082c` / `27e9a0c`；下文「现状」节均带代码出处，「目标架构」「执行方案」节为待落地内容，「待拍板」节是动手前需用户定向的点。
>
> 本文档给方案 + 记录进度。按惯例，重要落地后补 wiki `9-00` / `9-02`（当前拆分进度的 wiki 汇总条目仍待补）。

---

## 0. 一句话目标

把 [`PipelinePage.vue`](../../elys_project/frontend/elys-web/src/views/PipelinePage.vue) 从「**7000 行、什么都干的巨石组件**」收敛成三层：

1. **一个薄装配壳**（PipelinePage 本身只剩组合 composable + 摆放子组件）；
2. **一组按职责切开的 composable**（横切：画布 / 执行 / 检查器 / 各功能域）；
3. **一个按节点类型插拔的 Inspector 注册表**（纵切：让特殊节点 UI 可扩展）。

目标效果：**编辑器自身可维护**，且**节点数量增长时前端复杂度保持常数级**——加 100 个标准分析节点，前端零增长；只有少数需要专属交互的节点才各加一个面板组件。

---

## 1. 现状盘点（代码事实）

### 1.1 体量

| 指标 | 拆分前 | 当前（已抽 6 批） |
|---|---|---|
| 总行数 | 7269（对话起点）→ 7297（含并行的 Teleport/HMR 改动） | **6786** |
| 文件大小 | 271 KB（单文件 Read 工具都装不下，上限 256 KB） | — |
| 三段分布 | `<template>` ~1100 / `<script setup>` ~4500 / `<style>` ~1600 | script 持续缩小中 |
| 响应式状态 | 151 个 `ref/reactive/computed` | — |
| 函数 | ~200 个 | — |

> 黑话铺垫：**巨石组件（God Component）** 指一个组件什么都干、状态与逻辑高度耦合、谁都改不动的反模式。健康的 `.vue` 单文件通常几百行，7000 行属教科书级反例。

### 1.2 一个文件干了多少事（职责清单）

`PipelinePage.vue` 实际上是**一整套可视化工作流编辑器**，至少揽下这些**互相独立**的关注点：

| 关注点 | 估算行数 | 代表符号 |
|---|---|---|
| 可视化 DAG 画布引擎（litegraph.js + 大量自绘 patch） | ~900 | `initLiteGraphCanvas` / `drawNodeStatusBadge` / `bindHiDpiLiteGraphEvents` |
| 节点检查器 / 参数编辑（含通道选择、事件选择、标签、模板预览） | ~700 | `visibleBasicProperties` / `toggleChannel` / `saveSpec` |
| 运行调度 + 实时轮询 + 编辑锁 | ~600 | `runPipeline` / `startRunPolling` / `acquirePipelineEditLock` |
| 数据源筛选（LoadData 解析） | ~500 | `resolveLoadDataPreview` / `normalizeLoadDataFilter` |
| 产物（DerivedDataset）管理 | ~460 | `openArtifactPreview` / `setArtifactRetentionAction` |
| ICA 人工剔除交互 | ~150 | `submitIcaDecision` / `resumeIcaNode` |
| 节点增删改连 + 右键菜单 | ~350 | `addNodeAt` / `duplicatePipelineNode` |
| 草稿暂存 / 抽屉布局 / 节点库 / 格式化工具 | ~500 | （已抽，见 1.3） |

**关键结论**：这个文件的体量**主要来自横向职责堆叠**，跟节点数量无关——把所有节点删光，它还是 6000+ 行（详见 §2.4）。

### 1.3 已抽出的部分（6 批，全部已提交、typecheck 全绿）

抽到 [`composables/pipeline/`](../../elys_project/frontend/elys-web/src/composables/pipeline/)：

| 批 | 文件 | 行数 | 职责 | commit |
|---|---|---|---|---|
| 1 | `pipelineConstants.ts` | 107 | 颜色 / 选项 / 尺寸等 39 个常量 | `d6c0f83` |
| 1 | `pipelineFormatters.ts` | 226 | 33 个纯展示 / 格式化函数 | `d6c0f83` |
| 2 | `useEditorLayout.ts` | 125 | 抽屉布局：显隐 / 拖拽改宽 / Esc | `d6c0f83` |
| 3 | `useNodeLibrary.ts` | 33 | 节点库搜索 / 分组 / 折叠 | `d6c0f83` |
| 4 | `usePipelineEditor.ts` | 41 | **承重墙**：`definition` / 选中节点 / `nodeSpecs` | `45d012c` |
| 5 | `useDraftPersistence.ts` | 127 | 草稿 localStorage 暂存 / 恢复 | `476082c` |
| 6 | `useExecutionTasks.ts` | 104 | 异步任务事件流（取消 / 重试 / 拉事件） | `27e9a0c` |

拆分手法统一为「**纯移动定义 + 解构回填同名符号**」：逻辑搬进 composable，主文件用 `const { ... } = useXxx()` 拿回同名引用，**所有调用点（template / watch / 生命周期钩子）一行不改**，靠 `vue-tsc` 全量 typecheck 兜底验证。承重墙的 133 处引用即是这样零改动迁移的。

---

## 2. 问题诊断

### P1 · 体量与职责混杂（巨石）

6786 行仍是巨石。十几个关注点（§1.2）共享同一个 `<script setup>` 作用域，任何一处改动都要在数千行里定位，且**修改一个职责容易误伤另一个**（它们共享状态、共用作用域）。

### P2 · 横向耦合：这才是拆分难的真正原因

不是简单的「代码长」，而是**状态与函数互相缠绕**，具体三种缠法：

1. **承重墙状态被全域引用**：`definition.value` 55 处、`selectedNode` 69 处、`nodeSpecs` 9 处——画布、检查器、执行、产物、CRUD 全都读写它（已抽成 [`usePipelineEditor`](../../elys_project/frontend/elys-web/src/composables/pipeline/usePipelineEditor.ts)，解构回填）。
2. **执行态被多个域共享**：`activeExecutionId` / `selectedJob` / `latestPipelineExecution` / `activeExecutionDetail` 被 ICA、产物、任务、画布运行态同时依赖。
3. **共享标志散落 + 画布函数被反向调用**：`statusMessage` / `dirty` / `hydrating`（原本是裸 `let`，第 5 批已升级为 `ref` 才能跨 composable 传递）这类「编辑器级标志」到处被读写；画布函数 `syncDefinitionToLiteGraph` / `applyLiteGraphRunState` / `selectLiteGraphNode` 被**非画布逻辑**（草稿恢复、执行刷新、选中节点）反向调用。

**后果**：用「显式传参」抽深耦合的域时，参数会爆炸。实测 ICA 一个面板就依赖 **9 个外部符号**（`selectedJob` / `activeExecutionId` / `latestPipelineExecution` / `refreshRunState` / `isTerminalRunStatus` / `startRunPolling` / `statusMessage` / `describeError` / `selectedStudyId`）。这是 §3 选型的核心约束。

### P3 · 纵向风险：特殊节点 UI 硬编码进主文件（面向未来最致命）

这是结合「节点会很多很多」要重点指出的问题。**有些节点需要专属 UI，现在直接焊在主文件里**：

- **ICA 决策面板**：[`PipelinePage.vue` template 第 679–718 行](../../elys_project/frontend/elys-web/src/views/PipelinePage.vue) + 7 个 `ica*` 函数，整块写死在主文件。
- **检查器的特殊参数类型**：虽然普通参数走 schema 驱动的通用渲染，但 `event_select`（事件多选 chip）、`channel_list`（通道 listbox 多选）这两种特殊参数类型的**渲染 + 交互逻辑（~400 行）也在主文件**（template 第 730+ 行 + 一堆 `toggleChannel` / `toggleEventId` 函数）。

**增长模型**：每新增一种「需要专属交互的节点 / 参数类型」（未来 ML 调参、统计对比组、行为反应时分布……），主文件就**线性膨胀一截**。LoadData 已经做对了——抽成了独立的 [`LoadDataPanel.vue`](../../elys_project/frontend/elys-web/src/components/LoadDataPanel.vue)（template 第 720–728 行只剩一个 `<LoadDataPanel>` 标签）——但这只是个孤例，没有成体系的机制。

### P4 · 画布引擎是最大且最难动的耦合块

litegraph.js 被大量 patch（自绘网格 / 坐标轴 / 节点状态徽章 / 保存图标 / HiDPI 适配 / 右键菜单），且这些自绘逻辑**依赖闭包里的 canvas 实例 + `definition` + 执行态**（要画运行中/成功/失败的节点配色）。~900 行，是横切拆分里风险最高的一块，须留到最后、小步做。

### 2.4 一句话钉死认知误区

> **PipelinePage.vue 的大小 ≈ f(编辑器横向职责)，与节点数量无关。**
> 节点系统**早已是配置驱动**（后端 [`backend/app/pipeline/nodes/*.json`](../../elys_project/backend/app/pipeline/nodes/)，每节点一个 JSON，[`registry.py`](../../elys_project/backend/app/pipeline/registry.py) 自动扫描，前端节点库 + 参数面板全自动渲染）。加普通节点前端零改。所以「节点暴涨 → PipelinePage 更大」这个因果是**断的**；真正会让前端长的是 P3 的特殊节点 UI，而那要靠 §3.3 的注册表解决，**不是给每个节点写一个 vue**（那会把已做对的配置驱动倒退回 schema 双重维护）。

---

## 3. 目标架构

### 3.1 两条正交的拆分线

| 线 | 拆什么 | 解决哪个问题 | 状态 |
|---|---|---|---|
| **横切**（composable / 子组件） | 画布 / 执行 / 检查器 / 各功能域 → 独立模块 | P1 / P2 / P4：编辑器自身职责解耦 | 6/约 12 批，进行中 |
| **纵切**（Inspector 注册表） | 特殊节点 UI → 按 type 插拔 | P3：节点增长时前端可控 | 雏形已有（LoadDataPanel），待成体系 |

两条线**正交、都要做**，解决的是不同维度的问题，别混为一谈。

### 3.2 横切：composable 分层 + 一个关键选型修正

已验证的「解构回填」手法对**叶子域**（布局 / 节点库 / 草稿 / 任务）很顺。但对**深耦合核心域**（执行 / ICA / 产物 / 画布），P2 的参数爆炸使「散列显式传参」难看且易错。

**选型修正（建议）**：把「编辑器级共享上下文」收敛成**一个 reactive 上下文对象**（承重墙状态 + 执行态 + 共享标志 + 少量基础方法），用 **`provide` / `inject`** 在 PipelinePage 顶层注入、各 composable `inject` 取用，**而非每个 composable 传 9 个参数**。

- 现状 `usePipelineEditor()` 已是承重墙雏形，可平滑升级为「编辑器上下文 provider」。
- 叶子域保持现有 options 传参（依赖少、显式清晰）即可，不强行改。
- 收益：执行 / ICA / 产物 / 画布抽取时从「传一长串参数」变成「`const ctx = useEditorContext()`」，参数爆炸消失。

> 黑话铺垫：**provide / inject** 是 Vue 的跨层级依赖注入——父组件 `provide` 一份共享状态，任意子孙 `inject` 取用，省去层层传参。代价是依赖变隐式（排查「这数据哪来的」稍累），所以**只对真正全域共享的核心上下文用它，叶子域仍显式传参**。

### 3.3 纵切：Inspector 注册表（面向节点暴涨的核心准备）

检查器面板的逻辑收敛成一句话：**按选中节点的 `type` 去注册表查；查到 → 用专属组件，查不到 → fallback 到通用 `PropertyForm`。**

```
components/pipeline/inspectors/
  index.ts                 ← 注册表：Record<nodeType, Component>
                              { 'eeg/data/load': LoadDataInspector,
                                'eeg/ica/apply': IcaInspector, ... }
  PropertyForm.vue         ← 通用 schema 渲染器（覆盖大多数节点）
  LoadDataInspector.vue    ← 由现有 LoadDataPanel 迁入
  IcaInspector.vue         ← 从主文件硬编码迁出（解 P3）
  fields/                  ← 特殊参数类型控件（event_select / channel_list 迁出）
    EventSelectField.vue
    ChannelListField.vue
  （未来）MlTuningInspector.vue / StatsClusterInspector.vue / BehaviorAlignInspector.vue
```

- **普通节点**：0 个 vue（配置 + 通用渲染）。
- **特殊节点**：1 个**纯 UI** 组件（只管自己的面板，接收 `nodeSpec` + `params`、emit 更新，**不重复定义 schema**）。
- PipelinePage 不再因「又来个花哨节点」而膨胀——新面板进 `inspectors/`，主文件不动。

### 3.4 NodeSpec schema 增强（把「需要特殊 UI」的节点比例压到最低）

性价比最高的一笔投资：**每给通用 schema 加一种参数类型，就有一批节点从「需要特殊 UI」降级成「纯配置」**。

- 现有 property type（[`nodes/*.json`](../../elys_project/backend/app/pipeline/nodes/) 的 `properties[].type`）：`select` / `number` / `integer` / `event_select` / `channel_list` / `dataset_filter` / `dataset_ids`。
- 建议扩充：`range`（区间，如频带）、`group`（参数分组折叠）、`dynamic_options`（选项来自上游，如通道名）、`key_value`（超参字典，给 ML）、`multi_select`（通用多选）。
- 配套：通用 `PropertyForm` 为每种类型实现一个 `fields/` 控件即可，仍是「加类型 → 一批节点受益」的杠杆。

### 3.5 目标终态（结构示意）

```
views/PipelinePage.vue                 装配壳，目标 < 400 行
composables/pipeline/
  usePipelineEditor.ts        承重墙 →（升级）编辑器上下文 provider
  useEditorLayout / useNodeLibrary / useDraftPersistence / useExecutionTasks   ✅ 已抽
  useLoadDataResolve / useArtifacts / useIcaInteraction      ← 待抽（功能域）
  usePipelineExecution        ← 待抽（执行调度核心，inject 上下文）
  useLiteGraphCanvas          ← 待抽（画布引擎，最后、小步）
  pipelineConstants / pipelineFormatters    ✅ 已抽
components/pipeline/
  NodeLibraryPanel / NodeInspectorPanel / RunDrawer / RunDialog / ...   ← 模板子组件化
  inspectors/                 ← §3.3 注册表
```

---

## 4. 执行方案

### 4.1 剩余横切批次（按建议顺序）

| 批 | composable | 体量 | 依赖 | 风险 | 备注 |
|---|---|---|---|---|---|
| 7 | `usePipelineExecution`（执行态核心） | ~600 | 承重墙 + 画布函数 | 🔴 高 | 建议先升级承重墙为上下文 provider，再抽；它是 ICA/产物/任务的依赖源 |
| 8 | `useArtifacts`（产物管理） | ~460 | 执行态 + 选中节点 | 🟡 中 | inject 上下文后参数清爽 |
| 9 | `useIcaInteraction`（ICA 逻辑） | ~150 | 执行态（9 依赖）| 🟡 中 | 逻辑抽 composable，UI 进 §4.2 的 IcaInspector |
| 10 | `useLoadDataResolve`（数据筛选） | ~500 | 承重墙 + 节点 | 🟡 中 | — |
| 11 | `useNodeInspector`（检查器逻辑） | ~700 | 承重墙 + 参数编辑 | 🟡 中 | 配合 §4.2 把特殊字段迁 `fields/` |
| 12 | `useLiteGraphCanvas`（画布引擎） | ~900 | 承重墙 + 执行态 | 🔴 高 | **最后做、小步**；自绘逻辑闭包耦合最深 |
| 13 | 模板子组件化 | template ~1100 | — | 🟡 中 | aside / dialog 抽 `.vue`，样式随迁 |

每批照旧：抽取 → `npm run typecheck` 绿 → `git` 提交 → 下一批。

### 4.2 纵切落地（Inspector 注册表，可与横切并行）

1. 建 `components/pipeline/inspectors/index.ts` 注册表 + 通用 `PropertyForm.vue`。
2. **LoadData**：把现有 `LoadDataPanel.vue` 平移进 `inspectors/`、注册为 `eeg/data/load`（低风险，已是独立组件）。
3. **ICA**：把主文件硬编码的 ICA 面板迁成 `IcaInspector.vue`、注册为 `eeg/ica/apply`（解 P3，配合批 9）。
4. **特殊字段**：`event_select` / `channel_list` 迁成 `fields/` 控件（配合批 11）。
5. 检查器面板主体改为「查注册表 → 命中用专属组件 / 未命中用 PropertyForm」。

### 4.3 风险与原则

- **画布最后做**：批 12 闭包耦合最深，且同期可能有人改画布初始化（已遇到过 Teleport/HMR 并行改动），单独小步、改完真机点连线/拖拽/右键。
- **每批 typecheck 兜底**：`definition`/`selectedNode` 等高频引用靠 `vue-tsc` 全量验证，漏接立刻报错。
- **调试期红利**：无真实数据、无兼容包袱，可大胆改 schema / 升级承重墙为 provider，不写迁移。
- **纯前端**：不动后端 / API / 节点 JSON；行为不变是硬约束（引用点零改 + typecheck 绿）。

---

## 5. 待拍板

1. **承重墙是否升级为 `provide`/`inject` 上下文 provider**（§3.2）。这是抽执行/画布前的关键选型——升级则后续核心域参数清爽，不升级则继续 options 传参（深耦合域会难看）。**建议升级。**
2. **Inspector 注册表是否现在就立**（§3.3 / §4.2），还是等横切批次推到检查器（批 11）时一并做。**建议现在立**，先把 LoadData/ICA 两个范例迁进去奠基。
3. **NodeSpec schema 类型扩充的优先级**（§3.4）——可按未来节点路线图（wiki `5-25`）的批次（时频 / 脑网络 / 统计 / ML）倒推最缺哪几种参数类型先补。

---

## 附：与节点架构讨论的关系

本方案的 §2.4 / §3.3 / §3.4 是 2026-06-10 与用户讨论「节点会很多很多、要不要每节点一个 vue」的结论沉淀：**节点是配置不是组件（后端已做对，保持）；PipelinePage 的肥是职责堆出来的不是节点喂出来的（横切解决）；为节点暴涨做的前端准备是 Inspector 注册表 + 更强的 schema 类型（纵切解决），而非给每个节点写 vue。**
