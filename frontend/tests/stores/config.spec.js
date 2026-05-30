import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('../../src/api/config.js', () => ({
  getConfig: vi.fn(),
}))

import { useConfigStore } from '../../src/stores/config.js'
import { getConfig } from '../../src/api/config.js'

describe('Config Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getConfig.mockReset()
  })

  it('starts with demoMode=false and loaded=false', () => {
    const store = useConfigStore()
    expect(store.demoMode).toBe(false)
    expect(store.loaded).toBe(false)
  })

  it('load() sets demoMode=true when API returns demo_mode=true', async () => {
    getConfig.mockResolvedValue({ demo_mode: true })
    const store = useConfigStore()
    await store.load()
    expect(store.demoMode).toBe(true)
    expect(store.loaded).toBe(true)
  })

  it('load() sets demoMode=false when API returns demo_mode=false', async () => {
    getConfig.mockResolvedValue({ demo_mode: false })
    const store = useConfigStore()
    await store.load()
    expect(store.demoMode).toBe(false)
    expect(store.loaded).toBe(true)
  })

  it('load() coerces truthy non-boolean to true', async () => {
    getConfig.mockResolvedValue({ demo_mode: 1 })
    const store = useConfigStore()
    await store.load()
    expect(store.demoMode).toBe(true)
    expect(store.loaded).toBe(true)
  })

  it('load() fails open: demoMode stays false and loaded becomes true on API error', async () => {
    getConfig.mockRejectedValue(new Error('Network error'))
    const store = useConfigStore()
    await store.load()
    expect(store.demoMode).toBe(false)
    expect(store.loaded).toBe(true)
  })

  it('load() fails open on 500 rejection', async () => {
    getConfig.mockRejectedValue({ response: { status: 500 } })
    const store = useConfigStore()
    await store.load()
    expect(store.demoMode).toBe(false)
    expect(store.loaded).toBe(true)
  })
})
