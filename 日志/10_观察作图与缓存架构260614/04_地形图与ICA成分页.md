# 04 · 地形图（Topomap）引擎与 ICA 成分页

> 整理日期：2026-06-14
> 事实源优先级：P0 = 当前代码（`Niantong-eeg-analysis/` 只读参照 + `elys_project/` 落地目标），P1 = wiki。
> 本文只给方案、不改代码；Niantong 是只读参照系，绝不修改其任何文件。待讨论项（见 §8）定向后再动手；落地后按惯例补 wiki 9-00 / 9-0x。
> 状态图例：✅ 现有 · 🆕 新增 · ⏸ 暂缓（阻塞于未决）。

---

## 0. 一句话目标

把 Niantong 那套「头皮地形图（topomap，俗称‘脑电热力图’：把每个电极的一个标量值在头皮二维投影上插值成连续色块图）」的**画图行为 + 页面布局**几乎照搬到 elys，做成**一个可复用的 Vue 渲染器组件 `<TopomapView>`**（被 ERP/时域、PSD/频域、ICA、伪迹四处共享），并在其之上重建 **ICA 成分页**（成分地形图 / 成分时序 / 成分功率谱 / 滤波前后对比 四图 + 成分选择列表）；只把配色、样式、字体、图标换成 elys 主体设计语言。

---

## 1. 背景与设计纲领

### 1.1 为什么 topomap 是「主文档」

topomap 不是一张孤立的图，而是一个**被多处复用的渲染原语**：

- ERP/时域观察：拖时间游标 → 实时刷新「当前时刻的头皮电位分布」。
- PSD/频域：选一个频段 → 出「该频段功率的头皮分布」。
- ICA：每个成分一张「空间权重（mixing column，即该成分对各电极的贡献系数）地形图」。
- 伪迹/坏道：坏道高亮、bad channel 标记叠加在 topomap 上。

所以 topomap 引擎单独成文、其它页面引用本文，避免四处重复描述同一套插值 + Canvas + 等值线逻辑。

### 1.2 「极大吸收」Niantong 原版的什么

行为与布局**照搬**，这些都来自 Niantong 已经调得很顺手的实现：

- 96×96 网格 + IDW（Inverse Distance Weighting，反距离加权：网格点的值 = 周围电极值按「距离的负幂」加权平均，越近权重越大）插值，power=3。
- 鲁棒百分位色限（robust color limit：取绝对值的 90 分位而非最大值定色标上下界，避免一个尖峰把整张图洗白）+ 帧间平滑。
- `d3-contour` 微包等值线（contour：等高线，把相同电位的点连成圈，让色块图更易读）。
- Canvas `putImageData` 画热力底图 + SVG 画电极点 / 标签 / 鼻子 / 耳朵 / 等值线的**双层叠加**结构。
- 电极点击选中、双击、hover tooltip、坏道描边、活动标签高亮等交互手势。
- `buildVectorSvgString` 矢量导出（论文出图用纯 SVG，等值线变填充色块）。

### 1.3 只换不照搬的：配色 / 样式 / 字体 / 图标走 elys

elys 受众是医生 / 心理 / 神经科学家（非工程师），纲领是「让脑电处理显得简单、fancy，而非复杂」。所以：

- 头皮轮廓 / 鼻子 / 耳朵的线色、电极描边、等值线色：从 Niantong 的 `#4d5f72` / `rgba(36,53,73,0.45)` 改走 elys 设计变量（`--c-border-strong` / `--c-text-3` 等），见 `IcaPage.vue:316`（现有 mock 用的就是 elys 变量体系）。
- 色标：Niantong 用 `d3.interpolateSpectral`（彩虹谱）；elys 可保留发散色标但建议换成「蓝-白-红（RdBu_r）」这类临床更习惯的发散色（diverging colormap：中点白、两端冷暖，适合「有正有负、关心偏离 0」的电位 / 权重）。这点列入 §8 待议。
- 字体：Niantong 标签用 `Arial, "Microsoft YaHei UI"...`（`VisualFactors_Topography.js:1012`）→ 改 elys 字体变量。
- 文案：用领域语言，不用文件系统语言。「Dataset / Epoch / Channel」→「数据集 / 事件 / 通道」，与 `IcaPage.vue` 现有中文一致。

### 1.4 elys 现状（只读）

- `elys_project/frontend/elys-web/src/views/IcaPage.vue` 是一张**纯静态设计稿**：成分卡片、地形图、时序、PSD、对比图全是 CSS `radial-gradient` 伪造 + 写死的 SVG path（`IcaPage.vue:39`、`:75`、`:102`），零真实数据、零 API。它确立了 elys 的 ICA 页**视觉语言**（成分网格 + 选中详情 + 右侧推荐侧栏），但底下没有任何引擎。
- `elys_project/frontend/elys-web/src/composables/pipeline/useIcaInteraction.ts` 是**唯一真实的 ICA 数据通路**：它服务的是「工作流编辑器里 ICA 节点暂停 → 人工勾选剔除成分 → 提交决策 → 恢复」的半自动交互（`useIcaInteraction.ts:47`），数据来自 `pipelineApi.getNodeInteraction`。但它拿到的 `components` 只有元信息（`std` / `max_abs` / `top_channels`，见 `useIcaInteraction.ts:146`），**没有地形图权重、没有时序、没有频谱**。
- elys 后端对应 schema `PipelineInteractionResponse`（`elys_project/backend/app/schemas/pipeline.py:358`）：`interaction_type="ica_component_selection"`、`components: list[dict]`、`decision.excluded_components: list[int]`。同样**没有 topomap / timecourse / spectrum 二进制端点**。

结论：elys 这边「ICA 决策骨架」已通（暂停 / 勾选 / 提交 / 恢复），但「四图可视化所需的数据接口与渲染引擎」全缺，需要从 Niantong 移植。

---

## 2. 原版「画图行为功能」盘点（带 文件:行号）

均来自 `Niantong-eeg-analysis/frontend/js/ui/VisualFactors_Topography.js`（topomap 引擎，1312 行）与 `Interact_ICA.js`（ICA 编排，1806 行）。

### 2.1 topomap 引擎的画图行为

| 行为 | 说明 | 文件:行号 |
| --- | --- | --- |
| 创建渲染器 | `createTopographyRenderer(config)` 返回 `{ ensureForPayload, renderAtIndex, schedule, resize, setTopomapScale, getTopomapScale, buildVectorSvgString, destroy, ... }` 命令式 API | `VisualFactors_Topography.js:644`、:1285 |
| 建结构（一次性） | `ensureForPayload(payload, context)`：测量 host、算几何、建 Canvas + SVG + clipPath + 头皮圆 / 鼻子 / 耳朵 / 电极点 / 标签，预计算网格插值权重 | `:706`、:837–:1019 |
| 逐帧重绘 | `renderAtIndex(payload, index, context)`：取该时刻各电极值 → 算色限 → 网格插值 → `putImageData` → `drawImage` 裁圆 → 等值线 → 电极点上色 | `:1057` |
| 节流调度 | `schedule()` 用 `requestAnimationFrame` 合并高频重绘（拖游标时关键）；`pendingIndex` 只留最后一帧 | `:1172` |
| IDW 插值 | `computeInterpolatedValue(cell, values)`：权重 `1/dist^power`，`exactPointIndex` 命中电极正上方时直接取原值不插值 | `:534`、权重预计算 :819–:828 |
| 鲁棒色限 | `computeRobustAbsLimit`：绝对值排序取 `colorLimitPercentile`（默认 0.9）分位，再与 `maxValue*0.35` 取大；帧间用 `colorLimitSmoothing`（0.18）线性平滑 | `:503`、:1074–:1082 |
| 色标 | `d3.scaleSequential` + `d3.interpolateSpectral(1-t)`，`clamp(true)`，domain `[-limit, +limit]` 对称 | `:1044` |
| 等值线 | `d3.contours().size().smooth(true).thresholds()`，零附近线加粗（`contourZeroBandRatio`） | `:1117`–:1138 |
| 电极点击 | 点击 → 设 `activeLabelName` → 高亮该标签 + 回调 `onPointClick` | `:939` |
| 电极双击 | 回调 `onPointDoubleClick`（坏道切换常挂这里） | `:947` |
| 空白点击 | 点击 SVG 空白 → 清空活动标签 | `:962` |
| hover 提示 | 每个电极点 `<title>` 原生 tooltip | `:958` |
| 坏道渲染 | `context.badChannels`（Set）→ 描边变灰 `#7e8892`、半透明、加粗 | `:1140`、:1149 |
| 缩放 | `setTopomapScale(scale)` 在 `[0.5, 2.5]` 内夹取后 `resize()` 重建 | `:1190` |
| 自适应 resize | `resize()` 清 `hostSizeKey` 强制重建 + 重绘；ICA 页用 `ResizeObserver` 驱动（`Interact_ICA.js:1100`） | `:1184` |
| 矢量导出 | `buildVectorSvgString({ contourSteps })`：clone SVG，等值线从「线」改「填充色块 + 描边」（更多阈值，28 级），返回带 XML 头的字符串 | `:1207` |
| 标签布局 | `getTopomapLabelPlacement` 按电极方位推 textAnchor / dx / dy；通道多时缩字号、内缩 | `:595`、:572–:593 |
| 防重叠布点 | `distributeTopomapPoints`：弹簧式迭代把过近电极推开（36 步），同时拉回原位保持可辨认 | `:277` |

### 2.2 ICA 页的画图行为（编排层）

| 行为 | 说明 | 文件:行号 |
| --- | --- | --- |
| 选成分 | `icaSelectComponent(idx)` → 存 state → 更新勾选 → `icaRequestComponentReload` | `Interact_ICA.js:481` |
| 翻成分 | `icaShiftComponent(delta)`（上一个 / 下一个） | `:498` |
| 设待移除集 | `icaSetComponentsToRemove(nextSelection)` → 存 `componentsToRemove` → 更新移除列表 | `:505` |
| 单成分加载去抖 | `installICALoadSingleComponentOptimizer`：70ms 去抖 + `requestKey` 短路（同 key 不重画） | `:78` |
| 四图渲染入口 | `updateICATopography` / `updateICATimecourse` / `updateICASpectrum` / `updateICAComparison` | `:1036` / `:1120` / `:1268` / `:1349` |
| 对比数据流 | `updateSpatialComparisonFromRemovalList`：带 `requestSeq` + snapshot 防过期（stale）覆盖，空选集不请求、不覆盖现图 | `:789`、:845、isStale :772 |
| 对比去抖 | `triggerSpatialComparisonUpdateDebounced(250ms)` | `:934` |
| 切事件 | `applyEpochSelection` → 存 `selectedEpoch` → 触发对比更新 + 成分重载 | `:423` |
| 切通道 | `applyChannelSelection` → 存 `selectedChannel`（对比图的对照通道） | `:439` |

---

## 3. 原版「页面布局」盘点（带 文件:行号）

ICA 页 shell 由 `buildShellHtml()` 生成（`Interact_ICA.js:232`），分 v1 / v2 两套（v2 是中文重设计版）。布局骨架两版一致：**顶栏 + 左控制区 + 右图区（3 卡网格）**。

### 3.1 顶栏（toolbar）

- 「返回流程图」按钮（`#ica-back-btn`，`Interact_ICA.js:320`）
- 标题 / 品牌（v2 是 `ICA 成分可视化 / 成分审阅` 品牌块，`:238`）
- 数据集名（`#ica-dataset-name`）

### 3.2 左控制区（`.ica-left`）

分两组（v2 有分组标题「数据选择」「成分审阅」）：

- **数据选择行**（`.ica-selector-row`，`:329`）三张卡并排：
  - 数据集 `#ica-dataset-selector`（`:332`）
  - 事件 `#ica-epoch-selector`（`:337`）
  - 通道 `#ica-channel-selector`（`:340`，对比图的对照通道）
- **成分审阅行**（`.ica-component-row`，`:347`）两张卡并排：
  - 选择成分 `#ica-component-checkboxes`（`:350`，当前查看哪个成分）
  - 待移除成分 `#ica-removal-checkboxes`（`:354`，勾选要剔除的成分集）
- **动作区**：「应用并返回」按钮 `#ica-apply-btn`（`:360`）

### 3.3 右图区（`.ica-right` → `.ica-grid`）三张图卡

- **功率谱卡**（`.ica-card-spectrum`，`:366`）：主体是 `#ica-spectrum-plot`，右上角**嵌一张小地形图** `#ica-topo-plot`（`.ica-topo-inset`，`:370`）——这是原版精巧处：地形图作为功率谱卡的 inset 缩略图，省一格。
- **时域信号卡**（`.ica-card-timecourse`，`:376`）：`#ica-timecourse-plot`
- **空间滤波对比卡**（`.ica-card-comparison`，`:381`）：`#ica-comparison-plot`，对照通道在「移除选中成分前 / 后」的波形叠加

### 3.4 选择器复用

数据集 / 事件 / 通道选择器复用共享模块 `VisualFactors_SelecDataset/SelecEvents/SelecChannels`（`Interact_ICA.js:519`），成分 / 待移除用 `VisualFactors_CompToRemove`（`VisualFactors_CompToRemove.js:37` 的 `renderCompToRemoveSelector`，纯 DOM 列表非图）。

---

## 4. 数据接口（后端端点 + 二进制协议 + 参数）

### 4.1 ICA 成分二进制（一次取 地形图 + 时域 + 频谱）✅ Niantong

端点：`GET /api/ica/component`（`fastapi_server.py:10442`），`format=binary`。

请求参数（`Call_ICA_Data_From_Backend.js:162`）：`session_id`、`ica_id`、`component_idx`、`format=binary`、可选 `epoch_idx` / `channel_idx` / `input_data_id` / `known_hash`。

**二进制布局**（小端，`fastapi_server.py:9576` 的 `_build_ica_component_binary_response`，解码 `window_decode_worker.js:10`）：

```
uint32  topography JSON 字节长度
uint32  n_times
uint32  n_freqs
float64[n_times]  时序 times
float32[n_times]  时序 values
float32[n_freqs]  频谱 frequencies
float32[n_freqs]  频谱 power_db
uint8[topoLen]    topography JSON（UTF-8）
```

响应头：`X-ICA-Component-Hash`（内容哈希，`:9629`）。前端把哈希存 `icaComponentHashCache`，下次带 `known_hash`，后端命中返回 **204**（前端用本地缓存，`Call_ICA_Data_From_Backend.js:182`）——这是「哈希短路」省带宽。

**topography JSON 字段**（来自 `ica_visualization_utils.py:307` 的 `get_ica_topography_data` 返回）：
- `interpolated_data`：res×res 网格（NaN→null）——**注意：这是后端 CloughTocher2D 插值的结果**
- `grid_x` / `grid_y`：网格坐标
- `channel_positions`：`[{x, y, name, standard_name, montage, source, weight}]`
- `channel_weights`：各通道原始权重
- `standard_channel_positions` / `standard_position_missing_channels` / `channel_position_source="mne_standard_topomap_2d"`
- `head_contour`：`{circle, nose, left_ear, right_ear}`
- `head_geometry`：`{center_x, center_y, radius}`
- `color_range`：`{vmin, vmax}`（对称）
- `mask` / `resolution` / `interpolation_method="CloughTocher2D"`

### 4.2 滤波前后对比二进制 ✅ Niantong

端点：`GET /api/ica/comparison`（`fastapi_server.py:10725`），`format=binary`。参数：`session_id` / `ica_id` / `input_data_id` / `components_to_remove`（逗号分隔）/ `epoch_idx` / `channel_idx`。

**布局**（`Call_ICA_Data_From_Backend.js:276` 的 `decodeICAComparisonBinary`）：magic `ICACMP01`(8B) + uint32 meta 长度 + meta JSON + float64[n_times] times + float32[n_times] original + float32[n_times] cleaned。后端逻辑 `get_spatial_filter_comparison`（`ica_visualization_utils.py:396`）：copy ICA → `exclude=components_to_remove` → `apply` → 取对照通道前后波形。

### 4.3 其它 JSON 端点 ✅ Niantong

- `GET /api/ica/dataset_info`（`:10322`）：通道数 / 成分数 / 采样率 / 时长 / `ch_names` / `n_epochs` / `is_epochs`（`get_dataset_info`，`ica_visualization_utils.py:478`）
- `GET /api/ica/matrix`（`:10258`）：混合矩阵
- 成分列表 `get_all_components_list`（`:528`）：`[{idx, number, label, variance_explained}]`
- `POST /api/ica/apply_removal` / `/api/process/ica_apply`（`Call_ICA_Data_From_Backend.js:358`、:373）

### 4.4 后端电极 2D 坐标 ✅ Niantong

`channel_position_utils.py`：`get_standard_channel_positions(ch_names)`（`:53`）用 MNE `make_standard_montage("standard_1005"/"standard_1020")` + `_find_topomap_coords(to_sphere=True)`（`:91`）做球面投影到 2D；非标准通道（如 IO 参考）进 missing 列表不上头皮（`:56`）。

### 4.5 elys 现状端点（差距）

elys 现仅有 `getNodeInteraction` / `submitNodeDecision` / `resumeNode`（`useIcaInteraction.ts:73`、:105、:129），返回 `PipelineInteractionResponse`（`schemas/pipeline.py:358`），`components` 仅元信息。**topomap / timecourse / spectrum / comparison 四类数据端点均需新建**（见 §7 P2）。

---

## 5. elys 落地设计

### 5.1 渲染技术选型（与 ./00 总览一致）

| 子图 | 技术 | 理由 |
| --- | --- | --- |
| topomap 热力底图 | 原生 Canvas `ImageData`（`putImageData` 到小 buffer canvas 再 `drawImage` 放大裁圆） | 96×96 逐像素上色，Canvas 比 SVG 快得多 |
| topomap 电极 / 标签 / 鼻耳 / 等值线 | SVG（d3 选择集） | 矢量、可交互、可直接导出 |
| topomap 等值线几何 | `d3-contour` + `d3-geoPath` | 微包，等高线生成 |
| 成分时序 / 滤波对比 | **uPlot（Canvas）** | 实时探索面、点多 |
| 成分功率谱 | **uPlot**（与信号作图同引擎，折线 + 轴） | 统一渲染：1D 曲线都走 uPlot（含 PSD/ICA 谱），不再为它单开 SVG；Niantong 原版是 D3 SVG 折线（`VisualFactor_ICAPower.js:136`） |
| 论文出图 topomap | SVG 矢量（等值线变填充色块），接 FigureSpec | 对应 `buildVectorSvgString`（`VisualFactors_Topography.js:1207`） |

### 5.2 `<TopomapView>` 作为可复用渲染器组件

核心设计：**把命令式的 `createTopographyRenderer` 包成一个声明式 Vue 组件**，对外只暴露 props，内部用 template ref + 生命周期管理命令式引擎。

```
<TopomapView
  :positions="chPos"        // [{name, x, y}]  电极 2D 坐标（来自后端）
  :weights="weights"        // Float32Array    当前帧各电极标量（电位 / 权重 / 功率）
  :color-range="range"      // {vmin, vmax} 可选；不给则前端鲁棒百分位自算
  :bad-channels="badSet"    // Set<string>
  :active-label="activeCh"  // 高亮通道名
  :show-labels="false"
  :scale="1"
  mode="canvas"             // 'canvas' 实时预览 | 'svg' 矢量出图
  @point-click="..."
  @point-dblclick="..."
/>
```

Vue 集成要点（命令式库的标准接法）：

- **template ref + onMounted 建 / onUnmounted 销**：`createTopographyRenderer({ host: hostRef.value, ... })` 在 `onMounted` 调用，`onUnmounted` 调 `destroy()`。uPlot / Canvas 都是命令式 DOM 库，不能让 Vue 的虚拟 DOM 去管它们内部的 canvas。
- **大 TypedArray 不进响应式**：`weights`（Float32Array）、`positions`、内部 `gridCells` / `gridValues` 用 `shallowRef` / `markRaw` / `toRaw` 持有；绝不放进 `reactive`——否则 Vue 的 Proxy 会逐元素拦截，几万次插值直接卡死。引擎内部 `state` 对象整体 `markRaw`。
- **props → 命令式调用**：`watch([weights, activeLabel, ...])` → 调 `renderer.schedule(...)`（沿用 rAF 节流）；`positions` / 尺寸变化 → `renderer.resize()`（触发 `ensureForPayload` 重建结构）。
- **ResizeObserver**：组件内建一个，回调里 `renderer.resize()`，对齐 Niantong `Interact_ICA.js:1100`。

### 5.3 既出 Canvas 预览又出 SVG 矢量（接 FigureSpec）

- **预览路径**（`mode="canvas"`）：Canvas 热力 + SVG 装饰，即 Niantong 现行双层结构，给屏幕实时探索用。
- **矢量路径**（`mode="svg"` 或导出动作）：调引擎的 `buildVectorSvgString` 等价物——等值线从「描边线」改「填充色块 + 细描边」，整图纯 SVG。但 elys 不直接吐 SVG 字符串拼接，而是**产出一份 FigureSpec**（单一事实源，见 ./00）：

  ```
  FigureSpec(topomap) = {
    kind: 'topomap',
    positions, weights, colorRange, colormap,
    contours: { steps, smooth },
    head: { circle, nose, ears },
    labels: { show, channels },
    badChannels,
  }
  ```

  由一个 `renderTopomapSvg(spec)` 纯函数把 FigureSpec → SVG（论文出图）；同一个 spec 也能喂给 Canvas 预览。这样「屏上看的」和「导出的」是同一份描述，不会两套代码画出两张不一样的图。

### 5.4 后端给坐标 + 权重 + 色范围，前端插值（分工，别重复 CloughTocher2D）⏸/🆕

关键决策（列入 §8 待议但有强倾向）：

- **后端职责**：只给 `channel_positions`（电极 2D 投影坐标，球面投影由 MNE 算，前端算不准）+ `channel_weights`（或当前帧各电极标量）+ 可选 `color_range`。即 `channel_position_utils.py` 那条路。
- **前端职责**：拿坐标 + 权重，用 **IDW（power=3）在 96×96 网格上自己插值**（Niantong topomap 引擎的做法，`VisualFactors_Topography.js:819`），因为时域 / 频域是**实时拖游标 / 选频段**，每帧权重都变，不可能每帧回后端。
- **不要采纳**：`ica_visualization_utils.py:138` 的 `get_ica_topography_data` 返回的 `interpolated_data`（后端 CloughTocher2D 整张网格）——那是为「ICA 一次性出图」准备的，对实时探索是浪费。ICA 成分页里前端**同样只用 `channel_positions` + `channel_weights` 两个字段**走 IDW 自插（看 `Interact_ICA.js:1062`–:1076：它把后端的 topo 数据降维成 `ch_names + data:[[w]]` 再喂给同一个 IDW 引擎，**完全没用** `interpolated_data`）。这反过来证明：elys 后端的 ICA 端点**只需吐 positions + weights**，连 CloughTocher2D 都可以不算。
- 也**不采纳** `ica_visualization_utils.py` 里那个 `get_ica_topography`（matplotlib 出 PNG）——确认是死代码。

两种插值的差异（一句话铺垫）：CloughTocher2D 是「三角剖分 + 三次插值」，平滑但慢、要 scipy；IDW 是「按距离加权平均」，快、纯前端 JS、效果对头皮图足够好。elys 统一用前端 IDW。

### 5.5 ICA 四图 + 成分列表的 Vue 组件树

```
IcaPage.vue（已存在静态稿，改造为容器）
├─ IcaToolbar           顶栏（数据集名 / 排序 / 批量标记 / 应用去除）  ← 保留现有 mock 结构
├─ IcaComponentGrid     成分网格（每卡一张 <TopomapView mode=canvas size=xs>）
│    └─ IcaComponentCard ×N  缩略地形图 + 标签 + 置信度 + keep/remove/doubt 边色
├─ IcaDetailPanel       选中成分详情
│    ├─ <TopomapView size=lg>     成分地形图（大）
│    ├─ IcaTimecourseChart        成分时序（uPlot）
│    ├─ IcaSpectrumChart          成分功率谱（SVG 折线）
│    └─ IcaComparisonChart        滤波前后对比（uPlot 双线）
└─ IcaSidebar           右侧：推荐操作 / 伪迹类型计数 / 参数 / 应用按钮   ← 保留现有 mock
```

布局映射 Niantong → elys：
- Niantong 的「左控制区三选择器 + 两成分列表」→ elys 收进顶栏（数据集 / 排序下拉）+ 成分网格本身就是「选成分」的载体（点卡片即选中），「待移除」用卡片边色 + 批量按钮表达。这是 elys 设计稿已定的方向（`IcaPage.vue:31`–:47），比 Niantong 的双 checkbox 列表更 fancy。
- Niantong 的「地形图 inset 在功率谱卡右上角」→ elys 详情区把地形图升级成独立大图（`IcaPage.vue:59`），网格里每卡再放 xs 缩略图。两种用法同一个 `<TopomapView>`，只是 size 不同。
- Niantong 的「事件 / 通道选择器」（对比图对照通道）→ elys 详情区对比图上方加一个轻量通道选择（或沿用顶栏）。

### 5.6 状态管理

- **运行态决策**（暂停 / 勾选 / 提交 / 恢复）沿用 `useIcaInteraction.ts`，不动其骨架——它已经接通后端 `getNodeInteraction/submitNodeDecision/resumeNode`。
- **可视化态**（当前成分 idx、选中事件 / 通道、四图 payload、各渲染器实例引用）新建 `useIcaVisualization.ts`：负责拉 component 二进制、缓存、喂四个图。渲染器实例（uPlot / topo renderer）用 `shallowRef` 持有。
- 两者解耦：决策态决定「excluded_components」，可视化态决定「现在看哪个成分」。`excluded` 集合驱动成分卡边色 + 对比图的 `components_to_remove`。

### 5.7 配色 / 样式如何走 elys

- 头皮轮廓、电极描边、等值线、坏道色：全部改 elys CSS 变量（参照 `IcaPage.vue:316` 的 `--c-border-strong` 等），不再写死 `#4d5f72`。
- 色标：建议 RdBu_r 发散色（待 §8 定）。
- keep/remove/doubt 边色沿用 `IcaPage.vue:310`–:312（`--c-success` / `--c-danger` / `--c-warning`）。
- 字体走 elys 字体变量，标签 `paint-order: stroke` 白描边保可读性（沿用 Niantong `:1017` 的技巧）。

---

## 6. 缓存接入（引用 ./01）

缓存原理见 `./01_前后台多级缓存机制.md`，本节只说本页接哪几层、key 怎么构。

本页涉及三类缓存：

1. **ICA 成分结果缓存（trace_code / 内容哈希 短路）** —— 对应 §4.1。
   - 多级：L1 内存（Map）+ L2 持久（IndexedDB）+ 服务端哈希短路（204）。
   - cache key 参照 Niantong `getICAComponentCacheKey`（`Call_ICA_Data_From_Backend.js:50`）：`datasetToken|comp:{idx}|e:{epoch}|ch:{channel}`；持久层再叠 `ica-component|icaId|inputDataId|comp|epoch|channel`（`:65`）。
   - elys 化：把 `datasetToken` 换成 elys 的 `study_output` / `trace_code`（节点结果指纹），与 ./01 的「节点结果 trace_code 缓存」对齐。`known_hash` → 204 短路保留。

2. **EEG 窗口缓存（L1/L3）** —— 仅当 topomap 复用在**时域观察页**时：拖游标取「当前窗口」的样本走 EEG 窗口缓存（L1 内存窗 + L3 服务端切片），topomap 只是消费窗口里某一列。本 ICA 页**不直接**碰它，但 `<TopomapView>` 作为共享组件，其消费方（时域页）会接。

3. **TFR 切片缓存** —— 仅当 topomap 复用在**频域 / TFR 页**取「某频段功率分布」时相关，本页不接，列此仅为说明 `<TopomapView>` 的复用边界。

去抖与防过期（属缓存协同，不属缓存本身）：成分切换 70ms 去抖 + `requestKey` 短路（Niantong `:78`）、对比 250ms 去抖 + `requestSeq`/snapshot 防 stale 覆盖（`:772`、:934）——elys 在 `useIcaVisualization.ts` 复刻。

cache key 构造原则：**凡是会改变图内容的输入都进 key**（成分 idx、事件、对照通道、待移除集、输入数据指纹），避免「换了成分还显示旧图」。

---

## 7. 分阶段开发计划

### P1 · `<TopomapView>` 独立组件（先把引擎搬通）🆕

- 交付物：`<TopomapView>` Vue 组件，内部移植 `createTopographyRenderer` 全部画图逻辑（IDW / 鲁棒色限 / Canvas ImageData / d3-contour / SVG 电极层 / 点击 hover / 坏道 / scale / resize），配色样式换 elys 变量。先喂**静态假数据**（一组 64 通道坐标 + 随机权重）验证渲染。
- 验收：屏上出正确头皮图，拖一个 slider 改权重能流畅重绘（rAF 节流生效），点击电极高亮，resize 不崩；TypedArray 不进响应式（性能验证：64 通道 96×96 每帧 < 8ms）。

### P2 · 后端 ICA 可视化端点（补数据通路）🆕

- 交付物：elys 后端新增（移植 `ica_visualization_utils.py` 逻辑，但 topomap 只吐 positions + weights，不算 CloughTocher2D）：
  - 成分二进制端点（地形图 positions+weights / 时序 / 频谱 一次取，沿用 §4.1 二进制布局 + 哈希短路）
  - 滤波前后对比端点（§4.2）
  - 成分列表 / dataset_info（§4.3）
  - 电极坐标 helper（移植 `channel_position_utils.py`）
- 验收：云端真机 ICA 节点跑通后，端点返回真实成分数据，二进制解码无尺寸错位（对齐 `window_decode_worker.js` 校验）。

### P3 · ICA 四图接真实数据 🆕

- 交付物：`useIcaVisualization.ts` + `IcaTimecourseChart`（uPlot）/ `IcaSpectrumChart`（SVG）/ `IcaComparisonChart`（uPlot 双线）/ `IcaComponentGrid`（每卡 `<TopomapView size=xs>`）/ `IcaDetailPanel`（大 topomap）。把 `IcaPage.vue` 从静态稿改造成接 P2 端点的真实页；保留现有视觉语言。
- 验收：点成分卡 → 四图同步刷新；勾选 / 批量标记 → 对比图随 `components_to_remove` 更新；与 `useIcaInteraction.ts` 决策态联动（excluded 集驱动边色 + 应用按钮）。

### P4 · 缓存接入 🆕

- 交付物：接 ./01 的成分结果缓存（L1/L2 + 哈希短路）、去抖 / 防过期复刻。
- 验收：来回切成分秒回（命中缓存）、重复请求触发 204 短路、快速连点不出现旧图覆盖新图。

### P5 · FigureSpec / 矢量出图 ⏸（阻塞于 ./00 FigureSpec 定稿）

- 交付物：`renderTopomapSvg(FigureSpec)` 纯函数（等值线填充色块版），topomap 接 FigureSpec 单一事实源；导出 SVG / PDF。
- 验收：导出的矢量图与屏上预览一致；可进 Methods 自动出图链路。

### P6 · 复用回灌到时域 / 频域页 🆕

- 交付物：时域观察页拖游标驱动 `<TopomapView>`（接 EEG 窗口缓存）、PSD 页选频段驱动 topomap（接 TFR 切片缓存）。
- 验收：三处共用同一个 `<TopomapView>`，行为一致。

---

## 8. 待讨论问题

1. **色标走哪套？** Niantong 用 `interpolateSpectral`（彩虹谱，工程感强）；elys persona 是临床 / 科研，RdBu_r（蓝-白-红发散色）更符合「关心偏离 0」的电位 / 权重语义且论文常见。是否统一切 RdBu_r？是否做成 `<TopomapView>` 的可配 prop（不同子图不同色：电位用发散、功率用顺序色）？

2. **插值分工最终拍板**：确认「后端只给 positions + weights、前端统一 IDW（power=3）、ICA 端点也不返 CloughTocher2D 网格」这条（§5.4）。这关系到后端要不要保留 scipy CloughTocher2D 路径（mne 1.7.1 / scipy 1.14.1 环境锁，见记忆「mne 版本坑」）。

3. **ICA 页布局取舍**：Niantong 是「左三选择器 + 两 checkbox 列表 + 右三图卡 + 地形图 inset」；elys 静态稿是「顶栏 + 成分网格 + 选中详情 + 右侧推荐栏」。详情区四图怎么排（2×2？还是地形图大图 + 三小图）？事件 / 对照通道选择器放顶栏还是详情区对比图旁？

4. **成分自动标签从哪来？** elys 静态稿有 keep/remove/doubt + 眼动 / 肌电 / 心电 + 置信度（`IcaPage.vue:177`），这需要 ICLabel 之类的自动分类。当前 elys 后端 `components` 只有 std/max_abs/top_channels（`useIcaInteraction.ts:146`），Niantong 也没有自动分类。是先把 UI 的标签 / 置信度做成「占位 + 留接口」，还是这阶段引入 ICLabel？

5. **`<TopomapView>` 的 props 边界**：是否让它同时接「整段 payload（多帧 data + times + index）」（时域 / 频域复用，沿用 Niantong `renderAtIndex(payload, index)`）和「单帧 weights」（ICA 复用）两种入参？还是统一成「单帧 weights + 外部驱动帧切换」由消费方负责取帧？

6. **缓存 key 的数据指纹用什么？** Niantong 用 `datasetToken|comp|epoch|channel` + 服务端内容哈希。elys 是否统一用节点 `trace_code`（节点结果指纹）作为前缀，使 topomap / 时域 / 频域 / TFR 缓存 key 同构？这点与 ./01 联动，需对齐。

---

## 9. 关键文件:行号速查

Niantong（只读参照）：

- topomap 引擎：`../../Niantong-eeg-analysis/frontend/js/ui/VisualFactors_Topography.js`
  - `createTopographyRenderer` :644 ｜ `ensureForPayload`（建结构）:706 ｜ `renderAtIndex`（逐帧）:1057 ｜ `schedule`（rAF 节流）:1172
  - IDW `computeInterpolatedValue` :534 ｜ 网格权重预计算 :812–:835 ｜ 鲁棒色限 `computeRobustAbsLimit` :503
  - 色标 `interpolateSpectral` :1044 ｜ 等值线 `d3.contours` :1117 ｜ 电极点击 :939 / 双击 :947 ｜ 坏道渲染 :1140
  - 矢量导出 `buildVectorSvgString` :1207 ｜ 防重叠布点 :277 ｜ 头皮 / 鼻 / 耳 SVG :899–:927 ｜ `destroy` :1264
- 后端电极坐标：`../../Niantong-eeg-analysis/backend/channel_position_utils.py:53`（`get_standard_channel_positions`，MNE `_find_topomap_coords` :91）
- ICA 后端数据：`../../Niantong-eeg-analysis/backend/ica_visualization_utils.py`
  - `get_ica_topography_data` :138（前端只用其 `channel_positions`/`channel_weights`）｜ `get_ica_timecourse` :52 ｜ `get_ica_spectrum` :91 ｜ `get_spatial_filter_comparison` :396 ｜ `get_all_components_list` :528 ｜ `get_dataset_info` :478
- ICA 编排：`../../Niantong-eeg-analysis/frontend/js/ui/Interact_ICA.js`
  - shell 布局 `buildShellHtml` :232（左控制区 :326 / 右三图卡 :364 / 地形图 inset :370）
  - 四图入口 `updateICATopography` :1036 / `updateICATimecourse` :1120 / `updateICASpectrum` :1268 / `updateICAComparison` :1349
  - 对比数据流防过期 `updateSpatialComparisonFromRemovalList` :789（isStale :772）｜ 成分去抖优化 :78 ｜ topomap 降维喂引擎 :1062–:1076 ｜ ResizeObserver :1100
- 二进制取数：`../../Niantong-eeg-analysis/frontend/js/core/Call_ICA_Data_From_Backend.js`
  - `fetchICAComponentBinary` :140（请求 :162 / 204 短路 :182）｜ cache key :50 / 持久 key :65 ｜ 对比解码 `ICACMP01` :276 ｜ `fetchICAComparison` :329
- 二进制协议：后端 `../../Niantong-eeg-analysis/backend/fastapi_server.py:9576`（成分二进制布局）；端点 `/api/ica/component` :10442、`/api/ica/comparison` :10725、`/api/ica/dataset_info` :10322、`/api/ica/matrix` :10258 ｜ worker 解码 `../../Niantong-eeg-analysis/frontend/js/core/window_decode_worker.js:10`
- 功率谱 / 对比图渲染：`../../Niantong-eeg-analysis/frontend/js/ui/VisualFactor_ICAPower.js:136`（D3 SVG 折线）、`VisualFactor_ICAFilterComparison.js:13`、`VisualFactors_CompToRemove.js:37`（DOM 选择器）
- wiki：`../../Niantong-eeg-analysis/docs/wiki/02-功能模块-02-预处理模块.md`、`../../Niantong-eeg-analysis/doc/ICA_visual_data_process.md`

elys（落地目标）：

- ICA 页静态稿：`../../elys_project/frontend/elys-web/src/views/IcaPage.vue`（成分网格 :31 / 详情四图 :58 / 右侧栏 :124 / 视觉变量 :316）
- ICA 决策交互（运行态，保留）：`../../elys_project/frontend/elys-web/src/composables/pipeline/useIcaInteraction.ts:26`（getNodeInteraction :73 / submitNodeDecision :105 / resumeNode :129 / 元信息 :146）
- ICA 交互 schema：`../../elys_project/backend/app/schemas/pipeline.py:358`（`PipelineInteractionResponse`，excluded_components :372）

本系列其它文档：`./00_总览与架构决策.md`（FigureSpec / 双渲染平面）、`./01_前后台多级缓存机制.md`（多级缓存原理）、`./05_待讨论问题清单.md`（汇总 §8）。
