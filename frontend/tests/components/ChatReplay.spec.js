import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ChatReplay from '../../src/components/ChatReplay.vue'

describe('ChatReplay', () => {
  it('shows empty state when no messages', () => {
    const wrapper = mount(ChatReplay, { props: { messages: [], startExpanded: true } })
    expect(wrapper.text()).toContain('No messages')
  })

  it('renders messages in the chat log', () => {
    const messages = [
      { role: 'assistant', agent: 'researcher', content: 'Starting research...', timestamp: null },
      { role: 'user', content: 'Proceed with analysis', timestamp: null },
    ]
    const wrapper = mount(ChatReplay, { props: { messages, startExpanded: true } })
    expect(wrapper.text()).toContain('Starting research...')
    expect(wrapper.text()).toContain('Proceed with analysis')
  })
})
