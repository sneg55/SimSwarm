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

export async function getHistory() {
  const response = await api.get('/billing/history')
  return response.data
}
