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
        <!-- Drafts -->
        <section v-if="draftJobs.length" class="mb-8">
          <h2 class="text-lg font-semibold text-white/90 mb-3">Drafts</h2>
          <div class="space-y-3">
            <div
              v-for="draft in draftJobs"
              :key="draft.id"
              class="group relative bg-white/5 border border-white/10 rounded-xl p-4 cursor-pointer hover:bg-white/10 transition-colors"
              @click="$router.push(`/new?draft=${draft.id}`)"
            >
              <div class="flex items-center justify-between">
                <div class="flex-1 min-w-0">
                  <p class="text-white/80 truncate">
                    {{ draft.goal || 'Untitled draft' }}
                  </p>
                  <div class="flex items-center gap-2 mt-1">
                    <span class="text-xs px-2 py-0.5 rounded-full bg-white/10 text-white/50">
                      Draft
                    </span>
                    <span v-if="draft.tier" class="text-xs text-white/40">
                      {{ draft.tier }} tier
                    </span>
                    <span class="text-xs text-white/30">
                      {{ new Date(draft.created_at).toLocaleDateString() }}
                    </span>
                  </div>
                </div>
                <button
                  class="opacity-0 group-hover:opacity-100 text-white/30 hover:text-red-400 transition-all p-1"
                  title="Delete draft"
                  @click.stop="handleDelete(draft.id)"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </section>

        <!-- Active -->
        <template v-if="activeJobs.length > 0">
          <div class="flex items-center gap-3 text-[11px] font-semibold uppercase tracking-[0.1em] text-mist-slate mb-4">
            Active
            <div class="flex-1 h-px bg-gradient-to-r from-mist-depth to-transparent" />
          </div>
          <div class="space-y-3 mb-10">
            <SimCard v-for="job in activeJobs" :key="job.id" :job="job" @delete="handleDelete" @restart="handleRestart" />
          </div>
        </template>

        <!-- Recent -->
        <div class="flex items-center gap-3 text-[11px] font-semibold uppercase tracking-[0.1em] text-mist-slate mb-4">
          Recent
          <div class="flex-1 h-px bg-gradient-to-r from-mist-depth to-transparent" />
        </div>
        <div class="space-y-3">
          <SimCard v-for="job in recentJobs" :key="job.id" :job="job" @delete="handleDelete" @restart="handleRestart" />
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
import { listJobs, deleteJob, getJob, createDraft } from '../api/jobs.js'
import { getBalance } from '../api/billing.js'
import { useCreditsStore } from '../stores/credits.js'
import { useRouter } from 'vue-router'

const creditsStore = useCreditsStore()
const router = useRouter()
const jobs = ref([])
const loading = ref(true)
const page = ref(1)
const totalJobs = ref(0)

const hasMore = computed(() => jobs.value.length < totalJobs.value)

const draftJobs = computed(() =>
  jobs.value.filter(j => j.status === 'DRAFT')
)

const activeJobs = computed(() =>
  jobs.value.filter(j => ['RUNNING', 'PROVISIONING', 'PENDING'].includes(j.status))
)

const recentJobs = computed(() =>
  jobs.value.filter(j =>
    !['RUNNING', 'PROVISIONING', 'PENDING', 'DRAFT'].includes(j.status)
  )
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

async function handleRestart(job) {
  try {
    const full = await getJob(job.id)
    const draft = await createDraft({
      seed_text: full.seed_text,
      goal: full.goal,
      tier: full.tier,
      enrich_web: full.enrich_web,
      forecast_days: full.forecast_days ?? 30,
    })
    router.push(`/sim/new?draft=${draft.id}`)
  } catch (err) {
    console.error('Failed to restart job:', err)
  }
}
</script>
