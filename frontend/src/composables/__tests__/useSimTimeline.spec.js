import { describe, it, expect } from 'vitest'
import { useSimTimeline } from '../useSimTimeline'

const START = '2026-01-01T00:00:00Z'

describe('useSimTimeline — date mapping', () => {
  it('spaces rounds evenly across the horizon', () => {
    const t = useSimTimeline({
      startedAt: START,
      forecastDays: 30,
      roundCount: 4,
      structured: {},
      marketCurves: [],
      topPosts: [],
      agentTrajectories: [],
    })
    expect(t.roundDates).toHaveLength(4)
    expect(t.roundDates[0].toISOString()).toBe('2026-01-01T00:00:00.000Z')
    expect(t.roundDates[3].toISOString()).toBe('2026-01-31T00:00:00.000Z')
    const deltaMs = t.roundDates[1] - t.roundDates[0]
    expect(deltaMs).toBe((30 * 86400 * 1000) / 3)
  })

  it('handles a single-round sim by pinning to the start', () => {
    const t = useSimTimeline({
      startedAt: START, forecastDays: 30, roundCount: 1,
      structured: {}, marketCurves: [], topPosts: [], agentTrajectories: [],
    })
    expect(t.roundDates).toHaveLength(1)
    expect(t.roundDates[0].toISOString()).toBe('2026-01-01T00:00:00.000Z')
  })

  it('returns an empty timeline when inputs are missing', () => {
    const t = useSimTimeline({
      startedAt: null, forecastDays: null, roundCount: 0,
      structured: null, marketCurves: null, topPosts: null, agentTrajectories: null,
    })
    expect(t.roundDates).toEqual([])
    expect(t.moments).toEqual([])
    expect(t.start).toBeNull()
    expect(t.end).toBeNull()
  })
})
