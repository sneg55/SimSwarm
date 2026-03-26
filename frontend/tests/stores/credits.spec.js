import { describe, it, expect } from 'vitest'
import { useCreditsStore } from '../../src/stores/credits'

describe('Credits Store', () => {
  it('starts with zero balance', () => {
    const store = useCreditsStore()
    expect(store.balance).toBe(0)
  })

  it('sets balance correctly', () => {
    const store = useCreditsStore()
    store.setBalance(100)
    expect(store.balance).toBe(100)
  })

  it('detects low balance when below threshold', () => {
    const store = useCreditsStore()
    store.setBalance(20)
    expect(store.isLow).toBe(true)
  })

  it('not low when balance is sufficient', () => {
    const store = useCreditsStore()
    store.setBalance(50)
    expect(store.isLow).toBe(false)
  })

  it('canAfford returns true when balance covers tier cost', () => {
    const store = useCreditsStore()
    store.setBalance(90)
    expect(store.canAfford('small')).toBe(true)
    expect(store.canAfford('medium')).toBe(true)
    expect(store.canAfford('large')).toBe(false)
  })
})
