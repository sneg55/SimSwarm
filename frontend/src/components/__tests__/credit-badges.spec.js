import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import CreditBadge from '../CreditBadge.vue'
import CreditWarning from '../CreditWarning.vue'
import { useCreditsStore } from '../../stores/credits.js'

const RouterLinkStub = { template: '<a><slot /></a>' }

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('CreditBadge', () => {
  it('renders current balance', () => {
    const store = useCreditsStore()
    store.balance = 100
    const wrapper = mount(CreditBadge, { global: { stubs: { RouterLink: RouterLinkStub } } })
    expect(wrapper.text()).toContain('100 credits')
  })

  it('uses coral style when balance is low', () => {
    const store = useCreditsStore()
    store.balance = 5
    const wrapper = mount(CreditBadge, { global: { stubs: { RouterLink: RouterLinkStub } } })
    expect(wrapper.html()).toContain('coral')
  })

  it('uses sage style when balance is healthy', () => {
    const store = useCreditsStore()
    store.balance = 500
    const wrapper = mount(CreditBadge, { global: { stubs: { RouterLink: RouterLinkStub } } })
    expect(wrapper.html()).toContain('organic')
  })

  it('links to /account', () => {
    const store = useCreditsStore()
    store.balance = 100
    const RouterLinkSpy = { props: ['to'], template: '<a :href="to"><slot /></a>' }
    const wrapper = mount(CreditBadge, { global: { stubs: { RouterLink: RouterLinkSpy } } })
    expect(wrapper.find('a').attributes('href')).toBe('/account')
  })
})

describe('CreditWarning', () => {
  it('hides when balance is healthy', () => {
    const store = useCreditsStore()
    store.balance = 500
    const wrapper = mount(CreditWarning, { global: { stubs: { RouterLink: RouterLinkStub } } })
    expect(wrapper.text()).toBe('')
  })

  it('shows when balance is low', () => {
    const store = useCreditsStore()
    store.balance = 5
    const wrapper = mount(CreditWarning, { global: { stubs: { RouterLink: RouterLinkStub } } })
    expect(wrapper.text()).toContain('Low credit balance')
    expect(wrapper.text()).toContain('5 credits')
  })
})
