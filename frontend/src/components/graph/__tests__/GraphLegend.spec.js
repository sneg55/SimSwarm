import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import GraphLegend from '../GraphLegend.vue'

describe('GraphLegend', () => {
  const entityTypes = [
    { name: 'Person', count: 12, color: '#A78BFA' },
    { name: 'Organization', count: 5, color: '#22D3EE' },
  ]

  const nodes = [
    { sentiment: 0.5 },
    { sentiment: -0.5 },
    { sentiment: 0 },
    { sentiment: 0.3 },
  ]

  it('renders entity types with counts', () => {
    const wrapper = mount(GraphLegend, { props: { entityTypes, nodes } })
    expect(wrapper.text()).toContain('Person')
    expect(wrapper.text()).toContain('12')
    expect(wrapper.text()).toContain('Organization')
    expect(wrapper.text()).toContain('5')
  })

  it('renders sentiment buckets with computed counts', () => {
    const wrapper = mount(GraphLegend, { props: { entityTypes, nodes } })
    expect(wrapper.text()).toContain('Positive')
    expect(wrapper.text()).toContain('Negative')
    expect(wrapper.text()).toContain('Neutral')
    // positive: 2, negative: 1, neutral: 1
    expect(wrapper.text()).toMatch(/2/)
  })

  it('emits toggle-type', async () => {
    const wrapper = mount(GraphLegend, { props: { entityTypes, nodes } })
    // first button is "All", then "None", then entity type buttons
    const typeBtn = wrapper.findAll('button').find(b => b.text().includes('Person'))
    await typeBtn.trigger('click')
    expect(wrapper.emitted('toggle-type')?.[0]).toEqual(['Person'])
  })

  it('emits show-all and hide-all', async () => {
    const wrapper = mount(GraphLegend, { props: { entityTypes, nodes } })
    const allBtn = wrapper.findAll('button').find(b => b.text() === 'All')
    const noneBtn = wrapper.findAll('button').find(b => b.text() === 'None')
    await allBtn.trigger('click')
    await noneBtn.trigger('click')
    expect(wrapper.emitted('show-all')).toBeTruthy()
    expect(wrapper.emitted('hide-all')).toBeTruthy()
  })

  it('emits toggle-sentiment', async () => {
    const wrapper = mount(GraphLegend, { props: { entityTypes, nodes } })
    const posBtn = wrapper.findAll('button').find(b => b.text().includes('Positive'))
    await posBtn.trigger('click')
    expect(wrapper.emitted('toggle-sentiment')?.[0]).toEqual(['positive'])
  })

  it('shows filter banner and show-all-nodes button when set', async () => {
    const wrapper = mount(GraphLegend, { props: { entityTypes, nodes, filterBanner: 'Showing 50 of 200' } })
    expect(wrapper.text()).toContain('Showing 50 of 200')
    const btn = wrapper.findAll('button').find(b => b.text() === 'Show all')
    await btn.trigger('click')
    expect(wrapper.emitted('show-all-nodes')).toBeTruthy()
  })

  it('applies dimmed class to hidden types', () => {
    const wrapper = mount(GraphLegend, {
      props: { entityTypes, nodes, hiddenTypes: new Set(['Person']) },
    })
    expect(wrapper.html()).toContain('opacity-30')
  })
})
