import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'job1' } }),
}))

vi.mock('../../src/composables/useScrollReveal.js', () => ({
  useScrollReveal: () => {},
}))

vi.mock('../../src/composables/useResultsExport.js', () => ({
  useResultsExport: () => ({
    pdfLoading: { value: false },
    shareStatus: { value: '' },
    handleExport: vi.fn(),
    handleShare: vi.fn(),
  }),
}))

vi.mock('../../src/api/jobs.js', () => ({
  getJob: vi.fn(),
  getJobGraph: vi.fn(),
  getSimData: vi.fn(),
}))

import SimulationResults from '../../src/views/SimulationResults.vue'
import { getJob, getJobGraph, getSimData } from '../../src/api/jobs.js'

const stubs = {
  ResultsToolbar: {
    name: 'ResultsToolbar',
    props: ['title', 'viewMode', 'showToggle', 'showData'],
    emits: ['update:viewMode'],
    template: '<div>{{ title }}</div>',
  },
  ResultsBottomBar: { props: ['showPng', 'showJson', 'showCsv', 'pdfLoading', 'shareStatus'], template: '<div />' },
  ReportToc: true,
  ReportViewer: { props: ['content'], template: '<div class="rv">{{ content }}</div>' },
  ChatReplay: { name: 'ChatReplay', template: '<div class="cr" />' },
  GraphVisualization: { name: 'GraphVisualization', template: '<div class="gv" />' },
  FindingCard: true,
  CoalitionCard: true,
  ConfidenceGrid: true,
  DataDashboard: { props: ['jobId'], template: '<div class="dd">{{ jobId }}</div>' },
  MarketCurveCompact: true,
  EngagementCompact: true,
  InfoTooltip: { template: '<span><slot /></span>' },
}

describe('SimulationResults.vue', () => {
  beforeEach(() => {
    getJob.mockReset()
    getJobGraph.mockReset()
    getSimData.mockReset()
    window.innerWidth = 1200
  })

  it('shows loading then not found when job missing', async () => {
    getJob.mockResolvedValue(null)
    getJobGraph.mockResolvedValue({ nodes: [], edges: [] })
    const wrapper = mount(SimulationResults, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('Results not found')
  })

  it('renders story view with structured data', async () => {
    getJob.mockResolvedValue({
      id: 'job1', goal: 'Will X?', tier: 'small',
      created_at: '2026-01-01T00:00:00Z',
      completed_at: '2026-01-02T00:00:00Z',
      result_report: 'Body',
      result_structured: {
        brief: 'Brief text',
        confidence: [{ label: 'x', value: 80 }],
        findings: [{ label: 'F', title: 'T', description: 'D' }],
        coalitions: [{ name: 'C', description: 'Desc' }],
      },
      sim_data_available: false,
      enriched_seed: '## Background',
    })
    getJobGraph.mockResolvedValue({ nodes: [{ uuid: 'a', name: 'A' }], edges: [] })
    const wrapper = mount(SimulationResults, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('Will X?')
    expect(wrapper.text()).toContain('Executive Brief')
    expect(wrapper.text()).toContain('Sources & Background')
  })

  it('renders plain report when no structured', async () => {
    getJob.mockResolvedValue({
      id: 'job1', goal: 'G', tier: 'medium', result_report: 'Text',
    })
    getJobGraph.mockResolvedValue({ nodes: [], edges: [] })
    const wrapper = mount(SimulationResults, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('G')
  })

  it('fetches sim data when sim_data_available', async () => {
    getJob.mockResolvedValue({
      id: 'job1', goal: 'G', tier: 'medium', result_report: 'R',
      sim_data_available: true,
    })
    getJobGraph.mockResolvedValue({ nodes: [], edges: [] })
    getSimData.mockResolvedValue({
      files: {
        'market_curves.json': 'https://x/m.json',
        'engagement_summary.json': 'https://x/e.json',
      },
    })
    global.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve([{ slug: 'm' }]) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve([{ metric: 'e' }]) })
    const wrapper = mount(SimulationResults, { global: { stubs } })
    await flushPromises()
    expect(getSimData).toHaveBeenCalled()
  })

  it('disables sim data on getSimData failure', async () => {
    getJob.mockResolvedValue({ id: 'job1', goal: 'G', tier: 'small', sim_data_available: true })
    getJobGraph.mockResolvedValue({ nodes: [], edges: [] })
    getSimData.mockRejectedValue(new Error('x'))
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    mount(SimulationResults, { global: { stubs } })
    await flushPromises()
    expect(warn).toHaveBeenCalled()
    warn.mockRestore()
  })

  it('handles graph error 404', async () => {
    getJob.mockResolvedValue({ id: 'job1', goal: 'G', tier: 'small' })
    getJobGraph.mockRejectedValue({ response: { status: 404 } })
    const wrapper = mount(SimulationResults, { global: { stubs } })
    await flushPromises()
    wrapper.findComponent({ name: 'ResultsToolbar' }).vm.$emit('update:viewMode', 'graph')
    await flushPromises()
    expect(wrapper.findComponent({ name: 'GraphVisualization' }).exists()).toBe(true)
  })

  it('handles graph generic error', async () => {
    getJob.mockResolvedValue({ id: 'job1', goal: 'G', tier: 'small' })
    getJobGraph.mockRejectedValue({ response: { status: 500 } })
    mount(SimulationResults, { global: { stubs } })
    await flushPromises()
  })

  it('load failure logs', async () => {
    getJob.mockRejectedValue(new Error('x'))
    getJobGraph.mockResolvedValue({ nodes: [], edges: [] })
    const err = vi.spyOn(console, 'error').mockImplementation(() => {})
    mount(SimulationResults, { global: { stubs } })
    await flushPromises()
    expect(err).toHaveBeenCalled()
    err.mockRestore()
  })

  it('switches to report view with chat', async () => {
    getJob.mockResolvedValue({
      id: 'job1', goal: 'G', tier: 'small',
      result_report: 'body',
      result_chat_log: JSON.stringify([{ role: 'user', content: 'hi' }]),
    })
    getJobGraph.mockResolvedValue({ nodes: [], edges: [] })
    const wrapper = mount(SimulationResults, { global: { stubs } })
    await flushPromises()
    wrapper.findComponent({ name: 'ResultsToolbar' }).vm.$emit('update:viewMode', 'report')
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ChatReplay' }).exists()).toBe(true)
  })

  it('switches to data view', async () => {
    getJob.mockResolvedValue({ id: 'job1', goal: 'G', tier: 'small' })
    getJobGraph.mockResolvedValue({ nodes: [], edges: [] })
    const wrapper = mount(SimulationResults, { global: { stubs } })
    await flushPromises()
    wrapper.findComponent({ name: 'ResultsToolbar' }).vm.$emit('update:viewMode', 'data')
    await flushPromises()
    expect(wrapper.find('.dd').exists()).toBe(true)
  })

  it('graph view with nodes relationships built', async () => {
    getJob.mockResolvedValue({ id: 'job1', goal: 'G', tier: 'small' })
    getJobGraph.mockResolvedValue({
      nodes: [{ uuid: 'a', name: 'A' }, { uuid: 'b', name: 'B' }],
      edges: [{ source_node_uuid: 'a', target_node_uuid: 'b', name: 'knows' }],
    })
    const wrapper = mount(SimulationResults, { global: { stubs } })
    await flushPromises()
    wrapper.findComponent({ name: 'ResultsToolbar' }).vm.$emit('update:viewMode', 'graph')
    await flushPromises()
    expect(wrapper.findComponent({ name: 'GraphVisualization' }).exists()).toBe(true)
  })

  it('cleans up on unmount', async () => {
    getJob.mockResolvedValue({ id: 'job1', goal: 'G', tier: 'small' })
    getJobGraph.mockResolvedValue({ nodes: [], edges: [] })
    const wrapper = mount(SimulationResults, { global: { stubs } })
    await flushPromises()
    // trigger resize
    window.innerWidth = 500
    window.dispatchEvent(new Event('resize'))
    wrapper.unmount()
  })
})
