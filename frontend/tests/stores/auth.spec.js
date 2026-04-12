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
  it('loadFromStorage hydrates when token and user present', () => {
    localStorage.setItem('auth_token', 'stored-jwt')
    localStorage.setItem('auth_user', JSON.stringify({ id: 'u-2', email: 'stored@example.com' }))
    const store = useAuthStore()
    store.loadFromStorage()
    expect(store.token).toBe('stored-jwt')
    expect(store.user.email).toBe('stored@example.com')
    expect(store.isLoggedIn).toBe(true)
  })
  it('loadFromStorage is a no-op when storage is empty', () => {
    const store = useAuthStore()
    store.loadFromStorage()
    expect(store.isLoggedIn).toBe(false)
  })
  it('loadFromStorage is a no-op when only token is set', () => {
    localStorage.setItem('auth_token', 'only-token')
    const store = useAuthStore()
    store.loadFromStorage()
    expect(store.isLoggedIn).toBe(false)
  })
})
