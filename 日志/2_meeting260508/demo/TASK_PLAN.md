# 念析 (ELYS) HTML 静态页面 — 任务计划与进度

> 本文件是工作清单与执行日志。每完成一项即在此处更新状态。中断后可基于本文件无缝续作。

## 1. 项目目标

根据 `2_meeting260508/07-前端页面/` 中的所有 markdown 规格文档，制作一套静态 HTML 页面：

- **风格**：简洁美观、科技风、白色 / 浅色底
- **可用性**：信息引导直觉化，小白能上手；熟练用户使用方便、有效率
- **结构**：每份 md 规格文档至少对应一个 html 文件，行为分支多的拆成多个文件
- **链接**：页面之间相互跳转，符合 sitemap 拓扑
- **输出位置**：所有 html / css / js 资产保存在 `2_meeting260508/demo/` 目录下
- **不参考**：不读取或使用 `deepseek/`、`GLM5.1/` 文件夹

## 2. 设计系统规范（统一遵守）

| 项 | 取值 |
|---|---|
| 主色调 | 极简白底 `#FFFFFF` / `#F7F9FC`，主操作色 `#2E6BFF` (科技蓝)，强调色 `#00C2A8` (青绿) |
| 文字色 | 主文 `#1B2940`，次文 `#5B6B85`，弱文 `#8A95A8` |
| 边框 | `#E5E9F2` 细线 1px，圆角 8-12px |
| 阴影 | `0 1px 2px rgba(27,41,64,.04), 0 4px 12px rgba(27,41,64,.06)` |
| 字体 | -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif |
| 等宽 | "JetBrains Mono", "Consolas", monospace |
| 图标 | 内联 SVG（统一 stroke 1.6px，线条风） |
| 间距尺度 | 4 / 8 / 12 / 16 / 24 / 32 / 48 |
| 全局 CSS | `assets/style.css`（共享变量、布局、组件） |
| JS | `assets/app.js`（侧栏切换、tab 切换、轻交互） |

布局采用两套：
- **沉浸布局**：登录、工作流编辑器、观察浏览、作图编辑器
- **标准布局**：其余页面，左侧 240px 侧栏 + 顶栏 56px

## 3. 文件清单与状态

> 状态枚举：⬜ 待办 / 🟦 进行中 / ✅ 完成

### 3.1 共享资产
| 资产 | 状态 | 备注 |
|---|---|---|
| `assets/style.css` | ✅ | 设计系统全局样式 |
| `assets/app.js` | ✅ | 侧栏 / tab / 简单交互 |

### 3.2 页面文件
| # | 源文档 | 输出 HTML | 状态 | 备注 |
|---|---|---|---|---|
| 0 | — | `index.html` | ✅ | 项目首页 / 入口聚合，落地页 |
| 1 | 02-登录页.md | `login.html` | ✅ | 三 Tab：登录 / 注册 / SSO |
| 2 | 03-仪表盘.md | `dashboard.html` | ✅ | 工作台总览 |
| 3 | 04-项目列表.md | `projects.html` | ✅ | 列表 + 卡片视图 |
| 4 | 05-项目详情.md | `project-detail.html` | ✅ | 7 Tab |
| 5 | 06-数据导入.md | `import.html` | ✅ | 上传 + BIDS 转换 |
| 6 | 07-工作流编辑器.md | `pipeline.html` | ✅ | 节点画布占位 + 配置面板 |
| 7 | 08-预处理交互.md | `preprocess.html` | ✅ | 坏通道 / 坏段 / ICA Tab |
| 8 | 09-观察浏览.md | `view.html` | ✅ | 类型选择入口 |
| 9 | 09a-时域ERP观察.md | `view-erp.html` | ✅ | 时域 ERP |
| 10 | 09b-频域PSD观察.md | `view-psd.html` | ✅ | 频域 PSD |
| 11 | 09c-时频TFR观察.md | `view-tfr.html` | ✅ | 时频 TFR |
| 12 | 09d-脑网络观察.md | `view-connectivity.html` | ✅ | 脑网络 |
| 13 | 09e-微状态观察.md | `view-microstate.html` | ✅ | 微状态 |
| 14 | 09f-溯源观察.md | `view-source.html` | ✅ | 溯源 |
| 15 | 11-统计分析.md | `statistics.html` | ✅ | 三步式向导 |
| 16 | 12-作图编辑器.md | `figures.html` | ✅ | 三栏：数据 / 画布 / 样式 |
| 17 | 13-机器学习工作台.md | `ml.html` | ✅ | ML 工作流 |
| 18 | 14-管理面板.md | `admin.html` | ✅ | 用户 / 角色 / 系统 / 审计 |
| 19 | 01-共享组件与布局.md | （融入所有页面） | ✅ | 顶栏 / 侧栏 / 任务条 |

### 3.3 验收
| 项 | 状态 | 备注 |
|---|---|---|
| 所有页面在浏览器可打开 | ✅ | 静态文件，纯 HTML/CSS/JS |
| 顶栏 / 侧栏导航互链全通 | ✅ | 共 19 个唯一 .html 引用全部存在 |
| 视觉风格一致 | ✅ | 共用 `assets/style.css`（CSS 变量 + 组件） |
| 移动端可用（基本响应式） | ✅ | 媒体查询折叠侧栏（≤960px）+ grid 自动堆叠 |

## 4. 信息架构（页面互链拓扑）

```
index.html
   ├─→ login.html
   └─→ dashboard.html ──→ projects.html ──→ project-detail.html
                          └→ admin.html        ├─→ import.html
                                               ├─→ pipeline.html
                                               ├─→ preprocess.html
                                               ├─→ view.html ─┬─→ view-erp.html
                                               │              ├─→ view-psd.html
                                               │              ├─→ view-tfr.html
                                               │              ├─→ view-connectivity.html
                                               │              ├─→ view-microstate.html
                                               │              └─→ view-source.html
                                               ├─→ statistics.html
                                               ├─→ figures.html
                                               └─→ ml.html
```

## 5. 执行日志（每完成一项追加一行；中断后从最后一行继续）

- **2026-05-08**：开始任务，创建 TASK_PLAN.md。读取 README、登录、共享组件、概述、需求总览。
- **2026-05-08**：读完全部 19 个页面规格文档。
- **2026-05-08**：完成共享设计系统 `assets/style.css` 与 `assets/app.js`。
- **2026-05-08**：完成 `index.html`（首页落地页 + 全部页面导航卡片）。
- **2026-05-08**：完成 `login.html`（三 Tab：登录 / 注册 / SSO）。
- **2026-05-08**：完成 `dashboard.html`（KPI / 项目 / 任务 / 系统状态 / 活动）。
- **2026-05-08**：完成 `projects.html`（卡片+列表双视图、筛选、新建项目对话框）。
- **2026-05-08**：完成 `project-detail.html`（7 Tab：概览/被试/数据/工作流/结果/图表/日志）。
- **2026-05-08**：完成 `import.html`（三步式向导：目标 → 上传 → 选项 + QA 摘要）。
- **2026-05-08**：完成 `pipeline.html`（节点面板 + 画布 + SVG 连线 + 配置面板 + 底栏进度）。
- **2026-05-08**：完成 `preprocess.html`（波形 / 坏通道 / ICA 三 Tab，含 SVG 波形与 IC 缩略图）。
- **2026-05-08**：完成 `view.html`（六类观察类型选择卡片 + 最近结果跳转）。
- **2026-05-08**：完成 `view-erp.html`（叠加/分行/网格 + SEM/峰值/差异波）。
- **2026-05-08**：完成 `view-psd.html`（频谱叠加 + 频段背景 + IAF + 频段对比柱状图）。
- **2026-05-08**：完成 `view-tfr.html`（时频热图 + ERP/PSD 子图 + 显著轮廓 + 色彩映射）。
- **2026-05-08**：完成 `view-connectivity.html`（圆形图/邻接矩阵/3D 脑 + 图论指标）。
- **2026-05-08**：完成 `view-microstate.html`（K=4 模板 + GFP 序列 + 转移矩阵 + 参数表）。
- **2026-05-08**：完成 `view-source.html`（3D 皮层 + ROI 时序 + 排行表 + 切片视图）。
- **2026-05-08**：完成 `statistics.html`（左方法树 / 中配置+结果 / 右多重比较+Cluster）。
- **2026-05-08**：完成 `figures.html`（三栏：数据绑定 / 所见即所得画布 / 样式 + 期刊预设 + 批量导出）。
- **2026-05-08**：完成 `ml.html`（节点画布 + SHAP 特征重要性 + ROC + 混淆矩阵 + Saliency）。
- **2026-05-08**：完成 `admin.html`（用户/系统/审计/统计四 Tab + 系统状态侧栏）。
- **2026-05-08**：交叉链接验证通过，所有 19 个唯一 .html 引用对应实存文件。
- **2026-05-08**：✅ 全部 20 个 HTML 页面 + 共享 CSS/JS 完成交付。

## 6. 二次迭代（参考 elys_v1）

### 6.1 第一步 · 顶部导航（2026-05-08 完成）

按 elys_v1 的设计模式，把 7 个核心模块从「侧栏」抬升到「顶部主导航」：仪表盘 / 项目管理 / 分析 / 观察 / 统计 / 作图 / 机器学习。

| 资产 | 状态 | 说明 |
|---|---|---|
| `assets/style.css` 新增 `.topbar` 样式 | ✅ | sticky · 56px · 毛玻璃白底 · 主操作色高亮 |
| `assets/topbar.js`（新增） | ✅ | `renderTopbar(activeKey)` 渲染 logo + 7 项导航 + 右侧操作 |
| 17 个工作台页面挂载 | ✅ | dashboard / projects / project-detail / import / pipeline / preprocess / view + 6 子页 / statistics / figures / ml / admin |
| `index.html`（落地页） | ⏸ | 保留独立营销头，不接入主导航 |
| `login.html` | ⏸ | 独立认证布局，不接入主导航 |

**active key 映射**：
- `dashboard` → dashboard.html
- `projects` → projects.html / project-detail.html / import.html
- `analysis` → pipeline.html / preprocess.html
- `observe` → view.html / view-erp/psd/tfr/connectivity/microstate/source.html
- `stats` → statistics.html
- `figure` → figures.html
- `ai` → ml.html
- 无激活 → admin.html

### 6.2 第二步 · ERP 观察页重设计（2026-05-08 完成）

参考 `elys_v1/observe-timeseries.html`，把 `claude/view-erp.html` 重写为「左选择器 / 中 2×3 面板网格 / 右统计」三栏布局。

| 改动 | 状态 | 说明 |
|---|---|---|
| 顶部子页 Tab | ✅ | 时域 ERP / 频域 PSD / 时频 TFR / 脑网络 / 微状态 / 溯源 6 项链接 |
| 左侧选择器面板（244px） | ✅ | 数据集 checkbox 树 + 条件 pill + 通道 chip + 试次 range + 4 种布局快选 |
| 中央工具栏 | ✅ | 时窗 / Y 轴 / 单试次开关 / 平均开关 / 置信区间 / 区间统计按钮 |
| 已选区间提示条 | ✅ | 浅蓝底 · 显示 300-500 ms（P300 窗口） |
| 2×3 面板网格 | ✅ | Fz / FCz / Cz / CPz / Pz + 蝶形图（含 GFP 包络与图例） |
| 动态 SVG ERP 生成 | ✅ | 内嵌 JS：N100 + P300 高斯峰 + 噪声 + 单试次淡线 + S1/S2 双均值曲线 |
| 右侧统计面板（300px） | ✅ | 区间提示卡 + 5 通道 stat-card（最大/潜伏/均值/面积）+ S1 vs S2 对比表 + 导出按钮 |
| 设计令牌对齐 | ✅ | elys_v1 的 `--accent / --teal / --green ...` → `--c-primary / --c-success ...`；保留 elys_v1 的视觉密度与组件命名 |

### 6.3 第三步 · 出图设计器重设计（2026-05-08 完成）

参考 `elys_v1/figure-designer.html`，把 `claude/figures.html` 重写为「左组件库 / 中所见即所得纸面 / 右属性图层」三栏出图工作台。

| 改动 | 状态 | 说明 |
|---|---|---|
| 左侧 224px 组件库 | ✅ | 8 数据图组件（ERP/PSD/TFR/拓扑/网络/柱/箱线/散点）+ 8 装饰元素（文本/箭头/矩形/直线/比例尺/图例/子图标签/注释）+ 3 期刊模板（Cell/Nature/IEEE）+ 数据源导入按钮 |
| 中央工具栏 | ✅ | 撤销/重做 · 画布尺寸+方向 · 4 种对齐 · 组合/解组/锁定 · 缩放百分比 · 网格/预览/导出 |
| 中央纸面 | ✅ | 800×1131 白纸 + 浅色辅助网格 + 棋格画布背景；4 个绝对定位面板 + 标题区 + 论文 caption |
| 4 个真实 panel SVG | ✅ | (a) ERP Stroke vs Control 含 95% CI 置信带<br>(b) 拓扑双图（Stroke / Control）+ 电极点 + RdBu 色彩条（默认选中，含 8 个手柄）<br>(c) 柱状图含误差线 + ⋆⋆⋆/⋆⋆ 显著性括号 + 双组图例<br>(d) 时频 TFR + cluster 显著轮廓 + 色彩条 |
| 右侧 296px 属性面板 | ✅ | 已选元素卡片 / 位置尺寸 (X/Y/W/H + 锁定纵横比) / 图表属性（数据源·色彩映射·数值范围·等高线·电极·色彩条）/ 排版（边框/字体/字号/内边距）/ 6 层图层列表 / 导出选项（格式/DPI/色彩空间/嵌入字体/透明背景）+ 主导出按钮 |
| 设计令牌对齐 | ✅ | elys_v1 的 `--accent / --teal / --green ...` → `--c-primary / --c-success ...`；纸面字体保留 `Times New Roman serif` 表达论文级出图质感 |
| 轻交互 | ✅ | 点击 panel 切换高亮选中态；点击图层行切换 active；边框宽度 range 实时显示数值 |

### 6.4 第四步 · TFR 观察页重设计（2026-05-08 完成）

参考 [Brain Products 频谱分析教学文](https://pressrelease.brainproducts.com/spectral-analysis-methods/)，把 `claude/view-tfr.html` 改造为「方法选择 + 参数权衡 + 时频热图 + 多方法对比 + 教学卡片」的交互式时频观察页。

| 改动 | 状态 | 说明 |
|---|---|---|
| 顶部决策提示条 | ✅ | "需要时间信息吗？" → 是/否 → 时频/PSD 分支；同时显示采样率与频率分辨率 |
| 左侧方法选择 | ✅ | 6 个方法卡片：FFT · Welch · STFT · Wavelet (默认选中, 推荐) · Hilbert · Burg AR；每卡含「前置条件徽章」+「一句话描述」 |
| 左侧参数面板 | ✅ | Morlet `c` 滑块 + 公式 `Δf = f / c · 2.355` · 频率范围 · 对数/线性分布 · 4 种归一化（ERS/ERD · dB · z-score · 绝对）+ 基线区间 |
| 中央 RdBu 时频热图 | ✅ | 80×38 单元格按对数频率分布（1→40 Hz）· α ERD (8-13Hz, 320ms) 蓝色凹陷 · β 浅 ERD · θ 微 ERS<br/>+ 黄色 cluster 显著性轮廓 + 刺激线 |
| 安全边界 COI | ✅ | 左右两侧半透明黑色锥形遮罩，频率越低锥越宽（程序生成 path） |
| 上下方联动子图 | ✅ | 顶部 ERP 联动 · 右侧整段 PSD（蓝色填充） |
| 多方法对比图 | ✅ | 同一 α 阻断任务下三条曲线叠加：Wavelet (蓝) / Complex Demod (绿) / ERS-ERD (橙) · 边缘 COI 暗化提示 |
| 右侧 6 行方法对比表 | ✅ | 时间精度 / 频率精度 / 前置条件三列 · ✓ ✗ 中色编码 · Wavelet 行高亮 |
| 教学提示卡片 | ✅ | ① 频率分辨率 `Δf = Fs/N` 含示例计算<br/>② COI 安全边界（橙色警告框）`safety = c/(2·min f)`<br/>③ 时频权衡 `c` 取值建议<br/>④ ERS/ERD 推荐窗长（半周期，α=50ms） |
| 色阶条 | ✅ | 右上浮窗 · −3 → +3 dB · RdBu_r |

### 6.5 第五步 · 脑网络观察页重设计（2026-05-08 完成）

参考用户提供的多面板脑网络图（a/b 脑顶视图 + c Circos 主图 + d/e/f 三种子小图），重写 `claude/view-connectivity.html`。

| 改动 | 状态 | 说明 |
|---|---|---|
| 主画布栅格 | ✅ | 6 行 3 列 grid：左 a/b 脑顶视（1+2 行高）· 中 c Circos 主图（满高）· 右 d/e/f 三个种子子图（各 2 行高） |
| Panel a 全连接脑顶视 | ✅ | 半透明大脑轮廓 + 中线虚线 + 36 个节点按解剖位置散布 + 弧线边按 YlOrRd 色彩 |
| Panel b 种子聚焦脑顶视 | ✅ | 同 a 布局，但 L inf PCUN 节点放大为深红，仅高亮其参与的边，其它边/节点淡化为灰 |
| Panel c Circos 主图 | ✅ | 36 ROI 标签按角度分布（衬线 OK，等宽显数据），每条边为穿过中心的二次贝塞尔，YlOrRd 色映射 |
| Panel d/e/f 种子子图 | ✅ | 缩小版 Circos · 仅显示种子（L SPL / L inf PCUN / R AMYG）的连接，其余 ROI 标签灰化 |
| 色阶与色彩映射 | ✅ | 默认 YlOrRd · 提供 RdBu_r / Spectral / viridis 切换；左下色阶条 Low → High |
| 左侧选择器 | ✅ | 数据集 · 频段 (δθα*βγ) · 连接方法 (wPLI/PLV/Coherence/dPLI/PSI/Granger) · 解剖图谱 · 阈值滑块 (2-40%, 默认 12%) · FDR · 跨半球过滤 · 节点/边/标签开关 |
| 右侧统计 | ✅ | 选中节点卡片（度/介数/聚类/模块）· 全局图论 6 指标（效率/路径/聚类/小世界 σ/模块化 Q/同配性）· 种子节点列表（按度排序，色块=度数）· 教学卡片（小世界系数公式 + 阈值稳定性提示） |
| 交互 | ✅ | 阈值滑块实时重渲染所有 4 个 SVG · 种子列表点击切换高亮 |
| 程序生成 | ✅ | JS：36 ROI · 半结构化连接矩阵（同侧偏好 + hub 中心性 + 同区域偏好）· 阈值化 → top X% 边 · 函数 `drawCircos` 与 `drawBrain` 复用四张图 |

### 6.6 第六步 · 微状态观察页重设计（2026-05-08 完成）

参考用户提供的「微状态分析三联图（A 流水线 + B 转移矩阵对比 + C 组间百分比柱状图）」，重写 `claude/view-microstate.html`。

| 改动 | 状态 | 说明 |
|---|---|---|
| 4 色微状态全局变量 | ✅ | A=黄 (#FBC02D) · B=绿 (#4CAF50) · C=青 (#00BCD4) · D=红 (#F4511E)，与参考图一致，全页保持四色身份 |
| **A 区流水线** | ✅ | 5 行 grid：① 28 通道 raw EEG（黑色叠加 SVG）② GFP 橙色包络 + 11 个峰位竖线带 ABCD 字母标记 ③ 4 模板（diverging RdBu 双极拓扑）+ 配色边框 + 名称/coverage/duration ④ ↓ 指派提示 ⑤ 状态序列色带（15 段不同长度的 ABCD 色块） |
| **B 区转移矩阵 (4 张 2×2)** | ✅ | Schematic（虚线全联）/ Controls vs SCZ / Controls vs Null / SCZ vs Null。每张 ABCD 四角着色 + 黑色实箭头粗细=显著差异；虚灰箭头=非显著；数字注释 |
| **C 区组间百分比柱状图** | ✅ | 3 组（Panic / Schizophrenia / FT Dementia）× 4 状态柱；y 轴 ±30% 双向；带误差线 + 显著性 ⋆；Schizophrenia C=−22% / D=+14% 复现经典文献模式 |
| 4 模板 SVG 拓扑生成 | ✅ | 程序生成：圆形头底 + 鼻/双耳标记 + 13 电极点 + 用 radialGradient 双极配置——A: 右前(红)+左后(蓝) / B: 左前+右后 / C: 前后中线 / D: 中央径向 |
| 左侧选择器 | ✅ | 数据集 4 类被试组 · 当前被试切换（含 HC / SCZ 组平均）· **K 值 4 卡片**（3/4*/5/6, 显示对应 GEV）· 算法（modKM*/AAHC/T-AAHC, 极性合并）· 滤波带 2-20 Hz · GFP 峰检测（最小峰间距滑块, 50ms 平滑）· 显示开关 4 项 |
| 右侧统计 | ✅ | HC 组状态参数表（4 状态 × Dur/Occ/Cov/GFP）· 4×4 转移矩阵（A→C 高亮 ⋆⋆）· HC vs SCZ 显著性表（Δ% + p 值，C=−20.1% .001**）· 教学卡片（四要素定义 + SCZ 经典特征 Koenig 2002 引用）· 三个导出按钮 |
| 设计令牌一致性 | ✅ | 衬线字体（Times New Roman）用于状态字母 ABCD 和图标题；mono 字体用于数据；其余跟随 ELYS 主题 |

### 6.7 第七步 · 溯源观察页重设计（2026-05-08 完成）

参考用户提供的 sLORETA 风格图（5 视角皮层渲染 + 三正交切片 + Log F-ratio 色阶），重写 `claude/view-source.html`。

| 改动 | 状态 | 说明 |
|---|---|---|
| **A 区 5 视角皮层** | ✅ | 横排 5 个 cell：Left Lateral / Top axial / Right Lateral / Left Medial / Right Medial。每 cell 浅灰底 + SVG 脑形 + 装饰沟回 + 多个 hot 渐变热斑（按 SMA/SPL μ 激活模式），剪切到脑形内 |
| **B 区三正交切片** | ✅ | 横排 3 个 cell（黑底）：Axial / Sagittal / Coronal。每 cell 含：①脑切片灰阶轮廓 ②内部低对比纹理散点 ③体素感像素方块矩阵（高斯热斑）+ hot 径向光晕 ④白色十字虚线光标 + 中心圆 ⑤上方/左侧三角箭头标定 ⑥坐标轴 L/R · A/P · ±5cm 标签 + 顶部 [X,Y,Z]=[−6,−28,51] mm 黄色坐标条 + 右下 sLORETA 斜体标签 |
| **C 区 Log F-ratio 色阶** | ✅ | 黑→暗红→红→橙→金→黄→白 的 8 档线性渐变；7 个等距刻度 0.000 / 0.207 / 0.413 / 0.620 / 0.827 / 1.033 / 1.240；右上斜体 "Log F-ratio" |
| Hot colormap 函数 | ✅ | JS 实现 `hot(t)` 三段插值（黑→红 / 红→黄 / 黄→白），用于切片体素方块色彩 |
| 左侧选择器 | ✅ | 数据集 · **5 种溯源方法卡片**（sLORETA*/eLORETA/dSPM/MNE/LCMV，含徽章和一句话描述）· 解剖图谱（5 选）+ 头模板（MNI152/fsaverage5/个体 MRI）· 时窗+频段（Mu 8-13Hz 默认）· 阈值滑块（绑定色阶刻度，0.000-1.240）· 4 配色（Hot 默认 + viridis + Spectral + RdBu）· 5 个显示开关 |
| 右侧统计 | ✅ | **黑底金字坐标卡片**显示选中体素 [X,Y,Z]=[−6,−28,+51] · L Postcentral SMA · F=1.18 / p=.0021** · ROI 排行表（7 ROI，色块从黄到深棕匹配热度）· L SMA 时间序列（峰值 1.18@342ms 高亮黄圆点）· 三张教学卡片（Log F-ratio 解释 / EEG 溯源 1cm 不确定性 / 方法选择指南） |
| 工具栏 | ✅ | 峰值时刻 + [X,Y,Z] 坐标 mono 灰底显示 + 体素大小 + 投影方向 + 显著区/ROI 开关 + 重置视角 + 导出 |
| 设计令牌一致性 | ✅ | UI 走 ELYS 主题；hot 色阶仅用于数据可视化叠加层；Times New Roman serif 用于科学标签和方法名（sLORETA 斜体） |

### 6.8 后续待办

- ⬜ 第八步：剩余 view-psd（频域 PSD）
- ⬜ 第九步：精简侧栏 / 项目上下文条 / 风格细节对齐