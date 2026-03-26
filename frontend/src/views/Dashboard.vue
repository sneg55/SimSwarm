<template>
  <div class="max-w-6xl mx-auto px-4 py-8">
    <div class="flex items-center justify-between mb-8">
      <h1 class="text-2xl font-bold text-gray-900">Dashboard</h1>
      <div class="flex items-center gap-4">
        <CreditBadge />
        <router-link
          to="/sim/new"
          class="inline-flex items-center px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700"
        >
          New Simulation
        </router-link>
      </div>
    </div>

    <CreditWarning />

    <div class="mt-6">
      <h2 class="text-lg font-semibold text-gray-800 mb-4">Recent Simulations</h2>

      <div v-if="loading" class="text-center py-12 text-gray-500">Loading jobs...</div>

      <div v-else-if="jobs.length === 0" class="text-center py-12 bg-gray-50 rounded-lg">
        <p class="text-gray-500">No simulations yet.</p>
        <router-link to="/sim/new" class="mt-2 text-blue-600 hover:underline text-sm">
          Run your first simulation
        </router-link>
      </div>

      <div v-else class="space-y-3">
        <div
          v-for="job in jobs"
          :key="job.id"
          class="flex items-center justify-between p-4 bg-white border border-gray-200 rounded-lg hover:border-blue-300 transition-colors"
        >
          <div>
            <div class="font-medium text-gray-900">{{ job.goal || 'Simulation' }}</div>
            <div class="text-sm text-gray-500 mt-1">
              {{ job.tier }} tier &bull; {{ formatDate(job.created_at) }}
            </div>
          </div>
          <div class="flex items-center gap-3">
            <span
              class="text-xs px-2 py-1 rounded-full font-medium"
              :class="statusClass(job.status)"
            >
              {{ job.status }}
            </span>
            <router-link
              v-if="job.status === 'completed'"
              :to="`/sim/${job.id}/results`"
              class="text-sm text-blue-600 hover:underline"
            >
              View Results
            </router-link>
            <router-link
              v-else-if="job.status === 'running' || job.status === 'pending'"
              :to="`/sim/${job.id}`"
              class="text-sm text-blue-600 hover:underline"
            >
              View Progress
            </router-link>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import CreditBadge from '../components/CreditBadge.vue'
import CreditWarning from '../components/CreditWarning.vue'
import { listJobs } from '../api/jobs.js'
import { getBalance } from '../api/billing.js'
import { useCreditsStore } from '../stores/credits.js'

const creditsStore = useCreditsStore()
const jobs = ref([])
const loading = ref(true)

onMounted(async () => {
  try {
    const [jobData, balanceData] = await Promise.all([listJobs(), getBalance()])
    jobs.value = jobData.jobs || jobData
    creditsStore.setBalance(balanceData.balance ?? balanceData)
  } catch (err) {
    console.error('Failed to load dashboard data:', err)
  } finally {
    loading.value = false
  }
})

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  })
}

function statusClass(status) {
  const map = {
    completed: 'bg-green-100 text-green-800',
    running: 'bg-blue-100 text-blue-800',
    pending: 'bg-yellow-100 text-yellow-800',
    failed: 'bg-red-100 text-red-800',
  }
  return map[status] ?? 'bg-gray-100 text-gray-800'
}
</script>
