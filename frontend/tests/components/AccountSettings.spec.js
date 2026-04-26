import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const pushMock = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
}))

vi.mock('../../src/api/profile.js', () => ({
  changePassword: vi.fn(),
  deleteAccount: vi.fn(),
}))

import AccountSettings from '../../src/components/AccountSettings.vue'
import { changePassword, deleteAccount } from '../../src/api/profile.js'

describe('AccountSettings — password change', () => {
  beforeEach(() => {
    pushMock.mockClear()
    changePassword.mockReset()
    deleteAccount.mockReset()
  })

  it('rejects new password under 8 characters', async () => {
    const wrapper = mount(AccountSettings)
    const inputs = wrapper.findAll('input[type="password"]')
    await inputs[0].setValue('old')
    await inputs[1].setValue('short')
    await inputs[2].setValue('short')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.text()).toContain('at least 8 characters')
    expect(changePassword).not.toHaveBeenCalled()
  })

  it('rejects mismatched confirmation', async () => {
    const wrapper = mount(AccountSettings)
    const inputs = wrapper.findAll('input[type="password"]')
    await inputs[0].setValue('oldpass1')
    await inputs[1].setValue('newpass12')
    await inputs[2].setValue('different')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.text()).toContain('do not match')
    expect(changePassword).not.toHaveBeenCalled()
  })

  it('submits valid change and shows success', async () => {
    vi.useFakeTimers()
    changePassword.mockResolvedValue({})
    const wrapper = mount(AccountSettings)
    const inputs = wrapper.findAll('input[type="password"]')
    await inputs[0].setValue('oldpass1')
    await inputs[1].setValue('newpass12')
    await inputs[2].setValue('newpass12')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(changePassword).toHaveBeenCalledWith('oldpass1', 'newpass12')
    expect(wrapper.text()).toContain('Password updated successfully')
    vi.advanceTimersByTime(4500)
    vi.useRealTimers()
  })

  it('surfaces API error', async () => {
    changePassword.mockRejectedValue({ response: { data: { detail: 'Wrong password' } } })
    const wrapper = mount(AccountSettings)
    const inputs = wrapper.findAll('input[type="password"]')
    await inputs[0].setValue('oldpass1')
    await inputs[1].setValue('newpass12')
    await inputs[2].setValue('newpass12')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.text()).toContain('Wrong password')
  })
})

describe('AccountSettings — delete account', () => {
  beforeEach(() => {
    pushMock.mockClear()
    deleteAccount.mockReset()
  })

  it('deletes and redirects on confirmed flow', async () => {
    deleteAccount.mockResolvedValue({})
    const wrapper = mount(AccountSettings)
    const delBtn = wrapper.findAll('button').find(b => b.text() === 'Delete my account')
    await delBtn.trigger('click')
    await wrapper.find('input[type="text"]').setValue('delete')
    const confirmBtn = wrapper.findAll('button').find(b => b.text().includes('Confirm deletion'))
    await confirmBtn.trigger('click')
    await flushPromises()
    expect(deleteAccount).toHaveBeenCalled()
    expect(pushMock).toHaveBeenCalledWith('/')
  })

  it('cancels flow without calling deleteAccount', async () => {
    const wrapper = mount(AccountSettings)
    const delBtn = wrapper.findAll('button').find(b => b.text() === 'Delete my account')
    await delBtn.trigger('click')
    await wrapper.find('input[type="text"]').setValue('xxx')
    const cancel = wrapper.findAll('button').find(b => b.text() === 'Cancel')
    await cancel.trigger('click')
    await flushPromises()
    expect(deleteAccount).not.toHaveBeenCalled()
  })

  it('surfaces delete error', async () => {
    deleteAccount.mockRejectedValue({ response: { data: { detail: 'nope' } } })
    const wrapper = mount(AccountSettings)
    const delBtn = wrapper.findAll('button').find(b => b.text() === 'Delete my account')
    await delBtn.trigger('click')
    await wrapper.find('input[type="text"]').setValue('delete')
    const confirmBtn = wrapper.findAll('button').find(b => b.text().includes('Confirm deletion'))
    await confirmBtn.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('nope')
  })
})
