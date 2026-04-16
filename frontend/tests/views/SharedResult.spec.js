import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { token: 'abc' } }),
}))

vi.mock('../../src/composables/useScrollReveal.js', () => ({
  useScrollReveal: () => {},
}))

import SharedResult from '../../src/views/SharedResult.vue'

const stubs = {
  'router-link': { template: '<a><slot /></a>' },
  ResultsToolbar: {
    name: 'ResultsToolbar',
    props: ['title', 'viewMode', 'showToggle', 'backLink', 'backLabel'],
    emits: ['update:viewMode'],
    template: '<div class="toolbar">{{ title }}</div>',
  },
  ReportToc: true,
  ReportViewer: { props: ['content'], template: '<div class="rv">{{ content }}</div>' },
  ChatReplay: true,
  GraphVisualization: { name: 'GraphVisualization', template: '<div class="gv" />' },
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

function mockFetchOnce(body, ok = true) {
  global.fetch = vi.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 404,
    json: () => Promise.resolve(body),
  })
}

describe('SharedResult.vue', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('shows loading then error on failed fetch', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false, status: 404,
      json: () => Promise.resolve({ detail: 'gone' }),
    })
    const wrapper = mount(SharedResult, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('Result not found')
    expect(wrapper.text()).toContain('gone')
  })

  it('handles fetch rejecting', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('netfail'))
    const wrapper = mount(SharedResult, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('Result not found')
  })

  it('handles fetch error with non-JSON body', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false, status: 500,
      json: () => Promise.reject(new Error('not json')),
    })
    const wrapper = mount(SharedResult, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('Not found (500)')
  })

  it('renders story view with structured report data', async () => {
    mockFetchOnce({
      title: 'Shared sim',
      tier: 'small',
      created_at: '2026-01-01T00:00:00Z',
      completed_at: '2026-01-02T00:00:00Z',
      report: '## Section A\nContent',
      result_structured: {
        verdict: 'Industry will adapt within 18 months.',
        stakeholder_positions: [{ name: 'Banks', stance: 'supports' }],
        sim_scale: { participants: 12, horizon_days: 90, bloc_count: 3, market_stress: 'present' },
        findings: [
          { slot: 'industry', title: 'Banks aligned', body: 'Body text', citation: 'Cite' },
        ],
      },
    })
    const wrapper = mount(SharedResult, { global: { stubs } })
    await flushPromises()
    // Toolbar still shows the title
    expect(wrapper.text()).toContain('Shared sim')
    // Q+A hero stub renders question + verdict
    expect(wrapper.findComponent({ name: 'QuestionAnswerHero' }).exists()).toBe(true)
    expect(wrapper.text()).toContain('Industry will adapt within 18 months.')
    // Finding deck rendered
    expect(wrapper.findComponent({ name: 'FindingSlotCard' }).exists()).toBe(true)
    expect(wrapper.text()).toContain('What the simulation surfaced')
    // Scale footer rendered
    expect(wrapper.findComponent({ name: 'SimScaleFooter' }).exists()).toBe(true)
  })

  it('renders story view without structured (plain report)', async () => {
    mockFetchOnce({
      title: 'Plain',
      tier: 'medium',
      report: '# Report',
    })
    const wrapper = mount(SharedResult, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('Plain')
  })

  it('toggles to report view mode and shows headings as toc', async () => {
    mockFetchOnce({
      title: 'Plain',
      tier: 'medium',
      report: '## H1\n## **H2**',
    })
    const wrapper = mount(SharedResult, { global: { stubs } })
    await flushPromises()
    wrapper.findComponent({ name: 'ResultsToolbar' }).vm.$emit('update:viewMode', 'report')
    await flushPromises()
    expect(wrapper.html()).toContain('rv')
  })

  it('toggles to graph view with nodes/edges', async () => {
    mockFetchOnce({
      title: 'G', tier: 'small',
      graph: { nodes: [{ uuid: 'n1', name: 'N1' }], edges: [{ source_node_uuid: 'n1', target_node_uuid: 'n1' }] },
    })
    const wrapper = mount(SharedResult, { global: { stubs } })
    await flushPromises()
    wrapper.findComponent({ name: 'ResultsToolbar' }).vm.$emit('update:viewMode', 'graph')
    await flushPromises()
    expect(wrapper.findComponent({ name: 'GraphVisualization' }).exists()).toBe(true)
  })

  it('graph view handles nodes-only (no edges)', async () => {
    mockFetchOnce({
      title: 'G', tier: 'small',
      graph: { nodes: [{ uuid: 'n1', name: 'N1' }] },
    })
    const wrapper = mount(SharedResult, { global: { stubs } })
    await flushPromises()
    wrapper.findComponent({ name: 'ResultsToolbar' }).vm.$emit('update:viewMode', 'graph')
    await flushPromises()
    expect(wrapper.findComponent({ name: 'GraphVisualization' }).exists()).toBe(true)
  })
})
