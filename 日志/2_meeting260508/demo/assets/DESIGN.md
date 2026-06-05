# 念析 ELYS · 设计语言规约 v2

> 本文件是统一图标 + 配色 + 排版的事实标准。新页面或改动旧页面前请先读这里。

## 1. 设计哲学

| 维度 | 取向 |
|---|---|
| 风格 | 简洁科技（Clean Tech），白底浅色 |
| 信息密度 | 偏紧凑——研究员要在屏幕同时看到很多数字 |
| 字体 | 系统无衬线（PingFang SC / Inter）；衬线 Times New Roman 仅用于科学标签和图表标题 |
| 色彩节制 | UI chrome 只用 L1-L3 色；数据可视化只用 L4 色板，**两层不串用** |
| 图标 | 描边 1.8px、圆头圆角、24×24 viewBox、currentColor |

## 2. 色彩系统

### L1 — 品牌色

| 令牌 | 值 | 用途 |
|---|---|---|
| `--c-primary` | `#2E6BFF` | 主操作 / 链接 / 焦点环 |
| `--c-primary-hover` | `#1F58E0` | 主按钮 hover |
| `--c-primary-soft` | `#E8F0FF` | 选中底色 / 信息底 |
| `--c-accent` | `#00C2A8` | 强调辅色（少量点缀） |
| `--c-accent-soft` | `#DEF7F2` | accent 的浅底 |
| `--c-brand-grad` | 蓝→青线性渐变 | logo / banner |

### L2 — 语义色

| 语义 | 主色 | 浅底 | 用途 |
|---|---|---|---|
| 成功 | `--c-success` `#10B981` | `--c-success-soft` `#D9F5E9` | 完成 / 通过 / 正向 |
| 警告 | `--c-warning` `#F59E0B` | `--c-warning-soft` `#FEF3D7` | 注意 / 待审 |
| 危险 | `--c-danger` `#EF4444` | `--c-danger-soft` `#FCE2E2` | 错误 / 删除 |
| 信息 | `--c-info` `#3B82F6` | `--c-info-soft` `#DBEAFE` | 提示 / 帮助 |

### L3 — 中性色（用于一切 UI 框架）

| 令牌 | 值 | 用途 |
|---|---|---|
| `--c-bg` | `#FFFFFF` | 主背景 |
| `--c-bg-soft` | `#F7F9FC` | 次背景 / 灰区 |
| `--c-bg-tint` | `#EEF2F8` | 输入填充 / 微盒 |
| `--c-surface` | `#FFFFFF` | 卡片表面 |
| `--c-text` | `#1B2940` | 主要文字 |
| `--c-text-2` | `#5B6B85` | 次要文字 |
| `--c-text-3` | `#8A95A8` | 弱化文字 / 占位 |
| `--c-border` | `#E5E9F2` | 默认边框 |
| `--c-border-2` | `#D5DCE8` | hover 边框 |
| `--c-border-strong` | `#B5BEC9` | 强对比边框 |

### L4 — 数据可视化色板

8 色循环用于**类别区分**（ROI / 通道 / 条件 / 类别）。**绝不与 L1-L3 混用。**

| 令牌 | 颜色 | 工具类 | 数据类型示例 |
|---|---|---|---|
| `--d-1` | `#2E6BFF` 蓝 | `.swatch-data.s1` | 主条件 / Group A |
| `--d-2` | `#00C2A8` 青 | `.swatch-data.s2` | 副条件 / Group B |
| `--d-3` | `#F59E0B` 橙 | `.swatch-data.s3` | 第三类 |
| `--d-4` | `#EC4899` 粉 | `.swatch-data.s4` | 第四类 |
| `--d-5` | `#8B5CF6` 紫 | `.swatch-data.s5` | ROI 5 |
| `--d-6` | `#10B981` 绿 | `.swatch-data.s6` | ROI 6 |
| `--d-7` | `#EF4444` 红 | `.swatch-data.s7` | ROI 7 |
| `--d-8` | `#6366F1` 靛 | `.swatch-data.s8` | ROI 8 |

#### 微状态专属 4 色（不可替换）

| 状态 | 色值 | 令牌 | 工具类 |
|---|---|---|---|
| MS-A | `#FBC02D` 黄 | `--ms-a` | `.swatch-ms.A` |
| MS-B | `#4CAF50` 绿 | `--ms-b` | `.swatch-ms.B` |
| MS-C | `#00BCD4` 青 | `--ms-c` | `.swatch-ms.C` |
| MS-D | `#F4511E` 红/珊瑚 | `--ms-d` | `.swatch-ms.D` |

#### 序列 colormap（连续数据）

| 名称 | 渐变令牌 | 类名 | 适用 |
|---|---|---|---|
| Hot | `--grad-hot` | `.cmap-bar.is-hot` | sLORETA F-ratio · 单向激活强度 |
| RdBu_r | `--grad-rdbu` | `.cmap-bar.is-rdbu` | TFR / 差异图 / 双向数据 |
| viridis | `--grad-viridis` | `.cmap-bar.is-viridis` | 通用单调连续 |
| YlOrRd | `--grad-ylorrd` | `.cmap-bar.is-ylorrd` | 脑网络边强度 |

### L5 — 渐变 / 阴影

```css
--grad-warm: linear-gradient(135deg, var(--c-warning), var(--c-danger));
--grad-cool: linear-gradient(135deg, var(--c-primary), var(--d-5));

--shadow-sm: 0 1px 2px rgba(27,41,64,.04);
--shadow:    0 1px 2px rgba(27,41,64,.04), 0 4px 12px rgba(27,41,64,.06);
--shadow-md: 0 2px 6px rgba(27,41,64,.06), 0 12px 28px rgba(27,41,64,.08);
--shadow-lg: 0 8px 24px rgba(27,41,64,.10), 0 24px 48px rgba(27,41,64,.12);
--shadow-glow-primary: 0 4px 14px rgba(46,107,255,.25);
```

## 3. 图标系统

### 规范

| 维度 | 取值 |
|---|---|
| viewBox | `0 0 24 24` |
| stroke | `currentColor` · `1.8px` |
| 端点 | `linecap=round` · `linejoin=round` |
| fill | `none`（除特殊点状元素） |
| 默认尺寸 | `18×18` |
| 可选尺寸 | `sm 14` / `md 18` / `lg 22` / `xl 28` |

### 图标库结构（`assets/icons.js`）

按用途分组，共 **65 个**图标：

| 组 | 数量 | 关键图标 |
|---|---|---|
| 主导航 | 7 | `dashboard` `projects` `analysis` `observe` `stats` `figure` `ai` |
| 通用动作 | 16 | `plus` `close` `check` `search` `filter` `download` `upload` `share` `copy` `trash` `edit` `save` `refresh` `more` … |
| 播放控制 | 4 | `play` `pause` `stop` `restart` |
| 文件 / 存储 | 5 | `file` `folder` `file-data` `file-image` `archive` |
| EEG / 神经 | 12 | `brain-top` `brain-side` `electrode` `topomap` `wave` `waves` `spectrum` `heatmap` `network` `scatter` `box-plot` `source-3d` |
| 流程 / 工作流 | 4 | `pipeline` `branch` `merge` `flow` |
| UI 控件 | 8 | `chev-up` `chev-down` `chev-left` `chev-right` `arrow-left` `arrow-right` `expand` `collapse` |
| 状态 | 5 | `info` `alert` `warning` `check-circle` `x-circle` |
| 工具 / 系统 | 9 | `settings` `user` `users` `bell` `lock` `clock` `pin` `code` `home` |
| 数据操作 | 4 | `import` `export` `database` `table` |

### 用法

**1) 属性自动注入（推荐）**

```html
<!-- 加载库 -->
<script src="assets/icons.js"></script>

<!-- 任何元素加 data-ico 即可 -->
<span data-ico="search"></span>
<span data-ico="trash" data-size="22" data-stroke="2"></span>
```

页面加载完成后 `assets/icons.js` 会自动扫描并注入 SVG。

**2) JS 手动调用**

```js
element.innerHTML = icon('export', { size: 16, cls: 'is-active' });
```

**3) 动态渲染后强制扫描**

```js
window.ELYS_ICON_INJECT();
```

### 图标色彩约定

```css
/* 默认继承 currentColor，所以这样直接生效 */
.btn--primary [data-ico] { color: #fff; }
.nav-item.is-active     { color: var(--c-primary); }
.icon-btn               { color: var(--c-text-2); }
.icon-btn:hover         { color: var(--c-text); }
```

**绝对禁止**：直接给 `<svg>` 加 `fill` 或 `stroke` 写死颜色。要换色就改父元素 `color`。

## 4. 字体系统

```css
--ff-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
           "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif;
--ff-mono: "JetBrains Mono", "Consolas", "Menlo", "Courier New", monospace;
--ff-display: "Inter", var(--ff-sans);
```

| 场景 | 字体 |
|---|---|
| 一般 UI 文本 | `--ff-sans` |
| 数据 / 代码 / 数值 | `--ff-mono` |
| 科学图表标签 / Caption | `'Times New Roman', serif`（仅图内） |
| Logo "念析" | `--ff-display` 加粗 |

## 5. 命名约定

| 前缀 | 含义 | 示例 |
|---|---|---|
| `--c-*` | 通用色 | `--c-primary`, `--c-text-2` |
| `--d-1..8` | 数据色板 | `--d-1`, `--d-7` |
| `--ms-*` | 微状态专属 | `--ms-a` |
| `--grad-*` | 渐变 | `--grad-hot`, `--grad-rdbu` |
| `--hot-0..5` | colormap stops | `--hot-2` |
| `.is-*` | 状态修饰 | `.is-active`, `.is-on` |
| `.btn--*` | 按钮变体 | `.btn--primary` |
| `.cmap-bar.is-*` | colormap | `.cmap-bar.is-rdbu` |
| `data-ico="*"` | 图标声明 | `data-ico="search"` |

## 6. 反模式（不要做）

| ❌ | ✅ |
|---|---|
| `<svg fill="#2E6BFF">` 写死颜色 | 父元素 `color: var(--c-primary)` |
| 在 UI chrome 用 `--d-3` 橙 | 在 UI chrome 只用 `--c-warning` |
| 用 `#2E6BFF` 直接出现在 CSS | 总是用 `var(--c-primary)` |
| 微状态用 `--c-primary` 等代替 | 微状态四色保持 `--ms-a/b/c/d` |
| 不同页面的图标 stroke 1.5/1.6/1.8/2 混用 | 全部走 icons.js（1.8 统一） |
| TFR 热图用 `linear-gradient(...)` 写死 | 用 `var(--grad-rdbu)` |
| 重要信息只靠颜色（红/绿）传达 | 配合 ⋆ 显著性符号、文字 |

## 7. 维护

- 加新图标：编辑 `assets/icons.js` 的 `ICONS` 字典即可
- 调色：编辑 `assets/style.css` `:root` 的 token，全站生效
- 新页面：先用 `data-ico` + 现有 token，不要新增颜色