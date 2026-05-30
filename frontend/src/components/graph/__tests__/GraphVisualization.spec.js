import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('@dicebear/core', () => ({
  createAvatar: vi.fn(() => ({ toDataUri: () => 'data:image/svg+xml,test' })),
}))
vi.mock('@dicebear/collection', () => ({ personas: {} }))

import GraphVisualization from '../GraphVisualization.vue'

beforeEach(() => {
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
    clearRect: vi.fn(), beginPath: vi.fn(), moveTo: vi.fn(), lineTo: vi.fn(),
    stroke: vi.fn(), arc: vi.fn(), fill: vi.fn(), fillText: vi.fn(),
    setTransform: vi.fn(), save: vi.fn(), restore: vi.fn(),
    translate: vi.fn(), scale: vi.fn(),
    createRadialGradient: vi.fn(() => ({ addColorStop: vi.fn() })),
  }))
  global.requestAnimationFrame = vi.fn(() => 1)
  global.cancelAnimationFrame = vi.fn()
})

describe('GraphVisualization', () => {
  it('shows loading state', () => {
    const wrapper = mount(GraphVisualization, { props: { loading: true } })
    expect(wrapper.text()).toContain('Loading graph')
  })

  it('shows error state', () => {
    const wrapper = mount(GraphVisualization, { props: { error: 'Failed' } })
    expect(wrapper.text()).toContain('Failed')
  })

  it('mounts with empty data', async () => {
    const wrapper = mount(GraphVisualization, { props: { nodes: [], edges: [] }, attachTo: document.body })
    await flushPromises()
    expect(wrapper.find('canvas').exists()).toBe(true)
    wrapper.unmount()
  })

  it('renders with nodes and edges', async () => {
    const wrapper = mount(GraphVisualization, {
      props: {
        nodes: [
          { uuid: 'a', name: 'Alice', labels: ['Person'], sentiment: 0.5 },
          { uuid: 'b', name: 'Bob', labels: ['Person'] },
        ],
        edges: [{ source_node_uuid: 'a', target_node_uuid: 'b', name: 'KNOWS' }],
      },
      attachTo: document.body,
    })
    await flushPromises()
    expect(wrapper.find('canvas').exists()).toBe(true)
    wrapper.unmount()
  })

  it('exposes exportImage via defineExpose', async () => {
    const wrapper = mount(GraphVisualization, { props: { nodes: [], edges: [] }, attachTo: document.body })
    await flushPromises()
    expect(typeof wrapper.vm.exportImage).toBe('function')
    wrapper.unmount()
  })
})
