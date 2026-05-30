<template>
  <div class="fixed top-0 left-0 right-0 h-0.5 z-[100]">
    <div
      class="h-full bg-gradient-to-r from-ocean-cyan via-ocean-glow to-organic-violet shadow-[0_0_8px_rgba(34,211,238,0.4)]"
      :style="{ width: progress + '%' }"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const progress = ref(0)

function onScroll() {
  const el = document.documentElement
  progress.value = (el.scrollTop / (el.scrollHeight - el.clientHeight)) * 100
}

onMounted(() => window.addEventListener('scroll', onScroll, { passive: true }))
onUnmounted(() => window.removeEventListener('scroll', onScroll))
</script>
