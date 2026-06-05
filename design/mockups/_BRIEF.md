# 念析 ELYS · 全站静态设计稿 — Agent 作业规范

你的任务：把**指定的一个** ELYS 页面，做成一份**静态 HTML 设计稿**，套用念析 ELYS 设计系统（Steel 主题）。这是**换皮 / 重排版**，不是写功能——纯静态展示，逻辑全部用假数据表现。

## 必读（按顺序）

1. `design/mockups/_template.html` —— 骨架。**照抄 `<head>` 和 `<header class="topbar">`**，只改 `<title>` 和把当前页对应的 nav 项设 `is-active`。把内容写进 `<main class="page">` 内。
2. 你的 **Vue 源文件**（路径见任务）—— 从中提取**真实的字段名、分区、控件、列、状态枚举**，让设计稿反映这个页面**真实的信息结构**（不要照搬旧样式，只取“有哪些内容”）。
3. 你的 **JSX 目标模板**（若任务给了）—— 这是该页在新设计系统里的**目标长相**，尽量对齐它的布局与组件。
4. 需要查类定义时读 `design/mockups/assets/kit.css` 和 `assets/elys-design-system.css`。

## 产出

- 单文件：`design/mockups/<name>.html`（`<name>` 见任务）。
- **只写这一个文件**。不要改 `_template.html`、`_BRIEF.md`、`assets/`、或任何其他页面。

## 五条铁律（违反即返工）

1. **用色 60/30/10**：中性灰占绝大多数；主色 + 语义色是点缀。
2. **一屏一高亮**：整页只有一个 `.btn--primary` 实心主操作；其余用 `.btn`（次）/ `.btn--ghost` / `.btn--link`。
3. **颜色只给状态，不给分类**：实体类型用**中性灰文字 chip**区分；颜色（绿/蓝/琥珀/红）只表示 成功/进行/警告/失败。
4. **描边或重阴影二选一**：卡片 = `1px 边框 + --shadow-sm`，悬停才升一档。绝不又描边又重投影。
5. **同屏最多 3 级字阶**；`< 12px` 只允许 mono 数字标签（ID / 时间戳）。

## 内容规则

- **简体中文**，安静、陈述、不营销：无感叹号、无“快来/立即”这类话术。
- **ID / code / 时间戳**用 mono（`.cell-mono` / `.study-code` / `font-family:var(--ff-mono)`），数字列加 `tabular-nums`。
- **状态提示只显非零项**，写人话：用 `2 个处理中 · 1 个已发布`，**绝不**写 `working 1 · active 0 · error 0`。无异常就别显示状态条/横幅（安静=可信）。
- **相对时间**真实：`刚刚 / 12 分钟前 / 1 小时前`，绝对时间放 `title`。
- **绝不用 emoji / unicode 符号当图标**。只用线性图标 sprite（见下）。
- 示例数据要**适量、逼真**，口吻参考：`sub093 ERP` / `sub093-erp` / `静息态闭眼 ERP 分析` / `ICA 分解` / `task-erp` / `64 ch` / `1000 Hz` / `06/05 03:24`。

## 图标用法

```html
<svg class="icon" width="16" height="16"><use href="assets/elys-icons.svg#i-database"/></svg>
```
可用 id：`grid database folder branch layers eye bars image cpu search spark logout refresh clock plus check x chevron-down chevron-right arrow-right play pause filter more download upload settings file activity check-circle alert`。nav/行内 16px，顶栏图标按钮 18px。

## 类词汇表（只用这些，别造新类/新魔法数字/别引组件库）

- **页面骨架**：`.page` · `.page__header` · `.page__title`(h1) · `.page__subtitle` · `.page__title-row`(标题+徽章同行) · `.dashboard-actions`(右上操作组) · `.dashboard-sections`(纵向 flex，块间 32) · `.dashboard-grid`(主 1.55fr + 侧 .9fr 两栏)
- **面板**：`.dashboard-panel` · `.section-head`(内含 `h2` + `p` + 右侧 action；标题前可加 `<span class="live-dot">`)
- **按钮**：`.btn` · `.btn--primary` · `.btn--ghost` · `.btn--icon` · `.btn--sm` · `.btn--link` · `.btn--block`
- **统计卡**：`.page-stat-strip` 网格 + `.stat-card`（`__top`>`__label`+`__chip`(图标) · `__value`(big，内 `<small>`单位) · 二选一：`__foot`>`__bar`(内 `<i style="flex;background">`)+`__legend`(`span`>`<em 圆点>`+`<b 数>`+文字)，或 `__hint` 一句人话）
- **研究项行**：`.study-list` + `.srow2`（`__main`>`__title`(strong + `.srow2__code`) + `__meta`(`.desc`/`.sep`/`.m`>`<b>`，需处理用 `.m.attn`)；`__right`>状态徽章 + `.srow2__time`）
- **状态徽章**：`.tag2.ok`(活跃/已发布) · `.tag2.warn`(已归档/待处理) · `.tag2.neu`(草稿/中性)，内含 `<i>` 圆点 + 文字
- **运行行**：`.run-list` + `.run-row`（`.run-row__dot`+`is-running/is-waiting/is-failed/is-queued` · `__body`>`__title`(strong+`<span>运行 #N</span>`)+`<p>`动词·步骤 · 运行中加 `.run-progress`>`<span>` · `.run-row__time`）
- **活动时间线**：`.tl2` + `.tl2__row`（`.tl2__dot`+`ok/info/warn` · `.tl2__main`>`.tl2__top`(strong+`.act`+`.time`)+`.tl2__sub`(`.type`中性 + `.sep` + `归属 X`)）
- **数据表**：`.table-wrap` > `table.dtable`（`th`/`th.num` · `td`/`td.num` · `.cell-strong` · `.cell-mono` · `.cell-id`）
- **工具/筛选条**：`.toolbar`(+`.toolbar__spacer`) · `.search`(图标+input) · `.seg`(button，选中 `.is-active`)
- **Tab**：`.tabs` > `button.tab`(选中 `.is-active`；可带 `.tab__count`)
- **面包屑**：`.crumb`（`<a>` + `chevron-right` 图标 + `<b>` 当前）
- **详情双栏**：`.detail-grid`(主 + 300px 侧) · 侧栏用 `.meta-list` > `.meta-list__row`(`.meta-list__k` / `.meta-list__v`(.mono))
- **工作流卡**：`.wf-card`（`__head`: branch 图标 + strong + `.study-code` + spacer + 状态徽章 · `.pipeline`>`.pstep`(`.pstep__n` 序号) 步骤芯片，芯片间 `chevron-right.sep` · `__foot`: `<b>` 数 + 文字 + 试跑按钮）
- **空状态**：`.empty.empty--quiet`（`.empty__icon` + `strong` + `p`）—— 安静、虚线感
- **警示横幅**：`.attention-banner`(`--danger`/`--warn`) —— **只在真有失败/待确认时出现**，本稿一般 happy path 不放
- **Toast**：`.toast` —— 仅做演示时放一个

## chrome 三型（任务会指明）

- **workbench**（绝大多数页）：用 `_template.html` 的顶栏；按本页所属设 nav `is-active`。`观察/统计/作图/机器学习` 这四个是 `is-preview` 预览项，对应的分析页把它设 `is-active`（保留 is-preview 也行）。
- **landing**（仅首页 Index）：**不要工作台顶栏**。保留 template 的 `<head>` 与 `<html class>`，`<body>` 自己写：落地页 `app-header`（logomark + 念析 ELYS + 右侧轻导航 + 登录按钮）+ hero + 功能区 + 流程 + 页脚。克制，**不要营销大图/插画/渐变背景**。
- **login**（仅登录 Login）：**不要顶栏**。用 `.login` > `.login__card`（`.login__brand`: `.logomark`大号 + h1`念析 ELYS` + tagline `脑电研究的专业仪器` · 若干 `.field`(label+input) · `.btn--primary.btn--block` 登录）。

## 多页一致性

所有页共用同一套 css / sprite / 顶栏。**别自定义颜色、间距、圆角**——一律用变量与上面的类。拿不准的组件，去 `assets/kit.css` 找类，没有就用最接近的现成类，别新造。

## 收尾自检

- [ ] head + 顶栏与 `_template.html` 一致，只动了 title 和 is-active
- [ ] 一屏只有一个实心主按钮
- [ ] 实体类型是中性 chip，颜色只用于状态
- [ ] ID/时间是 mono，数字 tabular-nums
- [ ] 无 emoji；图标都用 sprite
- [ ] 真实字段来自 Vue 源；示例数据逼真适量

## 分析 / 可视化页配色（重要补充 —— 审查发现的高频坑）

观察类页（ERP/PSD/TFR/连接/微状态/源/ICA/波形）最容易违反铁律 3，补三条硬规则：
1. **通道 / 频段 / ROI / 成分 等“分类”一律中性灰 chip**（用 `.study-code` 那种 mono 灰底徽章，或 `.tag2.neu`）。**绝不用颜色区分分类**。
2. **图内确需配色**（色标、网络弧、地形图图例、序列曲线）时，只用**数据可视化令牌** `var(--d-1)`…`var(--d-8)`（L4 调色板），**禁止写死十六进制**；L4 不与 UI 的 L1–L3 串用。
3. **差值 / 对比列（Δ）不要无脑染绿**：差值是中性数据，用 `--c-text`；只有当某值真代表“成功/失败”状态时才上语义色。

## 观察子导航统一（ERP/PSD/TFR/连接/微状态/源 六页共用）

这六页顶部用同一套 `.tabs`，**元素统一用 `<button>`、标签集与顺序完全一致**：
`事件相关电位` · `功率谱 PSD` · `时频 TFR` · `功能连接` · `微状态` · `源定位`。
面包屑首段「观察」一律链到 `erp.html`（观察枢纽），不要链 `dashboard.html`。

## 状态色走类、不内联；终态语义要准

需处理 / 警告等状态色用现成类（`.m.attn`、`.tag2.warn`），不要 `style="color:var(--c-warning)"` 内联。终态语义别用错：撤回 / 驳回 / 归档**不是“成功”**，别套 `.tag2.ok`（绿），用中性或对应语义。
