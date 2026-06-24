import { describe, it, expect } from 'vitest'
import type { NodeSpec, NodeProperty } from '@/types'
import { planNodeWidgets, summarizeComplexParam, MAX_NODE_WIDGETS } from './nodeWidgetPlan'

const spec = (properties: NodeProperty[]): NodeSpec =>
  ({
    schema_version: '3.0',
    type: 't',
    title: 'T',
    category: 'preprocessing',
    phase: 'phase1',
    inputs: [],
    outputs: [],
    properties,
    backend: {},
  } as unknown as NodeSpec)

const P = (p: Partial<NodeProperty> & { name: string; type: NodeProperty['type'] }): NodeProperty =>
  ({ label: p.name, ...p } as NodeProperty)

describe('planNodeWidgets', () => {
  it('Filter(带通)：select→combo + 两个 number；advanced 排除、陷波项被 visible_when 隐藏', () => {
    const s = spec([
      P({ name: 'filter_type', type: 'select', default: 'bandpass', options: [
        { label: '带通', value: 'bandpass' }, { label: '陷波', value: 'notch' } ] }),
      P({ name: 'l_freq', type: 'number', default: 1, visible_when: { filter_type: ['bandpass', 'highpass'] } }),
      P({ name: 'h_freq', type: 'number', default: 40, visible_when: { filter_type: ['bandpass', 'lowpass'] } }),
      P({ name: 'notch_freq', type: 'number', default: 50, visible_when: { filter_type: ['notch'] } }),
      P({ name: 'method', type: 'select', default: 'fir', advanced: true, options: [{ label: 'FIR', value: 'fir' }] }),
    ])
    const plans = planNodeWidgets(s, { filter_type: 'bandpass', l_freq: 0.5, h_freq: 30 })
    expect(plans.map((p) => p.name)).toEqual(['filter_type', 'l_freq', 'h_freq'])
    const combo = plans[0]
    expect(combo.kind).toBe('combo')
    if (combo.kind === 'combo') {
      expect(combo.value).toBe('带通') // 当前值 bandpass → 显示中文 label
      expect(combo.valueByLabel['陷波']).toBe('notch') // label→value 反查表
    }
    expect(plans[1].kind).toBe('number')
    if (plans[1].kind === 'number') expect(plans[1].value).toBe(0.5)
  })

  it('visible_when 切换：filter_type=notch 时显示工频、隐藏 l_freq/h_freq', () => {
    const s = spec([
      P({ name: 'filter_type', type: 'select', default: 'bandpass', options: [
        { label: '带通', value: 'bandpass' }, { label: '陷波', value: 'notch' } ] }),
      P({ name: 'l_freq', type: 'number', default: 1, visible_when: { filter_type: ['bandpass'] } }),
      P({ name: 'notch_freq', type: 'number', default: 50, visible_when: { filter_type: ['notch'] } }),
    ])
    expect(planNodeWidgets(s, { filter_type: 'notch' }).map((p) => p.name)).toEqual(['filter_type', 'notch_freq'])
  })

  it('number 上下界俱全 → 滑块；否则步进器；integer 精度 0', () => {
    const s = spec([
      P({ name: 'order', type: 'integer', default: 4, min: 1, max: 12 }),
      P({ name: 'gain', type: 'number', default: 1.0 }),
    ])
    const plans = planNodeWidgets(s, {})
    expect(plans[0].kind).toBe('slider')
    if (plans[0].kind === 'slider') expect(plans[0].precision).toBe(0)
    expect(plans[1].kind).toBe('number')
  })

  it('boolean → toggle；复杂类型 → 摘要按钮', () => {
    const s = spec([
      P({ name: 'flag', type: 'boolean', default: true }),
      P({ name: 'conditions', type: 'event_select', label: 'Conditions' }),
    ])
    const plans = planNodeWidgets(s, { conditions: ['a', 'b'] })
    expect(plans[0].kind).toBe('toggle')
    if (plans[0].kind === 'toggle') expect(plans[0].value).toBe(true)
    expect(plans[1].kind).toBe('button')
    if (plans[1].kind === 'button') expect(plans[1].summary).toBe('2 项')
  })

  it('跳过 text/string；总数封顶 MAX_NODE_WIDGETS', () => {
    const props = [P({ name: 'note', type: 'text', default: 'x' })]
    for (let i = 0; i < 8; i += 1) props.push(P({ name: `n${i}`, type: 'number', default: i }))
    const plans = planNodeWidgets(spec(props), {})
    expect(plans.length).toBe(MAX_NODE_WIDGETS)
    expect(plans.some((p) => p.name === 'note')).toBe(false) // text 不上节点
  })

  it('summarizeComplexParam：数组计数 / 对象按筛选 / 空未设置', () => {
    expect(summarizeComplexParam(['a', 'b', 'c'])).toBe('3 项')
    expect(summarizeComplexParam([])).toBe('未设置')
    expect(summarizeComplexParam({ subjects: 'all' })).toBe('按筛选')
    expect(summarizeComplexParam('')).toBe('未设置')
  })
})
