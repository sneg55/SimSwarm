import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import TimelineChips from '../TimelineChips.vue'

describe('TimelineChips', () => {
  it('preselects 30-day chip when modelValue is null', () => {
    const wrapper = mount(TimelineChips, { props: { modelValue: null } })
    // Component should emit update:modelValue=30 on mount
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')[0]).toEqual([30])
  })

  it('does not override an explicit modelValue', () => {
    const wrapper = mount(TimelineChips, { props: { modelValue: 7 } })
    // With an explicit value, no default should be emitted
    const updates = wrapper.emitted('update:modelValue') || []
    expect(updates.length).toBe(0)
  })
})
