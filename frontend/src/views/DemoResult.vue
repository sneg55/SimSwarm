<template>
  <div :class="viewMode === 'graph' ? '' : 'max-w-4xl mx-auto px-4 py-10'">
    <!-- Loading state -->
    <div v-if="loading" class="text-center py-20 text-gray-400">
      Loading demo...
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="text-center py-20">
      <p class="text-red-500 text-lg mb-4">{{ error }}</p>
      <router-link to="/" class="text-blue-600 hover:underline">Back to home</router-link>
    </div>

    <!-- Demo content -->
    <div v-else-if="demo">
      <!-- Header -->
      <div class="mb-8" :class="viewMode !== 'report' ? 'px-4 pt-10' : ''">
        <div class="flex items-center gap-2 text-sm text-gray-400 mb-2">
          <router-link to="/" class="hover:text-blue-600">Home</router-link>
          <span>/</span>
          <span>Demo</span>
          <span>/</span>
          <span class="text-gray-600">{{ demo.title }}</span>
        </div>
        <div class="flex items-center justify-between">
          <div>
            <h1 class="text-3xl font-bold text-gray-900 mb-3">{{ demo.title }}</h1>
            <p class="text-gray-500 text-lg">{{ demo.description }}</p>
          </div>
          <ViewModeToggle
            v-if="hasGraph"
            v-model="viewMode"
            :compact="isSmallScreen"
          />
        </div>
        <div class="flex gap-4 mt-4 text-sm text-gray-400">
          <span v-if="demo.agent_count">{{ demo.agent_count.toLocaleString() }} agents</span>
          <span v-if="demo.rounds">·</span>
          <span v-if="demo.rounds">{{ demo.rounds }} rounds</span>
          <span v-if="demo.tier">·</span>
          <span v-if="demo.tier" class="capitalize">{{ demo.tier }} tier</span>
        </div>
      </div>

      <!-- Graph Mode -->
      <div v-if="viewMode === 'graph'" class="px-4" style="height: calc(100vh - 220px)">
        <GraphVisualization
          :nodes="graphData?.nodes || []"
          :edges="graphData?.edges || []"
          :metadata="graphData?.metadata || {}"
        />
      </div>

      <!-- Dual Column Mode -->
      <div v-else-if="viewMode === 'dual'" class="flex px-4 gap-0" style="height: calc(100vh - 280px)">
        <div class="flex-1 min-w-[300px]" style="flex-basis: 50%">
          <GraphVisualization
            :nodes="graphData?.nodes || []"
            :edges="graphData?.edges || []"
            :metadata="graphData?.metadata || {}"
            @node-selected="onNodeSelected"
          />
        </div>
        <div class="w-1 bg-gray-200 hover:bg-indigo-300 cursor-col-resize flex-shrink-0" />
        <div ref="reportPaneRef" class="flex-1 min-w-[300px] overflow-y-auto bg-white border border-gray-200 rounded-lg p-6" style="flex-basis: 50%">
          <ReportViewer :content="demo.report_markdown" />
        </div>
      </div>

      <!-- Report Mode (original layout) -->
      <template v-else>
        <!-- Seed Summary -->
        <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-5 mb-8">
          <h2 class="text-sm font-semibold text-yellow-700 uppercase tracking-wide mb-2">Seed Event</h2>
          <p class="text-gray-800">{{ demo.seed_summary }}</p>
        </div>

        <!-- Goal -->
        <div class="bg-blue-50 border border-blue-200 rounded-lg p-5 mb-8">
          <h2 class="text-sm font-semibold text-blue-700 uppercase tracking-wide mb-2">Simulation Goal</h2>
          <p class="text-gray-800">{{ demo.goal }}</p>
        </div>

        <!-- Report -->
        <div class="mb-10">
          <h2 class="text-xl font-bold text-gray-900 mb-4">Simulation Report</h2>
          <div class="border border-gray-200 rounded-lg p-6 bg-white shadow-sm">
            <ReportViewer :content="demo.report_markdown" />
          </div>
        </div>

        <!-- Chat Replay -->
        <div class="mb-10">
          <h2 class="text-xl font-bold text-gray-900 mb-4">Agent Chat Log</h2>
          <ChatReplay :messages="chatMessages" />
        </div>

        <!-- CTA Banner -->
        <div class="bg-gradient-to-r from-blue-600 to-blue-700 rounded-xl p-8 text-center text-white">
          <h2 class="text-2xl font-bold mb-2">Run Your Own Simulation</h2>
          <p class="text-blue-100 mb-6">
            Upload any seed document and let FishCloud simulate public opinion, market reactions, or narrative evolution at scale.
          </p>
          <router-link
            to="/register"
            class="inline-block px-8 py-3 bg-white text-blue-600 font-semibold rounded-lg hover:bg-blue-50 transition-colors"
          >
            Get started free
          </router-link>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import ReportViewer from '../components/ReportViewer.vue'
import ChatReplay from '../components/ChatReplay.vue'
import ViewModeToggle from '../components/ViewModeToggle.vue'
import GraphVisualization from '../components/graph/GraphVisualization.vue'
import { getDemo } from '../api/demos.js'

const route = useRoute()
const demo = ref(null)
const loading = ref(true)
const error = ref(null)
const viewMode = ref('report')
const isSmallScreen = ref(window.innerWidth < 768)
const reportPaneRef = ref(null)

const chatMessages = computed(() => {
  if (!demo.value?.chat_log) return []
  return demo.value.chat_log.map((entry) => ({
    role: 'assistant',
    agent: entry.agent_name,
    content: entry.action_args?.content || JSON.stringify(entry.action_args),
    timestamp: null,
  }))
})

const graphData = computed(() => demo.value?.graph_data || null)
const hasGraph = computed(() => graphData.value && graphData.value.nodes && graphData.value.nodes.length > 0)

function onNodeSelected(entityName) {
  if (viewMode.value !== 'dual' || !reportPaneRef.value) return
  const walker = document.createTreeWalker(reportPaneRef.value, NodeFilter.SHOW_TEXT)
  const lowerName = entityName.toLowerCase()
  while (walker.nextNode()) {
    if (walker.currentNode.textContent.toLowerCase().includes(lowerName)) {
      walker.currentNode.parentElement.scrollIntoView({ behavior: 'smooth', block: 'center' })
      const el = walker.currentNode.parentElement
      el.style.backgroundColor = 'rgba(99, 102, 241, 0.15)'
      setTimeout(() => { el.style.backgroundColor = '' }, 2000)
      break
    }
  }
}

function onResize() {
  isSmallScreen.value = window.innerWidth < 768
  if (isSmallScreen.value && viewMode.value === 'dual') viewMode.value = 'graph'
}

onMounted(async () => {
  window.addEventListener('resize', onResize)
  try {
    demo.value = await getDemo(route.params.slug)
  } catch (e) {
    error.value = e.message || 'Failed to load demo.'
  } finally {
    loading.value = false
  }
})

onBeforeUnmount(() => window.removeEventListener('resize', onResize))
</script>
