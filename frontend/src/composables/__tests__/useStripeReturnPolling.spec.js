import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { useStripeReturnPolling } from '../useStripeReturnPolling.js'

function makeStore(initial = 0) {
  return { balance: initial, setBalance(v) { this.balance = v } }
}

describe('useStripeReturnPolling', () => {
  beforeEach(() => { vi.useFakeTimers() })
  afterEach(() => { vi.useRealTimers() })

  it('polls until balance increases, then updates store and stops', async () => {
    const store = makeStore(50)
    const getBalance = vi.fn()
      .mockResolvedValueOnce({ balance: 50 })   // first poll: not yet credited
      .mockResolvedValueOnce({ balance: 50 })   // second poll: still not credited
      .mockResolvedValueOnce({ balance: 150 })  // third poll: webhook landed

    let polling
    const Comp = {
      setup() {
        const p = useStripeReturnPolling({ getBalance, creditsStore: store, intervalMs: 100, maxDurationMs: 10000 })
        polling = p
        p.start(50)
        return () => null
      },
      template: '<div />',
    }
    mount(Comp)

    // tick 3 cycles (each tick: advance timer + flush microtasks)
    for (let i = 0; i < 3; i++) {
      await vi.advanceTimersByTimeAsync(100)
    }

    expect(getBalance).toHaveBeenCalledTimes(3)
    expect(store.balance).toBe(150)
    expect(polling.polling.value).toBe(false)
  })

  it('stops polling when max duration elapses without a balance increase', async () => {
    const store = makeStore(50)
    const getBalance = vi.fn().mockResolvedValue({ balance: 50 })

    let polling
    const Comp = {
      setup() {
        const p = useStripeReturnPolling({ getBalance, creditsStore: store, intervalMs: 100, maxDurationMs: 250 })
        polling = p
        p.start(50)
        return () => null
      },
      template: '<div />',
    }
    mount(Comp)

    // Advance well past maxDurationMs
    for (let i = 0; i < 5; i++) {
      await vi.advanceTimersByTimeAsync(100)
    }
    expect(polling.polling.value).toBe(false)
    expect(store.balance).toBe(50)
  })

  it('stops on unmount', async () => {
    const store = makeStore(50)
    const getBalance = vi.fn().mockResolvedValue({ balance: 50 })

    let polling
    const Comp = {
      setup() {
        const p = useStripeReturnPolling({ getBalance, creditsStore: store, intervalMs: 100, maxDurationMs: 10000 })
        polling = p
        p.start(50)
        return () => null
      },
      template: '<div />',
    }
    const wrapper = mount(Comp)
    wrapper.unmount()
    expect(polling.polling.value).toBe(false)
  })
})
