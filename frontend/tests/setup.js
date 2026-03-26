import { config } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// Mock localStorage for jsdom
const storage = {}
global.localStorage = {
  getItem: (key) => storage[key] ?? null,
  setItem: (key, value) => { storage[key] = String(value) },
  removeItem: (key) => { delete storage[key] },
  clear: () => { Object.keys(storage).forEach(k => delete storage[k]) },
}

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
})
