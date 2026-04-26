import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Mock axios before importing any API module
vi.mock('axios', () => {
  const instance = {
    get: vi.fn().mockResolvedValue({ data: {} }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    put: vi.fn().mockResolvedValue({ data: {} }),
    patch: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: {} }),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  }
  return {
    default: {
      create: vi.fn(() => instance),
    },
  }
})

import api from '../index.js'
import axios from 'axios'
import * as ai from '../ai.js'
import * as auth from '../auth.js'
import * as billing from '../billing.js'
import * as demos from '../demos.js'
import * as jobs from '../jobs.js'
import * as profile from '../profile.js'

beforeEach(() => {
  api.get.mockClear?.()
  api.post.mockClear?.()
  api.put.mockClear?.()
  api.patch.mockClear?.()
  api.delete.mockClear?.()
  api.get.mockResolvedValue({ data: { ok: 1 } })
  api.post.mockResolvedValue({ data: { ok: 1 } })
  api.put.mockResolvedValue({ data: { ok: 1 } })
  api.patch.mockResolvedValue({ data: { ok: 1 } })
  api.delete.mockResolvedValue({ data: { ok: 1 } })
})

describe('api/index interceptors', () => {
  it('exports an axios instance', () => {
    expect(api).toBeTruthy()
    expect(axios.create).toHaveBeenCalled()
  })

  it('registers interceptors on request and response', () => {
    // interceptors.use was called during module load
    expect(api.interceptors.request.use).toHaveBeenCalled()
    expect(api.interceptors.response.use).toHaveBeenCalled()
  })

  it('request interceptor adds Bearer token when present', () => {
    const reqHandler = api.interceptors.request.use.mock.calls[0][0]
    localStorage.setItem('auth_token', 'abc123')
    const config = { headers: {} }
    const out = reqHandler(config)
    expect(out.headers.Authorization).toBe('Bearer abc123')
  })

  it('request interceptor leaves headers untouched if no token', () => {
    const reqHandler = api.interceptors.request.use.mock.calls[0][0]
    const config = { headers: {} }
    const out = reqHandler(config)
    expect(out.headers.Authorization).toBeUndefined()
  })

  it('response interceptor passes through on success', () => {
    const okHandler = api.interceptors.response.use.mock.calls[0][0]
    const resp = { data: 1 }
    expect(okHandler(resp)).toBe(resp)
  })

  it('response interceptor clears storage and redirects on 401', () => {
    const errHandler = api.interceptors.response.use.mock.calls[0][1]
    localStorage.setItem('auth_token', 'abc')
    localStorage.setItem('auth_user', JSON.stringify({ id: 1 }))
    delete window.location
    window.location = { href: '' }
    const rejection = errHandler({ response: { status: 401 } })
    expect(rejection).toBeInstanceOf(Promise)
    rejection.catch(() => {})
    expect(localStorage.getItem('auth_token')).toBe(null)
    expect(localStorage.getItem('auth_user')).toBe(null)
    expect(window.location.href).toBe('/login')
  })

  it('response interceptor only rejects (not redirect) on non-401 errors', () => {
    const errHandler = api.interceptors.response.use.mock.calls[0][1]
    const rejection = errHandler({ response: { status: 500 } })
    rejection.catch(() => {})
    // Should not clear or redirect
  })

  it('response interceptor handles errors with no response object', () => {
    const errHandler = api.interceptors.response.use.mock.calls[0][1]
    const rejection = errHandler(new Error('Network'))
    rejection.catch(() => {})
  })
})

describe('api/ai', () => {
  it('generateGoal POSTs to /ai/generate-goal', async () => {
    api.post.mockResolvedValue({ data: { goal: 'x' } })
    const result = await ai.generateGoal('seed', 'market-reaction')
    expect(api.post).toHaveBeenCalledWith('/ai/generate-goal', { seed_text: 'seed', category: 'market-reaction' })
    expect(result).toEqual({ goal: 'x' })
  })
})

describe('api/auth', () => {
  it('login POSTs credentials', async () => {
    api.post.mockResolvedValue({ data: { token: 't' } })
    const r = await auth.login('a@b.com', 'pw')
    expect(api.post).toHaveBeenCalledWith('/auth/login', { email: 'a@b.com', password: 'pw' })
    expect(r).toEqual({ token: 't' })
  })
  it('register POSTs credentials', async () => {
    api.post.mockResolvedValue({ data: { id: 1 } })
    const r = await auth.register('a@b.com', 'pw')
    expect(api.post).toHaveBeenCalledWith('/auth/register', { email: 'a@b.com', password: 'pw' })
    expect(r).toEqual({ id: 1 })
  })
})

describe('api/billing', () => {
  it('getPacks', async () => {
    await billing.getPacks()
    expect(api.get).toHaveBeenCalledWith('/billing/packs')
  })
  it('getBalance', async () => {
    await billing.getBalance()
    expect(api.get).toHaveBeenCalledWith('/billing/balance')
  })
  it('purchaseCredits', async () => {
    await billing.purchaseCredits('pack-1')
    expect(api.post).toHaveBeenCalledWith('/billing/purchase', { pack_id: 'pack-1' })
  })
  it('getHistory', async () => {
    await billing.getHistory()
    expect(api.get).toHaveBeenCalledWith('/billing/history', { params: {} })
  })
})

describe('api/demos', () => {
  it('listDemos GETs /share/demos', async () => {
    await demos.listDemos()
    expect(api.get).toHaveBeenCalledWith('/share/demos')
  })
})

describe('api/profile', () => {
  it('changePassword PUTs', async () => {
    await profile.changePassword('old', 'new')
    expect(api.put).toHaveBeenCalledWith('/profile/password', { current_password: 'old', new_password: 'new' })
  })
  it('deleteAccount DELETEs', async () => {
    await profile.deleteAccount()
    expect(api.delete).toHaveBeenCalledWith('/profile/account')
  })
})

describe('api/jobs', () => {
  it('createJob sends full payload with defaults', async () => {
    await jobs.createJob({ seed_text: 's', goal: 'g', tier: 'medium' })
    expect(api.post).toHaveBeenCalledWith('/jobs', {
      seed_text: 's', goal: 'g', tier: 'medium', enrich_web: true, forecast_days: null,
    })
  })

  it('createJob respects enrich_web=false and forecast_days', async () => {
    await jobs.createJob({ seed_text: 's', goal: 'g', tier: 'small', enrich_web: false, forecast_days: 30 })
    expect(api.post).toHaveBeenCalledWith('/jobs', {
      seed_text: 's', goal: 'g', tier: 'small', enrich_web: false, forecast_days: 30,
    })
  })

  it('createDraft uses defaults for missing fields', async () => {
    await jobs.createDraft({})
    expect(api.post).toHaveBeenCalledWith('/jobs/draft', {
      seed_text: '', enrich_web: true, goal: null, tier: null, forecast_days: null,
    })
  })

  it('createDraft passes through values', async () => {
    await jobs.createDraft({ seed_text: 'a', goal: 'b', tier: 'small', enrich_web: false, forecast_days: 7 })
    expect(api.post).toHaveBeenCalledWith('/jobs/draft', {
      seed_text: 'a', enrich_web: false, goal: 'b', tier: 'small', forecast_days: 7,
    })
  })

  it('updateDraft PATCHes', async () => {
    await jobs.updateDraft('id1', { goal: 'new' })
    expect(api.patch).toHaveBeenCalledWith('/jobs/draft/id1', { goal: 'new' })
  })

  it('launchDraft POSTs', async () => {
    await jobs.launchDraft('id1')
    expect(api.post).toHaveBeenCalledWith('/jobs/draft/id1/launch')
  })

  it('retryEnrichment POSTs', async () => {
    await jobs.retryEnrichment('jid')
    expect(api.post).toHaveBeenCalledWith('/jobs/jid/enrich-retry')
  })

  it('getJob GETs', async () => {
    await jobs.getJob('jid')
    expect(api.get).toHaveBeenCalledWith('/jobs/jid')
  })

  it('listJobs with defaults and overrides', async () => {
    await jobs.listJobs()
    expect(api.get).toHaveBeenCalledWith('/jobs', { params: { page: 1, per_page: 10 } })
    await jobs.listJobs(3, 25)
    expect(api.get).toHaveBeenCalledWith('/jobs', { params: { page: 3, per_page: 25 } })
  })

  it('retryJob, deleteJob, getJobGraph', async () => {
    await jobs.retryJob('j')
    expect(api.post).toHaveBeenCalledWith('/jobs/j/retry')
    await jobs.deleteJob('j')
    expect(api.delete).toHaveBeenCalledWith('/jobs/j')
    await jobs.getJobGraph('j')
    expect(api.get).toHaveBeenCalledWith('/jobs/j/graph')
  })

  it('exportPDF and exportJSON request blobs', async () => {
    await jobs.exportPDF('j')
    expect(api.get).toHaveBeenCalledWith('/jobs/j/export/pdf', { responseType: 'blob' })
    await jobs.exportJSON('j')
    expect(api.get).toHaveBeenCalledWith('/jobs/j/export/json', { responseType: 'blob' })
  })

  it('createShareLink, revokeShareLink', async () => {
    await jobs.createShareLink('j')
    expect(api.post).toHaveBeenCalledWith('/jobs/j/share')
    await jobs.revokeShareLink('j')
    expect(api.delete).toHaveBeenCalledWith('/jobs/j/share')
  })

  it('getSimData', async () => {
    await jobs.getSimData('j')
    expect(api.get).toHaveBeenCalledWith('/jobs/j/sim-data')
  })
})
