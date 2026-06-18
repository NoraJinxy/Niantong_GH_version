import { describe, it, expect } from 'vitest'
import { computeSnakeLayout } from './litegraphUtils'

// 用 100×100 的等距网格 + aspect=1，让列数可手算：cols = round(sqrt(aspect·n·gapY/gapX))。
const GRID = { gapX: 100, gapY: 100, aspect: 1, marginX: 0, marginY: 0 }
const chain = (...ids: string[]) =>
  ids.slice(1).map((to, i) => ({ from: { node: ids[i] }, to: { node: to } }))

describe('computeSnakeLayout', () => {
  it('空图返回空 Map', () => {
    expect(computeSnakeLayout([], [], GRID).size).toBe(0)
  })

  it('线性链折成蛇形网格：奇数行反向，使「上一行末」与「下一行首」上下相邻', () => {
    // n=4, cols=round(sqrt(4))=2 → 两列两行
    const nodes = [{ id: 'a' }, { id: 'b' }, { id: 'c' }, { id: 'd' }]
    const layout = computeSnakeLayout(nodes, chain('a', 'b', 'c', 'd'), GRID)
    expect(layout.get('a')).toEqual([0, 0]) // 行0 左→右
    expect(layout.get('b')).toEqual([100, 0])
    expect(layout.get('c')).toEqual([100, 100]) // 行1 反向：起点在右，正落在 b 正下方
    expect(layout.get('d')).toEqual([0, 100])
    // 关键：连续节点 b→c 上下相邻（同 x），这正是蛇形相对普通网格的价值
    expect(layout.get('b')![0]).toBe(layout.get('c')![0])
  })

  it('按拓扑层深排序，压过节点在数组里的原始顺序', () => {
    // 给的顺序故意打乱成 [d,c,b,a]；真实依赖：a→b, a→c, b→d
    const nodes = [{ id: 'd' }, { id: 'c' }, { id: 'b' }, { id: 'a' }]
    const links = [
      { from: { node: 'a' }, to: { node: 'b' } },
      { from: { node: 'a' }, to: { node: 'c' } },
      { from: { node: 'b' }, to: { node: 'd' } },
    ]
    const layout = computeSnakeLayout(nodes, links, GRID)
    // 深度 a=0 < {b,c}=1 < d=2 → 根 a 必在原点，最深的 d 必在最后一行（i=3 → 行1）
    expect(layout.get('a')).toEqual([0, 0])
    expect(layout.get('d')![1]).toBe(100)
    // a 一定排在 b/c/d 之前（y 更小或同行更靠序列前）
    expect(layout.get('a')![1]).toBeLessThanOrEqual(layout.get('d')![1])
  })

  it('marginX/marginY 平移整张网格', () => {
    const nodes = [{ id: 'a' }, { id: 'b' }, { id: 'c' }, { id: 'd' }]
    const layout = computeSnakeLayout(nodes, chain('a', 'b', 'c', 'd'), { ...GRID, marginX: 10, marginY: 20 })
    expect(layout.get('a')).toEqual([10, 20])
    expect(layout.get('b')).toEqual([110, 20])
  })

  it('忽略悬空 / 自环连线，不抛错', () => {
    const nodes = [{ id: 'a' }, { id: 'b' }]
    const links = [
      { from: { node: 'a' }, to: { node: 'ghost' } }, // 指向不存在的节点
      { from: { node: 'a' }, to: { node: 'a' } }, // 自环
      null, // 脏数据
    ]
    const layout = computeSnakeLayout(nodes, links, GRID)
    expect(layout.size).toBe(2)
  })
})
