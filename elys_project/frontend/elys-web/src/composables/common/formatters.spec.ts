import { describe, it, expect } from 'vitest'
import { formatDateTime } from './formatters'

describe('formatDateTime', () => {
  it('returns 暂无 for null/undefined/empty', () => {
    expect(formatDateTime(null)).toBe('暂无')
    expect(formatDateTime(undefined)).toBe('暂无')
    expect(formatDateTime('')).toBe('暂无')
  })
  it('returns the raw string when unparseable', () => {
    expect(formatDateTime('garbage')).toBe('garbage')
  })
  it('formats a valid ISO timestamp with zh-CN year/month/day/hour/minute', () => {
    const out = formatDateTime('2026-06-12T08:30:00Z')
    // 不锁具体时区下的字面值，只校验是否被格式化（含数字 + 分隔符，非原样）
    expect(out).not.toBe('2026-06-12T08:30:00Z')
    expect(out).toMatch(/2026/)
  })
})
