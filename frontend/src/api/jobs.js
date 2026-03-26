import api from './index.js'

export async function createJob(payload) {
  const response = await api.post('/jobs', payload)
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
