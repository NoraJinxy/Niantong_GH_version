import { describe, it, expect } from 'vitest'
import { computeFlowLayout } from './litegraphUtils'

// 用 100×100 的等距网格 + aspect=1，让「行数=令网格宽高比最接近画布」可手算（同分取更少行）。
const GRID = { gapX: 100, gapY: 100, aspect: 1, marginX: 0, marginY: 0 }
const chain = (...ids: string[]) =>
  ids.slice(1).map((to, i) => ({ from: { node: ids[i] }, to: { node: to } }))

describe('computeFlowLayout', () => {
  it('空图返回空 Map', () => {
    expect(computeFlowLayout([], [], GRID).size).toBe(0)
  })

  it('线性链居中折行：每行一律左→右（满行时居中即左对齐，不反向）', () => {
    // n=4, aspect=1 → rows=2（网格 2:2 宽高比 1 最贴画布）→ 两行各 2 个，满行无偏移
    const nodes = [{ id: 'a' }, { id: 'b' }, { id: 'c' }, { id: 'd' }]
    const layout = computeFlowLayout(nodes, chain('a', 'b', 'c', 'd'), GRID)
    expect(layout.get('a')).toEqual([0, 0]) // 行0 左→右
    expect(layout.get('b')).toEqual([100, 0])
    expect(layout.get('c')).toEqual([0, 100]) // 行1 从最左重新开始（非蛇形反向）
    expect(layout.get('d')).toEqual([100, 100])
    // 关键：同宽两行的第 0 列上下对齐（a 在 c 正上方），流向恒定向右
    expect(layout.get('a')![0]).toBe(layout.get('c')![0])
  })

  it('奇数节点均衡折行 + 窄行居中：n=7 → 3-2-2（非 3-3-1 孤儿），后两行居中偏移半列', () => {
    // n=7, aspect=1 → rows=3（网格 3:3 宽高比 1 最贴画布）→ 均分 3-2-2
    const ids = ['a', 'b', 'c', 'd', 'e', 'f', 'g']
    const layout = computeFlowLayout(ids.map((id) => ({ id })), chain(...ids), GRID)
    expect(layout.get('a')).toEqual([0, 0]) // 行0 满 3 列，左→右
    expect(layout.get('b')).toEqual([100, 0])
    expect(layout.get('c')).toEqual([200, 0])
    expect(layout.get('d')).toEqual([50, 100]) // 行1 两个、水平居中（偏移半列=50）
    expect(layout.get('e')).toEqual([150, 100])
    expect(layout.get('f')).toEqual([50, 200]) // 行2 同样居中
    expect(layout.get('g')).toEqual([150, 200])
  })

  it('窄行水平居中落在宽行正中：n=5 → 3-2，第二行居中', () => {
    // n=5, aspect=1 → rows=2（同分取更少行）→ 3-2
    const ids = ['a', 'b', 'c', 'd', 'e']
    const layout = computeFlowLayout(ids.map((id) => ({ id })), chain(...ids), GRID)
    expect(layout.get('a')).toEqual([0, 0])
    expect(layout.get('c')).toEqual([200, 0]) // 行0 满 3 列
    expect(layout.get('d')).toEqual([50, 100]) // 行1 两个、居中（偏移半列）
    expect(layout.get('e')).toEqual([150, 100])
  })

  it('按拓扑层深排序，压过节点在数组里的原始顺序', () => {
    // 给的顺序故意打乱成 [d,c,b,a]；真实依赖：a→b, a→c, b→d
    const nodes = [{ id: 'd' }, { id: 'c' }, { id: 'b' }, { id: 'a' }]
    const links = [
      { from: { node: 'a' }, to: { node: 'b' } },
      { from: { node: 'a' }, to: { node: 'c' } },
      { from: { node: 'b' }, to: { node: 'd' } },
    ]
    const layout = computeFlowLayout(nodes, links, GRID)
    // 深度 a=0 < {b,c}=1 < d=2 → 根 a 必在原点，最深的 d 必在最后一行（i=3 → 行1）
    expect(layout.get('a')).toEqual([0, 0])
    expect(layout.get('d')![1]).toBe(100)
    // a 一定排在 b/c/d 之前（y 更小或同行更靠序列前）
    expect(layout.get('a')![1]).toBeLessThanOrEqual(layout.get('d')![1])
  })

  it('marginX/marginY 平移整张网格', () => {
    const nodes = [{ id: 'a' }, { id: 'b' }, { id: 'c' }, { id: 'd' }]
    const layout = computeFlowLayout(nodes, chain('a', 'b', 'c', 'd'), { ...GRID, marginX: 10, marginY: 20 })
    expect(layout.get('a')).toEqual([10, 20])
    expect(layout.get('b')).toEqual([110, 20])
  })

  it('并行分支各成一块、互不交错：两条独立链 S1/S2 不被层深排序搅在一起', () => {
    // 两条独立链 a→b→c 与 x→y→z（无任何跨链连线）。旧逻辑按层深排序会得到 a,x,b,y,c,z 交错；
    // 新逻辑按连通分量分块：a/b/c 一块、x/y/z 一块，各自折行后上下堆叠，绝不交错。
    const ids1 = ['a', 'b', 'c']
    const ids2 = ['x', 'y', 'z']
    const nodes = [...ids1, ...ids2].map((id) => ({ id }))
    const links = [...chain(...ids1), ...chain(...ids2)]
    const layout = computeFlowLayout(nodes, links, GRID)
    // aspect=1、两块各 3 个 → cols=3：每块铺成一行（3 宽 × 共 2 行最贴方形画布）。
    // 块一（a/b/c）整体在块二（x/y/z）上方：块一最大 y < 块二最小 y，两块绝不交错。
    const block1MaxY = Math.max(layout.get('a')![1], layout.get('b')![1], layout.get('c')![1])
    const block2MinY = Math.min(layout.get('x')![1], layout.get('y')![1], layout.get('z')![1])
    expect(block1MaxY).toBeLessThan(block2MinY)
    // 块一三节点同一行、顺流向右 a<b<c
    expect(layout.get('a')![1]).toBe(layout.get('b')![1])
    expect(layout.get('b')![1]).toBe(layout.get('c')![1])
    expect(layout.get('a')![0]).toBeLessThan(layout.get('b')![0])
    expect(layout.get('b')![0]).toBeLessThan(layout.get('c')![0])
    // 块二三节点同一行、顺流向右 x<y<z
    expect(layout.get('x')![1]).toBe(layout.get('z')![1])
    expect(layout.get('x')![0]).toBeLessThan(layout.get('z')![0])
  })

  it('单连通图行为不变：仍是原「居中折行」（与分块前逐像素一致）', () => {
    // 回归护栏：上面 n=4/5/7 用例已逐像素锁住；这里再确认一条 6 节点链不受分块改动影响。
    const ids = ['a', 'b', 'c', 'd', 'e', 'f']
    const layout = computeFlowLayout(ids.map((id) => ({ id })), chain(...ids), GRID)
    // n=6, aspect=1 → cols=3 → 2 行 3-3
    expect(layout.get('a')).toEqual([0, 0])
    expect(layout.get('c')).toEqual([200, 0])
    expect(layout.get('d')).toEqual([0, 100])
    expect(layout.get('f')).toEqual([200, 100])
  })

  it('忽略悬空 / 自环连线，不抛错', () => {
    const nodes = [{ id: 'a' }, { id: 'b' }]
    const links = [
      { from: { node: 'a' }, to: { node: 'ghost' } }, // 指向不存在的节点
      { from: { node: 'a' }, to: { node: 'a' } }, // 自环
      null, // 脏数据
    ]
    const layout = computeFlowLayout(nodes, links, GRID)
    expect(layout.size).toBe(2)
  })
})
