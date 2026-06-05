/* ============================================================
 * 念析 ELYS · 图标库 v1
 * ------------------------------------------------------------
 * 设计语言：
 *   • 24×24 viewBox（Feather/Lucide 兼容）
 *   • 仅描边（stroke-only），统一 stroke-width = 1.8
 *   • 圆角端点：stroke-linecap / linejoin = round
 *   • 单色：currentColor，颜色由父元素 color 决定
 *   • 视觉密度：14-22 px 区间清晰可读
 *
 * 用法：
 *   import-style:   <span data-ico="dashboard" data-size="18"></span>
 *   programmatic:   element.innerHTML = icon('dashboard', { size: 22, cls: 'is-active' });
 *   inline-string:  document.querySelector('.x').innerHTML = icon('search');
 *
 * 全局：页面加载后会自动扫描 [data-ico] 元素并注入对应 SVG。
 * ============================================================ */

const ICONS = {
  /* ── 主导航（7 项） ── */
  'dashboard': '<rect x="3" y="3" width="7" height="9" rx="1.2"/><rect x="14" y="3" width="7" height="5" rx="1.2"/><rect x="14" y="12" width="7" height="9" rx="1.2"/><rect x="3" y="16" width="7" height="5" rx="1.2"/>',
  'projects':  '<path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/>',
  'analysis':  '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
  'observe':   '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>',
  'stats':     '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>',
  'figure':    '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>',
  'ai':        '<rect x="4" y="6" width="16" height="14" rx="2"/><path d="M12 6V3"/><line x1="9" y1="3" x2="15" y2="3"/><circle cx="9" cy="13" r="1.2"/><circle cx="15" cy="13" r="1.2"/><line x1="9" y1="17" x2="15" y2="17"/>',

  /* ── 通用动作（16 项） ── */
  'plus':      '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
  'minus':     '<line x1="5" y1="12" x2="19" y2="12"/>',
  'close':     '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
  'check':     '<polyline points="20 6 9 17 4 12"/>',
  'search':    '<circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
  'filter':    '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>',
  'sort':      '<line x1="3" y1="6" x2="21" y2="6"/><line x1="6" y1="12" x2="18" y2="12"/><line x1="9" y1="18" x2="15" y2="18"/>',
  'download':  '<path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
  'upload':    '<path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>',
  'share':     '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>',
  'copy':      '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>',
  'trash':     '<polyline points="3 6 5 6 21 6"/><path d="M19 6l-1.4 14.4A2 2 0 0115.6 22H8.4a2 2 0 01-2-1.6L5 6"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/><path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2"/>',
  'edit':      '<path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/>',
  'save':      '<path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>',
  'refresh':   '<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9A9 9 0 0118.36 5.64L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/>',
  'more':      '<circle cx="5" cy="12" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="19" cy="12" r="1.4"/>',

  /* ── 播放控制（4 项） ── */
  'play':      '<polygon points="6 4 20 12 6 20 6 4"/>',
  'pause':     '<rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/>',
  'stop':      '<rect x="5" y="5" width="14" height="14" rx="2"/>',
  'restart':   '<polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 102.13-9.36L1 10"/>',

  /* ── 文件 / 存储（5 项） ── */
  'file':      '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/>',
  'folder':    '<path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/>',
  'file-data': '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M8 17l2-3 3 5 4-7"/>',
  'file-image':'<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><circle cx="10" cy="13" r="1.5"/><polyline points="20 17 16 13 8 19"/>',
  'archive':   '<polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5"/><line x1="10" y1="12" x2="14" y2="12"/>',

  /* ── EEG / 神经科学专属（12 项） ── */
  'brain-top': '<ellipse cx="12" cy="12" rx="9" ry="8"/><line x1="12" y1="4" x2="12" y2="20"/><path d="M8 6c-1 2 0 4 1 5-1 1-2 3-1 5"/><path d="M16 6c1 2 0 4-1 5 1 1 2 3 1 5"/>',
  'brain-side':'<path d="M12 3a9 9 0 00-9 9c0 3 1.5 5 4 6.5L8 21h2v-3l1-1h2l2 1v3h2l1-2.5C20 17 21 15 21 12a9 9 0 00-9-9z"/><path d="M8 12c1-1 2-1 3 0M14 13c1-1 2-1 3 0"/>',
  'electrode': '<circle cx="12" cy="13" r="5"/><line x1="12" y1="3" x2="12" y2="8"/><line x1="9" y1="3" x2="15" y2="3"/><circle cx="12" cy="13" r="1.6" fill="currentColor" stroke="none"/>',
  'topomap':   '<circle cx="12" cy="12" r="9"/><path d="M11 3.5h2"/><path d="M3.5 11v2"/><path d="M20.5 11v2"/><circle cx="12" cy="9" r="2.5"/><circle cx="9" cy="14" r="1"/><circle cx="15" cy="14" r="1"/>',
  'wave':      '<path d="M3 12c2-3 4-3 6 0s4 3 6 0 4-3 6 0"/>',
  'waves':     '<path d="M3 7c2-2 4-2 6 0s4 2 6 0 4-2 6 0"/><path d="M3 12c2-2 4-2 6 0s4 2 6 0 4-2 6 0"/><path d="M3 17c2-2 4-2 6 0s4 2 6 0 4-2 6 0"/>',
  'spectrum':  '<line x1="4" y1="20" x2="4" y2="14"/><line x1="9" y1="20" x2="9" y2="8"/><line x1="14" y1="20" x2="14" y2="11"/><line x1="19" y1="20" x2="19" y2="16"/>',
  'heatmap':   '<rect x="3" y="3" width="18" height="18" rx="1.2"/><line x1="9" y1="3" x2="9" y2="21"/><line x1="15" y1="3" x2="15" y2="21"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/>',
  'network':   '<circle cx="12" cy="5" r="2"/><circle cx="5" cy="18" r="2"/><circle cx="19" cy="18" r="2"/><circle cx="12" cy="12" r="1.5"/><line x1="12" y1="7" x2="12" y2="10.5"/><line x1="11" y1="13" x2="6" y2="16.5"/><line x1="13" y1="13" x2="18" y2="16.5"/>',
  'scatter':   '<circle cx="6" cy="18" r="1.4"/><circle cx="9" cy="14" r="1.4"/><circle cx="12" cy="11" r="1.4"/><circle cx="15" cy="9" r="1.4"/><circle cx="18" cy="6" r="1.4"/><line x1="3" y1="3" x2="3" y2="21"/><line x1="3" y1="21" x2="21" y2="21"/>',
  'box-plot':  '<line x1="6" y1="6" x2="6" y2="18"/><rect x="3" y="9" width="6" height="6"/><line x1="14" y1="6" x2="14" y2="18"/><rect x="11" y="11" width="6" height="6"/>',
  'source-3d': '<path d="M12 2a9 9 0 00-9 9c0 4 2 6 4 8h10c2-2 4-4 4-8a9 9 0 00-9-9z"/><circle cx="11" cy="10" r="2.5" fill="currentColor" stroke="none"/>',

  /* ── 流程 / 工作流（4 项） ── */
  'pipeline':  '<circle cx="6" cy="6" r="2"/><circle cx="18" cy="18" r="2"/><circle cx="18" cy="6" r="2"/><line x1="8" y1="6" x2="16" y2="6"/><line x1="8" y1="6" x2="8" y2="18"/><line x1="8" y1="18" x2="16" y2="18"/>',
  'branch':    '<line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 01-9 9"/>',
  'merge':     '<circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M6 21V9a9 9 0 009 9h3"/>',
  'flow':      '<rect x="3" y="3" width="6" height="6" rx="1"/><rect x="15" y="3" width="6" height="6" rx="1"/><rect x="3" y="15" width="6" height="6" rx="1"/><rect x="15" y="15" width="6" height="6" rx="1"/><line x1="9" y1="6" x2="15" y2="6"/><line x1="6" y1="9" x2="6" y2="15"/><line x1="9" y1="18" x2="15" y2="18"/><line x1="18" y1="9" x2="18" y2="15"/>',

  /* ── UI 控件（8 项） ── */
  'chev-up':    '<polyline points="18 15 12 9 6 15"/>',
  'chev-down':  '<polyline points="6 9 12 15 18 9"/>',
  'chev-left':  '<polyline points="15 18 9 12 15 6"/>',
  'chev-right': '<polyline points="9 18 15 12 9 6"/>',
  'arrow-left': '<line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>',
  'arrow-right':'<line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>',
  'expand':     '<polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/>',
  'collapse':   '<polyline points="4 14 10 14 10 20"/><polyline points="20 10 14 10 14 4"/><line x1="14" y1="10" x2="21" y2="3"/><line x1="3" y1="21" x2="10" y2="14"/>',

  /* ── 状态（5 项） ── */
  'info':         '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>',
  'alert':        '<path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
  'warning':      '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
  'check-circle': '<path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
  'x-circle':     '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>',

  /* ── 工具与系统（9 项） ── */
  'settings': '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 00.34 1.83l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.7 1.7 0 00-1.83-.33 1.7 1.7 0 00-1 1.5V21a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1.1-1.5 1.7 1.7 0 00-1.83.33l-.06.07A2 2 0 114.27 16.9l.06-.06a1.7 1.7 0 00.33-1.83 1.7 1.7 0 00-1.5-1H3a2 2 0 110-4h.1a1.7 1.7 0 001.5-1.1 1.7 1.7 0 00-.33-1.83l-.06-.06a2 2 0 112.83-2.83l.06.06a1.7 1.7 0 001.83.33h.07a1.7 1.7 0 001-1.5V3a2 2 0 114 0v.1a1.7 1.7 0 001 1.5 1.7 1.7 0 001.83-.33l.06-.07a2 2 0 112.83 2.83l-.06.06a1.7 1.7 0 00-.33 1.83v.07a1.7 1.7 0 001.5 1H21a2 2 0 110 4h-.1a1.7 1.7 0 00-1.5 1z"/>',
  'user':     '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0116 0"/>',
  'users':    '<path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/>',
  'bell':     '<path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/>',
  'lock':     '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/>',
  'clock':    '<circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15 14"/>',
  'pin':      '<line x1="12" y1="17" x2="12" y2="22"/><path d="M5 17h14v-1.76a2 2 0 00-1.11-1.79L15 12V7l1-1V4H8v2l1 1v5l-2.89 1.45A2 2 0 005 15.24V17z"/>',
  'code':     '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>',
  'home':     '<path d="M3 12l9-9 9 9"/><path d="M5 10v10a1 1 0 001 1h12a1 1 0 001-1V10"/>',

  /* ── 数据操作（4 项） ── */
  'import':   '<path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>',
  'export':   '<path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
  'database': '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>',
  'table':    '<rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/><line x1="9" y1="3" x2="9" y2="21"/>',
};

/**
 * 生成 SVG 字符串
 * @param {string} name 图标名
 * @param {object} opts { size?: 18, cls?: '', strokeWidth?: 1.8 }
 */
function icon(name, opts = {}) {
  const { size = 18, cls = '', strokeWidth = 1.8 } = opts;
  const inner = ICONS[name] || ICONS['info'];
  return `<svg class="ico ${cls}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${strokeWidth}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${inner}</svg>`;
}

/* 自动注入：扫描 [data-ico] 元素 */
(function () {
  function inject() {
    document.querySelectorAll('[data-ico]').forEach(el => {
      if (el.dataset.icoInjected) return;
      const name = el.dataset.ico;
      const size = +el.dataset.size || 18;
      const sw = +el.dataset.stroke || 1.8;
      el.innerHTML = icon(name, { size, strokeWidth: sw });
      el.dataset.icoInjected = '1';
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', inject);
  else inject();
  // 暴露给后续动态插入
  window.ELYS_ICON_INJECT = inject;
})();
