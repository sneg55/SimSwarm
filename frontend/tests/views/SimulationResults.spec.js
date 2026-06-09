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
  // SimulationResults mounts useTimelineSimData, which calls getSimData when
  // job.sim_data_available is set. Provide a resolving stub so the timeline
  // load path runs instead of throwing on a missing mock export.
  getSimData: vi.fn().mockResolvedValue({ files: {} }),
}))

import SimulationResults from '../../src/views/SimulationResults.vue'
import { getJob, getJobGraph } from '../../src/api/jobs.js'

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
  DataDashboard: { props: ['jobId'], template: '<div class="dd">{{ jobId }}</div>' },
  QuestionAnswerHero: {
    name: 'QuestionAnswerHero',
    props: ['question', 'verdict', 'stakeholderPositions'],
    template: '<div class="qa-hero">{{ question }}|{{ verdict }}</div>',
  },
  FindingSlotCard: {
    name: 'FindingSlotCard',
    props: ['slotName', 'title', 'body', 'citation'],
    template: '<div class="slot-card">{{ slotName }}|{{ title }}</div>',
  },
  SimScaleFooter: {
    name: 'SimScaleFooter',
    props: ['scale'],
    template: '<div class="scale-footer" />',
  },
}

describe('SimulationResults.vue', () => {
  beforeEach(() => {
    getJob.mockReset()
    getJobGraph.mockReset()
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
        verdict: 'Yes, with caveats.',
        stakeholder_positions: [{ name: 'Banks', stance: 'supports' }],
        sim_scale: { participants: 12, horizon_days: 90, bloc_count: 3, market_stress: 'present' },
        findings: [
          { slot: 'industry', title: 'Banks aligned', body: 'Body text', citation: 'Cite' },
        ],
      },
      sim_data_available: false,
    })
    getJobGraph.mockResolvedValue({ nodes: [{ uuid: 'a', name: 'A' }], edges: [] })
    const wrapper = mount(SimulationResults, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('Will X?')
    expect(wrapper.findComponent({ name: 'QuestionAnswerHero' }).exists()).toBe(true)
    expect(wrapper.text()).toContain('Yes, with caveats.')
    expect(wrapper.findComponent({ name: 'FindingSlotCard' }).exists()).toBe(true)
    expect(wrapper.text()).toContain('What the simulation surfaced')
    expect(wrapper.findComponent({ name: 'SimScaleFooter' }).exists()).toBe(true)
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

  it('flags sim_data_available on the toolbar', async () => {
    getJob.mockResolvedValue({
      id: 'job1', goal: 'G', tier: 'medium', result_report: 'R',
      sim_data_available: true,
    })
    getJobGraph.mockResolvedValue({ nodes: [], edges: [] })
    const wrapper = mount(SimulationResults, { global: { stubs } })
    await flushPromises()
    const toolbar = wrapper.findComponent({ name: 'ResultsToolbar' })
    expect(toolbar.props('showData')).toBe(true)
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
