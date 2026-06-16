import { describe, it, expect } from 'vitest'
import {
  withAlpha,
  normalizedJobStatus,
  formatJobStatus,
  formatFileSize,
  formatDurationMs,
  formatSecondsMetric,
  formatMetricNumber,
  numericMetric,
  shortId,
  stepVisualState,
  isStepDone,
  portTypesCompatible,
  isWildcardPortType,
  liteGraphPortType,
  categoryKey,
  compactNodeTitle,
  formatExecutionMode,
  formatArtifactRetention,
  formatDataType,
  formatPipelineStatus,
} from './pipelineFormatters'

describe('withAlpha', () => {
  it('converts 6-digit hex to rgba', () => {
    expect(withAlpha('#FF8040', 0.5)).toBe('rgba(255, 128, 64, 0.5)')
  })
  it('clamps alpha into [0,1]', () => {
    expect(withAlpha('#000000', 2)).toBe('rgba(0, 0, 0, 1)')
    expect(withAlpha('#000000', -1)).toBe('rgba(0, 0, 0, 0)')
  })
  it('returns input unchanged for non 6-digit hex', () => {
    expect(withAlpha('#abc', 0.5)).toBe('#abc')
  })
})

describe('normalizedJobStatus', () => {
  it('maps completed to success and lowercases', () => {
    expect(normalizedJobStatus('Completed')).toBe('success')
    expect(normalizedJobStatus('RUNNING')).toBe('running')
  })
  it('defaults empty/null to pending', () => {
    expect(normalizedJobStatus('')).toBe('pending')
    expect(normalizedJobStatus(null)).toBe('pending')
  })
})

describe('formatJobStatus', () => {
  it('formats known statuses in Chinese', () => {
    expect(formatJobStatus('completed')).toBe('成功')
    expect(formatJobStatus('queued')).toBe('排队')
    expect(formatJobStatus('running')).toBe('运行中')
  })
  it('returns original for unknown', () => {
    expect(formatJobStatus('weird')).toBe('weird')
  })
})

describe('formatFileSize', () => {
  it('formats B/KB/MB', () => {
    expect(formatFileSize(512)).toBe('512 B')
    expect(formatFileSize(1536)).toBe('1.5 KB')
    expect(formatFileSize(2 * 1024 * 1024)).toBe('2.0 MB')
  })
  it('handles null', () => {
    expect(formatFileSize(null)).toBe('-')
  })
})

describe('formatDurationMs', () => {
  it('formats ms and s', () => {
    expect(formatDurationMs(500)).toBe('500ms')
    expect(formatDurationMs(1500)).toBe('1.5s')
    expect(formatDurationMs(15000)).toBe('15s')
  })
  it('handles null with em dash', () => {
    expect(formatDurationMs(null)).toBe('—')
  })
})

describe('numericMetric & formatSecondsMetric', () => {
  it('parses numeric strings', () => {
    expect(numericMetric('3.5')).toBe(3.5)
    expect(numericMetric('abc')).toBe(null)
  })
  it('formats seconds vs minutes', () => {
    expect(formatSecondsMetric(30)).toBe('30.00s')
    expect(formatSecondsMetric(90)).toBe('1.50min')
    expect(formatSecondsMetric('abc')).toBe('-')
  })
})

describe('formatMetricNumber', () => {
  it('uses 1 digit for >=10, appends suffix', () => {
    expect(formatMetricNumber(12.34)).toBe('12.3')
    expect(formatMetricNumber(7, ' Hz')).toBe('7 Hz')
  })
  it('handles non-numeric', () => {
    expect(formatMetricNumber('abc')).toBe('-')
  })
})

describe('shortId', () => {
  it('truncates to 8 chars', () => {
    expect(shortId('1234567890')).toBe('12345678')
    expect(shortId('abc')).toBe('abc')
    expect(shortId(null)).toBe('')
  })
})

describe('stepVisualState & isStepDone', () => {
  it('maps statuses to visual states', () => {
    expect(stepVisualState('completed')).toBe('done')
    expect(stepVisualState('running')).toBe('doing')
    expect(stepVisualState('failed')).toBe('failed')
    expect(stepVisualState('skipped')).toBe('skipped')
    expect(stepVisualState('pending')).toBe('pending')
  })
  it('isStepDone true for done/skipped', () => {
    expect(isStepDone('completed')).toBe(true)
    expect(isStepDone('skipped')).toBe(true)
    expect(isStepDone('running')).toBe(false)
  })
})

describe('port type helpers', () => {
  it('isWildcardPortType', () => {
    expect(isWildcardPortType('*')).toBe(true)
    expect(isWildcardPortType('any')).toBe(true)
    expect(isWildcardPortType('')).toBe(true)
    expect(isWildcardPortType(undefined)).toBe(true)
    expect(isWildcardPortType('eeg_data')).toBe(false)
  })
  it('liteGraphPortType maps wildcard to empty string', () => {
    expect(liteGraphPortType('*')).toBe('')
    expect(liteGraphPortType(undefined)).toBe('')
    expect(liteGraphPortType('epochs')).toBe('epochs')
  })
  it('portTypesCompatible', () => {
    expect(portTypesCompatible('eeg_data', 'eeg_data')).toBe(true)
    expect(portTypesCompatible('*', 'whatever')).toBe(true)
    expect(portTypesCompatible('raw', 'eeg_data')).toBe(true)
    expect(portTypesCompatible('foo', 'bar')).toBe(false)
  })
})

describe('categoryKey', () => {
  it('maps category text to canonical key', () => {
    expect(categoryKey('Preprocess/Filter')).toBe('preprocess')
    expect(categoryKey('ICA')).toBe('ica')
    expect(categoryKey('data load')).toBe('data')
    expect(categoryKey('')).toBe('')
  })
})

describe('compactNodeTitle', () => {
  it('keeps short titles (trimmed)', () => {
    expect(compactNodeTitle('  erp  ')).toBe('erp')
  })
  it('truncates long titles with ellipsis', () => {
    const long = 'x'.repeat(100)
    const out = compactNodeTitle(long)
    expect(out.endsWith('…')).toBe(true)
    expect(out.length).toBeLessThan(long.length)
  })
})

describe('mode / retention / pipeline status', () => {
  it('formatExecutionMode', () => {
    expect(formatExecutionMode('trial')).toBe('试跑')
    expect(formatExecutionMode('analysis')).toBe('正式分析')
    expect(formatExecutionMode(null)).toBe('-')
  })
  it('formatArtifactRetention precedence (deleted > keep > 不保存)', () => {
    expect(formatArtifactRetention({ deleted_at: 'x', keep: true })).toBe('已删除')
    expect(formatArtifactRetention({ keep: true })).toBe('保存')
    expect(formatArtifactRetention({ cache_eligible: true })).toBe('不保存')
    expect(formatArtifactRetention({})).toBe('不保存')
    expect(formatArtifactRetention(null)).toBe('未标记')
  })
  it('formatDataType maps enums to friendly labels, falls back to raw', () => {
    expect(formatDataType('evoked')).toBe('ERP 波形')
    expect(formatDataType('tfr')).toBe('时频图')
    expect(formatDataType('psd')).toBe('功率谱')
    expect(formatDataType('weird_unknown')).toBe('weird_unknown')
    expect(formatDataType(null)).toBe('结果')
  })
  it('formatPipelineStatus defaults empty to draft', () => {
    expect(formatPipelineStatus('active')).toBe('可运行')
    expect(formatPipelineStatus('draft')).toBe('草稿')
    expect(formatPipelineStatus('')).toBe('草稿')
  })
})
