<template>
  <div class="animate-pulse bg-ocean-deep border border-mist-depth rounded-2xl p-5 space-y-3">
    <div class="h-4 bg-mist-depth rounded w-3/4" />
    <div class="h-3 bg-mist-depth/60 rounded w-1/2" />
    <div v-if="lines > 0" class="space-y-2 mt-4">
      <div v-for="i in lines" :key="i" class="h-3 bg-mist-depth/40 rounded" :style="{ width: (90 - i * 10) + '%' }" />
    </div>
  </div>
</template>

<script setup>
defineProps({ lines: { type: Number, default: 2 } })
</script>
