import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const pushMock = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
}))

vi.mock('../../src/api/auth.js', () => ({
  login: vi.fn(),
}))

import Login from '../../src/views/Login.vue'
import { login } from '../../src/api/auth.js'

const stubs = { 'router-link': { template: '<a><slot /></a>' } }

describe('Login.vue', () => {
  beforeEach(() => {
    pushMock.mockClear()
    login.mockReset()
  })

  it('renders email and password inputs', () => {
    const wrapper = mount(Login, { global: { stubs } })
    expect(wrapper.find('input#email').exists()).toBe(true)
    expect(wrapper.find('input#password').exists()).toBe(true)
    expect(wrapper.text()).toContain('Sign in to SimSwarm')
  })

  it('submits form and redirects on success', async () => {
    login.mockResolvedValue({ user: { id: 1, email: 'a@b.c' }, token: 'tok' })
    const wrapper = mount(Login, { global: { stubs } })
    await wrapper.find('input#email').setValue('a@b.c')
    await wrapper.find('input#password').setValue('pw12345678')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(login).toHaveBeenCalledWith('a@b.c', 'pw12345678')
    expect(pushMock).toHaveBeenCalledWith('/dashboard')
  })

  it('shows server error message on failure', async () => {
    login.mockRejectedValue({ response: { data: { message: 'Bad creds' } } })
    const wrapper = mount(Login, { global: { stubs } })
    await wrapper.find('input#email').setValue('x@y.z')
    await wrapper.find('input#password').setValue('wrong')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.text()).toContain('Bad creds')
  })

  it('shows fallback error when response has none', async () => {
    login.mockRejectedValue(new Error('boom'))
    const wrapper = mount(Login, { global: { stubs } })
    await wrapper.find('input#email').setValue('x@y.z')
    await wrapper.find('input#password').setValue('wrong')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.text()).toContain('Login failed')
  })
})
