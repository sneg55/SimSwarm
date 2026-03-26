<template>
  <div class="space-y-3">
    <h3 class="text-sm font-medium text-gray-700">Select Simulation Tier</h3>
    <div class="grid grid-cols-3 gap-3">
      <button
        v-for="tier in tiers"
        :key="tier.id"
        @click="selectTier(tier.id)"
        :disabled="!creditsStore.canAfford(tier.id)"
        :class="[
          'relative p-4 border rounded-lg text-left transition-all',
          selectedTier === tier.id
            ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-500'
            : 'border-gray-200 hover:border-blue-300',
          !creditsStore.canAfford(tier.id)
            ? 'opacity-50 cursor-not-allowed bg-gray-50'
            : 'cursor-pointer',
        ]"
      >
        <div class="font-medium text-gray-900 capitalize">{{ tier.id }}</div>
        <div class="text-sm text-gray-500 mt-1">{{ tier.description }}</div>
        <div class="mt-2 text-sm font-semibold text-blue-600">
          {{ creditsStore.getTierCost(tier.id) }} credits
        </div>
        <div v-if="!creditsStore.canAfford(tier.id)" class="text-xs text-red-500 mt-1">
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
  { id: 'lite', description: '~2 min, basic analysis' },
  { id: 'standard', description: '~5 min, full pipeline' },
  { id: 'pro', description: '~15 min, deep research' },
]

function selectTier(tierId) {
  if (!creditsStore.canAfford(tierId)) return
  selectedTier.value = tierId
  emit('select', tierId)
}
</script>
