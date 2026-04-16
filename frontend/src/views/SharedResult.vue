<template>
  <div class="min-h-screen bg-ocean-midnight text-mist-foam">
    <!-- Toolbar (same as dashboard, different back link) -->
    <ResultsToolbar
      :title="result?.title || 'Shared Result'"
      :viewMode="viewMode"
      :showToggle="true"
      backLink="/"
      backLabel="Home"
      @update:viewMode="viewMode = $event"
    />

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center" style="height: calc(100vh - 140px)">
      <div class="text-mist-slate text-sm">Loading shared results...</div>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="flex items-center justify-center" style="height: calc(100vh - 140px)">
      <div class="text-center">
        <h2 class="text-xl text-mist-foam mb-2">Result not found</h2>
        <p class="text-mist-slate">{{ error }}</p>
        <router-link to="/" class="text-ocean-cyan mt-4 inline-block">Back to home</router-link>
      </div>
    </div>

    <template v-else>
      <!-- ── Story View ── (mirrors SimulationResults Story layout) -->
      <div v-if="viewMode === 'story'" class="relative pt-[120px] pb-24">
        <ReportToc :items="storySections" />

        <div class="max-w-[820px] mx-auto px-6 space-y-6">
          <!-- Meta row -->
          <div id="story-meta" class="flex items-center gap-3 font-mono text-[10px] text-mist-slate uppercase tracking-wider">
            <span>Simulation</span>
            <span class="w-1 h-1 rounded-full bg-mist-depth"></span>
            <span>{{ simScale.participants ?? '—' }} participants</span>
            <span class="w-1 h-1 rounded-full bg-mist-depth"></span>
            <span>{{ simScale.horizon_days ?? '—' }}d horizon</span>
            <span v-if="result.tier" class="w-1 h-1 rounded-full bg-mist-depth"></span>
            <span v-if="result.tier" class="capitalize">{{ result.tier }} depth</span>
          </div>

          <!-- Q+A Hero -->
          <div id="story-hero" data-reveal>
            <QuestionAnswerHero
              :question="result.title || ''"
              :verdict="verdict"
              :stakeholder-positions="stakeholderPositions"
            />
          </div>

          <!-- What the simulation surfaced -->
          <div v-if="structured?.findings?.length" id="story-findings">
            <div class="font-mono text-[10px] text-mist-slate uppercase tracking-wider mb-4 pl-1">What the simulation surfaced</div>
            <div :class="findingsGridClass">
              <FindingSlotCard
                v-for="(f, i) in structured.findings"
                :key="i"
                :slot-name="f.slot"
                :title="f.title"
                :body="f.body"
                :citation="f.citation"
              />
            </div>
          </div>

          <!-- Sim-scale footer -->
          <SimScaleFooter id="story-scale" :scale="simScale" />
        </div>
      </div>

      <!-- ── Graph View ── (identical to dashboard) -->
      <div v-else-if="viewMode === 'graph'" class="pt-[52px] overflow-hidden" style="height: 100vh">
        <GraphVisualization
          :nodes="graphNodes"
          :edges="graphEdges"
          :metadata="graphMetadata"
        />
      </div>

      <!-- ── Report View ── (identical to dashboard) -->
      <div v-else class="relative pt-[120px] pb-24">
        <ReportToc :items="tocItems" />

        <div class="max-w-[800px] mx-auto pl-12 pr-4 xl:pl-16 space-y-12">
          <div id="report-header" data-reveal class="bg-ocean-deep border border-mist-depth rounded-2xl p-8">
            <h1 class="text-2xl font-bold text-mist-foam mb-2">{{ result.title }}</h1>
            <p class="text-sm text-mist-slate capitalize">
              {{ result.tier }} tier
              <span v-if="result.created_at"> &bull; {{ formatDate(result.created_at) }}</span>
              <span v-if="result.completed_at"> &bull; Completed {{ formatDate(result.completed_at) }}</span>
            </p>
          </div>

          <div id="report-content" data-reveal class="bg-ocean-deep border border-mist-depth rounded-2xl p-10">
            <ReportViewer :content="result.report || 'No report available.'" />
          </div>

          <div v-if="chatMessages.length > 0" id="report-chat">
            <ChatReplay :messages="chatMessages" />
          </div>
        </div>
      </div>

      <!-- CTA Banner (shared-only) -->
      <div v-if="viewMode !== 'graph'" class="max-w-[800px] mx-auto pl-12 pr-4 xl:pl-16 pb-12">
        <div class="bg-ocean-deep border border-mist-depth rounded-xl p-8 text-center">
          <h3 class="text-lg font-bold text-mist-foam mb-2">Run your own simulation</h3>
          <p class="text-sm text-mist-slate mb-4">Create AI-powered predictions on any topic</p>
          <router-link to="/register" class="inline-block px-6 py-2 bg-ocean-cyan text-ocean-abyss font-semibold rounded-lg hover:bg-ocean-glow transition-colors">
            Get Started
          </router-link>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import ResultsToolbar from '../components/results/ResultsToolbar.vue'
import ReportToc from '../components/results/ReportToc.vue'
import ReportViewer from '../components/ReportViewer.vue'
import ChatReplay from '../components/ChatReplay.vue'
import GraphVisualization from '../components/graph/GraphVisualization.vue'
import QuestionAnswerHero from '../components/results/QuestionAnswerHero.vue'
import FindingSlotCard from '../components/results/FindingSlotCard.vue'
import SimScaleFooter from '../components/results/SimScaleFooter.vue'
import { useScrollReveal } from '../composables/useScrollReveal.js'
import { useSimulationData } from '../composables/useSimulationData.js'

const route = useRoute()
const token = route.params.token

useScrollReveal()

const result = ref(null)
const loading = ref(true)
const error = ref(null)
const viewMode = ref('story')

const {
  chatMessages,
  structured,
  verdict,
  stakeholderPositions,
  simScale,
  buildNodeRelationships,
} = useSimulationData(result)

// ── Story sections for timeline ──────────────────────────────────────────────

const storySections = computed(() => [
  { id: 'story-hero', label: 'Question & answer' },
  { id: 'story-findings', label: 'Findings' },
  { id: 'story-scale', label: 'Scale' },
])

const findingsGridClass = computed(() => {
  const n = structured.value?.findings?.length ?? 0
  if (n <= 1) return 'grid gap-4 grid-cols-1'
  if (n === 2) return 'grid gap-4 grid-cols-1 md:grid-cols-2'
  if (n === 3) return 'grid gap-4 grid-cols-1 md:grid-cols-2 [&>*:nth-child(3)]:md:col-span-2'
  return 'grid gap-4 grid-cols-1 md:grid-cols-2'  // 4+ → 2x2
})

// ── TOC items for report view ────────────────────────────────────────────────

const tocItems = computed(() => {
  const report = result.value?.report || ''
  const items = []
  const headingRegex = /^##\s+(.+)$/gm
  let match
  while ((match = headingRegex.exec(report)) !== null) {
    const text = match[1].replace(/\*\*/g, '')
    items.push({ id: `report-content`, label: text })
  }
  return items.length > 0 ? items : [{ id: 'report-content', label: 'Full Report' }]
})

// ── Graph helpers ────────────────────────────────────────────────────────────

const graphNodes = computed(() => {
  const graph = result.value?.graph
  if (!graph?.nodes?.length) return []
  if (graph.edges?.length) return buildNodeRelationships(graph.nodes, graph.edges)
  return graph.nodes
})

const graphEdges = computed(() => result.value?.graph?.edges || [])
const graphMetadata = computed(() => result.value?.graph?.metadata || {})

// ── Data fetching ────────────────────────────────────────────────────────────

onMounted(async () => {
  try {
    const resp = await fetch(`/api/share/${token}`)
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}))
      throw new Error(body.detail || `Not found (${resp.status})`)
    }
    result.value = await resp.json()
  } catch (err) {
    error.value = err.message || 'Failed to load shared result.'
  } finally {
    loading.value = false
  }
})

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'long', day: 'numeric', year: 'numeric',
  })
}
</script>
