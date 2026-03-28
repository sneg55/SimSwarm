<template>
  <div ref="containerRef" class="bg-ocean-deep border border-mist-depth rounded-2xl p-7">
    <div v-for="bar in bars" :key="bar.label" class="flex items-center gap-4 mb-4 last:mb-0">
      <span class="text-sm font-medium text-mist-drift min-w-[120px]">{{ bar.label }}</span>
      <div class="flex-1 h-2 bg-ocean-abyss rounded-full overflow-hidden">
        <div class="h-full rounded-full transition-[width] duration-[1.5s] ease-smooth"
          :style="{ width: (visible ? bar.width : 0) + '%', background: bar.gradient }" />
      </div>
      <span class="font-mono text-sm min-w-[48px] text-right" :style="{ color: bar.valueColor }">{{ bar.value }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

defineProps({
  bars: { type: Array, required: true },
})

const containerRef = ref(null)
const visible = ref(false)
let observer = null

onMounted(() => {
  observer = new IntersectionObserver(
    ([entry]) => { if (entry.isIntersecting) visible.value = true },
    { threshold: 0.3 }
  )
  if (containerRef.value) observer.observe(containerRef.value)
})

onUnmounted(() => observer?.disconnect())
</script>
