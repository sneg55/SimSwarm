<template>
  <div class="grid grid-cols-3 gap-3">
    <div v-for="item in items" :key="item.label"
      class="bg-ocean-deep border border-mist-depth rounded-xl p-5 text-center transition-colors hover:border-ocean-teal">
      <div class="font-mono text-3xl font-bold tracking-tight mb-1" :style="{ color: item.color }">{{ item.value }}</div>
      <div class="text-xs text-mist-slate uppercase tracking-wider">{{ item.label }}</div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  items: { type: Array, required: true },
})
</script>
