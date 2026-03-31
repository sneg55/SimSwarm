import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import GoalQualityMeter from '../wizard/GoalQualityMeter.vue'

describe('GoalQualityMeter', () => {
  it('shows "Not started" for empty goal', () => {
    const wrapper = mount(GoalQualityMeter, { props: { goal: '' } })
    expect(wrapper.text()).toContain('Not started')
  })

  it('does not show success message for empty goal', () => {
    const wrapper = mount(GoalQualityMeter, { props: { goal: '' } })
    expect(wrapper.text()).not.toContain('Goal looks great')
  })

  it('shows "Weak" for a very short goal', () => {
    const wrapper = mount(GoalQualityMeter, { props: { goal: 'What happens next?' } })
    expect(wrapper.text()).toContain('Weak')
  })

  it('shows tips when goal is short and missing criteria', () => {
    const wrapper = mount(GoalQualityMeter, { props: { goal: 'What happens next?' } })
    expect(wrapper.text()).toContain('Tip:')
  })

  it('shows "Fair" for a goal meeting 2–3 criteria', () => {
    // Has: question mark, stakeholder, causal (how will) — score 3
    const wrapper = mount(GoalQualityMeter, { props: { goal: 'How will retail investors react?' } })
    expect(wrapper.text()).toContain('Fair')
  })

  it('shows "Strong" for a high-quality goal meeting 4–5 criteria', () => {
    const goal =
      'How will retail investors and institutional traders react to the Fed rate hike over the next 30 days? ' +
      'What price narratives and sentiment shifts should we expect to emerge?'
    const wrapper = mount(GoalQualityMeter, { props: { goal } })
    expect(wrapper.text()).toContain('Strong')
  })

  it('shows success message for a high-quality goal', () => {
    const goal =
      'How will retail investors and institutional traders react to the Fed rate hike over the next 30 days? ' +
      'What price narratives and sentiment shifts should we expect to emerge?'
    const wrapper = mount(GoalQualityMeter, { props: { goal } })
    expect(wrapper.text()).toContain('Goal looks great')
  })

  it('does not count common words as causal language', () => {
    // 'change' and 'form' were removed from CAUSAL_RE — should not earn causal point
    const goal =
      'What is the change in form submission rates? How will this affect the customer over the next quarter?'
    const wrapper = mount(GoalQualityMeter, { props: { goal } })
    // 'affect' is still in CAUSAL_RE, so this will score causal — verify 'effect' alone does not
    const noAffect = 'What is the change in form submission rates over the next quarter for customers?'
    const wrapper2 = mount(GoalQualityMeter, { props: { goal: noAffect } })
    // Should not show success (causal point is absent, only timeframe+stakeholder = 2 = Fair)
    expect(wrapper2.text()).not.toContain('Strong')
    expect(wrapper2.text()).not.toContain('Goal looks great')
  })

  it('awards the causal point only for explicit causal verbs', () => {
    const causalGoal = 'How will regulators respond to the new policy over the next month?'
    const wrapper = mount(GoalQualityMeter, { props: { goal: causalGoal } })
    // Has: causal (how will + respond), stakeholder (regulator), timeframe, question mark — score >= 4
    expect(wrapper.text()).toContain('Strong')
  })
})
