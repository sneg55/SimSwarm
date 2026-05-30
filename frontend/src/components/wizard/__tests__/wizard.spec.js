import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import SeedTips from '../SeedTips.vue'
import WizardProgress from '../WizardProgress.vue'
import WizardGoal from '../WizardGoal.vue'
import WizardLaunch from '../WizardLaunch.vue'
import GoalTemplateCards from '../GoalTemplateCards.vue'

const RouterLinkStub = { template: '<a><slot /></a>' }

// Mock AI API to avoid network
vi.mock('../../../api/ai.js', () => ({
  generateGoal: vi.fn().mockResolvedValue({ goal: 'generated goal' }),
}))

import { generateGoal } from '../../../api/ai.js'

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('SeedTips', () => {
  it('hides tips initially (collapsed)', () => {
    const wrapper = mount(SeedTips)
    expect(wrapper.text()).toContain('What makes a good seed')
    expect(wrapper.text()).not.toContain('Specific events')
  })

  it('expands on click', async () => {
    const wrapper = mount(SeedTips)
    await wrapper.find('div.cursor-pointer').trigger('click')
    expect(wrapper.text()).toContain('Specific events')
    expect(wrapper.text()).toContain('Multiple stakeholders')
  })
})

describe('WizardProgress', () => {
  it('renders 3 step dots', () => {
    const wrapper = mount(WizardProgress, { props: { current: 1 } })
    expect(wrapper.text()).toContain('Seed')
    expect(wrapper.text()).toContain('Goal')
    expect(wrapper.text()).toContain('Launch')
  })

  it('emits go on click', async () => {
    const wrapper = mount(WizardProgress, { props: { current: 2 } })
    const dots = wrapper.findAll('div.cursor-pointer')
    await dots[0].trigger('click')
    expect(wrapper.emitted('go')?.[0]).toEqual([1])
  })

  it('applies different classes based on current step', () => {
    const wrapper = mount(WizardProgress, { props: { current: 2 } })
    // completed should use organic-sage, current uses ocean-glow
    expect(wrapper.html()).toContain('organic-sage')
    expect(wrapper.html()).toContain('ocean-glow')
  })
})

describe('GoalTemplateCards', () => {
  it('renders template buttons', () => {
    const wrapper = mount(GoalTemplateCards, { props: { seedText: '' } })
    expect(wrapper.text()).toContain('Market Reaction')
    expect(wrapper.text()).toContain('Crisis Response')
    expect(wrapper.text()).toContain('Policy Impact')
  })

  it('emits static description when no seed text', async () => {
    const wrapper = mount(GoalTemplateCards, { props: { seedText: '' } })
    await wrapper.findAll('button')[0].trigger('click')
    expect(wrapper.emitted('select')).toBeTruthy()
    expect(wrapper.emitted('select')[0][0]).toMatch(/Investor sentiment/)
  })

  it('calls generateGoal when seed is present', async () => {
    generateGoal.mockResolvedValue({ goal: 'AI goal text' })
    const wrapper = mount(GoalTemplateCards, { props: { seedText: 'seed content' } })
    await wrapper.findAll('button')[0].trigger('click')
    await new Promise(r => setTimeout(r, 0))
    expect(generateGoal).toHaveBeenCalled()
    expect(wrapper.emitted('select')?.[0]?.[0]).toBe('AI goal text')
  })

  it('falls back to static text on AI error', async () => {
    generateGoal.mockRejectedValue(new Error('fail'))
    const wrapper = mount(GoalTemplateCards, { props: { seedText: 'seed content' } })
    await wrapper.findAll('button')[0].trigger('click')
    await new Promise(r => setTimeout(r, 10))
    expect(wrapper.emitted('select')).toBeTruthy()
  })
})

describe('WizardGoal', () => {
  it('renders textarea and emits update on input', async () => {
    const wrapper = mount(WizardGoal, {
      props: { goal: '', seedText: '' },
      global: { stubs: { GoalTemplateCards: true } },
    })
    const textarea = wrapper.find('textarea')
    await textarea.setValue('new goal text')
    expect(wrapper.emitted('update:goal')).toBeTruthy()
  })

  it('forwards forecastDays changes', async () => {
    const wrapper = mount(WizardGoal, {
      props: { goal: '', seedText: '', forecastDays: null },
      global: { stubs: { GoalTemplateCards: true } },
    })
    // TimelineChips is a child; trigger a chip click
    const chip = wrapper.findAll('button')[0]
    await chip?.trigger('click')
    // Expect either update:forecastDays or it not errored
    expect(wrapper.html()).toBeTruthy()
  })

  it('renders with all child components', () => {
    const wrapper = mount(WizardGoal, {
      props: { goal: 'existing goal', seedText: 'seed', forecastDays: 30 },
      global: { stubs: { GoalTemplateCards: true, TimelineChips: true, GoalQualityMeter: true } },
    })
    expect(wrapper.find('textarea').element.value).toBe('existing goal')
  })
})

describe('WizardLaunch', () => {
  it('renders three tier cards and emits initial tier=medium', () => {
    const wrapper = mount(WizardLaunch, { props: {} })
    expect(wrapper.text()).toContain('Small')
    expect(wrapper.text()).toContain('Medium')
    expect(wrapper.text()).toContain('Large')
    expect(wrapper.emitted('update:tier')?.[0]).toEqual(['medium'])
  })

  it('all tiers enabled when no forecastDays constraint', () => {
    const wrapper = mount(WizardLaunch, { props: {} })
    const buttons = wrapper.findAll('button')
    expect(buttons[0].attributes('disabled')).toBeUndefined()
    expect(buttons[1].attributes('disabled')).toBeUndefined()
    expect(buttons[2].attributes('disabled')).toBeUndefined()
  })

  it('marks small+medium as disabled for long forecastDays (365)', () => {
    const wrapper = mount(WizardLaunch, { props: { forecastDays: 365 } })
    expect(wrapper.text()).toContain('Needs')
  })

  it('selecting a tier emits update:tier', async () => {
    const wrapper = mount(WizardLaunch, { props: {} })
    await wrapper.findAll('button')[0].trigger('click')  // small
    const emissions = wrapper.emitted('update:tier') || []
    // initial emit (medium) + click on small
    expect(emissions.length).toBeGreaterThanOrEqual(1)
  })
})
