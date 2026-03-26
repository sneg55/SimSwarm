<template>
  <span
    class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
    :class="creditsStore.isLow ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'"
  >
    <svg class="mr-1 h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
      <path d="M10 2a8 8 0 100 16A8 8 0 0010 2zm0 14a6 6 0 110-12 6 6 0 010 12zm1-9H9v2H7v2h2v2h2v-2h2v-2h-2V7z"/>
    </svg>
    {{ creditsStore.balance }} credits
  </span>
</template>

<script setup>
import { useCreditsStore } from '../stores/credits.js'

const creditsStore = useCreditsStore()
</script>
