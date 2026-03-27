<template>
  <nav class="bg-white border-b border-gray-200 sticky top-0 z-50">
    <div class="max-w-6xl mx-auto px-4">
      <div class="flex items-center justify-between h-16">
        <div class="flex items-center gap-6">
          <router-link to="/" class="text-xl font-bold text-blue-600">SimSwarm</router-link>
          <div v-if="authStore.isLoggedIn" class="flex items-center gap-4">
            <router-link
              to="/dashboard"
              class="text-sm text-gray-600 hover:text-gray-900"
              active-class="text-blue-600 font-medium"
            >
              Dashboard
            </router-link>
            <router-link
              to="/sim/new"
              class="text-sm text-gray-600 hover:text-gray-900"
              active-class="text-blue-600 font-medium"
            >
              New Simulation
            </router-link>
          </div>
        </div>

        <div class="flex items-center gap-4">
          <template v-if="authStore.isLoggedIn">
            <CreditBadge />
            <router-link
              to="/account"
              class="text-sm text-gray-600 hover:text-gray-900"
              active-class="text-blue-600 font-medium"
            >
              {{ authStore.user?.email }}
            </router-link>
            <button
              @click="handleLogout"
              class="text-sm text-gray-500 hover:text-gray-700"
            >
              Sign out
            </button>
          </template>
          <template v-else>
            <router-link
              to="/login"
              class="text-sm text-gray-600 hover:text-gray-900"
            >
              Sign in
            </router-link>
            <router-link
              to="/register"
              class="px-4 py-1.5 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700"
            >
              Get started
            </router-link>
          </template>
        </div>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import CreditBadge from './CreditBadge.vue'

const router = useRouter()
const authStore = useAuthStore()

function handleLogout() {
  authStore.logout()
  router.push('/')
}
</script>
