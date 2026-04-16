import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import FindingSlotCard from '../FindingSlotCard.vue'

describe('FindingSlotCard', () => {
  const baseProps = {
    slot: 'industry',
    title: 'Banks aligned on adaptable frameworks',
    body: 'Every private-sector participant converged on "industry-led" language.',
    citation: 'Morgan Stanley · 9 posts',
  }

  it('renders title, body, citation', () => {
    const wrapper = mount(FindingSlotCard, { props: baseProps })
    expect(wrapper.text()).toContain('Banks aligned on adaptable frameworks')
    expect(wrapper.text()).toContain('Every private-sector participant')
    expect(wrapper.text()).toContain('Morgan Stanley · 9 posts')
  })

  it('shows the slot label', () => {
    const wrapper = mount(FindingSlotCard, { props: baseProps })
    expect(wrapper.text().toLowerCase()).toContain('industry')
  })
})
