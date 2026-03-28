<template>
  <div class="space-y-3">
    <h3 class="text-sm font-medium text-mist-drift">Select Simulation Tier</h3>
    <div class="grid grid-cols-3 gap-3">
      <button
        v-for="tier in tiers"
        :key="tier.id"
        @click="selectTier(tier.id)"
        :disabled="!creditsStore.canAfford(tier.id)"
        :class="[
          'relative p-4 border rounded-xl text-left transition-all',
          selectedTier === tier.id
            ? 'border-ocean-cyan bg-ocean-cyan/10 ring-2 ring-ocean-cyan'
            : 'border-mist-depth hover:border-ocean-teal',
          !creditsStore.canAfford(tier.id)
            ? 'opacity-50 cursor-not-allowed bg-ocean-abyss/50'
            : 'cursor-pointer',
        ]"
      >
        <div class="font-medium text-mist-foam">{{ tier.label }}</div>
        <div class="text-sm text-mist-slate mt-1">{{ tier.description }}</div>
        <div class="mt-2 text-sm font-semibold text-ocean-glow">
          {{ creditsStore.getTierCost(tier.id) }} credits
        </div>
        <div v-if="!creditsStore.canAfford(tier.id)" class="text-xs text-coral mt-1">
          Insufficient credits
        </div>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useCreditsStore } from '../stores/credits.js'

const creditsStore = useCreditsStore()

const emit = defineEmits(['select'])

const selectedTier = ref(null)

const tiers = [
  { id: 'small', label: 'Small', description: '1-500 agents, < 30 min' },
  { id: 'medium', label: 'Medium', description: '501-2,000 agents, < 4 hrs' },
  { id: 'large', label: 'Large', description: '2,001-10,000 agents, < 12 hrs' },
]

function selectTier(tierId) {
  if (!creditsStore.canAfford(tierId)) return
  selectedTier.value = tierId
  emit('select', tierId)
}
</script>
