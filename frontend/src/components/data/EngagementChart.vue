<template>
  <div class="bg-ocean-deep border border-mist-depth rounded-2xl p-5">
    <div class="text-xs font-semibold uppercase tracking-wider text-mist-slate mb-3">Activity Over Time</div>
    <div class="relative" @mousemove="onHover" @mouseleave="hovered = null">
      <svg :viewBox="`0 0 ${W} ${H}`" class="w-full">
        <g v-for="(entry, i) in activeData" :key="i">
          <rect :x="barX(i)" :y="yScale(entry.total_posts + entry.total_likes + entry.total_comments)"
            :width="barW" :height="barH(entry.total_posts + entry.total_likes + entry.total_comments)"
            fill="#22D3EE" opacity="0.8" rx="2" />
          <rect :x="barX(i)" :y="yScale(entry.total_likes + entry.total_comments)"
            :width="barW" :height="barH(entry.total_likes + entry.total_comments)"
            fill="#6EE7B7" opacity="0.8" rx="2" />
          <rect :x="barX(i)" :y="yScale(entry.total_comments)"
            :width="barW" :height="barH(entry.total_comments)"
            fill="#A78BFA" opacity="0.8" rx="2" />
        </g>
      </svg>
      <div v-if="hovered"
        class="absolute pointer-events-none rounded-lg px-3 py-2 text-xs z-10 border"
        style="background: rgba(10,20,30,0.92); border-color: rgba(34,211,238,0.2); box-shadow: 0 10px 40px rgba(8,47,73,0.3);"
        :style="{ left: hovered.x + 'px', top: '8px', maxWidth: '240px' }">
        <div class="text-mist-slate">Round {{ hovered.round }}</div>
        <div><span style="color:#22D3EE;">Posts: {{ hovered.posts }}</span></div>
        <div><span style="color:#6EE7B7;">Likes: {{ hovered.likes }}</span></div>
        <div><span style="color:#A78BFA;">Comments: {{ hovered.comments }}</span></div>
        <div class="text-mist-slate">{{ hovered.agents }} active agents</div>
        <div class="border-t my-1.5" style="border-color: rgba(34,211,238,0.1);" />
        <div class="text-gray-400 text-[10px] leading-relaxed">{{ getTooltip('engagementChart.hoverMeaning')?.meaning }}</div>
      </div>
    </div>
    <div class="flex gap-4 mt-2 text-[10px] text-mist-slate">
      <span><span class="inline-block w-2 h-2 rounded-sm bg-[#22D3EE] mr-1 align-middle"></span>Posts</span>
      <span><span class="inline-block w-2 h-2 rounded-sm bg-[#6EE7B7] mr-1 align-middle"></span>Likes</span>
      <span><span class="inline-block w-2 h-2 rounded-sm bg-[#A78BFA] mr-1 align-middle"></span>Comments</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { getTooltip } from '../../data/tooltipCopy.js'

const props = defineProps({ data: { type: Array, default: () => [] } })

const W = 600, H = 140, PAD = 8
const hovered = ref(null)

const activeData = computed(() =>
  props.data.filter(e => (e.total_posts || 0) + (e.total_likes || 0) + (e.total_comments || 0) > 0)
)

const maxVal = computed(() => {
  let m = 1
  for (const e of activeData.value) {
    const total = (e.total_posts || 0) + (e.total_likes || 0) + (e.total_comments || 0)
    if (total > m) m = total
  }
  return m
})
const barW = computed(() => {
  if (!activeData.value.length) return 0
  const maxBarW = 40
  return Math.min(maxBarW, Math.max(8, (W - PAD * 2) / activeData.value.length - 2))
})
function barX(i) { return activeData.value.length ? PAD + (i / activeData.value.length) * (W - PAD * 2) : 0 }
function yScale(val) { return H - PAD - (val / maxVal.value) * (H - PAD * 2) }
function barH(val) { return (val / maxVal.value) * (H - PAD * 2) }

function onHover(e) {
  const rect = e.currentTarget.getBoundingClientRect()
  const mouseX = e.clientX - rect.left
  const idx = Math.floor((mouseX / rect.width) * activeData.value.length)
  if (idx < 0 || idx >= activeData.value.length) return
  const entry = activeData.value[idx]
  hovered.value = { x: mouseX, round: entry.round, posts: entry.total_posts, likes: entry.total_likes, comments: entry.total_comments, agents: entry.active_agents }
}
</script>
