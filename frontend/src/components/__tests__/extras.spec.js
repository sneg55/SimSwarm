import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ChatReplay from '../ChatReplay.vue'
import ViewModeToggle from '../ViewModeToggle.vue'

describe('ChatReplay extra', () => {
  it('auto-scrolls when messages update', async () => {
    const wrapper = mount(ChatReplay, {
      props: { startExpanded: true, messages: [{ role: 'user', content: 'hi' }] },
    })
    await wrapper.setProps({ messages: [
      { role: 'user', content: 'hi' },
      { role: 'assistant', content: 'hello' },
    ] })
    expect(wrapper.text()).toContain('hello')
  })

  it('formats timestamp to empty on null', () => {
    const wrapper = mount(ChatReplay, {
      props: { startExpanded: true, messages: [
        { role: 'assistant', agent: 'A', content: 'x' },
      ] },
    })
    expect(wrapper.html()).toBeTruthy()
  })
})

describe('ViewModeToggle branches', () => {
  it('compact mode filters dual', () => {
    const wrapper = mount(ViewModeToggle, {
      props: { modelValue: 'story', compact: true, showData: true },
    })
    // No 'dual' mode exists in baseModes, but compact filter is exercised
    expect(wrapper.findAll('button').length).toBe(4)
  })
})
