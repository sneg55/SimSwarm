import { describe, it, expect, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

describe('Config store — static mode', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it('load() sets demoMode=true without hitting the API in static mode', async () => {
    vi.stubEnv('VITE_STATIC_DEMO', 'true')
    vi.resetModules()
    setActivePinia(createPinia())

    const { useConfigStore } = await import('../../src/stores/config.js')
    const store = useConfigStore()
    await store.load()

    expect(store.demoMode).toBe(true)
    expect(store.loaded).toBe(true)
  })
})
