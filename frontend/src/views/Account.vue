<template>
  <div class="max-w-3xl mx-auto px-4 py-8">
    <h1 class="text-2xl font-bold text-gray-900 mb-8">Account</h1>

    <!-- Balance Section -->
    <div class="bg-white border border-gray-200 rounded-lg p-6 mb-6">
      <h2 class="text-lg font-semibold text-gray-800 mb-4">Credit Balance</h2>
      <div class="flex items-center justify-between">
        <div>
          <div class="text-4xl font-bold text-blue-600">{{ creditsStore.balance }}</div>
          <div class="text-sm text-gray-500 mt-1">credits remaining</div>
        </div>
        <CreditBadge />
      </div>
    </div>

    <!-- Purchase Credits Section -->
    <div class="bg-white border border-gray-200 rounded-lg p-6 mb-6">
      <h2 class="text-lg font-semibold text-gray-800 mb-4">Buy Credits</h2>
      <div class="grid grid-cols-3 gap-4">
        <button
          v-for="pack in creditPacks"
          :key="pack.id"
          @click="handlePurchase(pack)"
          :disabled="purchasing === pack.id"
          class="border border-gray-200 rounded-lg p-4 text-center hover:border-blue-300 hover:bg-blue-50 transition-all disabled:opacity-50"
        >
          <div class="text-2xl font-bold text-blue-600">{{ pack.credits }}</div>
          <div class="text-sm text-gray-500">credits</div>
          <div class="font-semibold text-gray-800 mt-2">{{ pack.price }}</div>
        </button>
      </div>
      <div v-if="purchaseSuccess" class="mt-4 p-3 bg-green-50 text-green-700 rounded text-sm">
        Credits purchased successfully!
      </div>
      <div v-if="purchaseError" class="mt-4 p-3 bg-red-50 text-red-700 rounded text-sm">
        {{ purchaseError }}
      </div>
    </div>

    <!-- Transaction History -->
    <div class="bg-white border border-gray-200 rounded-lg p-6">
      <h2 class="text-lg font-semibold text-gray-800 mb-4">Transaction History</h2>
      <div v-if="historyLoading" class="text-center text-gray-500 py-4">Loading...</div>
      <div v-else-if="history.length === 0" class="text-center text-gray-400 py-4 text-sm">
        No transactions yet.
      </div>
      <div v-else class="divide-y divide-gray-100">
        <div
          v-for="tx in history"
          :key="tx.id"
          class="flex items-center justify-between py-3"
        >
          <div>
            <div class="text-sm font-medium text-gray-800">{{ tx.description }}</div>
            <div class="text-xs text-gray-500">{{ formatDate(tx.created_at) }}</div>
          </div>
          <div
            class="text-sm font-semibold"
            :class="tx.amount > 0 ? 'text-green-600' : 'text-red-600'"
          >
            {{ tx.amount > 0 ? '+' : '' }}{{ tx.amount }} credits
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import CreditBadge from '../components/CreditBadge.vue'
import { useCreditsStore } from '../stores/credits.js'
import { getBalance, purchaseCredits, getHistory } from '../api/billing.js'

const creditsStore = useCreditsStore()

const history = ref([])
const historyLoading = ref(true)
const purchasing = ref(null)
const purchaseSuccess = ref(false)
const purchaseError = ref('')

const creditPacks = [
  { id: 'starter', credits: 100, price: '$19' },
  { id: 'pro', credits: 500, price: '$79' },
  { id: 'heavy', credits: 2000, price: '$249' },
]

onMounted(async () => {
  try {
    const [balanceData, historyData] = await Promise.all([getBalance(), getHistory()])
    creditsStore.setBalance(balanceData.balance ?? balanceData)
    history.value = historyData.transactions || historyData
  } catch (err) {
    console.error('Failed to load account data:', err)
  } finally {
    historyLoading.value = false
  }
})

async function handlePurchase(pack) {
  purchasing.value = pack.id
  purchaseSuccess.value = false
  purchaseError.value = ''
  try {
    const result = await purchaseCredits(pack.id)
    creditsStore.setBalance(result.balance ?? result)
    purchaseSuccess.value = true
    setTimeout(() => { purchaseSuccess.value = false }, 3000)
  } catch (err) {
    purchaseError.value = err.response?.data?.message || 'Purchase failed.'
  } finally {
    purchasing.value = null
  }
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  })
}
</script>
