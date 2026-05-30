import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import AgentProfileCards from '../AgentProfileCards.vue'
import AgentTrajectoryChart from '../AgentTrajectoryChart.vue'
import EngagementChart from '../EngagementChart.vue'
import MarketCurveChart from '../MarketCurveChart.vue'
import TopPostsFeed from '../TopPostsFeed.vue'
import TradeFeed from '../TradeFeed.vue'
import SocialGraphView from '../SocialGraphView.vue'

// Canvas stubs
beforeEach(() => {
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
    clearRect: vi.fn(),
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    stroke: vi.fn(),
    arc: vi.fn(),
    fill: vi.fn(),
    fillText: vi.fn(),
    setTransform: vi.fn(),
    save: vi.fn(),
    restore: vi.fn(),
    translate: vi.fn(),
    scale: vi.fn(),
    createRadialGradient: vi.fn(() => ({ addColorStop: vi.fn() })),
    createLinearGradient: vi.fn(() => ({ addColorStop: vi.fn() })),
    fillRect: vi.fn(),
    rect: vi.fn(),
    closePath: vi.fn(),
  }))
  HTMLCanvasElement.prototype.toDataURL = vi.fn(() => 'data:image/png;base64,x')
  global.requestAnimationFrame = vi.fn(() => 1)
  global.cancelAnimationFrame = vi.fn()
})

describe('AgentProfileCards', () => {
  it('shows empty state', () => {
    const wrapper = mount(AgentProfileCards, { props: { profiles: [] } })
    expect(wrapper.text()).toContain('No profiles available')
  })

  it('renders profiles with MBTI and country', () => {
    const wrapper = mount(AgentProfileCards, {
      props: { profiles: [
        { name: 'Alice', persona: 'Bio text', mbti: 'INTJ', country: 'USA' },
        { user_name: 'Bob', bio: 'Short bio' },
      ] },
    })
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('INTJ')
    expect(wrapper.text()).toContain('USA')
    expect(wrapper.text()).toContain('Bob')
  })
})

describe('AgentTrajectoryChart', () => {
  it('shows no-data state when all sentiments are zero', () => {
    const wrapper = mount(AgentTrajectoryChart, {
      props: { agents: [{ agent_id: 1, name: 'A', rounds: [{ sentiment: 0 }] }] },
    })
    expect(wrapper.text()).toContain('Insufficient sentiment data')
  })

  it('renders paths when sentiment data exists', () => {
    const wrapper = mount(AgentTrajectoryChart, {
      props: { agents: [
        { agent_id: 1, name: 'Alice', type: 'Person', rounds: [
          { round: 1, sentiment: 0.5, posts: 3 },
          { round: 2, sentiment: -0.3, posts: 4 },
        ] },
      ] },
    })
    expect(wrapper.find('path').exists()).toBe(true)
  })

  it('renders single-point circle', () => {
    const wrapper = mount(AgentTrajectoryChart, {
      props: { agents: [
        { agent_id: 1, name: 'Alice', rounds: [{ round: 1, sentiment: 0.7 }] },
      ] },
    })
    expect(wrapper.find('circle').exists()).toBe(true)
  })

  it('handles hover when data is present', async () => {
    const wrapper = mount(AgentTrajectoryChart, {
      props: { agents: [
        { agent_id: 1, name: 'Alice', rounds: [
          { round: 1, sentiment: 0.5, posts: 3 },
          { round: 2, sentiment: -0.3, posts: 4 },
        ] },
      ] },
    })
    const container = wrapper.find('div.relative')
    container.element.getBoundingClientRect = () => ({ left: 0, top: 0, width: 600, height: 180 })
    await container.trigger('mousemove', { clientX: 300, clientY: 20 })
  })
})

describe('EngagementChart', () => {
  it('renders empty svg when no data', () => {
    const wrapper = mount(EngagementChart, { props: { data: [] } })
    expect(wrapper.find('svg').exists()).toBe(true)
  })

  it('renders bars for active rounds', () => {
    const wrapper = mount(EngagementChart, {
      props: { data: [
        { round: 1, total_posts: 10, total_likes: 5, total_comments: 2, active_agents: 10 },
        { round: 2, total_posts: 0, total_likes: 0, total_comments: 0, active_agents: 0 },
        { round: 3, total_posts: 15, total_likes: 6, total_comments: 3, active_agents: 15 },
      ] },
    })
    // Active data filters out zero-activity rounds
    expect(wrapper.findAll('rect').length).toBeGreaterThan(0)
  })

  it('handles hover interaction', async () => {
    const wrapper = mount(EngagementChart, {
      props: { data: [
        { round: 1, total_posts: 10, total_likes: 5, total_comments: 2, active_agents: 10 },
      ] },
    })
    const container = wrapper.find('div.relative')
    container.element.getBoundingClientRect = () => ({ left: 0, top: 0, width: 600, height: 140 })
    await container.trigger('mousemove', { clientX: 100 })
  })
})

describe('MarketCurveChart', () => {
  it('renders markets with points', () => {
    const wrapper = mount(MarketCurveChart, {
      props: { markets: [{
        market_id: 'm1', question: 'Q?', outcome_a: 'YES', outcome_b: 'NO',
        points: [
          { price_yes: 0.5, price_no: 0.5, volume: 100, trade_idx: 1 },
          { price_yes: 0.6, price_no: 0.4, volume: 120, trade_idx: 2 },
        ],
      }] },
    })
    expect(wrapper.text()).toContain('Q?')
    expect(wrapper.find('path').exists()).toBe(true)
  })

  it('renders single-point market', () => {
    const wrapper = mount(MarketCurveChart, {
      props: { markets: [{
        market_id: 'm1', question: 'Q', outcome_a: 'YES', outcome_b: 'NO',
        points: [{ price_yes: 0.8, price_no: 0.2, volume: 50, trade_idx: 1 }],
      }] },
    })
    expect(wrapper.text()).toContain('Only 1 trade')
  })

  it('handles hover', async () => {
    const wrapper = mount(MarketCurveChart, {
      props: { markets: [{
        market_id: 'm1', question: 'Q', outcome_a: 'YES', outcome_b: 'NO',
        points: [
          { price_yes: 0.5, price_no: 0.5, volume: 100, trade_idx: 1 },
          { price_yes: 0.6, price_no: 0.4, volume: 120, trade_idx: 2 },
        ],
      }] },
    })
    const container = wrapper.find('div.relative')
    container.element.getBoundingClientRect = () => ({ left: 0, top: 0, width: 600, height: 200 })
    await container.trigger('mousemove', { clientX: 300 })
  })

  it('handles empty markets array', () => {
    const wrapper = mount(MarketCurveChart, { props: { markets: [] } })
    expect(wrapper.findAll('svg').length).toBe(0)
  })
})

describe('TopPostsFeed', () => {
  it('shows empty state', () => {
    const wrapper = mount(TopPostsFeed, { props: { posts: [] } })
    expect(wrapper.text()).toContain('No posts available')
  })

  it('renders posts with engagement counts', () => {
    const wrapper = mount(TopPostsFeed, { props: { posts: [
      { post_id: 1, platform: 'twitter', agent_name: 'Alice', content: 'Hello world', num_likes: 42, num_shares: 3, num_dislikes: 1 },
      { post_id: 2, platform: 'reddit', agent_name: 'Bob', content: 'Post 2' },
    ] } })
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('Hello world')
    expect(wrapper.text()).toContain('42')
    expect(wrapper.text()).toContain('Bob')
  })
})

describe('TradeFeed', () => {
  it('shows empty state', () => {
    const wrapper = mount(TradeFeed, { props: { trades: [] } })
    expect(wrapper.text()).toContain('No trades available')
  })

  it('renders trades with BUY/SELL badges', () => {
    const wrapper = mount(TradeFeed, { props: { trades: [
      { trade_id: 1, agent_name: 'Alice', side: 'buy', outcome: 'YES', price: 0.6, cost: 100 },
      { trade_id: 2, agent_name: 'Bob', side: 'sell', outcome: 'NO', price: 0.4, cost: 80 },
    ] } })
    expect(wrapper.text()).toContain('BUY')
    expect(wrapper.text()).toContain('SELL')
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('60%')
    expect(wrapper.text()).toContain('$100')
  })
})

describe('SocialGraphView', () => {
  it('shows empty state with no edges', () => {
    const wrapper = mount(SocialGraphView, { props: { graph: { edges: [], mutual_follows: [] } } })
    expect(wrapper.text()).toContain('No social connections')
  })

  it('renders canvas when edges present', async () => {
    const wrapper = mount(SocialGraphView, {
      props: { graph: {
        edges: [
          { follower_id: 1, follower_name: 'A', followee_id: 2, followee_name: 'B' },
          { follower_id: 2, follower_name: 'B', followee_id: 1, followee_name: 'A' },
        ],
        mutual_follows: [{ agent_a: 1, agent_b: 2 }],
      } },
    })
    await flushPromises()
    expect(wrapper.find('canvas').exists()).toBe(true)
  })
})
