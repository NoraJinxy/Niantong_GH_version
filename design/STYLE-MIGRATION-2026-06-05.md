# 前端风格迁移报告 · 2026-06-05

把生产 Vue 前端的视觉风格整体迁移到 **Steel 钢蓝**主题。**核心约束（用户三令五申）：显示内容与交互方式一律不变。** 本次只动样式层，**零 `.vue` 改动**。

---

## 1. 改了什么

唯一改动文件：`elys_project/frontend/elys-web/src/style.css`（全局样式，3277 行）。

### 1.1 令牌降饱和换肤（`:root`）
所有组件都引用 `var(--c-*)` 令牌，改令牌值即可让 **21 个页面一次性换肤**，markup 一行不动。

| 令牌 | 旧（vivid） | 新（Steel） |
|---|---|---|
| `--c-primary` | `#2E6BFF` 亮蓝 | `#3F5E8F` 钢蓝 |
| `--c-accent` | `#00C2A8` 青绿 | `#5E7BA8` 同系 |
| `--c-brand-grad` | 蓝→青 | 钢蓝同系 |
| `--c-success/warning/danger` | 高彩度 | 降彩度（如 success `#10B981`→`#4F8A6B`） |
| `--c-bg-soft / text / border` | 偏中性 | 转冷灰（text `#1B2940`→`#20293B` 等） |
| `--shadow-glow-primary` | 蓝光晕 `rgba(46,107,255,.25)` | 极轻阴影 |

> 数据可视化色板 `--d-1…--d-8`（L4）**保留不动**——图表 / 网络 / ROI 用色与 UI 用色分离是既有规则。

### 1.2 去装饰（"克制"）
都是全局 CSS 行，无 template 影响：
- 主按钮光晕、logo / 登录 logo 蓝光晕 → 极轻中性阴影
- `.avatar` 写死蓝青渐变 → `var(--c-brand-grad)`
- `.auth-stage` / `.hero` / `.module-hero` 蓝青径向 / 线性**渐变背景 → 纯色面**
- `.hero h1 .grad` 标题**文字渐变 → 实色** `var(--c-primary)`
- task-dock 脉冲动画、上传「处理中」状态的蓝残留 → 钢蓝

### 1.3 补字阶令牌
新增 `--fs-display / h1 / h2 / h3 / body / caption / micro`（标准版 v3 口径）。**不强改现有组件字号**（避免动版式 / 内容）。

---

## 2. 为什么是"换肤"而不是"按 mockup 重排页面"

之前的 `design/mockups/` 静态稿用的是新设计系统 kit 组件（分段统计卡、数据表 `dtable`、`tag2`、`tl2` 时间线…）。**若把这些套进生产页，会改变信息结构和交互方式**——直接违反「内容与交互不变」。

所以生产迁移的正确做法 = **全局令牌换肤 + 去装饰**：一处 CSS、全站生效、行为零风险。像素级贴近 mockup 的组件级重排，属于"会改内容"的动作，留作**后续逐页评审**再定。

---

## 3. 验证与安全

- ✅ `npm run build`（vite）**通过**：21 页全编译、CSS 打包无误（仅 PipelinePage 体积告警，既有，与本次无关）。因为没碰任何 `.vue`，**内容与交互按构造不变**。
- ✅ 顺带刷新 `dist/`，清掉了 `ProjectsPage` / `ProjectDetailPage` / `ImportPage` 等**旧迭代残留**产物。
- ⚠️ 本机无运行环境，**视觉效果需部署后肉眼核**（`deploy_remote.cmd`）。
- 🛟 仓库**无 git**：已把 `src/` 快照备份到 `_backups/elys-web-src-20260605/`，需回滚直接覆盖回去。

---

## 4. 顺带"捋清楚"前端的发现

1. **无版本控制**：整个仓库不是 git 仓库。强烈建议 `git init` + 首次提交，否则每次改动无安全网（本次靠手动备份兜底）。
2. **本地构建曾损坏**：`package.json` 列了 `@fontsource-variable/inter` 但 `node_modules` 没装，`vite build` 直接挂在 `main.ts` 的字体 import。已 `npm install` 修好（补 1 包）。新环境 checkout 后需先 `npm install`。
3. **`style.css` 是多代迭代的叠层**（3277 行）：注释可见 `v2 (ported from demo)` / `V1 业务样式` / `Demo 工作台` / landing / `module-*` 等层。抽查 `study-card`/`module-stage`/`import-scope`/`pipeline-mock` 仍被 Index/Studies/StaticWorkbench/Datasets 使用（**非死代码**）；`net-edge`/`task-dock` 疑似孤儿。建议用 PurgeCSS / coverage 工具做一次**正式死 CSS 审计**再删，别手工猜。
4. **两套并存的组件词汇**：生产页用 `.stat`/`.card`/`.study-card`/`.table`/`.badge`/`.module-*`；新设计系统 kit 用 `.stat-card`/`.srow2`/`.dtable`/`.tag2`/`.tl2`。长期看二者应收敛成一套（即逐页 port），但那会改内容，需评审。
5. **设计文档漂移**（早先已记）：`6-01`/`6-05` 里的圆角 10 vs 12、文字色 `#17233c` vs `#1B2940`、顶栏 48 vs 56 等仍与令牌不一致，待对账。

---

## 5. 未做 / 后续清单

| 项 | 说明 |
|---|---|
| observe 等"死页面"精修 | 按用户指示，只吃全局换肤，不单独动 |
| datasets 状态列统一 | 用户已同意；属组件级改，需碰 template，留待评审 |
| 组件级贴 mockup | 把生产页 port 到新 kit 组件——会改内容/交互，逐页评审 |
| 死 CSS 审计 | PurgeCSS 扫 `style.css` 真·未用类 |
| `git init` | 建版本控制安全网 |
| 设计文档对账 | 6-01/6-05 漂移值对齐到令牌 |
| 残留极少蓝点 | spinner 轨道 / blink / 连接图 viz mock 等死页面里几处 `rgba(46,107,255)`，低优先 |

---

## 6. 怎么看效果 / 怎么回滚

- **看效果**：`deploy_remote.cmd` 部署后在浏览器看；或本机 `npm run dev`（需后端起着才有数据，但登录页 / 落地页 / 外壳样式可直接看）。
- **回滚**：`_backups/elys-web-src-20260605/` 覆盖回 `src/`。

---

## 7. 续（同日）：组件 scoped 样式的 de-blue

发现全局 `style.css` 之外，各 `.vue` 的 `<style scoped>` 里还有硬编码亮蓝**漏网**。区分两类：
- **UI chrome 泄漏**（选中行边框 / 焦点光晕 / 装饰底色把品牌蓝写死）→ 在 **live 页**上会与钢蓝 UI 打架，已修。
- **数据可视化**（地形图 / 波形 / 色标 / 热力图 / 节点色）→ 按设计系统「viz 只用 L4」规则**本就该保持彩色**，不动；且多在分析"死页面"。

**已 steel 化（live 页 UI chrome）**：`DatasetsPage`（dataset-row / tab / decision-panel / target-panel 的选中·hover 边框+光晕+`#f7faff` 蓝底 → 钢蓝 + `var(--c-primary-soft)`，5 处）、`ResultsPage`（result-row 选中态 + 预览区装饰径向渐变，3 处）。`npm run build` 通过。

**核对结果**：DatasetsPage 已无残留品牌蓝；Studies / StudyDetail / Dashboard / Login / Index 本就干净。剩余品牌蓝全部是合法 viz（分析页地形图 / 波形 / 色标 / Pipeline 画布节点色）或 **Results 的 `data-type-tag` 分类色**——后者是"颜色给分类"（PSD 蓝 / TFR 青…），违设计原则但属信息编码，**留给你定**要不要改中性。
