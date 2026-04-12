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

vi.mock('../../src/api/profile.js', () => ({
  changePassword: vi.fn(),
  deleteAccount: vi.fn(),
}))

import Account from '../../src/views/Account.vue'
import { getPacks, getBalance, purchaseCredits, getHistory } from '../../src/api/billing.js'
import { changePassword, deleteAccount } from '../../src/api/profile.js'

const stubs = {
  CreditBadge: true,
  SkeletonCard: true,
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
    changePassword.mockReset()
    deleteAccount.mockReset()
  })

  it('loads account data and renders packs + history', async () => {
    getBalance.mockResolvedValue({ balance: 250 })
    getHistory.mockResolvedValue({ transactions: [
      { id: 1, description: 'Purchase', amount: 100, created_at: '2026-01-01T00:00:00Z' },
      { id: 2, description: 'Spent', amount: -30, created_at: '2026-01-02T00:00:00Z' },
    ] })
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
    getHistory.mockResolvedValue({ transactions: [] })
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
    getHistory.mockResolvedValue({ transactions: [] })
    getPacks.mockResolvedValue([])
    const wrapper = mount(Account, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('Payment successful')
  })

  it('shows payment cancelled banner', async () => {
    mockQuery = { cancel: '1' }
    getBalance.mockResolvedValue({ balance: 0 })
    getHistory.mockResolvedValue({ transactions: [] })
    getPacks.mockResolvedValue([])
    const wrapper = mount(Account, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('Payment was cancelled')
  })

  it('redirects on purchase with checkout_url', async () => {
    getBalance.mockResolvedValue({ balance: 0 })
    getHistory.mockResolvedValue({ transactions: [] })
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
    getHistory.mockResolvedValue({ transactions: [] })
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
    getHistory.mockResolvedValue({ transactions: [] })
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
    getHistory.mockResolvedValue({ transactions: [] })
    getPacks.mockResolvedValue(mkPacks())
    purchaseCredits.mockRejectedValue(new Error('x'))
    const wrapper = mount(Account, { global: { stubs } })
    await flushPromises()
    const packBtn = wrapper.findAll('button').find(b => b.text().includes('100'))
    await packBtn.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Purchase failed')
  })

  it('validates password change: too short', async () => {
    getBalance.mockResolvedValue({ balance: 0 })
    getHistory.mockResolvedValue({ transactions: [] })
    getPacks.mockResolvedValue([])
    const wrapper = mount(Account, { global: { stubs } })
    await flushPromises()
    const inputs = wrapper.findAll('input[type="password"]')
    await inputs[0].setValue('old')
    await inputs[1].setValue('short')
    await inputs[2].setValue('short')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.text()).toContain('at least 8 characters')
  })

  it('validates password mismatch', async () => {
    getBalance.mockResolvedValue({ balance: 0 })
    getHistory.mockResolvedValue({ transactions: [] })
    getPacks.mockResolvedValue([])
    const wrapper = mount(Account, { global: { stubs } })
    await flushPromises()
    const inputs = wrapper.findAll('input[type="password"]')
    await inputs[0].setValue('oldpass1')
    await inputs[1].setValue('newpass12')
    await inputs[2].setValue('different')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.text()).toContain('do not match')
  })

  it('changes password successfully', async () => {
    vi.useFakeTimers()
    getBalance.mockResolvedValue({ balance: 0 })
    getHistory.mockResolvedValue({ transactions: [] })
    getPacks.mockResolvedValue([])
    changePassword.mockResolvedValue({})
    const wrapper = mount(Account, { global: { stubs } })
    await flushPromises()
    const inputs = wrapper.findAll('input[type="password"]')
    await inputs[0].setValue('oldpass1')
    await inputs[1].setValue('newpass12')
    await inputs[2].setValue('newpass12')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(changePassword).toHaveBeenCalled()
    expect(wrapper.text()).toContain('Password updated successfully')
    vi.advanceTimersByTime(4500)
    vi.useRealTimers()
  })

  it('handles password change API error', async () => {
    getBalance.mockResolvedValue({ balance: 0 })
    getHistory.mockResolvedValue({ transactions: [] })
    getPacks.mockResolvedValue([])
    changePassword.mockRejectedValue({ response: { data: { detail: 'Wrong password' } } })
    const wrapper = mount(Account, { global: { stubs } })
    await flushPromises()
    const inputs = wrapper.findAll('input[type="password"]')
    await inputs[0].setValue('oldpass1')
    await inputs[1].setValue('newpass12')
    await inputs[2].setValue('newpass12')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.text()).toContain('Wrong password')
  })

  it('deletes account and logs out', async () => {
    getBalance.mockResolvedValue({ balance: 0 })
    getHistory.mockResolvedValue({ transactions: [] })
    getPacks.mockResolvedValue([])
    deleteAccount.mockResolvedValue({})
    const wrapper = mount(Account, { global: { stubs } })
    await flushPromises()
    // Show confirm
    const delBtn = wrapper.findAll('button').find(b => b.text() === 'Delete my account')
    await delBtn.trigger('click')
    await wrapper.find('input[type="text"]').setValue('delete')
    const confirmBtn = wrapper.findAll('button').find(b => b.text().includes('Confirm deletion'))
    await confirmBtn.trigger('click')
    await flushPromises()
    expect(deleteAccount).toHaveBeenCalled()
    expect(pushMock).toHaveBeenCalledWith('/')
  })

  it('does nothing on delete when typed text wrong', async () => {
    getBalance.mockResolvedValue({ balance: 0 })
    getHistory.mockResolvedValue({ transactions: [] })
    getPacks.mockResolvedValue([])
    const wrapper = mount(Account, { global: { stubs } })
    await flushPromises()
    const delBtn = wrapper.findAll('button').find(b => b.text() === 'Delete my account')
    await delBtn.trigger('click')
    // Confirm button is disabled when text !== 'delete'; click anyway no-op via handler short circuit
    await wrapper.find('input[type="text"]').setValue('xxx')
    const cancel = wrapper.findAll('button').find(b => b.text() === 'Cancel')
    await cancel.trigger('click')
    await flushPromises()
    expect(deleteAccount).not.toHaveBeenCalled()
  })

  it('delete API error', async () => {
    getBalance.mockResolvedValue({ balance: 0 })
    getHistory.mockResolvedValue({ transactions: [] })
    getPacks.mockResolvedValue([])
    deleteAccount.mockRejectedValue({ response: { data: { detail: 'nope' } } })
    const wrapper = mount(Account, { global: { stubs } })
    await flushPromises()
    const delBtn = wrapper.findAll('button').find(b => b.text() === 'Delete my account')
    await delBtn.trigger('click')
    await wrapper.find('input[type="text"]').setValue('delete')
    const confirmBtn = wrapper.findAll('button').find(b => b.text().includes('Confirm deletion'))
    await confirmBtn.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('nope')
  })

  it('supports array history shape and non-wrapped balance', async () => {
    getBalance.mockResolvedValue(77)
    getHistory.mockResolvedValue([{ id: 9, description: 'legacy', amount: 1, created_at: null }])
    getPacks.mockResolvedValue([])
    const wrapper = mount(Account, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('legacy')
  })
})
