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

  it('shows member count and rationale keywords when provided', () => {
    const wrapper = mount(StakeholderChip, {
      props: {
        name: 'Opposition bloc',
        stance: 'opposed',
        memberCount: 4,
        rationaleKeywords: ['rates', 'mandate', 'burden'],
      },
    })
    expect(wrapper.text()).toContain('Opposition bloc')
    expect(wrapper.text()).toContain('4 agents')
    expect(wrapper.text()).toContain('rates, mandate, burden')
    expect(wrapper.text()).not.toContain('Opposed')
  })

  it('pluralizes correctly for a single member', () => {
    const wrapper = mount(StakeholderChip, {
      props: { name: 'Neutral bloc', stance: 'neutral', memberCount: 1, rationaleKeywords: [] },
    })
    expect(wrapper.text()).toContain('1 agent')
    expect(wrapper.text()).not.toContain('1 agents')
  })

  it('omits keywords when list is empty', () => {
    const wrapper = mount(StakeholderChip, {
      props: { name: 'Neutral bloc', stance: 'neutral', memberCount: 3, rationaleKeywords: [] },
    })
    const text = wrapper.text()
    expect(text).toContain('3 agents')
    expect(text).not.toMatch(/3 agents · /)
  })
})
