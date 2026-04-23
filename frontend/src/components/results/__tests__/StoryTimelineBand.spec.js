import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StoryTimelineBand from '../StoryTimelineBand.vue'

const baseProps = {
  start: new Date('2026-01-01T00:00:00Z'),
  end:   new Date('2026-01-31T00:00:00Z'),
  roundCount: 5,
  moments: [
    { id: 'a', type: 'market',    roundIndex: 0, title: 'A', detail: '' },
    { id: 'b', type: 'finding',   roundIndex: 2, title: 'B', detail: '' },
    { id: 'c', type: 'coalition', roundIndex: 4, title: 'C', detail: '' },
  ],
}

describe('StoryTimelineBand', () => {
  it('renders one dot per moment when no clustering applies', () => {
    const w = mount(StoryTimelineBand, { props: baseProps })
    expect(w.findAll('[data-timeline-dot]')).toHaveLength(3)
  })

  it('renders nothing when start/end are missing', () => {
    const w = mount(StoryTimelineBand, {
      props: { ...baseProps, start: null, end: null },
    })
    expect(w.find('[data-timeline-band]').exists()).toBe(false)
  })

  it('emits select with the clicked moment id', async () => {
    const w = mount(StoryTimelineBand, { props: baseProps })
    await w.findAll('[data-timeline-dot]')[1].trigger('click')
    expect(w.emitted('select')?.[0]?.[0]).toBe('b')
  })

  it('renders a cluster chip when two moments share a round', async () => {
    const w = mount(StoryTimelineBand, {
      props: {
        ...baseProps,
        moments: [
          { id: 'a', type: 'market',  roundIndex: 2, title: 'A', detail: '' },
          { id: 'b', type: 'finding', roundIndex: 2, title: 'B', detail: '' },
        ],
      },
    })
    expect(w.findAll('[data-timeline-dot]')).toHaveLength(0)
    const chip = w.find('[data-timeline-cluster]')
    expect(chip.exists()).toBe(true)
    expect(chip.text()).toContain('+2')
  })
})
