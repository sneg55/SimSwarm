<template>
  <div
    v-if="creditsStore.isLow"
    class="flex items-center gap-3 px-5 py-3 rounded-xl
           bg-coral-amber/8 border border-coral-amber/20 text-coral-amber"
  >
    <svg class="w-5 h-5 flex-shrink-0 opacity-80" fill="currentColor" viewBox="0 0 20 20">
      <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
    </svg>
    <p class="text-sm">
      Low credit balance ({{ creditsStore.balance }} credits).
      <router-link to="/account" class="font-semibold underline hover:text-coral transition-colors">
        Purchase more credits
      </router-link>
      to continue running simulations.
    </p>
  </div>
</template>

<script setup>
import { useCreditsStore } from '../stores/credits.js'

const creditsStore = useCreditsStore()
</script>
