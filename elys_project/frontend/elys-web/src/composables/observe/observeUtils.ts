// 观察作图三页（时域 / 频域 / 时频域）共用的小工具：查询参数读取 + 数值格式化。
// 从 WaveformDetailPage / PsdPage / TfrPage 三处逐字重复的内联定义收口到此，作单一来源。
import { useRoute } from 'vue-router'

/**
 * URL 查询字符串读取器：数组取首个、缺省回退。
 * 因依赖 useRoute()，做成 composable —— 在 setup 内 `const qstr = useQueryString()` 后照常调用。
 */
export function useQueryString() {
  const route = useRoute()
  return (key: string, fallback = ''): string => {
    const raw = route.query[key]
    if (Array.isArray(raw)) return raw[0] ?? fallback
    return raw ?? fallback
  }
}

/** 四舍五入到 p 位小数。 */
export function round(n: number, p: number): number {
  const f = Math.pow(10, p)
  return Math.round(n * f) / f
}

/** 输入框取数：空 / 非法 → null，否则有限数。 */
export function toNum(v: number | string): number | null {
  if (v === '' || v === null || v === undefined) return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

/** ID 缩略：超 10 字符截前 8 + 省略号。 */
export function shortId(value?: string | null): string {
  if (!value) return ''
  return value.length > 10 ? value.slice(0, 8) + '…' : value
}

/** 整数夹取到 [lo, hi]。 */
export function clampInt(v: number, lo: number, hi: number): number {
  return v < lo ? lo : v > hi ? hi : v
}
