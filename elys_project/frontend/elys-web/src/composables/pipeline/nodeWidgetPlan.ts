// 工作流编辑器 · 节点就地控件「规划层」（纯函数，无 litegraph / 无 Vue 依赖，可单测）
//
// 把一个节点的 spec.properties + 当前 params 翻译成「画在节点卡片上的 1~4 个控件描述」。
// 真正 addWidget / 画布绑定在 PipelinePage.applyNodeWidgets 里做；这里只决定「出哪些控件、初值是什么」。
//
// 规则（与 useNodeParamEditor 的可见性口径一致）：
//   - 跳过 advanced（高级设置留检查器）、跳过 text/string（决策：文本不放节点，避开 litegraph prompt）；
//   - visible_when 当前命中才出（如陷波才显示「工频」）；
//   - 标量 select/number/integer/boolean → 下拉 / 步进 / 滑块 / 开关，就地编辑；
//   - 复杂类型（通道 / 事件 / 标签 / 数据集）→ 摘要按钮，点击跳右侧检查器对应区；
//   - 总数封顶 MAX_NODE_WIDGETS（保持「简洁优雅」）。

import type { NodeSpec, NodeProperty } from '@/types'

/** 每个节点最多就地放几个控件（决策：封顶 4）。 */
export const MAX_NODE_WIDGETS = 4

/** 复杂类型：没有简单控件，做成「摘要 + 编辑 ›」按钮，点开右侧检查器编辑。 */
const COMPLEX_TYPES = new Set(['channel_list', 'event_select', 'tags_input', 'dataset_filter', 'dataset_ids'])
/** 不放节点的类型（文本走检查器，避开 litegraph 的浏览器 prompt）。 */
const SKIP_TYPES = new Set(['text', 'string'])

export type NodeWidgetPlan =
  | { kind: 'combo'; name: string; label: string; value: string; labels: string[]; valueByLabel: Record<string, unknown> }
  | { kind: 'number'; name: string; label: string; value: number; min: number | null; max: number | null; step: number; precision: number }
  | { kind: 'slider'; name: string; label: string; value: number; min: number; max: number; precision: number }
  | { kind: 'toggle'; name: string; label: string; value: boolean }
  | { kind: 'button'; name: string; label: string; summary: string }

function isFiniteNum(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v)
}

/** 默认值 + 实参合并（实参非空才覆盖默认）—— 给 visible_when 判定和取初值用，口径同 useNodeParamEditor。 */
function effectiveParams(spec: NodeSpec, params: Record<string, unknown>): Record<string, unknown> {
  const eff: Record<string, unknown> = {}
  for (const p of spec.properties) if (p.default !== undefined) eff[p.name] = p.default
  for (const [k, v] of Object.entries(params || {})) if (v !== undefined && v !== null && v !== '') eff[k] = v
  return eff
}

function isVisible(prop: NodeProperty, eff: Record<string, unknown>): boolean {
  const rules = prop.visible_when
  if (!rules) return true
  return Object.entries(rules).every(([key, allowed]) => allowed.map((x) => String(x)).includes(String(eff[key])))
}

/** 复杂参数的一行摘要：数组→「N 项」、对象→「按筛选」、字符串→截断、空→「未设置」。 */
export function summarizeComplexParam(value: unknown): string {
  if (Array.isArray(value)) return value.length ? `${value.length} 项` : '未设置'
  if (value && typeof value === 'object') return '按筛选'
  const s = String(value ?? '').trim()
  if (!s) return '未设置'
  return s.length > 10 ? `${s.slice(0, 10)}…` : s
}

/** 节点 spec + 当前 params → 就地控件描述列表（封顶 MAX_NODE_WIDGETS）。 */
export function planNodeWidgets(spec: NodeSpec | null | undefined, params: Record<string, unknown>): NodeWidgetPlan[] {
  if (!spec) return []
  const eff = effectiveParams(spec, params)
  const plans: NodeWidgetPlan[] = []

  for (const prop of spec.properties) {
    if (plans.length >= MAX_NODE_WIDGETS) break
    if (prop.advanced) continue
    if (SKIP_TYPES.has(prop.type)) continue
    if (!isVisible(prop, eff)) continue

    const raw = params?.[prop.name]
    const current = raw !== undefined && raw !== null && raw !== '' ? raw : prop.default

    if (COMPLEX_TYPES.has(prop.type)) {
      plans.push({ kind: 'button', name: prop.name, label: prop.label, summary: summarizeComplexParam(current) })
    } else if (prop.type === 'boolean') {
      plans.push({ kind: 'toggle', name: prop.name, label: prop.label, value: Boolean(current) })
    } else if (prop.type === 'select') {
      const opts = prop.options || []
      const labels = opts.map((o) => o.label)
      const valueByLabel: Record<string, unknown> = {}
      for (const o of opts) valueByLabel[o.label] = o.value
      // litegraph combo 用 label 数组显示/循环；这里把当前值映射回 label，回调时再 label→value 反查存真值。
      const curLabel = opts.find((o) => String(o.value) === String(current))?.label ?? labels[0] ?? String(current ?? '')
      plans.push({ kind: 'combo', name: prop.name, label: prop.label, value: curLabel, labels, valueByLabel })
    } else if (prop.type === 'number' || prop.type === 'integer') {
      const min = isFiniteNum(prop.min) ? prop.min : null
      const max = isFiniteNum(prop.max) ? prop.max : null
      const num = isFiniteNum(Number(current)) ? Number(current) : 0
      const isInt = prop.type === 'integer'
      const precision = isInt ? 0 : 1
      const step = isFiniteNum(prop.step) ? prop.step : 1
      // 上下界俱全 → 滑块（直观可拖）；否则步进器（可拖可改）。
      if (min !== null && max !== null) {
        plans.push({ kind: 'slider', name: prop.name, label: prop.label, value: num, min, max, precision })
      } else {
        plans.push({ kind: 'number', name: prop.name, label: prop.label, value: num, min, max, step, precision })
      }
    }
  }

  return plans
}
