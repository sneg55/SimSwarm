import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import GraphControls from '../GraphControls.vue'

describe('GraphControls', () => {
  it('emits zoom-fit, refresh, toggle-edge-labels, export, toggle-fullscreen', async () => {
    const wrapper = mount(GraphControls, { props: { showEdgeLabels: false } })
    const buttons = wrapper.findAll('button')
    // buttons[0] = zoom-fit, buttons[1] = refresh, buttons[2,3] = group-by toggle
    // buttons[4] = edge labels, buttons[5] = export, buttons[6] = fullscreen
    await buttons[0].trigger('click')
    await buttons[1].trigger('click')
    await buttons[4].trigger('click')
    await buttons[5].trigger('click')
    await buttons[6].trigger('click')
    expect(wrapper.emitted('zoom-fit')).toBeTruthy()
    expect(wrapper.emitted('refresh')).toBeTruthy()
    expect(wrapper.emitted('toggle-edge-labels')).toBeTruthy()
    expect(wrapper.emitted('export')).toBeTruthy()
    expect(wrapper.emitted('toggle-fullscreen')).toBeTruthy()
  })

  it('emits set-group-by on tab click', async () => {
    const wrapper = mount(GraphControls, { props: { groupBy: 'type' } })
    const buttons = wrapper.findAll('button')
    await buttons[2].trigger('click')  // Type
    await buttons[3].trigger('click')  // Sentiment
    expect(wrapper.emitted('set-group-by')).toBeTruthy()
    expect(wrapper.emitted('set-group-by')).toContainEqual(['sentiment'])
  })

  it('emits change-layout on select change', async () => {
    const wrapper = mount(GraphControls, { props: { layoutName: 'cose-bilkent' } })
    await wrapper.find('select').setValue('circle')
    expect(wrapper.emitted('change-layout')?.[0]).toEqual(['circle'])
  })

  it('toggles fullscreen icon', () => {
    const w1 = mount(GraphControls, { props: { isFullscreen: false } })
    const w2 = mount(GraphControls, { props: { isFullscreen: true } })
    expect(w1.html()).not.toBe(w2.html())
  })

  it('applies active class for edge labels', () => {
    const wrapper = mount(GraphControls, { props: { showEdgeLabels: true } })
    expect(wrapper.html()).toContain('ocean-cyan')
  })
})
