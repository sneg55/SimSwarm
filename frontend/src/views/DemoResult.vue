<template>
  <div :class="viewMode === 'graph' ? '' : 'max-w-4xl mx-auto px-4 py-10'">
    <!-- Loading state -->
    <div v-if="loading" class="text-center py-20 text-mist-slate">
      Loading demo...
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="text-center py-20">
      <p class="text-coral text-lg mb-4">{{ error }}</p>
      <router-link to="/" class="text-ocean-glow hover:underline">Back to home</router-link>
    </div>

    <!-- Demo content -->
    <div v-else-if="demo">
      <!-- Header -->
      <div class="mb-8" :class="viewMode !== 'report' ? 'px-4 pt-10' : ''">
        <div class="flex items-center gap-2 text-sm text-mist-slate mb-2">
          <router-link to="/" class="hover:text-ocean-glow">Home</router-link>
          <span>/</span>
          <span>Demo</span>
          <span>/</span>
          <span class="text-mist-drift">{{ demo.title }}</span>
        </div>
        <div class="flex items-center justify-between">
          <div>
            <h1 class="text-3xl font-bold text-mist-foam mb-3">{{ demo.title }}</h1>
            <p class="text-mist-slate text-lg">{{ demo.description }}</p>
          </div>
          <ViewModeToggle
            v-if="hasGraph"
            v-model="viewMode"
            :compact="isSmallScreen"
          />
        </div>
        <div class="flex gap-4 mt-4 text-sm text-mist-slate">
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

      <!-- Report Mode (original layout) -->
      <template v-else>
        <!-- Seed Summary -->
        <div class="bg-coral-amber/10 border border-coral-amber/20 rounded-2xl p-5 mb-8">
          <h2 class="text-sm font-semibold text-coral-sand uppercase tracking-wide mb-2">Seed Event</h2>
          <p class="text-mist-foam">{{ demo.seed_summary }}</p>
        </div>

        <!-- Goal -->
        <div class="bg-ocean-cyan/10 border border-ocean-cyan/20 rounded-2xl p-5 mb-8">
          <h2 class="text-sm font-semibold text-ocean-glow uppercase tracking-wide mb-2">Simulation Goal</h2>
          <p class="text-mist-foam">{{ demo.goal }}</p>
        </div>

        <!-- Report -->
        <div class="mb-10">
          <h2 class="text-xl font-bold text-mist-foam mb-4">Simulation Report</h2>
          <div class="border border-mist-depth rounded-2xl p-6 bg-ocean-deep">
            <ReportViewer :content="demo.report_markdown" />
          </div>
        </div>

        <!-- Chat Replay -->
        <div class="mb-10">
          <h2 class="text-xl font-bold text-mist-foam mb-4">Agent Chat Log</h2>
          <ChatReplay :messages="chatMessages" />
        </div>

        <!-- CTA Banner -->
        <div class="bg-gradient-to-r from-ocean-cyan to-cyan-500 rounded-2xl p-8 text-center text-white">
          <h2 class="text-2xl font-bold mb-2">Run Your Own Simulation</h2>
          <p class="text-cyan-100 mb-6">
            Upload any seed document and let FishCloud simulate public opinion, market reactions, or narrative evolution at scale.
          </p>
          <router-link
            to="/register"
            class="inline-block px-8 py-3 bg-gradient-to-br from-ocean-cyan to-cyan-500 text-white font-semibold rounded-2xl glow-cyan hover:glow-cyan-lg hover:-translate-y-0.5 transition-all ease-spring"
          >
            Get started
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

function onResize() {
  isSmallScreen.value = window.innerWidth < 768
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
