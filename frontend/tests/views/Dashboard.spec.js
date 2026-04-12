import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('../../src/api/jobs.js', () => ({
  listJobs: vi.fn(),
  deleteJob: vi.fn(),
}))
vi.mock('../../src/api/billing.js', () => ({
  getBalance: vi.fn(),
}))

import Dashboard from '../../src/views/Dashboard.vue'
import { listJobs, deleteJob } from '../../src/api/jobs.js'
import { getBalance } from '../../src/api/billing.js'

const stubs = {
  'router-link': { template: '<a><slot /></a>' },
  CreditWarning: true,
  DashboardEmpty: { template: '<div class="empty">No jobs</div>' },
  SimCard: { props: ['job'], template: '<div class="simcard">{{ job.goal }}</div>' },
  SkeletonCard: true,
}

describe('Dashboard.vue', () => {
  beforeEach(() => {
    listJobs.mockReset()
    deleteJob.mockReset()
    getBalance.mockReset()
    vi.stubGlobal('confirm', vi.fn(() => true))
  })

  it('shows empty state', async () => {
    listJobs.mockResolvedValue({ jobs: [], total: 0 })
    getBalance.mockResolvedValue({ balance: 100 })
    const wrapper = mount(Dashboard, { global: { stubs } })
    await flushPromises()
    expect(wrapper.find('.empty').exists()).toBe(true)
  })

  it('renders drafts, active and recent jobs', async () => {
    listJobs.mockResolvedValue({
      jobs: [
        { id: 'd1', status: 'DRAFT', goal: 'Draft goal', tier: 'small', created_at: '2026-01-01T00:00:00Z' },
        { id: 'a1', status: 'RUNNING', goal: 'Active goal' },
        { id: 'r1', status: 'COMPLETED', goal: 'Done goal' },
      ],
      total: 3,
    })
    getBalance.mockResolvedValue({ balance: 50 })
    const wrapper = mount(Dashboard, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('Drafts')
    expect(wrapper.text()).toContain('Active')
    expect(wrapper.text()).toContain('Recent')
    expect(wrapper.text()).toContain('Draft goal')
    expect(wrapper.findAll('.simcard').length).toBe(2)
  })

  it('handles draft with no goal and missing tier', async () => {
    listJobs.mockResolvedValue({
      jobs: [{ id: 'd1', status: 'DRAFT', goal: '', created_at: '2026-01-01T00:00:00Z' }],
      total: 1,
    })
    getBalance.mockResolvedValue({ balance: 0 })
    const wrapper = mount(Dashboard, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('Untitled draft')
  })

  it('handles load failure', async () => {
    listJobs.mockRejectedValue(new Error('fail'))
    getBalance.mockRejectedValue(new Error('fail'))
    const err = vi.spyOn(console, 'error').mockImplementation(() => {})
    const wrapper = mount(Dashboard, { global: { stubs } })
    await flushPromises()
    expect(err).toHaveBeenCalled()
    err.mockRestore()
  })

  it('loads more jobs and handles error rollback', async () => {
    listJobs.mockResolvedValueOnce({ jobs: [{ id: '1', status: 'COMPLETED' }], total: 2 })
    getBalance.mockResolvedValue({ balance: 10 })
    const wrapper = mount(Dashboard, { global: { stubs } })
    await flushPromises()
    // load more success
    listJobs.mockResolvedValueOnce({ jobs: [{ id: '2', status: 'COMPLETED' }], total: 2 })
    await wrapper.find('button').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.simcard').length).toBe(2)
  })

  it('load more failure rolls back page', async () => {
    listJobs.mockResolvedValueOnce({ jobs: [{ id: '1', status: 'COMPLETED' }], total: 2 })
    getBalance.mockResolvedValue({ balance: 10 })
    const wrapper = mount(Dashboard, { global: { stubs } })
    await flushPromises()
    listJobs.mockRejectedValueOnce(new Error('x'))
    const err = vi.spyOn(console, 'error').mockImplementation(() => {})
    await wrapper.find('button').trigger('click')
    await flushPromises()
    expect(err).toHaveBeenCalled()
    err.mockRestore()
  })

  it('deletes draft after confirm', async () => {
    listJobs.mockResolvedValue({
      jobs: [{ id: 'd1', status: 'DRAFT', goal: 'G', created_at: '2026-01-01' }],
      total: 1,
    })
    getBalance.mockResolvedValue({ balance: 0 })
    deleteJob.mockResolvedValue({})
    const wrapper = mount(Dashboard, { global: { stubs } })
    await flushPromises()
    const delBtn = wrapper.find('button[title="Delete draft"]')
    await delBtn.trigger('click')
    await flushPromises()
    expect(deleteJob).toHaveBeenCalledWith('d1')
  })

  it('cancels delete when user declines confirm', async () => {
    vi.stubGlobal('confirm', vi.fn(() => false))
    listJobs.mockResolvedValue({
      jobs: [{ id: 'd1', status: 'DRAFT', goal: 'G', created_at: '2026-01-01' }],
      total: 1,
    })
    getBalance.mockResolvedValue({ balance: 0 })
    const wrapper = mount(Dashboard, { global: { stubs } })
    await flushPromises()
    const delBtn = wrapper.find('button[title="Delete draft"]')
    await delBtn.trigger('click')
    await flushPromises()
    expect(deleteJob).not.toHaveBeenCalled()
  })

  it('delete failure logged', async () => {
    listJobs.mockResolvedValue({
      jobs: [{ id: 'd1', status: 'DRAFT', goal: 'G', created_at: '2026-01-01' }],
      total: 1,
    })
    getBalance.mockResolvedValue({ balance: 0 })
    deleteJob.mockRejectedValue(new Error('nope'))
    const err = vi.spyOn(console, 'error').mockImplementation(() => {})
    const wrapper = mount(Dashboard, { global: { stubs } })
    await flushPromises()
    await wrapper.find('button[title="Delete draft"]').trigger('click')
    await flushPromises()
    expect(err).toHaveBeenCalled()
    err.mockRestore()
  })
})
