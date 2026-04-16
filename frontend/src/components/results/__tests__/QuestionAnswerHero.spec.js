import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import QuestionAnswerHero from '../QuestionAnswerHero.vue'

describe('QuestionAnswerHero', () => {
  const baseProps = {
    question: 'Will proposal X pass?',
    verdict: 'Unlikely — 3 of 5 blocs opposed.',
    stakeholderPositions: [
      { name: 'Industry bloc', stance: 'opposed', members: ['A'], member_count: 1, rationale_keywords: [] },
      { name: 'Support bloc', stance: 'supports', members: ['B'], member_count: 1, rationale_keywords: [] },
    ],
  }

  it('renders the question prominently', () => {
    const wrapper = mount(QuestionAnswerHero, { props: baseProps })
    expect(wrapper.text()).toContain('Will proposal X pass?')
  })

  it('renders the verdict', () => {
    const wrapper = mount(QuestionAnswerHero, { props: baseProps })
    expect(wrapper.text()).toContain('Unlikely — 3 of 5 blocs opposed.')
  })

  it('renders a chip per stakeholder position', () => {
    const wrapper = mount(QuestionAnswerHero, { props: baseProps })
    const chips = wrapper.findAllComponents({ name: 'StakeholderChip' })
    expect(chips).toHaveLength(2)
  })

  it('shows empty state when verdict is missing', () => {
    const wrapper = mount(QuestionAnswerHero, {
      props: { ...baseProps, verdict: '' },
    })
    expect(wrapper.text()).toContain('Verdict pending')
  })
})
