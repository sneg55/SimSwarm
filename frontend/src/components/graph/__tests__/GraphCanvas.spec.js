import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import GraphCanvas from '../GraphCanvas.vue'

beforeEach(() => {
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
    clearRect: vi.fn(), beginPath: vi.fn(), moveTo: vi.fn(), lineTo: vi.fn(),
    stroke: vi.fn(), arc: vi.fn(), fill: vi.fn(), fillText: vi.fn(),
    setTransform: vi.fn(), save: vi.fn(), restore: vi.fn(),
    translate: vi.fn(), scale: vi.fn(),
    createRadialGradient: vi.fn(() => ({ addColorStop: vi.fn() })),
  }))
  HTMLCanvasElement.prototype.toDataURL = vi.fn(() => 'data:image/png;base64,test')
  global.requestAnimationFrame = vi.fn(() => 1)
  global.cancelAnimationFrame = vi.fn()
})

describe('GraphCanvas', () => {
  const nodes = [
    { uuid: 'u1', name: 'Alice', labels: ['Person'], sentiment: 0.5, connection_count: 3 },
    { uuid: 'u2', name: 'Bob', labels: ['Person'], sentiment: -0.3, connection_count: 2 },
    { uuid: 'u3', name: 'Acme', labels: ['Organization'], sentiment: 0, connection_count: 5 },
  ]
  const edges = [
    { source_node_uuid: 'u1', target_node_uuid: 'u2', name: 'KNOWS' },
    { source_node_uuid: 'u2', target_node_uuid: 'u3', fact: 'works at' },
  ]

  it('mounts and unmounts without error', async () => {
    const wrapper = mount(GraphCanvas, {
      props: { nodes, edges },
      attachTo: document.body,
    })
    await flushPromises()
    expect(wrapper.find('canvas').exists()).toBe(true)
    wrapper.unmount()
  })

  it('exposes exportImage, runLayout, focusNode, getCy, fitToVisibleArea', async () => {
    const wrapper = mount(GraphCanvas, {
      props: { nodes, edges },
      attachTo: document.body,
    })
    await flushPromises()
    expect(typeof wrapper.vm.exportImage).toBe('function')
    expect(typeof wrapper.vm.runLayout).toBe('function')
    expect(typeof wrapper.vm.focusNode).toBe('function')
    expect(typeof wrapper.vm.getCy).toBe('function')
    expect(typeof wrapper.vm.fitToVisibleArea).toBe('function')
    expect(wrapper.vm.getCy()).toBeNull()
    // Execute methods
    wrapper.vm.runLayout()
    wrapper.vm.focusNode('u1')
    wrapper.vm.fitToVisibleArea()
    const img = wrapper.vm.exportImage()
    expect(img).toMatch(/data:image/)
    wrapper.unmount()
  })

  it('handles empty nodes', async () => {
    const wrapper = mount(GraphCanvas, { props: { nodes: [], edges: [] }, attachTo: document.body })
    await flushPromises()
    expect(wrapper.find('canvas').exists()).toBe(true)
    wrapper.unmount()
  })

  it('handles hiddenTypes and hiddenSentiments props', async () => {
    const wrapper = mount(GraphCanvas, {
      props: {
        nodes, edges,
        hiddenTypes: new Set(['Person']),
        hiddenSentiments: new Set(['neutral']),
      },
      attachTo: document.body,
    })
    await flushPromises()
    wrapper.unmount()
  })

  it('canvas events do not throw', async () => {
    const wrapper = mount(GraphCanvas, { props: { nodes, edges }, attachTo: document.body })
    await flushPromises()
    const canvas = wrapper.find('canvas').element
    canvas.getBoundingClientRect = () => ({ left: 0, top: 0, width: 800, height: 600 })
    canvas.dispatchEvent(new MouseEvent('mousemove', { clientX: 10, clientY: 20 }))
    canvas.dispatchEvent(new MouseEvent('mousedown', { button: 0, clientX: 15, clientY: 25 }))
    canvas.dispatchEvent(new MouseEvent('mousemove', { clientX: 50, clientY: 60 }))
    canvas.dispatchEvent(new MouseEvent('mouseup'))
    canvas.dispatchEvent(new WheelEvent('wheel', { deltaY: -100, clientX: 100, clientY: 100 }))
    canvas.dispatchEvent(new MouseEvent('mouseleave'))
    wrapper.unmount()
  })

  it('reacts to props.nodes change', async () => {
    const wrapper = mount(GraphCanvas, { props: { nodes: [], edges: [] }, attachTo: document.body })
    await flushPromises()
    await wrapper.setProps({ nodes, edges })
    await flushPromises()
    wrapper.unmount()
  })

  it('reacts to selectedNodeId change', async () => {
    const wrapper = mount(GraphCanvas, { props: { nodes, edges }, attachTo: document.body })
    await flushPromises()
    await wrapper.setProps({ selectedNodeId: 'u1' })
    await wrapper.setProps({ selectedNodeId: null })
    wrapper.unmount()
  })

  it('reacts to panelOpen change', async () => {
    const wrapper = mount(GraphCanvas, { props: { nodes, edges }, attachTo: document.body })
    await flushPromises()
    await wrapper.setProps({ panelOpen: true })
    wrapper.unmount()
  })
})
