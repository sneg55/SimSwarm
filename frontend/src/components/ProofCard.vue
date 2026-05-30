<template>
  <div class="bg-ocean-deep border border-mist-depth rounded-xl p-7 text-left transition-all duration-350 ease-spring hover:-translate-y-1 hover:border-ocean-teal">
    <p class="text-[15px] text-mist italic leading-relaxed mb-4">
      "{{ quote }}"
    </p>
    <div class="text-sm font-semibold text-mist-foam">{{ author }}</div>
    <div class="text-xs text-mist-slate">{{ role }}</div>
  </div>
</template>

<script setup>
defineProps({
  quote: { type: String, required: true },
  author: { type: String, required: true },
  role: { type: String, required: true },
})
</script>
