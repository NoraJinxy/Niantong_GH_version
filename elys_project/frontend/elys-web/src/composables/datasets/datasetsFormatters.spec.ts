import { describe, it, expect } from 'vitest'
import {
  queryString,
  sanitizeCode,
  getDateValue,
  formatDate,
  formatDuration,
  formatRelative,
  formatFileSize,
  formatVersionLabel,
  getVisibilityClass,
  getVisibilityLabel,
  formatSourceFormat,
  formatChannelEvent,
  qaStatusLabel,
  isQaPassed,
  getQaStatusLabel,
  getQaStatusClass,
  getErrorMessage,
  lifecycleErrorMessage,
  countFilesByRole,
  fileBucketOf,
  sumFileSize,
  normalizeFilePath,
  getFileShortPath,
  getFileRoleGroup,
  matchesFileRoleFilter,
} from './datasetsFormatters'

describe('queryString', () => {
  it('returns string as-is, first of array, else empty', () => {
    expect(queryString('foo')).toBe('foo')
    expect(queryString(['a', 'b'])).toBe('a')
    expect(queryString(123)).toBe('')
    expect(queryString([])).toBe('')
  })
})

describe('sanitizeCode', () => {
  it('trims, spaces->dash, strips illegal, collapses dashes, trims edges', () => {
    expect(sanitizeCode('  Hello World  ')).toBe('Hello-World')
    expect(sanitizeCode('a@@b##c')).toBe('abc')
    expect(sanitizeCode('--a--b--')).toBe('a-b')
    expect(sanitizeCode('foo_bar')).toBe('foo_bar')
  })
})

describe('getDateValue', () => {
  it('parses to epoch ms, 0 for null/invalid', () => {
    expect(getDateValue(null)).toBe(0)
    expect(getDateValue('garbage')).toBe(0)
    expect(getDateValue('2026-06-12T00:00:00Z')).toBeGreaterThan(0)
  })
})

describe('formatDate / formatRelative edge cases', () => {
  it('formatDate handles null and invalid', () => {
    expect(formatDate(null)).toBe('未记录')
    expect(formatDate('garbage')).toBe('garbage')
  })
  it('formatRelative handles null and invalid', () => {
    expect(formatRelative(null)).toBe('尚未导入')
    expect(formatRelative('garbage')).toBe('garbage')
  })
})

describe('formatDuration', () => {
  it('formats seconds / minutes / hours / days', () => {
    expect(formatDuration(0)).toBe('0 分')
    expect(formatDuration(-5)).toBe('0 分')
    expect(formatDuration(30)).toBe('30 秒')
    expect(formatDuration(90)).toBe('1 分')
    expect(formatDuration(3600)).toBe('1 时')
    expect(formatDuration(3660)).toBe('1 时 1 分')
    expect(formatDuration(90000)).toBe('1 天 1 时')
  })
})

describe('formatFileSize', () => {
  it('scales B/KB/MB with adaptive decimals', () => {
    expect(formatFileSize(0)).toBe('0 B')
    expect(formatFileSize(512)).toBe('512 B')
    expect(formatFileSize(1024)).toBe('1.0 KB')
    expect(formatFileSize(1536)).toBe('1.5 KB')
    expect(formatFileSize(15 * 1024)).toBe('15 KB')
    expect(formatFileSize(1024 * 1024)).toBe('1.0 MB')
  })
})

describe('version / visibility labels', () => {
  it('formatVersionLabel maps working to 工作版本', () => {
    expect(formatVersionLabel(null)).toBe('工作版本')
    expect(formatVersionLabel('working')).toBe('工作版本')
    expect(formatVersionLabel('1.0.0')).toBe('1.0.0')
  })
  it('visibility class & label', () => {
    expect(getVisibilityClass('public')).toBe('badge--success')
    expect(getVisibilityClass('shared')).toBe('badge--primary')
    expect(getVisibilityClass('private')).toBe('badge--outline')
    expect(getVisibilityLabel('private')).toBe('私有')
    expect(getVisibilityLabel('unknown')).toBe('unknown')
  })
})

describe('recording display helpers', () => {
  it('formatSourceFormat', () => {
    expect(formatSourceFormat(null)).toBe('未知')
    expect(formatSourceFormat('brainvision')).toBe('BrainVision')
    expect(formatSourceFormat('edf')).toBe('EDF')
  })
  it('formatChannelEvent', () => {
    expect(formatChannelEvent(64, 876)).toBe('64 ch / 876 evt')
    expect(formatChannelEvent(null, null)).toBe('- / -')
  })
})

describe('QA status helpers', () => {
  it('qaStatusLabel', () => {
    expect(qaStatusLabel('pass')).toBe('已通过')
    expect(qaStatusLabel('fail')).toBe('未通过')
    expect(qaStatusLabel(null)).toBe('未运行')
  })
  it('isQaPassed (case-insensitive, multiple aliases)', () => {
    expect(isQaPassed('pass')).toBe(true)
    expect(isQaPassed('PASSED')).toBe(true)
    expect(isQaPassed('approved')).toBe(true)
    expect(isQaPassed('fail')).toBe(false)
    expect(isQaPassed(null)).toBe(false)
  })
  it('getQaStatusLabel', () => {
    expect(getQaStatusLabel('pass')).toBe('通过')
    expect(getQaStatusLabel('failed')).toBe('未通过')
    expect(getQaStatusLabel('warning')).toBe('需复核')
    expect(getQaStatusLabel(null)).toBe('未质控')
    expect(getQaStatusLabel('xyz')).toBe('xyz')
  })
  it('getQaStatusClass', () => {
    expect(getQaStatusClass('pass')).toBe('badge--success')
    expect(getQaStatusClass('failed')).toBe('badge--danger')
    expect(getQaStatusClass('warning')).toBe('badge--warning')
    expect(getQaStatusClass('pending')).toBe('badge--outline')
  })
})

describe('error message extraction', () => {
  it('getErrorMessage handles detail variants', () => {
    expect(getErrorMessage({ response: { data: { detail: 'boom' } } })).toBe('boom')
    expect(getErrorMessage({ response: { data: { detail: [{ msg: 'a' }, { msg: 'b' }] } } })).toBe('a，b')
    expect(getErrorMessage({ response: { status: 500 } })).toBe('准备失败 (HTTP 500)')
    expect(getErrorMessage({ message: 'net' })).toBe('准备失败：net')
    expect(getErrorMessage({})).toBe('准备失败')
  })
  it('lifecycleErrorMessage falls back to message then fallback', () => {
    expect(lifecycleErrorMessage({ response: { data: { detail: 'x' } } }, 'fb')).toBe('x')
    expect(lifecycleErrorMessage(new Error('e'), 'fb')).toBe('e')
    expect(lifecycleErrorMessage({}, 'fb')).toBe('fb')
  })
})

describe('file role / path / bucket', () => {
  it('countFilesByRole counts matching keywords', () => {
    const files = [{ file_role: 'original_upload' }, { file_role: 'canonical_fif' }, { file_role: 'sidecar' }] as any
    expect(countFilesByRole(files, ['original'])).toBe(1)
    expect(countFilesByRole(files, ['fif', 'sidecar'])).toBe(2)
  })
  it('fileBucketOf classifies into upload/fif/tech', () => {
    expect(fileBucketOf({ file_role: 'original_upload' } as any)).toBe('upload')
    expect(fileBucketOf({ file_role: 'canonical_fif' } as any)).toBe('fif')
    expect(fileBucketOf({ file_role: 'sidecar' } as any)).toBe('tech')
  })
  it('sumFileSize tolerates missing sizes', () => {
    expect(sumFileSize([{ file_size: 100 }, { file_size: 200 }, { file_size: null }] as any)).toBe(300)
  })
  it('normalizeFilePath converts backslashes', () => {
    expect(normalizeFilePath('a\\b\\c')).toBe('a/b/c')
  })
  it('getFileShortPath keeps last 3 segments', () => {
    expect(getFileShortPath({ logical_path: 'a/b/c/d/e' } as any)).toBe('c/d/e')
    expect(getFileShortPath({ logical_path: 'a/b' } as any)).toBe('a/b')
  })
  it('getFileRoleGroup & matchesFileRoleFilter', () => {
    expect(getFileRoleGroup({ file_role: 'original' } as any)).toBe('original')
    expect(getFileRoleGroup({ file_role: 'raw_bids' } as any)).toBe('raw-bids')
    expect(getFileRoleGroup({ file_role: 'canonical_fif' } as any)).toBe('canonical-fif')
    expect(getFileRoleGroup({ file_role: 'sidecar' } as any)).toBe('other')
    expect(matchesFileRoleFilter({ file_role: 'original' } as any, 'all')).toBe(true)
    expect(matchesFileRoleFilter({ file_role: 'original' } as any, 'original')).toBe(true)
    expect(matchesFileRoleFilter({ file_role: 'original' } as any, 'raw-bids')).toBe(false)
  })
})
