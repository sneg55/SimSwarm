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
          <router-link to="/dashboard" class="nav-link">Dashboard</router-link>
          <router-link to="/sim/new" class="nav-link">New Simulation</router-link>
          <CreditBadge />
          <button
            @click="handleLogout"
            class="text-sm text-mist-drift hover:text-mist-foam transition-colors"
          >
            Sign out
          </button>
        </template>
        <template v-else>
          <router-link to="/login" class="nav-link">Sign in</router-link>
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

<style scoped>
.nav-link {
  font-size: 14px;
  font-weight: 500;
  color: #94A3B8;
  position: relative;
  padding-bottom: 2px;
  transition: color 0.3s;
}
.nav-link:hover {
  color: #F1F5F9;
}
.nav-link::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  width: 0;
  height: 2px;
  background: #22D3EE;
  border-radius: 1px;
  transition: width 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.nav-link:hover::after {
  width: 100%;
}
</style>
