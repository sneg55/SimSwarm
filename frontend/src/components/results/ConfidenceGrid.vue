<template>
  <div ref="gridRef" class="grid grid-cols-3 gap-3">
    <div v-for="(item, i) in items" :key="item.label"
      class="bg-ocean-deep border border-mist-depth rounded-xl p-5 text-center transition-all hover:border-ocean-teal"
      :style="{ transitionDelay: visible ? `${i * 100}ms` : '0ms' }"
      :class="visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-3'"
    >
      <div class="font-mono text-3xl font-bold tracking-tight mb-1 transition-all duration-700" :style="{ color: item.color }">
        {{ visible ? item.value : '0' }}
      </div>
      <div class="text-xs text-mist-slate uppercase tracking-wider">{{ item.label }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

defineProps({
  items: { type: Array, required: true },
})

const gridRef = ref(null)
const visible = ref(false)
let observer = null

onMounted(() => {
  observer = new IntersectionObserver(
    ([entry]) => { if (entry.isIntersecting) visible.value = true },
    { threshold: 0.3 }
  )
  if (gridRef.value) observer.observe(gridRef.value)
})

onUnmounted(() => observer?.disconnect())
</script>
