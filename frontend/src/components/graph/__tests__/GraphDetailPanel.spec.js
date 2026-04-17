import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('@dicebear/core', () => ({
  createAvatar: vi.fn(() => ({ toDataUri: () => 'data:image/svg+xml,test' })),
}))
vi.mock('@dicebear/collection', () => ({ personas: {} }))

import GraphDetailPanel from '../GraphDetailPanel.vue'

describe('GraphDetailPanel', () => {
  it('renders nothing when node is null', () => {
    const wrapper = mount(GraphDetailPanel, { props: { node: null } })
    expect(wrapper.text()).toBe('')
  })

  it('renders node info', () => {
    const node = {
      name: 'Alice', entityType: 'Person', summary: 'A person.',
      connectionCount: 5, sentiment: 0.7, stance: 'supportive',
      relationships: [
        { direction: 'outgoing', target_uuid: 'x', targetName: 'Acme', type: 'WORKS_AT' },
        { direction: 'incoming', source_uuid: 'y', sourceName: 'Bob', type: 'KNOWS' },
      ],
    }
    const wrapper = mount(GraphDetailPanel, { props: { node, agentActions: [] } })
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('Person')
    expect(wrapper.text()).toContain('A person.')
    expect(wrapper.text()).toContain('Acme')
    expect(wrapper.text()).toContain('Bob')
    expect(wrapper.text()).toContain('WORKS_AT')
    expect(wrapper.text()).toContain('5')
  })

  it('emits close on close button click', async () => {
    const wrapper = mount(GraphDetailPanel, {
      props: { node: { name: 'A', entityType: 'Person' } },
    })
    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('emits navigate-to with target uuid', async () => {
    const node = {
      name: 'A', entityType: 'Person',
      relationships: [{ direction: 'outgoing', target_uuid: 'xx', targetName: 'B', type: 'KNOWS' }],
    }
    const wrapper = mount(GraphDetailPanel, { props: { node } })
    const relBtns = wrapper.findAll('button').filter(b => b.text().includes('B'))
    if (relBtns.length) {
      await relBtns[0].trigger('click')
      expect(wrapper.emitted('navigate-to')?.[0]).toEqual(['xx'])
    }
  })

  it('dedupes agent actions by action_type/round/content', () => {
    const node = { name: 'A', entityType: 'Person' }
    const agentActions = [
      { action_type: 'CREATE_POST', round_num: 1, platform: 'twitter', action_args: { content: 'hi' } },
      { action_type: 'CREATE_POST', round_num: 1, platform: 'reddit', action_args: { content: 'hi' } },
      { action_type: 'LIKE_POST', round_num: 2, platform: 'twitter', action_args: { content: '' } },
    ]
    const wrapper = mount(GraphDetailPanel, { props: { node, agentActions } })
    expect(wrapper.text()).toContain('Activity')
  })

  it('renders new-engine schema: lowercase action_type and action_args.text', () => {
    const node = { name: 'SEC', entityType: 'Organization' }
    const agentActions = [
      {
        action_type: 'create_post',
        round_num: 1,
        platform: 'social',
        action_args: { text: 'New AI disclosure rules require public companies to report material risks.' },
      },
    ]
    const wrapper = mount(GraphDetailPanel, { props: { node, agentActions } })
    expect(wrapper.text()).toContain('New AI disclosure rules require public companies to report material risks.')
    expect(wrapper.text()).toContain('Post')
    expect(wrapper.text()).not.toContain('create_post')
  })

  it('dedupes new-engine actions by text across platforms', () => {
    const node = { name: 'SEC', entityType: 'Organization' }
    const agentActions = [
      { action_type: 'create_post', round_num: 1, platform: 'twitter', action_args: { text: 'same body' } },
      { action_type: 'create_post', round_num: 1, platform: 'reddit', action_args: { text: 'same body' } },
    ]
    const wrapper = mount(GraphDetailPanel, { props: { node, agentActions } })
    const cards = wrapper.findAll('[class*="rounded-xl"]').filter(w => w.text().includes('same body'))
    expect(cards.length).toBe(1)
  })

  it('shows sentiment with correct color for positive/negative/neutral', () => {
    const neg = mount(GraphDetailPanel, { props: { node: { name: 'A', entityType: 'Person', sentiment: -0.7 } } })
    // jsdom converts hex colors to rgb() strings when set via style
    expect(neg.html()).toMatch(/FF6B6B|255, ?107, ?107/i)
    const pos = mount(GraphDetailPanel, { props: { node: { name: 'A', entityType: 'Person', sentiment: 0.7 } } })
    expect(pos.html()).toMatch(/6EE7B7|110, ?231, ?183/i)
  })

  it('shows stance color variants', () => {
    const sup = mount(GraphDetailPanel, { props: { node: { name: 'A', entityType: 'Person', stance: 'supportive' } } })
    expect(sup.html()).toMatch(/6EE7B7|110, ?231, ?183/i)
    const opp = mount(GraphDetailPanel, { props: { node: { name: 'A', entityType: 'Person', stance: 'opposing' } } })
    expect(opp.html()).toMatch(/FF6B6B|255, ?107, ?107/i)
  })

  it('renders various action badges', () => {
    const node = { name: 'A', entityType: 'Person' }
    const types = ['CREATE_POST', 'LIKE_POST', 'DISLIKE_POST', 'FOLLOW', 'DO_NOTHING']
    for (const t of types) {
      const wrapper = mount(GraphDetailPanel, { props: {
        node,
        agentActions: [{ action_type: t, round_num: 1, platform: 'twitter', action_args: { content: 'x' } }],
      } })
      expect(wrapper.html()).toBeTruthy()
    }
  })
})
