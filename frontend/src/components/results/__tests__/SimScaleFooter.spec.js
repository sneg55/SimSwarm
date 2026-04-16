import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SimScaleFooter from '../SimScaleFooter.vue'

describe('SimScaleFooter', () => {
  it('renders all four stats from scale prop', () => {
    const wrapper = mount(SimScaleFooter, {
      props: { scale: { participants: 10, horizon_days: 30, bloc_count: 2, market_stress: 'none_observed' } },
    })
    expect(wrapper.text()).toContain('10')
    expect(wrapper.text()).toContain('30')
    expect(wrapper.text()).toContain('2')
  })

  it('shows "None" when market_stress is none_observed', () => {
    const wrapper = mount(SimScaleFooter, {
      props: { scale: { participants: 1, horizon_days: 7, bloc_count: 0, market_stress: 'none_observed' } },
    })
    expect(wrapper.text()).toContain('None')
  })

  it('shows "Present" when market_stress is present', () => {
    const wrapper = mount(SimScaleFooter, {
      props: { scale: { participants: 1, horizon_days: 7, bloc_count: 0, market_stress: 'present' } },
    })
    expect(wrapper.text()).toContain('Present')
  })
})
