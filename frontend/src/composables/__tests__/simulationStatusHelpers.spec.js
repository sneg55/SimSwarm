import { describe, it, expect } from 'vitest'
import {
  STAGE_NAMES,
  STAGE_STEP_IDS,
  TIER_ESTIMATES,
  formatSeconds,
  formatDate,
} from '../simulationStatusHelpers.js'

describe('simulationStatusHelpers — constants', () => {
  it('STAGE_NAMES has 5 entries', () => {
    expect(STAGE_NAMES).toHaveLength(5)
    expect(STAGE_NAMES[0]).toBe('Seeding')
    expect(STAGE_NAMES[4]).toBe('Generating report')
  })

  it('STAGE_STEP_IDS has 5 entries matching the stages', () => {
    expect(STAGE_STEP_IDS).toHaveLength(5)
    expect(STAGE_STEP_IDS[0]).toBe('seed')
    expect(STAGE_STEP_IDS[2]).toBe('simulate')
    expect(STAGE_STEP_IDS[4]).toBe('report')
  })

  it('TIER_ESTIMATES has small/medium/large each with 5 values', () => {
    expect(Object.keys(TIER_ESTIMATES)).toEqual(['small', 'medium', 'large'])
    for (const tier of ['small', 'medium', 'large']) {
      expect(TIER_ESTIMATES[tier]).toHaveLength(5)
      expect(TIER_ESTIMATES[tier].every(v => typeof v === 'number' && v > 0)).toBe(true)
    }
  })

  it('TIER_ESTIMATES small total is less than medium total', () => {
    const sumSmall = TIER_ESTIMATES.small.reduce((a, b) => a + b, 0)
    const sumMedium = TIER_ESTIMATES.medium.reduce((a, b) => a + b, 0)
    expect(sumSmall).toBeLessThan(sumMedium)
  })
})

describe('formatSeconds', () => {
  it('returns seconds-only string for < 60s', () => {
    expect(formatSeconds(0)).toBe('0s')
    expect(formatSeconds(45)).toBe('45s')
    expect(formatSeconds(59)).toBe('59s')
  })

  it('returns minutes+seconds string for 60–3599s', () => {
    expect(formatSeconds(60)).toBe('1m 0s')
    expect(formatSeconds(90)).toBe('1m 30s')
    expect(formatSeconds(3599)).toBe('59m 59s')
  })

  it('returns hours+minutes string for ≥ 3600s', () => {
    expect(formatSeconds(3600)).toBe('1h 0m')
    expect(formatSeconds(3660)).toBe('1h 1m')
    expect(formatSeconds(7322)).toBe('2h 2m')
  })
})

describe('formatDate', () => {
  it('returns empty string for falsy input', () => {
    expect(formatDate(null)).toBe('')
    expect(formatDate(undefined)).toBe('')
    expect(formatDate('')).toBe('')
  })

  it('returns a non-empty locale string for a valid ISO date', () => {
    const result = formatDate('2026-01-15T10:30:00Z')
    expect(typeof result).toBe('string')
    expect(result.length).toBeGreaterThan(0)
    // Should include the year
    expect(result).toContain('2026')
  })

  it('handles date-only strings without throwing', () => {
    const result = formatDate('2025-06-01')
    expect(typeof result).toBe('string')
    expect(result.length).toBeGreaterThan(0)
  })
})
