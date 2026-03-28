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
        <!-- Left timeline -->
        <StoryTimeline :sections="storySections" />

        <!-- Content -->
        <div class="max-w-[800px] mx-auto pl-12 pr-4 xl:pl-16 space-y-8">
          <!-- Simulation header -->
          <div id="story-header" class="bg-ocean-deep border border-mist-depth rounded-2xl p-8">
            <h1 class="text-2xl font-bold text-mist-foam mb-2">{{ job.goal }}</h1>
            <p class="text-sm text-mist-slate capitalize">
              {{ job.tier }} tier
              <span v-if="job.created_at"> &bull; Started {{ formatDate(job.created_at) }}</span>
              <span v-if="job.completed_at"> &bull; Completed {{ formatDate(job.completed_at) }}</span>
            </p>
          </div>

          <!-- Report -->
          <div id="story-report" class="bg-ocean-deep border border-mist-depth rounded-2xl p-10">
            <ReportViewer :content="job.result_report || job.report || 'No report available.'" />
          </div>

          <!-- Chat replay -->
          <!-- Chat replay only in Report view, not Story -->
        </div>
      </div>

      <!-- ── Graph View ── -->
      <div v-else-if="viewMode === 'graph'" class="pt-[52px]" style="height: calc(100vh - 140px)">
        <GraphVisualization
          :nodes="graphData?.nodes || []"
          :edges="graphData?.edges || []"
          :metadata="graphData?.metadata || {}"
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
        <div class="max-w-[800px] mx-auto pl-12 pr-4 xl:pl-16 space-y-8">
          <!-- Simulation header -->
          <div id="report-header" class="bg-ocean-deep border border-mist-depth rounded-2xl p-8">
            <h1 class="text-2xl font-bold text-mist-foam mb-2">{{ job.goal }}</h1>
            <p class="text-sm text-mist-slate capitalize">
              {{ job.tier }} tier
              <span v-if="job.created_at"> &bull; Started {{ formatDate(job.created_at) }}</span>
              <span v-if="job.completed_at"> &bull; Completed {{ formatDate(job.completed_at) }}</span>
            </p>
          </div>

          <!-- Report -->
          <div id="report-content" class="bg-ocean-deep border border-mist-depth rounded-2xl p-10">
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
import { getJob, getJobGraph } from '../api/jobs.js'

const route = useRoute()
const jobId = route.params.id

const job = ref(null)
const loading = ref(true)
const viewMode = ref('story')

const graphData = ref(null)
const graphLoading = ref(false)
const graphError = ref(null)
const hasGraph = ref(false)

const pdfLoading = ref(false)

const isSmallScreen = ref(window.innerWidth < 768)

// ── Computed ──────────────────────────────────────────────────────────────────

const chatMessages = computed(() => {
  if (!job.value) return []
  try {
    const raw = job.value.result_chat_log || job.value.chat_log || '[]'
    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
    if (!Array.isArray(parsed)) return []
    // Transform MiroFish chat log format to ChatReplay format
    return parsed.map(entry => {
      // If already in ChatReplay format (has content + role), pass through
      if (entry.content && entry.role) return entry
      // MiroFish format: { agent_name, action_type, action_args: { content }, timestamp }
      return {
        role: 'assistant',
        agent: entry.agent_name || entry.agent || 'Agent',
        content: entry.action_args?.content || entry.content || JSON.stringify(entry.action_args || {}),
        timestamp: entry.timestamp || null,
      }
    }).filter(m => m.content)
  } catch { return [] }
})

const storySections = computed(() => {
  const sections = [
    { id: 'story-header', label: 'Overview' },
    { id: 'story-report', label: 'Report' },
  ]
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
    graphData.value = await getJobGraph(jobId)
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
  // Graph PNG export is delegated to the GraphVisualization component via the
  // canvas it manages. We emit a custom event that GraphVisualization can listen
  // to if wired; for now, print a message to the console.
  console.warn('PNG export: trigger from GraphVisualization component ref if needed.')
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function handleShare() {
  if (navigator.share) {
    navigator.share({ title: job.value?.goal, url: window.location.href }).catch(() => {})
  } else {
    navigator.clipboard.writeText(window.location.href).then(() => alert('Link copied!')).catch(() => {})
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
