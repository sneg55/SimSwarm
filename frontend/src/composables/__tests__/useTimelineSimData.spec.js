import { describe, it, expect } from 'vitest'
import { computeRoundCount } from '../useTimelineSimData'

describe('computeRoundCount', () => {
  it('derives round count from agent rounds[].round (real extractor shape)', () => {
    const at = [{ rounds: [{ round: 1 }, { round: 12 }, { round: 100 }] }]
    expect(computeRoundCount([], at)).toBe(100)
  })
  it('still honors stance_per_round shape (legacy tests)', () => {
    const at = [{ stance_per_round: [{ round_num: 1 }, { round_num: 5 }] }]
    expect(computeRoundCount([], at)).toBe(5)
  })
  it('returns 0 when neither shape has rounds', () => {
    expect(computeRoundCount([], [{}])).toBe(0)
  })
})
