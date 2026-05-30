import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, nextTick } from 'vue'
import { useTooltipPosition, tooltipTransitionHooks } from '../useTooltipPosition.js'

function mountHook(hasTooltip, preferredPosition, triggerRef) {
  let state
  const Comp = {
    setup() {
      state = useTooltipPosition(hasTooltip, preferredPosition, triggerRef)
      return state
    },
    template: '<div />',
  }
  const wrapper = mount(Comp, { attachTo: document.body })
  return { wrapper, get state() { return state } }
}

describe('useTooltipPosition', () => {
  it('returns initial state', () => {
    const hasTooltip = ref(true)
    const triggerRef = ref(null)
    const { wrapper, state } = mountHook(hasTooltip, 'top', triggerRef)
    expect(state.visible.value).toBe(false)
    expect(state.actualPosition.value).toBe('top')
    wrapper.unmount()
  })

  it('show/hide with timers', async () => {
    vi.useFakeTimers()
    const hasTooltip = ref(true)
    const triggerRef = ref(null)
    const { wrapper, state } = mountHook(hasTooltip, 'top', triggerRef)
    state.onTriggerEnter()
    vi.advanceTimersByTime(250)
    expect(state.visible.value).toBe(true)
    state.onTriggerLeave()
    vi.advanceTimersByTime(200)
    expect(state.visible.value).toBe(false)
    wrapper.unmount()
    vi.useRealTimers()
  })

  it('toggleTooltip flips visibility', () => {
    const hasTooltip = ref(true)
    const { wrapper, state } = mountHook(hasTooltip, 'top', ref(null))
    state.toggleTooltip()
    expect(state.visible.value).toBe(true)
    state.toggleTooltip()
    expect(state.visible.value).toBe(false)
    wrapper.unmount()
  })

  it('Escape key closes tooltip', () => {
    const hasTooltip = ref(true)
    const { wrapper, state } = mountHook(hasTooltip, 'top', ref(null))
    state.visible.value = true
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(state.visible.value).toBe(false)
    wrapper.unmount()
  })

  it('onPanelEnter clears timers, onPanelLeave hides', () => {
    vi.useFakeTimers()
    const hasTooltip = ref(true)
    const { wrapper, state } = mountHook(hasTooltip, 'top', ref(null))
    state.visible.value = true
    state.onPanelEnter()
    state.onPanelLeave()
    vi.advanceTimersByTime(200)
    expect(state.visible.value).toBe(false)
    wrapper.unmount()
    vi.useRealTimers()
  })

  it('positionPanel runs with trigger and panel refs', async () => {
    vi.useFakeTimers()
    const hasTooltip = ref(true)
    const triggerRef = ref({
      getBoundingClientRect: () => ({ top: 100, left: 100, right: 200, bottom: 120, width: 100, height: 20 }),
    })
    const { wrapper, state } = mountHook(hasTooltip, 'top', triggerRef)
    state.panelRef.value = {
      getBoundingClientRect: () => ({ top: 0, left: 0, right: 150, bottom: 60, width: 150, height: 60 }),
    }
    state.onTriggerEnter()
    vi.advanceTimersByTime(250)
    await nextTick()
    expect(state.visible.value).toBe(true)
    wrapper.unmount()
    vi.useRealTimers()
  })

  it('click outside visible panel closes it', () => {
    const hasTooltip = ref(true)
    const { wrapper, state } = mountHook(hasTooltip, 'top', ref(null))
    state.visible.value = true
    state.panelRef.value = document.createElement('div')
    const outside = document.createElement('span')
    document.body.appendChild(outside)
    outside.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    wrapper.unmount()
  })
})

describe('tooltipTransitionHooks', () => {
  it('returns before/enter/leave hooks', () => {
    const hooks = tooltipTransitionHooks()
    const el = document.createElement('div')
    hooks.onBeforeEnter(el)
    const done = vi.fn()
    hooks.onEnter(el, done)
    hooks.onLeave(el, done)
    expect(typeof hooks.onBeforeEnter).toBe('function')
  })
})
