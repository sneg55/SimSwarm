import { describe, it, expect, afterEach } from 'vitest'
import { useStoryScrollSync, __resetStoryScrollSync } from '../useStoryScrollSync'

afterEach(() => __resetStoryScrollSync())

describe('useStoryScrollSync', () => {
  it('exposes a shared activeRoundIndex across callers', () => {
    const a = useStoryScrollSync()
    const b = useStoryScrollSync()
    a.setActiveRoundIndex(3)
    expect(b.activeRoundIndex.value).toBe(3)
  })

  it('clamps negative or out-of-range indices via setActiveRoundIndex', () => {
    const s = useStoryScrollSync()
    s.setActiveRoundIndex(-5)
    expect(s.activeRoundIndex.value).toBe(0)
    s.setActiveRoundIndex(1.7)
    expect(s.activeRoundIndex.value).toBe(1)
  })
})
