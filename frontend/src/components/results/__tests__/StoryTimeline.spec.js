import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StoryTimeline from '../StoryTimeline.vue'

const sections = [
  { id: 'story-hero',     label: 'Q&A' },
  { id: 'story-findings', label: 'Findings' },
]

describe('StoryTimeline', () => {
  it('renders section dots when no moments prop is passed (legacy behavior)', () => {
    const w = mount(StoryTimeline, { props: { sections } })
    expect(w.findAll('[data-section-dot]')).toHaveLength(2)
    expect(w.findAll('[data-moment-dot]')).toHaveLength(0)
  })

  it('renders moment dots when moments prop is passed', () => {
    const w = mount(StoryTimeline, {
      props: {
        sections,
        moments: [
          { id: 'm1', type: 'market',  roundIndex: 0 },
          { id: 'm2', type: 'finding', roundIndex: 4 },
        ],
        roundCount: 5,
      },
    })
    expect(w.findAll('[data-section-dot]')).toHaveLength(2)
    expect(w.findAll('[data-moment-dot]')).toHaveLength(2)
  })
})
