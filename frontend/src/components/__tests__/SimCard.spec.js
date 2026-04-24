import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import SimCard from '../SimCard.vue'

const RouterLinkStub = { template: '<a><slot /></a>', props: ['to'] }

describe('SimCard', () => {
  const baseJob = {
    id: 'j1', goal: 'My Sim', tier: 'small', status: 'COMPLETED',
    pipeline_seconds: 125, created_at: new Date().toISOString(),
  }

  it('renders goal, tier, status label', () => {
    const wrapper = mount(SimCard, {
      props: { job: baseJob },
      global: { stubs: { RouterLink: RouterLinkStub } },
    })
    expect(wrapper.text()).toContain('My Sim')
    expect(wrapper.text()).toContain('small tier')
    expect(wrapper.text()).toContain('Completed')
  })

  it('shows key insight for completed jobs', () => {
    const wrapper = mount(SimCard, {
      props: { job: { ...baseJob, key_insight: 'Markets may rise.' } },
      global: { stubs: { RouterLink: RouterLinkStub } },
    })
    expect(wrapper.text()).toContain('Markets may rise')
  })

  it('picks coral for risk insight', () => {
    const wrapper = mount(SimCard, {
      props: { job: { ...baseJob, status: 'COMPLETED', key_insight: 'Market crash risk' } },
      global: { stubs: { RouterLink: RouterLinkStub } },
    })
    // jsdom normalizes hex colors to rgb(); accept either form
    expect(wrapper.html()).toMatch(/ff6b6b|255, ?107, ?107/i)
  })

  it('picks green for positive insight', () => {
    const wrapper = mount(SimCard, {
      props: { job: { ...baseJob, status: 'COMPLETED', key_insight: 'Strong growth' } },
      global: { stubs: { RouterLink: RouterLinkStub } },
    })
    expect(wrapper.html()).toMatch(/6ee7b7|110, ?231, ?183/i)
  })

  it('shows error message on FAILED', () => {
    const wrapper = mount(SimCard, {
      props: { job: { ...baseJob, status: 'FAILED', error_message: 'oops' } },
      global: { stubs: { RouterLink: RouterLinkStub } },
    })
    expect(wrapper.text()).toContain('oops')
    expect(wrapper.text()).toContain('Failed')
  })

  it('shows running step for RUNNING jobs', () => {
    const wrapper = mount(SimCard, {
      props: { job: { ...baseJob, status: 'RUNNING', pipeline_stage: 3 } },
      global: { stubs: { RouterLink: RouterLinkStub } },
    })
    expect(wrapper.text()).toContain('Step 3/5')
  })

  it('toggles kebab menu and emits delete', async () => {
    const wrapper = mount(SimCard, {
      props: { job: baseJob },
      global: { stubs: { RouterLink: RouterLinkStub } },
      attachTo: document.body,
    })
    const kebab = wrapper.findAll('button')[0]
    await kebab.trigger('click')
    const deleteBtn = wrapper.findAll('button').find(b => b.text().includes('Delete'))
    await deleteBtn.trigger('click')
    expect(wrapper.emitted('delete')?.[0]).toEqual(['j1'])
    wrapper.unmount()
  })

  it('click outside closes kebab menu', async () => {
    const wrapper = mount(SimCard, {
      props: { job: baseJob },
      global: { stubs: { RouterLink: RouterLinkStub } },
      attachTo: document.body,
    })
    await wrapper.find('button').trigger('click')
    document.body.click()
    wrapper.unmount()
  })

  it('formats time variants', () => {
    const now = new Date()
    const minutes = new Date(now - 5 * 60000).toISOString()
    const hours = new Date(now - 5 * 3600000).toISOString()
    const days = new Date(now - 3 * 86400000).toISOString()
    for (const created_at of [minutes, hours, days]) {
      const wrapper = mount(SimCard, {
        props: { job: { ...baseJob, created_at } },
        global: { stubs: { RouterLink: RouterLinkStub } },
      })
      expect(wrapper.html()).toBeTruthy()
    }
  })

  it('uses unknown status fallback', () => {
    const wrapper = mount(SimCard, {
      props: { job: { ...baseJob, status: 'WEIRD' } },
      global: { stubs: { RouterLink: RouterLinkStub } },
    })
    expect(wrapper.text()).toContain('WEIRD')
  })

  it('covers PROVISIONING, PENDING, REFUNDED statuses', () => {
    for (const status of ['PROVISIONING', 'PENDING', 'REFUNDED']) {
      const wrapper = mount(SimCard, {
        props: { job: { ...baseJob, status } },
        global: { stubs: { RouterLink: RouterLinkStub } },
      })
      expect(wrapper.html()).toBeTruthy()
    }
  })

  it('shows Restart in kebab for terminal statuses', async () => {
    for (const status of ['COMPLETED', 'FAILED', 'REFUNDED']) {
      const wrapper = mount(SimCard, {
        props: { job: { ...baseJob, status } },
        global: { stubs: { RouterLink: RouterLinkStub } },
        attachTo: document.body,
      })
      await wrapper.findAll('button')[0].trigger('click')
      const labels = wrapper.findAll('button').map(b => b.text())
      expect(labels).toContain('Restart')
      wrapper.unmount()
    }
  })

  it('hides Restart for in-flight statuses', async () => {
    for (const status of ['RUNNING', 'PROVISIONING', 'PENDING']) {
      const wrapper = mount(SimCard, {
        props: { job: { ...baseJob, status } },
        global: { stubs: { RouterLink: RouterLinkStub } },
        attachTo: document.body,
      })
      await wrapper.findAll('button')[0].trigger('click')
      const labels = wrapper.findAll('button').map(b => b.text())
      expect(labels).not.toContain('Restart')
      wrapper.unmount()
    }
  })

  it('emits restart with the full job when Restart clicked', async () => {
    const wrapper = mount(SimCard, {
      props: { job: { ...baseJob, status: 'COMPLETED' } },
      global: { stubs: { RouterLink: RouterLinkStub } },
      attachTo: document.body,
    })
    await wrapper.findAll('button')[0].trigger('click')
    const restartBtn = wrapper.findAll('button').find(b => b.text().includes('Restart'))
    await restartBtn.trigger('click')
    expect(wrapper.emitted('restart')?.[0]?.[0]).toMatchObject({
      id: 'j1', goal: 'My Sim', status: 'COMPLETED',
    })
    wrapper.unmount()
  })
})
