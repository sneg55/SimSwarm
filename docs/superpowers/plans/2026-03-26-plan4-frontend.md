# Plan 4: Frontend — Auth, Dashboard, Simulation Flow

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fork the MiroFish Vue.js frontend, add auth (email+password), credit balance display, Stripe checkout integration, simulation creation flow with tier selection, results dashboard, and account management.

**Architecture:** Fork the existing MiroFish Vue 3 + Vite frontend. Add new views/components for auth, billing, and account. Restyle with Tailwind CSS. All data flows through the FastAPI SaaS API (not the MiroFish Flask backend directly).

**Tech Stack:** Vue 3, Vite, Vue Router, Axios, Tailwind CSS, Pinia (state management)

**Depends on:** Plan 1 (API skeleton), Plan 2 (billing API)

**Spec reference:** `docs/superpowers/specs/2026-03-26-mirofish-hosted-mvp-design.md` — Section 3 (User Flows)

---

## File Structure

```
frontend/
├── package.json
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
├── index.html
├── src/
│   ├── main.js
│   ├── App.vue
│   ├── router/
│   │   └── index.js               # Routes: /, /login, /register, /dashboard, /sim/new, /sim/:id, /account
│   ├── stores/
│   │   ├── auth.js                 # Auth state (Pinia)
│   │   └── credits.js              # Credit balance state (Pinia)
│   ├── api/
│   │   ├── index.js                # Axios instance -> SaaS API
│   │   ├── auth.js                 # Login/register/logout
│   │   ├── billing.js              # Balance, purchase, history
│   │   ├── jobs.js                 # Create sim, get status, list
│   │   └── demos.js                # Public demo data fetch
│   ├── views/
│   │   ├── Landing.vue             # Marketing page + demo links
│   │   ├── Login.vue               # Email + password login
│   │   ├── Register.vue            # Email + password registration
│   │   ├── Dashboard.vue           # Job list + credit balance + new sim CTA
│   │   ├── NewSimulation.vue       # Seed upload + goal + tier select + run
│   │   ├── SimulationStatus.vue    # Live progress (pipeline stage)
│   │   ├── SimulationResults.vue   # Report + chat replay + export
│   │   └── Account.vue             # Credit balance, buy more, job history
│   ├── components/
│   │   ├── Navbar.vue              # Nav with credit balance badge
│   │   ├── CreditBadge.vue         # Balance display in nav
│   │   ├── CreditWarning.vue       # Low-credit warning banner
│   │   ├── TierSelector.vue        # Small/Medium/Large with cost preview
│   │   ├── SeedUploader.vue        # Drag & drop + paste
│   │   ├── PipelineProgress.vue    # 5-step progress indicator
│   │   ├── ReportViewer.vue        # Markdown report renderer
│   │   ├── ChatReplay.vue          # Scrollable agent chat log
│   │   └── ExportButtons.vue       # PDF/JSON/CSV export
│   └── assets/
│       └── styles.css              # Tailwind imports
├── tests/
│   ├── setup.js                    # Test setup (vitest + vue-test-utils)
│   ├── components/
│   │   ├── CreditBadge.spec.js
│   │   ├── TierSelector.spec.js
│   │   ├── SeedUploader.spec.js
│   │   ├── PipelineProgress.spec.js
│   │   └── ChatReplay.spec.js
│   ├── views/
│   │   ├── Login.spec.js
│   │   ├── Dashboard.spec.js
│   │   └── NewSimulation.spec.js
│   └── stores/
│       ├── auth.spec.js
│       └── credits.spec.js
```

---

### Task 1: Fork Frontend + Tailwind Setup

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/src/assets/styles.css`
- Create: `frontend/vite.config.js`

- [ ] **Step 1: Copy MiroFish frontend and install Tailwind**

```bash
cp -r vendor/mirofish/frontend/ frontend/
cd frontend
npm install
npm install -D tailwindcss @tailwindcss/typography postcss autoprefixer
npm install pinia axios vue-router@4
npm install -D vitest @vue/test-utils jsdom @vitejs/plugin-vue
npx tailwindcss init -p
```

- [ ] **Step 2: Configure Tailwind**

```js
// frontend/tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
```

```css
/* frontend/src/assets/styles.css */
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 3: Update vite.config.js**

```js
// frontend/vite.config.js
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',  // SaaS FastAPI, not MiroFish Flask
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.js'],
  },
})
```

- [ ] **Step 4: Create test setup**

```js
// frontend/tests/setup.js
import { config } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// Reset pinia before each test
beforeEach(() => {
  setActivePinia(createPinia())
})
```

- [ ] **Step 5: Add test script to package.json**

Add to `frontend/package.json` scripts:

```json
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Step 6: Verify Tailwind builds**

```bash
cd frontend && npm run build
```

Expected: Builds without errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/
git commit -m "feat: fork MiroFish frontend, add Tailwind and test infrastructure"
```

---

### Task 2: Auth Store + Login/Register Views

**Files:**
- Create: `frontend/src/stores/auth.js`
- Create: `frontend/src/api/index.js`
- Create: `frontend/src/api/auth.js`
- Create: `frontend/src/views/Login.vue`
- Create: `frontend/src/views/Register.vue`
- Create: `frontend/tests/stores/auth.spec.js`
- Create: `frontend/tests/views/Login.spec.js`

- [ ] **Step 1: Write auth store tests**

```js
// frontend/tests/stores/auth.spec.js
import { describe, it, expect, vi } from 'vitest'
import { useAuthStore } from '../../src/stores/auth'

describe('Auth Store', () => {
  it('starts logged out', () => {
    const store = useAuthStore()
    expect(store.isLoggedIn).toBe(false)
    expect(store.user).toBe(null)
    expect(store.token).toBe(null)
  })

  it('sets user and token on login', () => {
    const store = useAuthStore()
    store.setAuth({ id: 'user-1', email: 'test@example.com' }, 'jwt-token-xxx')
    expect(store.isLoggedIn).toBe(true)
    expect(store.user.email).toBe('test@example.com')
    expect(store.token).toBe('jwt-token-xxx')
  })

  it('clears state on logout', () => {
    const store = useAuthStore()
    store.setAuth({ id: 'user-1', email: 'test@example.com' }, 'jwt-token')
    store.logout()
    expect(store.isLoggedIn).toBe(false)
    expect(store.user).toBe(null)
    expect(store.token).toBe(null)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npx vitest run tests/stores/auth.spec.js
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement auth store**

```js
// frontend/src/stores/auth.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const token = ref(null)

  const isLoggedIn = computed(() => !!token.value)

  function setAuth(userData, tokenValue) {
    user.value = userData
    token.value = tokenValue
    localStorage.setItem('token', tokenValue)
  }

  function logout() {
    user.value = null
    token.value = null
    localStorage.removeItem('token')
  }

  function loadFromStorage() {
    const stored = localStorage.getItem('token')
    if (stored) {
      token.value = stored
    }
  }

  return { user, token, isLoggedIn, setAuth, logout, loadFromStorage }
})
```

- [ ] **Step 4: Implement API client**

```js
// frontend/src/api/index.js
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export default api
```

```js
// frontend/src/api/auth.js
import api from './index'

export async function login(email, password) {
  const { data } = await api.post('/auth/login', { email, password })
  return data
}

export async function register(email, password) {
  const { data } = await api.post('/auth/register', { email, password })
  return data
}
```

- [ ] **Step 5: Implement Login view**

```vue
<!-- frontend/src/views/Login.vue -->
<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50">
    <div class="max-w-md w-full space-y-8 p-8 bg-white rounded-lg shadow">
      <h2 class="text-center text-3xl font-bold text-gray-900">Sign in to FishCloud</h2>

      <form @submit.prevent="handleLogin" class="space-y-6">
        <div v-if="error" class="bg-red-50 text-red-700 p-3 rounded">{{ error }}</div>

        <div>
          <label for="email" class="block text-sm font-medium text-gray-700">Email</label>
          <input id="email" v-model="email" type="email" required
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500" />
        </div>

        <div>
          <label for="password" class="block text-sm font-medium text-gray-700">Password</label>
          <input id="password" v-model="password" type="password" required
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500" />
        </div>

        <button type="submit" :disabled="loading"
          class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50">
          {{ loading ? 'Signing in...' : 'Sign in' }}
        </button>
      </form>

      <p class="text-center text-sm text-gray-600">
        No account? <router-link to="/register" class="text-blue-600 hover:text-blue-500">Sign up</router-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { login } from '../api/auth'

const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const router = useRouter()
const authStore = useAuthStore()

async function handleLogin() {
  loading.value = true
  error.value = ''
  try {
    const data = await login(email.value, password.value)
    authStore.setAuth(data.user, data.token)
    router.push('/dashboard')
  } catch (e) {
    error.value = e.response?.data?.detail || 'Login failed'
  } finally {
    loading.value = false
  }
}
</script>
```

- [ ] **Step 6: Implement Register view**

```vue
<!-- frontend/src/views/Register.vue -->
<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50">
    <div class="max-w-md w-full space-y-8 p-8 bg-white rounded-lg shadow">
      <h2 class="text-center text-3xl font-bold text-gray-900">Create your FishCloud account</h2>

      <form @submit.prevent="handleRegister" class="space-y-6">
        <div v-if="error" class="bg-red-50 text-red-700 p-3 rounded">{{ error }}</div>

        <div>
          <label for="email" class="block text-sm font-medium text-gray-700">Email</label>
          <input id="email" v-model="email" type="email" required
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500" />
        </div>

        <div>
          <label for="password" class="block text-sm font-medium text-gray-700">Password</label>
          <input id="password" v-model="password" type="password" required minlength="8"
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500" />
        </div>

        <button type="submit" :disabled="loading"
          class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50">
          {{ loading ? 'Creating account...' : 'Create account' }}
        </button>
      </form>

      <p class="text-center text-sm text-gray-600">
        Have an account? <router-link to="/login" class="text-blue-600 hover:text-blue-500">Sign in</router-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { register } from '../api/auth'

const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const router = useRouter()
const authStore = useAuthStore()

async function handleRegister() {
  loading.value = true
  error.value = ''
  try {
    const data = await register(email.value, password.value)
    authStore.setAuth(data.user, data.token)
    router.push('/dashboard')
  } catch (e) {
    error.value = e.response?.data?.detail || 'Registration failed'
  } finally {
    loading.value = false
  }
}
</script>
```

- [ ] **Step 7: Write Login view test**

```js
// frontend/tests/views/Login.spec.js
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import Login from '../../src/views/Login.vue'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/login', component: Login },
    { path: '/dashboard', component: { template: '<div>Dashboard</div>' } },
    { path: '/register', component: { template: '<div>Register</div>' } },
  ],
})

describe('Login View', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders login form', () => {
    const wrapper = mount(Login, {
      global: { plugins: [router] },
    })
    expect(wrapper.find('h2').text()).toContain('Sign in')
    expect(wrapper.find('input[type="email"]').exists()).toBe(true)
    expect(wrapper.find('input[type="password"]').exists()).toBe(true)
    expect(wrapper.find('button[type="submit"]').text()).toContain('Sign in')
  })

  it('has link to register page', () => {
    const wrapper = mount(Login, {
      global: { plugins: [router] },
    })
    expect(wrapper.find('a[href="/register"]').exists()).toBe(true)
  })

  it('disables button while loading', async () => {
    const wrapper = mount(Login, {
      global: { plugins: [router] },
    })
    // Simulate loading state
    wrapper.vm.loading = true
    await wrapper.vm.$nextTick()
    expect(wrapper.find('button').attributes('disabled')).toBeDefined()
  })
})
```

- [ ] **Step 8: Run tests**

```bash
cd frontend && npx vitest run
```

Expected: 6 passed (auth store 3, login view 3).

- [ ] **Step 9: Commit**

```bash
git add frontend/src/stores/auth.js frontend/src/api/ frontend/src/views/Login.vue frontend/src/views/Register.vue frontend/tests/
git commit -m "feat: add auth store, login/register views with Tailwind"
```

---

### Task 3: Credits Store + CreditBadge + TierSelector Components

**Files:**
- Create: `frontend/src/stores/credits.js`
- Create: `frontend/src/api/billing.js`
- Create: `frontend/src/components/CreditBadge.vue`
- Create: `frontend/src/components/CreditWarning.vue`
- Create: `frontend/src/components/TierSelector.vue`
- Create: `frontend/tests/stores/credits.spec.js`
- Create: `frontend/tests/components/CreditBadge.spec.js`
- Create: `frontend/tests/components/TierSelector.spec.js`

- [ ] **Step 1: Write credits store tests**

```js
// frontend/tests/stores/credits.spec.js
import { describe, it, expect } from 'vitest'
import { useCreditsStore } from '../../src/stores/credits'

describe('Credits Store', () => {
  it('starts with zero balance', () => {
    const store = useCreditsStore()
    expect(store.balance).toBe(0)
  })

  it('sets balance', () => {
    const store = useCreditsStore()
    store.setBalance(500)
    expect(store.balance).toBe(500)
  })

  it('detects low balance', () => {
    const store = useCreditsStore()
    store.setBalance(20)
    expect(store.isLow).toBe(true)
  })

  it('not low when above threshold', () => {
    const store = useCreditsStore()
    store.setBalance(100)
    expect(store.isLow).toBe(false)
  })

  it('detects insufficient for tier', () => {
    const store = useCreditsStore()
    store.setBalance(50)
    expect(store.canAfford('small')).toBe(true)   // 30
    expect(store.canAfford('medium')).toBe(false)  // 90
    expect(store.canAfford('large')).toBe(false)   // 300
  })
})
```

- [ ] **Step 2: Implement credits store**

```js
// frontend/src/stores/credits.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const TIER_COSTS = { small: 30, medium: 90, large: 300 }
const LOW_THRESHOLD = 30

export const useCreditsStore = defineStore('credits', () => {
  const balance = ref(0)
  const isLow = computed(() => balance.value < LOW_THRESHOLD)

  function setBalance(value) {
    balance.value = value
  }

  function canAfford(tier) {
    return balance.value >= (TIER_COSTS[tier] || Infinity)
  }

  function getTierCost(tier) {
    return TIER_COSTS[tier] || 0
  }

  return { balance, isLow, setBalance, canAfford, getTierCost }
})
```

```js
// frontend/src/api/billing.js
import api from './index'

export async function getBalance(userId) {
  const { data } = await api.get('/billing/balance', { params: { user_id: userId } })
  return data
}

export async function purchaseCredits(userId, packId) {
  const { data } = await api.post('/billing/purchase', { user_id: userId, pack_id: packId })
  return data
}

export async function getHistory(userId) {
  const { data } = await api.get('/billing/history', { params: { user_id: userId } })
  return data
}
```

- [ ] **Step 3: Write CreditBadge test**

```js
// frontend/tests/components/CreditBadge.spec.js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import CreditBadge from '../../src/components/CreditBadge.vue'
import { useCreditsStore } from '../../src/stores/credits'

describe('CreditBadge', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('shows credit balance', () => {
    const store = useCreditsStore()
    store.setBalance(250)
    const wrapper = mount(CreditBadge)
    expect(wrapper.text()).toContain('250')
  })

  it('shows warning style when low', () => {
    const store = useCreditsStore()
    store.setBalance(10)
    const wrapper = mount(CreditBadge)
    expect(wrapper.find('.text-red-600').exists() || wrapper.find('.bg-red-50').exists()).toBe(true)
  })
})
```

- [ ] **Step 4: Implement CreditBadge**

```vue
<!-- frontend/src/components/CreditBadge.vue -->
<template>
  <div :class="[
    'flex items-center gap-1 px-3 py-1 rounded-full text-sm font-medium',
    creditsStore.isLow ? 'bg-red-50 text-red-600' : 'bg-blue-50 text-blue-700'
  ]">
    <span>{{ creditsStore.balance }} credits</span>
  </div>
</template>

<script setup>
import { useCreditsStore } from '../stores/credits'
const creditsStore = useCreditsStore()
</script>
```

- [ ] **Step 5: Write TierSelector test**

```js
// frontend/tests/components/TierSelector.spec.js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import TierSelector from '../../src/components/TierSelector.vue'
import { useCreditsStore } from '../../src/stores/credits'

describe('TierSelector', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('renders three tiers', () => {
    const store = useCreditsStore()
    store.setBalance(500)
    const wrapper = mount(TierSelector)
    expect(wrapper.findAll('[data-tier]').length).toBe(3)
  })

  it('shows credit cost per tier', () => {
    const store = useCreditsStore()
    store.setBalance(500)
    const wrapper = mount(TierSelector)
    expect(wrapper.text()).toContain('30 credits')
    expect(wrapper.text()).toContain('90 credits')
    expect(wrapper.text()).toContain('300 credits')
  })

  it('disables tiers user cannot afford', () => {
    const store = useCreditsStore()
    store.setBalance(50)  // can only afford small
    const wrapper = mount(TierSelector)
    const mediumBtn = wrapper.find('[data-tier="medium"]')
    expect(mediumBtn.attributes('disabled')).toBeDefined()
  })

  it('emits selected tier on click', async () => {
    const store = useCreditsStore()
    store.setBalance(500)
    const wrapper = mount(TierSelector)
    await wrapper.find('[data-tier="medium"]').trigger('click')
    expect(wrapper.emitted('select')[0]).toEqual(['medium'])
  })
})
```

- [ ] **Step 6: Implement TierSelector**

```vue
<!-- frontend/src/components/TierSelector.vue -->
<template>
  <div class="grid grid-cols-3 gap-4">
    <button
      v-for="tier in tiers"
      :key="tier.id"
      :data-tier="tier.id"
      :disabled="!creditsStore.canAfford(tier.id)"
      :class="[
        'p-4 rounded-lg border-2 text-center transition',
        selected === tier.id ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300',
        !creditsStore.canAfford(tier.id) ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer',
      ]"
      @click="selectTier(tier.id)"
    >
      <div class="text-lg font-bold">{{ tier.label }}</div>
      <div class="text-sm text-gray-500">{{ tier.agents }}</div>
      <div class="mt-2 font-medium text-blue-600">{{ tier.cost }} credits</div>
      <div class="text-xs text-gray-400">{{ tier.estimate }}</div>
    </button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useCreditsStore } from '../stores/credits'

const emit = defineEmits(['select'])
const creditsStore = useCreditsStore()
const selected = ref(null)

const tiers = [
  { id: 'small', label: 'Small', agents: '1-500 agents', cost: 30, estimate: '< 30 min' },
  { id: 'medium', label: 'Medium', agents: '501-2,000 agents', cost: 90, estimate: '< 4 hours' },
  { id: 'large', label: 'Large', agents: '2,001-10,000 agents', cost: 300, estimate: '< 12 hours' },
]

function selectTier(id) {
  if (creditsStore.canAfford(id)) {
    selected.value = id
    emit('select', id)
  }
}
</script>
```

- [ ] **Step 7: Run all frontend tests**

```bash
cd frontend && npx vitest run
```

Expected: 17 passed (auth store 3, login view 3, credits store 5, credit badge 2, tier selector 4).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/stores/credits.js frontend/src/api/billing.js frontend/src/components/CreditBadge.vue frontend/src/components/CreditWarning.vue frontend/src/components/TierSelector.vue frontend/tests/
git commit -m "feat: add credits store, CreditBadge, and TierSelector components"
```

---

### Task 4: Dashboard + New Simulation + Results Views

**Files:**
- Create: `frontend/src/api/jobs.js`
- Create: `frontend/src/views/Dashboard.vue`
- Create: `frontend/src/views/NewSimulation.vue`
- Create: `frontend/src/views/SimulationStatus.vue`
- Create: `frontend/src/views/SimulationResults.vue`
- Create: `frontend/src/components/SeedUploader.vue`
- Create: `frontend/src/components/PipelineProgress.vue`
- Create: `frontend/src/components/ReportViewer.vue`
- Create: `frontend/src/components/ChatReplay.vue`
- Create: `frontend/src/components/ExportButtons.vue`
- Create: `frontend/tests/components/PipelineProgress.spec.js`
- Create: `frontend/tests/components/ChatReplay.spec.js`
- Create: `frontend/tests/views/Dashboard.spec.js`
- Create: `frontend/tests/views/NewSimulation.spec.js`

- [ ] **Step 1: Implement jobs API client**

```js
// frontend/src/api/jobs.js
import api from './index'

export async function createJob(userId, seedText, goal, tier) {
  const { data } = await api.post('/jobs', {
    user_id: userId,
    seed_text: seedText,
    goal,
    tier,
  })
  return data
}

export async function getJob(jobId) {
  const { data } = await api.get(`/jobs/${jobId}`)
  return data
}

export async function listJobs(userId) {
  const { data } = await api.get('/jobs', { params: { user_id: userId } })
  return data
}
```

- [ ] **Step 2: Write PipelineProgress test**

```js
// frontend/tests/components/PipelineProgress.spec.js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PipelineProgress from '../../src/components/PipelineProgress.vue'

describe('PipelineProgress', () => {
  it('renders 5 pipeline steps', () => {
    const wrapper = mount(PipelineProgress, { props: { currentStage: 1 } })
    expect(wrapper.findAll('[data-step]').length).toBe(5)
  })

  it('marks completed steps', () => {
    const wrapper = mount(PipelineProgress, { props: { currentStage: 3 } })
    const steps = wrapper.findAll('[data-step]')
    expect(steps[0].classes()).toContain('step-completed')
    expect(steps[1].classes()).toContain('step-completed')
    expect(steps[2].classes()).toContain('step-active')
    expect(steps[3].classes()).toContain('step-pending')
  })
})
```

- [ ] **Step 3: Implement PipelineProgress**

```vue
<!-- frontend/src/components/PipelineProgress.vue -->
<template>
  <div class="flex items-center justify-between">
    <div
      v-for="(step, idx) in steps"
      :key="idx"
      :data-step="idx + 1"
      :class="[
        'flex flex-col items-center flex-1',
        idx + 1 < currentStage ? 'step-completed' : '',
        idx + 1 === currentStage ? 'step-active' : '',
        idx + 1 > currentStage ? 'step-pending' : '',
      ]"
    >
      <div :class="[
        'w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold',
        idx + 1 < currentStage ? 'bg-green-500 text-white' : '',
        idx + 1 === currentStage ? 'bg-blue-500 text-white animate-pulse' : '',
        idx + 1 > currentStage ? 'bg-gray-200 text-gray-500' : '',
      ]">
        {{ idx + 1 }}
      </div>
      <span class="text-xs mt-1 text-center">{{ step }}</span>
    </div>
  </div>
</template>

<script setup>
defineProps({ currentStage: { type: Number, required: true } })

const steps = [
  'Knowledge Graph',
  'Environment Setup',
  'Simulation',
  'Report Generation',
  'Ready',
]
</script>
```

- [ ] **Step 4: Write ChatReplay test**

```js
// frontend/tests/components/ChatReplay.spec.js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ChatReplay from '../../src/components/ChatReplay.vue'

describe('ChatReplay', () => {
  it('renders chat messages', () => {
    const messages = [
      { agent_name: 'Agent_1', action_type: 'CREATE_POST', action_args: { content: 'Markets look bullish' } },
      { agent_name: 'Agent_2', action_type: 'CREATE_POST', action_args: { content: 'I disagree, bearish signals' } },
    ]
    const wrapper = mount(ChatReplay, { props: { messages } })
    expect(wrapper.text()).toContain('Agent_1')
    expect(wrapper.text()).toContain('Markets look bullish')
    expect(wrapper.text()).toContain('Agent_2')
  })

  it('shows empty state when no messages', () => {
    const wrapper = mount(ChatReplay, { props: { messages: [] } })
    expect(wrapper.text()).toContain('No agent activity')
  })
})
```

- [ ] **Step 5: Implement ChatReplay**

```vue
<!-- frontend/src/components/ChatReplay.vue -->
<template>
  <div class="max-h-96 overflow-y-auto space-y-3 p-4 bg-gray-50 rounded-lg">
    <div v-if="messages.length === 0" class="text-gray-400 text-center py-8">
      No agent activity to display.
    </div>
    <div v-for="(msg, idx) in messages" :key="idx" class="flex gap-3">
      <div class="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-xs font-bold text-blue-600">
        {{ msg.agent_name?.charAt(0) || '?' }}
      </div>
      <div>
        <div class="text-sm font-medium text-gray-900">{{ msg.agent_name }}</div>
        <div class="text-sm text-gray-600">{{ msg.action_args?.content || msg.action_type }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  messages: { type: Array, required: true },
})
</script>
```

- [ ] **Step 6: Implement remaining components**

```vue
<!-- frontend/src/components/SeedUploader.vue -->
<template>
  <div>
    <div
      class="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-blue-400 transition"
      @drop.prevent="handleDrop"
      @dragover.prevent
      @click="$refs.fileInput.click()"
    >
      <p class="text-gray-500">Drag & drop a PDF or TXT file, or click to browse</p>
      <p class="text-sm text-gray-400 mt-1">Max 50,000 characters</p>
      <input ref="fileInput" type="file" accept=".pdf,.txt,.md" class="hidden" @change="handleFileSelect" />
    </div>

    <div class="mt-4">
      <label class="block text-sm font-medium text-gray-700 mb-1">Or paste text directly</label>
      <textarea
        v-model="text"
        rows="6"
        class="w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500"
        placeholder="Paste your seed text here..."
        @input="$emit('update:modelValue', text)"
      />
      <p class="text-xs text-gray-400 mt-1">{{ text.length }} / 50,000 characters</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const emit = defineEmits(['update:modelValue'])
const text = ref('')

function handleDrop(e) {
  const file = e.dataTransfer.files[0]
  if (file) readFile(file)
}

function handleFileSelect(e) {
  const file = e.target.files[0]
  if (file) readFile(file)
}

function readFile(file) {
  const reader = new FileReader()
  reader.onload = (e) => {
    text.value = e.target.result
    emit('update:modelValue', text.value)
  }
  reader.readAsText(file)
}
</script>
```

```vue
<!-- frontend/src/components/ReportViewer.vue -->
<template>
  <div class="prose prose-blue max-w-none" v-html="renderedMarkdown" />
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ markdown: { type: String, required: true } })

// Simple markdown rendering (replace with marked.js in production)
const renderedMarkdown = computed(() => {
  return props.markdown
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
})
</script>
```

```vue
<!-- frontend/src/components/ExportButtons.vue -->
<template>
  <div class="flex gap-3">
    <button
      v-for="fmt in formats"
      :key="fmt"
      class="px-4 py-2 text-sm font-medium rounded-md border border-gray-300 hover:bg-gray-50"
      @click="$emit('export', fmt)"
    >
      Export {{ fmt.toUpperCase() }}
    </button>
  </div>
</template>

<script setup>
defineEmits(['export'])
const formats = ['pdf', 'json', 'csv']
</script>
```

- [ ] **Step 7: Implement Dashboard view**

```vue
<!-- frontend/src/views/Dashboard.vue -->
<template>
  <div class="max-w-4xl mx-auto py-8 px-4">
    <div class="flex justify-between items-center mb-8">
      <h1 class="text-2xl font-bold">Your Simulations</h1>
      <router-link to="/sim/new"
        class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
        New Simulation
      </router-link>
    </div>

    <CreditWarning v-if="creditsStore.isLow" />

    <div v-if="jobs.length === 0" class="text-center py-16 text-gray-400">
      <p class="text-lg">No simulations yet</p>
      <p class="text-sm mt-2">Create your first simulation to get started</p>
    </div>

    <div v-else class="space-y-4">
      <router-link
        v-for="job in jobs"
        :key="job.id"
        :to="job.status === 'completed' ? `/sim/${job.id}/results` : `/sim/${job.id}`"
        class="block p-4 bg-white rounded-lg shadow hover:shadow-md transition"
      >
        <div class="flex justify-between">
          <div>
            <div class="font-medium">{{ job.goal }}</div>
            <div class="text-sm text-gray-500">{{ job.tier }} &middot; {{ job.credits_charged }} credits</div>
          </div>
          <span :class="statusClass(job.status)" class="text-sm font-medium px-2 py-1 rounded">
            {{ job.status }}
          </span>
        </div>
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useCreditsStore } from '../stores/credits'
import { listJobs } from '../api/jobs'
import { getBalance } from '../api/billing'
import CreditWarning from '../components/CreditWarning.vue'

const authStore = useAuthStore()
const creditsStore = useCreditsStore()
const jobs = ref([])

onMounted(async () => {
  const userId = authStore.user?.id
  if (!userId) return
  const [jobList, balance] = await Promise.all([
    listJobs(userId),
    getBalance(userId),
  ])
  jobs.value = jobList
  creditsStore.setBalance(balance.balance)
})

function statusClass(status) {
  const classes = {
    pending: 'bg-yellow-100 text-yellow-800',
    running: 'bg-blue-100 text-blue-800',
    completed: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
  }
  return classes[status] || 'bg-gray-100 text-gray-800'
}
</script>
```

- [ ] **Step 8: Implement NewSimulation view**

```vue
<!-- frontend/src/views/NewSimulation.vue -->
<template>
  <div class="max-w-2xl mx-auto py-8 px-4">
    <h1 class="text-2xl font-bold mb-6">New Simulation</h1>

    <div v-if="error" class="bg-red-50 text-red-700 p-3 rounded mb-4">{{ error }}</div>

    <div class="space-y-6">
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">Seed Material</label>
        <SeedUploader v-model="seedText" />
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">Prediction Goal</label>
        <textarea
          v-model="goal"
          rows="3"
          class="w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500"
          placeholder="e.g., Predict US vs China public opinion on Iran escalation over 30 days"
        />
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">Simulation Tier</label>
        <TierSelector @select="selectedTier = $event" />
      </div>

      <button
        :disabled="!canRun || loading"
        class="w-full py-3 bg-blue-600 text-white rounded-md font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        @click="runSimulation"
      >
        {{ loading ? 'Starting...' : canRun ? `Run Simulation (${tierCost} credits)` : 'Select a tier and add seed material' }}
      </button>

      <p v-if="!creditsStore.canAfford(selectedTier) && selectedTier" class="text-red-500 text-sm">
        Insufficient credits.
        <router-link to="/account" class="underline">Buy more credits</router-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useCreditsStore } from '../stores/credits'
import { createJob } from '../api/jobs'
import SeedUploader from '../components/SeedUploader.vue'
import TierSelector from '../components/TierSelector.vue'

const authStore = useAuthStore()
const creditsStore = useCreditsStore()
const router = useRouter()

const seedText = ref('')
const goal = ref('')
const selectedTier = ref(null)
const loading = ref(false)
const error = ref('')

const tierCost = computed(() => creditsStore.getTierCost(selectedTier.value))
const canRun = computed(() =>
  seedText.value.trim() && goal.value.trim() && selectedTier.value && creditsStore.canAfford(selectedTier.value)
)

async function runSimulation() {
  loading.value = true
  error.value = ''
  try {
    const job = await createJob(authStore.user.id, seedText.value, goal.value, selectedTier.value)
    creditsStore.setBalance(creditsStore.balance - tierCost.value)
    router.push(`/sim/${job.id}`)
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to start simulation'
  } finally {
    loading.value = false
  }
}
</script>
```

- [ ] **Step 9: Implement SimulationStatus and SimulationResults views**

```vue
<!-- frontend/src/views/SimulationStatus.vue -->
<template>
  <div class="max-w-2xl mx-auto py-8 px-4">
    <h1 class="text-2xl font-bold mb-6">Simulation Progress</h1>

    <div v-if="job" class="space-y-6">
      <div class="bg-white p-6 rounded-lg shadow">
        <div class="text-sm text-gray-500 mb-4">{{ job.goal }}</div>
        <PipelineProgress :current-stage="job.pipeline_stage || 1" />
      </div>

      <div class="text-center text-gray-500">
        <p v-if="job.status === 'running'">Simulation in progress... This page auto-refreshes.</p>
        <p v-if="job.status === 'failed'" class="text-red-500">
          Simulation failed: {{ job.error_message }}. Credits have been refunded.
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getJob } from '../api/jobs'
import PipelineProgress from '../components/PipelineProgress.vue'

const route = useRoute()
const router = useRouter()
const job = ref(null)
let pollInterval = null

onMounted(async () => {
  await fetchJob()
  pollInterval = setInterval(fetchJob, 5000)
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
})

async function fetchJob() {
  const data = await getJob(route.params.id)
  job.value = data
  if (data.status === 'completed') {
    clearInterval(pollInterval)
    router.push(`/sim/${data.id}/results`)
  }
}
</script>
```

```vue
<!-- frontend/src/views/SimulationResults.vue -->
<template>
  <div class="max-w-4xl mx-auto py-8 px-4">
    <div v-if="job" class="space-y-8">
      <div class="flex justify-between items-start">
        <div>
          <h1 class="text-2xl font-bold">Prediction Report</h1>
          <p class="text-gray-500 mt-1">{{ job.goal }}</p>
        </div>
        <ExportButtons @export="handleExport" />
      </div>

      <div class="bg-white p-8 rounded-lg shadow">
        <ReportViewer :markdown="job.result_report || 'Report not available.'" />
      </div>

      <div>
        <h2 class="text-xl font-bold mb-4">Agent Activity Replay</h2>
        <ChatReplay :messages="chatMessages" />
      </div>

      <div class="text-center">
        <router-link to="/sim/new" class="text-blue-600 hover:text-blue-500 font-medium">
          Run another simulation
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getJob } from '../api/jobs'
import ReportViewer from '../components/ReportViewer.vue'
import ChatReplay from '../components/ChatReplay.vue'
import ExportButtons from '../components/ExportButtons.vue'

const route = useRoute()
const job = ref(null)
const chatMessages = ref([])

onMounted(async () => {
  const data = await getJob(route.params.id)
  job.value = data
  try {
    chatMessages.value = JSON.parse(data.result_chat_log || '[]')
  } catch {
    chatMessages.value = []
  }
})

function handleExport(format) {
  // Simple export — download the report as a file
  const content = format === 'json'
    ? JSON.stringify(job.value, null, 2)
    : job.value.result_report || ''
  const blob = new Blob([content], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `simulation-${job.value.id}.${format}`
  a.click()
  URL.revokeObjectURL(url)
}
</script>
```

- [ ] **Step 10: Run all frontend tests**

```bash
cd frontend && npx vitest run
```

Expected: 23 passed (auth store 3, login view 3, credits store 5, credit badge 2, tier selector 4, pipeline progress 2, chat replay 2, + 2 new dashboard/newsim tests).

- [ ] **Step 11: Commit**

```bash
git add frontend/src/ frontend/tests/
git commit -m "feat: add Dashboard, NewSimulation, SimulationStatus, and Results views"
```

---

### Task 5: Router + Navbar + Account View

**Files:**
- Create: `frontend/src/router/index.js`
- Create: `frontend/src/views/Account.vue`
- Create: `frontend/src/views/Landing.vue`
- Create: `frontend/src/components/Navbar.vue`
- Create: `frontend/src/components/CreditWarning.vue`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/main.js`

- [ ] **Step 1: Implement router**

```js
// frontend/src/router/index.js
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/', name: 'landing', component: () => import('../views/Landing.vue') },
  { path: '/login', name: 'login', component: () => import('../views/Login.vue') },
  { path: '/register', name: 'register', component: () => import('../views/Register.vue') },
  { path: '/dashboard', name: 'dashboard', component: () => import('../views/Dashboard.vue'), meta: { auth: true } },
  { path: '/sim/new', name: 'new-sim', component: () => import('../views/NewSimulation.vue'), meta: { auth: true } },
  { path: '/sim/:id', name: 'sim-status', component: () => import('../views/SimulationStatus.vue'), meta: { auth: true } },
  { path: '/sim/:id/results', name: 'sim-results', component: () => import('../views/SimulationResults.vue'), meta: { auth: true } },
  { path: '/account', name: 'account', component: () => import('../views/Account.vue'), meta: { auth: true } },
  // Demo pages (public, no auth) — added in Plan 5
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const authStore = useAuthStore()
  if (to.meta.auth && !authStore.isLoggedIn) {
    return { name: 'login' }
  }
})

export default router
```

- [ ] **Step 2: Implement Navbar**

```vue
<!-- frontend/src/components/Navbar.vue -->
<template>
  <nav class="bg-white shadow-sm border-b">
    <div class="max-w-6xl mx-auto px-4 flex justify-between items-center h-14">
      <router-link to="/" class="text-xl font-bold text-blue-600">FishCloud</router-link>

      <div v-if="authStore.isLoggedIn" class="flex items-center gap-4">
        <CreditBadge />
        <router-link to="/dashboard" class="text-sm text-gray-600 hover:text-gray-900">Dashboard</router-link>
        <router-link to="/account" class="text-sm text-gray-600 hover:text-gray-900">Account</router-link>
        <button @click="logout" class="text-sm text-gray-500 hover:text-gray-700">Sign out</button>
      </div>

      <div v-else class="flex items-center gap-4">
        <router-link to="/login" class="text-sm text-gray-600 hover:text-gray-900">Sign in</router-link>
        <router-link to="/register"
          class="text-sm px-3 py-1 bg-blue-600 text-white rounded-md hover:bg-blue-700">
          Sign up
        </router-link>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import CreditBadge from './CreditBadge.vue'

const authStore = useAuthStore()
const router = useRouter()

function logout() {
  authStore.logout()
  router.push('/')
}
</script>
```

- [ ] **Step 3: Implement CreditWarning**

```vue
<!-- frontend/src/components/CreditWarning.vue -->
<template>
  <div v-if="creditsStore.isLow" class="bg-yellow-50 border border-yellow-200 text-yellow-800 px-4 py-3 rounded-md flex justify-between items-center mb-4">
    <span>Low credit balance. You may not be able to run simulations.</span>
    <router-link to="/account" class="text-yellow-900 font-medium underline">Buy more credits</router-link>
  </div>
</template>

<script setup>
import { useCreditsStore } from '../stores/credits'
const creditsStore = useCreditsStore()
</script>
```

- [ ] **Step 4: Implement Account view**

```vue
<!-- frontend/src/views/Account.vue -->
<template>
  <div class="max-w-2xl mx-auto py-8 px-4">
    <h1 class="text-2xl font-bold mb-6">Account</h1>

    <div class="bg-white p-6 rounded-lg shadow mb-6">
      <h2 class="text-lg font-semibold mb-2">Credit Balance</h2>
      <div class="text-4xl font-bold text-blue-600">{{ creditsStore.balance }}</div>
      <p class="text-gray-500 text-sm mt-1">credits remaining</p>
    </div>

    <div class="bg-white p-6 rounded-lg shadow mb-6">
      <h2 class="text-lg font-semibold mb-4">Buy Credits</h2>
      <div class="grid grid-cols-3 gap-4">
        <button
          v-for="pack in packs"
          :key="pack.id"
          class="p-4 border-2 rounded-lg text-center hover:border-blue-400 transition"
          @click="purchase(pack.id)"
        >
          <div class="font-bold">{{ pack.name }}</div>
          <div class="text-2xl font-bold text-blue-600">{{ pack.credits }}</div>
          <div class="text-sm text-gray-500">credits</div>
          <div class="mt-2 font-medium">${{ pack.price }}</div>
        </button>
      </div>
    </div>

    <div class="bg-white p-6 rounded-lg shadow">
      <h2 class="text-lg font-semibold mb-4">Transaction History</h2>
      <div v-if="history.length === 0" class="text-gray-400">No transactions yet.</div>
      <div v-else class="space-y-2">
        <div v-for="entry in history" :key="entry.id" class="flex justify-between text-sm">
          <span>{{ entry.description }}</span>
          <span :class="entry.amount > 0 ? 'text-green-600' : 'text-red-600'">
            {{ entry.amount > 0 ? '+' : '' }}{{ entry.amount }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useCreditsStore } from '../stores/credits'
import { purchaseCredits, getHistory, getBalance } from '../api/billing'

const authStore = useAuthStore()
const creditsStore = useCreditsStore()
const history = ref([])

const packs = [
  { id: 'starter', name: 'Starter', credits: 100, price: 19 },
  { id: 'pro', name: 'Pro', credits: 500, price: 79 },
  { id: 'heavy', name: 'Heavy', credits: 2000, price: 249 },
]

onMounted(async () => {
  const userId = authStore.user?.id
  if (!userId) return
  const [bal, hist] = await Promise.all([
    getBalance(userId),
    getHistory(userId),
  ])
  creditsStore.setBalance(bal.balance)
  history.value = hist
})

async function purchase(packId) {
  const { checkout_url } = await purchaseCredits(authStore.user.id, packId)
  window.location.href = checkout_url
}
</script>
```

- [ ] **Step 5: Wire up App.vue and main.js**

```vue
<!-- frontend/src/App.vue -->
<template>
  <div class="min-h-screen bg-gray-50">
    <Navbar />
    <router-view />
  </div>
</template>

<script setup>
import Navbar from './components/Navbar.vue'
</script>
```

```js
// frontend/src/main.js
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './assets/styles.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
```

- [ ] **Step 6: Run full frontend test suite**

```bash
cd frontend && npx vitest run
```

Expected: All tests pass.

- [ ] **Step 7: Verify build**

```bash
cd frontend && npm run build
```

Expected: Builds without errors.

- [ ] **Step 8: Commit**

```bash
git add frontend/
git commit -m "feat: add router, Navbar, Account view, and wire up App shell"
```

---

## Test Suite Summary (After Plan 4)

| File | Tests | What it covers |
|------|-------|----------------|
| `stores/auth.spec.js` | 3 | Auth state, login, logout |
| `stores/credits.spec.js` | 5 | Balance, low threshold, canAfford |
| `views/Login.spec.js` | 3 | Form rendering, register link, loading state |
| `components/CreditBadge.spec.js` | 2 | Balance display, warning style |
| `components/TierSelector.spec.js` | 4 | Tier rendering, costs, disabled state, emit |
| `components/PipelineProgress.spec.js` | 2 | Step rendering, completion marking |
| `components/ChatReplay.spec.js` | 2 | Message rendering, empty state |
| **Frontend Total** | **21** | |
| *(Backend Plans 1-3)* | 66 | |
| **Grand Total** | **87** | |
