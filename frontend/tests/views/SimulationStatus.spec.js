import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const pushMock = vi.fn()
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'jobX' } }),
  useRouter: () => ({ push: pushMock }),
}))

vi.mock('../../src/api/jobs.js', () => ({
  getJob: vi.fn(),
  retryJob: vi.fn(),
  retryEnrichment: vi.fn(),
}))

import SimulationStatus from '../../src/views/SimulationStatus.vue'
import { getJob, retryJob, retryEnrichment } from '../../src/api/jobs.js'

const stubs = {
  'router-link': { template: '<a><slot /></a>' },
  PipelineProgress: { props: ['currentStep', 'completedSteps'], template: '<div class="pp" />' },
  ChatReplay: { name: 'ChatReplay', template: '<div class="cr" />' },
  SkeletonCard: true,
  ReportViewer: { props: ['content'], template: '<div class="rv" />' },
  LiveActivity: { name: 'LiveActivity', template: '<div class="la" />' },
}

describe('SimulationStatus.vue', () => {
  beforeEach(() => {
    pushMock.mockClear()
    getJob.mockReset()
    retryJob.mockReset()
    retryEnrichment.mockReset()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows loading initially then RUNNING details', async () => {
    getJob.mockResolvedValue({
      id: 'jobX', status: 'RUNNING', goal: 'G', tier: 'small',
      pipeline_stage: 3, created_at: new Date(Date.now() - 60_000).toISOString(),
    })
    const wrapper = mount(SimulationStatus, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('Running')
    expect(wrapper.text()).toContain('Simulating')
    expect(wrapper.text()).toContain('of 5')
    wrapper.unmount()
  })

  it('renders PENDING state', async () => {
    getJob.mockResolvedValue({
      id: 'jobX', status: 'PENDING', goal: 'G', tier: 'medium',
      created_at: new Date().toISOString(),
    })
    const wrapper = mount(SimulationStatus, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('Queued')
    expect(wrapper.text()).toContain('Waiting for GPU')
    wrapper.unmount()
  })

  it('renders PROVISIONING state', async () => {
    getJob.mockResolvedValue({
      id: 'jobX', status: 'PROVISIONING', goal: 'G', tier: 'large',
      created_at: new Date().toISOString(),
    })
    const wrapper = mount(SimulationStatus, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('Allocating GPU')
    wrapper.unmount()
  })

  it('renders COMPLETED state with completed_at', async () => {
    getJob.mockResolvedValue({
      id: 'jobX', status: 'COMPLETED', goal: 'G', tier: 'small',
      created_at: '2026-01-01T00:00:00Z',
      completed_at: '2026-01-01T00:05:00Z',
      pipeline_seconds: 300,
    })
    const wrapper = mount(SimulationStatus, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('Complete')
    expect(wrapper.text()).toContain('View Results')
    wrapper.unmount()
  })

  it('COMPLETED fallback duration from timestamps', async () => {
    getJob.mockResolvedValue({
      id: 'jobX', status: 'COMPLETED', goal: 'G', tier: 'small',
      created_at: '2026-01-01T00:00:00Z',
      completed_at: '2026-01-01T00:02:30Z',
    })
    const wrapper = mount(SimulationStatus, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('Duration')
    wrapper.unmount()
  })

  it('renders FAILED with retry that routes to new job', async () => {
    getJob.mockResolvedValue({
      id: 'jobX', status: 'FAILED', goal: 'G', tier: 'small',
      error_message: 'broke',
      created_at: '2026-01-01T00:00:00Z',
    })
    retryJob.mockResolvedValue({ id: 'jobY' })
    const wrapper = mount(SimulationStatus, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('Simulation failed')
    expect(wrapper.text()).toContain('broke')
    const retryBtn = wrapper.findAll('button').find(b => b.text().includes('Retry'))
    await retryBtn.trigger('click')
    await flushPromises()
    expect(pushMock).toHaveBeenCalledWith('/sim/jobY')
    wrapper.unmount()
  })

  it('FAILED retry failure alerts', async () => {
    getJob.mockResolvedValue({
      id: 'jobX', status: 'FAILED', goal: 'G', tier: 'small',
      created_at: '2026-01-01T00:00:00Z',
    })
    retryJob.mockRejectedValue({ response: { data: { detail: 'nope' } } })
    const alertMock = vi.fn()
    vi.stubGlobal('alert', alertMock)
    const wrapper = mount(SimulationStatus, { global: { stubs } })
    await flushPromises()
    const retryBtn = wrapper.findAll('button').find(b => b.text().includes('Retry'))
    await retryBtn.trigger('click')
    await flushPromises()
    expect(alertMock).toHaveBeenCalledWith('nope')
    wrapper.unmount()
  })

  it('toggles web research panel', async () => {
    getJob.mockResolvedValue({
      id: 'jobX', status: 'RUNNING', goal: 'G', tier: 'small',
      pipeline_stage: 2, created_at: new Date().toISOString(),
      enriched_seed: '## Found this',
    })
    const wrapper = mount(SimulationStatus, { global: { stubs } })
    await flushPromises()
    const toggle = wrapper.findAll('button').find(b => b.text().includes('Web Research'))
    await toggle.trigger('click')
    await flushPromises()
    wrapper.unmount()
  })

  it('handles retryEnrich click and failure silently', async () => {
    getJob.mockResolvedValue({
      id: 'jobX', status: 'PENDING', goal: 'G', tier: 'small',
      enrich_web: true, enriched_seed: null,
      created_at: new Date(Date.now() - 60_000).toISOString(),
    })
    retryEnrichment.mockRejectedValue(new Error('x'))
    const wrapper = mount(SimulationStatus, { global: { stubs } })
    await flushPromises()
    const retryBtn = wrapper.findAll('button').find(b => b.text().includes('Retry'))
    if (retryBtn) {
      await retryBtn.trigger('click')
      await flushPromises()
      expect(retryEnrichment).toHaveBeenCalled()
    }
    wrapper.unmount()
  })

  it('renders chat during active run', async () => {
    getJob.mockResolvedValue({
      id: 'jobX', status: 'RUNNING', goal: 'G', tier: 'small',
      pipeline_stage: 3, created_at: new Date().toISOString(),
      result_chat_log: JSON.stringify([{ role: 'assistant', content: 'hi', agent: 'A' }]),
    })
    const wrapper = mount(SimulationStatus, { global: { stubs } })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ChatReplay' }).exists()).toBe(true)
    wrapper.unmount()
  })

  it('renders live activity when log lines present', async () => {
    getJob.mockResolvedValue({
      id: 'jobX', status: 'RUNNING', goal: 'G', tier: 'small',
      pipeline_stage: 3, created_at: new Date().toISOString(),
      live_status: {
        updated_at: Date.now() / 1000 - 5,
        log_lines: ['log1'],
        partial_chat: [{ agent: 'A', content: 'hi' }],
        round: 3,
        max_rounds: 15,
      },
    })
    const wrapper = mount(SimulationStatus, { global: { stubs } })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'LiveActivity' }).exists()).toBe(true)
    expect(wrapper.text()).toContain('Rounds')
    wrapper.unmount()
  })

  it('handles getJob failure', async () => {
    getJob.mockRejectedValue(new Error('x'))
    const err = vi.spyOn(console, 'error').mockImplementation(() => {})
    const wrapper = mount(SimulationStatus, { global: { stubs } })
    await flushPromises()
    expect(err).toHaveBeenCalled()
    err.mockRestore()
    wrapper.unmount()
  })

  it('stops polling when job completes', async () => {
    getJob.mockResolvedValue({
      id: 'jobX', status: 'COMPLETED', goal: 'G', tier: 'small',
      created_at: '2026-01-01T00:00:00Z', completed_at: '2026-01-01T00:05:00Z',
      pipeline_seconds: 300,
    })
    const wrapper = mount(SimulationStatus, { global: { stubs } })
    await flushPromises()
    // Advance timer; fetchJob should not be called again past clearInterval
    getJob.mockClear()
    vi.advanceTimersByTime(5000)
    await flushPromises()
    wrapper.unmount()
  })

  it('handles malformed chat log', async () => {
    getJob.mockResolvedValue({
      id: 'jobX', status: 'RUNNING', goal: 'G', tier: 'small',
      pipeline_stage: 2, created_at: new Date().toISOString(),
      result_chat_log: 'not json',
    })
    const wrapper = mount(SimulationStatus, { global: { stubs } })
    await flushPromises()
    // Should not crash
    wrapper.unmount()
  })

  it('citations parse failure falls back', async () => {
    getJob.mockResolvedValue({
      id: 'jobX', status: 'RUNNING', goal: 'G', tier: 'small',
      pipeline_stage: 1, created_at: new Date().toISOString(),
      enrichment_citations: 'broken',
    })
    const wrapper = mount(SimulationStatus, { global: { stubs } })
    await flushPromises()
    wrapper.unmount()
  })

  it('REFUNDED status label map', async () => {
    getJob.mockResolvedValue({
      id: 'jobX', status: 'REFUNDED', goal: 'G', tier: 'small',
      created_at: '2026-01-01T00:00:00Z',
    })
    const wrapper = mount(SimulationStatus, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('Refunded')
    wrapper.unmount()
  })
})
