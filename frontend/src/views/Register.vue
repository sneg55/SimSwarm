<template>
  <div class="min-h-screen flex items-center justify-center">
    <div class="max-w-md w-full space-y-8 p-8 bg-ocean-deep border border-mist-depth rounded-2xl">
      <div>
        <h2 class="text-3xl font-bold text-center text-mist-foam">Create your account</h2>
      </div>

      <!-- Post-registration verification notice -->
      <div v-if="registered" class="bg-ocean-cyan/10 border border-ocean-cyan/20 text-ocean-glow p-4 rounded-xl text-sm">
        <p class="font-medium">Account created successfully!</p>
        <p class="mt-1">Check your email for a verification link. You can still log in while your email is unverified.</p>
        <router-link to="/dashboard" class="mt-2 inline-block text-ocean-glow hover:underline font-medium">
          Go to dashboard
        </router-link>
      </div>

      <form v-else @submit.prevent="handleRegister" class="space-y-4">
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
            minlength="8"
            class="mt-1 block w-full px-3 py-2 border border-mist-depth rounded-xl bg-ocean-abyss text-mist focus:outline-none focus:ring-2 focus:ring-ocean-cyan focus:border-ocean-cyan"
            placeholder="••••••••"
          />
        </div>
        <button
          type="submit"
          :disabled="loading"
          class="w-full flex justify-center py-2 px-4 border border-transparent rounded-xl text-sm font-medium text-white bg-gradient-to-br from-ocean-cyan to-cyan-500 hover:shadow-[0_0_24px_rgba(14,116,144,0.4)] transition-all ease-spring focus:outline-none disabled:opacity-50"
        >
          {{ loading ? 'Creating account...' : 'Create account' }}
        </button>
      </form>

      <p v-if="!registered" class="text-center text-sm text-mist-slate">
        Already have an account?
        <router-link to="/login" class="text-ocean-glow hover:underline">Sign in</router-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAuthStore } from '../stores/auth.js'
import { register } from '../api/auth.js'

const authStore = useAuthStore()

const email = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')
const registered = ref(false)

async function handleRegister() {
  loading.value = true
  error.value = ''
  try {
    const data = await register(email.value, password.value)
    authStore.setAuth(data.user, data.token)
    registered.value = true
  } catch (err) {
    error.value = err.response?.data?.detail || err.response?.data?.message || 'Registration failed. Please try again.'
  } finally {
    loading.value = false
  }
}
</script>
