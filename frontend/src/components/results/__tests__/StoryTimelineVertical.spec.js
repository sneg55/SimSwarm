import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StoryTimelineVertical from '../StoryTimelineVertical.vue'

const moments = [
  { id: 'a', type: 'finding',   roundIndex: 0, title: 'First',  detail: 'd1', date: new Date('2026-01-01T00:00:00Z') },
  { id: 'b', type: 'coalition', roundIndex: 4, title: 'Flip',   detail: 'd2', date: new Date('2026-01-15T00:00:00Z') },
  { id: 'c', type: 'post',      roundIndex: 8, title: 'Viral',  detail: 'd3', date: new Date('2026-01-30T00:00:00Z') },
]

describe('StoryTimelineVertical', () => {
  it('renders one row per moment with title and type badge', () => {
    const w = mount(StoryTimelineVertical, { props: { moments, start: null, end: null, roundCount: 10 } })
    expect(w.findAll('[data-timeline-row]')).toHaveLength(3)
    expect(w.text()).toContain('First')
    expect(w.text()).toContain('Flip')
    expect(w.text()).toContain('Viral')
    expect(w.text()).toContain('Finding')
    expect(w.text()).toContain('Coalition')
  })

  it('alternates card placement left/right', () => {
    const w = mount(StoryTimelineVertical, { props: { moments, start: null, end: null, roundCount: 10 } })
    const rows = w.findAll('[data-timeline-row]')
    expect(rows[0].find('[data-card-side="left"]').exists()).toBe(true)
    expect(rows[1].find('[data-card-side="right"]').exists()).toBe(true)
    expect(rows[2].find('[data-card-side="left"]').exists()).toBe(true)
  })

  it('renders nothing when moments is empty', () => {
    const w = mount(StoryTimelineVertical, { props: { moments: [], start: null, end: null, roundCount: 0 } })
    expect(w.find('[data-timeline-row]').exists()).toBe(false)
  })
})
