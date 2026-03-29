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
      <div v-if="loading" class="space-y-4">
        <SkeletonCard v-for="i in 3" :key="i" :lines="2" />
      </div>

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
            <SimCard v-for="job in activeJobs" :key="job.id" :job="job" @delete="handleDelete" />
          </div>
        </template>

        <!-- Recent -->
        <div class="flex items-center gap-3 text-[11px] font-semibold uppercase tracking-[0.1em] text-mist-slate mb-4">
          Recent
          <div class="flex-1 h-px bg-gradient-to-r from-mist-depth to-transparent" />
        </div>
        <div class="space-y-3">
          <SimCard v-for="job in recentJobs" :key="job.id" :job="job" @delete="handleDelete" />
        </div>

        <!-- Load more -->
        <div v-if="hasMore" class="flex justify-center mt-8">
          <button
            @click="loadMore"
            class="bg-ocean-deep border border-mist-depth text-mist-drift hover:border-ocean-teal/40 hover:text-mist-foam rounded-xl px-6 py-2.5 text-sm font-semibold transition-all"
          >
            Load more
          </button>
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
import SkeletonCard from '../components/SkeletonCard.vue'
import { listJobs, deleteJob } from '../api/jobs.js'
import { getBalance } from '../api/billing.js'
import { useCreditsStore } from '../stores/credits.js'

const creditsStore = useCreditsStore()
const jobs = ref([])
const loading = ref(true)
const page = ref(1)
const totalJobs = ref(0)

const hasMore = computed(() => jobs.value.length < totalJobs.value)

const activeJobs = computed(() =>
  jobs.value.filter(j => ['RUNNING', 'PROVISIONING', 'PENDING'].includes(j.status))
)

const recentJobs = computed(() =>
  jobs.value.filter(j => !['RUNNING', 'PROVISIONING', 'PENDING'].includes(j.status))
)

onMounted(async () => {
  try {
    const [jobData, balanceData] = await Promise.all([listJobs(page.value), getBalance()])
    jobs.value = jobData.jobs
    totalJobs.value = jobData.total
    creditsStore.setBalance(balanceData.balance ?? balanceData)
  } catch (err) {
    console.error('Failed to load dashboard data:', err)
  } finally {
    loading.value = false
  }
})

async function loadMore() {
  try {
    page.value += 1
    const data = await listJobs(page.value)
    jobs.value = [...jobs.value, ...data.jobs]
    totalJobs.value = data.total
  } catch (err) {
    console.error('Failed to load more jobs:', err)
    page.value -= 1
  }
}

async function handleDelete(jobId) {
  if (!confirm('Delete this simulation? This cannot be undone.')) return
  try {
    await deleteJob(jobId)
    jobs.value = jobs.value.filter(j => j.id !== jobId)
    totalJobs.value = Math.max(0, totalJobs.value - 1)
  } catch (err) {
    console.error('Failed to delete job:', err)
  }
}
</script>
