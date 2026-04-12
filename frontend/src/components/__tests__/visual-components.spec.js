import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import DashboardEmpty from '../DashboardEmpty.vue'
import ExperienceStep from '../ExperienceStep.vue'
import HeroRotatingText from '../HeroRotatingText.vue'
import ScrollProgress from '../ScrollProgress.vue'
import * as tooltipArrowStyles from '../tooltipArrowStyles.js'

const RouterLinkStub = { template: '<a><slot /></a>' }

beforeEach(() => {
  global.IntersectionObserver = class {
    constructor(cb) { this.cb = cb }
    observe = vi.fn()
    unobserve = vi.fn()
    disconnect = vi.fn()
  }
})

describe('DashboardEmpty', () => {
  it('renders CTA and link', () => {
    const wrapper = mount(DashboardEmpty, {
      global: { stubs: { RouterLink: RouterLinkStub } },
    })
    expect(wrapper.text()).toContain('Your ecosystem is ready')
    expect(wrapper.text()).toContain('Start your first simulation')
  })
})

describe('ExperienceStep', () => {
  it('renders step number and slots', () => {
    const wrapper = mount(ExperienceStep, {
      props: { stepNumber: '01' },
      slots: {
        title: 'Title Text',
        description: 'Desc Text',
        detail: 'Detail Text',
        mockup: '<div>Mockup</div>',
      },
    })
    expect(wrapper.text()).toContain('01')
    expect(wrapper.text()).toContain('Title Text')
    expect(wrapper.text()).toContain('Desc Text')
    expect(wrapper.text()).toContain('Detail Text')
    expect(wrapper.text()).toContain('Mockup')
  })

  it('renders without detail slot', () => {
    const wrapper = mount(ExperienceStep, {
      props: { stepNumber: '02' },
      slots: { title: 'T', description: 'D', mockup: '<span/>' },
    })
    expect(wrapper.text()).toContain('02')
  })

  it('reverse prop applies order classes', () => {
    const wrapper = mount(ExperienceStep, {
      props: { stepNumber: '03', reverse: true },
      slots: { title: 'T', description: 'D', mockup: '<span/>' },
    })
    expect(wrapper.html()).toContain('order-')
  })
})

describe('HeroRotatingText', () => {
  it('renders all words', () => {
    const wrapper = mount(HeroRotatingText)
    expect(wrapper.findAll('span.block').length).toBeGreaterThan(5)
  })

  it('cycles words when interval fires', async () => {
    vi.useFakeTimers()
    const wrapper = mount(HeroRotatingText, { attachTo: document.body })
    vi.advanceTimersByTime(2500)
    vi.advanceTimersByTime(800)
    wrapper.unmount()
    vi.useRealTimers()
  })
})

describe('ScrollProgress', () => {
  it('renders', () => {
    const wrapper = mount(ScrollProgress)
    expect(wrapper.find('div.fixed').exists()).toBe(true)
  })

  it('updates progress on scroll', async () => {
    const wrapper = mount(ScrollProgress, { attachTo: document.body })
    Object.defineProperty(document.documentElement, 'scrollTop', { value: 100, configurable: true })
    Object.defineProperty(document.documentElement, 'scrollHeight', { value: 1000, configurable: true })
    Object.defineProperty(document.documentElement, 'clientHeight', { value: 500, configurable: true })
    window.dispatchEvent(new Event('scroll'))
    wrapper.unmount()
  })
})

describe('tooltipArrowStyles module', () => {
  it('exports arrowStyles for each placement', () => {
    expect(tooltipArrowStyles.arrowStyles.top).toBeTruthy()
    expect(tooltipArrowStyles.arrowStyles.bottom).toBeTruthy()
    expect(tooltipArrowStyles.arrowStyles.left).toBeTruthy()
    expect(tooltipArrowStyles.arrowStyles.right).toBeTruthy()
  })

  it('exports panelBaseStyle and dividerStyle', () => {
    expect(tooltipArrowStyles.panelBaseStyle.background).toBeTruthy()
    expect(tooltipArrowStyles.dividerStyle.borderTop).toBeTruthy()
    expect(tooltipArrowStyles.calcLabelColor).toBeTruthy()
  })
})
