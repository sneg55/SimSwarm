import { describe, it, expect } from 'vitest'
import { useSimTimeline, clusterMoments } from '../useSimTimeline'

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

describe('useSimTimeline — finding moments', () => {
  it('anchors findings to phase end-rounds when phase matches', () => {
    const t = useSimTimeline({
      startedAt: START, forecastDays: 30, roundCount: 9,
      structured: {
        findings: [
          { title: 'F1', phase: 'Early' },
          { title: 'F2', phase: 'Late' },
          { title: 'F3' },
        ],
        phase_boundaries: [
          { phase: 'Early', rounds: [1, 3] },
          { phase: 'Mid', rounds: [4, 6] },
          { phase: 'Late', rounds: [7, 9] },
        ],
      },
      marketCurves: [], topPosts: [], agentTrajectories: [],
    })
    const f = t.moments.filter(m => m.type === 'finding')
    expect(f).toHaveLength(3)
    expect(f[0].title).toBe('F1'); expect(f[0].roundIndex).toBe(2)  // round 3
    expect(f[1].title).toBe('F2'); expect(f[1].roundIndex).toBe(8)  // round 9
    expect(f[2].title).toBe('F3'); expect(f[2].roundIndex).toBe(4)  // midpoint
  })

  it('returns no finding moments when findings array is missing', () => {
    const t = useSimTimeline({
      startedAt: START, forecastDays: 10, roundCount: 5,
      structured: {}, marketCurves: [], topPosts: [], agentTrajectories: [],
    })
    expect(t.moments.filter(m => m.type === 'finding')).toEqual([])
  })
})

describe('useSimTimeline — post moments', () => {
  it('keeps top-engagement post per round, above floor', () => {
    const t = useSimTimeline({
      startedAt: START, forecastDays: 10, roundCount: 3,
      structured: {},
      marketCurves: [],
      topPosts: [
        { round_num: 1, agent_name: 'A', text: 'low',  engagement: 0 },
        { round_num: 2, agent_name: 'B', text: 'mid',  engagement: 3 },
        { round_num: 2, agent_name: 'C', text: 'high', engagement: 7 },
        { round_num: 3, agent_name: 'D', text: 'only', engagement: 2 },
      ],
      agentTrajectories: [],
    })
    const posts = t.moments.filter(m => m.type === 'post')
    expect(posts).toHaveLength(2)
    expect(posts[0].roundIndex).toBe(1); expect(posts[0].title).toContain('C')
    expect(posts[1].roundIndex).toBe(2); expect(posts[1].title).toContain('D')
  })
})

describe('useSimTimeline — coalition moments', () => {
  it('emits a moment when plurality stance flips round-over-round', () => {
    const t = useSimTimeline({
      startedAt: START, forecastDays: 10, roundCount: 4,
      structured: {}, marketCurves: [], topPosts: [],
      agentTrajectories: [
        { agent_name: 'a', stance_per_round: [
          { round_num: 1, stance: 'pro' }, { round_num: 2, stance: 'pro' },
          { round_num: 3, stance: 'con' }, { round_num: 4, stance: 'con' },
        ]},
        { agent_name: 'b', stance_per_round: [
          { round_num: 1, stance: 'pro' }, { round_num: 2, stance: 'pro' },
          { round_num: 3, stance: 'con' }, { round_num: 4, stance: 'pro' },
        ]},
      ],
    })
    const shifts = t.moments.filter(m => m.type === 'coalition')
    expect(shifts.map(s => s.roundIndex)).toEqual([2, 3])
    expect(shifts[0].detail).toContain('pro')
    expect(shifts[0].detail).toContain('con')
  })

  it('ignores neutral/unknown stances when computing plurality', () => {
    const t = useSimTimeline({
      startedAt: START, forecastDays: 10, roundCount: 2,
      structured: {}, marketCurves: [], topPosts: [],
      agentTrajectories: [
        { agent_name: 'a', stance_per_round: [
          { round_num: 1, stance: 'neutral' }, { round_num: 2, stance: 'neutral' },
        ]},
      ],
    })
    expect(t.moments.filter(m => m.type === 'coalition')).toEqual([])
  })
})

describe('clusterMoments', () => {
  it('groups moments within the threshold and leaves others alone', () => {
    const moments = [
      { id: 'a', roundIndex: 0 },
      { id: 'b', roundIndex: 1 },
      { id: 'c', roundIndex: 10 },
    ]
    const clusters = clusterMoments(moments, 11, 0.02)
    expect(clusters).toHaveLength(3)
  })

  it('collapses nearby moments into a single cluster', () => {
    const moments = [
      { id: 'a', roundIndex: 5 },
      { id: 'b', roundIndex: 5 },
      { id: 'c', roundIndex: 6 },
    ]
    const clusters = clusterMoments(moments, 100, 0.02)
    expect(clusters).toHaveLength(1)
    expect(clusters[0].items).toHaveLength(3)
  })

  it('sorts input by roundIndex before clustering', () => {
    const moments = [
      { id: 'c', roundIndex: 10 },
      { id: 'a', roundIndex: 0 },
      { id: 'b', roundIndex: 1 },
    ]
    const clusters = clusterMoments(moments, 11, 0.02)
    expect(clusters.map(c => c.items[0].id)).toEqual(['a', 'b', 'c'])
  })
})
