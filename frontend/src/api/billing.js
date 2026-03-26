import api from './index.js'

export async function getBalance() {
  const response = await api.get('/billing/balance')
  return response.data
}

export async function purchaseCredits(pack) {
  const response = await api.post('/billing/purchase', { pack })
  return response.data
}

export async function getHistory() {
  const response = await api.get('/billing/history')
  return response.data
}
