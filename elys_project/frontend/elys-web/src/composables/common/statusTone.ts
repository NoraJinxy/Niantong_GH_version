// 全站状态色调（tone）词表：StatusPill 组件与各域的「状态 → tone」映射函数共用同一套枚举，
// 避免每个页面各写一套药丸配色。具体配色由 StatusPill.vue 的 scoped 样式落地（读全局 CSS 变量）。
export type StatusTone = 'success' | 'warn' | 'danger' | 'muted' | 'info'
