import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import InfoTooltip from '../InfoTooltip.vue'

describe('InfoTooltip', () => {
  it('renders slot content', () => {
    const wrapper = mount(InfoTooltip, {
      props: { copyKey: 'coalitionCard.strength' },
      slots: { default: '<span class="metric">82%</span>' },
    })
    expect(wrapper.find('.metric').text()).toBe('82%')
  })

  it('renders info icon for known copyKey', () => {
    const wrapper = mount(InfoTooltip, {
      props: { copyKey: 'coalitionCard.strength' },
      slots: { default: '<span>82%</span>' },
    })
    expect(wrapper.find('[data-testid="info-icon"]').exists()).toBe(true)
  })

  it('does not render icon for unknown copyKey', () => {
    const wrapper = mount(InfoTooltip, {
      props: { copyKey: 'nonexistent.metric' },
      slots: { default: '<span>42</span>' },
    })
    expect(wrapper.find('[data-testid="info-icon"]').exists()).toBe(false)
  })

  it('shows tooltip on mouseenter', async () => {
    const wrapper = mount(InfoTooltip, {
      props: { copyKey: 'coalitionCard.strength' },
      slots: { default: '<span>82%</span>' },
      attachTo: document.body,
    })
    await wrapper.find('[data-testid="tooltip-trigger"]').trigger('mouseenter')
    // Wait for 200ms hover delay
    await new Promise(r => setTimeout(r, 250))
    expect(wrapper.find('[data-testid="tooltip-panel"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="tooltip-panel"]').text()).toContain('Coalition Strength')
    expect(wrapper.find('[data-testid="tooltip-panel"]').text()).toContain('How tightly aligned')
    expect(wrapper.find('[data-testid="tooltip-panel"]').text()).toContain('Calculated from:')
    wrapper.unmount()
  })

  it('hides tooltip on mouseleave', async () => {
    const wrapper = mount(InfoTooltip, {
      props: { copyKey: 'coalitionCard.strength' },
      slots: { default: '<span>82%</span>' },
      attachTo: document.body,
    })
    await wrapper.find('[data-testid="tooltip-trigger"]').trigger('mouseenter')
    await new Promise(r => setTimeout(r, 250))
    expect(wrapper.find('[data-testid="tooltip-panel"]').exists()).toBe(true)
    await wrapper.find('[data-testid="tooltip-trigger"]').trigger('mouseleave')
    await new Promise(r => setTimeout(r, 200))
    expect(wrapper.find('[data-testid="tooltip-panel"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('has correct aria attributes', async () => {
    const wrapper = mount(InfoTooltip, {
      props: { copyKey: 'coalitionCard.strength' },
      slots: { default: '<span>82%</span>' },
      attachTo: document.body,
    })
    const icon = wrapper.find('[data-testid="info-icon"]')
    expect(icon.attributes('role')).toBe('button')
    expect(icon.attributes('tabindex')).toBe('0')
    expect(icon.attributes('aria-label')).toBe('More info')
    wrapper.unmount()
  })
})
