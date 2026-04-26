import api from './index.js'

export async function createJob(payload) {
  const body = {
    seed_text: payload.seed_text,
    goal: payload.goal,
    tier: payload.tier,
    enrich_web: payload.enrich_web ?? true,
    forecast_days: payload.forecast_days ?? null,
  }
  const response = await api.post('/jobs', body)
  return response.data
}

export async function createDraft(payload) {
  const body = {
    seed_text: payload.seed_text ?? '',
    enrich_web: payload.enrich_web ?? true,
    goal: payload.goal ?? null,
    tier: payload.tier ?? null,
    forecast_days: payload.forecast_days ?? null,
  }
  const response = await api.post('/jobs/draft', body)
  return response.data
}

export async function updateDraft(draftId, payload) {
  const response = await api.patch(`/jobs/draft/${draftId}`, payload)
  return response.data
}

export async function launchDraft(draftId) {
  const response = await api.post(`/jobs/draft/${draftId}/launch`)
  return response.data
}

export async function retryEnrichment(jobId) {
  const response = await api.post(`/jobs/${jobId}/enrich-retry`)
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

export async function createShareLink(jobId) {
  const resp = await api.post(`/jobs/${jobId}/share`)
  return resp.data
}

export async function revokeShareLink(jobId) {
  const resp = await api.delete(`/jobs/${jobId}/share`)
  return resp.data
}

export async function getSimData(jobId) {
  const response = await api.get(`/jobs/${jobId}/sim-data`)
  return response.data
}
