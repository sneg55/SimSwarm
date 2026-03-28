# Design System Foundation & Landing Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the SimSwarm "Deep Ocean" design system (tokens, fonts, shared utilities) and rebuild the landing page with interactive swarm canvas, rotating headline, Wave Pulse logo, and organic micro-interactions.

**Architecture:** Extend the existing Tailwind config with custom design tokens. Create shared Vue composables for swarm canvas and micro-interactions. Rebuild Landing.vue and Navbar.vue with the new design system. No backend changes needed.

**Tech Stack:** Vue 3 (Composition API), Tailwind CSS 3.4, Canvas API (2D), Inter + JetBrains Mono (Google Fonts)

**Spec reference:** `docs/superpowers/specs/2026-03-27-simswarm-visual-redesign.md`

**Mockup reference:** `.superpowers/brainstorm/` in this worktree (open HTML files in browser)

---

## File Structure

```
frontend/
  index.html                          # MODIFY - add font preloads
  tailwind.config.js                  # MODIFY - add design tokens
  src/
    assets/styles.css                 # MODIFY - add base dark styles + utilities
    App.vue                           # MODIFY - dark bg, remove old gray-50
    components/
      LogoWavePulse.vue               # CREATE - animated SVG logo component
      NavbarNew.vue                   # CREATE - frosted glass navbar (replaces Navbar.vue)
      ScrollProgress.vue              # CREATE - gradient scroll progress bar
      HeroSwarm.vue                   # CREATE - interactive canvas swarm
      HeroRotatingText.vue            # CREATE - sliding word rotation
      ExperienceStep.vue              # CREATE - scroll-reveal step component
      PricingCard.vue                 # CREATE - pricing card with accent glow
      ProofCard.vue                   # CREATE - testimonial card
      DemoCard.vue                    # MODIFY - restyle for dark theme
      CreditBadge.vue                 # MODIFY - restyle for dark theme
      Navbar.vue                      # MODIFY - import NavbarNew as replacement
    views/
      Landing.vue                     # MODIFY - full rebuild with new sections
```

---

### Task 1: Design Tokens — Tailwind Config

**Files:**
- Modify: `frontend/tailwind.config.js`

- [ ] **Step 1: Update tailwind.config.js with design tokens**

```js
const defaultTheme = require('tailwindcss/defaultTheme')

export default {
  content: ["./index.html", "./src/**/*.{vue,js}"],
  theme: {
    extend: {
      colors: {
        ocean: {
          abyss: '#0B1426',
          deep: '#0F2035',
          teal: '#164E63',
          cyan: '#0E7490',
          glow: '#22D3EE',
        },
        coral: {
          DEFAULT: '#FF6B6B',
          amber: '#F97316',
          sand: '#FBBF24',
        },
        organic: {
          sage: '#10B981',
          seafoam: '#6EE7B7',
          violet: '#A78BFA',
        },
        mist: {
          foam: '#F1F5F9',
          DEFAULT: '#CBD5E1',
          drift: '#94A3B8',
          slate: '#64748B',
          depth: '#1E293B',
        },
      },
      fontFamily: {
        sans: ['Inter', ...defaultTheme.fontFamily.sans],
        mono: ['JetBrains Mono', ...defaultTheme.fontFamily.mono],
      },
      transitionTimingFunction: {
        'spring': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
        'smooth': 'cubic-bezier(0.22, 1, 0.36, 1)',
      },
      animation: {
        'glow-breathe': 'glow-breathe 3s ease-in-out infinite',
        'shimmer': 'shimmer 2s infinite',
      },
      keyframes: {
        'glow-breathe': {
          '0%, 100%': { opacity: '0.5' },
          '50%': { opacity: '1' },
        },
        'shimmer': {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(200%)' },
        },
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
}
```

- [ ] **Step 2: Verify Tailwind builds**

Run: `cd frontend && npx tailwindcss --content "./index.html,./src/**/*.{vue,js}" --output /dev/null 2>&1 | head -5`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/tailwind.config.js
git commit -m "feat: add Deep Ocean design tokens to Tailwind config"
```

---

### Task 2: Font Loading & Base Styles

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/src/assets/styles.css`

- [ ] **Step 1: Add font preloads to index.html**

Replace the entire `frontend/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SimSwarm</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
</head>
<body class="bg-ocean-abyss text-mist">
  <div id="app"></div>
  <script type="module" src="/src/main.js"></script>
</body>
</html>
```

- [ ] **Step 2: Add base styles and utility classes to styles.css**

Replace `frontend/src/assets/styles.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  html {
    scroll-behavior: smooth;
    scrollbar-width: thin;
    scrollbar-color: #164E63 #0B1426;
  }
  body {
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }
}

@layer utilities {
  /* Gradient text utility */
  .text-gradient {
    background: linear-gradient(135deg, #22D3EE, #A78BFA, #FF6B6B);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  /* Frosted glass */
  .glass {
    background: rgba(11, 20, 38, 0.7);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
  }
  .glass-solid {
    background: rgba(11, 20, 38, 0.92);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
  }

  /* Glow shadows */
  .glow-cyan {
    box-shadow: 0 0 20px rgba(14, 116, 144, 0.3);
  }
  .glow-cyan-lg {
    box-shadow: 0 0 32px rgba(14, 116, 144, 0.5), 0 4px 16px rgba(0, 0, 0, 0.3);
  }
  .glow-coral {
    box-shadow: 0 0 28px rgba(255, 107, 107, 0.25);
  }
  .glow-coral-lg {
    box-shadow: 0 0 40px rgba(255, 107, 107, 0.4), 0 6px 20px rgba(0, 0, 0, 0.3);
  }
}
```

- [ ] **Step 3: Update App.vue for dark theme**

Replace `frontend/src/App.vue`:

```vue
<template>
  <div class="min-h-screen bg-ocean-abyss text-mist">
    <Navbar />
    <main>
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import Navbar from './components/Navbar.vue'
import { useAuthStore } from './stores/auth.js'

const authStore = useAuthStore()

onMounted(() => {
  authStore.loadFromStorage()
})
</script>
```

- [ ] **Step 4: Verify the app loads with dark background**

Run: `cd frontend && npm run dev`
Open: `http://localhost:3000`
Expected: Dark navy background (#0B1426), text is light gray. Existing pages will look broken (colors mismatched) — this is expected.

- [ ] **Step 5: Commit**

```bash
git add frontend/index.html frontend/src/assets/styles.css frontend/src/App.vue
git commit -m "feat: add Inter/JetBrains Mono fonts and dark theme base styles"
```

---

### Task 3: Wave Pulse Logo Component

**Files:**
- Create: `frontend/src/components/LogoWavePulse.vue`

- [ ] **Step 1: Create the logo component**

Create `frontend/src/components/LogoWavePulse.vue`:

```vue
<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 48 48"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    class="block"
  >
    <defs>
      <linearGradient :id="gradId" x1="0" y1="24" x2="48" y2="24">
        <stop offset="0%" stop-color="#22D3EE" />
        <stop offset="50%" stop-color="#A78BFA" />
        <stop offset="100%" stop-color="#FF6B6B" />
      </linearGradient>
    </defs>

    <!-- Concentric pulse rings -->
    <template v-if="animated">
      <circle cx="24" cy="24" r="20" stroke="#22D3EE" stroke-width="1" fill="none" opacity="0.12">
        <animate attributeName="r" values="16;22;16" dur="4s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.15;0.05;0.15" dur="4s" repeatCount="indefinite" />
      </circle>
      <circle cx="24" cy="24" r="14" stroke="#A78BFA" stroke-width="1" fill="none" opacity="0.15">
        <animate attributeName="r" values="12;17;12" dur="4s" begin="1.3s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.2;0.06;0.2" dur="4s" begin="1.3s" repeatCount="indefinite" />
      </circle>
      <circle cx="24" cy="24" r="8" stroke="#FF6B6B" stroke-width="1" fill="none" opacity="0.2">
        <animate attributeName="r" values="8;12;8" dur="4s" begin="2.6s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.25;0.08;0.25" dur="4s" begin="2.6s" repeatCount="indefinite" />
      </circle>
    </template>
    <template v-else>
      <circle cx="24" cy="24" r="16" stroke="#22D3EE" stroke-width="1.5" fill="none" opacity="0.15" />
      <circle cx="24" cy="24" r="10" stroke="#A78BFA" stroke-width="1.5" fill="none" opacity="0.2" />
    </template>

    <!-- Agent dots -->
    <template v-if="animated">
      <circle cx="10" cy="16" r="2" fill="#22D3EE" opacity="0.7">
        <animate attributeName="opacity" values="0.5;1;0.5" dur="3s" repeatCount="indefinite" />
      </circle>
      <circle cx="38" cy="18" r="1.5" fill="#A78BFA" opacity="0.6">
        <animate attributeName="opacity" values="0.5;1;0.5" dur="3s" begin="0.5s" repeatCount="indefinite" />
      </circle>
      <circle cx="14" cy="36" r="1.5" fill="#6EE7B7" opacity="0.6">
        <animate attributeName="opacity" values="0.5;1;0.5" dur="3s" begin="1s" repeatCount="indefinite" />
      </circle>
      <circle cx="36" cy="34" r="2" fill="#FF6B6B" opacity="0.7">
        <animate attributeName="opacity" values="0.5;1;0.5" dur="3s" begin="1.5s" repeatCount="indefinite" />
      </circle>
      <circle cx="24" cy="8" r="1.5" fill="#FBBF24" opacity="0.5">
        <animate attributeName="opacity" values="0.3;0.8;0.3" dur="3s" begin="2s" repeatCount="indefinite" />
      </circle>
    </template>
    <template v-else>
      <circle cx="12" cy="18" r="2" fill="#22D3EE" opacity="0.4" />
      <circle cx="36" cy="30" r="2" fill="#FF6B6B" opacity="0.4" />
    </template>

    <!-- Core -->
    <circle cx="24" cy="24" r="5" :fill="`url(#${gradId})`" opacity="0.9" />
    <circle cx="24" cy="24" r="2.5" fill="#F1F5F9" opacity="0.85" />
  </svg>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  size: { type: Number, default: 36 },
  animated: { type: Boolean, default: true },
})

// Unique gradient ID to avoid SVG ID collisions when multiple logos render
const gradId = computed(() => `logo-grad-${props.size}`)
</script>
```

- [ ] **Step 2: Verify the component renders**

Temporarily add to `App.vue` template to test:
```vue
<LogoWavePulse :size="48" />
<LogoWavePulse :size="24" :animated="false" />
```
Expected: Two logos — large animated with pulsing rings, small static with two rings.
Remove the test after verifying.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/LogoWavePulse.vue
git commit -m "feat: add Wave Pulse animated logo component"
```

---

### Task 4: New Navbar (Frosted Glass)

**Files:**
- Create: `frontend/src/components/NavbarNew.vue`
- Modify: `frontend/src/components/Navbar.vue`

- [ ] **Step 1: Create NavbarNew.vue**

Create `frontend/src/components/NavbarNew.vue`:

```vue
<template>
  <nav
    class="fixed top-0 left-0 right-0 z-50 border-b transition-all duration-300"
    :class="scrolled
      ? 'glass-solid py-2.5 border-mist-depth/80'
      : 'glass py-4 border-mist-depth/50'"
  >
    <div class="max-w-6xl mx-auto px-4 md:px-8 flex items-center justify-between">
      <!-- Brand -->
      <router-link to="/" class="flex items-center gap-2.5 group">
        <div class="transition-transform duration-400 ease-spring group-hover:scale-110 group-hover:rotate-[5deg]">
          <LogoWavePulse :size="36" />
        </div>
        <span class="text-xl font-extrabold text-mist-foam tracking-tight transition-colors group-hover:text-ocean-glow">
          SimSwarm
        </span>
      </router-link>

      <!-- Links -->
      <div class="flex items-center gap-7">
        <template v-if="authStore.isLoggedIn">
          <NavLink to="/dashboard">Dashboard</NavLink>
          <NavLink to="/sim/new">New Simulation</NavLink>
          <NavLink to="/account">{{ authStore.user?.email }}</NavLink>
          <CreditBadge />
          <button
            @click="handleLogout"
            class="text-sm text-mist-drift hover:text-mist-foam transition-colors"
          >
            Sign out
          </button>
        </template>
        <template v-else>
          <NavLink href="#experience">How it works</NavLink>
          <NavLink href="#pricing">Pricing</NavLink>
          <NavLink to="/login">Sign in</NavLink>
          <router-link
            to="/register"
            class="px-5 py-2 rounded-lg text-sm font-semibold text-white
                   bg-gradient-to-br from-ocean-cyan to-cyan-500
                   glow-cyan transition-all duration-250 ease-spring
                   hover:glow-cyan-lg hover:-translate-y-px"
          >
            Get started
          </router-link>
        </template>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import LogoWavePulse from './LogoWavePulse.vue'
import CreditBadge from './CreditBadge.vue'

const NavLink = {
  props: {
    to: String,
    href: String,
  },
  template: `
    <component
      :is="to ? 'router-link' : 'a'"
      v-bind="to ? { to } : { href }"
      class="text-sm font-medium text-mist-drift relative pb-0.5
             transition-colors hover:text-mist-foam
             after:content-[''] after:absolute after:bottom-0 after:left-0
             after:w-0 after:h-0.5 after:bg-ocean-glow after:rounded-sm
             after:transition-[width] after:duration-300 after:ease-spring
             hover:after:w-full"
    >
      <slot />
    </component>
  `,
}

const router = useRouter()
const authStore = useAuthStore()
const scrolled = ref(false)

function onScroll() {
  scrolled.value = window.scrollY > 60
}

function handleLogout() {
  authStore.logout()
  router.push('/')
}

onMounted(() => window.addEventListener('scroll', onScroll, { passive: true }))
onUnmounted(() => window.removeEventListener('scroll', onScroll))
</script>
```

- [ ] **Step 2: Replace Navbar.vue with a wrapper**

Replace `frontend/src/components/Navbar.vue`:

```vue
<template>
  <NavbarNew />
</template>

<script setup>
import NavbarNew from './NavbarNew.vue'
</script>
```

- [ ] **Step 3: Verify navbar renders**

Run: `cd frontend && npm run dev`
Expected: Frosted glass navbar at top with Wave Pulse logo, "SimSwarm" text, navigation links. Shrinks on scroll. Logo scales on hover.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/NavbarNew.vue frontend/src/components/Navbar.vue
git commit -m "feat: replace navbar with frosted glass design + Wave Pulse logo"
```

---

### Task 5: Scroll Progress Bar

**Files:**
- Create: `frontend/src/components/ScrollProgress.vue`

- [ ] **Step 1: Create ScrollProgress.vue**

Create `frontend/src/components/ScrollProgress.vue`:

```vue
<template>
  <div class="fixed top-0 left-0 right-0 h-0.5 z-[100]">
    <div
      class="h-full bg-gradient-to-r from-ocean-cyan via-ocean-glow to-organic-violet shadow-[0_0_8px_rgba(34,211,238,0.4)]"
      :style="{ width: progress + '%' }"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const progress = ref(0)

function onScroll() {
  const el = document.documentElement
  progress.value = (el.scrollTop / (el.scrollHeight - el.clientHeight)) * 100
}

onMounted(() => window.addEventListener('scroll', onScroll, { passive: true }))
onUnmounted(() => window.removeEventListener('scroll', onScroll))
</script>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ScrollProgress.vue
git commit -m "feat: add gradient scroll progress bar component"
```

---

### Task 6: Hero Rotating Text

**Files:**
- Create: `frontend/src/components/HeroRotatingText.vue`

- [ ] **Step 1: Create HeroRotatingText.vue**

Create `frontend/src/components/HeroRotatingText.vue`:

```vue
<template>
  <span ref="wrapperRef" class="inline-block relative overflow-hidden align-bottom" :style="{ height: '1.2em', width: wrapperWidth }">
    <span
      v-for="(word, i) in words"
      :key="word"
      class="block text-gradient whitespace-nowrap absolute top-0 left-0 right-0 text-center transition-all duration-600 ease-smooth"
      :class="{
        'translate-y-0 opacity-100': i === current,
        '-translate-y-[110%] opacity-0': i === exiting,
        'translate-y-[110%] opacity-0': i !== current && i !== exiting,
      }"
    >
      {{ word }}
    </span>
  </span>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'

const words = [
  'public opinion',
  'market reactions',
  'geopolitical shifts',
  'crisis responses',
  'cultural impacts',
  'regulatory cascades',
  'supply-chain ripples',
  'stakeholder coalitions',
  'sentiment waves',
  'escalation paths',
  'economic trajectories',
  'narrative ecosystems',
]

const current = ref(0)
const exiting = ref(-1)
const wrapperRef = ref(null)
const wrapperWidth = ref('auto')
let interval = null

function measureWidth() {
  if (!wrapperRef.value) return
  const wrapper = wrapperRef.value
  const spans = wrapper.querySelectorAll('span')
  let maxW = 0
  spans.forEach(span => {
    span.style.position = 'relative'
    span.style.visibility = 'hidden'
    span.style.opacity = '1'
    span.style.transform = 'none'
    maxW = Math.max(maxW, span.offsetWidth)
    span.style.position = ''
    span.style.visibility = ''
    span.style.opacity = ''
    span.style.transform = ''
  })
  wrapperWidth.value = (maxW + 4) + 'px'
}

function rotate() {
  exiting.value = current.value
  current.value = (current.value + 1) % words.length
  setTimeout(() => { exiting.value = -1 }, 700)
}

onMounted(async () => {
  await nextTick()
  if (document.fonts?.ready) {
    await document.fonts.ready
  }
  measureWidth()
  window.addEventListener('resize', measureWidth)
  interval = setInterval(rotate, 2500)
})

onUnmounted(() => {
  clearInterval(interval)
  window.removeEventListener('resize', measureWidth)
})
</script>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/HeroRotatingText.vue
git commit -m "feat: add rotating hero text component with slide animation"
```

---

### Task 7: Interactive Swarm Canvas

**Files:**
- Create: `frontend/src/components/HeroSwarm.vue`

- [ ] **Step 1: Create HeroSwarm.vue**

Create `frontend/src/components/HeroSwarm.vue`:

```vue
<template>
  <div ref="containerRef" class="absolute inset-0 overflow-hidden z-0">
    <canvas ref="canvasRef" class="block w-full h-full" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const containerRef = ref(null)
const canvasRef = ref(null)

const AGENT_COUNT = 120
const MOUSE_RADIUS = 200
const MOUSE_FORCE = 0.035
const FRICTION = 0.98
const CONNECTION_DIST = 80
const HOME_FORCE = 0.00008
const NUM_ATTRACTORS = 5

const palette = [
  { r: 34, g: 211, b: 238 },
  { r: 167, g: 139, b: 250 },
  { r: 110, g: 231, b: 183 },
  { r: 255, g: 107, b: 107 },
  { r: 251, g: 191, b: 36 },
]

let agents = []
let attractors = []
let mouse = { x: -1000, y: -1000 }
let ctx = null
let dpr = 1
let raf = null
let lastTime = 0

function initAgents(w, h) {
  agents = []
  for (let i = 0; i < AGENT_COUNT; i++) {
    const c = palette[Math.floor(Math.random() * palette.length)]
    const hx = Math.random()
    const hy = Math.random()
    agents.push({
      x: hx * w, y: hy * h,
      vx: (Math.random() - 0.5) * 0.4,
      vy: (Math.random() - 0.5) * 0.4,
      size: 1.5 + Math.random() * 2.5,
      color: c,
      homeX: hx, homeY: hy,
      phase: Math.random() * Math.PI * 2,
    })
  }
}

function initAttractors() {
  attractors = []
  for (let i = 0; i < NUM_ATTRACTORS; i++) {
    attractors.push({
      x: Math.random(), y: Math.random(),
      vx: (Math.random() - 0.5) * 0.0008,
      vy: (Math.random() - 0.5) * 0.0008,
      strength: 0, targetStrength: 0,
      radius: 120 + Math.random() * 80,
      nextActivate: 3 + Math.random() * 8,
      activeDuration: 0,
      maxDuration: 4 + Math.random() * 6,
    })
  }
}

function resize() {
  if (!containerRef.value || !canvasRef.value) return
  const w = containerRef.value.clientWidth
  const h = containerRef.value.clientHeight
  dpr = window.devicePixelRatio || 1
  canvasRef.value.width = w * dpr
  canvasRef.value.height = h * dpr
  canvasRef.value.style.width = w + 'px'
  canvasRef.value.style.height = h + 'px'
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
}

function animate(timestamp) {
  if (!containerRef.value) return
  const W = containerRef.value.clientWidth
  const H = containerRef.value.clientHeight
  const time = timestamp * 0.001
  const dt = Math.min(time - lastTime, 0.05)
  lastTime = time
  ctx.clearRect(0, 0, W, H)

  // Update attractors
  for (const att of attractors) {
    att.x += att.vx
    att.y += att.vy
    if (att.x < 0.05 || att.x > 0.95) att.vx *= -1
    if (att.y < 0.05 || att.y > 0.95) att.vy *= -1
    att.x = Math.max(0.05, Math.min(0.95, att.x))
    att.y = Math.max(0.05, Math.min(0.95, att.y))

    if (att.targetStrength === 0) {
      att.nextActivate -= dt
      if (att.nextActivate <= 0) {
        att.targetStrength = 0.0015 + Math.random() * 0.001
        att.activeDuration = 0
        att.maxDuration = 4 + Math.random() * 6
        att.vx = (Math.random() - 0.5) * 0.001
        att.vy = (Math.random() - 0.5) * 0.001
      }
    } else {
      att.activeDuration += dt
      if (att.activeDuration >= att.maxDuration) {
        att.targetStrength = 0
        att.nextActivate = 5 + Math.random() * 10
        att.radius = 120 + Math.random() * 80
      }
    }
    att.strength += (att.targetStrength - att.strength) * 0.02
  }

  // Update agents
  for (let i = 0; i < agents.length; i++) {
    const a = agents[i]
    a.vx += (a.homeX * W - a.x) * HOME_FORCE
    a.vy += (a.homeY * H - a.y) * HOME_FORCE
    a.vx += Math.sin(time * 0.4 + a.phase) * 0.012
    a.vy += Math.cos(time * 0.3 + a.phase * 1.7) * 0.012

    for (const att of attractors) {
      if (att.strength < 0.0001) continue
      const ax = att.x * W, ay = att.y * H
      const dx = ax - a.x, dy = ay - a.y
      const d = Math.sqrt(dx * dx + dy * dy)
      if (d < att.radius && d > 15) {
        a.vx += (dx / d) * att.strength * (att.radius - d)
        a.vy += (dy / d) * att.strength * (att.radius - d)
      }
      if (d < att.radius * 0.7 && d > 20) {
        a.vx += (-dy / d) * att.strength * 0.3
        a.vy += (dx / d) * att.strength * 0.3
      }
    }

    for (let j = i + 1; j < agents.length; j++) {
      const b = agents[j]
      const dx = b.x - a.x, dy = b.y - a.y
      const d = Math.sqrt(dx * dx + dy * dy)
      if (d < 20 && d > 1) {
        const rep = 0.004 * (1 - d / 20)
        a.vx -= (dx / d) * rep
        a.vy -= (dy / d) * rep
        b.vx += (dx / d) * rep
        b.vy += (dy / d) * rep
      }
    }

    const mdx = mouse.x - a.x, mdy = mouse.y - a.y
    const mdist = Math.sqrt(mdx * mdx + mdy * mdy)
    if (mdist < MOUSE_RADIUS && mdist > 1) {
      const force = MOUSE_FORCE * (1 - mdist / MOUSE_RADIUS)
      a.vx += (mdx / mdist) * force
      a.vy += (mdy / mdist) * force
    }

    a.vx *= FRICTION
    a.vy *= FRICTION
    a.x += a.vx
    a.y += a.vy

    if (a.x < 10) a.vx += 0.15
    if (a.x > W - 10) a.vx -= 0.15
    if (a.y < 10) a.vy += 0.15
    if (a.y > H - 10) a.vy -= 0.15
  }

  // Draw connections
  ctx.lineWidth = 0.5
  for (let i = 0; i < agents.length; i++) {
    for (let j = i + 1; j < agents.length; j++) {
      const a = agents[i], b = agents[j]
      const dx = a.x - b.x, dy = a.y - b.y
      const d = Math.sqrt(dx * dx + dy * dy)
      if (d < CONNECTION_DIST) {
        const alpha = (1 - d / CONNECTION_DIST) * 0.2
        ctx.beginPath()
        ctx.moveTo(a.x, a.y)
        ctx.lineTo(b.x, b.y)
        ctx.strokeStyle = `rgba(${(a.color.r + b.color.r) >> 1},${(a.color.g + b.color.g) >> 1},${(a.color.b + b.color.b) >> 1},${alpha})`
        ctx.stroke()
      }
    }
  }

  // Draw agents
  for (const a of agents) {
    const pulse = 1 + Math.sin(time * 1.5 + a.phase) * 0.12
    const s = a.size * pulse

    const grad = ctx.createRadialGradient(a.x, a.y, 0, a.x, a.y, s * 6)
    grad.addColorStop(0, `rgba(${a.color.r},${a.color.g},${a.color.b},0.2)`)
    grad.addColorStop(0.4, `rgba(${a.color.r},${a.color.g},${a.color.b},0.05)`)
    grad.addColorStop(1, `rgba(${a.color.r},${a.color.g},${a.color.b},0)`)
    ctx.beginPath()
    ctx.arc(a.x, a.y, s * 6, 0, Math.PI * 2)
    ctx.fillStyle = grad
    ctx.fill()

    ctx.beginPath()
    ctx.arc(a.x, a.y, s, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(${a.color.r},${a.color.g},${a.color.b},0.85)`
    ctx.fill()

    ctx.beginPath()
    ctx.arc(a.x, a.y, s * 0.35, 0, Math.PI * 2)
    ctx.fillStyle = 'rgba(255,255,255,0.3)'
    ctx.fill()
  }

  raf = requestAnimationFrame(animate)
}

function onMouseMove(e) {
  if (!canvasRef.value) return
  const rect = canvasRef.value.getBoundingClientRect()
  mouse.x = e.clientX - rect.left
  mouse.y = e.clientY - rect.top
}

function onMouseLeave() {
  mouse.x = -1000
  mouse.y = -1000
}

onMounted(() => {
  ctx = canvasRef.value.getContext('2d')
  resize()
  const W = containerRef.value.clientWidth
  const H = containerRef.value.clientHeight
  initAttractors()
  initAgents(W, H)
  lastTime = performance.now() * 0.001
  raf = requestAnimationFrame(animate)

  const parent = containerRef.value.parentElement
  parent.addEventListener('mousemove', onMouseMove)
  parent.addEventListener('mouseleave', onMouseLeave)
  window.addEventListener('resize', resize)
})

onUnmounted(() => {
  cancelAnimationFrame(raf)
  const parent = containerRef.value?.parentElement
  if (parent) {
    parent.removeEventListener('mousemove', onMouseMove)
    parent.removeEventListener('mouseleave', onMouseLeave)
  }
  window.removeEventListener('resize', resize)
})
</script>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/HeroSwarm.vue
git commit -m "feat: add interactive swarm canvas with attractor-based clustering"
```

---

### Task 8: Supporting Landing Page Components

**Files:**
- Create: `frontend/src/components/ExperienceStep.vue`
- Create: `frontend/src/components/PricingCard.vue`
- Create: `frontend/src/components/ProofCard.vue`
- Modify: `frontend/src/components/DemoCard.vue`

- [ ] **Step 1: Create ExperienceStep.vue**

Create `frontend/src/components/ExperienceStep.vue`:

```vue
<template>
  <div
    ref="stepRef"
    class="max-w-[1100px] mx-auto py-16 grid grid-cols-1 md:grid-cols-2 gap-16 items-center transition-all duration-800 ease-out"
    :class="[
      visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10',
      reverse ? 'md:direction-rtl' : '',
    ]"
  >
    <div :class="reverse ? 'md:order-2' : ''">
      <div class="font-mono text-sm text-ocean-cyan tracking-wide mb-2">{{ stepNumber }}</div>
      <h3 class="text-2xl font-bold text-mist-foam tracking-tight mb-3">
        <slot name="title" />
      </h3>
      <p class="text-base text-mist-drift leading-relaxed">
        <slot name="description" />
      </p>
      <p v-if="$slots.detail" class="mt-3 text-sm text-mist-slate">
        <slot name="detail" />
      </p>
    </div>
    <div :class="reverse ? 'md:order-1' : ''">
      <div class="bg-ocean-deep border border-mist-depth rounded-2xl overflow-hidden transition-all duration-500 ease-spring hover:-translate-y-1 hover:shadow-[0_16px_48px_rgba(0,0,0,0.3)]">
        <div class="px-4 py-2.5 bg-ocean-abyss border-b border-mist-depth flex gap-1.5">
          <div class="w-2 h-2 rounded-full bg-coral" />
          <div class="w-2 h-2 rounded-full bg-coral-sand" />
          <div class="w-2 h-2 rounded-full bg-organic-sage" />
        </div>
        <div class="p-6 min-h-[240px]">
          <slot name="mockup" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

defineProps({
  stepNumber: { type: String, required: true },
  reverse: { type: Boolean, default: false },
})

const stepRef = ref(null)
const visible = ref(false)
let observer = null

onMounted(() => {
  observer = new IntersectionObserver(
    ([entry]) => { if (entry.isIntersecting) visible.value = true },
    { threshold: 0.2 }
  )
  if (stepRef.value) observer.observe(stepRef.value)
})

onUnmounted(() => observer?.disconnect())
</script>
```

- [ ] **Step 2: Create PricingCard.vue**

Create `frontend/src/components/PricingCard.vue`:

```vue
<template>
  <div
    class="relative overflow-hidden rounded-2xl border p-9 text-center transition-all duration-350 ease-spring hover:-translate-y-1.5 hover:shadow-[0_12px_40px_rgba(0,0,0,0.3)]"
    :class="[
      featured
        ? 'border-ocean-teal bg-gradient-to-b from-ocean-deep to-ocean-abyss shadow-[0_0_40px_rgba(14,116,144,0.1)]'
        : 'border-mist-depth bg-ocean-deep hover:border-ocean-teal',
    ]"
  >
    <!-- Top accent line -->
    <div
      class="absolute top-0 left-0 right-0 h-[3px] transition-opacity duration-300"
      :class="featured ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'"
      :style="{ background: accentColor }"
    />

    <div v-if="featured" class="absolute top-4 right-4 text-[11px] font-semibold uppercase tracking-wider text-ocean-glow bg-ocean-glow/10 border border-ocean-glow/20 px-2.5 py-1 rounded-full">
      Most popular
    </div>

    <div class="text-lg font-bold text-mist-foam mb-1">{{ name }}</div>
    <div class="font-mono text-sm text-mist-slate mb-5">{{ credits }} credits</div>
    <div class="text-5xl font-extrabold tracking-tight mb-1 transition-transform duration-300 hover:scale-105" :style="{ color: accentColor }">
      {{ price }}
    </div>
    <div class="text-sm text-mist-slate mb-6">one-time</div>

    <ul class="text-left mb-7 space-y-1.5">
      <li v-for="feature in features" :key="feature" class="flex items-center gap-2 text-sm text-mist-drift">
        <span class="w-1.5 h-1.5 rounded-full flex-shrink-0" :style="{ background: accentColor, boxShadow: `0 0 6px ${accentColor}` }" />
        {{ feature }}
      </li>
    </ul>

    <button
      class="w-full py-3 rounded-xl text-[15px] font-semibold transition-all duration-250 ease-spring"
      :class="featured
        ? 'bg-gradient-to-br from-ocean-cyan to-cyan-500 text-white glow-cyan hover:glow-cyan-lg hover:-translate-y-0.5'
        : 'bg-transparent text-mist-drift border border-mist-depth hover:border-ocean-teal hover:text-mist-foam hover:bg-ocean-teal/20 hover:-translate-y-0.5 hover:shadow-[0_4px_16px_rgba(0,0,0,0.2)]'"
    >
      Get started
    </button>
  </div>
</template>

<script setup>
defineProps({
  name: { type: String, required: true },
  credits: { type: Number, required: true },
  price: { type: String, required: true },
  features: { type: Array, required: true },
  accentColor: { type: String, default: '#22D3EE' },
  featured: { type: Boolean, default: false },
})
</script>
```

- [ ] **Step 3: Create ProofCard.vue**

Create `frontend/src/components/ProofCard.vue`:

```vue
<template>
  <div class="bg-ocean-deep border border-mist-depth rounded-xl p-7 text-left transition-all duration-350 ease-spring hover:-translate-y-1 hover:border-ocean-teal">
    <p class="text-[15px] text-mist italic leading-relaxed mb-4">
      "{{ quote }}"
    </p>
    <div class="text-sm font-semibold text-mist-foam">{{ author }}</div>
    <div class="text-xs text-mist-slate">{{ role }}</div>
  </div>
</template>

<script setup>
defineProps({
  quote: { type: String, required: true },
  author: { type: String, required: true },
  role: { type: String, required: true },
})
</script>
```

- [ ] **Step 4: Restyle DemoCard.vue for dark theme**

Replace `frontend/src/components/DemoCard.vue`:

```vue
<template>
  <router-link
    :to="`/demo/${slug}`"
    class="block p-6 bg-ocean-deep border border-mist-depth rounded-xl
           transition-all duration-350 ease-spring
           hover:-translate-y-1 hover:border-ocean-teal hover:shadow-[0_8px_32px_rgba(0,0,0,0.3)]"
  >
    <h3 class="font-semibold text-mist-foam mb-2">{{ title }}</h3>
    <p class="text-sm text-mist-drift">{{ description }}</p>
    <div class="mt-4 text-sm text-ocean-glow font-medium">View demo &rarr;</div>
  </router-link>
</template>

<script setup>
defineProps({
  slug: { type: String, required: true },
  title: { type: String, required: true },
  description: { type: String, default: '' },
})
</script>
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ExperienceStep.vue frontend/src/components/PricingCard.vue frontend/src/components/ProofCard.vue frontend/src/components/DemoCard.vue
git commit -m "feat: add landing page components (ExperienceStep, PricingCard, ProofCard, restyle DemoCard)"
```

---

### Task 9: Restyle CreditBadge for Dark Theme

**Files:**
- Modify: `frontend/src/components/CreditBadge.vue`

- [ ] **Step 1: Replace CreditBadge.vue**

Replace `frontend/src/components/CreditBadge.vue`:

```vue
<template>
  <span
    class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-sm font-semibold cursor-pointer transition-all duration-300 hover:-translate-y-px"
    :class="creditsStore.isLow
      ? 'bg-coral/10 border border-coral/20 text-coral hover:bg-coral/[0.18] hover:shadow-[0_0_16px_rgba(255,107,107,0.15)]'
      : 'bg-organic-sage/10 border border-organic-seafoam/20 text-organic-seafoam hover:bg-organic-sage/[0.18] hover:shadow-[0_0_16px_rgba(110,231,183,0.15)]'"
  >
    <span class="transition-transform duration-400 ease-spring hover:rotate-90">&#x2295;</span>
    {{ creditsStore.balance }} credits
  </span>
</template>

<script setup>
import { useCreditsStore } from '../stores/credits.js'

const creditsStore = useCreditsStore()
</script>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/CreditBadge.vue
git commit -m "feat: restyle CreditBadge for dark ocean theme"
```

---

### Task 10: Landing Page Full Rebuild

**Files:**
- Modify: `frontend/src/views/Landing.vue`

- [ ] **Step 1: Replace Landing.vue**

Replace `frontend/src/views/Landing.vue`:

```vue
<template>
  <div>
    <ScrollProgress />

    <!-- Hero -->
    <section class="relative min-h-screen flex flex-col justify-center items-center text-center pt-20">
      <!-- Background gradient wash -->
      <div class="absolute inset-0 pointer-events-none"
        style="background: radial-gradient(ellipse 80% 60% at 50% 40%, rgba(14,116,144,0.12), transparent), radial-gradient(ellipse 60% 50% at 20% 80%, rgba(167,139,250,0.06), transparent), radial-gradient(ellipse 50% 40% at 80% 70%, rgba(255,107,107,0.04), transparent)"
      />

      <HeroSwarm />

      <h1 class="relative z-10 text-[clamp(36px,5vw,64px)] font-extrabold text-mist-foam tracking-[-0.03em] leading-[1.08] max-w-[720px]">
        What if you could watch<br>
        <HeroRotatingText /><br>
        form in real time?
      </h1>

      <p class="relative z-10 text-[clamp(16px,2vw,20px)] text-mist-drift max-w-[540px] mt-5 leading-relaxed">
        Upload a document. Launch a swarm of AI agents. Watch emergent intelligence reveal how markets, media, and people will react — before it happens.
      </p>

      <p class="relative z-10 text-sm text-mist-slate mt-3">Move your mouse to attract the swarm</p>

      <div class="relative z-10 flex gap-4 mt-10">
        <router-link
          to="/register"
          class="px-8 py-3.5 rounded-xl text-base font-bold text-white
                 bg-gradient-to-br from-coral to-coral-amber
                 glow-coral transition-all duration-250 ease-spring
                 hover:glow-coral-lg hover:-translate-y-0.5"
        >
          Get started
        </router-link>
        <a
          href="#experience"
          class="px-8 py-3.5 rounded-xl text-base font-semibold text-mist
                 border border-mist-depth/60
                 transition-all duration-300
                 hover:border-mist-slate hover:bg-mist-depth/40 hover:text-mist-foam"
        >
          See it in action &#x2193;
        </a>
      </div>

      <div class="relative z-10 flex gap-8 mt-12 text-sm text-mist-slate">
        <span class="flex items-center gap-1.5">&#x1F4B3; Pay-as-you-go credits</span>
        <span class="flex items-center gap-1.5">&#x26A1; Results in under 5 minutes</span>
        <span class="flex items-center gap-1.5">&#x1F30A; Up to 10,000 agent swarms</span>
      </div>
    </section>

    <!-- Divider -->
    <div class="max-w-[1100px] mx-auto h-px bg-gradient-to-r from-transparent via-mist-depth to-transparent" />

    <!-- Experience -->
    <section id="experience" class="px-4 md:px-8">
      <div class="text-center pt-24 pb-16 max-w-[1100px] mx-auto">
        <div class="text-[11px] font-bold uppercase tracking-[0.12em] text-ocean-cyan mb-3">How it works</div>
        <h2 class="text-[clamp(28px,3.5vw,40px)] font-extrabold text-mist-foam tracking-tight">
          Three steps. One living ecosystem.
        </h2>
        <p class="text-[17px] text-mist-drift mt-3 max-w-[540px] mx-auto">
          Drop your document, set your question, and let the swarm reveal what happens next.
        </p>
      </div>

      <ExperienceStep stepNumber="01 — Seed the ecosystem">
        <template #title>Drop your document</template>
        <template #description>
          Upload a press release, policy draft, earnings report, or campaign brief.
          The swarm reads it, extracts entities, and builds a living knowledge graph
          of every stakeholder, market force, and narrative thread.
        </template>
        <template #detail>Supports PDF, TXT, CSV, Markdown — up to 50,000 characters.</template>
        <template #mockup>
          <div class="border-2 border-dashed border-ocean-teal rounded-xl p-8 text-center transition-colors hover:border-ocean-cyan">
            <div class="text-4xl mb-2 animate-[float_4s_ease-in-out_infinite]">&#x1F30A;</div>
            <div class="text-[15px] text-mist-drift font-medium">Drop your document here</div>
            <div class="text-sm text-mist-slate mt-1.5">or click to browse</div>
            <div class="flex gap-2 justify-center mt-4">
              <span v-for="t in ['Press release', 'Policy draft', 'Report']" :key="t"
                class="text-[11px] text-mist-slate bg-ocean-abyss px-2.5 py-1 rounded-md border border-mist-depth">
                {{ t }}
              </span>
            </div>
          </div>
        </template>
      </ExperienceStep>

      <ExperienceStep stepNumber="02 — Watch the swarm evolve" :reverse="true">
        <template #title>Agents school and interact</template>
        <template #description>
          Hundreds of AI agents — each representing a market participant, journalist,
          regulator, or public voice — begin to interact. Watch opinion clusters form,
          alliances shift, and consensus emerge like a living ecosystem.
        </template>
        <template #detail>Real-time progress with agent chat replay.</template>
        <template #mockup>
          <div class="relative h-[220px] overflow-hidden">
            <div
              v-for="i in 24" :key="i"
              class="absolute rounded-full"
              :style="agentStyle(i)"
            />
          </div>
        </template>
      </ExperienceStep>

      <ExperienceStep stepNumber="03 — Insights surface naturally">
        <template #title>The ecosystem reveals patterns</template>
        <template #description>
          The swarm's emergent intelligence distills into a clear, scrollable narrative —
          key findings, sentiment shifts, coalition maps, and confidence scores.
          No PhD required. Just scroll and understand.
        </template>
        <template #detail>Export as PDF, JSON, or CSV for your team.</template>
        <template #mockup>
          <div
            v-for="insight in insights" :key="insight.label"
            class="bg-ocean-abyss border border-mist-depth rounded-lg p-4 mb-2.5 transition-transform duration-300 hover:translate-x-1"
            :style="{ borderLeftWidth: '3px', borderLeftColor: insight.color }"
          >
            <div class="text-[11px] font-semibold uppercase tracking-wider mb-1.5" :style="{ color: insight.color }">
              {{ insight.label }}
            </div>
            <div class="text-sm text-mist" :class="insight.mono ? 'font-mono text-mist-drift text-[13px]' : ''">
              {{ insight.text }}
            </div>
          </div>
        </template>
      </ExperienceStep>
    </section>

    <div class="max-w-[1100px] mx-auto h-px bg-gradient-to-r from-transparent via-mist-depth to-transparent" />

    <!-- Social Proof -->
    <section id="proof" class="py-20 px-4 md:px-8 max-w-[1100px] mx-auto text-center">
      <div class="text-[11px] font-bold uppercase tracking-[0.12em] text-ocean-cyan mb-3">Trusted by strategists</div>
      <h2 class="text-[clamp(24px,3vw,36px)] font-extrabold text-mist-foam tracking-tight">
        See what teams are building
      </h2>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mt-10">
        <ProofCard
          v-for="proof in proofs" :key="proof.author"
          :quote="proof.quote" :author="proof.author" :role="proof.role"
        />
      </div>
    </section>

    <div class="max-w-[1100px] mx-auto h-px bg-gradient-to-r from-transparent via-mist-depth to-transparent" />

    <!-- Pricing -->
    <section id="pricing" class="py-24 px-4 md:px-8 max-w-[1100px] mx-auto text-center">
      <div class="text-[11px] font-bold uppercase tracking-[0.12em] text-ocean-cyan mb-3">Simple pricing</div>
      <h2 class="text-[clamp(24px,3vw,36px)] font-extrabold text-mist-foam tracking-tight">
        Pay only for what you simulate
      </h2>
      <p class="text-[17px] text-mist-drift mt-2">No subscriptions. No hidden fees. Buy credits, run simulations.</p>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-5 mt-12">
        <PricingCard
          v-for="tier in pricingTiers" :key="tier.name"
          :name="tier.name" :credits="tier.credits" :price="tier.price"
          :features="tier.features" :accentColor="tier.accent" :featured="tier.featured"
        />
      </div>
    </section>

    <div class="max-w-[1100px] mx-auto h-px bg-gradient-to-r from-transparent via-mist-depth to-transparent" />

    <!-- Final CTA -->
    <section class="py-24 px-4 text-center relative overflow-hidden">
      <div class="absolute inset-0 pointer-events-none"
        style="background: radial-gradient(ellipse 70% 50% at 50% 50%, rgba(14,116,144,0.15), transparent), radial-gradient(ellipse 40% 40% at 30% 60%, rgba(255,107,107,0.05), transparent)"
      />
      <h2 class="relative text-[clamp(28px,4vw,44px)] font-extrabold text-mist-foam tracking-[-0.03em] mb-4">
        Ready to see what happens next?
      </h2>
      <p class="relative text-lg text-mist-drift mb-8">
        Upload your first document and watch the ecosystem come alive.
      </p>
      <router-link
        to="/register"
        class="relative inline-block px-10 py-4 rounded-xl text-lg font-bold text-white
               bg-gradient-to-br from-coral to-coral-amber
               glow-coral transition-all duration-250 ease-spring
               hover:glow-coral-lg hover:-translate-y-0.5"
      >
        Get started
      </router-link>
    </section>

    <!-- Footer -->
    <footer class="border-t border-mist-depth max-w-[1100px] mx-auto px-4 md:px-8 py-12 flex justify-between items-center text-sm text-mist-slate">
      <div class="flex items-center gap-2">
        <LogoWavePulse :size="24" :animated="false" />
        <span class="font-bold text-mist-drift">SimSwarm</span>
        <span>&copy; 2026</span>
      </div>
      <div class="flex gap-6">
        <a href="#" class="hover:text-mist-drift transition-colors">Privacy</a>
        <a href="#" class="hover:text-mist-drift transition-colors">Terms</a>
        <a href="#" class="hover:text-mist-drift transition-colors">Docs</a>
        <a href="#" class="hover:text-mist-drift transition-colors">GitHub</a>
      </div>
    </footer>
  </div>
</template>

<script setup>
import ScrollProgress from '../components/ScrollProgress.vue'
import HeroSwarm from '../components/HeroSwarm.vue'
import HeroRotatingText from '../components/HeroRotatingText.vue'
import ExperienceStep from '../components/ExperienceStep.vue'
import PricingCard from '../components/PricingCard.vue'
import ProofCard from '../components/ProofCard.vue'
import LogoWavePulse from '../components/LogoWavePulse.vue'

const insights = [
  { label: 'Key Finding', color: '#FF6B6B', text: 'Public sentiment shifts negative within 48 hours of announcement, driven by regulatory agent cluster.' },
  { label: 'Emerging Coalition', color: '#6EE7B7', text: 'Financial analysts and media agents converge on a "cautiously optimistic" narrative by round 3.' },
  { label: 'Confidence', color: '#A78BFA', text: 'Overall: 94.2% · Sentiment: 87.6% · Coalition stability: 91.0%', mono: true },
]

const proofs = [
  { quote: 'We simulated public reaction to our pricing change before announcing. The swarm predicted the exact backlash points our focus groups missed.', author: 'Head of Strategy', role: 'Fortune 500 CPG Company' },
  { quote: 'Replaced three weeks of consultant work with a 5-minute simulation. The coalition mapping alone saved our policy team dozens of hours.', author: 'Policy Director', role: 'Government Affairs Think Tank' },
  { quote: 'The guided story format means I can share simulation results directly with the C-suite. No translation needed — they just scroll.', author: 'VP of Communications', role: 'Global PR Agency' },
]

const pricingTiers = [
  { name: 'Starter', credits: 100, price: '$19', accent: '#22D3EE', featured: false,
    features: ['3-4 small simulations', 'Up to 500 agents per run', 'Full guided story results', 'PDF & JSON export'] },
  { name: 'Pro', credits: 500, price: '$79', accent: '#A78BFA', featured: true,
    features: ['15-20 medium simulations', 'Up to 2,000 agents per run', 'Priority GPU allocation', 'Full export suite'] },
  { name: 'Heavy', credits: 2000, price: '$249', accent: '#FBBF24', featured: false,
    features: ['Large-scale simulations', 'Up to 10,000 agents per run', 'Dedicated GPU instances', 'Priority support'] },
]

// Generate random swarm agent styles for step 2 mockup
const swarmColors = [
  { bg: '#22D3EE', glow: 'rgba(34,211,238,0.3)' },
  { bg: '#6EE7B7', glow: 'rgba(110,231,183,0.3)' },
  { bg: '#FF6B6B', glow: 'rgba(255,107,107,0.3)' },
  { bg: '#A78BFA', glow: 'rgba(167,139,250,0.3)' },
  { bg: '#FBBF24', glow: 'rgba(251,191,36,0.3)' },
]

// Pre-compute random values at module level for SSR consistency
const agentSeeds = Array.from({ length: 24 }, (_, i) => ({
  size: 6 + ((i * 7 + 3) % 10),
  colorIdx: i % swarmColors.length,
  left: 10 + ((i * 13 + 5) % 80),
  top: 10 + ((i * 17 + 7) % 80),
  dur: 5 + ((i * 3) % 6),
  delay: -((i * 2) % 5),
  x1: ((i * 11 + 3) % 60) - 30, y1: ((i * 7 + 5) % 60) - 30,
  x2: ((i * 13 + 7) % 60) - 30, y2: ((i * 9 + 11) % 60) - 30,
  x3: ((i * 5 + 13) % 60) - 30, y3: ((i * 11 + 3) % 60) - 30,
  x4: ((i * 7 + 17) % 60) - 30, y4: ((i * 13 + 5) % 60) - 30,
  opacity: 0.5 + ((i * 3) % 5) / 10,
}))

function agentStyle(i) {
  const s = agentSeeds[i - 1]
  const c = swarmColors[s.colorIdx]
  return {
    width: s.size + 'px', height: s.size + 'px',
    background: c.bg,
    boxShadow: `0 0 ${s.size}px ${c.glow}`,
    left: s.left + '%', top: s.top + '%',
    opacity: s.opacity,
    animation: `swim ${s.dur}s ease-in-out infinite alternate`,
    animationDelay: s.delay + 's',
    '--x1': s.x1 + 'px', '--y1': s.y1 + 'px',
    '--x2': s.x2 + 'px', '--y2': s.y2 + 'px',
    '--x3': s.x3 + 'px', '--y3': s.y3 + 'px',
    '--x4': s.x4 + 'px', '--y4': s.y4 + 'px',
  }
}
</script>

<style scoped>
@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-8px); }
}
@keyframes swim {
  0% { transform: translate(0, 0); }
  25% { transform: translate(var(--x1), var(--y1)); }
  50% { transform: translate(var(--x2), var(--y2)); }
  75% { transform: translate(var(--x3), var(--y3)); }
  100% { transform: translate(var(--x4), var(--y4)); }
}
</style>
```

- [ ] **Step 2: Verify the full landing page**

Run: `cd frontend && npm run dev`
Open: `http://localhost:3000`

Expected:
- Dark ocean background everywhere
- Frosted glass navbar with Wave Pulse logo
- Hero with interactive swarm canvas, rotating text, gradient CTAs
- Scroll progress bar tracks position
- 3 experience steps fade in on scroll
- Social proof cards
- Pricing cards with accent glows and hover lift on all buttons
- Final CTA section
- Footer with static logo

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/Landing.vue
git commit -m "feat: rebuild landing page with interactive swarm, rotating headline, deep ocean theme"
```

---

### Task 11: Verify Full Build

- [ ] **Step 1: Run the production build**

Run: `cd frontend && npm run build`
Expected: Build completes with no errors. Output in `dist/`.

- [ ] **Step 2: Run frontend tests to check nothing is broken**

Run: `cd frontend && npm test -- --run`
Expected: Tests pass (some may need minor color/class updates if they assert on old styles — note any failures).

- [ ] **Step 3: Commit any test fixes**

If tests needed updates:
```bash
git add -u
git commit -m "fix: update tests for dark theme class changes"
```
