import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../index.js', () => {
  return { default: { get: vi.fn() } }
})

import api from '../index.js'
import { getHistory } from '../billing.js'

describe('getHistory', () => {
  beforeEach(() => { api.get.mockReset() })

  it('returns array + total from x-total-count when paginated', async () => {
    api.get.mockResolvedValue({
      data: [{ id: 1, amount: 100 }, { id: 2, amount: 50 }],
      headers: { 'x-total-count': '17' },
    })
    const result = await getHistory({ limit: 2, offset: 0 })
    expect(api.get).toHaveBeenCalledWith('/billing/history', { params: { limit: 2, offset: 0 } })
    expect(result.entries).toHaveLength(2)
    expect(result.total).toBe(17)
  })

  it('falls back to data length when no x-total-count header', async () => {
    api.get.mockResolvedValue({
      data: [{ id: 1 }, { id: 2 }, { id: 3 }],
      headers: {},
    })
    const result = await getHistory()
    expect(api.get).toHaveBeenCalledWith('/billing/history', { params: {} })
    expect(result.total).toBe(3)
  })

  it('passes through offset to query params', async () => {
    api.get.mockResolvedValue({ data: [], headers: { 'x-total-count': '50' } })
    await getHistory({ limit: 20, offset: 40 })
    expect(api.get).toHaveBeenCalledWith('/billing/history', { params: { limit: 20, offset: 40 } })
  })
})
