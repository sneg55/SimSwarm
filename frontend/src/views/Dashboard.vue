<template>
  <div>
    <!-- Waterline Strip -->
    <div class="relative overflow-hidden border-b border-mist-depth bg-gradient-to-b from-ocean-deep to-ocean-abyss pt-14">
      <div class="absolute inset-0 pointer-events-none"
        style="background: radial-gradient(ellipse 60% 80% at 80% 50%, rgba(14,116,144,0.06), transparent)"
      />
      <div class="relative max-w-[1000px] mx-auto px-4 md:px-8 py-8 flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold text-mist-foam tracking-tight">Welcome back</h1>
          <p class="text-sm text-mist-drift mt-1">
            <strong class="text-organic-seafoam font-semibold">{{ creditsStore.balance }} credits</strong>
            remaining
          </p>
        </div>
        <router-link
          to="/sim/new"
          class="inline-flex items-center gap-2.5 px-7 py-3.5 rounded-xl text-base font-bold text-white
                 bg-gradient-to-br from-coral to-coral-amber
                 glow-coral transition-all duration-250 ease-spring
                 hover:glow-coral-lg hover:-translate-y-0.5"
        >
          <span class="w-5 h-5 rounded-full border-2 border-white/50 flex items-center justify-center text-sm leading-none">+</span>
          New Simulation
        </router-link>
      </div>
    </div>

    <!-- Main Content -->
    <div class="max-w-[1000px] mx-auto px-4 md:px-8 py-8">

      <CreditWarning class="mb-6" />

      <!-- Loading -->
      <div v-if="loading" class="text-center py-20 text-mist-slate">Loading...</div>

      <!-- Empty State -->
      <DashboardEmpty v-else-if="jobs.length === 0" />

      <!-- Simulation List -->
      <template v-else>
        <!-- Active -->
        <template v-if="activeJobs.length > 0">
          <div class="flex items-center gap-3 text-[11px] font-semibold uppercase tracking-[0.1em] text-mist-slate mb-4">
            Active
            <div class="flex-1 h-px bg-gradient-to-r from-mist-depth to-transparent" />
          </div>
          <div class="space-y-3 mb-10">
            <SimCard v-for="job in activeJobs" :key="job.id" :job="job" />
          </div>
        </template>

        <!-- Recent -->
        <div class="flex items-center gap-3 text-[11px] font-semibold uppercase tracking-[0.1em] text-mist-slate mb-4">
          Recent
          <div class="flex-1 h-px bg-gradient-to-r from-mist-depth to-transparent" />
        </div>
        <div class="space-y-3">
          <SimCard v-for="job in recentJobs" :key="job.id" :job="job" />
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import CreditWarning from '../components/CreditWarning.vue'
import DashboardEmpty from '../components/DashboardEmpty.vue'
import SimCard from '../components/SimCard.vue'
import { listJobs } from '../api/jobs.js'
import { getBalance } from '../api/billing.js'
import { useCreditsStore } from '../stores/credits.js'

const creditsStore = useCreditsStore()
const jobs = ref([])
const loading = ref(true)

const activeJobs = computed(() =>
  jobs.value.filter(j => ['RUNNING', 'PROVISIONING', 'PENDING'].includes(j.status))
)

const recentJobs = computed(() =>
  jobs.value.filter(j => !['RUNNING', 'PROVISIONING', 'PENDING'].includes(j.status))
)

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
</script>
