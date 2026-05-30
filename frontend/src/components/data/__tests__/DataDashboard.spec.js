import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('../../../api/jobs.js', () => ({
  getSimData: vi.fn(),
}))

import { getSimData } from '../../../api/jobs.js'
import DataDashboard from '../DataDashboard.vue'

beforeEach(() => {
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
    clearRect: vi.fn(), beginPath: vi.fn(), moveTo: vi.fn(), lineTo: vi.fn(),
    stroke: vi.fn(), arc: vi.fn(), fill: vi.fn(), fillText: vi.fn(),
    setTransform: vi.fn(), fillRect: vi.fn(),
  }))
  global.requestAnimationFrame = vi.fn(() => 1)
  global.cancelAnimationFrame = vi.fn()
})

describe('DataDashboard', () => {
  it('renders loading state initially', () => {
    getSimData.mockReturnValue(new Promise(() => {}))
    const wrapper = mount(DataDashboard, { props: { jobId: 123 } })
    expect(wrapper.text()).toContain('Loading simulation data')
  })

  it('renders error state when API throws', async () => {
    getSimData.mockRejectedValue(new Error('boom'))
    const wrapper = mount(DataDashboard, { props: { jobId: 123 } })
    await flushPromises()
    expect(wrapper.text()).toContain('Simulation data not available')
  })

  it('renders dashboard with fetched data', async () => {
    getSimData.mockResolvedValue({ files: {
      'market_curves.json': '/m.json',
      'agent_trajectories.json': '/a.json',
      'engagement_summary.json': '/e.json',
      'top_posts.json': '/t.json',
      'social_graph.json': '/s.json',
      'trades.json': '/tr.json',
      'profiles.json': '/p.json',
    } })
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve([]) })
    const wrapper = mount(DataDashboard, { props: { jobId: 1 } })
    await flushPromises()
    // Renders without error state
    expect(wrapper.text()).not.toContain('not available')
  })

  it('handles non-ok fetch response gracefully', async () => {
    getSimData.mockResolvedValue({ files: { 'market_curves.json': '/m.json' } })
    global.fetch = vi.fn().mockResolvedValue({ ok: false })
    const wrapper = mount(DataDashboard, { props: { jobId: 1 } })
    await flushPromises()
    expect(wrapper.html()).toBeTruthy()
  })
})
