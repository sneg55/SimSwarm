<template>
  <div class="max-w-3xl mx-auto px-4 py-8">
    <h1 class="text-2xl font-bold text-mist-foam mb-8">Account</h1>

    <div v-if="paymentSuccess" class="bg-organic-sage/10 border border-organic-sage/20 text-organic-seafoam px-4 py-3 rounded-md mb-6">
      Payment successful! Your credits will be added shortly once the payment is confirmed.
    </div>
    <div v-if="paymentCancelled" class="bg-coral-amber/10 border border-coral-amber/20 text-coral-amber px-4 py-3 rounded-md mb-6">
      Payment was cancelled. You were not charged.
    </div>

    <!-- Balance Section -->
    <div class="bg-ocean-deep border border-mist-depth rounded-2xl p-6 mb-6">
      <h2 class="text-lg font-semibold text-mist-foam mb-4">Credit Balance</h2>
      <div class="flex items-center justify-between">
        <div>
          <div class="text-4xl font-bold text-ocean-glow">{{ creditsStore.balance }}</div>
          <div class="text-sm text-mist-slate mt-1">credits remaining</div>
        </div>
        <CreditBadge />
      </div>
    </div>

    <!-- Purchase Credits Section -->
    <div class="bg-ocean-deep border border-mist-depth rounded-2xl p-6 mb-6">
      <h2 class="text-lg font-semibold text-mist-foam mb-4">Buy Credits</h2>
      <div class="grid grid-cols-3 gap-4">
        <button
          v-for="pack in creditPacks"
          :key="pack.id"
          @click="handlePurchase(pack)"
          :disabled="purchasing === pack.id"
          class="border border-mist-depth rounded-2xl p-4 text-center hover:border-ocean-teal hover:bg-ocean-cyan/10 transition-all disabled:opacity-50"
        >
          <div class="text-2xl font-bold text-ocean-glow">{{ pack.credits }}</div>
          <div class="text-sm text-mist-slate">credits</div>
          <div class="font-semibold text-mist-foam mt-2">{{ pack.price }}</div>
        </button>
      </div>
      <div v-if="purchaseSuccess" class="mt-4 p-3 bg-organic-sage/10 border border-organic-sage/20 text-organic-seafoam rounded text-sm">
        Credits purchased successfully!
      </div>
      <div v-if="purchaseError" class="mt-4 p-3 bg-coral/10 border border-coral/20 text-coral rounded text-sm">
        {{ purchaseError }}
      </div>
    </div>

    <!-- Transaction History -->
    <div class="bg-ocean-deep border border-mist-depth rounded-2xl p-6 mb-6">
      <h2 class="text-lg font-semibold text-mist-foam mb-4">Transaction History</h2>
      <div v-if="historyLoading" class="space-y-6">
        <SkeletonCard :lines="1" />
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <SkeletonCard v-for="i in 3" :key="i" :lines="2" />
        </div>
      </div>
      <div v-else-if="history.length === 0" class="text-center text-mist-slate py-4 text-sm">
        No transactions yet.
      </div>
      <div v-else>
        <div class="divide-y divide-mist-depth">
          <div
            v-for="tx in history"
            :key="tx.id"
            class="flex items-center justify-between py-3"
          >
            <div>
              <div class="text-sm font-medium text-mist-foam">{{ tx.description }}</div>
              <div class="text-xs text-mist-slate">{{ formatDate(tx.created_at) }}</div>
            </div>
            <div
              class="text-sm font-semibold"
              :class="tx.amount > 0 ? 'text-organic-seafoam' : 'text-coral'"
            >
              {{ tx.amount > 0 ? '+' : '' }}{{ tx.amount }} credits
            </div>
          </div>
        </div>
        <div v-if="history.length < historyTotal" class="mt-4 flex items-center justify-between">
          <span class="text-xs text-mist-slate">
            Showing {{ history.length }} of {{ historyTotal }}
          </span>
          <button
            @click="loadMoreHistory"
            :disabled="historyLoadingMore"
            class="px-4 py-2 text-sm font-medium text-mist-drift border border-mist-depth rounded-lg hover:border-ocean-teal hover:text-mist-foam transition-colors disabled:opacity-50"
          >
            {{ historyLoadingMore ? 'Loading…' : 'Load more' }}
          </button>
        </div>
      </div>
    </div>

    <AccountSettings />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import CreditBadge from '../components/CreditBadge.vue'
import SkeletonCard from '../components/SkeletonCard.vue'
import AccountSettings from '../components/AccountSettings.vue'
import { useCreditsStore } from '../stores/credits.js'
import { getPacks, getBalance, purchaseCredits, getHistory } from '../api/billing.js'
import { useStripeReturnPolling } from '../composables/useStripeReturnPolling.js'

const route = useRoute()
const creditsStore = useCreditsStore()

const paymentSuccess = computed(() => route.query.success === '1')
const paymentCancelled = computed(() => route.query.cancel === '1')

const HISTORY_PAGE_SIZE = 20

const history = ref([])
const historyTotal = ref(0)
const historyLoading = ref(true)
const historyLoadingMore = ref(false)
const purchasing = ref(null)
const purchaseSuccess = ref(false)
const purchaseError = ref('')
const creditPacks = ref([])

const { start: startBalancePoll } = useStripeReturnPolling({ getBalance, creditsStore })

function formatPrice(priceCents) {
  return '$' + (priceCents / 100).toFixed(0)
}

onMounted(async () => {
  try {
    const [balanceData, historyData, packsData] = await Promise.all([
      getBalance(),
      getHistory({ limit: HISTORY_PAGE_SIZE, offset: 0 }),
      getPacks(),
    ])
    const initialBalance = balanceData.balance ?? balanceData
    creditsStore.setBalance(initialBalance)
    history.value = historyData.entries
    historyTotal.value = historyData.total
    creditPacks.value = packsData.map(p => ({
      id: p.slug,
      credits: p.credits,
      price: formatPrice(p.price_cents),
      description: p.description,
    }))
    if (paymentSuccess.value) {
      startBalancePoll(initialBalance)
    }
  } catch (err) {
    console.error('Failed to load account data:', err)
  } finally {
    historyLoading.value = false
  }
})

async function loadMoreHistory() {
  if (historyLoadingMore.value) return
  historyLoadingMore.value = true
  try {
    const next = await getHistory({ limit: HISTORY_PAGE_SIZE, offset: history.value.length })
    history.value.push(...next.entries)
    historyTotal.value = next.total
  } catch (err) {
    console.error('Failed to load more history:', err)
  } finally {
    historyLoadingMore.value = false
  }
}

async function handlePurchase(pack) {
  purchasing.value = pack.id
  purchaseSuccess.value = false
  purchaseError.value = ''
  try {
    const result = await purchaseCredits(pack.id)
    if (result.checkout_url) {
      window.location.href = result.checkout_url
      return
    }
    creditsStore.setBalance(result.balance ?? result)
    purchaseSuccess.value = true
    setTimeout(() => { purchaseSuccess.value = false }, 3000)
  } catch (err) {
    purchaseError.value = err.response?.data?.detail || err.response?.data?.message || 'Purchase failed.'
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
