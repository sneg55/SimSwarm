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
      <div v-else class="divide-y divide-mist-depth">
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
    </div>

    <!-- Settings Section -->
    <div class="bg-ocean-deep border border-mist-depth rounded-2xl p-6 mb-6">
      <h2 class="text-lg font-semibold text-mist-foam mb-6">Settings</h2>

      <!-- Password Change -->
      <div class="mb-8">
        <h3 class="text-base font-medium text-mist-drift mb-4">Change Password</h3>
        <form @submit.prevent="handleChangePassword" class="space-y-4">
          <div>
            <label class="block text-sm text-mist-slate mb-1.5">Current password</label>
            <input
              v-model="pwForm.current"
              type="password"
              autocomplete="current-password"
              class="w-full bg-ocean-abyss border border-mist-depth rounded-lg px-4 py-2.5 text-mist-foam focus:outline-none focus:border-ocean-teal transition-colors"
              placeholder="••••••••"
            />
          </div>
          <div>
            <label class="block text-sm text-mist-slate mb-1.5">New password</label>
            <input
              v-model="pwForm.newPw"
              type="password"
              autocomplete="new-password"
              class="w-full bg-ocean-abyss border border-mist-depth rounded-lg px-4 py-2.5 text-mist-foam focus:outline-none focus:border-ocean-teal transition-colors"
              placeholder="••••••••"
            />
          </div>
          <div>
            <label class="block text-sm text-mist-slate mb-1.5">Confirm new password</label>
            <input
              v-model="pwForm.confirm"
              type="password"
              autocomplete="new-password"
              class="w-full bg-ocean-abyss border border-mist-depth rounded-lg px-4 py-2.5 text-mist-foam focus:outline-none focus:border-ocean-teal transition-colors"
              placeholder="••••••••"
            />
          </div>
          <div v-if="pwError" class="p-3 bg-coral/10 border border-coral/20 text-coral rounded text-sm">
            {{ pwError }}
          </div>
          <div v-if="pwSuccess" class="p-3 bg-organic-sage/10 border border-organic-sage/20 text-organic-seafoam rounded text-sm">
            Password updated successfully.
          </div>
          <button
            type="submit"
            :disabled="pwLoading"
            class="px-5 py-2.5 bg-ocean-teal text-ocean-deep font-semibold rounded-lg hover:bg-ocean-glow transition-colors disabled:opacity-50 text-sm"
          >
            {{ pwLoading ? 'Updating…' : 'Update password' }}
          </button>
        </form>
      </div>
    </div>

    <!-- Danger Zone -->
    <div class="bg-coral/5 border border-coral/20 rounded-2xl p-6">
      <h2 class="text-lg font-semibold text-coral mb-2">Danger Zone</h2>
      <p class="text-sm text-mist-drift mb-5">
        Permanently delete your account. This action cannot be undone — all your data will be removed.
      </p>

      <div v-if="!deleteConfirmVisible">
        <button
          @click="deleteConfirmVisible = true"
          class="px-5 py-2.5 bg-coral/10 border border-coral/30 text-coral font-semibold rounded-lg hover:bg-coral/20 transition-colors text-sm"
        >
          Delete my account
        </button>
      </div>

      <div v-else class="space-y-4">
        <p class="text-sm text-mist-drift">
          Type <span class="font-mono font-semibold text-coral">delete</span> below to confirm.
        </p>
        <input
          v-model="deleteConfirmInput"
          type="text"
          class="w-full bg-ocean-abyss border border-coral/30 rounded-lg px-4 py-2.5 text-mist-foam focus:outline-none focus:border-coral transition-colors"
          placeholder="delete"
        />
        <div v-if="deleteError" class="p-3 bg-coral/10 border border-coral/20 text-coral rounded text-sm">
          {{ deleteError }}
        </div>
        <div class="flex gap-3">
          <button
            @click="handleDeleteAccount"
            :disabled="deleteConfirmInput !== 'delete' || deleteLoading"
            class="px-5 py-2.5 bg-coral text-white font-semibold rounded-lg hover:bg-coral-light transition-colors disabled:opacity-40 text-sm"
          >
            {{ deleteLoading ? 'Deleting…' : 'Confirm deletion' }}
          </button>
          <button
            @click="cancelDelete"
            class="px-5 py-2.5 border border-mist-depth text-mist-drift rounded-lg hover:border-mist-slate transition-colors text-sm"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CreditBadge from '../components/CreditBadge.vue'
import SkeletonCard from '../components/SkeletonCard.vue'
import { useCreditsStore } from '../stores/credits.js'
import { useAuthStore } from '../stores/auth.js'
import { getPacks, getBalance, purchaseCredits, getHistory } from '../api/billing.js'
import { changePassword, deleteAccount } from '../api/profile.js'

const route = useRoute()
const router = useRouter()
const creditsStore = useCreditsStore()
const authStore = useAuthStore()

const paymentSuccess = computed(() => route.query.success === '1')
const paymentCancelled = computed(() => route.query.cancel === '1')

const history = ref([])
const historyLoading = ref(true)
const purchasing = ref(null)
const purchaseSuccess = ref(false)
const purchaseError = ref('')

// Password change state
const pwForm = ref({ current: '', newPw: '', confirm: '' })
const pwLoading = ref(false)
const pwError = ref('')
const pwSuccess = ref(false)

// Delete account state
const deleteConfirmVisible = ref(false)
const deleteConfirmInput = ref('')
const deleteLoading = ref(false)
const deleteError = ref('')

const creditPacks = ref([])

function formatPrice(priceCents) {
  return '$' + (priceCents / 100).toFixed(0)
}

onMounted(async () => {
  try {
    const [balanceData, historyData, packsData] = await Promise.all([
      getBalance(),
      getHistory(),
      getPacks(),
    ])
    creditsStore.setBalance(balanceData.balance ?? balanceData)
    history.value = historyData.transactions || historyData
    creditPacks.value = packsData.map(p => ({
      id: p.slug,
      credits: p.credits,
      price: formatPrice(p.price_cents),
      description: p.description,
    }))
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
    // Redirect to Stripe Checkout
    if (result.checkout_url) {
      window.location.href = result.checkout_url
      return
    }
    // Fallback if no redirect URL
    creditsStore.setBalance(result.balance ?? result)
    purchaseSuccess.value = true
    setTimeout(() => { purchaseSuccess.value = false }, 3000)
  } catch (err) {
    purchaseError.value = err.response?.data?.detail || err.response?.data?.message || 'Purchase failed.'
  } finally {
    purchasing.value = null
  }
}

async function handleChangePassword() {
  pwError.value = ''
  pwSuccess.value = false

  if (pwForm.value.newPw.length < 8) {
    pwError.value = 'New password must be at least 8 characters.'
    return
  }
  if (pwForm.value.newPw !== pwForm.value.confirm) {
    pwError.value = 'New passwords do not match.'
    return
  }

  pwLoading.value = true
  try {
    await changePassword(pwForm.value.current, pwForm.value.newPw)
    pwSuccess.value = true
    pwForm.value = { current: '', newPw: '', confirm: '' }
    setTimeout(() => { pwSuccess.value = false }, 4000)
  } catch (err) {
    pwError.value = err.response?.data?.detail || 'Failed to update password.'
  } finally {
    pwLoading.value = false
  }
}

async function handleDeleteAccount() {
  if (deleteConfirmInput.value !== 'delete') return
  deleteError.value = ''
  deleteLoading.value = true
  try {
    await deleteAccount()
    authStore.logout()
    router.push('/')
  } catch (err) {
    deleteError.value = err.response?.data?.detail || 'Failed to delete account.'
    deleteLoading.value = false
  }
}

function cancelDelete() {
  deleteConfirmVisible.value = false
  deleteConfirmInput.value = ''
  deleteError.value = ''
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  })
}
</script>
