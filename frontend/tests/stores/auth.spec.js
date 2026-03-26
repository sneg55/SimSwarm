import { describe, it, expect } from 'vitest'
import { useAuthStore } from '../../src/stores/auth'

describe('Auth Store', () => {
  it('starts logged out', () => {
    const store = useAuthStore()
    expect(store.isLoggedIn).toBe(false)
  })
  it('sets user and token on login', () => {
    const store = useAuthStore()
    store.setAuth({ id: 'user-1', email: 'test@example.com' }, 'jwt-token-xxx')
    expect(store.isLoggedIn).toBe(true)
    expect(store.user.email).toBe('test@example.com')
  })
  it('clears state on logout', () => {
    const store = useAuthStore()
    store.setAuth({ id: 'user-1', email: 'test@example.com' }, 'jwt-token')
    store.logout()
    expect(store.isLoggedIn).toBe(false)
  })
})
