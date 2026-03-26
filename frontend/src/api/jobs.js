import api from './index.js'

export async function createJob(payload) {
  const body = {
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
  const response = await api.get('/jobs')
  return response.data
}
