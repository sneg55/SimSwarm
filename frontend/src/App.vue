<template>
  <div class="min-h-screen bg-gray-50">
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
