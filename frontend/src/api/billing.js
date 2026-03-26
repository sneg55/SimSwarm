import api from './index.js'
import { useAuthStore } from '../stores/auth.js'

function getUserId() {
  const authStore = useAuthStore()
  return authStore.user?.id
}

export async function getBalance() {
  const userId = getUserId()
  const response = await api.get('/billing/balance', { params: { user_id: userId } })
  return response.data
}

export async function purchaseCredits(packId) {
  const userId = getUserId()
  const response = await api.post('/billing/purchase', { user_id: userId, pack_id: packId })
  return response.data
}

export async function getHistory() {
  const userId = getUserId()
  const response = await api.get('/billing/history', { params: { user_id: userId } })
  return response.data
}
