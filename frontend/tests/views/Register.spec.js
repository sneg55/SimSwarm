import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('../../src/api/auth.js', () => ({
  register: vi.fn(),
}))

import Register from '../../src/views/Register.vue'
import { register } from '../../src/api/auth.js'

const stubs = { 'router-link': { template: '<a><slot /></a>' } }

describe('Register.vue', () => {
  beforeEach(() => {
    register.mockReset()
  })

  it('renders form', () => {
    const wrapper = mount(Register, { global: { stubs } })
    expect(wrapper.find('input#email').exists()).toBe(true)
    expect(wrapper.find('input#password').exists()).toBe(true)
  })

  it('shows success banner after registration', async () => {
    register.mockResolvedValue({ user: { id: 1 }, token: 't' })
    const wrapper = mount(Register, { global: { stubs } })
    await wrapper.find('input#email').setValue('a@b.c')
    await wrapper.find('input#password').setValue('password123')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.text()).toContain('Account created successfully')
  })

  it('shows error from detail', async () => {
    register.mockRejectedValue({ response: { data: { detail: 'bad email' } } })
    const wrapper = mount(Register, { global: { stubs } })
    await wrapper.find('input#email').setValue('a@b.c')
    await wrapper.find('input#password').setValue('password123')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.text()).toContain('bad email')
  })

  it('shows error from message', async () => {
    register.mockRejectedValue({ response: { data: { message: 'msg err' } } })
    const wrapper = mount(Register, { global: { stubs } })
    await wrapper.find('input#email').setValue('a@b.c')
    await wrapper.find('input#password').setValue('password123')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.text()).toContain('msg err')
  })

  it('shows fallback error', async () => {
    register.mockRejectedValue(new Error('x'))
    const wrapper = mount(Register, { global: { stubs } })
    await wrapper.find('input#email').setValue('a@b.c')
    await wrapper.find('input#password').setValue('password123')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.text()).toContain('Registration failed')
  })
})
