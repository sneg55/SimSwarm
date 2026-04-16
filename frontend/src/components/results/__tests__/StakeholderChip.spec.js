import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StakeholderChip from '../StakeholderChip.vue'

describe('StakeholderChip', () => {
  it('renders name and stance', () => {
    const wrapper = mount(StakeholderChip, {
      props: { name: 'Industry bloc', stance: 'opposed' },
    })
    expect(wrapper.text()).toContain('Industry bloc')
    expect(wrapper.text()).toContain('Opposed')
  })

  it('applies opposed style when stance is opposed', () => {
    const wrapper = mount(StakeholderChip, {
      props: { name: 'X', stance: 'opposed' },
    })
    expect(wrapper.attributes('class')).toMatch(/coral|amber/)
  })

  it('applies supports style when stance is supports', () => {
    const wrapper = mount(StakeholderChip, {
      props: { name: 'X', stance: 'supports' },
    })
    expect(wrapper.attributes('class')).toMatch(/ocean|glow/)
  })
})
