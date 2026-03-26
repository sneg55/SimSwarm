import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

// Tier costs in credits
const TIER_COSTS = {
  small: 30,
  medium: 90,
  large: 300,
}

const LOW_BALANCE_THRESHOLD = 30

export const useCreditsStore = defineStore('credits', () => {
  const balance = ref(0)

  const isLow = computed(() => balance.value < LOW_BALANCE_THRESHOLD)

  function setBalance(amount) {
    balance.value = amount
  }

  function canAfford(tier) {
    const cost = TIER_COSTS[tier] ?? Infinity
    return balance.value >= cost
  }

  function getTierCost(tier) {
    return TIER_COSTS[tier] ?? 0
  }

  function deduct(amount) {
    balance.value = Math.max(0, balance.value - amount)
  }

  return { balance, isLow, setBalance, canAfford, getTierCost, deduct }
})
