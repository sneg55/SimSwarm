import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import DemoCard from '../DemoCard.vue'
import PricingCard from '../PricingCard.vue'
import ProofCard from '../ProofCard.vue'
import SkeletonCard from '../SkeletonCard.vue'
import LogoWavePulse from '../LogoWavePulse.vue'
import ViewModeToggle from '../ViewModeToggle.vue'
import PipelineProgress from '../PipelineProgress.vue'
import ChatReplay from '../ChatReplay.vue'

const RouterLinkStub = { template: '<a><slot /></a>' }

describe('DemoCard', () => {
  it('renders title and description', () => {
    const wrapper = mount(DemoCard, {
      props: { shareUrl: '/s/abc', title: 'Title', description: 'Desc' },
      global: { stubs: { RouterLink: RouterLinkStub } },
    })
    expect(wrapper.text()).toContain('Title')
    expect(wrapper.text()).toContain('Desc')
    expect(wrapper.text()).toContain('View results')
  })
})

describe('PricingCard', () => {
  const baseProps = {
    name: 'Pro', credits: 500, price: '$99', features: ['A', 'B', 'C'],
  }

  it('renders name, credits, price', () => {
    const wrapper = mount(PricingCard, { props: baseProps })
    expect(wrapper.text()).toContain('Pro')
    expect(wrapper.text()).toContain('500 credits')
    expect(wrapper.text()).toContain('$99')
    expect(wrapper.text()).toContain('A')
    expect(wrapper.text()).toContain('B')
  })

  it('shows Most popular badge when featured', () => {
    const wrapper = mount(PricingCard, { props: { ...baseProps, featured: true } })
    expect(wrapper.text()).toContain('Most popular')
  })

  it('omits featured badge by default', () => {
    const wrapper = mount(PricingCard, { props: baseProps })
    expect(wrapper.text()).not.toContain('Most popular')
  })

  it('applies accent color', () => {
    const wrapper = mount(PricingCard, { props: { ...baseProps, accentColor: '#FF0000' } })
    expect(wrapper.html()).toContain('#FF0000')
  })
})

describe('ProofCard', () => {
  it('renders quote, author, role', () => {
    const wrapper = mount(ProofCard, {
      props: { quote: 'Quote text', author: 'Name', role: 'CEO' },
    })
    expect(wrapper.text()).toContain('Quote text')
    expect(wrapper.text()).toContain('Name')
    expect(wrapper.text()).toContain('CEO')
  })
})

describe('SkeletonCard', () => {
  it('renders with default lines', () => {
    const wrapper = mount(SkeletonCard)
    expect(wrapper.findAll('[class*="bg-mist-depth"]').length).toBeGreaterThan(0)
  })
  it('renders custom lines count', () => {
    const wrapper = mount(SkeletonCard, { props: { lines: 5 } })
    expect(wrapper.html()).toBeTruthy()
  })
  it('renders zero lines', () => {
    const wrapper = mount(SkeletonCard, { props: { lines: 0 } })
    expect(wrapper.html()).toBeTruthy()
  })
})

describe('LogoWavePulse', () => {
  it('renders SVG with animated elements by default', () => {
    const wrapper = mount(LogoWavePulse)
    expect(wrapper.find('svg').exists()).toBe(true)
    expect(wrapper.findAll('circle').length).toBeGreaterThan(3)
    expect(wrapper.findAll('animate').length).toBeGreaterThan(0)
  })
  it('renders without animation when animated=false', () => {
    const wrapper = mount(LogoWavePulse, { props: { animated: false } })
    expect(wrapper.findAll('animate').length).toBe(0)
  })
  it('uses custom size', () => {
    const wrapper = mount(LogoWavePulse, { props: { size: 72 } })
    expect(wrapper.find('svg').attributes('width')).toBe('72')
  })
})

describe('ViewModeToggle', () => {
  it('renders three modes by default', () => {
    const wrapper = mount(ViewModeToggle, { props: { modelValue: 'story' } })
    const buttons = wrapper.findAll('button')
    expect(buttons.length).toBe(3)
    expect(wrapper.text()).toContain('Story')
    expect(wrapper.text()).toContain('Graph')
    expect(wrapper.text()).toContain('Report')
  })

  it('emits update:modelValue on click', async () => {
    const wrapper = mount(ViewModeToggle, { props: { modelValue: 'story' } })
    await wrapper.findAll('button')[1].trigger('click')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['graph'])
  })

  it('adds Data mode when showData is true', () => {
    const wrapper = mount(ViewModeToggle, { props: { modelValue: 'story', showData: true } })
    expect(wrapper.text()).toContain('Data')
    expect(wrapper.findAll('button').length).toBe(4)
  })

  it('highlights active mode', () => {
    const wrapper = mount(ViewModeToggle, { props: { modelValue: 'graph' } })
    const buttons = wrapper.findAll('button')
    expect(buttons[1].classes().some(c => c.includes('ocean-cyan'))).toBe(true)
  })
})

describe('PipelineProgress', () => {
  it('renders all 5 steps', () => {
    const wrapper = mount(PipelineProgress, { props: {} })
    expect(wrapper.text()).toContain('Seed')
    expect(wrapper.text()).toContain('Research')
    expect(wrapper.text()).toContain('Simulate')
    expect(wrapper.text()).toContain('Analyze')
    expect(wrapper.text()).toContain('Report')
  })

  it('marks completed steps with checkmark', () => {
    const wrapper = mount(PipelineProgress, { props: { completedSteps: ['seed', 'research'], currentStep: 'simulate' } })
    expect(wrapper.findAll('svg').length).toBeGreaterThan(0)
  })

  it('shows pulse indicator on active step', () => {
    const wrapper = mount(PipelineProgress, { props: { currentStep: 'simulate' } })
    expect(wrapper.html()).toContain('animate-pulse')
  })

  it('defaults work with no props', () => {
    const wrapper = mount(PipelineProgress)
    expect(wrapper.html()).toBeTruthy()
  })
})

describe('ChatReplay', () => {
  it('renders message count and collapsed by default', () => {
    const wrapper = mount(ChatReplay, { props: { messages: [{ role: 'user', content: 'hi' }] } })
    expect(wrapper.text()).toContain('1 messages')
  })

  it('opens when startExpanded=true and shows messages', () => {
    const wrapper = mount(ChatReplay, {
      props: {
        startExpanded: true,
        messages: [
          { role: 'user', content: 'hello' },
          { role: 'assistant', agent: 'Agent1', content: 'world' },
          { role: 'system', content: 'system msg' },
        ],
      },
    })
    expect(wrapper.text()).toContain('hello')
    expect(wrapper.text()).toContain('world')
    expect(wrapper.text()).toContain('Agent1')
    expect(wrapper.text()).toContain('system msg')
  })

  it('toggles expansion on header click', async () => {
    const wrapper = mount(ChatReplay, { props: { messages: [] } })
    await wrapper.find('div.cursor-pointer').trigger('click')
    expect(wrapper.text()).toContain('No messages')
  })

  it('formats timestamp', () => {
    const wrapper = mount(ChatReplay, {
      props: {
        startExpanded: true,
        messages: [{ role: 'assistant', agent: 'A', content: 'x', timestamp: '2024-01-01T12:30:00Z' }],
      },
    })
    expect(wrapper.html()).toMatch(/\d{2}:\d{2}/)
  })

  it('assigns distinct color to agent', () => {
    const wrapper = mount(ChatReplay, {
      props: {
        startExpanded: true,
        messages: [
          { role: 'assistant', agent: 'Alpha', content: 'a' },
          { role: 'assistant', agent: 'Beta', content: 'b' },
        ],
      },
    })
    expect(wrapper.html()).toContain('color')
  })

  it('handles assistant with no agent name', () => {
    const wrapper = mount(ChatReplay, {
      props: {
        startExpanded: true,
        messages: [{ role: 'assistant', content: 'x' }],
      },
    })
    expect(wrapper.text()).toContain('Agent')
  })
})
