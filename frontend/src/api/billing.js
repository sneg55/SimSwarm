import api from './index.js'

export async function getPacks() {
  const response = await api.get('/billing/packs')
  return response.data
}

export async function getBalance() {
  const response = await api.get('/billing/balance')
  return response.data
}

export async function purchaseCredits(packId) {
  const response = await api.post('/billing/purchase', { pack_id: packId })
  return response.data
}

export async function getHistory({ limit, offset = 0 } = {}) {
  const params = limit !== undefined ? { limit, offset } : {}
  const response = await api.get('/billing/history', { params })
  // Paginated calls surface the row count via X-Total-Count.
  // Unpaginated calls fall back to the array length so callers can treat the
  // shape uniformly without branching.
  const totalHeader = response.headers?.['x-total-count']
  const total = totalHeader !== undefined ? parseInt(totalHeader, 10) : response.data.length
  return { entries: response.data, total }
}
