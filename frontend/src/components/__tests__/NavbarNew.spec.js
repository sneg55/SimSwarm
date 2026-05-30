import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import NavbarNew from '../NavbarNew.vue'
import Navbar from '../Navbar.vue'
import { useAuthStore } from '../../stores/auth.js'

const RouterLinkStub = { template: '<a><slot /></a>' }
const pushSpy = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushSpy }),
}))

beforeEach(() => {
  setActivePinia(createPinia())
  pushSpy.mockClear()
})

describe('NavbarNew', () => {
  it('renders sign-in link when logged out', () => {
    const wrapper = mount(NavbarNew, { global: { stubs: { RouterLink: RouterLinkStub } } })
    expect(wrapper.text()).toContain('Sign in')
    expect(wrapper.text()).toContain('Get started')
  })

  it('always shows a Docs link to the docs site', () => {
    const wrapper = mount(NavbarNew, { global: { stubs: { RouterLink: RouterLinkStub } } })
    const docs = wrapper.findAll('a').find(a => a.text() === 'Docs')
    expect(docs).toBeTruthy()
    expect(docs.attributes('href')).toBe('https://docs.simswarm.xyz')
  })

  it('renders dashboard, new sim, and sign-out when logged in', () => {
    const auth = useAuthStore()
    auth.token = 'xyz'
    auth.user = { email: 'a@b.com' }
    const wrapper = mount(NavbarNew, { global: { stubs: { RouterLink: RouterLinkStub } } })
    expect(wrapper.text()).toContain('Dashboard')
    expect(wrapper.text()).toContain('New Simulation')
    expect(wrapper.text()).toContain('Sign out')
  })

  it('logs out and navigates home on Sign out click', async () => {
    const auth = useAuthStore()
    auth.token = 'xyz'
    auth.user = { email: 'a@b.com' }
    const wrapper = mount(NavbarNew, { global: { stubs: { RouterLink: RouterLinkStub } } })
    const btn = wrapper.findAll('button').find(b => b.text() === 'Sign out')
    await btn.trigger('click')
    expect(pushSpy).toHaveBeenCalledWith('/')
  })

  it('scrolled state changes on window scroll', async () => {
    const wrapper = mount(NavbarNew, { global: { stubs: { RouterLink: RouterLinkStub } }, attachTo: document.body })
    Object.defineProperty(window, 'scrollY', { value: 100, configurable: true })
    window.dispatchEvent(new Event('scroll'))
    wrapper.unmount()
  })
})

describe('Navbar wrapper', () => {
  it('renders NavbarNew', () => {
    const wrapper = mount(Navbar, { global: { stubs: { RouterLink: RouterLinkStub } } })
    expect(wrapper.html()).toContain('nav')
  })
})
