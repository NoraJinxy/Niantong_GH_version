// 通用三级取数：内存 LRU → IndexedDB（跨会话持久）→ 网络（二进制优先 / JSON 回退）。命中即回填更近层。
// 把时域页 plotCache 与审核页手搓的那套统一成一个工厂——各页只提供 namespace / keyOf / endpoint / decode。
// 决策见 日志/10_观察作图与缓存架构260614 + 二进制/缓存推广方案（2026-06）。
//
// 正确性约定（调用方负责）：keyOf 必须含「内容身份指纹」——观察页用 outputId（node_hash 内容寻址、产物不变键不变，
// 可跨会话命中）；执行中数据用 executionId 版本化防陈旧。键里参数变了就该是新键，别把不同结果合并到一个键。
import { dataApi } from '@/api/client'
import { idbGet, idbSet } from './idbCache'

export type TieredSource = 'memory' | 'indexeddb' | 'network'

export interface TieredFetchOptions<T> {
  /** 进键前缀，区分不同数据/页面，避免跨页串台（'psd' | 'tfr_cube' | 'ica_detail' | ...）。 */
  namespace: string
  /** 版本指纹键（不含 namespace，本工厂自动加前缀）。务必含 outputId/executionId 等不可变身份。 */
  keyOf: (params: Record<string, unknown>) => string
  /** 取数 URL。 */
  endpoint: (params: Record<string, unknown>) => string
  /** 给了则二进制优先（请求带 format=binary、responseType arraybuffer）；失败回退 JSON。不给则只走 JSON。 */
  decodeBinary?: (buf: ArrayBuffer) => T
  /** JSON 响应 → T（默认按 T 原样返回）。 */
  fromJson?: (data: unknown) => T
  /** 内存 LRU 上限（条）。 */
  memMax?: number
}

export function useTieredFetch<T>(opts: TieredFetchOptions<T>) {
  const mem = new Map<string, T>()
  const memMax = opts.memMax ?? 32

  function memSet(key: string, v: T) {
    if (mem.has(key)) mem.delete(key)
    mem.set(key, v)
    while (mem.size > memMax) {
      const k = mem.keys().next().value
      if (k === undefined) break
      mem.delete(k)
    }
  }

  async function fetchNetwork(params: Record<string, unknown>): Promise<T> {
    const url = opts.endpoint(params)
    if (opts.decodeBinary) {
      try {
        const res = await dataApi.get(url, { params: { ...params, format: 'binary' }, responseType: 'arraybuffer' })
        const buf = res.data as ArrayBuffer
        if (!buf || buf.byteLength < 12) throw new Error('empty binary')
        return opts.decodeBinary(buf)
      } catch {
        /* 二进制不可用/解码失败 → 回退 JSON */
      }
    }
    const res = await dataApi.get(url, { params })
    return opts.fromJson ? opts.fromJson(res.data) : (res.data as T)
  }

  /** 三级取数；返回数据 + 命中层级（供调试统计）。 */
  async function fetch(params: Record<string, unknown>): Promise<{ data: T; source: TieredSource }> {
    const key = `${opts.namespace}::${opts.keyOf(params)}`
    const hit = mem.get(key)
    if (hit !== undefined) {
      mem.delete(key)
      mem.set(key, hit) // LRU 触达
      return { data: hit, source: 'memory' }
    }
    const idb = await idbGet<T>(key)
    if (idb) {
      memSet(key, idb)
      return { data: idb, source: 'indexeddb' }
    }
    const data = await fetchNetwork(params)
    memSet(key, data)
    void idbSet(key, data) // best-effort 回填，失败静默
    return { data, source: 'network' }
  }

  /** 清空内存层（如数据集切换时）。IndexedDB 持久层不动（靠 LRU 自然淘汰）。 */
  function clearMemory() {
    mem.clear()
  }

  return { fetch, clearMemory }
}
