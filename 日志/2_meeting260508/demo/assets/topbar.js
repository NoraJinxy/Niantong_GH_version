/* 念析 ELYS — 共享顶部导航 v2
 * 依赖 assets/icons.js（必须先于本文件加载）
 *
 * 用法：
 *   <div id="topbar-mount"></div>
 *   <script src="assets/icons.js"></script>
 *   <script src="assets/topbar.js"></script>
 *   <script>renderTopbar('<key>');</script>
 *
 * key 取值：dashboard / projects / analysis / observe / stats / figure / ai
 */

const TOPBAR_ITEMS = [
  { key: 'dashboard', label: '仪表盘',   href: 'dashboard.html',  ico: 'dashboard' },
  { key: 'projects',  label: '项目管理', href: 'projects.html',   ico: 'projects'  },
  { key: 'analysis',  label: '分析',     href: 'pipeline.html',   ico: 'analysis'  },
  { key: 'observe',   label: '观察',     href: 'view.html',       ico: 'observe'   },
  { key: 'stats',     label: '统计',     href: 'statistics.html', ico: 'stats'     },
  { key: 'figure',    label: '作图',     href: 'figures.html',    ico: 'figure'    },
  { key: 'ai',        label: '机器学习', href: 'ml.html',          ico: 'ai'        },
];

function renderTopbar(activeKey) {
  // 容错：icons.js 没加载时退化到内联 SVG（避免页面崩）
  const safeIcon = (typeof icon === 'function') ? icon : (n) => `<svg class="ico" viewBox="0 0 24 24" width="18" height="18"></svg>`;

  const navHTML = TOPBAR_ITEMS.map(item => `
    <a href="${item.href}" class="${item.key === activeKey ? 'is-active' : ''}" data-key="${item.key}">
      ${safeIcon(item.ico, { size: 16 })}
      <span>${item.label}</span>
    </a>
  `).join('');

  const html = `
    <header class="topbar">
      <a href="index.html" class="topbar__brand" title="返回首页">
        <div class="logo">析</div>
        <div class="topbar__brand-text">
          <strong>念析</strong>
          <small>NIANXI EEG</small>
        </div>
      </a>
      <nav class="topbar__nav">${navHTML}</nav>
      <div class="topbar__right">
        <button class="icon-btn" title="搜索">
          ${safeIcon('search', { size: 16 })}
        </button>
        <button class="icon-btn" title="任务">
          ${safeIcon('clock', { size: 16 })}
          <span class="badge">3</span>
        </button>
        <button class="icon-btn" title="通知">
          ${safeIcon('bell', { size: 16 })}
        </button>
        <button class="icon-btn" title="设置" onclick="window.location='admin.html'">
          ${safeIcon('settings', { size: 16 })}
        </button>
        <div class="user-chip" title="张三 · 管理员">
          <div class="avatar">张</div>
          <span>张三</span>
        </div>
      </div>
    </header>
  `;

  const mount = document.getElementById('topbar-mount');
  if (mount) mount.outerHTML = html;
  // 在 outerHTML 替换后，重新触发 [data-ico] 注入（如果有）
  if (typeof window.ELYS_ICON_INJECT === 'function') window.ELYS_ICON_INJECT();
}
