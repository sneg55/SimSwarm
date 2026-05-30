import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import LiveActivity from '../LiveActivity.vue'

describe('LiveActivity', () => {
  it('is collapsed by default when prop open not provided — starts open', () => {
    const wrapper = mount(LiveActivity, {
      props: { logLines: ['[pipeline] Building graph here'], partialChat: [], stage: 1 },
    })
    // Default is open=true; log line text should be visible
    expect(wrapper.text()).toContain('Building graph here')
  })

  it('renders log lines when partialChat is empty', () => {
    const wrapper = mount(LiveActivity, {
      props: {
        logLines: ['[pipeline] 12 entities extracted', '[pipeline] Building knowledge graph'],
        partialChat: [],
        stage: 1,
      },
    })
    expect(wrapper.text()).toContain('12 entities extracted')
    expect(wrapper.text()).toContain('Building knowledge graph')
  })

  it('strips [pipeline] prefix from log lines', () => {
    const wrapper = mount(LiveActivity, {
      props: { logLines: ['[pipeline] 12 entities extracted'], partialChat: [], stage: 1 },
    })
    expect(wrapper.text()).not.toContain('[pipeline]')
    expect(wrapper.text()).toContain('12 entities extracted')
  })

  it('renders agent messages from partialChat', () => {
    const messages = [
      { agent: 'agent_47', content: 'First message content here', role: 'assistant' },
      { agent: 'agent_12', content: 'Latest message content', role: 'assistant' },
    ]
    const wrapper = mount(LiveActivity, {
      props: { logLines: [], partialChat: messages, stage: 3 },
    })
    expect(wrapper.text()).toContain('First message content here')
    expect(wrapper.text()).toContain('Latest message content')
  })

  it('shows LIVE badge only on the last message', () => {
    const messages = [
      { agent: 'agent_1', content: 'first message text', role: 'assistant' },
      { agent: 'agent_2', content: 'second message text', role: 'assistant' },
    ]
    const wrapper = mount(LiveActivity, {
      props: { logLines: [], partialChat: messages, stage: 3 },
    })
    const liveBadges = wrapper.findAll('[data-testid="live-badge"]')
    expect(liveBadges).toHaveLength(1)
  })

  it('hides log lines section when partialChat has messages', () => {
    const wrapper = mount(LiveActivity, {
      props: {
        logLines: ['[pipeline] some log line here'],
        partialChat: [{ agent: 'a', content: 'msg', role: 'assistant' }],
        stage: 3,
      },
    })
    expect(wrapper.find('[data-testid="log-lines"]').exists()).toBe(false)
  })

  it('collapses when header is clicked', async () => {
    const wrapper = mount(LiveActivity, {
      props: { logLines: ['[pipeline] 12 entities extracted'], partialChat: [], stage: 1 },
    })
    expect(wrapper.text()).toContain('12 entities extracted')
    await wrapper.find('button').trigger('click')
    // After collapse, the body div is hidden (v-show)
    const body = wrapper.find('[data-testid="live-body"]')
    expect(body.isVisible()).toBe(false)
  })
})
