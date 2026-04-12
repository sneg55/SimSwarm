import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { useScrollReveal } from '../useScrollReveal.js'

describe('useScrollReveal', () => {
  let observeSpy, disconnectSpy

  beforeEach(() => {
    observeSpy = vi.fn()
    disconnectSpy = vi.fn()
    global.IntersectionObserver = class {
      constructor(cb) { this.cb = cb }
      observe = observeSpy
      unobserve = vi.fn()
      disconnect = disconnectSpy
    }
    global.MutationObserver = class {
      observe = vi.fn()
      disconnect = vi.fn()
    }
  })

  it('observes elements with data-reveal and disconnects on unmount', async () => {
    document.body.innerHTML = '<div data-reveal>Hi</div>'
    const Comp = {
      setup() { useScrollReveal() },
      template: '<div />',
    }
    const wrapper = mount(Comp, { attachTo: document.body })
    await nextTick()
    await new Promise(r => setTimeout(r, 10))
    wrapper.unmount()
    expect(disconnectSpy).toHaveBeenCalled()
  })

  it('runs without data-reveal elements', async () => {
    document.body.innerHTML = '<div>nothing</div>'
    const Comp = {
      setup() { useScrollReveal() },
      template: '<div />',
    }
    const wrapper = mount(Comp, { attachTo: document.body })
    await nextTick()
    wrapper.unmount()
  })
})
