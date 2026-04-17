import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import MarketsList from '../MarketsList.vue'

describe('MarketsList', () => {
  it('renders a row per market with question + price + rationale', () => {
    const markets = [
      { question: 'Fed cuts 50bp+?', initial_price_yes: 0.45, rationale: 'labor market softening' },
      { question: 'Fed holds rates?', initial_price_yes: 0.25, rationale: 'base case' },
    ]
    const wrapper = mount(MarketsList, { props: { markets } })
    const rows = wrapper.findAll('[data-test="market-row"]')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('Fed cuts 50bp+?')
    expect(rows[0].text()).toContain('45%')
    expect(rows[0].text()).toContain('labor market softening')
  })

  it('shows empty state when no markets', () => {
    const wrapper = mount(MarketsList, { props: { markets: [] } })
    expect(wrapper.text().toLowerCase()).toContain('no markets')
  })

  it('omits rationale cleanly when blank', () => {
    const wrapper = mount(MarketsList, {
      props: { markets: [{ question: 'Q?', initial_price_yes: 0.5, rationale: '' }] },
    })
    expect(wrapper.findAll('[data-test="market-rationale"]')).toHaveLength(0)
  })

  it('handles null markets prop as empty', () => {
    const wrapper = mount(MarketsList, { props: { markets: null } })
    expect(wrapper.findAll('[data-test="market-row"]')).toHaveLength(0)
  })
})
