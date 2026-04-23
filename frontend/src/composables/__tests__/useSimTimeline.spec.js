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

describe('useSimTimeline — market moments', () => {
  it('emits a moment when |Δprice_yes| >= 15pp between consecutive rounds', () => {
    const t = useSimTimeline({
      startedAt: START, forecastDays: 10, roundCount: 5,
      structured: {},
      marketCurves: [{
        market_id: 'm1',
        question: 'Will X happen?',
        points: [
          { round_num: 1, price_yes: 0.50 },
          { round_num: 2, price_yes: 0.52 },  // +2pp, ignored
          { round_num: 3, price_yes: 0.70 },  // +18pp, keep
          { round_num: 4, price_yes: 0.55 },  // -15pp, keep (boundary)
          { round_num: 5, price_yes: 0.60 },  // +5pp, ignored
        ],
      }],
      topPosts: [], agentTrajectories: [],
    })
    const market = t.moments.filter(m => m.type === 'market')
    expect(market).toHaveLength(2)
    expect(market[0].roundIndex).toBe(2)  // 0-indexed round 3
    expect(market[0].refId).toBe('m1')
    expect(market[0].title).toContain('Will X happen?')
    expect(market[1].roundIndex).toBe(3)
  })

  it('skips markets with fewer than 2 points', () => {
    const t = useSimTimeline({
      startedAt: START, forecastDays: 10, roundCount: 3,
      structured: {},
      marketCurves: [{ market_id: 'm1', question: 'Q', points: [{ round_num: 1, price_yes: 0.5 }] }],
      topPosts: [], agentTrajectories: [],
    })
    expect(t.moments.filter(m => m.type === 'market')).toHaveLength(0)
  })
})
