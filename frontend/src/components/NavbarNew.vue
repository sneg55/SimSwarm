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
