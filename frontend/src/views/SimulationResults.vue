<template>
  <div :class="viewMode === 'report' ? 'max-w-4xl mx-auto px-4 py-8' : ''">
    <!-- Header -->
    <div class="mb-6 flex items-center justify-between" :class="viewMode !== 'report' ? 'px-4 pt-8' : ''">
      <div>
        <router-link to="/dashboard" class="text-sm text-blue-600 hover:underline">&larr; Back to Dashboard</router-link>
        <h1 class="text-2xl font-bold text-gray-900 mt-2">Simulation Results</h1>
      </div>
      <div class="flex items-center gap-4">
        <ViewModeToggle
          v-if="job && hasGraph"
          v-model="viewMode"
          :compact="isSmallScreen"
        />
        <ExportButtons
          v-if="job"
          :job-id="jobId"
          :report-content="job.report"
          :messages="job.messages"
        />
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-center py-12 text-gray-500">
      Loading results...
    </div>

    <div v-else-if="job">
      <!-- Job meta (shown in report and dual modes) -->
      <div v-if="viewMode === 'report' || viewMode === 'dual'" class="mb-6" :class="viewMode === 'dual' ? 'px-4' : ''">
        <div class="bg-white border border-gray-200 rounded-lg p-6">
          <h2 class="text-lg font-semibold text-gray-800 mb-1">{{ job.goal }}</h2>
          <p class="text-sm text-gray-500 capitalize">
            {{ job.tier }} tier &bull; Completed {{ formatDate(job.completed_at) }}
          </p>
        </div>
      </div>

      <!-- Graph Mode -->
      <div v-if="viewMode === 'graph'" class="px-4" style="height: calc(100vh - 180px)">
        <GraphVisualization
          :nodes="graphData?.nodes || []"
          :edges="graphData?.edges || []"
          :metadata="graphData?.metadata || {}"
          :loading="graphLoading"
          :error="graphError"
          @node-selected="onNodeSelected"
        />
      </div>

      <!-- Dual Column Mode -->
      <div v-else-if="viewMode === 'dual'" class="flex px-4 gap-0" style="height: calc(100vh - 240px)">
        <div class="flex-1 min-w-[300px]" style="flex-basis: 50%">
          <GraphVisualization
            :nodes="graphData?.nodes || []"
            :edges="graphData?.edges || []"
            :metadata="graphData?.metadata || {}"
            :loading="graphLoading"
            :error="graphError"
            @node-selected="onNodeSelected"
          />
        </div>
        <div
          class="w-1 bg-gray-200 hover:bg-indigo-300 cursor-col-resize flex-shrink-0 transition-colors"
          @mousedown="startResize"
        />
        <div
          ref="reportPaneRef"
          class="flex-1 min-w-[300px] overflow-y-auto bg-white border border-gray-200 rounded-lg p-6"
          style="flex-basis: 50%"
        >
          <h3 class="text-lg font-semibold text-gray-800 mb-4">Report</h3>
          <ReportViewer :content="job.result_report || job.report || 'No report available.'" />
        </div>
      </div>

      <!-- Report Mode (original layout) -->
      <div v-else class="space-y-6">
        <div class="bg-white border border-gray-200 rounded-lg p-6">
          <h3 class="text-lg font-semibold text-gray-800 mb-4">Report</h3>
          <ReportViewer :content="job.result_report || job.report || 'No report available.'" />
        </div>

        <div v-if="chatMessages.length > 0" class="bg-white border border-gray-200 rounded-lg p-6">
          <h3 class="text-lg font-semibold text-gray-800 mb-4">Agent Conversation</h3>
          <ChatReplay :messages="chatMessages" />
        </div>
      </div>
    </div>

    <div v-else class="text-center py-12 text-gray-500">
      Results not found.
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import ReportViewer from '../components/ReportViewer.vue'
import ChatReplay from '../components/ChatReplay.vue'
import ExportButtons from '../components/ExportButtons.vue'
import ViewModeToggle from '../components/ViewModeToggle.vue'
import GraphVisualization from '../components/graph/GraphVisualization.vue'
import { getJob, getJobGraph } from '../api/jobs.js'

const route = useRoute()
const jobId = route.params.id

const job = ref(null)
const loading = ref(true)
const viewMode = ref('report')

const graphData = ref(null)
const graphLoading = ref(false)
const graphError = ref(null)
const hasGraph = ref(false)

const isSmallScreen = ref(window.innerWidth < 768)
const reportPaneRef = ref(null)

const chatMessages = computed(() => {
  if (!job.value) return []
  try {
    const raw = job.value.result_chat_log || job.value.chat_log || '[]'
    return typeof raw === 'string' ? JSON.parse(raw) : raw
  } catch { return [] }
})

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

function onNodeSelected(entityName) {
  if (viewMode.value !== 'dual' || !reportPaneRef.value) return
  const walker = document.createTreeWalker(reportPaneRef.value, NodeFilter.SHOW_TEXT)
  const lowerName = entityName.toLowerCase()
  while (walker.nextNode()) {
    if (walker.currentNode.textContent.toLowerCase().includes(lowerName)) {
      const el = walker.currentNode.parentElement
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      el.style.backgroundColor = 'rgba(99, 102, 241, 0.15)'
      setTimeout(() => { el.style.backgroundColor = '' }, 2000)
      break
    }
  }
}

function startResize(e) {
  const startX = e.clientX
  const container = e.target.parentElement
  const leftPane = container.children[0]
  const rightPane = container.children[2]
  const startLeftWidth = leftPane.getBoundingClientRect().width
  const totalWidth = container.getBoundingClientRect().width

  function onMove(ev) {
    const dx = ev.clientX - startX
    const newLeft = Math.max(300, Math.min(totalWidth - 304, startLeftWidth + dx))
    leftPane.style.flexBasis = newLeft + 'px'
    rightPane.style.flexBasis = (totalWidth - newLeft - 4) + 'px'
  }

  function onUp() {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
  }

  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}

function onResize() {
  isSmallScreen.value = window.innerWidth < 768
  if (isSmallScreen.value && viewMode.value === 'dual') {
    viewMode.value = 'graph'
  }
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

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'long', day: 'numeric', year: 'numeric',
  })
}
</script>
