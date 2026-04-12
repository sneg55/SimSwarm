import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import { useGraphVisualization } from '../useGraphVisualization.js'

function setup(props = {}, emit = vi.fn()) {
  let exposed
  const Comp = {
    setup() {
      exposed = useGraphVisualization({
        nodes: props.nodes || [],
        edges: props.edges || [],
        chatLog: props.chatLog || [],
      }, emit)
      return {}
    },
    template: '<div />',
  }
  const wrapper = mount(Comp)
  return { exposed, emit, wrapper }
}

describe('useGraphVisualization', () => {
  it('initial state', () => {
    const { exposed } = setup()
    expect(exposed.showEdgeLabels.value).toBe(false)
    expect(exposed.layoutName.value).toBe('cose-bilkent')
    expect(exposed.isFullscreen.value).toBe(false)
    expect(exposed.groupBy.value).toBe('type')
    expect(exposed.hiddenTypes.value.size).toBe(0)
    expect(exposed.selectedNode.value).toBe(null)
  })

  it('visibleNodes returns all when under threshold', () => {
    const nodes = Array.from({ length: 10 }, (_, i) => ({
      uuid: `u${i}`, name: `N${i}`, labels: ['Person'], connection_count: i,
    }))
    const { exposed } = setup({ nodes })
    expect(exposed.visibleNodes.value.length).toBe(10)
    expect(exposed.filterBanner.value).toBe('')
  })

  it('visibleNodes caps at NODE_LIMIT when over threshold', () => {
    const nodes = Array.from({ length: 150 }, (_, i) => ({
      uuid: `u${i}`, name: `N${i}`, labels: ['Person'], connection_count: i,
    }))
    const { exposed } = setup({ nodes })
    expect(exposed.visibleNodes.value.length).toBe(50)
    expect(exposed.filterBanner.value).toMatch(/Showing 50 of 150/)
  })

  it('showAllNodes removes the cap', () => {
    const nodes = Array.from({ length: 150 }, (_, i) => ({
      uuid: `u${i}`, name: `N${i}`, labels: ['Person'], connection_count: i,
    }))
    const { exposed } = setup({ nodes })
    exposed.showAllNodes()
    expect(exposed.visibleNodes.value.length).toBe(150)
    expect(exposed.filterBanner.value).toBe('')
  })

  it('entityTypeSummary groups by type', () => {
    const nodes = [
      { uuid: '1', labels: ['Person'] },
      { uuid: '2', labels: ['Person'] },
      { uuid: '3', labels: ['Organization'] },
    ]
    const { exposed } = setup({ nodes })
    expect(exposed.entityTypeSummary.value[0].name).toBe('Person')
    expect(exposed.entityTypeSummary.value[0].count).toBe(2)
  })

  it('toggleType adds and removes', () => {
    const { exposed } = setup()
    exposed.toggleType('Person')
    expect(exposed.hiddenTypes.value.has('Person')).toBe(true)
    exposed.toggleType('Person')
    expect(exposed.hiddenTypes.value.has('Person')).toBe(false)
  })

  it('toggleSentiment adds and removes', () => {
    const { exposed } = setup()
    exposed.toggleSentiment('positive')
    expect(exposed.hiddenSentiments.value.has('positive')).toBe(true)
    exposed.toggleSentiment('positive')
    expect(exposed.hiddenSentiments.value.has('positive')).toBe(false)
  })

  it('showAllTypes and hideAllTypes', () => {
    const nodes = [{ uuid: '1', labels: ['Person'] }, { uuid: '2', labels: ['Org'] }]
    const { exposed } = setup({ nodes })
    exposed.hideAllTypes()
    expect(exposed.hiddenTypes.value.size).toBeGreaterThan(0)
    exposed.showAllTypes()
    expect(exposed.hiddenTypes.value.size).toBe(0)
  })

  it('onNodeClick with data emits node-selected', () => {
    const { exposed, emit } = setup()
    exposed.onNodeClick({ id: 'x', name: 'Alice' })
    expect(exposed.selectedNode.value.name).toBe('Alice')
    expect(emit).toHaveBeenCalledWith('node-selected', 'Alice')
  })

  it('onNodeClick with null clears selection', () => {
    const { exposed } = setup()
    exposed.onNodeClick({ id: 'x', name: 'A' })
    exposed.onNodeClick(null)
    expect(exposed.selectedNode.value).toBe(null)
  })

  it('onNodeHover and onNodeUnhover', async () => {
    vi.useFakeTimers()
    const { exposed } = setup()
    exposed.onNodeHover({ name: 'X' })
    vi.advanceTimersByTime(250)
    expect(exposed.hoveredNode.value?.name).toBe('X')
    exposed.onNodeUnhover()
    expect(exposed.hoveredNode.value).toBe(null)
    vi.useRealTimers()
  })

  it('toggleFullscreen flips', () => {
    const { exposed } = setup()
    exposed.toggleFullscreen()
    expect(exposed.isFullscreen.value).toBe(true)
    exposed.toggleFullscreen()
    expect(exposed.isFullscreen.value).toBe(false)
  })

  it('agentActions filters chatLog by agent_name', () => {
    const chatLog = [
      { agent_name: 'Alice', content: 'a' },
      { agent_name: 'Bob', content: 'b' },
    ]
    const { exposed } = setup({ chatLog })
    exposed.onNodeClick({ id: 'x', name: 'Alice' })
    expect(exposed.agentActions.value.length).toBe(1)
  })

  it('onSearchSelect sets selectedNode and calls canvas.focusNode', () => {
    const nodes = [{ uuid: 'u1', name: 'Alice', labels: ['Person'] }]
    const { exposed, emit } = setup({ nodes })
    exposed.canvasRef.value = { focusNode: vi.fn() }
    exposed.onSearchSelect('u1')
    expect(exposed.canvasRef.value.focusNode).toHaveBeenCalledWith('u1')
    expect(exposed.selectedNode.value.name).toBe('Alice')
    expect(emit).toHaveBeenCalledWith('node-selected', 'Alice')
  })

  it('onRefresh, onZoomFit, onCanvasReady no-op on missing canvas', () => {
    const { exposed } = setup()
    expect(() => exposed.onRefresh()).not.toThrow()
    expect(() => exposed.onZoomFit()).not.toThrow()
    expect(() => exposed.onCanvasReady()).not.toThrow()
  })

  it('onRefresh calls canvas.runLayout', () => {
    const { exposed } = setup()
    exposed.canvasRef.value = { runLayout: vi.fn(), fitToVisibleArea: vi.fn() }
    exposed.onRefresh()
    expect(exposed.canvasRef.value.runLayout).toHaveBeenCalled()
    exposed.onZoomFit()
    expect(exposed.canvasRef.value.fitToVisibleArea).toHaveBeenCalled()
  })

  it('navigateToNode sets selection and calls focusNode', () => {
    const nodes = [{ uuid: 'u1', name: 'Alice', labels: ['Person'] }]
    const { exposed } = setup({ nodes })
    exposed.canvasRef.value = { focusNode: vi.fn() }
    exposed.navigateToNode('u1')
    expect(exposed.canvasRef.value.focusNode).toHaveBeenCalledWith('u1')
    expect(exposed.selectedNode.value.name).toBe('Alice')
  })

  it('onExport triggers canvas export', () => {
    const { exposed } = setup()
    const clickSpy = vi.fn()
    const origCreate = document.createElement.bind(document)
    document.createElement = vi.fn((t) => {
      const el = origCreate(t)
      if (t === 'a') el.click = clickSpy
      return el
    })
    exposed.canvasRef.value = { exportImage: vi.fn(() => 'data:image/png;base64,xxx') }
    exposed.onExport()
    expect(clickSpy).toHaveBeenCalled()
    document.createElement = origCreate
  })

  it('onExport no-ops when exportImage returns null', () => {
    const { exposed } = setup()
    exposed.canvasRef.value = { exportImage: vi.fn(() => null) }
    expect(() => exposed.onExport()).not.toThrow()
  })

  it('onExport no-ops when canvasRef is missing', () => {
    const { exposed } = setup()
    expect(() => exposed.onExport()).not.toThrow()
  })

  it('Escape key exits fullscreen', () => {
    const { exposed } = setup()
    exposed.toggleFullscreen()
    const evt = new KeyboardEvent('keydown', { key: 'Escape' })
    document.dispatchEvent(evt)
    expect(exposed.isFullscreen.value).toBe(false)
  })
})
