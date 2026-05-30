<template>
  <div class="pb-24 px-4 md:px-8">
    <div class="max-w-[960px] mx-auto">
      <div v-if="loading" class="flex items-center justify-center py-20">
        <div class="text-mist-slate text-sm">Loading simulation data…</div>
      </div>
      <div v-else-if="error" class="flex items-center justify-center py-20">
        <div class="text-mist-slate text-sm">{{ error }}</div>
      </div>
      <template v-else>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="md:col-span-2">
            <MarketCurveChart :markets="marketCurves" />
          </div>
          <AgentTrajectoryChart :agents="agentTrajectories" />
          <EngagementChart :data="engagementSummary" />
          <TopPostsFeed :posts="topPosts" />
          <SocialGraphView :graph="socialGraph" />
          <div class="md:col-span-2">
            <MarketsList :markets="markets" />
          </div>
          <div class="md:col-span-2">
            <TradeFeed :trades="trades" />
          </div>
          <div class="md:col-span-2">
            <AgentProfileCards :profiles="profiles" />
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getSimData } from '../../api/jobs.js'
import MarketCurveChart from './MarketCurveChart.vue'
import AgentTrajectoryChart from './AgentTrajectoryChart.vue'
import EngagementChart from './EngagementChart.vue'
import TopPostsFeed from './TopPostsFeed.vue'
import SocialGraphView from './SocialGraphView.vue'
import TradeFeed from './TradeFeed.vue'
import AgentProfileCards from './AgentProfileCards.vue'
import MarketsList from './MarketsList.vue'

const props = defineProps({
  jobId: { type: [String, Number], required: true },
  markets: { type: Array, default: () => [] },
})

const loading = ref(true)
const error = ref(null)
const marketCurves = ref([])
const agentTrajectories = ref([])
const engagementSummary = ref([])
const topPosts = ref([])
const socialGraph = ref({ edges: [], mutual_follows: [] })
const trades = ref([])
const profiles = ref([])

async function fetchFile(url) {
  const resp = await fetch(url)
  if (!resp.ok) return null
  return resp.json()
}

onMounted(async () => {
  try {
    const { files } = await getSimData(props.jobId)
    const [mc, at, es, tp] = await Promise.all([
      fetchFile(files['market_curves.json']),
      fetchFile(files['agent_trajectories.json']),
      fetchFile(files['engagement_summary.json']),
      fetchFile(files['top_posts.json']),
    ])
    marketCurves.value = mc || []
    agentTrajectories.value = at || []
    engagementSummary.value = es || []
    topPosts.value = tp || []
    const [sg, tr, pr] = await Promise.all([
      fetchFile(files['social_graph.json']),
      fetchFile(files['trades.json']),
      fetchFile(files['profiles.json']),
    ])
    socialGraph.value = sg || { edges: [], mutual_follows: [] }
    trades.value = tr || []
    profiles.value = pr || []
  } catch (err) {
    error.value = 'Simulation data not available.'
    console.error('Failed to load sim data:', err)
  } finally {
    loading.value = false
  }
})
</script>
