<template>
  <div class="min-h-screen flex items-center justify-center">
    <div class="max-w-md w-full space-y-8 p-8 bg-ocean-deep border border-mist-depth rounded-2xl">
      <div>
        <h2 class="text-3xl font-bold text-center text-mist-foam">Sign in to SimSwarm</h2>
      </div>
      <form @submit.prevent="handleLogin" class="space-y-4">
        <div v-if="error" class="bg-coral/10 border border-coral/20 text-coral rounded-xl p-3 text-sm">{{ error }}</div>
        <div>
          <label for="email" class="block text-sm font-medium text-mist-drift">Email</label>
          <input
            id="email"
            v-model="email"
            type="email"
            required
            class="mt-1 block w-full px-3 py-2 border border-mist-depth rounded-xl bg-ocean-abyss text-mist focus:outline-none focus:ring-2 focus:ring-ocean-cyan focus:border-ocean-cyan"
            placeholder="you@example.com"
          />
        </div>
        <div>
          <label for="password" class="block text-sm font-medium text-mist-drift">Password</label>
          <input
            id="password"
            v-model="password"
            type="password"
            required
            class="mt-1 block w-full px-3 py-2 border border-mist-depth rounded-xl bg-ocean-abyss text-mist focus:outline-none focus:ring-2 focus:ring-ocean-cyan focus:border-ocean-cyan"
            placeholder="••••••••"
          />
        </div>
        <button
          type="submit"
          :disabled="loading"
          class="w-full flex justify-center py-2 px-4 border border-transparent rounded-xl text-sm font-medium text-white bg-gradient-to-br from-ocean-cyan to-cyan-500 hover:shadow-[0_0_24px_rgba(14,116,144,0.4)] transition-all ease-spring focus:outline-none disabled:opacity-50"
        >
          {{ loading ? 'Signing in...' : 'Sign in' }}
        </button>
      </form>
      <p class="text-center text-sm text-mist-slate">
        Don't have an account?
        <router-link to="/register" class="text-ocean-glow hover:underline">Register</router-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { login } from '../api/auth.js'

const router = useRouter()
const authStore = useAuthStore()

const email = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  loading.value = true
  error.value = ''
  try {
    const data = await login(email.value, password.value)
    authStore.setAuth(data.user, data.token)
    router.push('/dashboard')
  } catch (err) {
    error.value = err.response?.data?.message || 'Login failed. Please try again.'
  } finally {
    loading.value = false
  }
}
</script>
