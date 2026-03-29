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

export async function listJobs(page = 1, perPage = 10) {
  const response = await api.get('/jobs', { params: { page, per_page: perPage } })
  return response.data
}

export async function retryJob(jobId) {
  const response = await api.post(`/jobs/${jobId}/retry`)
  return response.data
}

export async function deleteJob(jobId) {
  const response = await api.delete(`/jobs/${jobId}`)
  return response.data
}

export async function getJobGraph(jobId) {
  const response = await api.get(`/jobs/${jobId}/graph`)
  return response.data
}

export async function exportPDF(jobId) {
  const resp = await api.get(`/jobs/${jobId}/export/pdf`, { responseType: 'blob' })
  return resp.data
}

export async function exportJSON(jobId) {
  const resp = await api.get(`/jobs/${jobId}/export/json`, { responseType: 'blob' })
  return resp.data
}

export async function createShareLink(jobId) {
  const resp = await api.post(`/jobs/${jobId}/share`)
  return resp.data
}

export async function revokeShareLink(jobId) {
  const resp = await api.delete(`/jobs/${jobId}/share`)
  return resp.data
}
