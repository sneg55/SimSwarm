import api from './index.js'
import { useAuthStore } from '../stores/auth.js'

function getUserId() {
  const authStore = useAuthStore()
  return String(authStore.user?.id ?? '')
}

export async function createJob(payload) {
  const userId = getUserId()
  const body = {
    user_id: userId,
    seed_text: payload.seed_text,
    goal: payload.goal,
    tier: payload.tier,
  }
  const response = await api.post('/jobs', body)
  return response.data
}

export async function getJob(jobId) {
  const response = await api.get(`/jobs/${jobId}`)
  return response.data
}

export async function listJobs() {
  const userId = getUserId()
  const response = await api.get('/jobs', { params: { user_id: userId } })
  return response.data
}
