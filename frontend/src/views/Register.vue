<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50">
    <div class="max-w-md w-full space-y-8 p-8 bg-white rounded-lg shadow">
      <div>
        <h2 class="text-3xl font-bold text-center text-gray-900">Create your account</h2>
      </div>

      <!-- Post-registration verification notice -->
      <div v-if="registered" class="bg-blue-50 border border-blue-200 text-blue-800 p-4 rounded text-sm">
        <p class="font-medium">Account created successfully!</p>
        <p class="mt-1">Check your email for a verification link. You can still log in while your email is unverified.</p>
        <router-link to="/dashboard" class="mt-2 inline-block text-blue-600 hover:underline font-medium">
          Go to dashboard
        </router-link>
      </div>

      <form v-else @submit.prevent="handleRegister" class="space-y-4">
        <div v-if="error" class="bg-red-50 text-red-700 p-3 rounded text-sm">{{ error }}</div>
        <div>
          <label for="email" class="block text-sm font-medium text-gray-700">Email</label>
          <input
            id="email"
            v-model="email"
            type="email"
            required
            class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            placeholder="you@example.com"
          />
        </div>
        <div>
          <label for="password" class="block text-sm font-medium text-gray-700">Password</label>
          <input
            id="password"
            v-model="password"
            type="password"
            required
            minlength="8"
            class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            placeholder="••••••••"
          />
        </div>
        <button
          type="submit"
          :disabled="loading"
          class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none disabled:opacity-50"
        >
          {{ loading ? 'Creating account...' : 'Create account' }}
        </button>
      </form>

      <p v-if="!registered" class="text-center text-sm text-gray-600">
        Already have an account?
        <router-link to="/login" class="text-blue-600 hover:underline">Sign in</router-link>
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
