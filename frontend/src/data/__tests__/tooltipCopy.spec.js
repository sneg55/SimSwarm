import { describe, it, expect } from 'vitest'
import { tooltipCopy, normalizeKey, getTooltip } from '../tooltipCopy.js'

describe('tooltipCopy', () => {
  it('exports a non-empty dictionary', () => {
    expect(Object.keys(tooltipCopy).length).toBeGreaterThan(30)
  })

  it('every entry has title, meaning, and calculation strings', () => {
    for (const [key, entry] of Object.entries(tooltipCopy)) {
      expect(entry.title, `${key} missing title`).toBeTruthy()
      expect(typeof entry.title).toBe('string')
      expect(entry.meaning, `${key} missing meaning`).toBeTruthy()
      expect(typeof entry.meaning).toBe('string')
      expect(entry.calculation, `${key} missing calculation`).toBeTruthy()
      expect(typeof entry.calculation).toBe('string')
    }
  })
})

describe('normalizeKey', () => {
  it('converts space-separated words to camelCase', () => {
    expect(normalizeKey('Agents Active')).toBe('agentsActive')
  })

  it('handles single word', () => {
    expect(normalizeKey('Consensus')).toBe('consensus')
  })

  it('handles single-word lowercase input', () => {
    expect(normalizeKey('agentsactive')).toBe('agentsactive')
  })

  it('handles mixed case with multiple spaces', () => {
    expect(normalizeKey('Total Market Volume')).toBe('totalMarketVolume')
  })

  it('returns empty string for empty input', () => {
    expect(normalizeKey('')).toBe('')
    expect(normalizeKey('   ')).toBe('')
  })

  it('lowercases ALL CAPS words correctly', () => {
    expect(normalizeKey('YES NO')).toBe('yesNo')
  })
})

describe('getTooltip', () => {
  it('returns entry for known key', () => {
    const entry = getTooltip('coalitionCard.strength')
    expect(entry).toBeTruthy()
    expect(entry.title).toBe('Coalition Strength')
  })

  it('returns null for unknown key', () => {
    expect(getTooltip('nonexistent.key')).toBeNull()
  })
})
