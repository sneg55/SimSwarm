<template>
  <div class="min-h-screen bg-ocean-midnight text-mist-foam">
    <!-- Toolbar -->
    <ResultsToolbar
      :title="job?.goal || 'Results'"
      :viewMode="viewMode"
      :showToggle="true"
      @update:viewMode="viewMode = $event"
    />

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center" style="height: calc(100vh - 140px)">
      <div class="text-mist-slate text-sm">Loading results…</div>
    </div>

    <!-- Not found -->
    <div v-else-if="!job" class="flex items-center justify-center" style="height: calc(100vh - 140px)">
      <div class="text-mist-slate text-sm">Results not found.</div>
    </div>

    <template v-else>
      <!-- ── Story View ── -->
      <div v-if="viewMode === 'story'" class="relative pt-[120px] pb-24">
        <!-- Left TOC -->
        <ReportToc :items="storySections" />

        <!-- Content -->
        <div class="max-w-[800px] mx-auto pl-12 pr-4 xl:pl-16 space-y-12">
          <!-- Simulation header -->
          <div id="story-header" data-reveal class="bg-ocean-deep border border-mist-depth rounded-2xl p-8">
            <h1 class="text-2xl font-bold text-mist-foam mb-2">{{ job.goal }}</h1>
            <p class="text-sm text-mist-slate capitalize">
              {{ job.tier }} tier
              <span v-if="job.created_at"> &bull; Started {{ formatDate(job.created_at) }}</span>
              <span v-if="job.completed_at"> &bull; Completed {{ formatDate(job.completed_at) }}</span>
            </p>
          </div>

          <!-- Report -->
          <div id="story-report" data-reveal class="bg-ocean-deep border border-mist-depth rounded-2xl p-10">
            <template v-if="structured">
              <div v-if="structured.brief" class="mb-8">
                <h2 class="text-lg font-bold text-mist-foam mb-3">Executive Brief</h2>
                <p class="text-sm text-mist-drift leading-relaxed">{{ structured.brief }}</p>
              </div>
              <ConfidenceGrid v-if="structured.confidence?.length" :items="structured.confidence" class="mb-8" />
              <div v-if="structured.findings?.length" class="mb-8" data-reveal data-reveal-stagger>
                <h2 class="text-lg font-bold text-mist-foam mb-4">Key Findings</h2>
                <div class="grid gap-4">
                  <FindingCard v-for="(f, i) in structured.findings" :key="i"
                    data-reveal-child
                    :label="f.label" :title="f.title" :description="f.description"
                    :metric="f.metric" :accent-color="f.accentColor" />
                </div>
              </div>
              <SentimentBars v-if="sentimentBars.length" :bars="sentimentBars" class="mb-8" />
              <div v-if="structured.coalitions?.length" class="mb-8">
                <h2 class="text-lg font-bold text-mist-foam mb-4">Agent Coalitions</h2>
                <div class="grid gap-4 md:grid-cols-2">
                  <CoalitionCard v-for="(c, i) in structured.coalitions" :key="i"
                    :name="c.name" :description="c.description" :agents="c.agents"
                    :strength="c.strength" :color="c.color" />
                </div>
              </div>
              <ReportViewer :content="job.result_report || ''" />
            </template>
            <template v-else>
              <ReportViewer :content="job.result_report || job.report || 'No report available.'" />
            </template>
          </div>

          <!-- Sources & Background -->
          <div v-if="job.enriched_seed" id="story-sources" data-reveal class="bg-ocean-deep border border-mist-depth rounded-2xl p-8">
            <h2 class="text-lg font-bold text-mist-foam mb-4">Sources & Background</h2>
            <ReportViewer :content="job.enriched_seed" />
          </div>

          <!-- Chat replay -->
          <!-- Chat replay only in Report view, not Story -->
        </div>
      </div>

      <!-- ── Graph View ── -->
      <div v-else-if="viewMode === 'graph'" class="pt-[52px] overflow-hidden" style="height: 100vh">
        <GraphVisualization
          ref="graphVizRef"
          :nodes="graphData?.nodes || []"
          :edges="graphData?.edges || []"
          :metadata="graphData?.metadata || {}"
          :chat-log="chatLog"
          :loading="graphLoading"
          :error="graphError"
          @node-selected="onNodeSelected"
        />
      </div>

      <!-- ── Report View ── -->
      <div v-else class="relative pt-[120px] pb-24">
        <!-- Left TOC -->
        <ReportToc :items="tocItems" />

        <!-- Content shifted right on xl screens -->
        <div class="max-w-[800px] mx-auto pl-12 pr-4 xl:pl-16 space-y-12">
          <!-- Simulation header -->
          <div id="report-header" data-reveal class="bg-ocean-deep border border-mist-depth rounded-2xl p-8">
            <h1 class="text-2xl font-bold text-mist-foam mb-2">{{ job.goal }}</h1>
            <p class="text-sm text-mist-slate capitalize">
              {{ job.tier }} tier
              <span v-if="job.created_at"> &bull; Started {{ formatDate(job.created_at) }}</span>
              <span v-if="job.completed_at"> &bull; Completed {{ formatDate(job.completed_at) }}</span>
            </p>
          </div>

          <!-- Report -->
          <div id="report-content" data-reveal class="bg-ocean-deep border border-mist-depth rounded-2xl p-10">
            <ReportViewer :content="job.result_report || job.report || 'No report available.'" />
          </div>

          <!-- Chat replay -->
          <div v-if="chatMessages.length > 0" id="report-chat">
            <ChatReplay :messages="chatMessages" />
          </div>
        </div>
      </div>
    </template>

    <!-- Bottom bar -->
    <ResultsBottomBar
      v-if="job"
      :showPng="viewMode === 'graph'"
      :showJson="viewMode !== 'graph'"
      :showCsv="viewMode !== 'graph'"
      :pdfLoading="pdfLoading"
      :shareStatus="shareStatus"
      @export="handleExport"
      @share="handleShare"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import ReportViewer from '../components/ReportViewer.vue'
import ChatReplay from '../components/ChatReplay.vue'
import GraphVisualization from '../components/graph/GraphVisualization.vue'
import ResultsToolbar from '../components/results/ResultsToolbar.vue'
import ResultsBottomBar from '../components/results/ResultsBottomBar.vue'
import StoryTimeline from '../components/results/StoryTimeline.vue'
import ReportToc from '../components/results/ReportToc.vue'
import FindingCard from '../components/results/FindingCard.vue'
import SentimentBars from '../components/results/SentimentBars.vue'
import CoalitionCard from '../components/results/CoalitionCard.vue'
import ConfidenceGrid from '../components/results/ConfidenceGrid.vue'
import { useScrollReveal } from '../composables/useScrollReveal.js'
import { useSimulationData } from '../composables/useSimulationData.js'
import { getJob, getJobGraph, createShareLink } from '../api/jobs.js'

const route = useRoute()
const jobId = route.params.id

useScrollReveal()

const job = ref(null)
const loading = ref(true)
const viewMode = ref('story')

const graphVizRef = ref(null)
const graphData = ref(null)
const graphLoading = ref(false)
const graphError = ref(null)
const hasGraph = ref(false)

const pdfLoading = ref(false)

const isSmallScreen = ref(window.innerWidth < 768)

// ── Computed ──────────────────────────────────────────────────────────────────

const { chatLog, chatMessages, structured, sentimentBars, buildNodeRelationships } = useSimulationData(job)

const enrichmentCitations = computed(() => {
  if (!job.value?.enrichment_citations) return []
  try { return JSON.parse(job.value.enrichment_citations) } catch { return [] }
})

const storySections = computed(() => {
  const sections = [
    { id: 'story-header', label: 'Overview' },
    { id: 'story-report', label: 'Report' },
  ]
  if (job.value?.enriched_seed) sections.push({ id: 'story-sources', label: 'Sources' })
  return sections
})

const tocItems = computed(() => {
  const items = [
    { id: 'report-header', label: 'Overview' },
    { id: 'report-content', label: 'Report' },
  ]
  if (chatMessages.value.length > 0) items.push({ id: 'report-chat', label: 'Conversation' })
  return items
})

// ── Data fetching ─────────────────────────────────────────────────────────────

async function fetchGraphData() {
  graphLoading.value = true
  graphError.value = null
  try {
    const raw = await getJobGraph(jobId)
    if (raw?.nodes?.length && raw?.edges?.length) {
      raw.nodes = buildNodeRelationships(raw.nodes, raw.edges)
    }
    graphData.value = raw
    hasGraph.value = graphData.value?.nodes?.length > 0
  } catch (err) {
    graphError.value = err.response?.status === 404
      ? 'Graph data not available for this simulation.'
      : 'Failed to load graph data.'
    hasGraph.value = false
  } finally {
    graphLoading.value = false
  }
}

function onNodeSelected(_entityName) {
  // In three-view mode there's no split pane; graph view is fullscreen.
}

// ── Export handlers ───────────────────────────────────────────────────────────

async function handleExport(format) {
  if (format === 'pdf') {
    await exportPDF()
  } else if (format === 'json') {
    exportJSON()
  } else if (format === 'csv') {
    exportCSV()
  } else if (format === 'png') {
    exportPNG()
  }
}

async function exportPDF() {
  pdfLoading.value = true
  try {
    const token = localStorage.getItem('auth_token')
    const resp = await fetch(`/api/jobs/${jobId}/export/pdf`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      alert(`PDF export failed: ${err.detail || resp.statusText}`)
      return
    }
    const blob = await resp.blob()
    triggerDownload(blob, `simulation-${jobId}.pdf`)
  } catch (err) {
    console.error('PDF export error:', err)
    alert('PDF export failed. Please try again.')
  } finally {
    pdfLoading.value = false
  }
}

function exportJSON() {
  const data = {
    jobId,
    report: job.value?.result_report || job.value?.report,
    messages: chatMessages.value,
    exportedAt: new Date().toISOString(),
  }
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  triggerDownload(blob, `simswarm-${jobId}.json`)
}

function exportCSV() {
  const messages = chatMessages.value
  const rows = [['role', 'agent', 'content', 'timestamp']]
  messages.forEach((msg) => {
    rows.push([msg.role || '', msg.agent || '', (msg.content || '').replace(/,/g, ';'), msg.timestamp || ''])
  })
  const csv = rows.map((r) => r.map((c) => `"${c}"`).join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  triggerDownload(blob, `simswarm-${jobId}.csv`)
}

function exportPNG() {
  if (graphVizRef.value) {
    graphVizRef.value.exportImage()
  }
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

const shareStatus = ref('')

async function handleShare() {
  try {
    shareStatus.value = 'generating'
    const data = await createShareLink(jobId)
    const publicUrl = `${window.location.origin}/s/${data.share_token}`
    await navigator.clipboard.writeText(publicUrl)
    shareStatus.value = 'copied'
    setTimeout(() => { shareStatus.value = '' }, 3000)
  } catch (err) {
    console.error('Failed to create share link:', err)
    shareStatus.value = 'error'
    setTimeout(() => { shareStatus.value = '' }, 3000)
  }
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────

function onResize() {
  isSmallScreen.value = window.innerWidth < 768
}

onMounted(async () => {
  window.addEventListener('resize', onResize)
  try {
    job.value = await getJob(jobId)
    await fetchGraphData()
  } catch (err) {
    console.error('Failed to load results:', err)
  } finally {
    loading.value = false
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
})

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'long', day: 'numeric', year: 'numeric',
  })
}
</script>
