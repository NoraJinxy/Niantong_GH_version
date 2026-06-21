// 时域绘图数据的三级缓存：内存 Map → IndexedDB → 网络（二进制优先，失败回退 JSON）。
// 决策见 日志/10_观察作图与缓存架构260614/01 §3、06 §5。模块级单例，命中统计供 CacheDebugOverlay 显示。
import { reactive } from 'vue'
import { dataApi } from '@/api/client'
import type { StudyOutputTimeseries } from '@/types'
import { idbGet, idbSet } from './idbCache'

export type PlotSource = 'memory' | 'indexeddb' | 'network'
export interface FetchParams {
  index?: number
  tmin?: number | null
  tmax?: number | null
  maxPoints: number
  maxChannels: number
  // view-only 瞬时滤波（不存储、不影响 pipeline）
  lFreq?: number | null
  hFreq?: number | null
  notch?: number | null
}

export const cacheStats = reactive({
  memory: 0,
  indexeddb: 0,
  network: 0,
  entries: 0,
  bytes: 0,
  lastSource: '' as PlotSource | '',
})

const MEM_MAX = 64
const mem = new Map<string, StudyOutputTimeseries>()

function keyOf(studyId: string, dd: string, p: FetchParams): string {
  return [studyId, dd, p.index ?? 0, p.tmin ?? '', p.tmax ?? '', p.maxPoints, p.maxChannels, p.lFreq ?? '', p.hFreq ?? '', p.notch ?? ''].join('::')
}

function memSet(key: string, v: StudyOutputTimeseries) {
  if (mem.has(key)) mem.delete(key)
  mem.set(key, v)
  while (mem.size > MEM_MAX) {
    const k = mem.keys().next().value
    if (k === undefined) break
    mem.delete(k)
  }
  cacheStats.entries = mem.size
}

// 二进制解码：b"EEGBIN01" + u32(metaLen,LE) + meta(JSON utf8) + f64 times[n] + f32 data[n_ch*n_times]（µV，C-order）
export function decodeBinary(buf: ArrayBuffer): StudyOutputTimeseries {
  const dv = new DataView(buf)
  const metaLen = dv.getUint32(8, true)
  const metaStart = 12
  const meta = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, metaStart, metaLen)))
  const nTimes = Number(meta.n_times) || 0
  const chNames: string[] = Array.isArray(meta.ch_names) ? meta.ch_names : []
  const timesStart = metaStart + metaLen
  const times = new Float64Array(buf.slice(timesStart, timesStart + nTimes * 8))
  const data = new Float32Array(buf.slice(timesStart + nTimes * 8))
  const channels = chNames.map((name, i) => ({
    name,
    values: Array.from(data.subarray(i * nTimes, (i + 1) * nTimes)),
  }))
  return { ...meta, times: Array.from(times), channels } as StudyOutputTimeseries
}

async function fetchNetwork(studyId: string, dd: string, p: FetchParams): Promise<StudyOutputTimeseries> {
  const url = `/studies/${studyId}/outputs/${dd}/timeseries`
  const params: Record<string, unknown> = {
    index: p.index,
    tmin: p.tmin ?? undefined,
    tmax: p.tmax ?? undefined,
    max_points: p.maxPoints,
    max_channels: p.maxChannels,
    l_freq: p.lFreq ?? undefined,
    h_freq: p.hFreq ?? undefined,
    notch: p.notch ?? undefined,
  }
  // 先试二进制端点；任何问题（未部署/解码失败）回退 JSON，保证可用。两路都带滤波参数。
  try {
    const res = await dataApi.get(url, { params: { ...params, format: 'binary' }, responseType: 'arraybuffer' })
    const buf = res.data as ArrayBuffer
    if (!buf || buf.byteLength < 12) throw new Error('empty binary')
    const magic = new TextDecoder().decode(new Uint8Array(buf, 0, 8))
    if (magic !== 'EEGBIN01') throw new Error('bad magic')
    cacheStats.bytes += buf.byteLength
    return decodeBinary(buf)
  } catch {
    const res = await dataApi.get(url, { params })
    return res.data as StudyOutputTimeseries
  }
}

/** 三级取数：内存 → IndexedDB → 网络（命中即回填更近层）。 */
export async function fetchTimeseries(
  studyId: string,
  dd: string,
  p: FetchParams,
): Promise<{ ts: StudyOutputTimeseries; source: PlotSource }> {
  const key = keyOf(studyId, dd, p)

  const hit = mem.get(key)
  if (hit) {
    mem.delete(key)
    mem.set(key, hit)
    cacheStats.memory++
    cacheStats.lastSource = 'memory'
    return { ts: hit, source: 'memory' }
  }

  const idb = await idbGet<StudyOutputTimeseries>(key)
  if (idb) {
    memSet(key, idb)
    cacheStats.indexeddb++
    cacheStats.lastSource = 'indexeddb'
    return { ts: idb, source: 'indexeddb' }
  }

  const ts = await fetchNetwork(studyId, dd, p)
  memSet(key, ts)
  void idbSet(key, ts)
  cacheStats.network++
  cacheStats.lastSource = 'network'
  return { ts, source: 'network' }
}
