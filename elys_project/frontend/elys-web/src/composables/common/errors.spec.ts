import { describe, it, expect } from 'vitest'
import { friendlyError } from './errors'

describe('friendlyError', () => {
  it('prefixes string detail with the fallback', () => {
    expect(friendlyError({ response: { data: { detail: 'boom' } } }, '审核提交失败')).toBe(
      '审核提交失败：boom',
    )
  })
  it('takes the first msg of a validation-error array', () => {
    expect(
      friendlyError({ response: { data: { detail: [{ msg: 'a' }, { msg: 'b' }] } } }, 'fb'),
    ).toBe('fb：a')
  })
  it('handles a string-array detail', () => {
    expect(friendlyError({ response: { data: { detail: ['x'] } } }, 'fb')).toBe('fb：x')
  })
  it('falls back to Error.message when no detail', () => {
    expect(friendlyError(new Error('net'), 'fb')).toBe('net')
  })
  it('uses fallback when nothing else is available', () => {
    expect(friendlyError({}, 'fb')).toBe('fb')
    expect(friendlyError({ response: { data: { detail: '' } } }, 'fb')).toBe('fb')
  })
})
