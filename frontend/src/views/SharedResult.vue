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
      <!-- ── Story View ── (identical to dashboard) -->
      <div v-if="viewMode === 'story'" class="relative pt-[120px] pb-24">
        <StoryTimeline :sections="storySections" />

        <div class="max-w-[800px] mx-auto pl-12 pr-4 xl:pl-16 space-y-12">
          <!-- Simulation header card -->
          <div id="story-header" data-reveal class="bg-ocean-deep border border-mist-depth rounded-2xl p-8">
            <h1 class="text-2xl font-bold text-mist-foam mb-2">{{ result.title }}</h1>
            <p class="text-sm text-mist-slate capitalize">
              {{ result.tier }} tier
              <span v-if="result.created_at"> &bull; {{ formatDate(result.created_at) }}</span>
              <span v-if="result.completed_at"> &bull; Completed {{ formatDate(result.completed_at) }}</span>
            </p>
          </div>

          <!-- Report content card -->
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
              <ReportViewer :content="result.report || ''" />
            </template>
            <template v-else>
              <ReportViewer :content="result.report || 'No report available.'" />
            </template>
          </div>
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
import StoryTimeline from '../components/results/StoryTimeline.vue'
import ReportToc from '../components/results/ReportToc.vue'
import ReportViewer from '../components/ReportViewer.vue'
import ChatReplay from '../components/ChatReplay.vue'
import GraphVisualization from '../components/graph/GraphVisualization.vue'
import FindingCard from '../components/results/FindingCard.vue'
import SentimentBars from '../components/results/SentimentBars.vue'
import CoalitionCard from '../components/results/CoalitionCard.vue'
import ConfidenceGrid from '../components/results/ConfidenceGrid.vue'
import { useScrollReveal } from '../composables/useScrollReveal.js'

const route = useRoute()
const token = route.params.token

useScrollReveal()

const result = ref(null)
const loading = ref(true)
const error = ref(null)
const viewMode = ref('story')

// ── Story sections for timeline ──────────────────────────────────────────────

const storySections = computed(() => [
  { id: 'story-header', label: 'Overview' },
  { id: 'story-report', label: 'Report' },
])

// ── TOC items for report view ────────────────────────────────────────────────

const tocItems = computed(() => {
  const report = result.value?.report || ''
  const items = []
  const headingRegex = /^##\s+(.+)$/gm
  let match
  while ((match = headingRegex.exec(report)) !== null) {
    const text = match[1].replace(/\*\*/g, '')
    const id = text.toLowerCase().replace(/[^a-z0-9]+/g, '-')
    items.push({ id: `report-content`, label: text })
  }
  return items.length > 0 ? items : [{ id: 'report-content', label: 'Full Report' }]
})

// ── Chat messages ────────────────────────────────────────────────────────────

const chatMessages = computed(() => {
  if (!result.value?.chat_log) return []
  try {
    const raw = result.value.chat_log
    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
    if (!Array.isArray(parsed)) return []
    return parsed.map(entry => {
      if (entry.content && entry.role) return entry
      return {
        role: 'assistant',
        agent: entry.agent_name || entry.agent || 'Agent',
        content: entry.action_args?.content || entry.content || JSON.stringify(entry.action_args || {}),
        timestamp: entry.timestamp || null,
      }
    }).filter(m => m.content)
  } catch { return [] }
})

// ── Structured data ──────────────────────────────────────────────────────────

const structured = computed(() => {
  if (!result.value?.structured) return null
  try {
    return typeof result.value.structured === 'string'
      ? JSON.parse(result.value.structured)
      : result.value.structured
  } catch { return null }
})

const sentimentBars = computed(() => {
  if (!structured.value?.sentiment) return []
  return structured.value.sentiment.map(s => ({
    label: s.label,
    width: s.value,
    value: `${s.value}%`,
    gradient: s.direction === 'positive'
      ? 'linear-gradient(90deg, #22D3EE, #6EE7B7)'
      : 'linear-gradient(90deg, #FF6B6B, #F97316)',
    valueColor: s.direction === 'positive' ? '#6EE7B7' : '#FF6B6B',
  }))
})

// ── Graph helpers ────────────────────────────────────────────────────────────

function buildNodeRelationships(nodes, edges) {
  const relMap = {}
  for (const edge of edges) {
    if (!relMap[edge.source_node_uuid]) relMap[edge.source_node_uuid] = []
    relMap[edge.source_node_uuid].push({
      direction: 'outgoing',
      type: edge.name || edge.fact || '',
      target_uuid: edge.target_node_uuid,
      targetName: edge.target_node_name || '',
    })
    if (!relMap[edge.target_node_uuid]) relMap[edge.target_node_uuid] = []
    relMap[edge.target_node_uuid].push({
      direction: 'incoming',
      type: edge.name || edge.fact || '',
      source_uuid: edge.source_node_uuid,
      sourceName: edge.source_node_name || '',
    })
  }
  return nodes.map(n => ({ ...n, relationships: relMap[n.uuid] || [] }))
}

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
