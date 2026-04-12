import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import CoalitionCard from '../CoalitionCard.vue'
import ConfidenceGrid from '../ConfidenceGrid.vue'
import EngagementCompact from '../EngagementCompact.vue'
import FindingCard from '../FindingCard.vue'
import MarketCurveCompact from '../MarketCurveCompact.vue'
import ReportToc from '../ReportToc.vue'
import ResultsBottomBar from '../ResultsBottomBar.vue'
import ResultsToolbar from '../ResultsToolbar.vue'
import SentimentBars from '../SentimentBars.vue'
import StoryTimeline from '../StoryTimeline.vue'

const RouterLinkStub = { template: '<a><slot /></a>' }

// Stub IntersectionObserver
global.IntersectionObserver = class {
  constructor(cb) { this.cb = cb }
  observe() {}
  unobserve() {}
  disconnect() {}
}

describe('CoalitionCard', () => {
  it('renders name, description, agents, strength', () => {
    const wrapper = mount(CoalitionCard, {
      props: { name: 'Bulls', description: 'Optimistic investors', agents: 42, strength: 77 },
    })
    expect(wrapper.text()).toContain('Bulls')
    expect(wrapper.text()).toContain('Optimistic investors')
    expect(wrapper.text()).toContain('42')
    expect(wrapper.text()).toContain('77')
  })

  it('applies custom color', () => {
    const wrapper = mount(CoalitionCard, {
      props: { name: 'N', description: 'D', agents: 1, strength: 10, color: '#FF0000' },
    })
    expect(wrapper.html()).toContain('#FF0000')
  })
})

describe('ConfidenceGrid', () => {
  it('renders grid items', () => {
    const wrapper = mount(ConfidenceGrid, {
      props: { items: [
        { label: 'Confidence', value: '82%', color: '#22D3EE' },
        { label: 'Sentiment Shift', value: '+12', color: '#6EE7B7' },
        { label: 'Risk Level', value: 'Low', color: '#FBBF24' },
      ] },
    })
    expect(wrapper.text()).toContain('Confidence')
    expect(wrapper.text()).toContain('Sentiment Shift')
    expect(wrapper.text()).toContain('Risk Level')
  })
})

describe('EngagementCompact', () => {
  it('renders total posts and likes', () => {
    const wrapper = mount(EngagementCompact, {
      props: { data: [
        { total_posts: 10, total_likes: 5 },
        { total_posts: 20, total_likes: 8 },
      ] },
    })
    expect(wrapper.text()).toContain('30 posts')
    expect(wrapper.text()).toContain('13 likes')
  })

  it('hides when data is empty', () => {
    const wrapper = mount(EngagementCompact, { props: { data: [] } })
    expect(wrapper.text()).toBe('')
  })

  it('hides likes label when zero likes', () => {
    const wrapper = mount(EngagementCompact, {
      props: { data: [{ total_posts: 5, total_likes: 0 }] },
    })
    expect(wrapper.text()).toContain('5 posts')
    expect(wrapper.text()).not.toContain('likes')
  })
})

describe('FindingCard', () => {
  it('renders label, title, description', () => {
    const wrapper = mount(FindingCard, {
      props: { label: 'F1', title: 'Finding Title', description: 'Detail...' },
    })
    expect(wrapper.text()).toContain('F1')
    expect(wrapper.text()).toContain('Finding Title')
    expect(wrapper.text()).toContain('Detail')
  })

  it('renders metric chip when metric prop supplied', () => {
    const wrapper = mount(FindingCard, {
      props: { label: 'L', title: 'T', description: 'D', metric: '+42%' },
    })
    expect(wrapper.text()).toContain('+42%')
  })

  it('hides metric when not supplied', () => {
    const wrapper = mount(FindingCard, {
      props: { label: 'L', title: 'T', description: 'D' },
    })
    expect(wrapper.html()).not.toMatch(/\+42%/)
  })
})

describe('MarketCurveCompact', () => {
  it('hides when no markets', () => {
    const wrapper = mount(MarketCurveCompact, { props: { markets: [] } })
    expect(wrapper.text()).toBe('')
  })

  it('renders question and current yes', () => {
    const wrapper = mount(MarketCurveCompact, {
      props: { markets: [{
        question: 'Will X happen?',
        points: [
          { price_yes: 0.5, price_no: 0.5 },
          { price_yes: 0.6, price_no: 0.4 },
        ],
      }] },
    })
    expect(wrapper.text()).toContain('Will X happen?')
    expect(wrapper.text()).toContain('60%')
  })

  it('renders single-point market', () => {
    const wrapper = mount(MarketCurveCompact, {
      props: { markets: [{ question: 'Q', points: [{ price_yes: 0.7, price_no: 0.3 }] }] },
    })
    expect(wrapper.find('circle').exists()).toBe(true)
  })

  it('handles zero-point market', () => {
    const wrapper = mount(MarketCurveCompact, {
      props: { markets: [{ question: 'Q', points: [] }] },
    })
    expect(wrapper.text()).toContain('—')
  })
})

describe('ReportToc', () => {
  it('renders items', () => {
    const wrapper = mount(ReportToc, {
      props: { items: [
        { id: 'sec-1', label: 'Overview' },
        { id: 'sec-2', label: 'Detail', sub: true },
      ] },
    })
    expect(wrapper.text()).toContain('Overview')
    expect(wrapper.text()).toContain('Detail')
  })

  it('scrollTo calls scrollIntoView on element', async () => {
    document.body.innerHTML = '<div id="sec-1"></div>'
    const el = document.getElementById('sec-1')
    el.scrollIntoView = vi.fn()
    const wrapper = mount(ReportToc, {
      props: { items: [{ id: 'sec-1', label: 'Overview' }] },
    })
    await wrapper.find('a').trigger('click')
    expect(el.scrollIntoView).toHaveBeenCalled()
  })
})

describe('ResultsBottomBar', () => {
  it('renders PDF and Share buttons by default', () => {
    const wrapper = mount(ResultsBottomBar, { props: {} })
    expect(wrapper.text()).toContain('Export as PDF')
    expect(wrapper.text()).toContain('Share simulation')
  })

  it('emits export on button clicks', async () => {
    const wrapper = mount(ResultsBottomBar, { props: { showPng: true, showJson: true, showCsv: true } })
    const buttons = wrapper.findAll('button')
    for (const btn of buttons) await btn.trigger('click')
    expect(wrapper.emitted('export')).toBeTruthy()
    expect(wrapper.emitted('share')).toBeTruthy()
  })

  it('shows generating state', () => {
    const wrapper = mount(ResultsBottomBar, { props: { pdfLoading: true } })
    expect(wrapper.text()).toContain('Generating')
  })

  it('shows copied state', () => {
    const wrapper = mount(ResultsBottomBar, { props: { shareStatus: 'copied' } })
    expect(wrapper.text()).toContain('copied')
  })

  it('shows error state', () => {
    const wrapper = mount(ResultsBottomBar, { props: { shareStatus: 'error' } })
    expect(wrapper.text()).toContain('Failed')
  })

  it('shows generating share state', () => {
    const wrapper = mount(ResultsBottomBar, { props: { shareStatus: 'generating' } })
    expect(wrapper.text()).toContain('Generating link')
  })
})

describe('ResultsToolbar', () => {
  it('renders title, back link, mode toggle', () => {
    const wrapper = mount(ResultsToolbar, {
      props: { title: 'My Sim', viewMode: 'story' },
      global: { stubs: { RouterLink: RouterLinkStub } },
    })
    expect(wrapper.text()).toContain('My Sim')
    expect(wrapper.text()).toContain('Dashboard')
  })

  it('hides toggle when showToggle=false', () => {
    const wrapper = mount(ResultsToolbar, {
      props: { showToggle: false },
      global: { stubs: { RouterLink: RouterLinkStub } },
    })
    expect(wrapper.findAll('button').length).toBe(0)
  })

  it('passes through custom backLabel', () => {
    const wrapper = mount(ResultsToolbar, {
      props: { backLink: '/home', backLabel: 'Home' },
      global: { stubs: { RouterLink: RouterLinkStub } },
    })
    expect(wrapper.text()).toContain('Home')
  })
})

describe('SentimentBars', () => {
  it('renders bars with labels and values', () => {
    const wrapper = mount(SentimentBars, {
      props: { bars: [
        { label: 'Optimism', width: 60, value: '60%', gradient: 'x', valueColor: '#fff' },
        { label: 'Risk', width: 40, value: '40%', gradient: 'y', valueColor: '#fff' },
      ] },
    })
    expect(wrapper.text()).toContain('Optimism')
    expect(wrapper.text()).toContain('Risk')
    expect(wrapper.text()).toContain('60%')
  })
})

describe('StoryTimeline', () => {
  it('renders sections', () => {
    const wrapper = mount(StoryTimeline, {
      props: { sections: [
        { id: 'a', label: 'A' },
        { id: 'b', label: 'B' },
        { id: 'c', label: 'C' },
      ] },
    })
    expect(wrapper.text()).toContain('A')
    expect(wrapper.text()).toContain('B')
  })

  it('scrollTo calls scrollIntoView', async () => {
    document.body.innerHTML = '<div id="sec-a"></div>'
    const el = document.getElementById('sec-a')
    el.scrollIntoView = vi.fn()
    const wrapper = mount(StoryTimeline, { props: { sections: [{ id: 'sec-a', label: 'A' }] } })
    await wrapper.find('div.cursor-pointer').trigger('click')
    expect(el.scrollIntoView).toHaveBeenCalled()
  })
})
