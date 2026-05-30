import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('../../src/api/jobs.js', () => ({
  listJobs: vi.fn(),
  deleteJob: vi.fn(),
  getJob: vi.fn(),
  createDraft: vi.fn(),
}))

const { routerPush } = vi.hoisted(() => ({ routerPush: vi.fn() }))
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: routerPush }),
}))

import Dashboard from '../../src/views/Dashboard.vue'
import { listJobs, deleteJob, getJob, createDraft } from '../../src/api/jobs.js'

const stubs = {
  'router-link': { template: '<a><slot /></a>' },
  DashboardEmpty: { template: '<div class="empty">No jobs</div>' },
  SimCard: {
    props: ['job'],
    emits: ['delete', 'restart'],
    template: `<div class="simcard">{{ job.goal }}<button class="restart-trigger" @click="$emit('restart', job)">r</button></div>`,
  },
  SkeletonCard: true,
}

describe('Dashboard.vue', () => {
  beforeEach(() => {
    listJobs.mockReset()
    deleteJob.mockReset()
    getJob.mockReset()
    createDraft.mockReset()
    routerPush.mockReset()
    vi.stubGlobal('confirm', vi.fn(() => true))
  })

  it('shows empty state', async () => {
    listJobs.mockResolvedValue({ jobs: [], total: 0 })

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

    const wrapper = mount(Dashboard, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('Untitled draft')
  })

  it('handles load failure', async () => {
    listJobs.mockRejectedValue(new Error('fail'))

    const err = vi.spyOn(console, 'error').mockImplementation(() => {})
    const wrapper = mount(Dashboard, { global: { stubs } })
    await flushPromises()
    expect(err).toHaveBeenCalled()
    err.mockRestore()
  })

  it('loads more jobs and handles error rollback', async () => {
    listJobs.mockResolvedValueOnce({ jobs: [{ id: '1', status: 'COMPLETED' }], total: 2 })

    const wrapper = mount(Dashboard, { global: { stubs } })
    await flushPromises()
    // load more success
    listJobs.mockResolvedValueOnce({ jobs: [{ id: '2', status: 'COMPLETED' }], total: 2 })
    const loadMore = wrapper.findAll('button').find(b => b.text().includes('Load more'))
    await loadMore.trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.simcard').length).toBe(2)
  })

  it('load more failure rolls back page', async () => {
    listJobs.mockResolvedValueOnce({ jobs: [{ id: '1', status: 'COMPLETED' }], total: 2 })

    const wrapper = mount(Dashboard, { global: { stubs } })
    await flushPromises()
    listJobs.mockRejectedValueOnce(new Error('x'))
    const err = vi.spyOn(console, 'error').mockImplementation(() => {})
    const loadMore = wrapper.findAll('button').find(b => b.text().includes('Load more'))
    await loadMore.trigger('click')
    await flushPromises()
    expect(err).toHaveBeenCalled()
    err.mockRestore()
  })

  it('deletes draft after confirm', async () => {
    listJobs.mockResolvedValue({
      jobs: [{ id: 'd1', status: 'DRAFT', goal: 'G', created_at: '2026-01-01' }],
      total: 1,
    })

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

    deleteJob.mockRejectedValue(new Error('nope'))
    const err = vi.spyOn(console, 'error').mockImplementation(() => {})
    const wrapper = mount(Dashboard, { global: { stubs } })
    await flushPromises()
    await wrapper.find('button[title="Delete draft"]').trigger('click')
    await flushPromises()
    expect(err).toHaveBeenCalled()
    err.mockRestore()
  })

  it('restart fetches full job, creates draft, routes to wizard', async () => {
    listJobs.mockResolvedValue({
      jobs: [{ id: 'r1', status: 'COMPLETED', goal: 'Done' }],
      total: 1,
    })

    getJob.mockResolvedValue({
      id: 'r1',
      seed_text: 'Seed body',
      goal: 'Done',
      tier: 'small',
      enrich_web: false,
      forecast_days: 90,
    })
    createDraft.mockResolvedValue({ id: 'd42' })

    const wrapper = mount(Dashboard, { global: { stubs } })
    await flushPromises()
    await wrapper.find('.restart-trigger').trigger('click')
    await flushPromises()

    expect(getJob).toHaveBeenCalledWith('r1')
    expect(createDraft).toHaveBeenCalledWith({
      seed_text: 'Seed body',
      goal: 'Done',
      tier: 'small',
      enrich_web: false,
      forecast_days: 90,
    })
    expect(routerPush).toHaveBeenCalledWith('/sim/new?draft=d42')
  })

  it('restart defaults forecast_days to 30 when source is null', async () => {
    listJobs.mockResolvedValue({
      jobs: [{ id: 'r1', status: 'COMPLETED', goal: 'Done' }],
      total: 1,
    })

    getJob.mockResolvedValue({
      id: 'r1', seed_text: 'S', goal: 'G', tier: 'small',
      enrich_web: true, forecast_days: null,
    })
    createDraft.mockResolvedValue({ id: 'd1' })

    const wrapper = mount(Dashboard, { global: { stubs } })
    await flushPromises()
    await wrapper.find('.restart-trigger').trigger('click')
    await flushPromises()

    expect(createDraft).toHaveBeenCalledWith(
      expect.objectContaining({ forecast_days: 30 }),
    )
  })

  it('restart failure does not navigate and is logged', async () => {
    listJobs.mockResolvedValue({
      jobs: [{ id: 'r1', status: 'COMPLETED', goal: 'Done' }],
      total: 1,
    })

    getJob.mockRejectedValue(new Error('nope'))
    const err = vi.spyOn(console, 'error').mockImplementation(() => {})

    const wrapper = mount(Dashboard, { global: { stubs } })
    await flushPromises()
    await wrapper.find('.restart-trigger').trigger('click')
    await flushPromises()

    expect(createDraft).not.toHaveBeenCalled()
    expect(routerPush).not.toHaveBeenCalled()
    expect(err).toHaveBeenCalled()
    err.mockRestore()
  })
})
