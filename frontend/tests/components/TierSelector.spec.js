import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import TierSelector from '../../src/components/TierSelector.vue'
import { useCreditsStore } from '../../src/stores/credits'

// Stub router-link
const RouterLinkStub = { template: '<a><slot /></a>', props: ['to'] }

describe('TierSelector', () => {
  it('renders 3 tier buttons', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useCreditsStore()
    store.setBalance(500)
    const wrapper = mount(TierSelector, {
      global: { plugins: [pinia], components: { RouterLink: RouterLinkStub } },
    })
    const buttons = wrapper.findAll('button')
    expect(buttons.length).toBe(3)
  })

  it('shows tier costs', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useCreditsStore()
    store.setBalance(500)
    const wrapper = mount(TierSelector, {
      global: { plugins: [pinia], components: { RouterLink: RouterLinkStub } },
    })
    const text = wrapper.text()
    expect(text).toContain('30 credits')
    expect(text).toContain('90 credits')
    expect(text).toContain('300 credits')
  })

  it('disables unaffordable tiers', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useCreditsStore()
    store.setBalance(50)
    const wrapper = mount(TierSelector, {
      global: { plugins: [pinia], components: { RouterLink: RouterLinkStub } },
    })
    const buttons = wrapper.findAll('button')
    // small=30, medium=90, large=300
    expect(buttons[0].attributes('disabled')).toBeUndefined() // small affordable
    expect(buttons[1].attributes('disabled')).toBeDefined()   // medium not affordable
    expect(buttons[2].attributes('disabled')).toBeDefined()   // large not affordable
  })

  it('emits select event when tier is clicked', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useCreditsStore()
    store.setBalance(500)
    const wrapper = mount(TierSelector, {
      global: { plugins: [pinia], components: { RouterLink: RouterLinkStub } },
    })
    const buttons = wrapper.findAll('button')
    await buttons[0].trigger('click')
    expect(wrapper.emitted('select')).toBeTruthy()
    expect(wrapper.emitted('select')[0]).toEqual(['small'])
  })
})
