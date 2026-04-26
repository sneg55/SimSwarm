import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const pushMock = vi.fn()
let mockQuery = {}
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
  useRoute: () => ({ query: mockQuery }),
}))

vi.mock('../../src/api/billing.js', () => ({
  getPacks: vi.fn(),
  getBalance: vi.fn(),
  purchaseCredits: vi.fn(),
  getHistory: vi.fn(),
}))

// AccountSettings renders a child component that imports profile API.
// Stub the child so this view test doesn't need to touch profile state.
import Account from '../../src/views/Account.vue'
import { getPacks, getBalance, purchaseCredits, getHistory } from '../../src/api/billing.js'

const stubs = {
  CreditBadge: true,
  SkeletonCard: true,
  AccountSettings: true,
}

function mkPacks() {
  return [
    { slug: 'starter', credits: 100, price_cents: 1900, description: 'Starter' },
    { slug: 'pro', credits: 500, price_cents: 7900, description: 'Pro' },
  ]
}

describe('Account.vue', () => {
  beforeEach(() => {
    pushMock.mockClear()
    mockQuery = {}
    getPacks.mockReset()
    getBalance.mockReset()
    purchaseCredits.mockReset()
    getHistory.mockReset()
  })

  it('loads account data and renders packs + history', async () => {
    getBalance.mockResolvedValue({ balance: 250 })
    getHistory.mockResolvedValue({ entries: [
      { id: 1, description: 'Purchase', amount: 100, created_at: '2026-01-01T00:00:00Z' },
      { id: 2, description: 'Spent', amount: -30, created_at: '2026-01-02T00:00:00Z' },
    ], total: 2 })
    getPacks.mockResolvedValue(mkPacks())
    const wrapper = mount(Account, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('Credit Balance')
    expect(wrapper.text()).toContain('Purchase')
    expect(wrapper.text()).toContain('+100 credits')
    expect(wrapper.text()).toContain('-30 credits')
    expect(wrapper.text()).toContain('$19')
  })

  it('renders empty history', async () => {
    getBalance.mockResolvedValue({ balance: 0 })
    getHistory.mockResolvedValue({ entries: [], total: 0 })
    getPacks.mockResolvedValue([])
    const wrapper = mount(Account, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('No transactions yet')
  })

  it('handles load failure', async () => {
    getBalance.mockRejectedValue(new Error('x'))
    getHistory.mockRejectedValue(new Error('x'))
    getPacks.mockRejectedValue(new Error('x'))
    const err = vi.spyOn(console, 'error').mockImplementation(() => {})
    const wrapper = mount(Account, { global: { stubs } })
    await flushPromises()
    expect(err).toHaveBeenCalled()
    err.mockRestore()
  })

  it('shows payment success banner from query', async () => {
    mockQuery = { success: '1' }
    getBalance.mockResolvedValue({ balance: 0 })
    getHistory.mockResolvedValue({ entries: [], total: 0 })
    getPacks.mockResolvedValue([])
    const wrapper = mount(Account, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('Payment successful')
  })

  it('shows payment cancelled banner', async () => {
    mockQuery = { cancel: '1' }
    getBalance.mockResolvedValue({ balance: 0 })
    getHistory.mockResolvedValue({ entries: [], total: 0 })
    getPacks.mockResolvedValue([])
    const wrapper = mount(Account, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('Payment was cancelled')
  })

  it('redirects on purchase with checkout_url', async () => {
    getBalance.mockResolvedValue({ balance: 0 })
    getHistory.mockResolvedValue({ entries: [], total: 0 })
    getPacks.mockResolvedValue(mkPacks())
    purchaseCredits.mockResolvedValue({ checkout_url: 'https://stripe/checkout' })
    const hrefSetter = vi.fn()
    Object.defineProperty(window, 'location', {
      value: { get href() { return '' }, set href(v) { hrefSetter(v) } },
      writable: true,
    })
    const wrapper = mount(Account, { global: { stubs } })
    await flushPromises()
    const packBtn = wrapper.findAll('button').find(b => b.text().includes('100'))
    await packBtn.trigger('click')
    await flushPromises()
    expect(hrefSetter).toHaveBeenCalledWith('https://stripe/checkout')
  })

  it('handles purchase success without redirect', async () => {
    vi.useFakeTimers()
    getBalance.mockResolvedValue({ balance: 0 })
    getHistory.mockResolvedValue({ entries: [], total: 0 })
    getPacks.mockResolvedValue(mkPacks())
    purchaseCredits.mockResolvedValue({ balance: 200 })
    const wrapper = mount(Account, { global: { stubs } })
    await flushPromises()
    const packBtn = wrapper.findAll('button').find(b => b.text().includes('100'))
    await packBtn.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Credits purchased successfully')
    vi.advanceTimersByTime(3100)
    vi.useRealTimers()
  })

  it('handles purchase failure', async () => {
    getBalance.mockResolvedValue({ balance: 0 })
    getHistory.mockResolvedValue({ entries: [], total: 0 })
    getPacks.mockResolvedValue(mkPacks())
    purchaseCredits.mockRejectedValue({ response: { data: { detail: 'Card declined' } } })
    const wrapper = mount(Account, { global: { stubs } })
    await flushPromises()
    const packBtn = wrapper.findAll('button').find(b => b.text().includes('100'))
    await packBtn.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Card declined')
  })

  it('purchase fallback error', async () => {
    getBalance.mockResolvedValue({ balance: 0 })
    getHistory.mockResolvedValue({ entries: [], total: 0 })
    getPacks.mockResolvedValue(mkPacks())
    purchaseCredits.mockRejectedValue(new Error('x'))
    const wrapper = mount(Account, { global: { stubs } })
    await flushPromises()
    const packBtn = wrapper.findAll('button').find(b => b.text().includes('100'))
    await packBtn.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Purchase failed')
  })

  it('supports non-wrapped balance shape', async () => {
    getBalance.mockResolvedValue(77)
    getHistory.mockResolvedValue({ entries: [{ id: 9, description: 'legacy', amount: 1, created_at: null }], total: 1 })
    getPacks.mockResolvedValue([])
    const wrapper = mount(Account, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('legacy')
  })

  it('renders Load more button and appends second page', async () => {
    getBalance.mockResolvedValue({ balance: 0 })
    getPacks.mockResolvedValue([])
    getHistory.mockResolvedValueOnce({
      entries: [{ id: 1, description: 'first page', amount: 10, created_at: '2026-01-01' }],
      total: 2,
    }).mockResolvedValueOnce({
      entries: [{ id: 2, description: 'second page', amount: 20, created_at: '2026-01-02' }],
      total: 2,
    })

    const wrapper = mount(Account, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('first page')
    expect(wrapper.text()).not.toContain('second page')
    expect(wrapper.text()).toContain('Showing 1 of 2')

    const loadMore = wrapper.findAll('button').find(b => b.text().includes('Load more'))
    expect(loadMore).toBeTruthy()
    await loadMore.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('first page')
    expect(wrapper.text()).toContain('second page')
    // Both pages now shown — Load more disappears
    const stillThere = wrapper.findAll('button').find(b => b.text().includes('Load more'))
    expect(stillThere).toBeFalsy()
    // Second call used offset=1
    expect(getHistory).toHaveBeenLastCalledWith({ limit: 20, offset: 1 })
  })
})
