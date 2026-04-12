import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import GraphSearchBar from '../GraphSearchBar.vue'

describe('GraphSearchBar', () => {
  const nodes = [
    { uuid: 'u1', name: 'Alice Smith', labels: ['Person'] },
    { uuid: 'u2', name: 'Bob Jones', labels: ['Person'] },
    { uuid: 'u3', name: 'Acme Corp', labels: ['Organization'] },
  ]

  it('renders input', () => {
    const wrapper = mount(GraphSearchBar, { props: { nodes } })
    expect(wrapper.find('input').exists()).toBe(true)
  })

  it('shows filtered results on input', async () => {
    const wrapper = mount(GraphSearchBar, { props: { nodes } })
    await wrapper.find('input').setValue('alice')
    expect(wrapper.text()).toContain('Alice Smith')
    expect(wrapper.text()).not.toContain('Bob Jones')
  })

  it('filters by entity type text', async () => {
    const wrapper = mount(GraphSearchBar, { props: { nodes } })
    await wrapper.find('input').setValue('organization')
    expect(wrapper.text()).toContain('Acme Corp')
  })

  it('emits select-node when result clicked', async () => {
    const wrapper = mount(GraphSearchBar, { props: { nodes } })
    await wrapper.find('input').setValue('alice')
    const resultBtns = wrapper.findAll('button')
    await resultBtns[0].trigger('click')
    expect(wrapper.emitted('select-node')?.[0]).toEqual(['u1'])
  })

  it('selects first result on Enter', async () => {
    const wrapper = mount(GraphSearchBar, { props: { nodes } })
    const input = wrapper.find('input')
    await input.setValue('bob')
    await input.trigger('keydown.enter')
    expect(wrapper.emitted('select-node')?.[0]).toEqual(['u2'])
  })

  it('closes dropdown on Escape', async () => {
    const wrapper = mount(GraphSearchBar, { props: { nodes } })
    const input = wrapper.find('input')
    await input.setValue('a')
    await input.trigger('keydown.escape')
    expect(wrapper.findAll('button').length).toBe(0)
  })

  it('empty query shows no results', async () => {
    const wrapper = mount(GraphSearchBar, { props: { nodes } })
    await wrapper.find('input').setValue('')
    expect(wrapper.findAll('button').length).toBe(0)
  })

  it('limits results to 20', async () => {
    const big = Array.from({ length: 30 }, (_, i) => ({ uuid: `u${i}`, name: `Node${i}`, labels: ['Person'] }))
    const wrapper = mount(GraphSearchBar, { props: { nodes: big } })
    await wrapper.find('input').setValue('node')
    expect(wrapper.findAll('button').length).toBeLessThanOrEqual(20)
  })
})
