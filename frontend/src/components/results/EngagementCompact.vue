<template>
  <div v-if="data.length" class="bg-ocean-deep border border-mist-depth rounded-2xl p-5">
    <div class="flex justify-between items-center mb-2">
      <div class="text-xs font-semibold uppercase tracking-wider text-mist-slate">Simulation Activity</div>
      <div class="text-xs text-mist-slate">{{ totalPosts }} posts · {{ totalLikes }} likes</div>
    </div>
    <div class="flex items-end gap-px" style="height: 40px;">
      <div v-for="(entry, i) in data" :key="i"
        class="flex-1 bg-ocean-cyan rounded-t-sm transition-all"
        :style="{ height: barHeight(entry) + '%', opacity: 0.5 + (barHeight(entry) / 200) }" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
})

const maxTotal = computed(() => {
  let m = 1
  for (const e of props.data) {
    const t = (e.total_posts || 0) + (e.total_likes || 0)
    if (t > m) m = t
  }
  return m
})

const totalPosts = computed(() => props.data.reduce((s, e) => s + (e.total_posts || 0), 0))
const totalLikes = computed(() => props.data.reduce((s, e) => s + (e.total_likes || 0), 0))

function barHeight(entry) {
  const t = (entry.total_posts || 0) + (entry.total_likes || 0)
  return Math.max(2, (t / maxTotal.value) * 100)
}
</script>
