import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import HeroSwarm from '../HeroSwarm.vue'

beforeEach(() => {
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
    clearRect: vi.fn(), beginPath: vi.fn(), moveTo: vi.fn(), lineTo: vi.fn(),
    stroke: vi.fn(), arc: vi.fn(), fill: vi.fn(), fillText: vi.fn(),
    setTransform: vi.fn(), save: vi.fn(), restore: vi.fn(),
    createRadialGradient: vi.fn(() => ({ addColorStop: vi.fn() })),
  }))
  global.requestAnimationFrame = vi.fn(() => 1)
  global.cancelAnimationFrame = vi.fn()
  window.matchMedia = window.matchMedia || vi.fn(() => ({ matches: false, addListener: vi.fn(), removeListener: vi.fn() }))
})

describe('HeroSwarm', () => {
  it('mounts and renders canvas', async () => {
    const wrapper = mount(HeroSwarm, { attachTo: document.body })
    await flushPromises()
    expect(wrapper.find('canvas').exists()).toBe(true)
    wrapper.unmount()
  })

  it('respects reduced motion preference', async () => {
    window.matchMedia = vi.fn(() => ({ matches: true, addListener: vi.fn(), removeListener: vi.fn() }))
    const wrapper = mount(HeroSwarm, { attachTo: document.body })
    await flushPromises()
    wrapper.unmount()
  })

  it('handles mouse events and resize without error', async () => {
    const wrapper = mount(HeroSwarm, { attachTo: document.body })
    await flushPromises()
    const container = wrapper.find('div').element
    container.parentElement.dispatchEvent(new MouseEvent('mousemove', { clientX: 50, clientY: 50 }))
    container.parentElement.dispatchEvent(new MouseEvent('mouseleave'))
    window.dispatchEvent(new Event('resize'))
    wrapper.unmount()
  })
})
