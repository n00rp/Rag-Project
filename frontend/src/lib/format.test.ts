import { describe, expect, it } from 'vitest'
import { formatBytes, formatTimestamp, pluralize } from './format'

describe('formatBytes', () => {
  it('scales units and uses a decimal comma', () => {
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(2048)).toBe('2 kB')
    expect(formatBytes(1.5 * 1024 * 1024)).toBe('1,5 MB')
  })
})

describe('pluralize', () => {
  it('picks singular only for exactly one', () => {
    expect(pluralize(1, 'sida', 'sidor')).toBe('1 sida')
    expect(pluralize(0, 'sida', 'sidor')).toBe('0 sidor')
    expect(pluralize(12, 'sida', 'sidor')).toBe('12 sidor')
  })
})

describe('formatTimestamp', () => {
  it('shows the time for today and the date for older messages', () => {
    const now = new Date('2026-10-12T15:00:00')
    expect(formatTimestamp('2026-10-12T09:05:00', now)).toMatch(/09[:.]05/)
    expect(formatTimestamp('2026-10-01T09:05:00', now)).toMatch(/1/)
    expect(formatTimestamp('2026-10-01T09:05:00', now)).not.toMatch(/09[:.]05/)
  })
})
