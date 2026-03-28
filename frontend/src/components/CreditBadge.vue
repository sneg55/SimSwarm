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
