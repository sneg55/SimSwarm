import { describe, it, expect, vi, afterEach } from 'vitest'

describe('listDemos — static mode', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
    vi.resetModules()
  })

  it('fetches /demos/index.json when VITE_STATIC_DEMO=true', async () => {
    vi.stubEnv('VITE_STATIC_DEMO', 'true')
    vi.resetModules()
    const fetchMock = vi.fn().mockResolvedValue({
      json: () => Promise.resolve([{ share_token: 'a', title: 'Demo A' }]),
    })
    vi.stubGlobal('fetch', fetchMock)

    const { listDemos } = await import('../demos.js')
    const out = await listDemos()

    expect(fetchMock).toHaveBeenCalledWith('/demos/index.json')
    expect(out).toEqual([{ share_token: 'a', title: 'Demo A' }])
  })
})
