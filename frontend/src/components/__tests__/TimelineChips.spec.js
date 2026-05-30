import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import TimelineChips from '../wizard/TimelineChips.vue'

describe('TimelineChips', () => {
  it('renders all 6 preset chips', () => {
    const wrapper = mount(TimelineChips)
    const buttons = wrapper.findAll('button')
    expect(buttons.length).toBe(6)
    expect(buttons[0].text()).toBe('1 day')
    expect(buttons[5].text()).toBe('1 year')
  })

  it('emits update:modelValue when a chip is clicked', async () => {
    const wrapper = mount(TimelineChips)
    await wrapper.findAll('button')[2].trigger('click')
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')[0]).toEqual([30])
  })

  it('highlights the selected chip', () => {
    const wrapper = mount(TimelineChips, { props: { modelValue: 7 } })
    const buttons = wrapper.findAll('button')
    expect(buttons[1].classes()).toContain('border-ocean-cyan')
  })

  it('deselects when clicking the active chip', async () => {
    const wrapper = mount(TimelineChips, { props: { modelValue: 30 } })
    await wrapper.findAll('button')[2].trigger('click')
    expect(wrapper.emitted('update:modelValue')[0]).toEqual([null])
  })
})
