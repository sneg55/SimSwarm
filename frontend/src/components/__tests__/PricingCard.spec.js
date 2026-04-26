import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import PricingCard from '../PricingCard.vue'

const Stub = { template: '<div />' }

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: Stub },
      { path: '/register', component: Stub },
      { path: '/account', component: Stub },
    ],
  })
}

describe('PricingCard CTA', () => {
  const baseProps = {
    name: 'Starter', credits: 100, price: '$19',
    features: ['feature one'],
  }

  it('renders a router-link to /register by default', async () => {
    const router = makeRouter()
    const wrapper = mount(PricingCard, {
      props: baseProps,
      global: { plugins: [router] },
    })
    await router.isReady()
    const link = wrapper.find('a')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('/register')
    expect(link.text()).toBe('Get started')
  })

  it('honors ctaTo + ctaLabel overrides', async () => {
    const router = makeRouter()
    const wrapper = mount(PricingCard, {
      props: { ...baseProps, ctaTo: '/account', ctaLabel: 'Buy now' },
      global: { plugins: [router] },
    })
    await router.isReady()
    const link = wrapper.find('a')
    expect(link.attributes('href')).toBe('/account')
    expect(link.text()).toBe('Buy now')
  })
})
