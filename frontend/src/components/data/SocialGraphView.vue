<template>
  <div class="bg-ocean-deep border border-mist-depth rounded-2xl p-5">
    <div class="text-xs font-semibold uppercase tracking-wider text-mist-slate mb-3">Social Graph</div>
    <template v-if="graph.edges && graph.edges.length">
      <div ref="containerRef" class="relative" style="height: 300px;">
        <canvas ref="canvasRef" class="w-full h-full" style="display:block;" />
      </div>
      <div class="flex gap-4 mt-2 text-[10px] text-mist-slate">
        <span>
          <InfoTooltip copyKey="socialGraphView.nodeSize">Nodes = agents</InfoTooltip>
          · Edges = follows ·
          <InfoTooltip copyKey="socialGraphView.mutualEdge"><span class="text-ocean-cyan">Bright edges</span> = mutual follows</InfoTooltip>
        </span>
      </div>
    </template>
    <div v-else class="flex items-center justify-center py-12 text-xs text-mist-slate">
      No social connections detected — agents didn't follow each other in this simulation.
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { getEntityColor } from '../graph/graphColors.js'
import InfoTooltip from '../InfoTooltip.vue'

const props = defineProps({
  graph: { type: Object, default: () => ({ edges: [], mutual_follows: [] }) },
})

const containerRef = ref(null)
const canvasRef = ref(null)

let ctx = null
let W = 0, H = 0
let nodes = []
let edges = []
let mutualSet = new Set()
let animFrame = null

function setup() {
  if (!canvasRef.value || !containerRef.value) return
  W = containerRef.value.clientWidth
  H = containerRef.value.clientHeight
  const dpr = window.devicePixelRatio || 1
  canvasRef.value.width = W * dpr
  canvasRef.value.height = H * dpr
  canvasRef.value.style.width = W + 'px'
  canvasRef.value.style.height = H + 'px'
  ctx = canvasRef.value.getContext('2d')
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
}

function buildGraph() {
  const gEdges = props.graph.edges || []
  const mutual = props.graph.mutual_follows || []
  const agentMap = {}
  for (const e of gEdges) {
    if (!agentMap[e.follower_id]) agentMap[e.follower_id] = { id: e.follower_id, name: e.follower_name, followers: 0 }
    if (!agentMap[e.followee_id]) agentMap[e.followee_id] = { id: e.followee_id, name: e.followee_name, followers: 0 }
    agentMap[e.followee_id].followers++
  }
  nodes = Object.values(agentMap).map((a) => ({
    ...a,
    x: W / 2 + (Math.random() - 0.5) * W * 0.6,
    y: H / 2 + (Math.random() - 0.5) * H * 0.6,
    vx: 0, vy: 0,
    size: 3 + Math.sqrt(a.followers + 1) * 2,
    color: getEntityColor(a.name || 'Entity'),
  }))
  const nodeIdx = {}
  nodes.forEach((n, i) => { nodeIdx[n.id] = i })
  edges = gEdges.map(e => ({ from: nodeIdx[e.follower_id], to: nodeIdx[e.followee_id] })).filter(e => e.from !== undefined && e.to !== undefined)
  mutualSet = new Set()
  for (const m of mutual) mutualSet.add(`${Math.min(m.agent_a, m.agent_b)}-${Math.max(m.agent_a, m.agent_b)}`)
}

function isMutual(a, b) { return mutualSet.has(`${Math.min(a, b)}-${Math.max(a, b)}`) }

function animate() {
  if (!ctx) { animFrame = requestAnimationFrame(animate); return }
  ctx.clearRect(0, 0, W, H)
  for (let i = 0; i < nodes.length; i++) {
    const n = nodes[i]
    n.vx += (W / 2 - n.x) * 0.0001
    n.vy += (H / 2 - n.y) * 0.0001
    for (let j = i + 1; j < nodes.length; j++) {
      const m = nodes[j]
      const dx = m.x - n.x, dy = m.y - n.y
      const d = Math.sqrt(dx * dx + dy * dy)
      if (d < 60 && d > 0.5) {
        const f = 0.15 * (1 - d / 60)
        n.vx -= (dx / d) * f; n.vy -= (dy / d) * f
        m.vx += (dx / d) * f; m.vy += (dy / d) * f
      }
    }
    n.vx *= 0.95; n.vy *= 0.95
    n.x += n.vx; n.y += n.vy
    n.x = Math.max(10, Math.min(W - 10, n.x))
    n.y = Math.max(10, Math.min(H - 10, n.y))
  }
  for (const e of edges) {
    const a = nodes[e.from], b = nodes[e.to]
    if (!a || !b) continue
    const m = isMutual(a.id, b.id)
    ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y)
    ctx.strokeStyle = m ? 'rgba(34,211,238,0.4)' : 'rgba(30,41,59,0.3)'
    ctx.lineWidth = m ? 1.5 : 0.5; ctx.stroke()
  }
  for (const n of nodes) {
    ctx.beginPath(); ctx.arc(n.x, n.y, n.size, 0, Math.PI * 2)
    ctx.fillStyle = n.color; ctx.globalAlpha = 0.8; ctx.fill(); ctx.globalAlpha = 1
    if (n.size > 5) {
      ctx.font = '9px Inter'; ctx.fillStyle = 'rgba(241,245,249,0.5)'
      ctx.textAlign = 'center'; ctx.fillText(n.name, n.x, n.y + n.size + 10)
    }
  }
  animFrame = requestAnimationFrame(animate)
}

watch(() => props.graph, () => { buildGraph() }, { deep: true })
onMounted(() => { nextTick(() => { setup(); buildGraph(); animFrame = requestAnimationFrame(animate) }) })
onBeforeUnmount(() => { if (animFrame) cancelAnimationFrame(animFrame) })
</script>
