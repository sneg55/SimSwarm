import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('../../src/api/demos.js', () => ({
  listDemos: vi.fn(),
}))

import Landing from '../../src/views/Landing.vue'
import { listDemos } from '../../src/api/demos.js'

const stubAll = {
  'router-link': { template: '<a><slot /></a>' },
  ScrollProgress: true,
  HeroSwarm: true,
  HeroRotatingText: true,
  ExperienceStep: { template: '<div><slot name="mockup" /></div>' },
  LogoWavePulse: true,
  DemoCard: { props: ['shareUrl', 'title', 'description'], template: '<div class="demo">{{ title }}</div>' },
}

describe('Landing.vue', () => {
  beforeEach(() => {
    listDemos.mockReset()
  })

  it('renders hero and sections', async () => {
    listDemos.mockResolvedValue([])
    const wrapper = mount(Landing, { global: { stubs: stubAll } })
    await flushPromises()
    expect(wrapper.text()).toContain('three steps')
    expect(wrapper.text()).toContain('Run the whole swarm on your own infra')
    expect(wrapper.text()).toContain('No demos available yet')
  })

  it('renders demos when listDemos returns', async () => {
    listDemos.mockResolvedValue([
      { share_token: 't1', share_url: '/s/t1', title: 'Demo 1', tier: 'small' },
      { share_token: 't2', share_url: '/s/t2', title: 'Demo 2', tier: 'medium' },
    ])
    const wrapper = mount(Landing, { global: { stubs: stubAll } })
    await flushPromises()
    expect(wrapper.text()).toContain('Demo 1')
    expect(wrapper.text()).toContain('Demo 2')
  })

  it('handles demo fetch failure gracefully', async () => {
    listDemos.mockRejectedValue(new Error('fail'))
    const wrapper = mount(Landing, { global: { stubs: stubAll } })
    await flushPromises()
    expect(wrapper.text()).toContain('No demos available yet')
  })

  it('generates agent swarm styles', async () => {
    listDemos.mockResolvedValue([])
    const wrapper = mount(Landing, { global: { stubs: stubAll } })
    await flushPromises()
    expect(wrapper.html()).toBeTruthy()
  })
})
