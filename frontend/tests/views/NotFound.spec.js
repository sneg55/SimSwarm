import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import NotFound from '../../src/views/NotFound.vue'

describe('NotFound.vue', () => {
  it('renders 404 message and navigation links', () => {
    const wrapper = mount(NotFound, {
      global: { stubs: { 'router-link': { template: '<a><slot /></a>' } } },
    })
    expect(wrapper.text()).toContain('404')
    expect(wrapper.text()).toContain('Page not found')
    expect(wrapper.text()).toContain('Home')
    expect(wrapper.text()).toContain('Dashboard')
  })
})
